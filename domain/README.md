# Domain 메타데이터 디렉토리

이 디렉토리는 **프로젝트의 심장부**입니다. 모든 도메인 지식이 YAML 파일과 Python 규칙으로 관리됩니다. 코드 수정 없이 도메인 지식을 업데이트할 수 있습니다.

## 🎯 핵심 설계 원칙

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
- **코드 변경 없이 자동 인식** ✅

---

## 📁 디렉토리 구조

```
domain/
├── schema/                    # 도메인 스키마 정의
│   ├── columns.yaml           # 컬럼 메타데이터 (도메인 키 ↔ CSV 컬럼명)
│   ├── metrics.yaml           # 집계 함수/지표 정의
│   ├── groups.yaml            # 그룹핑 정의
│   ├── units.yaml             # 단위 정의
│   ├── load_schema.py         # YAML 스키마 로더
│   └── parsed_schema.json      # Parsed 객체 JSON 스키마
├── synonyms/                  # 동의어 사전
│   ├── columns.yaml           # 컬럼 동의어 (하위 호환성)
│   ├── metrics.yaml           # 지표 동의어
│   ├── groups.yaml            # 그룹핑 동의어
│   └── patterns.yaml          # 패턴 정규화 규칙
└── rules/                     # 규칙 엔진
    ├── normalization.py       # 질문 정규화 (동의어 치환, 패턴 정규화)
    ├── validation.py          # 도메인 규칙 검증
    ├── resolution.py          # 모호성 해결 (압력/유량 등)
    ├── fallback.py            # 기본값/추론 규칙
    └── pressure_resolution.yaml # 모호성 해결 규칙 정의
```

---

## 📋 주요 파일 상세 설명

### `schema/columns.yaml`
**역할**: 컬럼 메타데이터 정의 (도메인 키 ↔ CSV 실제 컬럼명 매핑)

**실제 사용**: ✅ 모든 파싱과 SQL 생성에 사용됨

**구조**:
```yaml
version: 1
dataset: "standard_traces"
primary_table: "traces"

defaults:
  decimals_by_type:
    pressure: 3      # 압력 타입 기본 소수점 자리수
    flow: 1          # 유량 타입 기본 소수점 자리수
    temperature: 1  # 온도 타입 기본 소수점 자리수
  
  unit_label:
    mTorr: "mTorr"   # 단위 코드 → 화면 표시 라벨
    Torr: "Torr"
    sccm: "sccm"

columns:
  pressact:
    domain_name: "챔버 압력"      # 한글 이름
    physical_type: "pressure"    # 물리적 타입
    unit: "mTorr"                 # 단위 코드
    csv_columns: ["pressact"]     # 실제 DB 컬럼명 (slugify 후)
    aliases:                      # 동의어 목록
      - "챔버 압력"
      - "압력"
      - "진공"
      - "chamber pressure"
      - "pressure"
    decimals: 3                   # 소수점 자리수 (선택, 기본값 오버라이드)
```

**핵심**: 코드에서는 `pressact` 같은 도메인 키만 사용하고, 실제 SQL에서는 `csv_columns`의 `pressact`를 사용한다.

**사용 위치**:
- `nl_parse_v2.py`: 컬럼 추출 시 동의어 매칭
- `sql_builder.py`: 컬럼명 검증 및 변환
- `app.py`: 포맷팅 규칙 적용 (decimals, unit)

---

### `schema/metrics.yaml`
**역할**: 집계 함수/지표 정의

**실제 사용**: ✅ 파싱 시 집계 함수 인식에 사용됨

**구조**:
```yaml
avg:
  label: "평균"
  sql: "AVG"
  description: "산술 평균"

max:
  label: "최대"
  sql: "MAX"
  description: "최대값"

std:
  label: "표준편차"
  sql: "STDDEV"
  description: "표준편차"
```

**사용 위치**:
- `nl_parse_v2.py`: `_pick_agg()` 함수에서 지표 추출
- `domain/rules/validation.py`: 지표 유효성 검증

