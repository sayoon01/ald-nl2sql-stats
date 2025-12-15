# ALD NL→SQL Stats API

## 기술 스택

- **Backend**: FastAPI
- **DB**: DuckDB (OLAP, in-process)
- **NLP**: Rule-based 의도 파싱
- **Visualization**: Matplotlib
- **Template**: Jinja2

## 프로젝트 구조

```
src/
 ├─ nl_parse.py        # 질문 → 분석 의도
 ├─ sql_builder.py     # 의도 → SQL
 ├─ chart_templates.py # 의도 → 차트 템플릿
 ├─ process_metrics.py # 공정 특화 지표
 └─ app.py             # API & UI
```

반도체 ALD 공정 데이터를 자연어로 질의하여 SQL을 생성하고 통계 분석을 제공하는 웹 애플리케이션입니다.

## 주요 기능

### 📊 기본 통계 분석
- **집계 함수**: 평균, 최소, 최대, 개수
- **지표**: pressact, pressset, vg11, vg12, vg13, apcvalvemon, apcvalveset
- **예시**: `"pressact 평균"`, `"압력 최대"`, `"vg11 최소"`

### 📈 그룹별 통계
- **공정별 분석**: `"공정별 pressact 평균 top5"`
- **단계별 분석**: `"스텝별 pressact 평균"`
- **예시**: `"standard_trace_001 스텝별 pressact 평균"`

### ⏰ 시간 기반 분석
- **일별 트렌드**: `"pressact 일별 평균"`
- **시간별 분석**: `"pressact 시간별 평균"`
- **날짜 범위 필터링**: `"2024-01-01부터 pressact 평균"`

### 🔄 비교 기능
- **여러 공정 비교**: `"standard_trace_001과 standard_trace_002 pressact 비교"`
- **여러 단계 비교**: `"step=STANDBY와 step=B.FILL5 pressact 비교"`

### 📊 시각화
- **자동 차트 생성**: 그룹별 결과는 자동으로 차트 생성
- **라인 차트**: 시계열 데이터(일별, 시간별)
- **바 차트**: 그룹별 비교 데이터

### 🔍 데이터 탐색
- 컬럼 목록 조회
- 공정 ID 목록 조회
- 단계명 목록 조회
- 데이터 범위 확인 (최소/최대 날짜, 총 행 수)

### 💾 편의 기능
- 질문 히스토리 저장/조회
- 즐겨찾기 질문 저장
- CSV 다운로드

## 설치 방법

### 1. 가상 환경 생성 및 활성화

```bash
cd ~/ald_app
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# 또는
venv\Scripts\activate  # Windows
```

### 2. 패키지 설치

```bash
pip install -r requirements.txt
```

### 3. 데이터 전처리 (최초 1회)

CSV 파일들을 DuckDB로 변환합니다. 원본 CSV 파일은 `~/standard_traces/` 디렉토리에 있어야 합니다.

```bash
python -m src.preprocess_duckdb
```

이 명령은 다음을 수행합니다:
- `~/standard_traces/*.csv` 파일들을 읽어서
- `data_out/ald.duckdb` 데이터베이스를 생성합니다
- 컬럼명을 slugify하고 `step_name` 컬럼을 표준화합니다

## 사용 방법

### 웹 UI 사용

1. **서버 실행**

```bash
source venv/bin/activate
uvicorn src.app:app --reload --port 8000
```

2. **브라우저에서 접속**

```
http://127.0.0.1:8000/view
```

3. **질문 입력 예시**

- `공정별 pressact 평균 top5`
- `standard_trace_001 스텝별 pressact 평균`
- `standard_trace_001 step=STANDBY pressact 최대`
- `pressact 일별 평균`
- `standard_trace_001과 standard_trace_002 pressact 비교`

### CLI 사용

터미널에서 직접 실행:

```bash
source venv/bin/activate
python -m src.run_query
```

질문을 입력하면 결과를 확인할 수 있습니다.

### API 사용

