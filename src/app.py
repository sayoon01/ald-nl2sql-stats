from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request  # type: ignore
from fastapi.responses import Response, HTMLResponse, RedirectResponse  # type: ignore
from fastapi.templating import Jinja2Templates  # type: ignore
import duckdb  # type: ignore
import pandas as pd  # type: ignore
import matplotlib.pyplot as plt  # type: ignore
import io
import json
from datetime import datetime
import yaml  # type: ignore

# 한글 폰트 설정 (모듈 import 시 1회 실행)
from src.utils.mpl_korean import setup_korean_font
setup_korean_font()
# 기존 파서와 새 파서 선택 가능
try:
    from src.nl_parse_v2 import parse_question  # 새 도메인 메타데이터 기반 파서
except ImportError:
    from src.nl_parse import parse_question  # 기존 파서 (fallback)

# 정규화 함수 import
from domain.rules.normalization import normalize
from src.sql_builder import build_sql
from src.process_metrics import (
    build_stable_avg_sql,
    build_overshoot_sql,
    build_dwell_time_sql,
    build_outlier_detection_sql,
    build_trace_compare_sql,
)
<<<<<<< HEAD
from src.chart_templates import get_chart_template, apply_chart_template
from src.payload_builder import build_payload
from src.plot_generator import plot_timeseries
from src.question_suggestions import get_suggestions, get_category_suggestions, get_popular_questions

# 프로젝트 루트 기준 경로
PROJECT_ROOT = Path(__file__).parent.parent
DB = PROJECT_ROOT / "data_out" / "ald.duckdb"

app = FastAPI(title="ALD NL→SQL Stats API")
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))

def validate_database():
    """데이터베이스 무결성 검증: trace_id가 비어있으면 에러"""
    if not DB.exists():
        raise FileNotFoundError(f"데이터베이스가 없습니다: {DB}\n해결책: python -m src.preprocess_duckdb 실행 필요")
    
    con = duckdb.connect(str(DB))
    try:
        null_count = con.execute("""
            SELECT COUNT(*) 
            FROM traces_dedup 
            WHERE trace_id IS NULL OR trace_id = ''
        """).fetchone()[0]
        
        if null_count > 0:
            total = con.execute("SELECT COUNT(*) FROM traces_dedup").fetchone()[0]
            raise ValueError(
                f"데이터 무결성 오류: trace_id가 비어있는 행이 {null_count:,}개 ({null_count/total*100:.1f}%) 있습니다.\n"
                f"해결책: python -m src.preprocess_duckdb 실행하여 데이터베이스를 재생성하세요."
            )
    finally:
        con.close()

# 앱 시작 시 검증
@app.on_event("startup")
async def startup_event():
    try:
        validate_database()
    except (FileNotFoundError, ValueError) as e:
        print(f"⚠️  경고: {e}")
        # 에러를 출력하지만 앱은 계속 실행 (개발 편의를 위해)

class QueryIn(BaseModel):
    question: str
=======
from src.charts.renderer import render_chart
from src.services.summary import make_summary
from src.utils.parsed import to_parsed_dict

# 프로젝트 루트 경로 설정
PROJECT_ROOT = Path(__file__).parent.parent
DB = PROJECT_ROOT / "data_out" / "ald.duckdb"
SCHEMA_PATH = PROJECT_ROOT / "domain" / "schema" / "columns.yaml"

app = FastAPI(title="ALD NL→SQL Stats API")
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))
>>>>>>> 378f42a2115c8718668a2287e9ab54018ecf432a

@app.get("/")
def root():
    return RedirectResponse(url="/view")

def load_schema(path: Path) -> dict:
    """columns.yaml 로드 (서버 시작 시 1회)"""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

SCHEMA = load_schema(SCHEMA_PATH)
COLUMNS_SCHEMA = SCHEMA.get("columns", {})
DEFAULTS = SCHEMA.get("defaults", {})
DECIMALS_BY_TYPE = (DEFAULTS.get("decimals_by_type") or {})
UNIT_LABEL = (DEFAULTS.get("unit_label") or {})

