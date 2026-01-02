# src/ 디렉토리 설명

이 디렉토리는 ALD NL→SQL Stats API의 핵심 Python 모듈들을 포함합니다.

## 📋 파일 목록 및 역할

### 🚀 메인 애플리케이션

#### `app.py`
**역할**: FastAPI 웹 애플리케이션의 메인 진입점

**주요 기능**:
- FastAPI 앱 초기화 및 엔드포인트 정의
- 웹 UI 제공 (`/view`, `/plot`)
- JSON API 제공 (`/query`, `/api/*`)
- 데이터베이스 연결 관리
- 결과 포맷팅 및 차트 생성 조율

**주요 함수**:
- `validate_database()`: 데이터베이스 무결성 검증
- `format_value()`: 값 포맷팅 (소수점, 단위)
- `format_row()`: 행 데이터 포맷팅
- `make_summary()`: 결과 요약 생성 (interpreter 사용)
- `view()`: 메인 UI 페이지 렌더링
- `plot()`: 차트 이미지 생성
- `query()`: JSON API 엔드포인트

**주요 API 엔드포인트**:
- `GET /view`: 메인 UI 페이지
- `GET /api/query`: 표준 payload 반환 (JSON)
- `GET /api/plot`: 시계열 플롯 PNG 반환
- `GET /api/suggestions`: 질문 추천
- `GET /api/popular`: 인기 질문 목록

**의존성**:
- `nl_parse.py`: 질문 파싱
- `sql_builder.py`, `process_metrics.py`: SQL 생성
- `payload_builder.py`: 표준 payload 생성
- `interpreter.py`: 결과 해석
- `chart_templates.py`: 차트 생성 (Plotly)
- `plot_generator.py`: 시계열 플롯 (Matplotlib)
- `question_suggestions.py`: 질문 추천

---

### 🧠 자연어 처리

#### `nl_parse.py`
**역할**: 자연어 질문을 구조화된 `Parsed` 객체로 변환

**작동 원리**:
1. 정규표현식 기반 키워드 매칭
2. 집계 함수 추출 (평균, 최대, 최소, 표준편차 등)
3. 컬럼명 추출 (동의어 지원)
4. 필터 조건 추출 (trace_id, step_name, 날짜 범위)
5. 그룹핑 정보 추출 (공정별, 스텝별, 일별 등)
6. Top-N 및 정렬 방향 추출 ("상위 5개", "하위 3개")
7. 변동성/이상치 키워드 감지 → 자동 agg="std", order="desc"
8. 분석 유형 결정 (ranking, group_profile, comparison, stability)

**주요 함수**:
- `parse_question(text: str) -> Parsed`: 메인 파싱 함수
- `_pick_agg(text)`: 집계 함수 추출
- `_pick_col(text)`: 컬럼명 추출 (동의어 매핑)
- `_pick_group_by(text)`: 그룹핑 정보 추출
- `_pick_limit_and_order(text)`: Top-N 및 정렬 방향 추출

**Parsed 객체 구조**:
```python
@dataclass
class Parsed:
    agg: Agg                      # 집계 함수 (avg, max, min, std 등)
    col: Optional[str]            # 컬럼명 (pressact, tempact_u 등)
    trace_id: Optional[str]       # 공정 ID 필터
    group_by: Optional[str]       # 그룹핑 (trace_id, step_name 등)
    limit: Optional[int]          # LIMIT N (Top-N)
    order: Optional[Literal["desc", "asc"]]  # 정렬 방향
    analysis_type: AnalysisType   # 분석 유형
    is_overshoot: bool            # 공정 특화 지표 플래그
    is_outlier: bool
    is_trace_compare: bool
    # ... 기타 필드
```

**컬럼 동의어 매핑**:
- `pressact`: "챔버 압력", "압력", "압력 실측"
- `mfcmon_n2_1`: "질소 1", "n2-1", "퍼지 1"
- `tempact_u`: "상단 온도", "temp u"
- 등등...

---

### 🗄️ SQL 생성

#### `sql_builder.py`
**역할**: `Parsed` 객체를 기반으로 SQL 쿼리 생성 (기본 집계 함수)

**작동 원리**:
1. `Parsed` 객체 검증 (타입 체크)
2. 컬럼명 검증 (ALLOWED_COLS 화이트리스트)
3. WHERE 절 생성 (필터 조건)
4. GROUP BY 절 생성 (그룹핑)
5. 집계 함수 적용 (AVG, MAX, MIN, COUNT, STDDEV 등)
6. ORDER BY 및 LIMIT 적용

