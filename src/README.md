# src/ 디렉토리 설명

이 디렉토리는 ALD NL→SQL Stats API의 핵심 Python 모듈들을 포함합니다. 모든 파일은 실제 실행에 사용되며, 각 모듈은 명확한 역할을 가집니다.

## 📋 파일 목록 및 역할

### 🚀 메인 애플리케이션

#### `app.py`
**역할**: FastAPI 웹 애플리케이션의 메인 진입점

**실제 사용**: ✅ 서버 실행 시 메인 진입점

**주요 기능**:
- FastAPI 앱 초기화 및 엔드포인트 정의
- 웹 UI 제공 (`/view`, `/plot`)
- JSON API 제공 (`/query`, `/api/*`)
- 데이터베이스 연결 관리
- 결과 포맷팅 및 차트 생성 조율

**주요 함수**:
- `validate_database()`: 데이터베이스 무결성 검증 (서버 시작 시)
- `format_value()`: 값 포맷팅 (소수점, 단위) - UI 표시용
- `format_row()`: 행 데이터 포맷팅 - 테이블 표시용
- `make_summary()`: 결과 요약 생성 (interpreter 사용)
- `view()`: 메인 UI 페이지 렌더링 (`GET /view`)
- `plot()`: 차트 이미지 생성 (`GET /plot`)
- `query()`: JSON API 엔드포인트 (`POST /query`, `GET /api/query`)

**주요 API 엔드포인트**:
- `GET /view`: 메인 UI 페이지 (질문 입력, 결과 표시)
- `GET /plot`: PNG 차트 이미지 생성
- `POST /query`: 표준 payload 반환 (JSON)
- `GET /api/query`: GET 방식 표준 payload 반환
- `GET /api/plot`: 시계열 플롯 PNG 반환
- `GET /api/suggestions`: 질문 추천
- `GET /api/popular`: 인기 질문 목록
- `GET /api/columns`: 사용 가능한 컬럼 목록
- `GET /api/traces`: 공정 ID 목록
- `GET /api/steps`: 단계명 목록
- `GET /api/csv`: CSV 다운로드
- `GET /api/range`: 데이터 범위 정보

**의존성**:
- `nl_parse_v2.py`: 질문 파싱
- `sql_builder.py`, `process_metrics.py`: SQL 생성
- `payload_builder.py`: 표준 payload 생성
- `interpreter.py`: 결과 해석
- `chart_templates.py`: 차트 생성 (Matplotlib)
- `plot_generator.py`: 시계열 플롯 (Matplotlib)
- `question_suggestions.py`: 질문 추천

**동작 흐름**:
```
사용자 질문 입력
    ↓
parse_question() → Parsed 객체
    ↓
build_sql() 또는 process_metrics 함수 → SQL 쿼리
    ↓
DuckDB 실행 → DataFrame
    ↓
format_row() → 포맷팅된 데이터
    ↓
make_summary() → 자연어 요약
    ↓
UI 표시 또는 JSON 응답
```

---

### 🧠 자연어 처리

#### `nl_parse_v2.py`
**역할**: 자연어 질문을 구조화된 `Parsed` 객체로 변환

**실제 사용**: ✅ 모든 질문 처리에 사용됨

**작동 원리**:
1. **정규화**: `domain.rules.normalization`을 통해 질문 정규화
   - 소문자 변환
   - 동의어 치환 (챔버 압력 → pressact)
   - 패턴 정규화 (top5 → top5, step=STANDBY → step_name=STANDBY)

2. **집계 함수 추출**: `_pick_agg()`
   - 도메인 메타데이터(`domain/schema/metrics.yaml`)에서 지표 찾기
   - "평균", "최대", "최소", "표준편차" 등 추출

3. **컬럼명 추출**: `_pick_col()`
   - 도메인 메타데이터(`domain/schema/columns.yaml`)에서 컬럼 찾기
   - 키 직접 매칭 (가중치 3.0)
   - 동의어 매칭 (가중치 2.5)
   - 도메인명 매칭 (가중치 1.2)
   - 가장 높은 가중치 컬럼 선택

