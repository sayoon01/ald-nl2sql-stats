# ALD NL→SQL Stats API

반도체 ALD(Atomic Layer Deposition) 공정 데이터를 자연어로 질의하여 통계 분석 결과를 제공하는 웹 애플리케이션입니다.

## 🎯 프로젝트 소개

이 프로젝트는 반도체 제조 공정에서 생성된 대량의 시계열 데이터를 분석하기 위한 **자연어 인터페이스**를 제공합니다. 사용자는 복잡한 SQL 쿼리 작성 없이 자연어 질문을 입력하면, 시스템이 자동으로:

1. **질문 분석** → 구조화된 분석 의도로 변환
2. **SQL 생성** → 분석 의도에 맞는 SQL 쿼리 자동 생성
3. **데이터 분석** → DuckDB를 통해 효율적으로 데이터 조회
4. **결과 해석** → 사람이 읽기 쉬운 자연어 요약 제공
5. **시각화** → 분석 유형에 맞는 차트 자동 생성

## ⚡ 빠른 시작

### 1. 환경 설정

```bash
cd ~/ald_app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 데이터 준비 (최초 1회)

```bash
python -m src.preprocess_duckdb
```

CSV 파일들은 `data_in/` 디렉토리에 있어야 합니다.

### 3. 웹 서버 실행

```bash
uvicorn src.app:app --reload --port 8000
```

브라우저에서 `http://127.0.0.1:8000/view` 접속

## 📚 상세 문서

- **[src/README.md](src/README.md)**: 각 Python 모듈의 작동 원리와 구조
- **[templates/README.md](templates/README.md)**: UI 템플릿 구조와 기능

## 🛠 기술 스택

- **Backend**: FastAPI (비동기 웹 프레임워크)
- **Database**: DuckDB (OLAP, in-process)
- **NLP**: Rule-based 의도 파싱 (정규표현식)
- **Visualization**: Matplotlib (정적 차트)
- **Template**: Jinja2 (HTML 렌더링)
- **Data Processing**: Pandas

## 📁 프로젝트 구조

```
ald_app/
├── src/                      # 소스 코드
│   ├── app.py               # FastAPI 애플리케이션 (메인 진입점)
│   ├── nl_parse.py          # 자연어 질문 → Parsed 객체
│   ├── sql_builder.py       # Parsed → SQL 쿼리 (기본 집계)
│   ├── process_metrics.py   # 공정 특화 지표 (overshoot, outlier 등)
│   ├── interpreter.py       # 결과 → 자연어 해석 (요약 생성)
│   ├── chart_templates.py   # 분석 유형 → 차트 템플릿
│   ├── semantic_resolver.py # Semantic ID → Physical 컬럼
│   ├── payload_builder.py   # UI용 표준 payload 생성
│   ├── question_suggestions.py # 질문 추천 및 자동완성
│   ├── plot_generator.py    # Matplotlib 시계열 플롯 생성
│   ├── preprocess_duckdb.py # CSV → DuckDB 변환
│   └── run_query.py         # CLI 인터페이스
│
├── templates/               # HTML 템플릿
│   ├── index.html          # 메인 UI 페이지
│   └── plot.html           # 차트 전용 페이지
│
├── data_in/                # 입력 CSV 파일들
├── data_out/               # 출력 데이터베이스
│   └── ald.duckdb         # DuckDB 데이터베이스
│
├── catalog_physical.json   # 물리적 컬럼 분류 카탈로그
├── semantic_registry.yaml  # Semantic ID 매핑 레지스트리
└── requirements.txt        # Python 패키지 의존성
```

## 🔄 동작 흐름

```
사용자 질문
    ↓
[nl_parse.py] 자연어 파싱 → Parsed 객체
    ↓
[sql_builder.py / process_metrics.py] SQL 생성
    ↓
[DuckDB] SQL 실행 → DataFrame
    ↓
[interpreter.py] 결과 해석 → 자연어 요약
    ↓
[app.py] 포맷팅 + 차트 생성
    ↓
[UI] 결과 표시
```

## 💡 핵심 개념

### 1. 분석 유형 (Analysis Type)

질문 의도를 4가지로 분류하여 적절한 시각화를 자동 선택:

| 분석 유형 | 설명 | 예시 | 차트 |
|---------|------|------|------|
| **ranking** | 랭킹 분석 (Top-N) | `"공정별 pressact 평균 top5"` | 가로 막대 |
| **group_profile** | 그룹별 분포 | `"스텝별 pressact 평균"` | 세로 막대/라인 |
| **comparison** | 비교 분석 | `"trace_001과 trace_002 비교"` | 그룹 막대 |
| **stability** | 안정성 분석 | `"pressact 이상치 top5"` | 막대/박스 |

