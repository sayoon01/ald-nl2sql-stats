# ALD NL2SQL Stats - 자연어 기반 공정 데이터 분석 시스템

## 📋 프로젝트 개요

**ALD NL2SQL Stats**는 ALD(Atomic Layer Deposition) 공정 데이터를 자연어 질문으로 분석할 수 있는 웹 기반 시스템입니다. 사용자가 한국어로 질문하면 자동으로 SQL 쿼리를 생성하고, 결과를 시각화하여 제공합니다.

### 주요 기능

- 🔍 **자연어 질의**: "챔버 압력 평균", "스텝별 온도 최대값" 등 한국어 질문으로 데이터 분석
- 📊 **자동 SQL 생성**: 자연어를 SQL로 자동 변환
- 📈 **시각화**: 결과를 차트와 테이블로 자동 시각화
- 🎯 **도메인 특화**: ALD 공정에 특화된 메타데이터와 규칙 기반 파싱
- 🔧 **확장 가능**: YAML 기반 설정으로 새 컬럼/지표 추가 시 코드 수정 불필요

---

## 🏗️ 시스템 아키텍처

### 전체 구조

```
[사용자 질문] 
    ↓
[정규화 Layer] → domain/rules/normalization.py
    ↓
[파싱 Layer] → src/nl_parse_v2.py
    ↓
[메타데이터 조회] → domain/schema/*.yaml
    ↓
[SQL 생성] → src/sql_builder.py, src/process_metrics.py
    ↓
[쿼리 실행] → DuckDB
    ↓
[결과 해석] → src/interpreter.py
    ↓
[시각화] → templates/index.html, src/plot_generator.py
```

### 핵심 디렉토리 구조

```
ald-nl2sql/
├── src/                    # 소스 코드
│   ├── app.py             # FastAPI 메인 서버
│   ├── nl_parse_v2.py     # 자연어 파서 (도메인 메타데이터 기반)
│   ├── sql_builder.py     # SQL 생성기
│   ├── interpreter.py     # 결과 해석 레이어
│   ├── payload_builder.py # API 응답 빌더
│   ├── plot_generator.py  # 차트 생성
│   ├── process_metrics.py # 공정 특화 지표 (overshoot, dwell_time 등)
│   ├── semantic_resolver.py # 시맨틱 컬럼 → 물리 컬럼 변환
│   └── preprocess_duckdb.py # CSV → DuckDB 변환
│
├── domain/               # 도메인 지식 (YAML 기반)
│   ├── schema/           # 스키마 정의
│   │   ├── columns.yaml  # 컬럼 메타데이터
│   │   ├── metrics.yaml  # 집계 함수 정의
│   │   ├── groups.yaml   # 그룹핑 정의
│   │   └── units.yaml    # 단위 정의
│   ├── synonyms/         # 동의어 사전
│   │   ├── columns.yaml  # 컬럼 동의어
│   │   ├── metrics.yaml  # 지표 동의어
│   │   └── groups.yaml   # 그룹핑 동의어
│   └── rules/            # 규칙 엔진
│       ├── normalization.py # 질문 정규화
│       ├── resolution.py    # 모호성 해결
│       └── validation.py   # 도메인 규칙 검증
│

├── config/                # 설정 파일
│   ├── catalog_physical.json    # 물리 컬럼 카탈로그
│   └── semantic_registry.yaml   # 시맨틱 컬럼 레지스트리
│
├── data/                  # CSV 데이터 파일
│   └── standard_trace_*.csv  # 각 CSV 파일 = 1개 공정 (1:1 관계)
├── data_out/              # DuckDB 데이터베이스
│   └── ald.duckdb         # 변환된 데이터베이스 (모든 공정 통합)
│
├── templates/             # HTML 템플릿
│   ├── index.html         # 메인 UI
│   └── plot.html         # 차트 페이지
│
└── tests/                 # 테스트 코드
```

---

## 🎯 프로젝트 시작부터 실행까지 전체 흐름

### 프로젝트가 돌아가는 전체 과정

이 프로젝트는 **데이터 준비 → 서버 실행 → 질문 처리**의 3단계로 구성됩니다.

#### 📊 1단계: 데이터 준비 (최초 1회만 실행)

**목적**: CSV 파일들을 DuckDB 데이터베이스로 변환