4. **모호성 해결**: `domain.rules.resolution.resolve_column_from_text()`
   - 여러 컬럼이 매칭될 때 우선순위 규칙 적용
   - 구체적 센서 우선 (vg11 > pressact)
   - 컨텍스트 키워드 기반 해결

5. **필터 조건 추출**:
   - `trace_id`: "standard_trace_001" 같은 공정 ID
   - `step_name`: "STANDBY", "B.FILL" 같은 단계명
   - `date_start`, `date_end`: 날짜 범위

6. **그룹핑 정보 추출**: `_pick_group_by()`
   - "스텝별" → `group_by="step_name"`
   - "공정별" → `group_by="trace_id"`
   - "일별" → `group_by="date"`

7. **Top-N 및 정렬 방향 추출**: `_pick_limit_and_order()`
   - "상위 5개" → `limit=5, order="desc"`
   - "하위 3개" → `limit=3, order="asc"`

8. **분석 유형 결정**: `analysis_type`
   - `ranking`: Top-N 질문
   - `group_profile`: 그룹별 프로파일
   - `comparison`: 비교 분석
   - `stability`: 안정성 분석

**주요 함수**:
- `parse_question(text: str) -> Parsed`: 메인 파싱 함수
- `_pick_agg(text, validator)`: 집계 함수 추출
- `_pick_col(text, validator)`: 컬럼명 추출 (동의어 매핑)
- `_pick_group_by(text)`: 그룹핑 정보 추출
- `_pick_limit_and_order(text)`: Top-N 및 정렬 방향 추출

**Parsed 객체 구조**:
```python
@dataclass
class Parsed:
    agg: Agg                      # 집계 함수 (avg, max, min, std 등)
    col: Optional[str]            # 컬럼명 (pressact, tempact_u 등)
    trace_id: Optional[str]       # 공정 ID 필터
    trace_ids: List[str]          # 여러 공정 ID (비교용)
    step_name: Optional[str]      # 단계명 필터
    step_names: List[str]         # 여러 단계명 (비교용)
    group_by: Optional[str]        # 그룹핑 (trace_id, step_name 등)
    limit: Optional[int]           # LIMIT N (Top-N)
    order: Optional[Literal["desc", "asc"]]  # 정렬 방향
    analysis_type: AnalysisType    # 분석 유형
    is_overshoot: bool             # 공정 특화 지표 플래그
    is_outlier: bool
    is_dwell_time: bool
    is_stable_avg: bool
    is_trace_compare: bool
    date_start: Optional[str]      # 시작 날짜
    date_end: Optional[str]        # 종료 날짜
    chart_type: Optional[str]      # 차트 타입 힌트
```

**사용 예시**:
```python
from src.nl_parse_v2 import parse_question

parsed = parse_question("챔버 압력 평균")
# → Parsed(col="pressact", agg="avg", group_by=None, ...)

parsed = parse_question("스텝별 압력 평균 상위 5개")
# → Parsed(col="pressact", agg="avg", group_by="step_name", limit=5, order="desc", analysis_type="ranking")
```

---

### 🗄️ SQL 생성

#### `sql_builder.py`
**역할**: `Parsed` 객체를 기반으로 SQL 쿼리 생성 (기본 집계 함수)

**실제 사용**: ✅ 모든 기본 SQL 쿼리 생성에 사용됨

**작동 원리**:
1. `Parsed` 객체 검증 (타입 체크)
2. 컬럼명 검증 (ALLOWED_COLS 화이트리스트 - 향후 semantic_resolver로 교체 예정)
3. WHERE 절 생성 (`_build_filters()`)
   - `trace_id` 필터
   - `step_name` 필터
   - 날짜 범위 필터
4. GROUP BY 절 생성 (그룹핑)
5. 집계 함수 적용 (`_get_agg_function()`)
   - AVG, MAX, MIN, COUNT, STDDEV, QUANTILE_CONT 등