---

### `schema/groups.yaml`
**역할**: 그룹핑 정의

**실제 사용**: ✅ 파싱 시 그룹핑 인식에 사용됨

**구조**:
```yaml
step_name:
  label: "스텝별"
  description: "단계명별 그룹핑"
  sql_expr: "step_name"
  type: "categorical"

trace_id:
  label: "공정별"
  description: "공정 ID별 그룹핑"
  sql_expr: "trace_id"
  type: "categorical"
```

**사용 위치**:
- `nl_parse_v2.py`: `_pick_group_by()` 함수에서 그룹핑 추출
- `sql_builder.py`: GROUP BY 절 생성

---

### `synonyms/columns.yaml`
**역할**: 컬럼 동의어 사전 (하위 호환성)

**실제 사용**: ✅ 정규화 단계에서 동의어 치환에 사용됨

**구조**:
```yaml
pressact:
  - 챔버 압력
  - 챔버압
  - 압력
  - 진공
  - pressure
  - 압력 실측
  - 현재 압력
```

**사용 위치**:
- `domain/rules/normalization.py`: 질문 정규화 시 동의어 치환

---

### `synonyms/metrics.yaml`
**역할**: 지표 동의어 사전

**실제 사용**: ✅ 정규화 단계에서 지표 동의어 치환에 사용됨

**구조**:
```yaml
avg:
  - 평균
  - average
  - mean

max:
  - 최대
  - 최대값
  - maximum
```

---

### `synonyms/groups.yaml`
**역할**: 그룹핑 동의어 사전

**실제 사용**: ✅ 정규화 단계에서 그룹핑 동의어 치환에 사용됨

**구조**:
```yaml
step_name:
  - 스텝별
  - 단계별
  - step별
  - step by step

trace_id:
  - 공정별
  - trace별
  - 공정
```

---

### `synonyms/patterns.yaml`
**역할**: 패턴 정규화 규칙

**실제 사용**: ✅ 정규화 단계에서 패턴 정규화에 사용됨

**구조**:
```yaml
patterns:
  - pattern: "top\\s*(\\d+)"
    replacement: "top\\1"
    description: "top 5 → top5"
  
  - pattern: "step\\s*[:=]\\s*([A-Z0-9_]+)"
    replacement: "step_name=\\1"
    description: "step=STANDBY → step_name=STANDBY"
```

---

### `rules/normalization.py`
**역할**: 질문 정규화 파이프라인

**실제 사용**: ✅ 모든 질문 처리 전에 실행됨

**주요 클래스/함수**:
- `Normalizer`: 정규화 클래스 (싱글톤)
- `normalize(text: str) -> NormalizedText`: 메인 정규화 함수

**정규화 단계**:
1. **소문자 변환**: "압력" → "압력" (한글은 그대로)
2. **동의어 치환**: `synonyms/columns.yaml`, `synonyms/metrics.yaml` 사용
   - "챔버 압력" → "pressact"
   - "평균" → "avg"
3. **패턴 정규화**: `synonyms/patterns.yaml` 사용
   - "top 5" → "top5"
   - "step=STANDBY" → "step_name=STANDBY"

**사용 예시**:
```python
from domain.rules.normalization import normalize

result = normalize("챔버 압력 평균")
# → NormalizedText(raw="챔버 압력 평균", text="pressact avg")
```

---

### `rules/validation.py`
**역할**: 도메인 규칙 검증

**실제 사용**: ✅ 파싱 후 유효성 검증에 사용됨

**주요 클래스/함수**:
- `Validator`: 검증 클래스 (싱글톤)
- `get_validator() -> Validator`: 싱글톤 인스턴스 반환
- `is_valid_column(column: str) -> bool`: 컬럼 유효성 검증
- `is_valid_metric(metric: str) -> bool`: 지표 유효성 검증
- `get_column_info(column: str) -> Optional[dict]`: 컬럼 정보 조회

