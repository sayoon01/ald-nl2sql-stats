"""
차트 템플릿: 분석 유형(Analysis Type)별 고정 시각화 템플릿

원칙: 질문 의도 → 분석 유형 → 고정 그래프 (자동 선택 X, 자동 매핑 O)
"""
from typing import Tuple, Dict, Any, Literal
import matplotlib.pyplot as plt  # type: ignore
import numpy as np  # type: ignore
import pandas as pd  # type: ignore

ChartConfig = Dict[str, Any]

def get_chart_template(analysis_type: Literal["ranking", "group_profile", "comparison", "stability"]) -> ChartConfig:
    """
    분석 유형에 따른 차트 템플릿 반환
    
    Returns:
        ChartConfig: {
            "chart_type": "horizontal_bar" | "bar" | "line" | "grouped_bar" | "box" | "scatter",
            "use_top_n": bool,
            "color_scheme": "ranking" | "sequential" | "comparison" | "diverging",
            "highlight_max": bool,
            "ordered": bool,  # 순서가 중요한가 (step 순서 등)
        }
    """
    templates = {
        "ranking": {
            "chart_type": "horizontal_bar",
            "use_top_n": True,
            "color_scheme": "ranking",  # 상위 3개 강조
            "highlight_max": True,
            "ordered": False,  # 값 순서로 정렬
        },
        "group_profile": {
            "chart_type": "bar",  # 또는 line (시계열이면)
            "use_top_n": False,
            "color_scheme": "sequential",
            "highlight_max": False,
            "ordered": True,  # step 순서 중요
        },
        "comparison": {
            "chart_type": "grouped_bar",
            "use_top_n": False,
            "color_scheme": "comparison",  # 두 trace 색상
            "highlight_max": True,  # 차이 큰 step 강조
            "ordered": False,  # 차이 순서로 정렬
        },
        "stability": {
            "chart_type": "box",  # 또는 scatter (outlier인 경우)
            "use_top_n": True,  # top_n trace만
            "color_scheme": "diverging",
            "highlight_max": False,
            "ordered": False,
        },
    }
    return templates.get(analysis_type, templates["ranking"])

def apply_chart_template(
    ax: plt.Axes,
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    config: ChartConfig,
    parsed: Any,  # Parsed 객체
) -> None:
    """
    차트 템플릿을 적용하여 그래프 그리기
    
    Args:
        ax: matplotlib axes
        df: 데이터프레임
        x_col: x축 컬럼명
        y_col: y축 컬럼명
        config: 차트 설정 (get_chart_template 반환값)
        parsed: Parsed 객체 (추가 정보용)
    """
    chart_type = config["chart_type"]
    
    if chart_type == "horizontal_bar":
        _draw_horizontal_bar(ax, df, x_col, y_col, config, parsed)
    elif chart_type == "bar":
        _draw_bar(ax, df, x_col, y_col, config, parsed)
    elif chart_type == "line":
        _draw_line(ax, df, x_col, y_col, config, parsed)
    elif chart_type == "grouped_bar":
        _draw_grouped_bar(ax, df, x_col, y_col, config, parsed)
    elif chart_type == "box":
        _draw_box(ax, df, x_col, y_col, config, parsed)
    elif chart_type == "scatter":
        _draw_scatter(ax, df, x_col, y_col, config, parsed)
    else:
        # 기본값: bar
        _draw_bar(ax, df, x_col, y_col, config, parsed)

def _draw_horizontal_bar(ax: plt.Axes, df: pd.DataFrame, x_col: str, y_col: str, config: ChartConfig, parsed: Any) -> None:
    """랭킹용 가로 막대 차트"""
    y_vals = df[y_col].astype(float).tolist()
    labels = [str(x) for x in df[x_col].astype(str).tolist()]
    
    # 상위 3개 강조 색상, Others는 회색
    colors = []
    for i, label in enumerate(labels):
        if "Others" in str(label) or "기타" in str(label):
            colors.append('#888888')  # Others는 회색
        elif i < 3:
            colors.append('#ff6b6b' if i == 0 else '#ff8c69' if i == 1 else '#ffaa80')
        else:
            colors.append('#b0b0d0')
    
    bars = ax.barh(range(len(df)), y_vals, color=colors, edgecolor='white', linewidth=1.5)
    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    
    if config["highlight_max"] and y_vals:
        max_val = max(y_vals)
        max_pos = y_vals.index(max_val)
        ax.text(max_val, max_pos, f' 최대: {max_val:.2f}', 
                va='center', fontsize=10, fontweight='bold',
                bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7))

