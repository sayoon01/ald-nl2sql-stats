# ALD NL2SQL - 자연어 질문을 SQL로 변환하는 시스템

ALD (Atomic Layer Deposition) 공정 데이터를 자연어 질문으로 조회할 수 있는 웹 애플리케이션입니다.

## 📋 목차

1. [프로젝트 개요](#프로젝트-개요)
2. [시작하기](#시작하기)
3. [프로젝트 구조](#프로젝트-구조)
4. [각 디렉토리 상세 설명](#각-디렉토리-상세-설명)
5. [각 파일 상세 설명](#각-파일-상세-설명)
6. [시스템 작동 원리](#시스템-작동-원리)
7. [사용 예시](#사용-예시)
8. [확장 방법](#확장-방법)

---

## 프로젝트 개요

이 프로젝트는 **자연어 질문을 SQL 쿼리로 변환**하여 ALD 공정 데이터를 조회하는 시스템입니다.

### 주요 기능

- ✅ 자연어 질문 → SQL 변환
- ✅ 웹 인터페이스 제공 (FastAPI)
- ✅ 데이터 시각화 (Matplotlib)
- ✅ 도메인 메타데이터 기반 파싱
- ✅ 모호성 해결 (예: "압력" → pressact/vg11/vg12 등)

### 예시

```
사용자: "챔버 압력 평균"
  ↓
시스템: SELECT AVG(PressAct) FROM traces
  ↓
결과: 3.456 mTorr
```

---

## 시작하기

### 1. 환경 설정

```bash
# 프로젝트 디렉토리로 이동
cd ~/yune/ald-nl2sql

# 가상 환경 활성화
source venv/bin/activate

# 의존성 설치 (이미 설치되어 있음)
pip install -r requirements.txt
```

### 2. 데이터베이스 준비

```bash
# 더미 데이터 생성 (실제 CSV가 없을 경우)
python src/create_dummy_data.py

# 또는 실제 CSV 파일 전처리
python src/preprocess_duckdb.py
```

### 3. 서버 실행

```bash
# FastAPI 서버 시작
uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 웹 브라우저에서 접속

```
http://localhost:8000
```

---

## 프로젝트 구조

```
ald-nl2sql/
├── src/                    # 소스 코드
│   ├── app.py             # FastAPI 웹 애플리케이션
│   ├── nl_parse_v2.py     # 자연어 파서 (메인)
│   ├── nl_parse.py        # 자연어 파서 (레거시)
│   ├── sql_builder.py     # SQL 쿼리 생성기
│   ├── process_metrics.py # 지표 처리 로직
│   ├── run_query.py       # CLI 쿼리 테스트 도구
│   ├── preprocess_duckdb.py # CSV → DuckDB 변환
│   ├── create_dummy_data.py # 더미 데이터 생성
│   └── chart_templates.py # 차트 템플릿
├── domain/                 # 도메인 메타데이터 (프로젝트 심장부)
│   ├── schema/            # 스키마 정의
│   │   ├── columns.yaml   # 컬럼 메타데이터
│   │   ├── metrics.yaml   # 집계 함수 정의
│   │   ├── groups.yaml    # 그룹핑 정의
│   │   ├── units.yaml     # 단위 정의
│   │   ├── load_schema.py # YAML 로더
│   │   └── parsed_schema.json # Parsed 객체 스키마
│   ├── synonyms/          # 동의어 사전
│   │   ├── columns.yaml   # 컬럼 동의어
│   │   ├── metrics.yaml   # 지표 동의어
│   │   ├── groups.yaml    # 그룹핑 동의어
│   │   └── patterns.yaml  # 패턴 정규화 규칙
│   └── rules/             # 규칙 엔진
│       ├── normalization.py # 질문 정규화
│       ├── validation.py   # 도메인 규칙 검증
│       ├── resolution.py  # 모호성 해결
│       ├── fallback.py    # 기본값/추론 규칙
│       └── pressure_resolution.yaml # 모호성 해결 규칙
├── templates/              # HTML 템플릿
│   ├── index.html         # 메인 페이지
│   └── plot.html          # 차트 페이지
├── tests/                  # 테스트
│   ├── questions.jsonl    # 테스트 질문
│   ├── expected_parsed.jsonl # 예상 결과
│   └── test_parser.py     # 파서 테스트
├── data/                   # 원본 CSV 데이터 (선택)
├── data_out/               # 처리된 데이터
│   └── ald.duckdb         # DuckDB 데이터베이스
├── requirements.txt        # Python 의존성
├── README.md              # 이 파일
├── ARCHITECTURE.md        # 아키텍처 문서
├── PARSED_SCHEMA.md       # Parsed 객체 스키마 문서
└── venv/                  # 가상 환경 (gitignore)
```

---

## 각 디렉토리 상세 설명

### 📁 `src/` - 소스 코드

**역할**: 애플리케이션의 핵심 로직이 담긴 디렉토리

- **`app.py`**: FastAPI 웹 애플리케이션 메인 파일
  - HTTP 엔드포인트 정의 (`/`, `/query`, `/view`)
  - 질문 파싱 및 SQL 실행
  - 차트 생성 및 HTML 렌더링

- **`nl_parse_v2.py`**: 자연어 파서 (메인 버전)
  - 사용자 질문을 `Parsed` 객체로 변환
  - 도메인 메타데이터 기반 파싱
  - 모호성 해결 로직 포함

- **`nl_parse.py`**: 자연어 파서 (레거시 버전)
  - 하위 호환성을 위한 구버전 파서
  - `nl_parse_v2.py`가 실패할 경우 fallback

- **`sql_builder.py`**: SQL 쿼리 생성기
  - `Parsed` 객체를 SQL 쿼리로 변환
  - 집계 함수, 그룹핑, 필터링 처리

- **`process_metrics.py`**: 지표 처리 로직
  - 특수 지표 (overshoot, outlier 등) 처리
  - 커스텀 SQL 생성

- **`run_query.py`**: CLI 쿼리 테스트 도구
  - 터미널에서 직접 질문 테스트
  - 파싱 결과 및 SQL 확인

- **`preprocess_duckdb.py`**: CSV → DuckDB 변환
  - 원본 CSV 파일을 DuckDB로 변환
  - 데이터 전처리 및 인덱싱

- **`create_dummy_data.py`**: 더미 데이터 생성
  - 테스트용 더미 데이터 생성
  - 실제 CSV가 없을 때 사용

- **`chart_templates.py`**: 차트 템플릿
  - Matplotlib 차트 생성 로직
  - 한글 폰트 설정

### 📁 `domain/` - 도메인 메타데이터 (프로젝트 심장부)

**역할**: 모든 도메인 지식이 YAML과 Python 규칙으로 관리되는 디렉토리

#### `domain/schema/` - 스키마 정의

- **`columns.yaml`**: 컬럼 메타데이터
  - 도메인 키 ↔ CSV 실제 컬럼명 매핑
  - 예: `pressact` → `PressAct` (CSV 컬럼명)
  - 동의어, 단위, 물리적 타입 정의

- **`metrics.yaml`**: 집계 함수 정의
  - `avg`, `max`, `min`, `std`, `p95` 등
  - SQL 표현식 정의

- **`groups.yaml`**: 그룹핑 정의
  - `step_name`, `trace_id`, `day`, `hour` 등
  - SQL 표현식 정의

- **`units.yaml`**: 단위 정의
  - `mTorr`, `sccm`, `C` 등
  - 단위 변환 규칙

- **`load_schema.py`**: YAML 스키마 로더
  - `columns.yaml` 로드 및 파싱
  - `ColumnDef`, `DomainSchema` dataclass 제공

- **`parsed_schema.json`**: Parsed 객체 JSON 스키마
  - `Parsed` 객체의 표준 구조 정의
  - JSON 직렬화/역직렬화 스키마

#### `domain/synonyms/` - 동의어 사전

- **`columns.yaml`**: 컬럼 동의어 (하위 호환성)
  - 예: "챔버 압력" → `pressact`
  - 새 버전은 `schema/columns.yaml`의 `aliases` 사용

- **`metrics.yaml`**: 지표 동의어
  - 예: "평균" → `avg`, "흔들림" → `std`

- **`groups.yaml`**: 그룹핑 동의어
  - 예: "스텝별" → `step_name`

- **`patterns.yaml`**: 패턴 정규화 규칙
  - 예: "상위 5개" → `top5`
  - 정규식 패턴 정의

#### `domain/rules/` - 규칙 엔진

- **`normalization.py`**: 질문 정규화
  - 소문자 변환
  - 동의어 치환 (`columns.yaml`의 `aliases` 사용)
  - 패턴 정규화 (top5, step=STANDBY 등)

- **`validation.py`**: 도메인 규칙 검증
  - 컬럼/지표/그룹핑 유효성 확인
  - 메타데이터 조회

- **`resolution.py`**: 모호성 해결
  - "VG11 압력" → `vg11` (pressact 제거)
  - `pressure_resolution.yaml` 규칙 적용

- **`fallback.py`**: 기본값/추론 규칙
  - 컬럼/지표가 없을 때 기본값 제공
  - 예: 컬럼 없음 → `pressact` (기본값)

- **`pressure_resolution.yaml`**: 모호성 해결 규칙 정의
  - 컨텍스트 오버라이드 규칙
  - 기본값 규칙
  - 유량 채널 규칙

### 📁 `templates/` - HTML 템플릿

**역할**: 웹 인터페이스 HTML 템플릿

- **`index.html`**: 메인 페이지
  - 질문 입력 폼
  - 질문 히스토리
  - 즐겨찾기

- **`plot.html`**: 차트 페이지
  - 질문 결과 표시
  - 차트 이미지 표시
  - SQL 쿼리 표시

### 📁 `tests/` - 테스트

**역할**: 파서 테스트 및 검증

- **`questions.jsonl`**: 테스트 질문 목록
  - 각 줄에 JSON 형식의 질문

- **`expected_parsed.jsonl`**: 예상 결과
  - 각 질문에 대한 예상 `Parsed` 객체

- **`test_parser.py`**: 파서 테스트 스크립트
  - 질문과 예상 결과 비교
  - 테스트 통과율 표시

### 📁 `data/` - 원본 데이터 (선택)

**역할**: 원본 CSV 파일 저장 (선택사항)

- 실제 CSV 파일이 있으면 여기에 저장
- `preprocess_duckdb.py`가 이 디렉토리의 CSV를 읽어서 DuckDB로 변환

### 📁 `data_out/` - 처리된 데이터

**역할**: 처리된 데이터베이스 파일 저장

- **`ald.duckdb`**: DuckDB 데이터베이스 파일
  - CSV 파일이 전처리되어 저장된 최종 데이터베이스
  - 애플리케이션이 이 파일을 읽어서 쿼리 실행

---

## 각 파일 상세 설명

### 핵심 파일

#### `src/app.py` - FastAPI 웹 애플리케이션

**역할**: 웹 서버의 메인 진입점

**주요 기능**:
1. **HTTP 엔드포인트**:
   - `GET /`: 메인 페이지 (질문 입력)
   - `POST /query`: 질문 처리 및 JSON 응답
   - `GET /view`: 질문 결과 페이지 (차트 포함)

2. **질문 처리 파이프라인**:
   ```python
   질문 입력
   → normalize() (정규화)
   → parse_question() (파싱)
   → build_sql() (SQL 생성)
   → execute_query() (쿼리 실행)
   → make_summary() (요약 생성)
   → generate_chart() (차트 생성)
   ```

3. **한글 폰트 설정**:
   - Linux 환경에서 사용 가능한 한글 폰트 자동 감지
   - Matplotlib 차트에 한글 표시

**주요 함수**:
- `make_summary()`: 쿼리 결과를 자연어 요약으로 변환
- `generate_chart()`: 데이터를 Matplotlib 차트로 시각화

#### `src/nl_parse_v2.py` - 자연어 파서 (메인)

**역할**: 사용자 질문을 구조화된 `Parsed` 객체로 변환

**작동 원리**:
1. **정규화**: `normalize()` 함수로 질문 정규화
2. **컬럼 추출**: `_pick_col()` - 정규화된 텍스트에서 컬럼 찾기
3. **지표 추출**: `_pick_agg()` - 집계 함수 찾기 (avg, max, std 등)
4. **그룹핑 추출**: `_pick_group_by()` - 그룹핑 컬럼 찾기
5. **필터 추출**: `_pick_multiple_traces()`, `_pick_multiple_steps()` 등
6. **모호성 해결**: `resolve_column_from_text()` - 모호한 컬럼 선택 해결
7. **검증**: `Validator`로 컬럼/지표/그룹핑 유효성 확인

**반환값**: `Parsed` 객체
```python
@dataclass
class Parsed:
    metric: str          # 집계 함수 (avg, max, std 등)
    column: str         # 컬럼 (pressact, vg11 등)
    group_by: Optional[str]  # 그룹핑 (step_name, trace_id 등)
    filters: Dict       # 필터 (trace_id, step_name, date_start 등)
    top_n: Optional[int]  # Top N
    analysis_type: str   # 분석 유형 (ranking, group_profile 등)
    flags: Dict         # 플래그 (is_outlier, is_overshoot 등)
```

#### `src/sql_builder.py` - SQL 쿼리 생성기

**역할**: `Parsed` 객체를 SQL 쿼리로 변환

**주요 함수**:
- `build_sql(parsed: Parsed) -> str`: Parsed 객체를 SQL로 변환
  - SELECT 절: 집계 함수 + 컬럼
  - FROM 절: 테이블명
  - WHERE 절: 필터 조건
  - GROUP BY 절: 그룹핑
  - ORDER BY 절: 정렬
  - LIMIT 절: Top N

**예시**:
```python
parsed = Parsed(metric="avg", column="pressact", top_n=5)
sql = build_sql(parsed)
# → "SELECT AVG(PressAct) as value FROM traces ORDER BY value DESC LIMIT 5"
```

#### `domain/rules/normalization.py` - 질문 정규화

**역할**: 사용자 질문을 표준 형식으로 변환

**정규화 단계**:
1. **소문자 변환**: "VG11" → "vg11"
2. **공백 정리**: 여러 공백을 하나로
3. **Top N 정규화**: "상위 5개" → "top5"
4. **Step 필터 정규화**: "standby 단계" → "step=standby"
5. **동의어 치환**: "챔버 압력" → "pressact"
6. **그룹핑 동의어 치환**: "스텝별" → "group:step_name"

**반환값**: `Normalized` 객체
```python
@dataclass
class Normalized:
    raw: str    # 원문 질문
    text: str   # 정규화된 질문
```

#### `domain/rules/resolution.py` - 모호성 해결

**역할**: 모호한 컬럼 선택을 해결

**예시**:
- "VG11 압력" → `vg11` (pressact 제거)
- "압력 평균" → `pressact` (기본값)

**작동 원리**:
1. `pressure_resolution.yaml` 규칙 로드
2. 컨텍스트 오버라이드 확인 (vg11, vg12 등)
3. 유량 채널 규칙 확인 (n2, nh3 등)
4. 기본값 적용

#### `domain/schema/columns.yaml` - 컬럼 메타데이터

**역할**: 도메인 키와 실제 CSV 컬럼명 매핑

**구조**:
```yaml
columns:
  pressact:
    domain_name: "챔버 압력"
    physical_type: "pressure"
    unit: "mTorr"
    csv_columns: ["PressAct"]  # 실제 DB 컬럼명
    aliases: ["챔버 압력", "압력", "진공", "pressure"]
```

**핵심**: 코드에서는 `pressact` 같은 도메인 키만 사용하고, 실제 SQL에서는 `csv_columns`의 `PressAct`를 사용한다.

---

## 시스템 작동 원리

### 전체 파이프라인

```
[사용자 질문 입력]
    ↓
[1. 정규화] domain/rules/normalization.py
    - "챔버 압력 평균" → "pressact avg"
    ↓
[2. 파싱] src/nl_parse_v2.py
    - "pressact avg" → Parsed(metric="avg", column="pressact")
    ↓
[3. 모호성 해결] domain/rules/resolution.py
    - "vg11 pressact" → "vg11" (구체적 센서 우선)
    ↓
[4. 검증] domain/rules/validation.py
    - 컬럼/지표/그룹핑 유효성 확인
    ↓
[5. SQL 생성] src/sql_builder.py
    - Parsed → "SELECT AVG(PressAct) FROM traces"
    ↓
[6. 쿼리 실행] DuckDB
    - SQL 실행 및 결과 반환
    ↓
[7. 결과 처리] src/app.py
    - 요약 생성 (make_summary)
    - 차트 생성 (generate_chart)
    ↓
[8. 응답] JSON 또는 HTML
```

### 상세 단계 설명

#### 1단계: 정규화 (Normalization)

**입력**: "VG11 압력 평균"

**처리**:
```python
normalize("VG11 압력 평균")
# → Normalized(raw="VG11 압력 평균", text="vg11 pressact avg")
```

**변환 과정**:
- 소문자: "VG11" → "vg11"
- 동의어: "압력" → "pressact"
- 동의어: "평균" → "avg"

#### 2단계: 파싱 (Parsing)

**입력**: "vg11 pressact avg"

**처리**:
```python
parse_question("vg11 pressact avg")
# → Parsed(metric="avg", column="vg11", ...)
```

**추출 과정**:
- 컬럼: "vg11" (키 직접 매칭)
- 지표: "avg" (동의어 매칭)
- 그룹핑: None
- 필터: {}

#### 3단계: 모호성 해결 (Resolution)

**입력**: column="vg11", tokens=["vg11", "pressact", "avg"]

**처리**:
```python
resolve_column_from_text("vg11 pressact avg", "vg11")
# → "vg11" (구체적 센서 우선, pressact는 이미 제거됨)
```

**규칙 적용**:
- `pressure_resolution.yaml`의 `context_overrides` 확인
- "vg11" 토큰 발견 → `vg11` 반환

#### 4단계: SQL 생성 (SQL Building)

**입력**: `Parsed(metric="avg", column="vg11")`

**처리**:
```python
build_sql(parsed)
# → "SELECT AVG(VG11) as value FROM traces"
```

**변환 과정**:
- 도메인 키 `vg11` → CSV 컬럼명 `VG11` (columns.yaml에서 조회)
- 집계 함수 `avg` → SQL `AVG()`
- 테이블명: `traces` (기본값)

#### 5단계: 쿼리 실행 (Query Execution)

**입력**: `"SELECT AVG(VG11) as value FROM traces"`

**처리**:
```python
conn.execute(sql)
# → [{"value": 3.456}]
```

#### 6단계: 결과 처리 (Result Processing)

**입력**: `[{"value": 3.456}]`

**처리**:
```python
make_summary(rows, parsed)
# → "진공 게이지 11 압력 평균=3.456 mTorr"

generate_chart(rows, parsed)
# → PNG 이미지 (Matplotlib)
```

---

## 사용 예시

### 예시 1: 기본 질문

**입력**: "챔버 압력 평균"

**처리 과정**:
1. 정규화: "pressact avg"
2. 파싱: `Parsed(metric="avg", column="pressact")`
3. SQL: `SELECT AVG(PressAct) as value FROM traces`
4. 결과: `[{"value": 3.456}]`
5. 요약: "챔버 압력 평균=3.456 mTorr"

### 예시 2: 그룹핑 질문

**입력**: "스텝별 압력 평균"

**처리 과정**:
1. 정규화: "group:step_name pressact avg"
2. 파싱: `Parsed(metric="avg", column="pressact", group_by="step_name")`
3. SQL: `SELECT Step Name, AVG(PressAct) as value FROM traces GROUP BY Step Name`
4. 결과: `[{"Step Name": "STANDBY", "value": 2.5}, ...]`
5. 요약: "스텝별 챔버 압력 평균" + 차트

### 예시 3: Top N 질문

**입력**: "공정별 압력 평균 상위 5개"

**처리 과정**:
1. 정규화: "group:trace_id pressact avg top5"
2. 파싱: `Parsed(metric="avg", column="pressact", group_by="trace_id", top_n=5)`
3. SQL: `SELECT trace_id, AVG(PressAct) as value FROM traces GROUP BY trace_id ORDER BY value DESC LIMIT 5`
4. 결과: `[{"trace_id": "standard_trace_001", "value": 4.5}, ...]`
5. 요약: "공정별 챔버 압력 평균 상위 5개" + 차트

### 예시 4: 모호성 해결

**입력**: "VG11 압력 평균"

**처리 과정**:
1. 정규화: "vg11 pressact avg" (두 컬럼 모두 포함)
2. 파싱: `Parsed(metric="avg", column="vg11")` (키 직접 매칭으로 vg11 선택)
3. 모호성 해결: "vg11" (구체적 센서 우선)
4. SQL: `SELECT AVG(VG11) as value FROM traces`
5. 결과: `[{"value": 2.3}]`
6. 요약: "진공 게이지 11 압력 평균=2.3 mTorr"

---

## 확장 방법

### 새 컬럼 추가

1. **`domain/schema/columns.yaml`에 추가**:
```yaml
vg14:
  domain_name: "진공 게이지 14 압력"
  physical_type: "pressure"
  unit: "mTorr"
  csv_columns: ["VG14"]
  aliases: ["vg14", "게이지14", "진공게이지14"]
```

2. **모호성 해결 규칙 추가 (필요시)**:
`domain/rules/pressure_resolution.yaml`에 추가:
```yaml
resolution:
  context_overrides:
    - if_any_tokens: ["vg14", "게이지14"]
      prefer_column: "vg14"
      suppress_generic_pressure_token: true
```

3. **코드 변경 없음!** 자동으로 인식됩니다. ✅

### 새 지표 추가

1. **`domain/schema/metrics.yaml`에 추가**:
```yaml
overshoot:
  label: 오버슈트
  sql: custom
  description: 목표값 대비 초과량
```

2. **`domain/synonyms/metrics.yaml`에 동의어 추가**:
```yaml
overshoot:
  - 오버슈트
  - overshoot
  - 초과
```

3. **`src/process_metrics.py`에 SQL 빌더 추가** (필요시)

### 새 그룹핑 추가

1. **`domain/schema/groups.yaml`에 추가**:
```yaml
week:
  label: 주별
  description: 주 단위 그룹핑
  sql_expr: DATE_TRUNC('week', timestamp)
  type: temporal
```

2. **`domain/synonyms/groups.yaml`에 동의어 추가**:
```yaml
week:
  - 주별
  - week별
  - 주
```

---

## 참고 문서

- **`ARCHITECTURE.md`**: 전체 아키텍처 상세 설명
- **`domain/README.md`**: 도메인 메타데이터 디렉토리 가이드
- **`PARSED_SCHEMA.md`**: Parsed 객체 JSON 스키마 설명
- **`tests/README.md`**: 테스트 가이드

---

## 문제 해결

### 한글 폰트가 깨질 때

Linux 환경에서 한글 폰트가 없을 경우:
```bash
# 폰트 설치 (예: Ubuntu)
sudo apt-get install fonts-nanum fonts-noto-cjk
```

### 데이터베이스 파일이 없을 때

```bash
# 더미 데이터 생성
python src/create_dummy_data.py
```

### 파서가 질문을 인식하지 못할 때

1. `domain/schema/columns.yaml`에 동의어 추가
2. `domain/rules/pressure_resolution.yaml`에 규칙 추가
3. `tests/test_parser.py`로 테스트

---

## 라이선스

이 프로젝트는 내부 사용을 위한 것입니다.

---

## 문의

프로젝트 관련 문의사항이 있으면 이슈를 등록하거나 개발팀에 문의하세요.
