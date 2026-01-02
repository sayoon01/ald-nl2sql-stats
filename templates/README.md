# templates/ 디렉토리 설명

이 디렉토리는 웹 UI를 위한 HTML 템플릿 파일들을 포함합니다. Jinja2 템플릿 엔진을 사용하여 동적 HTML을 생성합니다.

## 📋 파일 목록

### `index.html`
**역할**: 메인 UI 페이지 (질문 입력, 결과 테이블, 차트, 요약 표시)

**실제 사용**: ✅ `GET /view` 엔드포인트에서 렌더링됨

**주요 섹션**:

#### 1. 질문 입력 영역
- 텍스트 입력 필드 (`<input type="text" name="q">`)
- "실행" 버튼
- 질문 추천 목록 (자동완성)

**JavaScript 기능**:
- 입력 시 실시간 추천 질문 표시 (디바운싱 300ms)
- `/api/suggestions?q=...` 또는 `/api/popular` 호출
- 추천 질문 클릭 시 자동 실행

#### 2. 결과 요약
- 자연어 형식의 요약 문장
- 해석 레이어(`interpreter.py`)에서 생성된 요약 표시
- 예: `"챔버 압력 평균은 358.354 Torr이며, 정상 범위(0.3~0.6 Torr) 밖입니다. (표본 2,429,600개, 표준편차 366.516)"`

**표시 조건**:
```jinja2
{% if summary %}
  <div class="summary">{{ summary }}</div>
{% endif %}
```

#### 3. 상세 정보 (접을 수 있음)
- 분석 파라미터 (Parsed 객체)
- 실행된 SQL 쿼리
- 정규화된 질문
- `<details>` 태그로 접기/펼치기 가능

**표시 내용**:
- `question_raw`: 원본 질문
- `question_normalized`: 정규화된 질문
- `parsed`: Parsed 객체 (dict 형태)
- `sql`: 실행된 SQL 쿼리

#### 4. 결과 테이블
- 동적 테이블 생성 (Jinja2 반복문)
- 컬럼별 색상 구분:
  - 파란색: `value`, `diff`
  - 초록색: `n`, `outlier_count`
  - 노란색: `std`, `min_val`, `max_val`
- 클라이언트 측 필터링/정렬 기능:
  - `step_name` 검색 (JavaScript)
  - 값/이름 정렬 (JavaScript)
- "전체 보기" 버튼:
  - 스텝별 쿼리 시 기본 Top 10만 표시
  - 클릭 시 전체 데이터 표시 (`show_all=1`)

**테이블 구조**:
```jinja2
<table>
  <thead>
    <tr>
      {% for col in rows[0].keys() %}
        <th>{{ col }}</th>
      {% endfor %}
    </tr>
  </thead>
  <tbody id="tableBody">
    {% for row in rows %}
      <tr data-step-name="{{ row.step_name|default('') }}" 
          data-value="{{ row.value|default(0) }}">
        {% for key, value in row.items() %}
          <td>{{ value }}</td>
        {% endfor %}
      </tr>
    {% endfor %}
  </tbody>
</table>
```

#### 5. 차트 이미지
- PNG 이미지로 차트 표시
- `analysis_type`에 따라 자동 생성된 차트
- Plotly 인터랙티브 차트 (향후 확장 가능)

**차트 타입**:
- `bignum`: 단일 값 큰 숫자 표시
- `bar`: 막대 차트 (Plotly)
- `line_img`: 시계열 라인 차트 (Matplotlib PNG)

**표시 조건**:
```jinja2
{% if meta.chart == "line_img" %}
  <img src="/api/plot?q={{ q|urlencode }}" />
{% elif meta.chart == "bar" %}
  <div id="plotly-chart"></div>
  <script>
    Plotly.newPlot('plotly-chart', {{ rows_json|tojson|safe }}, ...);
  </script>
{% endif %}
```

**주요 기능**:

- **질문 자동완성**: 입력 시 실시간 추천 질문 표시 (디바운싱 300ms)
- **클라이언트 측 필터링**: JavaScript로 테이블 필터링/정렬
- **동적 레이아웃**: 데이터 유무에 따라 섹션 표시/숨김
- **반응형 디자인**: 다양한 화면 크기 지원
- **다크 테마**: 어두운 배경색 적용

**Jinja2 변수**:
- `request`: FastAPI Request 객체
- `q`: 질문 문자열
- `question_raw`: 원본 질문
- `question_normalized`: 정규화된 질문
- `parsed`: Parsed 객체 (dict)
- `sql`: 실행된 SQL 쿼리
- `rows`: 포맷팅된 결과 행들 (list of dict, 최대 200행)
- `rows_raw`: 원본 데이터 (필터링/정렬용)
- `summary`: 자연어 요약 문장 (interpret() 결과)
- `suggestions`: 질문 추천 목록
- `meta`: 시각화 힌트 객체
  - `chart`: 차트 타입 ("bignum", "bar", "line_img")
  - `x`, `y`: x/y축 컬럼명
  - `title`: 차트 제목
  - `unit`: 단위
  - `img_endpoint`: 시계열 이미지 URL (line_img인 경우)
- `show_all_button`: "전체 보기" 버튼 표시 여부
- `error`: 에러 메시지 (있는 경우)

**JavaScript 기능 상세**:

1. **질문 자동완성**:
```javascript
function showSuggestions(query) {
  if (query.length < 2) {
    // 인기 질문 표시
    fetch('/api/popular')
      .then(r => r.json())
      .then(data => updateSuggestions(data.questions));
  } else {
    // 검색어 기반 추천
    fetch(`/api/suggestions?q=${encodeURIComponent(query)}`)
      .then(r => r.json())
      .then(data => updateSuggestions(data.suggestions));
  }
}
```

2. **필터링 및 정렬**:
```javascript
function filterAndSort() {
  const filterText = filterInput.value.toLowerCase();
  const rows = Array.from(tableBody.querySelectorAll('tr'));
  
  // 필터링
  rows.forEach(row => {
    const stepName = row.dataset.stepName || '';
    row.style.display = stepName.includes(filterText) ? '' : 'none';
  });
  
  // 정렬
  visibleRows.sort((a, b) => {
    // 값/이름 기준 정렬
  });
}
```

3. **차트 렌더링**:
- Plotly bar: `meta.chart === "bar"` → Plotly 차트 생성
- Matplotlib line_img: `meta.chart === "line_img"` → `<img src="/api/plot?...">`
- Bignum: `meta.chart === "bignum"` → 큰 숫자 표시

**데이터 속성**:
- `data-step-name`: 필터링용 step_name 값
- `data-value`: 정렬용 숫자 값

---

### `plot.html`
**역할**: 차트 전용 페이지 (차트 이미지만 표시)

**실제 사용**: ✅ `GET /plot_page` 엔드포인트에서 렌더링됨

**주요 기능**:
- 차트 이미지만 단독으로 표시
- 다른 페이지에서 iframe으로 임베드 가능
- 간단한 레이아웃

**Jinja2 변수**:
- `request`: FastAPI Request 객체
- `q`: 질문 문자열

**구조**:
```html
<!doctype html>
<html>
  <head>
    <title>Plot</title>
  </head>
  <body>
    <img src="/plot?q={{ q|urlencode }}" />
  </body>
</html>
```

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
    ├── 차트 이미지 → /plot?q=질문 또는 Plotly
    └── 요약 → summary 문자열 표시
```

**상세 흐름**:
1. 사용자가 `/view?q=질문` 접속
2. `app.py`의 `view()` 함수 실행
3. 질문 파싱, SQL 생성, 쿼리 실행
4. 결과 포맷팅 및 요약 생성
5. Jinja2 템플릿 렌더링
6. HTML 응답 반환

---

## 📝 템플릿 구조 예시

### 조건부 렌더링

```jinja2
{% if rows %}
    <!-- 테이블 표시 -->
    <table>...</table>
{% else %}
    <!-- "결과가 없습니다" 메시지 -->
    <div class="no-results">결과가 없습니다.</div>
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

### JSON 데이터 전달

```jinja2
<script>
  const data = {{ rows_json|tojson|safe }};
  Plotly.newPlot('chart', data, ...);
</script>
```

---

## 🎨 스타일 및 스크립트

### CSS 스타일
- 인라인 스타일 사용
- 컬럼별 색상 구분 (값, 개수, 표준편차)
- 다크 테마 적용 (#1a1a2e 배경)
- 반응형 디자인

### JavaScript 기능

**1. 질문 자동완성 및 추천** (`index.html`):
- 입력 시 실시간 추천 (디바운싱 300ms)
- `/api/suggestions?q=...` 또는 `/api/popular` 호출
- 추천 질문 목록 업데이트

**2. 필터링 및 정렬** (`index.html`):
- `step_name` 검색
- 값/이름 정렬
- 클라이언트 측에서 즉시 반영

**3. 차트 렌더링**:
- Plotly bar: `meta.chart === "bar"` → Plotly 차트 생성
- Matplotlib line_img: `meta.chart === "line_img"` → `<img src="/api/plot?...">`
- Bignum: `meta.chart === "bignum"` → 큰 숫자 표시

---

## 🎯 개선 사항 (향후)

- [ ] 더 나은 반응형 디자인
- [ ] 차트 인터랙티브 기능 (hover, zoom)
- [ ] 테이블 페이징
- [ ] 다크/라이트 테마 토글
- [ ] 결과 내보내기 버튼 (CSV, PDF)
- [ ] 히스토리 기능 (최근 질문 목록)
- [ ] 즐겨찾기 기능

---

## 📊 실제 사용 예시

### 질문 입력
```
사용자 입력: "챔버 압력 평균"
    ↓
GET /view?q=챔버%20압력%20평균
    ↓
app.py에서 처리
    ↓
index.html 렌더링
```

### 결과 표시
```jinja2
{% if rows %}
  <!-- 테이블 표시 -->
  <table>
    {% for row in rows %}
      <tr>
        <td>{{ row.value }}</td>
        <td>{{ row.n }}</td>
      </tr>
    {% endfor %}
  </table>
  
  <!-- 요약 표시 -->
  <div class="summary">{{ summary }}</div>
  
  <!-- 차트 표시 -->
  {% if meta.chart == "bignum" %}
    <div class="bignum">{{ rows[0].value }}</div>
  {% endif %}
{% endif %}
```

---

## 🔗 관련 파일

- `src/app.py`: 템플릿 렌더링 로직
- `src/chart_templates.py`: 차트 생성 로직
- `src/plot_generator.py`: 시계열 플롯 생성