def get_format_spec(col_key: Optional[str]) -> tuple[int, str]:
    """
    col_key(canonical key: pressact, mfcmon_n2_1 등) -> (decimals, unit_label) 반환
    규칙:
      1) physical_type별 defaults.decimals_by_type 적용
      2) 컬럼에 decimals가 있으면 override
      3) unit은 defaults.unit_label로 화면 라벨 변환
    """
    if not col_key:
        return (2, "")
    meta = COLUMNS_SCHEMA.get(col_key) or {}
    physical_type = meta.get("physical_type")
    unit_code = meta.get("unit")

    decimals = int(DECIMALS_BY_TYPE.get(physical_type, 2))
    if "decimals" in meta and meta["decimals"] is not None:
        decimals = int(meta["decimals"])

    unit_label = UNIT_LABEL.get(unit_code, unit_code or "")
    return (decimals, unit_label)

def format_value(value: float, col: Optional[str] = None, agg: str = "avg") -> str:
    """값 포맷팅 (반올림 + 단위)"""
    if value is None or (isinstance(value, float) and (value != value)):  # NaN 체크
        return "N/A"
    
    # null_ratio는 퍼센트
    if agg == "null_ratio":
        return f"{value:.2f}%"

    decimals, unit_label = get_format_spec(col)
    formatted = f"{value:.{decimals}f}"
    return f"{formatted}{' ' + unit_label if unit_label else ''}"

def format_row(row: dict, parsed: dict) -> dict:
    """행 데이터 포맷팅 (n, std 등 추가 정보 포함)"""
    formatted = {}
    col = parsed.get("col") or "pressact"  # 기본값
    
    for key, value in row.items():
        if key == "value" and col:
            formatted[key] = format_value(value, col, parsed.get("agg", "avg"))
        elif key in ("std", "min_val", "max_val", "avg_diff", "min_diff", "max_diff") and col:
            formatted[key] = format_value(value, col, "avg")
        elif key in ("diff", "diff_signed"):
            # 비교 차이는 원본 컬럼 기준으로 포맷팅
            formatted[key] = format_value(value, col, "avg") if col else f"{value:.2f}"
        elif key == "n" or key == "outlier_count":
            formatted[key] = int(value) if value else 0
        elif key in ("trace1_avg", "trace2_avg") and col:
            formatted[key] = format_value(value, col, "avg")
        else:
            formatted[key] = value
    
    return formatted