**왜 필요한가?**
- CSV 파일은 매번 전체를 읽어야 해서 느림
- DuckDB는 인덱싱과 최적화로 빠른 쿼리 가능
- 여러 CSV 파일을 하나의 데이터베이스로 통합

**실행 방법**:
```bash
python -m src.preprocess_duckdb
```

**이 명령이 하는 일**:

1. **CSV 파일 찾기 및 읽기**
   - `data/` 디렉토리에서 모든 CSV 파일 찾기 (`standard_trace_001.csv`, `002.csv` 등)
   - 총 74개 CSV 파일 발견 및 읽기 완료
   - 각 CSV 파일 = 1개 공정 (1:1 관계)

2. **공정 ID(`trace_id`) 추출**
   - 파일명에서 공정 ID 자동 추출
   - 예: `standard_trace_001.csv` → `trace_id = "standard_trace_001"`
   - 총 74개 공정 확인

3. **컬럼명 정규화 (slugify)**
   - 공백, 특수문자 제거 및 소문자 변환
   - 예: `PressAct` → `pressact`, `TempAct_U` → `tempact_u`
   - 총 210개 컬럼 정규화 완료

4. **`traces` 테이블 통합**
   - 모든 CSV 데이터를 하나의 `traces` 테이블로 통합
   - 각 행은 `(trace_id, timestamp, ...)` 형태로 저장
   - 총 2,438,733개 행 저장

5. **중복 제거 뷰 생성**
   - `traces_dedup` 뷰 생성 (중복 제거)
   - 키: `(trace_id, timestamp)`
   - 중복 제거: 9,133개 행 제거
   - 최종 행 수: 2,429,600개

6. **시간 축 표준화**
   - `time_bucket_second`: 초 단위 버킷
   - `epoch_ms`: 에포크 밀리초
   - `traces_dedup` 뷰에 추가 (총 212개 컬럼)

7. **DuckDB 파일 생성**
   - `data_out/ald.duckdb` 파일 생성 (약 624MB)
   - 모든 공정 데이터를 하나의 데이터베이스로 통합

8. **컬럼 카탈로그 자동 생성**
   - `config/catalog_physical.json` 생성 (약 4.2KB)
   - 총 212개 컬럼을 9개 카테고리로 자동 분류:
     - `meta`: 10개 (trace_id, timestamp, step_name 등)
     - `pressure`: 10개 (pressact, vg11, vg12 등)
     - `temp`: 51개 (tempact_u, tempact_l, heatertc 등)
     - `gas`: 31개 (mfcmon_n2_1, mfcmon_nh3 등)
     - `apc`: 4개 (apcvalvemon, apcvalveset 등)
     - `rf`: 9개 (f_pwr, l_pos, p_pos 등)
     - `valve`: 35개 (valveact_*, valveset_* 등)
     - `aux`: 52개 (auxmon_* 등)
     - `other`: 10개 (기타 컬럼)

**결과물**:
- `data_out/ald.duckdb`: 분석용 데이터베이스 파일
- `config/catalog_physical.json`: 컬럼 분류 정보

**중요**: 이 단계는 데이터를 처음 준비할 때만 실행하면 됩니다. 새로운 CSV 파일이 추가되면 다시 실행해야 합니다.

---

#### 🚀 2단계: 서버 실행 (매번 실행)

**목적**: 웹 서버를 시작하여 질문을 받을 준비

**실행 방법**:
```bash
python src/app.py
```

**이 명령이 하는 일**:
1. FastAPI 서버 시작
2. 데이터베이스 연결 확인 (`data_out/ald.duckdb` 존재 여부)
3. 도메인 메타데이터 로드 (`domain/schema/*.yaml` 파일들)
4. 웹 서버 대기 상태로 전환
5. `http://localhost:8000/view`에서 접속 가능

**서버가 시작되면**:
- 웹 브라우저에서 `http://localhost:8000/view` 접속
- 질문 입력창이 보임
- API 엔드포인트들 활성화 (`/query`, `/api/query` 등)

---

#### 💬 3단계: 질문 처리 (사용자가 질문할 때마다 실행)

**사용자가 "챔버 압력 평균"이라고 질문하면**:

**Step 1: 정규화** (`domain/rules/normalization.py`)
```
입력: "챔버 압력 평균"
↓
정규화: "pressact avg"
```
- 한글 동의어를 영문 키워드로 변환
- 소문자 변환, 공백 정리

