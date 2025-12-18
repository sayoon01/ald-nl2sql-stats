from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request  # type: ignore
from fastapi.responses import Response, HTMLResponse, RedirectResponse  # type: ignore
from fastapi.templating import Jinja2Templates  # type: ignore
from pydantic import BaseModel  # type: ignore
import duckdb  # type: ignore
import pandas as pd  # type: ignore
import matplotlib  # type: ignore
matplotlib.use('Agg')  # 서버 환경에서 필요한 백엔드 설정
import matplotlib.pyplot as plt  # type: ignore
import matplotlib.font_manager as fm  # type: ignore
import io
import json
from datetime import datetime

# 한글 폰트 설정 (Linux 환경)
# Linux에서 사용 가능한 한글 폰트 우선 시도
try:
    import matplotlib.font_manager as fm
    
    # 사용 가능한 폰트 목록
    font_list = [f.name for f in fm.fontManager.ttflist]
    
    # 한글 지원 폰트 우선순위
    korean_font_candidates = [
        'NanumGothic',
        'NanumBarunGothic', 
        'Noto Sans CJK KR',
        'Noto Sans CJK JP',  # 일본어 폰트도 한글 지원
        'Noto Sans CJK SC',  # 중국어 간체도 한글 지원
        'Noto Sans CJK TC',  # 중국어 번체도 한글 지원
        'Noto Sans CJK',     # 일반 Noto Sans CJK
    ]
    
    # 폰트 찾기 (부분 매칭 포함)
    selected_font = None
    for candidate in korean_font_candidates:
        # 정확한 매칭
        if candidate in font_list:
            selected_font = candidate
            break
        # 부분 매칭 (예: "Noto Sans CJK"로 시작하는 폰트)
        for font_name in font_list:
            if candidate.lower() in font_name.lower() or font_name.lower() in candidate.lower():
                selected_font = font_name
                break
        if selected_font:
            break
    
    if selected_font:
        plt.rcParams['font.family'] = selected_font
        print(f"[Font] 한글 폰트 설정: {selected_font}")
    else:
        # 폰트 파일 경로에서 직접 찾기
        for font_prop in fm.fontManager.ttflist:
            font_path = str(font_prop.fname).lower()
            if 'noto' in font_path and ('cjk' in font_path or 'korean' in font_path):
                plt.rcParams['font.family'] = font_prop.name
                print(f"[Font] 한글 폰트 설정 (경로 기반): {font_prop.name}")
                break
        else:
            # 마지막 fallback: DejaVu Sans (한글 미지원이지만 깨지지 않게)
            plt.rcParams['font.family'] = 'DejaVu Sans'
            print("[Font] 한글 폰트를 찾을 수 없어 DejaVu Sans 사용 (한글 깨짐 가능)")
            
except Exception as e:
    plt.rcParams['font.family'] = 'DejaVu Sans'
    print(f"[Font] 폰트 설정 오류: {e}, DejaVu Sans 사용")

plt.rcParams['axes.unicode_minus'] = False  # 음수 기호 깨짐 방지

# 폰트 캐시 재로드 (한글 폰트가 제대로 적용되도록)
try:
    fm._rebuild()
except:
    pass
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
from src.chart_templates import get_chart_template, apply_chart_template

# 프로젝트 루트 경로 설정
PROJECT_ROOT = Path(__file__).parent.parent
DB = PROJECT_ROOT / "data_out" / "ald.duckdb"

app = FastAPI(title="ALD NL→SQL Stats API")
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))

class QueryIn(BaseModel):
    question: str

@app.get("/")
def root():
    return RedirectResponse(url="/view")

# 컬럼별 반올림 규칙 및 단위
COL_FORMAT = {
    "pressact": {"decimals": 3, "unit": "mTorr"},
    "pressset": {"decimals": 3, "unit": "mTorr"},
    "vg11": {"decimals": 2, "unit": ""},
    "vg12": {"decimals": 2, "unit": ""},
    "vg13": {"decimals": 2, "unit": ""},
    "apcvalvemon": {"decimals": 2, "unit": "%"},
    "apcvalveset": {"decimals": 2, "unit": "%"},
}

def format_value(value: float, col: Optional[str] = None, agg: str = "avg") -> str:
    """값 포맷팅 (반올림 + 단위)"""
    if value is None or (isinstance(value, float) and (value != value)):  # NaN 체크
        return "N/A"
    
    # null_ratio는 퍼센트
    if agg == "null_ratio":
        return f"{value:.2f}%"
    
    # 컬럼별 포맷 규칙 적용
    if col and col in COL_FORMAT:
        fmt = COL_FORMAT[col]
        decimals = fmt["decimals"]
        unit = fmt["unit"]
        formatted = f"{value:.{decimals}f}"
        return f"{formatted}{' ' + unit if unit else ''}"
    
    # 기본: 소수점 2자리
    return f"{value:.2f}"

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