<<<<<<< HEAD
def make_summary(parsed: dict, rows: list) -> str:
    """
    결과 요약 생성 (해석 레이어 사용)
    
    특수 케이스(trace 비교, 이상치 등)는 기존 로직 유지,
    일반 케이스는 interpreter 사용하여 사람이 읽기 쉬운 문장으로 변환
    """
    from src.interpreter import interpret
    from src.nl_parse import Parsed
    
    # 특수 케이스: trace 비교
    if parsed.get("is_trace_compare") and rows:
        top = rows[0]
        trace_ids = parsed.get("trace_ids", [])
        if len(trace_ids) >= 2:
            step_name = top.get('step_name', '')
            diff_val = top.get('diff', 0)
            trace1_avg = top.get('trace1_avg', 0)
            trace2_avg = top.get('trace2_avg', 0)
            
            diff_str = f"{diff_val:.1f}" if isinstance(diff_val, (int, float)) else str(diff_val)
            trace1_str = f"{trace_ids[0]}"
            trace2_str = f"{trace_ids[1]}"
            
            interpretation = ""
            if step_name == "STANDBY":
                interpretation = "이는 대기 단계에서 진공 안정화 또는 배기 제어 차이가 있었을 가능성을 시사합니다."
            elif step_name in ["B.FILL", "B.FILL4", "B.FILL5"]:
                interpretation = "이는 충진 단계에서 압력 제어 프로파일 차이가 있었을 가능성을 시사합니다."
            elif step_name in ["B.UP", "B.DOWN"]:
                interpretation = "이는 압력 변화 단계에서 제어 속도 또는 목표값 차이가 있었을 가능성을 시사합니다."
            else:
                interpretation = "이는 해당 단계에서 공정 조건 또는 제어 파라미터 차이가 있었을 가능성을 시사합니다."
            
            return f"{step_name} 단계에서 trace 간 pressact 차이가 가장 큽니다 (차이: ≈{diff_str} mTorr, {trace1_str}: {trace1_avg:.1f} mTorr, {trace2_str}: {trace2_avg:.1f} mTorr). {interpretation}"
    
    # 특수 케이스: 이상치 탐지
    if parsed.get("is_outlier"):
        if not rows:
            return "이상치가 발견되지 않았습니다. (z-score > 1.0 기준)"
        top = rows[0]
        return f"이상치 비율 Top {len(rows)}. 1위 trace={top.get('trace_id')}: {top.get('value')}% (표본 {top.get('n')}개, 이상치 {top.get('outlier_count')}개)"
    
    # 일반 케이스: 해석 레이어 사용
    if not rows:
        from src.interpreter import LABEL, AGG_LABEL
        name = LABEL.get(parsed.get("col"), parsed.get("col")) if parsed.get("col") else "값"
        agg_kor = AGG_LABEL.get(parsed.get("agg"), parsed.get("agg", "결과"))
        return f"{name} {agg_kor} 결과가 없습니다."
    
    # rows를 DataFrame으로 변환
    try:
        df = pd.DataFrame(rows)
        # Parsed 객체 생성 (dict에서)
        parsed_obj = Parsed(
            agg=parsed.get("agg", "avg"),
            col=parsed.get("col"),
            trace_id=parsed.get("trace_id"),
            trace_ids=parsed.get("trace_ids", []),
            step_name=parsed.get("step_name"),
            step_names=parsed.get("step_names", []),
            group_by=parsed.get("group_by"),
            limit=parsed.get("limit"),
            order=parsed.get("order"),
            date_start=parsed.get("date_start"),
            date_end=parsed.get("date_end"),
            chart_type=parsed.get("chart_type"),
            analysis_type=parsed.get("analysis_type", "ranking"),
            is_stable_avg=parsed.get("is_stable_avg", False),
            is_overshoot=parsed.get("is_overshoot", False),
            is_dwell_time=parsed.get("is_dwell_time", False),
            is_variability=parsed.get("is_variability", False),
            is_outlier=parsed.get("is_outlier", False),
            is_trace_compare=parsed.get("is_trace_compare", False),
        )
        return interpret(parsed_obj, df, topn=5)
    except Exception as e:
        # 폴백: 기존 방식 (디버깅용)
        agg_kr_map = {
            "avg": "평균", "min": "최소", "max": "최대", "count": "개수",
            "std": "표준편차", "stddev": "표준편차"
        }
        agg_kr = agg_kr_map.get(parsed.get("agg"), parsed.get("agg", ""))
        col = parsed.get("col") or "*"
        r0 = rows[0] if rows else {}
        if "value" in r0:
            return f"{col} {agg_kr}={r0.get('value')} (표본 {r0.get('n', 0)}개)"
        return f"요약 생성 실패: {str(e)}"

@app.post("/query")
def query(q: QueryIn):
    """표준 payload 반환: question, summary, sql, columns, data, meta"""
    try:
        con = duckdb.connect(str(DB))
        try:
            payload = build_payload(q.question, con)
            return payload
        finally:
            con.close()
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "hint_examples": [
                "standard_trace_001 pressact 평균",
                "standard_trace_001 스텝별 pressact 평균",
                "공정별 pressact 평균 top5",
                "standard_trace_001 step=STANDBY pressact 최대",
                "pressact 표준편차",
                "pressact 중앙값",
            ],
        }
