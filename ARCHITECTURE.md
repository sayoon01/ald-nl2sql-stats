# 아키텍처 개요

## 핵심 설계 원칙

### 사용자 언어 ↔ 시스템 언어 분리

**문제**: 사용자가 "압력"이라고 말하면, 시스템에는 `pressact`, `vg11`, `vg12`, `vg13` 등 여러 센서가 존재한다.

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

**확장성**: 데이터가 늘어나는 복잡도를 규칙/스키마로 흡수한다.
- 새 센서 추가 → `columns.yaml`에 컬럼 정의만 추가
- 모호성 해결 → `pressure_resolution.yaml`에 규칙만 추가
- 코드 변경 없이 자동 인식 ✅

### 예시: 모호성 해결

| 사용자 입력 | 정규화 결과 | 모호성 해결 | 최종 컬럼 |
|-----------|-----------|-----------|---------|
| "압력 평균" | `pressact avg` | 기본값 적용 | `pressact` |
| "VG11 압력 평균" | `vg11 pressact avg` | 구체적 센서 우선 | `vg11` |
| "게이지11 압력 최대" | `vg11 pressact max` | 동의어 + 구체적 센서 | `vg11` |
| "챔버 압력 평균" | `pressact avg` | 컨텍스트 키워드 | `pressact` |
| "질소 유량 평균" | `mfcmon_n2_1 avg` | 기본 유량 채널 | `mfcmon_n2_1` |
| "n2-2 유량 평균" | `mfcmon_n2_2 avg` | 구체적 채널 | `mfcmon_n2_2` |

## 전체 구조

```
[사람 질문]
   ↓
[NLP 전처리 Layer] - domain/rules/normalization.py
   - normalize (소문자, 동의어 치환)
   - pattern extract (top5, step=STANDBY 등)
   ↓
[도메인 파서 Layer] - src/nl_parse_v2.py
   - intent (의도 파악)
   - slots (metric, column, group, filter, compare)
   ↓
[도메인 메타데이터] - domain/schema/*.yaml
   - 컬럼 의미 (columns.yaml)
   - 단위 (units.yaml)
   - 공정 의미
   ↓
[SQL Builder / Analysis Engine] - src/sql_builder.py, process_metrics.py
   ↓
[DB / DuckDB]
```

## 핵심 디렉토리: `domain/`

프로젝트의 심장부입니다. 모든 도메인 지식이 YAML 파일로 관리됩니다.

### 구조

```
domain/
├── schema/          # 도메인 스키마 정의
│   ├── columns.yaml # 컬럼 메타데이터
│   ├── metrics.yaml # 집계 함수/지표 정의
│   ├── groups.yaml  # 그룹핑 정의
│   └── units.yaml   # 단위 정의
├── synonyms/        # 동의어 사전
│   ├── columns.yaml # 컬럼 동의어
│   ├── metrics.yaml # 지표 동의어
│   ├── groups.yaml  # 그룹핑 동의어
│   └── patterns.yaml # 패턴 정규화 규칙
└── rules/           # 규칙 엔진
    ├── normalization.py # 질문 정규화
    ├── validation.py    # 도메인 규칙 검증
    ├── resolution.py   # 모호성 해결 (압력/유량 등)
    ├── fallback.py      # 기본값/추론 규칙
    └── pressure_resolution.yaml # 모호성 해결 규칙 정의
```

## 데이터 흐름

### 1. 질문 입력
```
"챔버 압력 평균"
```

### 2. 정규화 (normalization.py)
```python
normalize("챔버 압력 평균")
# → "pressact avg"
```
- 소문자 변환
- 동의어 치환 (챔버 압력 → pressact)
- 패턴 정규화 (top5 → top5)