def make_summary(parsed: dict, rows: list) -> str:
    agg_kr_map = {
        "avg": "평균", "min": "최소", "max": "최대", "count": "개수",
        "std": "표준편차", "stddev": "표준편차", "p50": "중앙값", "median": "중앙값",
        "p95": "95퍼센타일", "p99": "99퍼센타일", "null_ratio": "결측률"
    }
    agg_kr = agg_kr_map.get(parsed["agg"], parsed["agg"])
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
        key_kr = "공정 ID" if key == "trace_id" else ("단계명" if key == "step_name" else key)
        
        # 요청한 top_n과 실제 반환된 개수 비교
        requested_top_n = parsed.get("top_n")
        actual_count = len(rows)
        
        if requested_top_n and actual_count < requested_top_n:
            summary = f"{scope_txt}{col} {agg_kr} ({key_kr}별 Top {requested_top_n} 요청, 실제 {actual_count}개 반환). 1위={top.get(key)}: {top.get('value')}"
            summary += f" (데이터가 {requested_top_n}개보다 적습니다)"
        else:
            summary = f"{scope_txt}{col} {agg_kr} ({key_kr}별 Top {actual_count}). 1위={top.get(key)}: {top.get('value')}"
        
        # 추가 통계 정보 (n, std, min, max)가 있으면 표시
        if "n" in top:
            summary += f" (n={top['n']})"
        if "std" in top and top.get("std"):
            summary += f" [std={top['std']}]"
        if "min_val" in top and "max_val" in top:
            summary += f" [범위: {top['min_val']} ~ {top['max_val']}]"
        return summary
    
    # trace 비교 케이스
    if parsed.get("is_trace_compare") and rows:
        top = rows[0]
        trace_ids = parsed.get("trace_ids", [])
        if len(trace_ids) >= 2:
            step_name = top.get('step_name', '')
            diff_val = top.get('diff', 0)
            trace1_avg = top.get('trace1_avg', 0)
            trace2_avg = top.get('trace2_avg', 0)
            
            # 해석 추가
            diff_str = f"{diff_val:.1f}" if isinstance(diff_val, (int, float)) else str(diff_val)
            trace1_str = f"{trace_ids[0]}"
            trace2_str = f"{trace_ids[1]}"
            
            # 해석 텍스트 생성
            interpretation = ""
            if step_name == "STANDBY":
                interpretation = "이는 대기 단계에서 진공 안정화 또는 배기 제어 차이가 있었을 가능성을 시사합니다."
            elif step_name in ["B.FILL", "B.FILL4", "B.FILL5"]:
                interpretation = "이는 충진 단계에서 압력 제어 프로파일 차이가 있었을 가능성을 시사합니다."
            elif step_name in ["B.UP", "B.DOWN"]:
                interpretation = "이는 압력 변화 단계에서 제어 속도 또는 목표값 차이가 있었을 가능성을 시사합니다."
            else:
                interpretation = "이는 해당 단계에서 공정 조건 또는 제어 파라미터 차이가 있었을 가능성을 시사합니다."
            
            summary = f"{step_name} 단계에서 trace 간 pressact 차이가 가장 큽니다 (차이: ≈{diff_str} mTorr, {trace1_str}: {trace1_avg:.1f} mTorr, {trace2_str}: {trace2_avg:.1f} mTorr). {interpretation}"
            return summary
    
    # 이상치 탐지 케이스
    if parsed.get("is_outlier"):
        if not rows:
            return "이상치가 발견되지 않았습니다. (z-score > 1.0 기준)"
        top = rows[0]
        summary = f"이상치 비율 Top {len(rows)}. 1위 trace={top.get('trace_id')}: {top.get('value')}% (n={top.get('n')}, 이상치={top.get('outlier_count')})"
        return summary

    r0 = rows[0]
    if "value" in r0:
        summary = f"{scope_txt}{col} {agg_kr}={r0['value']}"
        if "n" in r0:
            summary += f" (n={r0['n']})"
        if "std" in r0 and r0.get("std"):
            summary += f" [std={r0['std']}]"
        return summary
    if "n" in r0:
        return f"{scope_txt}{col} {agg_kr}={r0['n']}"
    return "요약 생성 실패"