=======
def choose_sql(parsed_obj):
    """SQL 빌더 선택 (우선순위: trace_compare > overshoot > outlier > dwell_time > stable_avg > 기본)"""
    if parsed_obj.is_trace_compare:
        return build_trace_compare_sql(parsed_obj)
    if parsed_obj.is_overshoot:
        return build_overshoot_sql(parsed_obj)
    if parsed_obj.is_outlier:
        return build_outlier_detection_sql(parsed_obj)
    if parsed_obj.is_dwell_time:
        return build_dwell_time_sql(parsed_obj)
    if parsed_obj.is_stable_avg:
        return build_stable_avg_sql(parsed_obj)
    return build_sql(parsed_obj)

def run_query(parsed_obj):
    """SQL 실행 및 결과 반환"""
    sql, params = choose_sql(parsed_obj)
    with duckdb.connect(str(DB), read_only=True) as con:
        df = con.execute(sql, params).df()
    return sql.strip(), params, df

def strip_trailing_limit(sql: str) -> str:
    """맨 끝 LIMIT n만 제거 (위험 최소화)"""
    import re
    return re.sub(r"\s+LIMIT\s+\d+\s*;?\s*$", "", sql, flags=re.IGNORECASE)

def add_others_row(df_top: pd.DataFrame, df_all: pd.DataFrame) -> pd.DataFrame:
    """Others 행 추가 (Top N 외 나머지 데이터 요약)"""
    if df_all is None or len(df_all) <= len(df_top):
        return df_top

    x_col = df_top.columns[0]
    y_col = "value" if "value" in df_top.columns else ("n" if "n" in df_top.columns else df_top.columns[-1])

    others_df = df_all.iloc[len(df_top):]
    if others_df.empty:
        return df_top

    others_row = {x_col: "Others (기타)", y_col: float(others_df[y_col].mean())}

    if "n" in df_all.columns:
        others_row["n"] = int(others_df["n"].sum())
    if "std" in df_all.columns:
        others_row["std"] = float(others_df["std"].mean())
    if "min_val" in df_all.columns:
        others_row["min_val"] = float(others_df["min_val"].min())
    if "max_val" in df_all.columns:
        others_row["max_val"] = float(others_df["max_val"].max())

    return pd.concat([df_top, pd.DataFrame([others_row])], ignore_index=True)
>>>>>>> 378f42a2115c8718668a2287e9ab54018ecf432a

# ✅ HTML 테이블 UI
@app.get("/view", response_class=HTMLResponse)
def view(request: Request, q: str | None = None, show_all: str | None = None):
    if not q:
        return templates.TemplateResponse("index.html", {"request": request, "q": ""})

    try:
        norm = normalize(q)  # ✅ 추가: /query와 동일하게 정규화 객체 생성
        parsed_obj = parse_question(q)
        
        # 스텝별 쿼리는 기본값 limit=10 적용 (명시적으로 지정하지 않은 경우)
        # show_all=1이면 전체 보기
        if parsed_obj.group_by == "step_name" and parsed_obj.limit is None:
            if show_all != "1":
                parsed_obj.limit = 10
                parsed_obj.order = "desc"
                show_all_button = True
                add_others = True  # Others 그룹 추가
            else:
                show_all_button = False
                add_others = False
        else:
            show_all_button = False
            add_others = False
        
        # SQL 실행
        sql, params, df_top = run_query(parsed_obj)
        
<<<<<<< HEAD
        con = duckdb.connect(str(DB))
        try:
            df = con.execute(sql, params).df()
            
            # Others 그룹 추가 (스텝별이고 limit이 있을 때)
            if add_others and parsed_obj.group_by == "step_name" and parsed_obj.limit:
                # y_col 먼저 찾기
                y_col_temp = "value" if "value" in df.columns else ("n" if "n" in df.columns else df.columns[-1])
                x_col_temp = df.columns[0]
                
                # 전체 데이터 가져오기 (LIMIT 제거)
                sql_all = sql
                if "LIMIT" in sql_all.upper():
                    # LIMIT 절 제거
                    import re
                    sql_all = re.sub(r'\s+LIMIT\s+\d+', '', sql_all, flags=re.IGNORECASE)
                