**주요 함수**:
- `build_sql(p: Parsed) -> Tuple[str, List]`: 메인 SQL 생성 함수
- `_build_filters(p)`: WHERE 절 생성
- `_resolve_column(col)`: 컬럼명 검증 및 해석
- `_get_agg_function(agg, col)`: 집계 함수 SQL 문자열 생성
- `_build_sql_template_*()`: SQL 템플릿별 생성 함수

**SQL 스키마 보장**:
- **단일 값**: `value, n, std`
- **그룹별**: `group_col, value, n, std, min_val, max_val`

**보안**:
- 컬럼명 화이트리스트 (`ALLOWED_COLS`)
- 파라미터화된 쿼리 사용 (SQL 인젝션 방지)

---

#### `process_metrics.py`
**역할**: 공정 특화 지표를 위한 SQL 생성 (overshoot, outlier, dwell time 등)

**특화 지표**:

1. **Overshoot** (`build_overshoot_sql`)
   - 계산: `MAX(col) - pressset` (최대값 - 설정값)
   - 사용: `"pressact overshoot top5"`

2. **Outlier Detection** (`build_outlier_detection_sql`)
   - 계산: z-score 기반 이상치 탐지 (z > 1.0)
   - 공정별 이상치 비율 계산
   - 사용: `"pressact 이상치 top5"`

3. **Dwell Time** (`build_dwell_time_sql`)
   - 계산: 각 단계(step)의 체류 시간 (초)
   - 사용: `"standard_trace_001 스텝별 체류시간"`

4. **Stable Average** (`build_stable_avg_sql`)
   - 계산: 안정화 구간 평균 (초반 10% 제외)
   - 사용: `"step=STANDBY pressact 안정화 평균"`

5. **Trace Compare** (`build_trace_compare_sql`)
   - 계산: 두 공정(trace) 간 차이 분석
   - 사용: `"trace_001과 trace_002 pressact 비교"`

**작동 원리**:
- `Parsed` 객체의 플래그 (`is_overshoot`, `is_outlier` 등) 확인
- 해당 지표에 맞는 SQL 쿼리 생성
- 복잡한 윈도우 함수 및 서브쿼리 사용

---

### 📊 결과 해석

#### `interpreter.py`
**역할**: SQL 실행 결과(DataFrame)를 사람이 읽기 쉬운 자연어 문장으로 변환

**핵심 원칙**:
1. **SQL을 모른다**: df columns만 보고 해석
2. **해석 분기**: `(p.col, p.agg, p.group_by)`로 결정
3. **스키마 보장**: `build_sql`이 일정한 스키마 보장

**주요 함수**:
- `interpret_single(p, df)`: 단일 값 해석
  - 예: `"챔버 압력 평균은 358.354 Torr이며, 정상 범위(0.3~0.6 Torr) 밖입니다. (표본 2,429,600개, 표준편차 366.516)"`

- `interpret_group(p, df, topn=5)`: 그룹별 결과 해석
  - 예: `"단계명별 챔버 압력 평균 결과입니다. (총 47개 그룹)\n값 범위: 0.006 ~ 754.1\n상위 5개: ..."`

- `interpret(p, df, topn=5)`: 통합 해석기 (자동 분기)

**정상 범위 체크**:
- `semantic_registry.yaml`에서 메타데이터 조회
- `normal_range`가 있고 `unit`이 있으면 범위 판정 (평균값만)
- 범위 정보가 없으면 단위만 표시

**라벨 매핑**:
- `semantic_registry.yaml`에서 컬럼 설명(description) 자동 조회
- `AGG_LABEL`: 집계 함수 → 한글 라벨 (내부 딕셔너리)

---

### 📈 차트 생성

#### `chart_templates.py`
**역할**: 분석 유형에 따라 적절한 차트 템플릿을 적용

**작동 원리**:
1. 분석 유형(`analysis_type`)에 따라 차트 템플릿 선택
2. 고정된 차트 스타일 적용 (색상, 레이아웃 등)
3. 데이터에 맞게 차트 그리기

**차트 템플릿**:
- **ranking**: 가로 막대 (상위 3개 강조)
- **group_profile**: 세로 막대 또는 라인
- **comparison**: 그룹 막대 (두 값을 나란히)
- **stability**: 막대 또는 박스 플롯