@app.post("/query")
def query(q: QueryIn):
    # 정규화
    norm = normalize(q.question)
    
    try:
        parsed_obj = parse_question(q.question)
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "question": norm.raw,
            "normalized": norm.text,
            "hint_examples": [
                "standard_trace_001 pressact 평균",
                "standard_trace_001 스텝별 pressact 평균",
                "공정별 pressact 평균 top5",
                "standard_trace_001 step=STANDBY pressact 최대",
                "pressact 표준편차",
                "pressact 중앙값",
            ],
        }

    # 공정 친화 지표 또는 이상치 탐지 처리
    if parsed_obj.is_trace_compare:
        sql, params = build_trace_compare_sql(parsed_obj)
    elif parsed_obj.is_outlier:
        sql, params = build_outlier_detection_sql(parsed_obj)
    elif parsed_obj.is_dwell_time:
        sql, params = build_dwell_time_sql(parsed_obj)
    elif parsed_obj.is_overshoot:
        sql, params = build_overshoot_sql(parsed_obj)
    elif parsed_obj.is_stable_avg:
        sql, params = build_stable_avg_sql(parsed_obj)
    else:
        sql, params = build_sql(parsed_obj)

    con = duckdb.connect(str(DB))
    try:
        df = con.execute(sql, params).df()
        rows_raw = df.to_dict(orient="records")
        parsed = parsed_obj.__dict__
        # 포맷팅 적용
        rows = [format_row(row, parsed) for row in rows_raw]
    finally:
        con.close()
    
    parsed = parsed_obj.__dict__
    summary = make_summary(parsed, rows_raw)  # summary는 원본 값 사용

    return {
        "ok": True,
        "question": norm.raw,  # 원문 질문
        "normalized": norm.text,  # 정규화된 질문
        "parsed": parsed,
        "sql": sql.strip(),
        "rows": rows,
        "summary": summary,
    }

# ✅ HTML 테이블 UI
@app.get("/view", response_class=HTMLResponse)
def view(request: Request, q: str | None = None, show_all: str | None = None):
    if not q:
        return templates.TemplateResponse("index.html", {"request": request, "q": ""})

    try:
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
        try:
            df = con.execute(sql, params).df()
            
            # Others 그룹 추가 (스텝별이고 top_n이 있을 때)
            if add_others and parsed_obj.group_by == "step_name" and parsed_obj.top_n:
                # y_col 먼저 찾기
                y_col_temp = "value" if "value" in df.columns else ("n" if "n" in df.columns else df.columns[-1])
                x_col_temp = df.columns[0]
                
                # 전체 데이터 가져오기 (LIMIT 제거)
                sql_all = sql
                if "LIMIT" in sql_all.upper():
                    # LIMIT 절 제거
                    import re
                    sql_all = re.sub(r'\s+LIMIT\s+\d+', '', sql_all, flags=re.IGNORECASE)
                
                df_all = con.execute(sql_all, params).df()
                
                if len(df_all) > len(df):
                    # 나머지 데이터의 평균 계산
                    others_df = df_all.iloc[len(df):]
                    others_avg = others_df[y_col_temp].mean() if y_col_temp in others_df.columns else 0
                    others_count = others_df["n"].sum() if "n" in others_df.columns else len(others_df)
                    others_std = others_df["std"].mean() if "std" in others_df.columns else None
                    
                    # Others 행 추가
                    others_row = {x_col_temp: "Others (기타)", y_col_temp: others_avg}
                    if "n" in df_all.columns:
                        others_row["n"] = others_count
                    if "std" in df_all.columns and others_std is not None:
                        others_row["std"] = others_std
                    if "min_val" in df_all.columns:
                        others_row["min_val"] = others_df["min_val"].min() if "min_val" in others_df.columns else None
                    if "max_val" in df_all.columns:
                        others_row["max_val"] = others_df["max_val"].max() if "max_val" in others_df.columns else None
                    
                    df = pd.concat([df, pd.DataFrame([others_row])], ignore_index=True)
            
            rows_raw = df.to_dict(orient="records")
            # 포맷팅 적용
            parsed = parsed_obj.__dict__
            rows = [format_row(row, parsed) for row in rows_raw]
        finally:
            con.close()
        
        parsed = parsed_obj.__dict__
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

        # 🔥 핵심 변경: 분석 유형 기반 차트 템플릿 사용
        config = get_chart_template(parsed_obj.analysis_type)
        
        # 🔥 Rule 1: step 개수 > 12면 → 요약 그래프 (group_profile이지만 step이 많을 때)
        add_others_for_chart = False
        df_all_for_others = None
        if parsed_obj.analysis_type == "group_profile" and parsed_obj.group_by == "step_name" and len(df) > 12:
            # 요약 모드로 전환: Top 7 + Others
            if not parsed_obj.top_n:  # 사용자가 명시하지 않았으면
                config = get_chart_template("ranking")  # ranking 스타일로 전환
                config["chart_type"] = "horizontal_bar"  # 가로 막대로
                parsed_obj.top_n = 7  # Top 7만 표시
                add_others_for_chart = True  # Others 추가 플래그
                # 나머지는 Others로 묶기 위해 원본 저장 (값 기준 정렬 필요)
                df_all_for_others = df.copy()
                # 값 기준으로 정렬 (내림차순)
                df = df.sort_values(y_col, ascending=False).head(7) if len(df) > 7 else df.sort_values(y_col, ascending=False)
        
        # 템플릿 설정에 따라 데이터 처리
        if config["use_top_n"] and parsed_obj.top_n and len(df) > parsed_obj.top_n:
            df = df.head(parsed_obj.top_n)
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