=======
        # Others 그룹 추가 (스텝별이고 top_n이 있을 때)
        df = df_top
        if add_others and parsed_obj.group_by == "step_name" and parsed_obj.top_n:
            # 전체 데이터 가져오기 (LIMIT 제거)
            sql_all = strip_trailing_limit(sql)
            with duckdb.connect(str(DB), read_only=True) as con:
>>>>>>> 378f42a2115c8718668a2287e9ab54018ecf432a
                df_all = con.execute(sql_all, params).df()
            df = add_others_row(df_top, df_all)
        
        rows_raw = df.to_dict(orient="records")
        # 포맷팅 적용
        parsed = to_parsed_dict(parsed_obj)
        rows = [format_row(row, parsed) for row in rows_raw]
        summary = make_summary(parsed, rows_raw)
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request, 
                "q": q,  # 원문 질문
                "question_raw": norm.raw,  # 원문 질문 (명시적)
                "question_normalized": norm.text,  # 정규화된 질문
                "parsed": parsed, 
                "sql": sql.strip(), 
                "rows": rows, 
                "rows_raw": rows_raw,  # 원본 데이터 (필터링/정렬용)
                "summary": summary,
                "show_all_button": show_all_button,
            },
        )
    except Exception as e:
        return templates.TemplateResponse(
            "index.html", 
            {
                "request": request, 
                "q": q,
                "question_raw": norm.raw,
                "question_normalized": norm.text,
                "error": str(e)
            }
        )

# ✅ PNG plot (브라우저에서 바로 열리는 엔드포인트) - 레거시 (하위 호환성)
@app.get("/plot")
<<<<<<< HEAD
def plot_legacy(q: str):
    try:
        parsed_obj = parse_question(q)
        
        # 공정 친화 지표 또는 이상치 탐지 처리
        if parsed_obj.is_trace_compare:
            sql, params = build_trace_compare_sql(parsed_obj)
            # 비교는 바 차트
            parsed_obj.chart_type = "bar"
        elif parsed_obj.is_overshoot:
            sql, params = build_overshoot_sql(parsed_obj)
            # overshoot은 스텝별이므로 가로 막대
            parsed_obj.chart_type = "bar"
        elif parsed_obj.is_outlier:
            sql, params = build_outlier_detection_sql(parsed_obj)
            # 이상치는 trace별이므로 바 차트
            parsed_obj.chart_type = "bar"
        elif parsed_obj.is_dwell_time:
            sql, params = build_dwell_time_sql(parsed_obj)
            parsed_obj.chart_type = "bar"
        elif parsed_obj.is_stable_avg:
            sql, params = build_stable_avg_sql(parsed_obj)
        else:
            sql, params = build_sql(parsed_obj)
=======
def plot(q: str):
    parsed_obj = parse_question(q)
    
    # 차트 타입 설정
    if parsed_obj.is_trace_compare or parsed_obj.is_overshoot or parsed_obj.is_outlier or parsed_obj.is_dwell_time:
        parsed_obj.chart_type = "bar"
    
    # SQL 실행 및 차트 렌더링
    sql, params, df = run_query(parsed_obj)
    return render_chart(df, parsed_obj)
>>>>>>> 378f42a2115c8718668a2287e9ab54018ecf432a