6. ORDER BY 및 LIMIT 적용

**주요 함수**:
- `build_sql(p: Parsed, include_stats: bool = True) -> Tuple[str, List]`: 메인 SQL 생성 함수
- `_build_filters(p) -> Tuple[str, List]`: WHERE 절 생성
- `_resolve_column(col) -> str`: 컬럼명 검증 및 해석
- `_get_agg_function(agg, col) -> str`: 집계 함수 SQL 문자열 생성
- `_build_sql_template_single_value()`: 단일 값 SQL 템플릿
- `_build_sql_template_grouped()`: 그룹별 SQL 템플릿

**SQL 스키마 보장**:
- **단일 값**: `value, n, std`
- **그룹별**: `group_col, value, n, std, min_val, max_val`

**보안**:
- 컬럼명 화이트리스트 (`ALLOWED_COLS`)
- 파라미터화된 쿼리 사용 (SQL 인젝션 방지)

**사용 예시**:
```python
from src.sql_builder import build_sql
from src.nl_parse_v2 import parse_question

parsed = parse_question("챔버 압력 평균")
sql, params = build_sql(parsed)
# → ("SELECT AVG(pressact) AS value, COUNT(*) AS n, STDDEV(pressact) AS std FROM traces_dedup", [])
```

---

#### `process_metrics.py`
**역할**: 공정 특화 지표를 위한 SQL 생성 (overshoot, outlier, dwell time 등)

**실제 사용**: ✅ 특수 지표 질문 처리에 사용됨

**특화 지표**:

1. **Overshoot** (`build_overshoot_sql`)
   - 계산: `MAX(col) - pressset` (최대값 - 설정값)
   - 사용: `"pressact overshoot top5"`
   - SQL: 복잡한 윈도우 함수 사용

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
   - 결과: `step_name, diff, trace1_avg, trace2_avg`

**작동 원리**:
- `Parsed` 객체의 플래그 (`is_overshoot`, `is_outlier` 등) 확인
- 해당 지표에 맞는 SQL 쿼리 생성
- 복잡한 윈도우 함수 및 서브쿼리 사용

**사용 예시**:
```python
from src.process_metrics import build_overshoot_sql
from src.nl_parse_v2 import parse_question

parsed = parse_question("압력 오버슈트 상위 5개")
# → parsed.is_overshoot = True

sql, params = build_overshoot_sql(parsed)
# → 복잡한 SQL 쿼리 (윈도우 함수 포함)
```

---

### 📊 결과 해석

#### `interpreter.py`
**역할**: SQL 실행 결과(DataFrame)를 사람이 읽기 쉬운 자연어 문장으로 변환

**실제 사용**: ✅ 모든 결과 요약 생성에 사용됨

**핵심 원칙**:
1. **SQL을 모른다**: df columns만 보고 해석
2. **해석 분기**: `(p.col, p.agg, p.group_by)`로 결정
3. **스키마 보장**: `build_sql`이 일정한 스키마 보장
4. **메타데이터 활용**: `semantic_registry.yaml`에서 단위, 정상 범위 조회

**주요 함수**:
- `interpret_single(p, df) -> str`: 단일 값 해석
  - 예: `"챔버 압력 평균은 358.354 Torr이며, 정상 범위(0.3~0.6 Torr) 밖입니다. (표본 2,429,600개, 표준편차 366.516)"`

- `interpret_group(p, df, topn=5) -> str`: 그룹별 결과 해석
  - 예: `"단계명별 챔버 압력 평균 결과입니다. (총 47개 그룹)\n값 범위: 0.006 ~ 754.1\n상위 5개: ..."`

- `interpret(p, df, topn=5) -> str`: 통합 해석기 (자동 분기)
  - `group_by`가 있으면 `interpret_group()` 호출
  - 없으면 `interpret_single()` 호출