def _draw_bar(ax: plt.Axes, df: pd.DataFrame, x_col: str, y_col: str, config: ChartConfig, parsed: Any) -> None:
    """그룹별 분포용 세로 막대 차트"""
    y_vals = df[y_col].astype(float).tolist()
    labels = [str(x) for x in df[x_col].astype(str).tolist()]
    
    # 순차적 색상 (단계별 분포)
    colors = ['#667eea'] * len(y_vals)
    
    bars = ax.bar(range(len(df)), y_vals, color=colors, edgecolor='white', linewidth=1.5)
    ax.set_xticks(range(len(df)))
    ax.set_xticklabels(labels, rotation=45, ha='right')

def _draw_line(ax: plt.Axes, df: pd.DataFrame, x_col: str, y_col: str, config: ChartConfig, parsed: Any) -> None:
    """시계열 라인 차트"""
    x_vals = df[x_col].tolist()
    y_vals = df[y_col].astype(float).tolist()
    
    # 날짜/시간 정렬
    if x_col == "date":
        df = df.sort_values("date")
        x_vals = df[x_col].tolist()
        y_vals = df[y_col].astype(float).tolist()
    
    ax.plot(range(len(x_vals)), y_vals, marker='o', linewidth=2, markersize=6, color='#667eea')
    ax.set_xticks(range(len(x_vals)))
    ax.set_xticklabels([str(x) for x in x_vals], rotation=45, ha='right')

def _draw_grouped_bar(ax: plt.Axes, df: pd.DataFrame, x_col: str, y_col: str, config: ChartConfig, parsed: Any) -> None:
    """비교용 그룹 막대 차트 (trace 비교)"""
    if "trace1_avg" not in df.columns or "trace2_avg" not in df.columns:
        # 일반 막대로 대체
        _draw_bar(ax, df, x_col, y_col, config, parsed)
        return
    
    x = np.arange(len(df))
    width = 0.35
    
    trace1_vals = df["trace1_avg"].astype(float).tolist()
    trace2_vals = df["trace2_avg"].astype(float).tolist()
    labels = [str(x) for x in df[x_col].astype(str).tolist()]
    
    trace_ids = parsed.trace_ids if hasattr(parsed, 'trace_ids') and parsed.trace_ids else []
    trace1_label = trace_ids[0] if len(trace_ids) > 0 else "Trace 1"
    trace2_label = trace_ids[1] if len(trace_ids) > 1 else "Trace 2"
    
    bars1 = ax.bar(x - width/2, trace1_vals, width, label=trace1_label, 
                  color='#ff6b6b', edgecolor='white', linewidth=1.5)
    bars2 = ax.bar(x + width/2, trace2_vals, width, label=trace2_label, 
                  color='#667eea', edgecolor='white', linewidth=1.5)
    
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.legend(loc='upper left')
    
    # 최대 차이 step 강조
    if "diff" in df.columns and config["highlight_max"]:
        max_diff_idx = df["diff"].idxmax()
        max_diff_pos = df.index.get_loc(max_diff_idx)
        bars1[max_diff_pos].set_edgecolor('yellow')
        bars1[max_diff_pos].set_linewidth(3)
        bars2[max_diff_pos].set_edgecolor('yellow')
        bars2[max_diff_pos].set_linewidth(3)

def _draw_box(ax: plt.Axes, df: pd.DataFrame, x_col: str, y_col: str, config: ChartConfig, parsed: Any) -> None:
    """이상치/안정성용 박스 플롯"""
    # 간단한 막대로 대체 (박스 플롯은 데이터 구조가 달라야 함)
    _draw_horizontal_bar(ax, df, x_col, y_col, config, parsed)

def _draw_scatter(ax: plt.Axes, df: pd.DataFrame, x_col: str, y_col: str, config: ChartConfig, parsed: Any) -> None:
    """이상치 탐지용 산점도"""
    # 간단한 막대로 대체
    _draw_horizontal_bar(ax, df, x_col, y_col, config, parsed)

