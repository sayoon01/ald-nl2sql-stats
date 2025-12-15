from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import Response, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import duckdb
import matplotlib
matplotlib.use('Agg')  # 서버 환경에서 필요한 백엔드 설정
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import io
import json
from datetime import datetime

# 한글 폰트 설정 (macOS에서 사용 가능한 폰트 우선 사용)
plt.rcParams['font.family'] = 'Apple SD Gothic Neo'  # macOS 기본 한글 폰트
plt.rcParams['axes.unicode_minus'] = False  # 음수 기호 깨짐 방지
from src.nl_parse import parse_question
from src.sql_builder import build_sql

DB = Path.home() / "ald_app" / "data_out" / "ald.duckdb"

app = FastAPI(title="ALD NL→SQL Stats API")
templates = Jinja2Templates(directory=str(Path.home() / "ald_app" / "templates"))

class QueryIn(BaseModel):
    question: str

@app.get("/")
def root():
    return {"ok": True, "hint": "Go to /docs or /view"}

def make_summary(parsed: dict, rows: list) -> str:
    agg_kr = {"avg": "평균", "min": "최소", "max": "최대", "count": "개수"}.get(parsed["agg"], parsed["agg"])
    col = parsed.get("col") or "*"
    scope = []
    if parsed.get("trace_id"):
        scope.append(parsed["trace_id"])
    if parsed.get("step_name"):
        scope.append(f"step={parsed['step_name']}")
    scope_txt = (", ".join(scope) + " 기준 ") if scope else ""

    if not rows:
        return f"결과가 없습니다. ({scope_txt}{col} {agg_kr})"

    if parsed.get("group_by"):
        top = rows[0]
        key = parsed["group_by"]
        return f"{scope_txt}{col} {agg_kr} {key} 기준 Top {len(rows)}. 1위={top.get(key)} ({top.get('value')})."

    r0 = rows[0]
    if "value" in r0:
        return f"{scope_txt}{col} {agg_kr}={r0['value']}"
    if "n" in r0:
        return f"{scope_txt}{col} {agg_kr}={r0['n']}"
    return "요약 생성 실패"

@app.post("/query")
def query(q: QueryIn):
    try:
        parsed_obj = parse_question(q.question)
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "hint_examples": [
                "standard_trace_001 pressact 평균",
                "standard_trace_001 스텝별 pressact 평균",
                "공정별 pressact 평균 top5",
                "standard_trace_001 step=STANDBY pressact 최대",
            ],
        }

    sql, params = build_sql(parsed_obj)
    con = duckdb.connect(str(DB))
    try:
        df = con.execute(sql, params).df()
    finally:
        con.close()

    rows = df.to_dict(orient="records")
    parsed = parsed_obj.__dict__
    summary = make_summary(parsed, rows)

    return {
        "ok": True,
        "question": q.question,
        "parsed": parsed,
        "sql": sql.strip(),
        "rows": rows,
        "summary": summary,
    }

# ✅ HTML 테이블 UI
@app.get("/view", response_class=HTMLResponse)
def view(request: Request, q: str | None = None):
    if not q:
        return templates.TemplateResponse("index.html", {"request": request, "q": ""})

    try:
        parsed_obj = parse_question(q)
        sql, params = build_sql(parsed_obj)
        con = duckdb.connect(str(DB))
        try:
            df = con.execute(sql, params).df()
            rows = df.to_dict(orient="records")
        finally:
            con.close()
        parsed = parsed_obj.__dict__
        summary = make_summary(parsed, rows)
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "q": q, "parsed": parsed, "sql": sql.strip(), "rows": rows, "summary": summary},
        )
    except Exception as e:
        return templates.TemplateResponse("index.html", {"request": request, "q": q, "error": str(e)})