#### POST /query
JSON API로 질의 실행:

```bash
curl -X POST "http://127.0.0.1:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "pressact 평균"}'
```

#### GET /view?q=질문
HTML UI로 질의 실행:

```
http://127.0.0.1:8000/view?q=pressact+평균
```

#### GET /plot?q=질문
차트 이미지(PNG) 반환:

```
http://127.0.0.1:8000/plot?q=공정별+pressact+평균
```

## API 엔드포인트

### 웹 UI
- `GET /` - API 정보
- `GET /view?q=질문` - HTML UI (메인 페이지)
- `GET /plot?q=질문` - PNG 차트 이미지
- `GET /plot_page?q=질문` - 차트 페이지 (HTML)

### JSON API
- `POST /query` - 질의 실행 (JSON 응답)
  ```json
  {
    "question": "pressact 평균"
  }
  ```

### 데이터 탐색
- `GET /api/columns` - 사용 가능한 컬럼 목록
- `GET /api/traces` - 공정 ID 목록
- `GET /api/steps` - 단계명 목록
- `GET /api/range` - 데이터 범위 (최소/최대 날짜, 총 행 수)

### 편의 기능
- `POST /api/history` - 질문 히스토리 저장
- `GET /api/history` - 질문 히스토리 조회
- `POST /api/favorites` - 즐겨찾기 추가
- `GET /api/favorites` - 즐겨찾기 목록
- `DELETE /api/favorites` - 즐겨찾기 삭제
- `GET /api/csv?q=질문` - CSV 다운로드

## 질문 예시

### 기본 통계
```
pressact 평균
압력 최대
vg11 최소
공정별 pressact 개수
```

### 필터링
```
standard_trace_001 pressact 평균
standard_trace_001 step=STANDBY pressact 최대
2024-01-01부터 pressact 평균
```

### 그룹별 분석
```
공정별 pressact 평균 top5
스텝별 pressact 평균
standard_trace_001 스텝별 pressact 평균
```

### 시간 기반
```
pressact 일별 평균
pressact 시간별 평균
2024-01-01부터 pressact 일별 평균
```

### 비교
```
standard_trace_001과 standard_trace_002 pressact 비교
step=STANDBY와 step=B.FILL5 pressact 평균 비교
```

## 데이터 구조

### 원본 데이터 위치
- CSV 파일: `~/standard_traces/*.csv`
- 데이터베이스: `~/ald_app/data_out/ald.duckdb`

### 주요 컬럼
- `trace_id`: 공정 ID (예: standard_trace_001)
- `step_name`: 단계명 (예: STANDBY, B.FILL5)
- `timestamp`: 타임스탬프 (Date + Time)
- `pressact`: 챔버 압력 (실측)
- `pressset`: 압력 설정
- `vg11`, `vg12`, `vg13`: 밸브 관련 지표
- `apcvalvemon`: APC 밸브 모니터
- `apcvalveset`: APC 밸브 설정

## 주의사항

1. **데이터 전처리**: CSV 파일을 변경했거나 새로운 파일이 추가된 경우 `preprocess_duckdb.py`를 다시 실행해야 합니다.

2. **가상 환경**: 항상 가상 환경을 활성화한 후 사용하세요.

3. **포트 충돌**: 기본 포트 8000이 사용 중이면 다른 포트를 사용하세요:
   ```bash
   uvicorn src.app:app --reload --port 8001
   ```

## 문제 해결

### 차트가 보이지 않을 때
- matplotlib 백엔드가 올바르게 설정되었는지 확인
- 한글 폰트 설정 확인 (macOS: Apple SD Gothic Neo)

### SQL 에러가 발생할 때
- 컬럼명이 올바른지 확인 (허용된 컬럼만 사용 가능)
- 질문 구문이 올바른지 확인

### 데이터가 없을 때
- `data_out/ald.duckdb` 파일이 존재하는지 확인
- `preprocess_duckdb.py`를 실행했는지 확인

