# Domain 메타데이터 디렉토리

이 디렉토리는 **프로젝트의 심장부**입니다. 모든 도메인 지식이 YAML 파일과 Python 규칙으로 관리됩니다.

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

## 디렉토리 구조

```
domain/
├── schema/                    # 도메인 스키마 정의
│   ├── columns.yaml           # 컬럼 메타데이터 (도메인 키 ↔ CSV 컬럼명)
│   ├── metrics.yaml           # 집계 함수/지표 정의
│   ├── groups.yaml            # 그룹핑 정의
│   ├── units.yaml             # 단위 정의
│   └── load_schema.py         # YAML 스키마 로더
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

## 주요 파일 설명

### `schema/columns.yaml`

**도메인 키 ↔ CSV 실제 컬럼명 매핑**

```yaml
columns:
  pressact:
    domain_name: "챔버 압력"
    physical_type: "pressure"
    unit: "mTorr"
    csv_columns: ["PressAct"]  # 실제 DB 컬럼명
    aliases: ["챔버 압력", "압력", "진공", "pressure"]
```

**핵심**: 코드에서는 `pressact` 같은 도메인 키만 사용하고, 실제 SQL에서는 `csv_columns`의 `PressAct`를 사용한다.

### `rules/pressure_resolution.yaml`

**모호성 해결 규칙**

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

### `rules/normalization.py`

**질문 정규화 파이프라인**

1. 소문자 변환
2. 동의어 치환 (`columns.yaml`의 `aliases` 사용)
3. 패턴 정규화 (top5, step=STANDBY 등)

### `rules/resolution.py`

**모호성 해결 로직**

`pressure_resolution.yaml` 규칙을 적용하여 최종 컬럼 결정.

## 확장 방법

### 새 센서 추가

1. **`schema/columns.yaml`에 컬럼 정의 추가**:
```yaml
vg14:
  domain_name: "진공 게이지 14 압력"
  physical_type: "pressure"
  unit: "mTorr"
  csv_columns: ["VG14"]
  aliases: ["vg14", "게이지14", "진공게이지14"]
```

2. **모호성 해결 규칙 추가 (필요시)**:
`rules/pressure_resolution.yaml`에 추가:
```yaml
resolution:
  context_overrides:
    - if_any_tokens: ["vg14", "게이지14"]
      prefer_column: "vg14"
      suppress_generic_pressure_token: true
```

3. **코드 변경 없음!** 자동으로 인식됩니다. ✅

### 새 유량 채널 추가

1. **`schema/columns.yaml`에 추가**:
```yaml
mfcmon_n2_3:
  domain_name: "질소 유량 (N2-3)"
  physical_type: "flow"
  unit: "sccm"
  csv_columns: ["MFCMon_N2-3"]
  aliases: ["n2-3 유량", "mfc n2-3", "N2-3"]
```

2. **모호성 해결 규칙 추가 (필요시)**:
```yaml
resolution:
  flow_channel_rules:
    - if_any_tokens: ["n2-3"]
      prefer_column: "mfcmon_n2_3"
```

## 데이터 흐름 예시

### 입력: "VG11 압력 평균"

1. **정규화** (`normalization.py`):
   ```
   "VG11 압력 평균"
   → "vg11 pressact avg"
   ```

2. **컬럼 추출** (`nl_parse_v2.py`):
   ```
   "vg11 pressact avg"
   → column="vg11" (키 직접 매칭)
   ```

3. **모호성 해결** (`resolution.py`):
   ```
   column="vg11", tokens=["vg11", "pressact", "avg"]
   → "vg11" (구체적 센서 우선, pressact 유지)
   ```

4. **최종 결과**:
   ```python
   Parsed(column="vg11", metric="avg", ...)
   ```

## 장점

1. **DB 독립적**: DB 컬럼명이 바뀌어도 `csv_columns`만 수정
2. **확장 용이**: 새 컬럼 추가 시 YAML만 수정
3. **모호성 해결**: resolution 규칙으로 복잡도 흡수
4. **유지보수 용이**: 하드코딩 없이 설정 파일로 관리
5. **테스트 용이**: 메타데이터 기반으로 테스트 작성 가능

## 참고

- `ARCHITECTURE.md`: 전체 아키텍처 문서
- `schema/parsed_schema.json`: Parsed 객체 JSON 스키마
- `tests/`: 파서 테스트 케이스