**주요 함수**:
- `get_chart_template(analysis_type)`: 차트 설정 반환
- `apply_chart_template(...)`: 차트 그리기 (템플릿별 분기)
- `_draw_horizontal_bar()`: 가로 막대 그리기
- `_draw_bar()`: 세로 막대 그리기
- `_draw_line()`: 라인 차트 그리기
- `_draw_grouped_bar()`: 그룹 막대 그리기

**자동 조정 규칙**:
- 스텝 개수 > 12: Top 7 + Others로 요약
- 값 분포가 극단적: 로그축 또는 컷

---

### 🔧 데이터 처리

#### `preprocess_duckdb.py`
**역할**: CSV 파일들을 DuckDB 데이터베이스로 변환

**작동 원리**:
1. `data_in/*.csv` 파일 읽기
2. 컬럼명 정규화 (`slugify`)
3. `trace_id` 생성 (파일명에서 추출)
4. `timestamp` 생성 (Date + Time 결합)
5. `traces` 테이블에 저장
6. `traces_dedup` 뷰 생성 (중복 제거)
7. 시간 축 표준화 (`time_bucket_second`, `epoch_ms`)
8. `catalog_physical.json` 자동 생성 (컬럼 분류)

**중복 제거 뷰**:
- 키: `(trace_id, timestamp)`
- 중복 시 마지막 행 선택 (tie-breaker: `filename DESC, time DESC, no DESC`)

**물리적 카탈로그 생성**:
- 모든 컬럼을 자동 분류 (meta, pressure, temp, gas, apc, rf, valve, aux, other)
- `catalog_physical.json` 저장

**실행 방법**:
```bash
python -m src.preprocess_duckdb
```

---

#### `semantic_resolver.py`
**역할**: Semantic ID를 Physical 컬럼으로 해석 (Phase 1, 향후 확장용)

**작동 원리**:
1. `semantic_registry.yaml` 파일 로드
2. Semantic ID → Physical 컬럼 매핑 생성
3. 자연어 alias → Semantic ID 매핑 생성

**현재 상태**:
- Phase 1 구현 (기본 매핑)
- 향후 확장: Semantic 레이어 도입 시 활용

**주요 함수**:
- `load_registry()`: YAML 파일 로드
- `build_alias_map()`: alias → semantic ID 매핑
- `resolve_semantic_to_physical()`: semantic ID → physical 컬럼

---

### 🖥️ CLI 도구

#### `run_query.py`
**역할**: 터미널에서 직접 질의를 실행하는 CLI 인터페이스

**사용 방법**:
```bash
python -m src.run_query
```

**기능**:
- 질문 입력 받기
- Parsed 객체 출력
- SQL 쿼리 출력
- 결과 DataFrame 출력

**디버깅 용도**:
- 파싱 결과 확인
- SQL 쿼리 검증
- 데이터 확인

---

## 🔄 모듈 간 의존성

```
app.py
├── nl_parse.py (질문 파싱)
├── sql_builder.py (기본 SQL)
├── process_metrics.py (특화 SQL)
├── payload_builder.py (표준 payload 생성)
├── interpreter.py (결과 해석)
├── chart_templates.py (차트 생성)
├── plot_generator.py (Matplotlib 플롯)
└── question_suggestions.py (질문 추천)

nl_parse.py → Parsed 객체
    ↓
sql_builder.py / process_metrics.py → SQL 쿼리
    ↓
DuckDB → DataFrame
    ↓
payload_builder.py → 표준 payload (question, summary, sql, columns, data, meta)
    ├── interpreter.py → 자연어 요약
    └── build_meta() → 시각화 힌트
        ↓
app.py → UI 표시 / API 응답
    ├── chart_templates.py → Plotly 차트 (집계)
    └── plot_generator.py → Matplotlib 플롯 (시계열)
```

## 📝 코드 스타일

- **타입 힌팅**: 가능한 곳에 타입 힌트 추가
- **독스트링**: 주요 함수에 독스트링 작성
- **에러 처리**: 명확한 에러 메시지 제공
- **보안**: SQL 인젝션 방지 (화이트리스트, 파라미터화)

## 🧪 테스트

해석 레이어 테스트:
```bash
python test_interpreter.py
```

CLI 테스트:
```bash
python -m src.run_query
```

