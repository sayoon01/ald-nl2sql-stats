# 파서 테스트 프레임워크

이 디렉토리는 자연어 파서의 정확성을 보장하는 테스트 자산을 포함합니다.

## 파일 구조

```
tests/
├── questions.jsonl      # 테스트 질문과 예상 결과
├── expected_parsed.jsonl # 예상 파싱 결과 (선택사항, 자동 생성 가능)
├── test_parser.py       # 테스트 실행 스크립트
└── README.md           # 이 파일
```

## 사용 방법

### 테스트 실행

```bash
cd /home/keti_spark1/yune/ald-nl2sql
source venv/bin/activate
python tests/test_parser.py
```

### 상세 출력

```bash
python tests/test_parser.py --verbose
```

### 예상 결과 업데이트

실제 파싱 결과를 기반으로 예상 결과를 업데이트:

```bash
python tests/test_parser.py --update
```

## questions.jsonl 형식

각 줄은 JSON 객체로, 다음 필드를 포함합니다:

- `q`: 테스트할 질문 (문자열)
- `expect`: 예상 파싱 결과 (객체)

### 예시

```json
{"q": "챔버 압력 평균", "expect": {"metric": "avg", "column": "pressact"}}
{"q": "공정별 pressact 평균 top5", "expect": {"metric": "avg", "column": "pressact", "group_by": "trace_id", "top_n": 5, "analysis_type": "ranking"}}
```

## 예상 결과 형식

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

## 테스트 추가 방법

1. `questions.jsonl`에 새 테스트 케이스 추가:

```json
{"q": "새로운 질문", "expect": {"metric": "avg", "column": "pressact"}}
```

2. 테스트 실행:

```bash
python tests/test_parser.py
```

3. 실패하면 예상 결과를 수정하거나 파서 로직을 수정

## 중요 사항

- **Parsed JSON 스키마는 절대 변경되지 않아야 합니다**
- 이 스키마는 LLM을 사용하든 안 하든 최종 인터페이스입니다
- SQL은 이 스키마를 소비하는 하위 구현일 뿐입니다
- 하나를 고쳐서 전체가 깨지는 일을 방지하기 위해 테스트가 필수입니다

