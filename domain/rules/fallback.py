"""
Fallback 규칙
- 기본값 설정
- 추론 규칙
"""
from typing import Optional
from .validation import get_validator

def get_default_metric() -> str:
    """기본 집계 함수"""
    return "avg"

def get_default_column() -> Optional[str]:
    """기본 컬럼 (없으면 None)"""
    # 중요도가 높은 컬럼 중 첫 번째
    validator = get_validator()
    columns = validator.get_all_columns()
    
    # pressact가 있으면 우선
    if "pressact" in columns:
        return "pressact"
    
    # 없으면 첫 번째
    return columns[0] if columns else None

def infer_column_from_context(text: str, parsed: dict) -> Optional[str]:
    """컨텍스트에서 컬럼 추론"""
    # 이미 컬럼이 있으면 그대로
    if parsed.get("col"):
        return parsed["col"]
    
    # 기본 컬럼 반환
    return get_default_column()

def infer_metric_from_context(text: str, parsed: dict) -> str:
    """컨텍스트에서 지표 추론"""
    # 이미 지표가 있으면 그대로
    if parsed.get("agg"):
        return parsed["agg"]
    
    # 기본 지표 반환
    return get_default_metric()