**사용 위치**:
- `nl_parse_v2.py`: 파싱 후 유효성 검증
- `sql_builder.py`: SQL 생성 전 컬럼 검증

---

### `rules/resolution.py`
**역할**: 모호성 해결 로직

**실제 사용**: ✅ 여러 컬럼이 매칭될 때 우선순위 결정에 사용됨

**주요 함수**:
- `resolve_column_from_text(text: str, matched_column: str) -> str`: 모호성 해결

**해결 규칙** (우선순위):
1. **구체적 센서 우선**: "VG11 압력" → `vg11` (pressact보다 우선)
2. **컨텍스트 키워드**: "챔버 압력" → `pressact`
3. **기본값**: "압력" → `pressact` (가장 일반적인 컬럼)

**사용 위치**:
- `nl_parse_v2.py`: `_pick_col()` 함수에서 모호성 해결

---

### `rules/pressure_resolution.yaml`
**역할**: 압력 관련 모호성 해결 규칙 정의

**실제 사용**: ✅ `rules/resolution.py`에서 규칙 로드에 사용됨

**구조**:
```yaml
resolution:
  context_overrides:
    - if_any_tokens: ["vg11", "게이지11"]
      prefer_column: "vg11"
      suppress_generic_pressure_token: true  # pressact 제거
```

**예시**:
- "VG11 압력" → `vg11` (pressact 제거)
- "압력 평균" → `pressact` (기본값)

---

### `rules/fallback.py`
**역할**: 기본값/추론 규칙

**실제 사용**: ✅ 파싱 실패 시 기본값 제공에 사용됨

**주요 함수**:
- `get_default_metric() -> str`: 기본 집계 함수 반환 (보통 "avg")
- `get_default_column() -> Optional[str]`: 기본 컬럼 반환 (보통 "pressact")

---

### `schema/load_schema.py`
**역할**: YAML 스키마 로더

**실제 사용**: ✅ 다른 모듈에서 스키마 로드에 사용됨

**주요 함수**:
- `load_columns_yaml(path: Path) -> Schema`: columns.yaml 로드

---

## 🔄 데이터 흐름 예시

### 입력: "VG11 압력 평균"

**Step 1: 정규화** (`rules/normalization.py`)
```
"VG11 압력 평균"
↓
소문자 변환: "vg11 압력 평균"
동의어 치환: "vg11 pressact avg"
패턴 정규화: "vg11 pressact avg"
→ NormalizedText(raw="VG11 압력 평균", text="vg11 pressact avg")
```

**Step 2: 컬럼 추출** (`nl_parse_v2.py`의 `_pick_col()`)
```
"vg11 pressact avg"
↓
도메인 메타데이터에서 매칭:
- "vg11" → 키 직접 매칭 (가중치 3.0)
- "pressact" → 동의어 매칭 (가중치 2.5)
→ matched_cols = [(3.0, "vg11"), (2.5, "pressact")]
→ column="vg11" (가중치 높은 것 선택)
```

**Step 3: 모호성 해결** (`rules/resolution.py`)
```
column="vg11", tokens=["vg11", "pressact", "avg"]
↓
pressure_resolution.yaml 규칙 확인:
- "vg11" 토큰 발견 → prefer_column="vg11"
- suppress_generic_pressure_token=true → pressact 제거
→ 최종: "vg11"
```

**Step 4: 최종 결과**
```python
Parsed(
    col="vg11",
    agg="avg",
    group_by=None,
    ...
)
```

---

## 🔧 확장 방법

### 새 센서 추가

1. **`schema/columns.yaml`에 컬럼 정의 추가**:
```yaml
vg14:
  domain_name: "진공 게이지 14 압력"
  physical_type: "pressure"
  unit: "mTorr"
  csv_columns: ["vg14"]
  aliases: ["vg14", "게이지14", "진공게이지14"]
  decimals: 2  # 선택사항 (기본값 3 오버라이드)
```

2. **`synonyms/columns.yaml`에 동의어 추가**:
```yaml
vg14:
  - vg14
  - 게이지14
  - 진공게이지14
```

