# 모듈별 단위 테스트 가이드

각 컴포넌트를 독립적으로 테스트하는 방법

## 빠른 실행

```bash
# 전체 모듈 테스트
bash tests/test_individual_modules.sh

# 또는 Python으로 직접
python3 tests/test_modules.py
```

## 개별 모듈 테스트

### 1. 파서 모듈 (`src/nl_parse_v2.py`)

```bash
python3 -c "
from src.nl_parse_v2 import parse_question
p = parse_question('압력 평균')
print(f'column: {p.column}, metric: {p.metric}, analysis_type: {p.analysis_type}')
"
```

**테스트 포인트:**
- 다양한 질문 형식 파싱
- group_by, filters, top_n 추출
- analysis_type 결정

### 2. SQL 빌더 모듈 (`src/sql_builder.py`)

```bash
python3 -c "
from src.nl_parse_v2 import Parsed
from src.sql_builder import build_sql
p = Parsed(metric='avg', column='pressact', analysis_type='ranking')
sql, params = build_sql(p)
print(f'SQL: {sql[:100]}...')
print(f'Params: {params}')
"
```

**테스트 포인트:**
- 기본 SQL 생성
- group_by SQL 생성
- 필터 적용 SQL
- 도메인키 → 실제 컬럼명 변환

### 3. 쿼리 실행 (`src/run_query.py`)

```bash
# DB 파일이 있어야 함
python3 -c "
import duckdb
from pathlib import Path
db = Path('data_out/ald.duckdb')
if db.exists():
    con = duckdb.connect(str(db))
    result = con.execute('SELECT COUNT(*) FROM traces').fetchone()
    print(f'✅ DB 연결 성공: {result[0]} rows')
    con.close()
else:
    print('⚠️  DB 파일 없음')
"
```

**테스트 포인트:**
- DB 연결
- SQL 실행
- 결과 DataFrame 변환

### 4. 공정 지표 모듈 (`src/process_metrics.py`)

```bash
python3 -c "
from src.nl_parse_v2 import Parsed
from src.process_metrics import build_outlier_detection_sql
p = Parsed(metric='avg', column='pressact', flags={'is_outlier': True})
sql, params = build_outlier_detection_sql(p)
print(f'✅ 이상치 탐지 SQL: {len(sql)} chars')
"
```

**테스트 포인트:**
- 이상치 탐지 SQL
- Overshoot SQL
- Dwell time SQL
- Trace 비교 SQL

### 5. 차트 렌더링 (`src/charts/renderer.py`)

```bash
python3 -c "
import pandas as pd
from src.nl_parse_v2 import Parsed
from src.charts.renderer import render_chart
p = Parsed(metric='avg', column='pressact', group_by='trace_id')
df = pd.DataFrame({'trace_id': ['t1', 't2'], 'value': [10, 20]})
chart_bytes = render_chart(p, df)
print(f'✅ 차트 생성: {len(chart_bytes)} bytes')
"
```

**테스트 포인트:**
- 차트 이미지 생성
- 다양한 analysis_type별 차트
- 한글 폰트 적용

### 6. 요약 생성 (`src/services/summary.py`)

```bash
python3 -c "
import pandas as pd
from src.nl_parse_v2 import Parsed
from src.services.summary import make_summary
p = Parsed(metric='avg', column='pressact')
df = pd.DataFrame({'value': [10.5, 20.3, 15.7]})
summary = make_summary(p, df)
print(f'✅ 요약: {summary}')
"
```

**테스트 포인트:**
- 통계 요약 생성
- 다양한 metric 타입별 요약

### 7. 정규화 모듈 (`domain/rules/normalization.py`)

```bash
python3 -c "
from domain.rules.normalization import normalize
tests = ['압력 평균', '암모니아가스 유량', '스텝별 pressact 평균 top10']
for q in tests:
    n = normalize(q)
    print(f'{q:30} -> {n.text}')
"
```

**테스트 포인트:**
- 동의어 치환
- 접합어 분리
- 패턴 정규화

## 통합 테스트 (전체 파이프라인)

```bash
python3 -c "
from src.nl_parse_v2 import parse_question
from src.sql_builder import build_sql
import duckdb
from pathlib import Path

# 1. 파싱
q = '압력 평균'
parsed = parse_question(q)
print(f'✅ 파싱: {parsed.column}, {parsed.metric}')

# 2. SQL 생성
sql, params = build_sql(parsed)
print(f'✅ SQL 생성: {len(sql)} chars')

# 3. 실행 (DB 있으면)
db = Path('data_out/ald.duckdb')
if db.exists():
    con = duckdb.connect(str(db))
    df = con.execute(sql, params).df()
    print(f'✅ 실행 성공: {len(df)} rows')
    con.close()
"
```

## 특정 모듈만 테스트

```bash
# 파서만
python3 -c "from src.nl_parse_v2 import parse_question; print(parse_question('압력 평균'))"

# SQL 빌더만
python3 -c "from src.sql_builder import build_sql; from src.nl_parse_v2 import Parsed; print(build_sql(Parsed(metric='avg', column='pressact')))"

# 정규화만
python3 -c "from domain.rules.normalization import normalize; print(normalize('압력 평균'))"
```

## 문제 진단

### 모듈 import 실패
```bash
# Python 경로 확인
python3 -c "import sys; print('\n'.join(sys.path))"

# 모듈 위치 확인
python3 -c "from src.nl_parse_v2 import parse_question; import inspect; print(inspect.getfile(parse_question))"
```

### DB 연결 실패
```bash
# DB 파일 확인
ls -lh data_out/ald.duckdb

# DB 내용 확인
python3 -c "import duckdb; con = duckdb.connect('data_out/ald.duckdb'); print(con.execute('SELECT COUNT(*) FROM traces').fetchone())"
```

### 의존성 문제
```bash
# 필요한 패키지 확인
python3 -c "import duckdb, pandas, matplotlib, yaml; print('✅ 모든 의존성 OK')"
```