### 2. 공정 친화 지표

반도체 공정 분석에 특화된 지표:

- **Overshoot**: 최대값 - 설정값 (압력 초과량)
- **Dwell Time**: 각 단계의 체류 시간
- **Stable Average**: 안정화 구간 평균 (초반 10% 제외)
- **Outlier Detection**: z-score 기반 이상치 탐지

### 3. 해석 레이어

SQL 결과를 사람이 읽기 쉬운 문장으로 변환:

- **단일 값**: `"챔버 압력 평균은 358.354 Torr입니다 (표본 2,429,600개, 표준편차 366.516)"`
- **그룹별**: `"단계명별 챔버 압력 평균 결과입니다. (총 47개 그룹)\n값 범위: 0.006 ~ 754.1\n상위 5개: ..."`

**메타데이터**:
- `semantic_registry.yaml`에서 단위(unit), 설명(description) 자동 조회
- 정상 범위(normal_range)가 있는 경우만 범위 판정 표시

## 📖 사용 예시

### 기본 통계

```
압력 평균
질소 1 유량 최대
상단 온도 최소
```

### 필터링

```
standard_trace_001 압력 평균
standard_trace_001 step=STANDBY 압력 최대
2024-01-01부터 압력 평균
```

### 그룹별 분석

```
스텝별 압력 평균
공정별 압력 평균 top5
standard_trace_001 스텝별 온도 평균 top10
```

### 비교 분석

```
standard_trace_001과 standard_trace_002 압력 비교
```

### 공정 특화 지표

```
압력 overshoot top5
압력 이상치 top10
standard_trace_001 스텝별 체류시간
```

## 🔌 API 엔드포인트

### 웹 UI
- `GET /` → `/view`로 리다이렉트
- `GET /view?q=질문` → 메인 UI 페이지
- `GET /plot?q=질문` → PNG 차트 이미지

### JSON API
- `POST /query` → 질의 실행 (표준 payload 반환)
- `GET /api/query?q=질문` → 질의 실행 (표준 payload 반환)
- `GET /api/suggestions?q=검색어` → 질문 추천 (검색어 기반)
- `GET /api/popular` → 인기 질문 목록
- `GET /api/plot?q=질문` → 시계열 플롯 PNG 이미지
- `GET /api/columns` → 사용 가능한 컬럼 목록
- `GET /api/traces` → 공정 ID 목록
- `GET /api/steps` → 단계명 목록
- `GET /api/range` → 데이터 범위 정보
- `GET /api/csv?q=질문` → CSV 다운로드

## 📊 데이터 구조

### 주요 컬럼

- **`trace_id`**: 공정 ID (예: `standard_trace_001`)
- **`step_name`**: 단계명 (예: `STANDBY`, `B.FILL5`)
- **`timestamp`**: 타임스탬프
- **`pressact`**: 챔버 압력 (실측값)
- **`pressset`**: 압력 설정값
- **`mfcmon_*`**: 유량 모니터링 (N2, NH3, DCS 등)
- **`tempact_*`**: 온도 (U, CU, C, CL, L)
- **`apcvalvemon`**: APC 밸브 모니터

### 데이터베이스

- **테이블**: `traces` (원본), `traces_dedup` (중복 제거된 뷰)
- **위치**: `data_out/ald.duckdb`
- **전처리**: `src/preprocess_duckdb.py` 실행 시 자동 생성

## 🧪 테스트

해석 레이어 테스트:

```bash
python test_interpreter.py
```

## ⚠️ 주의사항

1. **데이터 전처리**: CSV 파일 변경 시 `python -m src.preprocess_duckdb` 재실행 필요
2. **가상 환경**: 항상 가상 환경 활성화 후 사용
3. **포트 충돌**: 기본 포트 8000 사용 중이면 다른 포트 사용 가능
4. **한글 폰트**: macOS 기본 폰트 사용, 다른 OS에서는 matplotlib 한글 폰트 설정 필요

## 🐛 문제 해결

### 차트가 보이지 않을 때
- matplotlib 백엔드 확인 (`matplotlib.use('Agg')`)
- 한글 폰트 설정 확인

### SQL 에러가 발생할 때
- 컬럼명 확인 (허용된 컬럼만 사용 가능)
- 질문 구문 확인
- 날짜 형식 확인 (YYYY-MM-DD)

### 데이터가 없을 때
- `data_out/ald.duckdb` 파일 존재 확인
- `preprocess_duckdb.py` 실행 확인

## 📝 라이센스

이 프로젝트는 내부 사용을 위한 것입니다.
