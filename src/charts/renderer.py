"""
차트 렌더링: matplotlib 기반 차트 생성
"""
import io
from typing import Optional
import pandas as pd  # type: ignore
import matplotlib.pyplot as plt  # type: ignore
from fastapi.responses import Response  # type: ignore

from src.chart_templates import get_chart_template, apply_chart_template
from src.charts.helpers import (
    get_xy_columns,
    apply_top_n_limit,
    prepare_chart_data_for_others,
    add_others_to_chart,
)
from src.charts.title import get_korean_labels, build_chart_title


def render_chart(df: pd.DataFrame, parsed_obj) -> Response:
    """
    차트 렌더링 (메인 함수)
    
    Args:
        df: 쿼리 결과 DataFrame
        parsed_obj: Parsed 객체
    
    Returns:
        Response: PNG 이미지
    """
    try:
        if df.empty:
            return Response(content=b"No data", media_type="text/plain")

        # 단일 값이면 간단 텍스트로
        if len(df.columns) == 1 and df.columns[0] in ("value", "n"):
            txt = df.to_string(index=False)
            return Response(content=txt.encode("utf-8"), media_type="text/plain; charset=utf-8")

        # parsed 딕셔너리 생성
        from src.utils.parsed import to_parsed_dict
        parsed = to_parsed_dict(parsed_obj)

        # x축, y축 컬럼 추출
        x_col, y_col = get_xy_columns(df)

        # 차트 템플릿 가져오기
        config = get_chart_template(parsed.get("analysis_type", "ranking"))

        # Others 추가를 위한 데이터 준비
        df, df_all_for_others, add_others_for_chart = prepare_chart_data_for_others(df, parsed, config)

        # Top N 제한 적용
        top_n = parsed.get("top_n")
        df = apply_top_n_limit(df, top_n if config["use_top_n"] else None)

        # 한글 레이블 매핑
        labels = get_korean_labels(parsed, x_col)

        # 차트 생성
        fig, ax = plt.subplots(figsize=(14, 7))
        fig.patch.set_facecolor('white')

        # 차트 타입에 따른 렌더링
        if config["chart_type"] == "line" or (parsed.get("group_by") in ("date", "hour", "day") or parsed.get("date_start") or parsed.get("date_end")):
            _render_line_chart(ax, df, x_col, y_col)
        else:
            # Others 그룹 추가 (요약 모드일 때)
            if add_others_for_chart:
                df = add_others_to_chart(df, df_all_for_others, x_col, y_col)
            apply_chart_template(ax, df, x_col, y_col, config, parsed_obj)

        # 축 레이블 및 제목 설정
        title_lines = build_chart_title(parsed, labels, df)
        
        if parsed.get("analysis_type") == "comparison" and "trace1_avg" in df.columns:
            ax.set_xlabel("단계명", fontsize=12, fontweight='bold', labelpad=10)
            ax.set_ylabel(f"{labels['col_kr']} 평균 (mTorr)", fontsize=12, fontweight='bold', labelpad=10)
        else:
            ax.set_xlabel(labels["x_col_kr"], fontsize=12, fontweight='bold', labelpad=10)
            ax.set_ylabel(labels["y_col_kr"], fontsize=12, fontweight='bold', labelpad=10)

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


def _render_line_chart(ax, df: pd.DataFrame, x_col: str, y_col: str):
    """라인 차트 렌더링"""
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

