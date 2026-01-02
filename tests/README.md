# tests/ 디렉토리 설명

이 디렉토리는 프로젝트의 테스트 코드와 테스트 자산을 포함합니다. 자연어 파서의 정확성을 보장하고 각 모듈의 동작을 검증합니다.

## 📋 파일 목록

### 테스트 스크립트

#### `test_parser.py`
**역할**: 자연어 파서 테스트 실행 스크립트

**실제 사용**: ✅ 파서 정확성 검증에 사용됨

**사용 방법**:
```bash
# 기본 테스트 실행
python tests/test_parser.py

# 상세 출력
python tests/test_parser.py --verbose

# 예상 결과 업데이트
python tests/test_parser.py --update
```

**기능**:
- `questions.jsonl`에서 테스트 케이스 읽기
- 각 질문에 대해 파싱 실행
- 예상 결과와 실제 결과 비교
- 실패한 케이스 보고

---

#### `test_parser_pytest.py`
**역할**: pytest 기반 파서 테스트

**실제 사용**: ✅ pytest로 테스트 실행 시 사용됨

**사용 방법**:
```bash
pytest tests/test_parser_pytest.py -v
```

---

#### `test_modules.py`
**역할**: 각 모듈별 단위 테스트

**실제 사용**: ✅ 모듈별 동작 검증에 사용됨

**테스트 항목**:
- 파서 모듈 테스트
- SQL 빌더 모듈 테스트
- 해석 레이어 테스트
- 차트 렌더링 테스트

**사용 방법**:
```bash
python tests/test_modules.py
```

---

#### `test_individual_modules.sh`
**역할**: 개별 모듈 테스트 스크립트

**실제 사용**: ✅ 쉘 스크립트로 모듈 테스트 실행

---

### 테스트 데이터

#### `questions.jsonl`
**역할**: 테스트 질문과 예상 결과

**실제 사용**: ✅ `test_parser.py`에서 테스트 케이스로 사용됨

**형식**:
```json
{"q": "챔버 압력 평균", "expect": {"metric": "avg", "column": "pressact"}}
{"q": "공정별 pressact 평균 top5", "expect": {"metric": "avg", "column": "pressact", "group_by": "trace_id", "top_n": 5, "analysis_type": "ranking"}}
```

**필드 설명**:
- `q`: 테스트할 질문 (문자열)
- `expect`: 예상 파싱 결과 (객체)

---

#### `expected_parsed.jsonl`
**역할**: 예상 파싱 결과 (선택사항, 자동 생성 가능)

**실제 사용**: ✅ `test_parser.py --update`로 자동 생성됨

---

### 테스트 유틸리티

#### `check_table_structure.py`
**역할**: 데이터베이스 테이블 구조 확인

**실제 사용**: ✅ 데이터베이스 구조 검증에 사용됨

---

#### `generate_test_cases.py`
**역할**: 테스트 케이스 자동 생성

**실제 사용**: ✅ 테스트 케이스 생성에 사용됨

---

### 테스트 가이드 문서

#### `MODULE_TEST_GUIDE.md`
**역할**: 모듈별 테스트 가이드

**실제 사용**: ✅ 개발자가 테스트 작성 시 참고

---

#### `TEST_GUIDE.md`
**역할**: 전체 테스트 가이드

**실제 사용**: ✅ 테스트 실행 방법 안내

---

## 🧪 테스트 실행 방법

### 파서 테스트

```bash
# 기본 실행
cd /home/keti_spark1/yune/ald-nl2sql
source venv/bin/activate
python tests/test_parser.py
```

**출력 예시**:
```
=== 파서 테스트 ===
✅ '챔버 압력 평균' → col=pressact, agg=avg
✅ '공정별 압력 평균 top5' → col=pressact, agg=avg, group_by=trace_id, limit=5
❌ '압력 최대값' → 예상: col=pressact, 실제: col=None
```

### 모듈별 테스트

```bash
python tests/test_modules.py
```

**테스트 항목**:
1. 파서 모듈 테스트
2. SQL 빌더 모듈 테스트
3. 해석 레이어 테스트
4. 차트 렌더링 테스트

### pytest 실행

```bash
pytest tests/test_parser_pytest.py -v
```

---

## 📝 테스트 케이스 추가 방법

### 1. questions.jsonl에 추가

```json
{"q": "새로운 질문", "expect": {"metric": "avg", "column": "pressact"}}
```

### 2. 테스트 실행

```bash
python tests/test_parser.py
```

### 3. 실패 시 처리

- 예상 결과를 수정하거나
- 파서 로직을 수정

---

## 📊 예상 결과 형식

예상 결과는 표준 Parsed JSON 스키마를 따릅니다:

```json
{
  "metric": "avg",
  "column": "pressact",
  "group_by": "trace_id",
  "filters": {
    "trace_id": "standard_trace_001"
  },
  "top_n": 5,
  "analysis_type": "ranking",
  "flags": {
    "is_trace_compare": false,
    "is_outlier": false
  }
}
```

### 필드 설명

- `metric`: 집계 함수 (avg, min, max, count, std, etc.)
- `column`: 분석할 컬럼명
- `group_by`: 그룹핑 기준 (trace_id, step_name, date, hour, day)
- `filters`: 필터 조건 객체
  - `trace_id`: 단일 공정 ID
  - `trace_ids`: 여러 공정 ID (비교용)
  - `step_name`: 단일 단계명
  - `step_names`: 여러 단계명 (비교용)
  - `date_start`: 시작 날짜
  - `date_end`: 종료 날짜
- `top_n`: 상위 N개 제한
- `analysis_type`: 분석 유형 (ranking, group_profile, comparison, stability)
- `flags`: 특수 분석 플래그
  - `is_trace_compare`: 공정 비교
  - `is_outlier`: 이상치 탐지
  - `is_dwell_time`: 체류 시간
  - `is_overshoot`: 오버슈트
  - `is_stable_avg`: 안정화 구간 평균

---

## ⚠️ 중요 사항

- **Parsed JSON 스키마는 절대 변경되지 않아야 합니다**
- 이 스키마는 LLM을 사용하든 안 하든 최종 인터페이스입니다
- SQL은 이 스키마를 소비하는 하위 구현일 뿐입니다
- 하나를 고쳐서 전체가 깨지는 일을 방지하기 위해 테스트가 필수입니다

---

## 🔄 테스트 워크플로우

```
1. questions.jsonl에 테스트 케이스 추가
    ↓
2. test_parser.py 실행
    ↓
3. 파싱 결과 확인
    ↓
4. 실패 시:
   - 예상 결과 수정 (파서가 맞는 경우)
   - 파서 로직 수정 (파서가 틀린 경우)
    ↓
5. 모든 테스트 통과 확인
```

---

## 📚 관련 문서

- `MODULE_TEST_GUIDE.md`: 모듈별 테스트 가이드
- `TEST_GUIDE.md`: 전체 테스트 가이드
- `../docs/PARSED_SCHEMA.md`: Parsed 객체 스키마 상세 설명