**Step 2: 파싱** (`src/nl_parse_v2.py`)
```
정규화된 텍스트: "pressact avg"
↓
Parsed 객체:
  - column: "pressact"  # 실제 필드명 (col은 하위 호환성 속성)
  - metric: "avg"       # 실제 필드명 (agg는 하위 호환성 속성)
  - group_by: None
  - trace_id: None
  - step_name: None
```
- 컬럼명 추출: "pressact" (챔버 압력)
- 집계 함수 추출: "avg" (평균)
- 필터/그룹핑 추출: 없음

**Step 3: 메타데이터 조회** (`domain/schema/columns.yaml`)
```
컬럼: "pressact"
↓
메타데이터:
  - domain_name: "챔버 압력"
  - unit: "mTorr"
  - decimals: 3
```

**Step 4: SQL 생성** (`src/sql_builder.py`)
```
Parsed 객체
↓
SQL: "SELECT AVG(PressAct) as value, COUNT(*) as n FROM traces_dedup"
```
- 컬럼명 변환: `pressact` → `PressAct` (실제 DB 컬럼명)
- 집계 함수 적용: `AVG(PressAct)`
- 테이블명: `traces_dedup` (중복 제거된 뷰)

**Step 5: 쿼리 실행** (DuckDB)
```python
con = duckdb.connect("data_out/ald.duckdb")
df = con.execute(sql).df()
# 결과: [{"value": 3.456, "n": 12345}]
```

**Step 6: 결과 포맷팅** (`src/app.py`)
```
원본 값: 3.456
↓
포맷팅: "3.456 mTorr"
```
- 소수점 자리수 적용 (decimals: 3)
- 단위 추가 (unit: "mTorr")

**Step 7: 결과 해석** (`src/interpreter.py`)
```
데이터: {"value": 3.456, "n": 12345}
↓
해석: "챔버 압력 평균은 3.456 mTorr로 정상 범위 내입니다."
```
- 사람이 읽기 쉬운 문장으로 변환
- 정상 범위 체크 (semantic_registry.yaml의 normal_range 참조)

**Step 8: 시각화** (`templates/index.html`)
- 단일 값: 큰 숫자로 표시
- 그룹핑: 막대 차트 또는 선 그래프
- Plotly로 인터랙티브 차트 생성

**최종 응답**:
```json
{
  "ok": true,
  "question": "챔버 압력 평균",
  "sql": "SELECT AVG(PressAct) as value, COUNT(*) as n FROM traces_dedup",
  "summary": "챔버 압력 평균은 3.456 mTorr로 정상 범위 내입니다.",
  "data": [{"value": "3.456 mTorr", "n": 12345}],
  "meta": {"chart": "bignum"}
}
```

---

### 프로젝트 실행 순서 요약

```bash
# 1. 처음 한 번만: 데이터 준비
python -m src.preprocess_duckdb
# → data_out/ald.duckdb 생성

# 2. 매번: 서버 실행
python src/app.py
# → http://localhost:8000/view 접속

# 3. 사용자가 질문하면 자동으로:
# 질문 → 정규화 → 파싱 → SQL 생성 → 쿼리 실행 → 결과 해석 → 시각화
```

---

## 🚀 시작하기

### 1. 환경 설정

#### 필수 요구사항

- Python 3.8 이상
- DuckDB
- 필요한 Python 패키지 (requirements.txt 참조)

#### 설치

```bash
# 1. 저장소 클론
git clone https://github.com/sayoon01/ald-nl2sql-stats.git
cd ald-nl2sql-stats

# 2. 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate  # Windows

# 3. 패키지 설치
pip install -r requirements.txt
```

### 2. 데이터 준비

#### CSV 파일 준비

**중요**: CSV 파일 1개 = 공정 1개 (1:1 관계)

- 각 CSV 파일은 하나의 공정(trace) 데이터를 포함합니다
- 파일명 형식: `standard_trace_XXX.csv` (예: `standard_trace_001.csv`, `standard_trace_002.csv`)
- 파일명에서 공정 ID(`trace_id`)가 자동으로 추출됩니다
  - 예: `standard_trace_001.csv` → `trace_id = "standard_trace_001"`

CSV 파일을 `data/` 디렉토리에 배치합니다.

#### 데이터베이스 생성

CSV 파일을 DuckDB로 변환:

```bash
# 프로젝트 루트에서 실행
python -m src.preprocess_duckdb
```