<<<<<<< HEAD
        if df.empty:
            return Response(content=b"No data", media_type="text/plain")

        # 단일 값이면 간단 텍스트로
        if len(df.columns) == 1 and df.columns[0] in ("value", "n"):
            txt = df.to_string(index=False)
            return Response(content=txt.encode("utf-8"), media_type="text/plain; charset=utf-8")

        # 그룹 결과: x축(첫번째 컬럼), y축(value or n)
        x_col = df.columns[0]
        y_col = "value" if "value" in df.columns else ("n" if "n" in df.columns else df.columns[-1])

        # 🔥 핵심 변경: 분석 유형 기반 차트 템플릿 사용
        config = get_chart_template(parsed_obj.analysis_type)
        
        # 🔥 Rule 1: step 개수 > 12면 → 요약 그래프 (group_profile이지만 step이 많을 때)
        add_others_for_chart = False
        df_all_for_others = None
        if parsed_obj.analysis_type == "group_profile" and parsed_obj.group_by == "step_name" and len(df) > 12:
            # 요약 모드로 전환: Top 7 + Others
            if not parsed_obj.limit:  # 사용자가 명시하지 않았으면
                config = get_chart_template("ranking")  # ranking 스타일로 전환
                config["chart_type"] = "horizontal_bar"  # 가로 막대로
                parsed_obj.limit = 7  # Top 7만 표시
                parsed_obj.order = "desc"
                add_others_for_chart = True  # Others 추가 플래그
                # 나머지는 Others로 묶기 위해 원본 저장 (값 기준 정렬 필요)
                df_all_for_others = df.copy()
                # 값 기준으로 정렬 (내림차순)
                df = df.sort_values(y_col, ascending=False).head(7) if len(df) > 7 else df.sort_values(y_col, ascending=False)
        
        # 템플릿 설정에 따라 데이터 처리
        if config["use_top_n"] and parsed_obj.limit and len(df) > parsed_obj.limit:
            df = df.head(parsed_obj.limit)
        elif len(df) > 100:
            df = df.head(100)  # 최대 100개
        
        # 한글 레이블 매핑
        agg_kr = {"avg": "평균", "min": "최소", "max": "최대", "count": "개수"}.get(parsed_obj.agg, parsed_obj.agg)
        col_kr = parsed_obj.col or "전체"
        x_col_kr = "공정 ID" if x_col == "trace_id" else ("단계명" if x_col == "step_name" else ("일자" if x_col == "date" else ("시간" if x_col == "hour" else x_col)))
        y_col_kr = f"{col_kr} {agg_kr}" if parsed_obj.col else agg_kr

        fig, ax = plt.subplots(figsize=(14, 7))
        fig.patch.set_facecolor('white')
        
        # 🔥 분석 유형 기반 고정 템플릿 적용
        if config["chart_type"] == "line" or (parsed_obj.group_by in ("date", "hour", "day") or parsed_obj.date_start or parsed_obj.date_end):
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
            if y_vals:
                max_idx = y_vals.index(max(y_vals))
                ax.plot(max_idx, y_vals[max_idx], 'ro', markersize=12)
                ax.annotate(f'최대: {y_vals[max_idx]:.2f}', 
                           xy=(max_idx, y_vals[max_idx]),
                           xytext=(max_idx, y_vals[max_idx] + (max(y_vals) - min(y_vals)) * 0.1),
                           fontsize=10, fontweight='bold',
                           bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7),
                           ha='center')
        else:
            # 🔥 템플릿 적용 (analysis_type 기반)
            # Others 그룹 추가 (요약 모드일 때)
            if add_others_for_chart and df_all_for_others is not None and len(df_all_for_others) > len(df):
                others_df = df_all_for_others.sort_values(y_col, ascending=False).iloc[len(df):]
                others_value_sum = sum(r for r in others_df[y_col].astype(float).tolist())
                others_avg = others_value_sum / len(others_df) if len(others_df) > 0 else 0
                others_row = {x_col: f"Others ({len(others_df)}개)", y_col: others_avg}
                # DataFrame에 Others 행 추가
                df = pd.concat([df, pd.DataFrame([others_row])], ignore_index=True)
            
            apply_chart_template(ax, df, x_col, y_col, config, parsed_obj)
        
        # 축 레이블 및 제목 설정
        title_lines = []
        filter_parts = []  # 초기화 필수
        
        if parsed_obj.analysis_type == "comparison" and "trace1_avg" in df.columns:
            # 비교 차트는 별도 처리
            ax.set_xlabel("단계명", fontsize=12, fontweight='bold', labelpad=10)
            ax.set_ylabel(f"{col_kr} 평균 (mTorr)", fontsize=12, fontweight='bold', labelpad=10)
            title_lines = [f"{col_kr} 평균 비교 (단계명별)"]
            if parsed_obj.trace_ids and len(parsed_obj.trace_ids) >= 2:
                title_lines.append(f"공정: {parsed_obj.trace_ids[0]}, {parsed_obj.trace_ids[1]}")
        else:
            # 일반 차트
            ax.set_xlabel(x_col_kr, fontsize=12, fontweight='bold', labelpad=10)
            ax.set_ylabel(y_col_kr, fontsize=12, fontweight='bold', labelpad=10)
            
            # 제목 생성
            title_lines.append(f"{y_col_kr} ({x_col_kr}별)")
            
            if parsed_obj.trace_id:
                filter_parts.append(f"공정: {parsed_obj.trace_id}")
            if len(parsed_obj.trace_ids) > 1 and parsed_obj.analysis_type != "comparison":
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
    df = con.execute("SELECT DISTINCT trace_id FROM traces_dedup ORDER BY trace_id").df()
    return {"traces": df['trace_id'].tolist()}