3. **모호성 해결 규칙 추가 (필요시)**:
`rules/pressure_resolution.yaml`에 추가:
```yaml
resolution:
  context_overrides:
    - if_any_tokens: ["vg14", "게이지14"]
      prefer_column: "vg14"
      suppress_generic_pressure_token: true
```

4. **코드 수정 없음!** 자동으로 인식됩니다. ✅

---

### 새 유량 채널 추가

1. **`schema/columns.yaml`에 추가**:
```yaml
mfcmon_n2_3:
  domain_name: "질소 유량 (N2-3)"
  physical_type: "flow"
  unit: "sccm"
  csv_columns: ["mfcmon_n2_3"]
  aliases: ["n2-3 유량", "mfc n2-3", "N2-3"]
```

2. **`synonyms/columns.yaml`에 동의어 추가**:
```yaml
mfcmon_n2_3:
  - n2-3 유량
  - mfc n2-3
  - N2-3
```

---

### 새 지표 추가

1. **`schema/metrics.yaml`에 추가**:
```yaml
overshoot:
  label: "오버슈트"
  sql: "custom"
  description: "목표값 대비 초과량"
```

2. **`synonyms/metrics.yaml`에 동의어 추가**:
```yaml
overshoot:
  - 오버슈트
  - overshoot
  - 초과
```

3. **`src/process_metrics.py`에 SQL 빌더 추가** (필요시)

---

### 새 그룹핑 추가

1. **`schema/groups.yaml`에 추가**:
```yaml
week:
  label: "주별"
  description: "주 단위 그룹핑"
  sql_expr: "DATE_TRUNC('week', timestamp)"
  type: "temporal"
```

2. **`synonyms/groups.yaml`에 동의어 추가**:
```yaml
week:
  - 주별
  - week별
  - 주
```

---

## 📊 파일별 실제 사용 위치

| 파일 | 사용 위치 | 용도 |
|------|----------|------|
| `schema/columns.yaml` | `nl_parse_v2.py`, `sql_builder.py`, `app.py` | 컬럼 메타데이터, 포맷팅 규칙 |
| `schema/metrics.yaml` | `nl_parse_v2.py` | 집계 함수 인식 |
| `schema/groups.yaml` | `nl_parse_v2.py`, `sql_builder.py` | 그룹핑 인식 |
| `synonyms/columns.yaml` | `rules/normalization.py` | 동의어 치환 |
| `synonyms/metrics.yaml` | `rules/normalization.py` | 지표 동의어 치환 |
| `synonyms/groups.yaml` | `rules/normalization.py` | 그룹핑 동의어 치환 |
| `synonyms/patterns.yaml` | `rules/normalization.py` | 패턴 정규화 |
| `rules/normalization.py` | `app.py`, `nl_parse_v2.py` | 질문 정규화 |
| `rules/validation.py` | `nl_parse_v2.py`, `sql_builder.py` | 유효성 검증 |
| `rules/resolution.py` | `nl_parse_v2.py` | 모호성 해결 |
| `rules/pressure_resolution.yaml` | `rules/resolution.py` | 압력 모호성 해결 규칙 |

---

## ✅ 장점

1. **DB 독립적**: DB 컬럼명이 바뀌어도 `csv_columns`만 수정
2. **확장 용이**: 새 컬럼 추가 시 YAML만 수정
3. **모호성 해결**: resolution 규칙으로 복잡도 흡수
4. **유지보수 용이**: 하드코딩 없이 설정 파일로 관리
5. **테스트 용이**: 메타데이터 기반으로 테스트 작성 가능
6. **비개발자 친화적**: YAML 파일 수정만으로 도메인 지식 업데이트

---

## 📚 참고 문서

- `../docs/ARCHITECTURE.md`: 전체 아키텍처 문서
- `schema/parsed_schema.json`: Parsed 객체 JSON 스키마
- `../tests/`: 파서 테스트 케이스