이 명령은 (`src/preprocess_duckdb.py` 실행):
- `data/` 디렉토리의 모든 CSV 파일을 읽어서
- 컬럼명을 정규화 (공백/특수문자 제거, 소문자 변환)
- 모든 CSV 데이터를 하나의 `traces` 테이블로 통합
- 중복 제거된 `traces_dedup` 뷰를 생성
- `data_out/ald.duckdb` 데이터베이스 파일 생성
- 컬럼 카탈로그 자동 생성 (`config/catalog_physical.json`)

**중요**: 
- 이 단계는 **최초 1회만** 실행하면 됩니다
- 새로운 CSV 파일이 추가되면 다시 실행해야 합니다
- 실행 후 `data_out/ald.duckdb` 파일이 생성되어야 서버가 정상 작동합니다

### 3. 서버 실행

```bash
# 기본 실행 (포트 8000)
python src/app.py

# 또는 호스트/포트 지정
python src/app.py --host 127.0.0.1 --port 8080
```

**서버가 시작되면**:
1. `src/app.py`가 FastAPI 서버를 시작합니다
2. 데이터베이스 존재 여부 확인 (`data_out/ald.duckdb`)
3. 도메인 메타데이터 로드 (`domain/schema/*.yaml` 파일들)
4. 웹 서버가 대기 상태로 전환됩니다
5. 브라우저에서 `http://localhost:8000/view`로 접속하면 질문 입력 화면이 나타납니다

**서버가 하는 일**:
- `/view`: 웹 UI 제공 (질문 입력, 결과 표시)
- `/query`: POST API (JSON 요청/응답)
- `/api/query`: GET API (URL 파라미터로 질문)
- `/api/columns`, `/api/traces`, `/api/steps`: 데이터 탐색 API
- `/plot`: PNG 차트 이미지 생성

**서버 종료**: `Ctrl+C`로 종료합니다

---

## 💡 사용 방법

### 웹 UI 사용

1. 브라우저에서 `http://localhost:8000/view` 접속
2. 질문 입력창에 자연어 질문 입력
3. 결과 확인:
   - SQL 쿼리
   - 데이터 테이블
   - 차트 시각화
   - 요약 설명

### 질문 예시

#### 기본 집계

```
챔버 압력 평균
VG11 압력 최대값
온도 표준편차
```

#### 그룹핑

```
스텝별 압력 평균
공정별 온도 최대값
일별 유량 평균
```

#### 필터링

```
standard_trace_001 압력 평균
step=STANDBY 압력 최대값
standard_trace_001 step=B.FILL 압력 평균
```

**참고**: 
- `standard_trace_001`은 CSV 파일명(`standard_trace_001.csv`)에서 자동으로 추출된 공정 ID입니다
- **CSV 파일 1개 = 공정 1개** (1:1 관계)
- 각 CSV 파일은 하나의 공정 데이터를 포함하며, 파일명이 공정 ID가 됩니다

#### Top N

```
공정별 압력 평균 상위 5개
스텝별 온도 최대값 top 10
```

#### 공정 특화 지표

```
overshoot (오버슈트)
dwell_time (체류 시간)
stable_avg (안정 구간 평균)
outlier (이상치 탐지)
```

#### 비교 분석

```
standard_trace_001 vs standard_trace_002 압력 비교
trace1과 trace2의 압력 차이
```

### API 사용

#### POST /query

```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "챔버 압력 평균"}'
```

응답 형식:

```json
{
  "ok": true,
  "question": "챔버 압력 평균",
  "question_normalized": "pressact avg",
  "parsed": {
    "col": "pressact",
    "agg": "avg",
    "group_by": null,
    "trace_id": null,
    "step_name": null
  },
  "sql": "SELECT AVG(PressAct) as value, COUNT(*) as n FROM traces_dedup",
  "summary": "챔버 압력 평균은 3.456 mTorr로 정상 범위 내입니다.",
  "columns": ["value", "n"],
  "data": [
    {"value": "3.456 mTorr", "n": 12345}
  ],
  "meta": {
    "chart": "bignum",
    "value_col": "value"
  }
}
```

#### GET /api/query

```bash
curl "http://localhost:8000/api/query?q=챔버%20압력%20평균"
```

#### GET /api/columns

사용 가능한 컬럼 목록 조회:

```bash
curl "http://localhost:8000/api/columns"
```