# ✅ 데이터 탐색: 단계명 목록
@app.get("/api/steps")
def get_steps():
    con = duckdb.connect(str(DB))
    df = con.execute("SELECT DISTINCT step_name FROM traces_dedup ORDER BY step_name").df()
    return {"steps": df['step_name'].tolist()}

# ✅ CSV 다운로드
@app.get("/api/csv")
def download_csv(q: str):
    try:
        parsed_obj = parse_question(q)
        
        if parsed_obj.is_trace_compare:
            sql, params = build_trace_compare_sql(parsed_obj)
        elif parsed_obj.is_overshoot:
            sql, params = build_overshoot_sql(parsed_obj)
        elif parsed_obj.is_outlier:
            sql, params = build_outlier_detection_sql(parsed_obj)
        elif parsed_obj.is_dwell_time:
            sql, params = build_dwell_time_sql(parsed_obj)
        elif parsed_obj.is_stable_avg:
            sql, params = build_stable_avg_sql(parsed_obj)
        else:
            sql, params = build_sql(parsed_obj)
        
        con = duckdb.connect(str(DB))
        try:
            df = con.execute(sql, params).df()
        finally:
            con.close()
        
        csv_content = df.to_csv(index=False)
        
        return Response(
            content=csv_content.encode("utf-8-sig"),  # BOM 포함 (Excel 호환)
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="query_result_{q[:20]}.csv"'}
        )
    except Exception as e:
        return Response(content=f"오류: {str(e)}".encode("utf-8"), media_type="text/plain")

# ✅ 데이터 탐색: 데이터 범위
@app.get("/api/range")
def get_data_range():
    con = duckdb.connect(str(DB))
    min_date = con.execute("SELECT MIN(DATE(timestamp)) as min_date FROM traces_dedup").fetchone()[0]
    max_date = con.execute("SELECT MAX(DATE(timestamp)) as max_date FROM traces_dedup").fetchone()[0]
    total_rows = con.execute("SELECT COUNT(*) as cnt FROM traces_dedup").fetchone()[0]
    return {
        "min_date": str(min_date) if min_date else None,
        "max_date": str(max_date) if max_date else None,
        "total_rows": total_rows
    }

@app.get("/api/query")
def query_get(q: str):
    """GET 방식: 표준 payload 반환: question, summary, sql, columns, data, meta"""
    try:
        con = duckdb.connect(str(DB))
        try:
            payload = build_payload(q, con)
            return payload
        finally:
            con.close()
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "hint_examples": get_popular_questions(5),
        }