**정상 범위 체크**:
- `semantic_registry.yaml`에서 메타데이터 조회
- `normal_range`가 있고 `unit`이 있으면 범위 판정 (평균값만)
- 범위 정보가 없으면 단위만 표시

**라벨 매핑**:
- `semantic_registry.yaml`에서 컬럼 설명(description) 자동 조회
- `AGG_LABEL`: 집계 함수 → 한글 라벨 (내부 딕셔너리)

**사용 예시**:
```python
from src.interpreter import interpret
from src.nl_parse_v2 import parse_question
import duckdb

parsed = parse_question("챔버 압력 평균")
sql, params = build_sql(parsed)
df = con.execute(sql, params).df()

summary = interpret(parsed, df)
# → "챔버 압력 평균은 358.354 Torr이며, 정상 범위(0.3~0.6 Torr) 밖입니다."
```

---

### 📈 차트 생성

#### `chart_templates.py`
**역할**: 분석 유형에 따라 적절한 차트 템플릿을 적용

**실제 사용**: ✅ `/plot` 엔드포인트에서 차트 생성에 사용됨

**작동 원리**:
1. 분석 유형(`analysis_type`)에 따라 차트 템플릿 선택 (`get_chart_template()`)
2. 고정된 차트 스타일 적용 (색상, 레이아웃 등)
3. 데이터에 맞게 차트 그리기 (`apply_chart_template()`)

**차트 템플릿**:
- **ranking**: 가로 막대 (상위 3개 강조)
- **group_profile**: 세로 막대 또는 라인
- **comparison**: 그룹 막대 (두 값을 나란히)
- **stability**: 막대 또는 박스 플롯

**주요 함수**:
- `get_chart_template(analysis_type) -> ChartConfig`: 차트 설정 반환
- `apply_chart_template(ax, df, x_col, y_col, config, parsed)`: 차트 그리기 (템플릿별 분기)
- `_draw_horizontal_bar()`: 가로 막대 그리기
- `_draw_bar()`: 세로 막대 그리기
- `_draw_line()`: 라인 차트 그리기
- `_draw_grouped_bar()`: 그룹 막대 그리기

**자동 조정 규칙**:
- 스텝 개수 > 12: Top 7 + Others로 요약
- 값 분포가 극단적: 로그축 또는 컷

**사용 예시**:
```python
from src.chart_templates import get_chart_template, apply_chart_template

config = get_chart_template("ranking")
# → {"chart_type": "horizontal_bar", "use_top_n": True, ...}

apply_chart_template(ax, df, "step_name", "value", config, parsed_obj)
# → 차트 그리기
```

---

#### `plot_generator.py`
**역할**: 시계열 Plot 생성 (Matplotlib)

**실제 사용**: ✅ `/api/plot` 엔드포인트에서 시계열 차트 생성에 사용됨

**주요 함수**:
- `plot_timeseries(df, title, x_col, y_col, unit) -> BytesIO`: 시계열 Plot 생성

**동작**:
1. DataFrame에서 timestamp와 value 컬럼 추출
2. Matplotlib로 시계열 라인 차트 생성
3. PNG 이미지로 변환하여 BytesIO 반환

**사용 예시**:
```python
from src.plot_generator import plot_timeseries

buf = plot_timeseries(df, title="압력 시계열", x_col="timestamp", y_col="value", unit="Torr")
# → PNG 이미지 BytesIO 객체
```

---

### 🔧 데이터 처리

#### `preprocess_duckdb.py`
**역할**: CSV 파일들을 DuckDB 데이터베이스로 변환

**실제 사용**: ✅ 데이터 준비 단계에서 실행됨

**작동 원리**:
1. `data/*.csv` 파일 읽기 (각 CSV 파일 = 1개 공정)
2. 파일명에서 공정 ID(`trace_id`) 추출
   - 예: `standard_trace_001.csv` → `trace_id = "standard_trace_001"`
