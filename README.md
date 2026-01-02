# ALD NL2SQL Stats

자연어를 SQL로 변환하는 ALD 공정 데이터 분석 시스템

## CSV 필드명 추출 기능

애플리케이션 실행 시 커맨드라인 인자로 CSV 파일명을 입력받아 해당 파일의 모든 필드명을 출력하고, 텍스트 파일(`fout.txt`)에 저장하는 기능이 포함되어 있습니다.

### 사용 방법

```bash
# 1. 가상환경 활성화
source venv/bin/activate

# 2. 프로젝트 루트로 이동
cd /home/keti_spark1/yune/ald-nl2sql

# 3. CSV 필드명 추출 모드 실행
PYTHONPATH=. python src/app.py --csv <CSV파일경로>

# 4. 출력 파일명 지정 (기본값: fout.txt)
PYTHONPATH=. python src/app.py --csv <CSV파일경로> --output <출력파일명>
```

**참고**: `PYTHONPATH=.`는 현재 디렉토리를 Python 모듈 검색 경로에 추가하는 것입니다. 프로젝트 루트에서 실행할 때 필요합니다.

### 예시

```bash
# 예시 1: 기본 사용 (fout.txt에 저장)
python src/app.py --csv data/sample.csv

# 예시 2: 출력 파일명 지정
python src/app.py --csv data/sample.csv --output fields.txt

# 예시 3: 상대 경로 사용
python src/app.py --csv ../data_in/traces.csv
```

### 출력 형식

1. **콘솔 출력**: CSV 파일의 모든 필드명이 번호와 함께 콘솔에 출력됩니다.
2. **텍스트 파일**: `fout.txt` (또는 지정한 파일명)에 다음 정보가 저장됩니다:
   - CSV 파일 경로
   - 총 필드 개수
   - 필드명 목록 (번호와 함께)

### 출력 파일 예시 (fout.txt)

```
CSV 파일: data/sample.csv
총 필드 개수: 15
============================================================
필드명 목록:
============================================================
  1. trace_id
  2. step_name
  3. timestamp
  4. pressact
  5. vg11
  6. vg12
  7. ...
============================================================
```

### 서버 실행 모드

CSV 파일을 지정하지 않으면 기본적으로 FastAPI 서버가 실행됩니다:

```bash
# 기본 서버 실행 (포트 8000)
python src/app.py

# 호스트와 포트 지정
python src/app.py --host 127.0.0.1 --port 8080
```

### 주의사항

- CSV 파일이 존재하지 않으면 오류 메시지가 출력되고 프로그램이 종료됩니다.
- 출력 파일이 이미 존재하는 경우 덮어씌워집니다.
- CSV 파일의 첫 번째 행(헤더)만 읽어서 필드명을 추출합니다.