#### GET /api/traces

공정 ID 목록 조회:

```bash
curl "http://localhost:8000/api/traces"
```

#### GET /api/steps

단계명 목록 조회:

```bash
curl "http://localhost:8000/api/steps"
```

---

## 🔧 시스템 동작 원리

### 1. 질문 처리 파이프라인

#### Step 1: 정규화 (Normalization)

```python
from domain.rules.normalization import normalize

normalize("챔버 압력 평균")
# → NormalizedText(raw="챔버 압력 평균", text="pressact avg")
```

- 소문자 변환
- 동의어 치환 (챔버 압력 → pressact)
- 패턴 정규화 (top5 → top5, step=STANDBY → step_name=STANDBY)

#### Step 2: 파싱 (Parsing)

```python
from src.nl_parse_v2 import parse_question

parsed = parse_question("pressact avg")
# → Parsed(
#     column="pressact",  # 실제 필드명
#     metric="avg",       # 실제 필드명
#     group_by=None,
#     filters={},
#     top_n=None
# )
# 참고: parsed.col, parsed.agg는 하위 호환성을 위한 @property 속성
```

파서는 다음을 추출합니다:
- **컬럼**: `column` (실제 필드명) 또는 `col` (하위 호환성 속성) - pressact, vg11, tempact_u 등
- **집계 함수**: `metric` (실제 필드명) 또는 `agg` (하위 호환성 속성) - avg, max, min, std 등
- **그룹핑**: `group_by` (trace_id, step_name, date 등)
- **필터**: `trace_id`, `step_name`, `date_start`, `date_end`
- **Top N**: `limit` (5, 10 등)
- **정렬**: `order` (asc, desc)

#### Step 3: 모호성 해결 (Resolution)

여러 컬럼이 매칭될 때 우선순위 규칙 적용:

```python
# 예: "VG11 압력 평균"
# → vg11과 pressact 모두 매칭
# → resolution 규칙: 구체적 센서 우선
# → 최종: vg11
```

규칙 파일: `domain/rules/pressure_resolution.yaml`

#### Step 4: SQL 생성

```python
from src.sql_builder import build_sql

sql, params = build_sql(parsed)
# → ("SELECT AVG(PressAct) as value, COUNT(*) as n FROM traces_dedup", [])
```

특수 지표는 별도 빌더 사용:
- `overshoot`: `build_overshoot_sql()`
- `dwell_time`: `build_dwell_time_sql()`
- `stable_avg`: `build_stable_avg_sql()`
- `outlier`: `build_outlier_detection_sql()`
- `trace_compare`: `build_trace_compare_sql()`

#### Step 5: 쿼리 실행

```python
import duckdb

con = duckdb.connect("data_out/ald.duckdb")
df = con.execute(sql, params).df()
```

#### Step 6: 결과 해석

```python
from src.interpreter import interpret

summary = interpret(parsed, df)
# → "챔버 압력 평균은 3.456 mTorr로 정상 범위 내입니다."
```

해석 레이어는:
- 단일 값: "평균은 X입니다"
- 그룹핑: "Top 5는 ..."
- 비교: "차이는 X입니다"
- 정상 범위 체크: "정상 범위 내/외"

### 2. 도메인 메타데이터 시스템

모든 도메인 지식은 YAML 파일로 관리됩니다.

#### 컬럼 정의 (`domain/schema/columns.yaml`)

```yaml
pressact:
  domain_name: "챔버 압력"
  physical_type: "pressure"
  unit: "mTorr"
  csv_columns: ["PressAct"]
  aliases: ["챔버 압력", "압력", "진공", "pressact"]
  decimals: 3  # 소수점 자리수 (선택)
```

#### 동의어 정의 (`domain/synonyms/columns.yaml`)

```yaml
pressact:
  - 챔버 압력
  - 압력
  - 진공
  - chamber pressure
```

#### 집계 함수 정의 (`domain/schema/metrics.yaml`)

```yaml
avg:
  label: "평균"
  sql: "AVG"
  description: "산술 평균"
```

### 3. 시맨틱 해석 시스템

#### 시맨틱 레지스트리 (`config/semantic_registry.yaml`)

시맨틱 컬럼(의미) → 물리 컬럼(실제 데이터) 매핑:

```yaml
pressure:
  chamber:
    act:
      physical_columns: ["pressact"]
      aliases: ["챔버 압력", "압력", "진공"]
      unit: "Torr"
      description: "챔버 압력"
```