3. 컬럼명 정규화 (`slugify()`)
   - 공백, 특수문자 제거
   - 소문자 변환
   - 예: `PressAct` → `pressact`, `TempAct_U` → `tempact_u`
4. `timestamp` 생성 (Date + Time 결합)
5. `traces` 테이블에 저장
6. `traces_dedup` 뷰 생성 (중복 제거)
   - 키: `(trace_id, timestamp)`
   - 중복 시 마지막 행 선택
7. 시간 축 표준화 (`time_bucket_second`, `epoch_ms`)
8. `catalog_physical.json` 자동 생성 (컬럼 분류)

**중복 제거 뷰**:
- 키: `(trace_id, timestamp)`
- 중복 시 마지막 행 선택 (tie-breaker: `filename DESC, time DESC, no DESC`)

**물리적 카탈로그 생성**:
- 모든 컬럼을 자동 분류 (meta, pressure, temp, gas, apc, rf, valve, aux, other)
- `config/catalog_physical.json` 저장

**실행 방법**:
```bash
python -m src.preprocess_duckdb
```

**결과물**:
- `data_out/ald.duckdb`: DuckDB 데이터베이스 파일
- `config/catalog_physical.json`: 컬럼 카탈로그

---

#### `semantic_resolver.py`
**역할**: Semantic ID를 Physical 컬럼으로 해석 및 메타데이터 조회

**실제 사용**: ✅ `interpreter.py`, `payload_builder.py`, `app.py`에서 사용됨

**작동 원리**:
1. `config/semantic_registry.yaml` 파일 로드 (캐싱)
2. Semantic ID → Physical 컬럼 매핑 생성
3. 자연어 alias → Semantic ID 매핑 생성
4. Physical 컬럼 → 메타데이터 조회

**주요 함수**:
- `load_registry() -> Dict`: YAML 파일 로드 (싱글톤)
- `build_alias_map() -> Dict`: alias → semantic ID 매핑
- `resolve_semantic_to_physical(semantic_id) -> List[str]`: semantic ID → physical 컬럼
- `get_metadata_by_physical_column(physical_col) -> Optional[Dict]`: 메타데이터 조회

**메타데이터 구조**:
```python
{
    "unit": "Torr",                    # 단위
    "description": "챔버 압력",        # 한글 설명
    "normal_range": {                  # 정상 범위 (선택)
        "min": 0.3,
        "max": 0.6
    }
}
```

**사용 예시**:
```python
from src.semantic_resolver import get_metadata_by_physical_column

metadata = get_metadata_by_physical_column("pressact")
# → {"unit": "Torr", "description": "챔버 압력", ...}
```

---

### 📦 API 응답 생성

#### `payload_builder.py`
**역할**: UI용 표준 payload 생성

**실제 사용**: ✅ `/query`, `/api/query` 엔드포인트에서 사용됨

**주요 함수**:
- `build_payload(question: str, con) -> Dict`: 표준 payload 생성
- `build_meta(p: Parsed) -> Dict`: 시각화 메타데이터 생성

**표준 payload 구조**:
```python
{
    "ok": True,
    "question": "챔버 압력 평균",
    "question_normalized": "pressact avg",
    "parsed": {...},              # Parsed 객체 (dict)
    "sql": "SELECT ...",          # 실행된 SQL
    "summary": "챔버 압력...",    # 자연어 요약
    "columns": ["value", "n"],    # 결과 컬럼명
    "data": [...],                # 포맷팅된 데이터
    "meta": {                     # 시각화 힌트
        "chart": "bignum",
        "title": "챔버 압력 평균",
        "unit": "Torr"
    }
}
```

**동작 흐름**:
```
질문 문자열
    ↓
parse_question() → Parsed 객체
    ↓
build_sql() → SQL 쿼리
    ↓
DuckDB 실행 → DataFrame
    ↓
interpret() → 자연어 요약
    ↓
build_meta() → 시각화 메타데이터
    ↓
표준 payload 반환
```

---

### 💡 질문 추천

