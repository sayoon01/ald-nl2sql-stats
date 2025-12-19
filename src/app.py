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
from src.charts.renderer import render_chart
from src.services.summary import make_summary
from src.utils.parsed import to_parsed_dict

# 프로젝트 루트 경로 설정
PROJECT_ROOT = Path(__file__).parent.parent
DB = PROJECT_ROOT / "data_out" / "ald.duckdb"
SCHEMA_PATH = PROJECT_ROOT / "domain" / "schema" / "columns.yaml"

app = FastAPI(title="ALD NL→SQL Stats API")
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))

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

# ✅ HTML 테이블 UI
@app.get("/view", response_class=HTMLResponse)
def view(request: Request, q: str | None = None, show_all: str | None = None):
    if not q:
        return templates.TemplateResponse("index.html", {"request": request, "q": ""})

    try:
        norm = normalize(q)  # ✅ 추가: /query와 동일하게 정규화 객체 생성
        parsed_obj = parse_question(q)
        
        # 스텝별 쿼리는 기본값 top10 적용 (명시적으로 지정하지 않은 경우)
        # show_all=1이면 전체 보기
        if parsed_obj.group_by == "step_name" and parsed_obj.top_n is None:
            if show_all != "1":
                parsed_obj.top_n = 10
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
        
        # Others 그룹 추가 (스텝별이고 top_n이 있을 때)
        df = df_top
        if add_others and parsed_obj.group_by == "step_name" and parsed_obj.top_n:
            # 전체 데이터 가져오기 (LIMIT 제거)
            sql_all = strip_trailing_limit(sql)
            with duckdb.connect(str(DB), read_only=True) as con:
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

# ✅ PNG plot (브라우저에서 바로 열리는 엔드포인트)
@app.get("/plot")
def plot(q: str):
    parsed_obj = parse_question(q)
    
    # 차트 타입 설정
    if parsed_obj.is_trace_compare or parsed_obj.is_overshoot or parsed_obj.is_outlier or parsed_obj.is_dwell_time:
        parsed_obj.chart_type = "bar"
    
    # SQL 실행 및 차트 렌더링
    sql, params, df = run_query(parsed_obj)
    return render_chart(df, parsed_obj)