#### 물리 컬럼 카탈로그 (`config/catalog_physical.json`)

물리 컬럼을 카테고리별로 분류:

```json
{
  "pressure": ["pressact", "vg11", "vg12", "vg13"],
  "temp": ["tempact_u", "tempact_l"],
  "gas": ["mfcmon_n2_1", "mfcmon_nh3"]
}
```

---

## 📊 주요 기능 상세

### 1. 자연어 파싱

#### 지원하는 질문 패턴

- **기본 집계**: "압력 평균", "온도 최대값"
- **그룹핑**: "스텝별 압력 평균", "공정별 온도 최대값"
- **필터링**: "standard_trace_001 압력 평균", "step=STANDBY 압력"
- **Top N**: "상위 5개", "top 10"
- **비교**: "trace1 vs trace2 압력 비교"
- **날짜 범위**: "2024-01-01부터 2024-01-31까지"

#### 모호성 해결

여러 컬럼이 매칭될 때:

1. **구체적 센서 우선**: "VG11 압력" → `vg11` (pressact보다 우선)
2. **컨텍스트 키워드**: "챔버 압력" → `pressact`
3. **기본값**: "압력" → `pressact` (가장 일반적인 컬럼)

### 2. SQL 생성

#### 기본 SQL 템플릿

```sql
SELECT 
  {AGG_FUNCTION}({COLUMN}) as value,
  COUNT(*) as n,
  STDDEV({COLUMN}) as std
FROM traces_dedup
WHERE {FILTERS}
GROUP BY {GROUP_BY}
ORDER BY value {ORDER}
LIMIT {LIMIT}
```

#### 특수 지표 SQL

**Overshoot (오버슈트)**:
```sql
SELECT 
  step_name,
  AVG(pressact - pressset) as overshoot,
  COUNT(*) as n
FROM traces_dedup
WHERE pressact > pressset
GROUP BY step_name
```

**Dwell Time (체류 시간)**:
```sql
SELECT 
  step_name,
  AVG(duration) as dwell_time,
  COUNT(*) as n
FROM traces_dedup
GROUP BY step_name
```

### 3. 결과 해석

#### 단일 값 해석

```
"챔버 압력 평균은 3.456 mTorr로 정상 범위 내입니다."
```

#### 그룹핑 해석

```
"스텝별 챔버 압력 평균 Top 5:
1. B.FILL: 5.234 mTorr (표본 1234개)
2. STANDBY: 3.456 mTorr (표본 5678개)
..."
```

#### 비교 해석

```
"B.FILL 단계에서 trace 간 pressact 차이가 가장 큽니다 
(차이: ≈1.5 mTorr, standard_trace_001: 5.2 mTorr, 
standard_trace_002: 3.7 mTorr). 
이는 충진 단계에서 압력 제어 프로파일 차이가 있었을 가능성을 시사합니다."
```

### 4. 시각화

#### 차트 타입

- **Big Number**: 단일 값 표시
- **Bar Chart**: 그룹별 비교
- **Line Chart**: 시계열 데이터
- **Horizontal Bar**: Top N (가로 막대)

#### 차트 생성

- **Plotly**: 웹 UI에서 인터랙티브 차트
- **Matplotlib**: PNG 이미지 생성 (`/plot` 엔드포인트)

---

## 🔨 확장 방법

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

2. **`domain/synonyms/columns.yaml`에 동의어 추가**:

```yaml
vg14:
  - vg14
  - 게이지14
  - 진공게이지14
```

3. **모호성 해결 규칙 추가 (필요시)**:

`domain/rules/pressure_resolution.yaml`:

```yaml
resolution:
  context_overrides:
    - if_any_tokens: ["vg14", "게이지14"]
      prefer_column: "vg14"
      suppress_generic_pressure_token: true
```

**코드 수정 없음!** 자동으로 인식됩니다. ✅

### 새 지표 추가

1. **`domain/schema/metrics.yaml`에 추가**:

```yaml
overshoot:
  label: "오버슈트"
  sql: "custom"
  description: "목표값 대비 초과량"
```

2. **`domain/synonyms/metrics.yaml`에 동의어 추가**:

```yaml
overshoot:
  - 오버슈트
  - overshoot
  - 초과
```

3. **`src/process_metrics.py`에 SQL 빌더 추가**:

```python
def build_overshoot_sql(parsed: Parsed) -> Tuple[str, List]:
    # SQL 생성 로직
    pass
```

### 새 그룹핑 추가

1. **`domain/schema/groups.yaml`에 추가**:

```yaml
week:
  label: "주별"
  description: "주 단위 그룹핑"
  sql_expr: "DATE_TRUNC('week', timestamp)"
  type: "temporal"
```

2. **`domain/synonyms/groups.yaml`에 동의어 추가**:

```yaml
week:
  - 주별
  - week별
  - 주
```

---

## 🧪 테스트

### 단위 테스트

```bash
# 파서 테스트
python -m pytest tests/test_parser.py

# 모듈별 테스트
python tests/test_modules.py
```

### 통합 테스트

```bash
# 모듈별 테스트 (tests/ 디렉토리 사용)
python tests/test_modules.py

# 파서 테스트
python tests/test_parser.py
```

**참고**: 루트 디렉토리의 테스트 전용 파일들(`test_api.sh`, `test_interpreter.py`, `check_file_usage.py`)과 `src/charts/` 디렉토리는 삭제되었습니다. 모든 테스트는 `tests/` 디렉토리에서 실행합니다.

### 테스트 케이스 추가

`tests/questions.jsonl`에 질문과 예상 결과 추가:

```json
{"question": "챔버 압력 평균", "expected_col": "pressact", "expected_agg": "avg"}
```

---

## 📁 주요 파일 설명

### `src/app.py`

FastAPI 메인 서버:
- `/view`: 웹 UI
- `/query`: POST API
- `/api/query`: GET API
- `/api/columns`, `/api/traces`, `/api/steps`: 데이터 탐색 API
- `/plot`: PNG 차트 생성

### `src/nl_parse_v2.py`

도메인 메타데이터 기반 자연어 파서:
- 질문을 `Parsed` 객체로 변환
- 컬럼, 집계 함수, 그룹핑, 필터 추출
- 모호성 해결

### `src/sql_builder.py`

SQL 생성기:
- `Parsed` 객체를 SQL로 변환
- 필터, 그룹핑, 정렬, LIMIT 처리

### `src/interpreter.py`

결과 해석 레이어:
- SQL 결과를 사람이 읽기 쉬운 문장으로 변환
- 정상 범위 체크
- 그룹핑 결과 요약

### `src/process_metrics.py`

공정 특화 지표:
- `overshoot`: 오버슈트 계산
- `dwell_time`: 체류 시간 계산
- `stable_avg`: 안정 구간 평균
- `outlier`: 이상치 탐지
- `trace_compare`: 공정 비교

### `src/preprocess_duckdb.py`

CSV → DuckDB 변환:
- CSV 파일 읽기
- 컬럼명 slugify (공백, 특수문자 처리)
- 중복 제거 뷰 생성
- 카탈로그 자동 생성

### `domain/rules/normalization.py`

질문 정규화:
- 소문자 변환
- 동의어 치환
- 패턴 정규화

### `domain/rules/resolution.py`

모호성 해결:
- 여러 컬럼 매칭 시 우선순위 결정
- 컨텍스트 기반 해결

---

## 🐛 문제 해결

### 데이터베이스가 없을 때

```bash
# 데이터베이스 재생성
python -m src.preprocess_duckdb
```

### 한글 폰트가 깨질 때

Linux 환경에서:

```bash
sudo apt-get install fonts-nanum fonts-noto-cjk
```

폰트 설정은 `src/utils/mpl_korean.py`에서 자동 처리됩니다.

### 파서가 질문을 인식하지 못할 때

1. `domain/schema/columns.yaml`에 동의어 추가
2. `domain/rules/pressure_resolution.yaml`에 규칙 추가
3. `tests/test_parser.py`로 테스트

### 서버 시작 시 에러

데이터베이스 무결성 검증 실패 시:

```bash
# 데이터베이스 재생성
python -m src.preprocess_duckdb
```

---

## 📚 추가 문서

### 디렉토리별 상세 가이드

각 디렉토리의 README 파일에서 해당 디렉토리의 코드 사용법과 동작 방식을 상세히 설명합니다:

- **`src/README.md`**: 소스 코드 모듈별 상세 설명
  - 각 파일의 역할, 실제 사용 위치, 동작 원리
  - 모듈 간 의존성 및 데이터 흐름
  - 사용 예시 및 코드 스타일