#### `question_suggestions.py`
**역할**: 질문 추천 및 자동완성

**실제 사용**: ✅ `/api/suggestions`, `/api/popular` 엔드포인트에서 사용됨

**주요 함수**:
- `get_suggestions(query: str, limit: int) -> List[Dict]`: 검색어 기반 추천
- `get_category_suggestions(category: str) -> List[str]`: 카테고리별 추천
- `get_popular_questions(limit: int) -> List[str]`: 인기 질문 목록

**동작 원리**:
1. 템플릿 기반 질문 목록 관리
2. 검색어 부분 매칭
3. 카테고리별 필터링

**사용 예시**:
```python
from src.question_suggestions import get_popular_questions

questions = get_popular_questions(5)
# → ["압력 평균", "스텝별 압력 평균", ...]
```

---

### 🛠️ 유틸리티

#### `utils/parsed.py`
**역할**: Parsed 객체 변환 유틸리티

**실제 사용**: ✅ `app.py`에서 Parsed 객체를 dict로 변환할 때 사용됨

**주요 함수**:
- `to_parsed_dict(parsed_obj) -> dict`: Parsed 객체를 딕셔너리로 변환

**하위 호환성**:
- `agg` / `metric` 통합
- `col` / `column` 통합
- `filters`, `flags` 구조 평탄화

---

#### `utils/mpl_korean.py`
**역할**: Matplotlib 한글 폰트 설정

**실제 사용**: ✅ `app.py` import 시 자동 실행됨

**주요 함수**:
- `setup_korean_font()`: 한글 폰트 자동 감지 및 설정

**동작**:
1. 시스템에 설치된 폰트 목록 확인
2. 한글 폰트 우선순위: NanumGothic > NanumBarunGothic > Noto Sans CJK KR
3. 폰트가 없으면 DejaVu Sans 사용 (한글 깨짐 가능)

---

### 🧪 테스트 전용 모듈 (삭제됨)

**참고**: `src/charts/` 디렉토리는 테스트 전용 모듈이었으나 삭제되었습니다. 실제 차트 생성은 `chart_templates.py`와 `plot_generator.py`를 사용합니다.

---

## 🔄 모듈 간 의존성

```
app.py (메인 진입점)
├── nl_parse_v2.py (질문 파싱)
│   └── domain/rules/normalization.py (정규화)
│   └── domain/rules/resolution.py (모호성 해결)
│   └── domain/schema/*.yaml (메타데이터)
├── sql_builder.py (기본 SQL)
├── process_metrics.py (특화 SQL)
├── payload_builder.py (표준 payload 생성)
│   ├── interpreter.py (결과 해석)
│   └── semantic_resolver.py (메타데이터 조회)
├── chart_templates.py (차트 생성)
├── plot_generator.py (Matplotlib 플롯)
└── question_suggestions.py (질문 추천)

데이터 흐름:
질문 → nl_parse_v2 → Parsed 객체
    ↓
sql_builder / process_metrics → SQL 쿼리
    ↓
DuckDB → DataFrame
    ↓
payload_builder → 표준 payload
    ├── interpreter → 자연어 요약
    └── build_meta() → 시각화 힌트
        ↓
app.py → UI 표시 / API 응답
    ├── chart_templates → Matplotlib 차트
    └── plot_generator → 시계열 플롯
```

---

## 📝 코드 스타일

- **타입 힌팅**: 가능한 곳에 타입 힌트 추가
- **독스트링**: 주요 함수에 독스트링 작성
- **에러 처리**: 명확한 에러 메시지 제공
- **보안**: SQL 인젝션 방지 (화이트리스트, 파라미터화)

---

## 🧪 테스트

모듈별 테스트:
```bash
python tests/test_modules.py
```

파서 테스트:
```bash
python tests/test_parser.py
```

**참고**: 루트 디렉토리의 `test_interpreter.py`는 삭제되었습니다. 모든 테스트는 `tests/` 디렉토리에서 실행합니다.