# ✅ PNG plot (브라우저에서 바로 열리는 엔드포인트)
@app.get("/plot")
def plot(q: str):
    try:
        parsed_obj = parse_question(q)
        sql, params = build_sql(parsed_obj)

        con = duckdb.connect(str(DB))
        try:
            df = con.execute(sql, params).df()
        finally:
            con.close()

        if df.empty:
            return Response(content=b"No data", media_type="text/plain")

        # 단일 값이면 간단 텍스트로
        if len(df.columns) == 1 and df.columns[0] in ("value", "n"):
            txt = df.to_string(index=False)
            return Response(content=txt.encode("utf-8"), media_type="text/plain; charset=utf-8")

        # 그룹 결과: x축(첫번째 컬럼), y축(value or n)
        x_col = df.columns[0]
        y_col = "value" if "value" in df.columns else ("n" if "n" in df.columns else df.columns[-1])

        # 너무 길면 상위 100개만 (보기 좋게)
        if len(df) > 100:
            df = df.head(100)

        # 한글 레이블 매핑
        agg_kr = {"avg": "평균", "min": "최소", "max": "최대", "count": "개수"}.get(parsed_obj.agg, parsed_obj.agg)
        col_kr = parsed_obj.col or "전체"
        x_col_kr = "공정 ID" if x_col == "trace_id" else ("단계명" if x_col == "step_name" else ("일자" if x_col == "date" else ("시간" if x_col == "hour" else x_col)))
        y_col_kr = f"{col_kr} {agg_kr}" if parsed_obj.col else agg_kr

        # 차트 타입에 따라 다르게 그리기
        chart_type = parsed_obj.chart_type or "bar"
        
        fig, ax = plt.subplots(figsize=(14, 7))
        fig.patch.set_facecolor('white')
        
        # 라인 차트 (시계열 데이터)
        if chart_type == "line" or x_col in ("date", "hour"):
            x_vals = df[x_col].tolist()
            y_vals = df[y_col].astype(float).tolist()
            
            # 날짜/시간이면 정렬
            if x_col == "date":
                df = df.sort_values("date")
                x_vals = df[x_col].tolist()
                y_vals = df[y_col].astype(float).tolist()
            
            ax.plot(range(len(x_vals)), y_vals, marker='o', linewidth=2, markersize=6, color='#667eea')
            ax.set_xticks(range(len(x_vals)))
            ax.set_xticklabels([str(x) for x in x_vals], rotation=45, ha='right')
            
            # 최대값 표시
            max_idx = y_vals.index(max(y_vals))
            ax.plot(max_idx, y_vals[max_idx], 'ro', markersize=12)
            ax.annotate(f'최대: {y_vals[max_idx]:.2f}', 
                       xy=(max_idx, y_vals[max_idx]),
                       xytext=(max_idx, y_vals[max_idx] + (max(y_vals) - min(y_vals)) * 0.1),
                       fontsize=10, fontweight='bold',
                       bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7),
                       ha='center')
        
        # 바 차트 (기본)
        else:
            bars = ax.bar(
                range(len(df)), 
                df[y_col].astype(float).tolist(),
                color='#667eea',
                edgecolor='white',
                linewidth=1.5
            )
            
            # 최대값 표시
            max_idx = df[y_col].idxmax()
            max_pos = df.index.get_loc(max_idx)
            max_val = df[y_col].max()
            bars[max_pos].set_color('#ff6b6b')
            
            ax.set_xticks(range(len(df)))
            ax.set_xticklabels([str(x) for x in df[x_col].astype(str).tolist()], rotation=45, ha='right')
            
            # 최대값 표시 텍스트
            ax.text(max_pos, max_val, f'최대: {max_val:.2f}', 
                    ha='center', va='bottom', fontsize=10, fontweight='bold',
                    bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7))
        
        ax.set_xlabel(x_col_kr, fontsize=12, fontweight='bold', labelpad=10)
        ax.set_ylabel(y_col_kr, fontsize=12, fontweight='bold', labelpad=10)
        
        # 제목 생성 (여러 줄로 나누기)
        title_lines = []
        title_lines.append(f"{y_col_kr} ({x_col_kr}별)")
        
        filter_parts = []
        if parsed_obj.trace_id:
            filter_parts.append(f"공정: {parsed_obj.trace_id}")
        if len(parsed_obj.trace_ids) > 1:
            filter_parts.append(f"공정: {', '.join(parsed_obj.trace_ids)}")
        if parsed_obj.step_name:
            filter_parts.append(f"단계: {parsed_obj.step_name}")
        if len(parsed_obj.step_names) > 1:
            filter_parts.append(f"단계: {', '.join(parsed_obj.step_names)}")
        if parsed_obj.date_start:
            filter_parts.append(f"시작: {parsed_obj.date_start}")
        if parsed_obj.date_end:
            filter_parts.append(f"종료: {parsed_obj.date_end}")
        
        if filter_parts:
            title_lines.append(" | ".join(filter_parts))
        
        title_text = "\n".join(title_lines)
        ax.set_title(title_text, fontsize=13, fontweight='bold', pad=15, loc='center', wrap=True)
        
        ax.grid(True, alpha=0.3, axis='y', linestyle='--')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        plt.tight_layout(pad=3.0)

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches='tight', facecolor='white', pad_inches=0.3)
        plt.close(fig)
        buf.seek(0)
        return Response(content=buf.read(), media_type="image/png")
    except Exception as e:
        # 에러가 발생하면 에러 메시지를 이미지로 반환
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.text(0.5, 0.5, f'Error: {str(e)}', 
                ha='center', va='center', fontsize=14, color='red',
                transform=ax.transAxes)
        ax.axis('off')
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return Response(content=buf.read(), media_type="image/png")