@app.get("/api/suggestions")
def get_question_suggestions(q: str = "", category: str = None, limit: int = 10):
    """
    질문 추천 및 자동완성
    
    Args:
        q: 검색어 (부분 매칭)
        category: 카테고리 필터
        limit: 반환할 최대 개수
    """
    if category:
        questions = get_category_suggestions(category)
        return {
            "suggestions": [{"question": q, "category": category} for q in questions[:limit]]
        }
    
    suggestions = get_suggestions(q, limit)
    return {"suggestions": suggestions}

@app.get("/api/popular")
def get_popular():
    """인기 질문 목록"""
    return {"questions": get_popular_questions(10)}

@app.get("/api/plot")
def plot_api(q: str):
    """시계열 Plot API: Matplotlib PNG 반환"""
    from urllib.parse import unquote
    
    try:
        q_decoded = unquote(q)
        p = parse_question(q_decoded)
        
        # SQL 생성
        if p.is_trace_compare:
            sql, params = build_trace_compare_sql(p)
        elif p.is_overshoot:
            sql, params = build_overshoot_sql(p)
        elif p.is_outlier:
            sql, params = build_outlier_detection_sql(p)
        elif p.is_dwell_time:
            sql, params = build_dwell_time_sql(p)
        elif p.is_stable_avg:
            sql, params = build_stable_avg_sql(p)
        else:
            sql, params = build_sql(p)
        
        con = duckdb.connect(str(DB))
        try:
            df = con.execute(sql, params).df()
        finally:
            con.close()
        
        # 시계열 Plot 생성
        from src.semantic_resolver import get_metadata_by_physical_column
        metadata = get_metadata_by_physical_column(p.col) if p.col else None
        unit = metadata.get("unit", "") if metadata else ""
        
        title = q_decoded
        x_col = "timestamp" if "timestamp" in df.columns else (df.columns[0] if not df.empty else "timestamp")
        y_col = "value" if "value" in df.columns else (df.columns[-1] if not df.empty else "value")
        
        buf = plot_timeseries(df, title=title, x_col=x_col, y_col=y_col, unit=unit)
        
        return Response(buf.read(), media_type="image/png")
    except Exception as e:
        # 에러 이미지 반환
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.text(0.5, 0.5, f"오류: {str(e)}", ha='center', va='center', transform=ax.transAxes, color='red')
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        buf.seek(0)
        plt.close(fig)
        return Response(buf.read(), media_type="image/png")

# ✅ CSV 다운로드
@app.get("/api/csv")
def download_csv(q: str):
    try:
        parsed_obj = parse_question(q)
        
        # 공정 친화 지표 또는 이상치 탐지 처리 (우선순위: trace_compare > overshoot > outlier > 기타)
        if parsed_obj.is_trace_compare:
            sql, params = build_trace_compare_sql(parsed_obj)
        elif parsed_obj.is_overshoot:
            sql, params = build_overshoot_sql(parsed_obj)
        elif parsed_obj.is_outlier:
            sql, params = build_outlier_detection_sql(parsed_obj)
        elif parsed_obj.is_dwell_time:
            sql, params = build_dwell_time_sql(parsed_obj)
        elif parsed_obj.is_stable_avg:
            sql, params = build_stable_avg_sql(parsed_obj)
        else:
            sql, params = build_sql(parsed_obj)
        
        con = duckdb.connect(str(DB))
        df = con.execute(sql, params).df()
        
        csv_str = df.to_csv(index=False)
        return Response(content=csv_str, media_type="text/csv", 
                       headers={"Content-Disposition": f"attachment; filename=query_result.csv"})
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ✅ 히스토리 저장/조회 (간단한 JSON 파일 기반)
HISTORY_FILE = PROJECT_ROOT / "data" / "history.json"

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
FAVORITES_FILE = PROJECT_ROOT / "data" / "favorites.json"

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
=======
>>>>>>> 378f42a2115c8718668a2287e9ab54018ecf432a