- **`domain/README.md`**: 도메인 메타데이터 가이드
  - YAML 파일 구조 및 사용법
  - 확장 방법 (새 컬럼/지표/그룹핑 추가)
  - 모호성 해결 규칙
  - 데이터 흐름 예시

- **`templates/README.md`**: HTML 템플릿 가이드
  - 템플릿 구조 및 Jinja2 변수
  - JavaScript 기능 상세 설명
  - 데이터 흐름 및 사용 예시

- **`tests/README.md`**: 테스트 가이드
  - 테스트 실행 방법
  - 테스트 케이스 추가 방법
  - 예상 결과 형식

### 기타 문서

- **`docs/ARCHITECTURE.md`**: 아키텍처 상세 설명 (있는 경우)
- **`docs/PARSED_SCHEMA.md`**: Parsed 객체 JSON 스키마 (있는 경우)

---

## 🔄 워크플로우 예시

### 예시 1: 기본 질문

**입력**: "챔버 압력 평균"

**처리 과정**:

1. 정규화: "pressact avg"
2. 파싱: `Parsed(col="pressact", agg="avg")`
3. SQL 생성: `SELECT AVG(PressAct) as value FROM traces_dedup`
4. 쿼리 실행: `[{"value": 3.456}]`
5. 포맷팅: `get_format_spec("pressact")` → `(3, "mTorr")`
6. 해석: "챔버 압력 평균은 3.456 mTorr로 정상 범위 내입니다."

### 예시 2: 그룹핑 질문

**입력**: "스텝별 압력 평균"

**처리 과정**:

1. 정규화: "group:step_name pressact avg"
2. 파싱: `Parsed(col="pressact", agg="avg", group_by="step_name")`
3. SQL 생성: `SELECT step_name, AVG(PressAct) as value FROM traces_dedup GROUP BY step_name`
4. 쿼리 실행: `[{"step_name": "STANDBY", "value": 2.5}, ...]`
5. 해석: "스텝별 챔버 압력 평균 Top 5: ..."
6. 차트: Bar Chart 생성

### 예시 3: Top N 질문

**입력**: "공정별 압력 평균 상위 5개"

**처리 과정**:

1. 정규화: "group:trace_id pressact avg top5"
2. 파싱: `Parsed(col="pressact", agg="avg", group_by="trace_id", limit=5)`
3. SQL 생성: `SELECT trace_id, AVG(PressAct) as value FROM traces_dedup GROUP BY trace_id ORDER BY value DESC LIMIT 5`
4. 쿼리 실행: `[{"trace_id": "standard_trace_001", "value": 4.5}, ...]`
5. 해석: "공정별 챔버 압력 평균 상위 5개: ..."
6. 차트: Horizontal Bar Chart 생성

---

## 🎯 핵심 설계 원칙

### 1. 사용자 언어 ↔ 시스템 언어 분리

**문제**: 사용자가 "압력"이라고 말하면, 시스템에는 `pressact`, `vg11`, `vg12` 등 여러 센서가 존재한다.

**해결**: **나누는 게 정석**. 복잡함은 resolution 규칙으로 해결한다.

```
사용자 언어: "압력"
    ↓
[columns.yaml] → 동의어/정의/실제 컬럼명 매핑
    ↓
[pressure_resolution.yaml] → 모호할 때 우선순위 규칙
    ↓
시스템 언어: pressact, vg11, vg12, vg13 ... (센서별)
```

### 2. 확장성: 데이터가 늘어나는 복잡도를 규칙/스키마로 흡수

- 새 센서 추가 → `columns.yaml`에 컬럼 정의만 추가
- 모호성 해결 → `pressure_resolution.yaml`에 규칙만 추가
- **코드 변경 없이 자동 인식** ✅

### 3. YAML 기반 도메인 지식 관리

모든 도메인 지식은 YAML 파일로 관리:
- 코드 수정 없이 도메인 지식 업데이트 가능
- 버전 관리 용이
- 비개발자도 수정 가능

---

## 📝 라이선스

이 프로젝트는 내부 사용을 위한 것입니다.

---

## 🤝 기여

프로젝트 관련 문의사항이 있으면 이슈를 등록하거나 개발팀에 문의하세요.

---

## 📞 문의

프로젝트 관련 문의사항이 있으면 이슈를 등록하거나 개발팀에 문의하세요.