### 3. 도메인 파싱 (nl_parse_v2.py)
```python
parse_question("vg11 pressact avg")
# → Parsed(col="vg11", agg="avg", ...)
```
- 컬럼 추출: `vg11` (정규화 결과에서)
- **모호성 해결**: `vg11 pressact` → `vg11` (구체적 센서 우선)
- 집계 함수 추출: `avg`
- 그룹핑 추출: `None`
- 필터 추출: `None`

### 4. 메타데이터 조회 (validation.py)
```python
validator.get_column_info("pressact")
# → {
#     "domain_name": "챔버 압력",
#     "unit": "mTorr",
#     "type": "continuous",
#     ...
# }
```

### 5. SQL 생성 (sql_builder.py)
```sql
SELECT AVG(pressact) as value
FROM traces
```

### 6. 결과 반환
```json
{
  "ok": true,
  "question": "챔버 압력 평균",
  "sql": "SELECT AVG(pressact) as value FROM traces",
  "rows": [{"value": 3.456}],
  "summary": "챔버 압력 평균=3.456 mTorr"
}
```

## 확장 방법

### 새 컬럼 추가

1. `domain/schema/columns.yaml`에 추가:
```yaml
vg14:  # 새 진공 게이지 추가 예시
  domain_name: "진공 게이지 14 압력"
  physical_type: "pressure"
  unit: "mTorr"
  csv_columns: ["VG14"]
  aliases: ["vg14", "게이지14", "진공게이지14", "vacuum gauge 14"]
```

2. 모호성 해결 규칙 추가 (필요시):
`domain/rules/pressure_resolution.yaml`에 추가:
```yaml
resolution:
  context_overrides:
    - if_any_tokens: ["vg14", "게이지14"]
      prefer_column: "vg14"
      suppress_generic_pressure_token: true
```

3. 코드 수정 없음! 자동으로 인식됩니다. ✅

### 새 지표 추가

1. `domain/schema/metrics.yaml`에 추가:
```yaml
overshoot:
  label: 오버슈트
  sql: custom
  description: 목표값 대비 초과량
```

2. `domain/synonyms/metrics.yaml`에 동의어 추가:
```yaml
overshoot:
  - 오버슈트
  - overshoot
  - 초과
```

3. `src/process_metrics.py`에 SQL 빌더 추가 (필요시)

### 새 그룹핑 추가

1. `domain/schema/groups.yaml`에 추가:
```yaml
week:
  label: 주별
  description: 주 단위 그룹핑
  sql_expr: DATE_TRUNC('week', timestamp)
  type: temporal
```

2. `domain/synonyms/groups.yaml`에 동의어 추가:
```yaml
week:
  - 주별
  - week별
  - 주
```

## 장점

1. **DB 독립적**: DB 컬럼명이 바뀌어도 YAML만 수정 (`csv_columns` 필드)
2. **확장 용이**: 새 컬럼/지표 추가가 간단 (YAML만 수정)
3. **유지보수 용이**: 하드코딩 없이 설정 파일로 관리
4. **모호성 해결**: resolution 규칙으로 복잡도 흡수
5. **테스트 용이**: 메타데이터 기반으로 테스트 작성 가능
6. **다국어 지원 가능**: 동의어 사전으로 확장 가능
7. **확장성**: 데이터 증가 시 규칙/스키마로 복잡도 관리

## 마이그레이션

기존 `nl_parse.py`는 하드코딩된 규칙을 사용했습니다.
새 `nl_parse_v2.py`는 도메인 메타데이터를 사용합니다.

`app.py`에서는 자동으로 새 파서를 사용하려고 시도하고, 실패하면 기존 파서로 fallback합니다:

```python
try:
    from src.nl_parse_v2 import parse_question
except ImportError:
    from src.nl_parse import parse_question
```

## 다음 단계

1. ✅ 도메인 메타데이터 구조 생성
2. ✅ 정규화 파이프라인 구현
3. ✅ 새 파서 구현
4. ⏳ 기존 파서 완전 교체 (선택사항)
5. ⏳ 더 많은 컬럼/지표 추가
6. ⏳ 패턴 정규화 강화

