"""
Parsed 객체 변환 유틸리티
"""
from typing import Dict


def to_parsed_dict(parsed_obj) -> dict:
    """Parsed 객체를 딕셔너리로 변환 (하위 호환성: agg, col 등 모든 속성 포함)"""
    d = parsed_obj.__dict__.copy()
    # 하위 호환성을 위한 속성 매핑
    d["agg"] = getattr(parsed_obj, "agg", d.get("metric", "avg"))
    d["col"] = getattr(parsed_obj, "col", d.get("column"))
    d["group_by"] = getattr(parsed_obj, "group_by", d.get("group_by"))
    d["top_n"] = getattr(parsed_obj, "top_n", d.get("top_n"))
    d["analysis_type"] = getattr(parsed_obj, "analysis_type", d.get("analysis_type"))
    # 필터 속성들
    filters = d.get("filters", {})
    d["trace_id"] = filters.get("trace_id") if filters else getattr(parsed_obj, "trace_id", None)
    d["trace_ids"] = filters.get("trace_ids", []) if filters else getattr(parsed_obj, "trace_ids", [])
    d["step_name"] = filters.get("step_name") if filters else getattr(parsed_obj, "step_name", None)
    d["step_names"] = filters.get("step_names", []) if filters else getattr(parsed_obj, "step_names", [])
    d["date_start"] = filters.get("date_start") if filters else getattr(parsed_obj, "date_start", None)
    d["date_end"] = filters.get("date_end") if filters else getattr(parsed_obj, "date_end", None)
    # 플래그 속성들
    flags = d.get("flags", {})
    d["is_trace_compare"] = flags.get("is_trace_compare", False) if flags else getattr(parsed_obj, "is_trace_compare", False)
    d["is_outlier"] = flags.get("is_outlier", False) if flags else getattr(parsed_obj, "is_outlier", False)
    d["is_overshoot"] = flags.get("is_overshoot", False) if flags else getattr(parsed_obj, "is_overshoot", False)
    d["is_dwell_time"] = flags.get("is_dwell_time", False) if flags else getattr(parsed_obj, "is_dwell_time", False)
    d["is_stable_avg"] = flags.get("is_stable_avg", False) if flags else getattr(parsed_obj, "is_stable_avg", False)
    return d

