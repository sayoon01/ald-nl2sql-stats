# templates/ 디렉토리 설명

이 디렉토리는 웹 UI를 위한 HTML 템플릿 파일들을 포함합니다. Jinja2 템플릿 엔진을 사용하여 동적 HTML을 생성합니다.

## 📋 파일 목록

### `index.html`
**역할**: 메인 UI 페이지 (질문 입력, 결과 테이블, 차트, 요약 표시)

**주요 섹션**:

1. **질문 입력 영역**
   - 텍스트 입력 필드
   - "실행" 버튼
   - 예시 질문 버튼들

2. **결과 요약**
   - 자연어 형식의 요약 문장
   - 해석 레이어(`interpreter.py`)에서 생성된 요약 표시
   - 예: `"챔버 압력 평균은 358.354 Torr이며, 정상 범위(0.3~0.6 Torr) 밖입니다. (표본 2,429,600개, 표준편차 366.516)"`

3. **상세 정보 (접을 수 있음)**
   - 분석 파라미터 (Parsed 객체)
   - 실행된 SQL 쿼리
   - `<details>` 태그로 접기/펼치기 가능

4. **결과 테이블**
   - 동적 테이블 생성 (Jinja2 반복문)
   - 컬럼별 색상 구분:
     - 파란색: `value`, `diff`
     - 초록색: `n`, `outlier_count`
     - 노란색: `std`, `min_val`, `max_val`
   - 클라이언트 측 필터링/정렬 기능:
     - `step_name` 검색
     - 값/이름 정렬
   - "전체 보기" 버튼:
     - 스텝별 쿼리 시 기본 Top 10만 표시
     - 클릭 시 전체 데이터 표시

5. **차트 이미지**
   - PNG 이미지로 차트 표시
   - `analysis_type`에 따라 자동 생성된 차트

**주요 기능**:

- **질문 자동완성**: 입력 시 실시간 추천 질문 표시 (디바운싱 300ms)
- **클라이언트 측 필터링**: JavaScript로 테이블 필터링/정렬
- **동적 레이아웃**: 데이터 유무에 따라 섹션 표시/숨김
- **반응형 디자인**: 다양한 화면 크기 지원

**Jinja2 변수**:
- `request`: FastAPI Request 객체
- `q`: 질문 문자열
- `parsed`: Parsed 객체 (dict)
- `sql`: 실행된 SQL 쿼리
- `rows`: 포맷팅된 결과 행들 (list of dict, 최대 200행)
- `summary`: 자연어 요약 문장 (interpret() 결과)
- `chart_url`: 차트 이미지 URL (`/plot?q=...`, 레거시)
- `meta`: 시각화 힌트 객체
  - `chart`: 차트 타입 ("bignum", "bar", "line_img")
  - `x`, `y`: x/y축 컬럼명
  - `title`: 차트 제목
  - `unit`: 단위
  - `img_endpoint`: 시계열 이미지 URL (line_img인 경우)
- `show_all_button`: "전체 보기" 버튼 표시 여부

---

### `plot.html`
**역할**: 차트 전용 페이지 (차트 이미지만 표시)

**주요 기능**:
- 차트 이미지만 단독으로 표시
- 다른 페이지에서 iframe으로 임베드 가능
- 간단한 레이아웃

**Jinja2 변수**:
- `request`: FastAPI Request 객체
- `chart_url`: 차트 이미지 URL

---

## 🎨 스타일 및 스크립트

### CSS 스타일
- 인라인 스타일 사용
- 컬럼별 색상 구분 (값, 개수, 표준편차)
- 다크 테마 적용

### JavaScript 기능

**1. 질문 자동완성 및 추천** (`index.html`):
```javascript
// 입력 시 실시간 추천
showSuggestions(query) {
  // /api/suggestions?q=... 또는 /api/popular 호출
  // 추천 질문 목록 업데이트
}
```

**2. 필터링 및 정렬** (`index.html`):
```javascript
// step_name 검색
function filterTable() { ... }

// 값/이름 정렬
function sortTable(column, type) { ... }
```

**3. 차트 렌더링**:
- Plotly bar: `meta.chart === "bar"` → Plotly 차트 생성
- Matplotlib line_img: `meta.chart === "line_img"` → `<img src="/api/plot?...">`
- Bignum: `meta.chart === "bignum"` → 큰 숫자 표시

**데이터 속성**:
- `data-step-name`: 필터링용 step_name 값
- `data-value`: 정렬용 숫자 값

---

## 🔄 데이터 흐름

```
app.py (view 함수)
    ↓
Jinja2 템플릿 렌더링
    ↓
index.html
    ├── 질문 입력 → /view?q=질문
    ├── 결과 테이블 → rows 데이터 표시
    ├── 차트 이미지 → /plot?q=질문
    └── 요약 → summary 문자열 표시
```

---

## 📝 템플릿 구조 예시

### 조건부 렌더링

```jinja2
{% if rows %}
    <!-- 테이블 표시 -->
{% else %}
    <!-- "결과가 없습니다" 메시지 -->
{% endif %}
```

### 반복문

```jinja2
{% for row in rows %}
    <tr>
        <td>{{ row.step_name }}</td>
        <td>{{ row.value }}</td>
        <td>{{ row.n }}</td>
    </tr>
{% endfor %}
```

### 동적 URL

```jinja2
<a href="/view?q={{ q }}&show_all=1">전체 보기</a>
<img src="/plot?q={{ q|urlencode }}">
```

---

## 🎯 개선 사항 (향후)

- [ ] 더 나은 반응형 디자인
- [ ] 차트 인터랙티브 기능 (hover, zoom)
- [ ] 테이블 페이징
- [ ] 다크/라이트 테마 토글
- [ ] 결과 내보내기 버튼 (CSV, PDF)

