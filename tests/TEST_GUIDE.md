# 테스트 실행 가이드

## 빠른 시작

### 1. 테스트 케이스 생성 (200개)

```bash
cd /home/keti_spark1/yune/ald-nl2sql
python tests/generate_test_cases.py
```

이 명령어는 `tests/questions.jsonl`에 200개의 테스트 케이스를 생성합니다.

### 2. pytest 설치 (필요시)

```bash
pip install pytest
```

### 3. 테스트 실행

#### 기본 실행 (간단한 결과만)
```bash
pytest tests/test_parser_pytest.py -v
```

#### 상세 출력 (실패한 테스트의 차이점 표시)
```bash
pytest tests/test_parser_pytest.py -v -s
```

#### 특정 테스트만 실행 (예: 라인 10번)
```bash
pytest tests/test_parser_pytest.py::test_parse_question[line10:챔버 압력 평균] -v
```

#### 실패한 테스트만 다시 실행
```bash
pytest tests/test_parser_pytest.py --lf -v
```

#### 통계 출력
```bash
pytest tests/test_parser_pytest.py -v --tb=short
```

### 4. 기존 테스트 스크립트 (선택사항)

기존 `test_parser.py`도 여전히 사용 가능합니다:

```bash
python tests/test_parser.py
python tests/test_parser.py --verbose
python tests/test_parser.py --update  # 예상 결과 업데이트
```

## 질문 타입별 분류

생성된 200개 테스트는 다음 8개 타입으로 분류됩니다:

1. **단일 집계** (30개): "챔버 압력 평균", "압력 최대" 등
2. **group by step** (30개): "스텝별 pressact 평균", "단계별 압력 최대" 등
3. **group by trace** (30개): "공정별 pressact 평균 top5" 등
4. **비교** (20개): "standard_trace_001과 standard_trace_002 pressact 비교" 등
5. **시간 집계** (20개): "pressact 일별 평균", "압력 시간별 최대" 등
6. **필터** (20개): "standard_trace_001 step=STANDBY pressact 최대" 등
7. **이상치** (15개): "pressact 이상치 top5" 등
8. **공정지표** (15개): "pressact overshoot top10", "압력 체류시간" 등
9. **Top N 변형** (10개): "상위 3개", "top5" 등

## 테스트 결과 해석

### 성공 예시
```
tests/test_parser_pytest.py::test_parse_question[line1:챔버 압력 평균] PASSED
```

### 실패 예시
```
tests/test_parser_pytest.py::test_parse_question[line5:공정별 pressact 평균 top5] FAILED
[테스트 #5, 라인 5] '공정별 pressact 평균 top5'
예상: {'metric': 'avg', 'column': 'pressact', 'group_by': 'trace_id', 'top_n': 5, 'analysis_type': 'ranking'}
실제: {'metric': 'avg', 'column': 'pressact', 'group_by': 'trace_id', 'top_n': 5, 'analysis_type': 'group_profile'}
차이점:
  - analysis_type: 예상=ranking, 실제=group_profile
```

## 문제 해결

### 테스트가 모두 실패하는 경우

1. 파서 코드가 변경되었을 수 있습니다
2. `tests/questions.jsonl`의 예상 결과를 업데이트해야 할 수 있습니다
3. 파서 로직을 확인하세요

### 특정 질문 타입만 실패하는 경우

1. 해당 타입의 파싱 로직을 확인하세요
2. `domain/rules/` 또는 `src/nl_parse_v2.py`를 확인하세요

### 예상 결과 업데이트

파서 로직이 변경되어 예상 결과가 바뀌었다면:

```bash
python tests/test_parser.py --update
```

이 명령어는 실제 파싱 결과를 `tests/expected_parsed.jsonl`에 저장합니다.
그 후 `tests/questions.jsonl`의 `expect` 필드를 수동으로 업데이트하세요.

## CI/CD 통합

GitHub Actions 등에서 자동 테스트를 실행하려면:

```yaml
# .github/workflows/test.yml
name: Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: pip install pytest
      - run: python tests/generate_test_cases.py
      - run: pytest tests/test_parser_pytest.py -v
```

## 다음 단계

테스트가 모두 통과하면:
1. 새로운 질문 타입 추가 시 `tests/generate_test_cases.py`에 추가
2. `python tests/generate_test_cases.py`로 재생성
3. `pytest tests/test_parser_pytest.py -v`로 확인

