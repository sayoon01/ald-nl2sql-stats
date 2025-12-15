from typing import Tuple, List
from src.nl_parse import Parsed

# 허용된 컬럼명 화이트리스트 (SQL 인젝션 방지)
ALLOWED_COLS = {"pressact", "pressset", "vg11", "vg12", "vg13", "apcvalvemon", "apcvalveset"}
ALLOWED_GROUP_BY = {"trace_id", "step_name"}

def _build_where_clause(p: Parsed) -> Tuple[str, List]:
    """WHERE 절과 파라미터 생성"""
    where = []
    params: List = []

    # 여러 trace_id 비교
    if len(p.trace_ids) > 1:
        placeholders = ','.join(['?' for _ in p.trace_ids])
        where.append(f"trace_id IN ({placeholders})")
        params.extend(p.trace_ids)
    elif p.trace_id:
        where.append("trace_id = ?")
        params.append(p.trace_id)

    # 여러 step_name 비교
    if len(p.step_names) > 1:
        placeholders = ','.join(['?' for _ in p.step_names])
        where.append(f"lower(step_name) IN ({placeholders})")
        params.extend([s.lower() for s in p.step_names])
    elif p.step_name:
        where.append("lower(step_name) = lower(?)")
        params.append(p.step_name)

    # 날짜 범위 필터링
    if p.date_start:
        where.append("DATE(timestamp) >= ?")
        params.append(p.date_start)
    if p.date_end:
        where.append("DATE(timestamp) <= ?")
        params.append(p.date_end)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    return where_sql, params

def _get_agg_function(agg: str, col: str) -> str:
    """집계 함수 SQL 생성"""
    if agg == "count":
        return "COUNT(*)"
    elif agg == "std" or agg == "stddev":
        return f"STDDEV({col})"
    elif agg == "p50" or agg == "median":
        return f"QUANTILE_CONT({col}, 0.5)"
    elif agg == "p95":
        return f"QUANTILE_CONT({col}, 0.95)"
    elif agg == "p99":
        return f"QUANTILE_CONT({col}, 0.99)"
    elif agg == "null_ratio":
        # 결측률: NULL 값 비율 (퍼센트)
        return f"CAST(COUNT(*) FILTER (WHERE {col} IS NULL) AS DOUBLE) / COUNT(*) * 100"
    else:
        agg_fn = {"avg": "AVG", "min": "MIN", "max": "MAX"}
        fn_name = agg_fn.get(agg, "AVG")
        return f"{fn_name}({col})"

def build_sql(p: Parsed, include_stats: bool = True) -> Tuple[str, List]:
    """
    SQL 생성
    include_stats: True면 n, std 등 추가 통계 포함 (기본값: True)
    """
    # 컬럼명 검증 (SQL 인젝션 방지)
    if p.col and p.col not in ALLOWED_COLS:
        raise ValueError(f"허용되지 않은 컬럼: {p.col}")
    
    where_sql, params = _build_where_clause(p)
    
    # 기본 집계 함수
    main_agg = _get_agg_function(p.agg, p.col) if p.col else "COUNT(*)"

    # 시간 기반 그룹핑 (일별, 시간별) - 중복 제거
    if p.group_by == "day":
        group_expr = "DATE(timestamp)"
        group_col = "date"
    elif p.group_by == "hour":
        group_expr = "EXTRACT(HOUR FROM timestamp)"
        group_col = "hour"
    else:
        group_expr = None
    
    if group_expr:
        if p.agg == "count":
            select_parts = [f"{group_expr} AS {group_col}", "COUNT(*) AS n"]
        else:
            select_parts = [f"{group_expr} AS {group_col}", f"{main_agg} AS value"]
            # 추가 통계 (n, std)
            if include_stats and p.col:
                select_parts.append(f"COUNT(*) AS n")
                if p.agg not in ("std", "stddev", "null_ratio"):
                    select_parts.append(f"STDDEV({p.col}) AS std")
        
        select_col = ", ".join(select_parts)
        order_col = group_col
        
        sql = f"""
        SELECT {select_col}
        FROM traces
        {where_sql}
        GROUP BY {group_expr}
        ORDER BY {order_col} ASC
        """
        
        if p.top_n:
            sql = f"SELECT * FROM ({sql}) ORDER BY {'n' if p.agg == 'count' else 'value'} DESC LIMIT {int(p.top_n)}"
        return sql, params

    # 여러 trace_id/step_name 비교 쿼리 (중복 제거)
    if len(p.trace_ids) > 1:
        group_col = "trace_id"
        order_col = "trace_id ASC"
    elif len(p.step_names) > 1:
        group_col = "step_name"
        order_col = "step_name ASC"
    elif p.group_by and p.group_by in ALLOWED_GROUP_BY:
        group_col = p.group_by
        order_col = "value DESC" if p.agg != "count" else "n DESC"
    else:
        group_col = None
    
    if group_col:
        if p.agg == "count":
            select_parts = [group_col, "COUNT(*) AS n"]
        else:
            select_parts = [group_col, f"{main_agg} AS value"]
            # 스텝별 통계 확장: n, std, min, max 추가
            if include_stats and p.col:
                select_parts.append("COUNT(*) AS n")
                if p.agg not in ("std", "stddev", "null_ratio"):
                    select_parts.append(f"STDDEV({p.col}) AS std")
                    # 스텝별이면 min/max도 추가
                    if group_col == "step_name":
                        select_parts.append(f"MIN({p.col}) AS min_val")
                        select_parts.append(f"MAX({p.col}) AS max_val")
        
        select_col = ", ".join(select_parts)
        order_by = order_col if len(p.trace_ids) > 1 or len(p.step_names) > 1 else ("n DESC" if p.agg == "count" else "value DESC")
        
        sql = f"""
        SELECT {select_col}
        FROM traces
        {where_sql}
        GROUP BY {group_col}
        ORDER BY {order_by}
        """
        
        if p.top_n:
            sql += f" LIMIT {int(p.top_n)}"
        return sql, params

    # 그룹이 없으면 단일 값
    if p.agg == "count":
        sql = f"SELECT COUNT(*) AS n FROM traces {where_sql}"
    else:
        select_parts = [f"{main_agg} AS value"]
        # 추가 통계 (n, std)
        if include_stats and p.col:
            select_parts.append("COUNT(*) AS n")
            if p.agg not in ("std", "stddev", "null_ratio"):
                select_parts.append(f"STDDEV({p.col}) AS std")
        select_col = ", ".join(select_parts)
        sql = f"SELECT {select_col} FROM traces {where_sql}"
    return sql, params
