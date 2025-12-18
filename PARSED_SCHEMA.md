# Parsed JSON 스키마

## 중요 사항

❗ **이 JSON 스키마는 절대 변경되지 않아야 하는 중간 표현입니다.**

- LLM을 사용하든 안 사용하든 **최종 인터페이스**입니다
- SQL은 이 스키마를 소비하는 하위 구현일 뿐입니다
- 하나를 고쳐서 전체가 깨지는 일을 방지하기 위해 테스트가 필수입니다

## 스키마 정의

```json
{
  "metric": "avg",
  "column": "pressact",
  "group_by": "step_name",
  "filters": {
    "trace_id": "standard_trace_001"
  },
  "top_n": null,
  "analysis_type": "group_profile",
  "flags": {
    "is_trace_compare": false,
    "is_outlier": false,
    "is_dwell_time": false,
    "is_overshoot": false,
    "is_stable_avg": false
  }
}
```

## 필드 설명

### 필수 필드

- `metric` (string, required): 집계 함수
  - 가능한 값: `"avg"`, `"min"`, `"max"`, `"count"`, `"std"`, `"stddev"`, `"p50"`, `"median"`, `"p95"`, `"p99"`, `"null_ratio"`

- `column` (string | null, required): 분석할 컬럼명 (DB 컬럼명)
  - 예: `"pressact"`, `"vg11"`, `"apcvalvemon"`

### 선택 필드

- `group_by` (string | null): 그룹핑 기준
  - 가능한 값: `"trace_id"`, `"step_name"`, `"date"`, `"hour"`, `"day"`

- `filters` (object): 필터 조건
  - `trace_id` (string | null): 단일 공정 ID 필터
  - `trace_ids` (array<string>): 여러 공정 ID 필터 (비교용)
  - `step_name` (string | null): 단일 단계명 필터
  - `step_names` (array<string>): 여러 단계명 필터 (비교용)
  - `date_start` (string | null): 시작 날짜 (YYYY-MM-DD)
  - `date_end` (string | null): 종료 날짜 (YYYY-MM-DD)

- `top_n` (integer | null): 상위 N개 제한
  - 최소값: 1

- `analysis_type` (string): 분석 유형
  - 가능한 값: `"ranking"`, `"group_profile"`, `"comparison"`, `"stability"`

- `flags` (object): 특수 분석 플래그
  - `is_trace_compare` (boolean): 공정 비교 분석
  - `is_outlier` (boolean): 이상치 탐지
  - `is_dwell_time` (boolean): 체류 시간 분석
  - `is_overshoot` (boolean): 오버슈트 분석
  - `is_stable_avg` (boolean): 안정화 구간 평균

## 예시

### 기본 통계

```json
{
  "metric": "avg",
  "column": "pressact"
}
```

### 그룹별 분석

```json
{
  "metric": "avg",
  "column": "pressact",
  "group_by": "trace_id",
  "top_n": 5,
  "analysis_type": "ranking"
}
```

### 필터링

```json
{
  "metric": "max",
  "column": "pressact",
  "filters": {
    "trace_id": "standard_trace_001",
    "step_name": "STANDBY"
  }
}
```

### 비교 분석

```json
{
  "metric": "avg",
  "column": "pressact",
  "filters": {
    "trace_ids": ["standard_trace_001", "standard_trace_002"]
  },
  "flags": {
    "is_trace_compare": true
  },
  "analysis_type": "comparison"
}
```

### 특수 지표

```json
{
  "metric": "avg",
  "column": "pressact",
  "top_n": 10,
  "flags": {
    "is_overshoot": true
  },
  "analysis_type": "stability"
}
```

## 구현

### Python 클래스

```python
from src.nl_parse_v2 import Parsed, parse_question

# 질문 파싱
parsed = parse_question("챔버 압력 평균")

# JSON 변환
json_data = parsed.to_dict()

# JSON에서 생성
parsed = Parsed.from_dict(json_data)
```

### 하위 호환성

기존 코드와의 호환성을 위해 다음 속성들이 제공됩니다:

- `parsed.col` → `parsed.column`
- `parsed.agg` → `parsed.metric`
- `parsed.trace_id` → `parsed.filters.get("trace_id")`
- `parsed.is_trace_compare` → `parsed.flags.get("is_trace_compare")`

## 테스트

표준 스키마 준수를 보장하기 위해 테스트 프레임워크가 제공됩니다:

```bash
python tests/test_parser.py
```

자세한 내용은 `tests/README.md`를 참조하세요.

