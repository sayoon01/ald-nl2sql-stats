"""
차트 제목 및 라벨 생성
"""
from typing import Dict, List


def get_korean_labels(parsed: dict, x_col: str) -> Dict[str, str]:
    """한글 레이블 매핑"""
    agg_kr_map = {"avg": "평균", "min": "최소", "max": "최대", "count": "개수"}
    agg_kr = agg_kr_map.get(parsed.get("agg", "avg"), parsed.get("agg", "avg"))
    col_kr = parsed.get("col") or "전체"
    
    x_col_kr_map = {
        "trace_id": "공정 ID",
        "step_name": "단계명",
        "date": "일자",
        "hour": "시간"
    }
    x_col_kr = x_col_kr_map.get(x_col, x_col)
    y_col_kr = f"{col_kr} {agg_kr}" if parsed.get("col") else agg_kr
    
    return {
        "agg_kr": agg_kr,
        "col_kr": col_kr,
        "x_col_kr": x_col_kr,
        "y_col_kr": y_col_kr
    }


def build_chart_title(parsed: dict, labels: Dict[str, str], df) -> List[str]:
    """차트 제목 생성"""
    title_lines = []
    filter_parts = []
    
    if parsed.get("analysis_type") == "comparison" and "trace1_avg" in df.columns:
        # 비교 차트는 별도 처리
        title_lines = [f"{labels['col_kr']} 평균 비교 (단계명별)"]
        trace_ids = parsed.get("trace_ids", [])
        if trace_ids and len(trace_ids) >= 2:
            title_lines.append(f"공정: {trace_ids[0]}, {trace_ids[1]}")
    else:
        # 일반 차트
        title_lines.append(f"{labels['y_col_kr']} ({labels['x_col_kr']}별)")
        
        if parsed.get("trace_id"):
            filter_parts.append(f"공정: {parsed['trace_id']}")
        trace_ids = parsed.get("trace_ids", [])
        if len(trace_ids) > 1 and parsed.get("analysis_type") != "comparison":
            filter_parts.append(f"공정: {', '.join(trace_ids)}")
        if parsed.get("step_name"):
            filter_parts.append(f"단계: {parsed['step_name']}")
        step_names = parsed.get("step_names", [])
        if len(step_names) > 1:
            filter_parts.append(f"단계: {', '.join(step_names)}")
        if parsed.get("date_start"):
            filter_parts.append(f"시작: {parsed['date_start']}")
        if parsed.get("date_end"):
            filter_parts.append(f"종료: {parsed['date_end']}")
    
    if filter_parts:
        title_lines.append(" | ".join(filter_parts))
    
    return title_lines