# ✅ plot을 페이지로 보기(이미지 태그로 렌더링)
@app.get("/plot_page", response_class=HTMLResponse)
def plot_page(request: Request, q: str):
    return templates.TemplateResponse("plot.html", {"request": request, "q": q})

# ✅ 데이터 탐색: 컬럼 목록
@app.get("/api/columns")
def get_columns():
    con = duckdb.connect(str(DB))
    df = con.execute("DESCRIBE traces").df()
    # slugify된 컬럼명만 (실제 사용 가능한 컬럼들)
    cols = [row[0] for row in df.values if not row[0].startswith('_') and row[0] != 'No.']
    return {"columns": cols}

# ✅ 데이터 탐색: 공정 ID 목록
@app.get("/api/traces")
def get_traces():
    con = duckdb.connect(str(DB))
    df = con.execute("SELECT DISTINCT trace_id FROM traces ORDER BY trace_id").df()
    return {"traces": df['trace_id'].tolist()}

# ✅ 데이터 탐색: 단계명 목록
@app.get("/api/steps")
def get_steps():
    con = duckdb.connect(str(DB))
    df = con.execute("SELECT DISTINCT step_name FROM traces ORDER BY step_name").df()
    return {"steps": df['step_name'].tolist()}

# ✅ 데이터 탐색: 데이터 범위
@app.get("/api/range")
def get_data_range():
    con = duckdb.connect(str(DB))
    min_date = con.execute("SELECT MIN(DATE(timestamp)) as min_date FROM traces").fetchone()[0]
    max_date = con.execute("SELECT MAX(DATE(timestamp)) as max_date FROM traces").fetchone()[0]
    total_rows = con.execute("SELECT COUNT(*) as cnt FROM traces").fetchone()[0]
    return {
        "min_date": str(min_date) if min_date else None,
        "max_date": str(max_date) if max_date else None,
        "total_rows": total_rows
    }

# ✅ CSV 다운로드
@app.get("/api/csv")
def download_csv(q: str):
    try:
        parsed_obj = parse_question(q)
        sql, params = build_sql(parsed_obj)
        con = duckdb.connect(str(DB))
        df = con.execute(sql, params).df()
        
        csv_str = df.to_csv(index=False)
        return Response(content=csv_str, media_type="text/csv", 
                       headers={"Content-Disposition": f"attachment; filename=query_result.csv"})
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ✅ 히스토리 저장/조회 (간단한 JSON 파일 기반)
HISTORY_FILE = Path.home() / "ald_app" / "data" / "history.json"

@app.post("/api/history")
def save_history(q: QueryIn):
    try:
        if not HISTORY_FILE.parent.exists():
            HISTORY_FILE.parent.mkdir(parents=True)
        
        history = []
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
        
        # 중복 제거 및 최근 것만 유지 (최대 100개)
        history = [h for h in history if h['question'] != q.question]
        history.insert(0, {"question": q.question, "timestamp": datetime.now().isoformat()})
        history = history[:100]
        
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/api/history")
def get_history():
    try:
        if not HISTORY_FILE.exists():
            return {"history": []}
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            history = json.load(f)
        return {"history": history[:20]}  # 최근 20개만
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ✅ 즐겨찾기 저장/조회
FAVORITES_FILE = Path.home() / "ald_app" / "data" / "favorites.json"

@app.post("/api/favorites")
def save_favorite(q: QueryIn):
    try:
        if not FAVORITES_FILE.parent.exists():
            FAVORITES_FILE.parent.mkdir(parents=True)
        
        favorites = []
        if FAVORITES_FILE.exists():
            with open(FAVORITES_FILE, 'r', encoding='utf-8') as f:
                favorites = json.load(f)
        
        if q.question not in favorites:
            favorites.append(q.question)
        
        with open(FAVORITES_FILE, 'w', encoding='utf-8') as f:
            json.dump(favorites, f, ensure_ascii=False, indent=2)
        
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/api/favorites")
def get_favorites():
    try:
        if not FAVORITES_FILE.exists():
            return {"favorites": []}
        with open(FAVORITES_FILE, 'r', encoding='utf-8') as f:
            favorites = json.load(f)
        return {"favorites": favorites}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.delete("/api/favorites")
def delete_favorite(q: QueryIn):
    try:
        if not FAVORITES_FILE.exists():
            return {"ok": True}
        
        with open(FAVORITES_FILE, 'r', encoding='utf-8') as f:
            favorites = json.load(f)
        
        favorites = [f for f in favorites if f != q.question]
        
        with open(FAVORITES_FILE, 'w', encoding='utf-8') as f:
            json.dump(favorites, f, ensure_ascii=False, indent=2)
        
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
