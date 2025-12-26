"""
Payload Builder: UI용 표준 payload 생성

역할:
- meta 생성 (시각화 전용 정보)
- payload 조립 (question, summary, sql, columns, data, meta)
"""
from typing import Dict, Any
import pandas as pd
from src.nl_parse import Parsed
from src.semantic_resolver import get_metadata_by_physical_column


def build_meta(p: Parsed) -> Dict[str, Any]:
    """
    meta 생성: UI가 어떻게 그릴지만 결정 (시각화 전용 정보)
    
    원칙:
    - 데이터 해석 ❌
    - SQL ❌
    → 시각화 전용 정보만 제공
    
    Args:
        p: Parsed 객체
        
    Returns:
        meta 딕셔너리 (chart, title, unit, description 등)
    """
    col = p.col
    agg = p.agg
    group = p.group_by
    
    # semantic_registry에서 메타데이터 가져오기
    metadata = get_metadata_by_physical_column(col) if col else None
    unit = metadata.get("unit", "") if metadata else ""
    description = metadata.get("description", "") if metadata else (col if col else "")
    
    # 집계 함수 한글 변환
    agg_map = {
        "avg": "평균",
        "max": "최대",
        "min": "최소",
        "std": "표준편차",
        "count": "개수"
    }
    agg_kor = agg_map.get(agg, agg)
    
    # ---- 단일 값 (bignum) ----
    if group is None:
        title = f"{description} {agg_kor}" if description else f"{col} {agg_kor}"
        return {
            "chart": "bignum",
            "title": title,
            "value_col": "value",
            "unit": unit,
            "description": description if description else col
        }
    
    # ---- 시계열 (time series) ----
    if group in ("day", "hour") or (hasattr(p, 'date_start') and p.date_start) or (hasattr(p, 'date_end') and p.date_end):
        # img_endpoint는 build_payload에서 질문 문자열로 채워짐
        return {
            "chart": "line_img",
            "title": f"{description} {agg_kor}" if description else f"{col} {agg_kor}",
            "x": group if group in ("day", "hour") else "timestamp",
            "y": "value",
            "unit": unit,
            "description": description if description else col
        }
    
    # ---- 그룹형 (bar chart) ----
    group_map = {
        "step_name": "스텝",
        "trace_id": "공정",
        "day": "일",
        "hour": "시간"
    }
    group_kor = group_map.get(group, group)
    title = f"{group_kor}별 {description} {agg_kor}" if description else f"{group_kor}별 {col} {agg_kor}"
    
    meta = {
        "chart": "bar",
        "title": title,
        "x": group,
        "y": "value",
        "unit": unit,
        "description": description if description else col
    }
    
    # order와 top_n 추가 (있는 경우만)
    if hasattr(p, 'order') and p.order:
        meta["order"] = p.order
    if hasattr(p, 'limit') and p.limit:
        meta["top_n"] = p.limit
    
    return meta


def build_payload(question: str, con) -> Dict[str, Any]:
    """
    최종 payload 조립
    
    Args:
        question: 사용자 질문
        con: DuckDB connection
        
    Returns:
        표준 payload 딕셔너리:
        {
            "question": str,
            "summary": str,
            "sql": str,
            "columns": List[str],
            "data": List[Dict],
            "meta": Dict
        }
    """
    from src.nl_parse import parse_question
    from src.sql_builder import build_sql
    from src.interpreter import interpret
    from urllib.parse import quote
    
    p = parse_question(question)
    sql, params = build_sql(p)
    df = con.execute(sql, params).df()
    
    # meta 생성 시 질문 문자열 전달 (시계열용)
    p._question = question  # 임시 속성 추가
    meta = build_meta(p)
    
    # 시계열인 경우 img_endpoint에 질문 추가
    if meta.get("chart") == "line_img":
        meta["img_endpoint"] = f"/api/plot?q={quote(question)}"
    
    payload = {
        "question": question,
        "summary": interpret(p, df),
        "sql": sql.strip(),
        "columns": list(df.columns),
        "data": df.head(200).to_dict(orient="records"),
        "meta": meta
    }
    
    return payload

