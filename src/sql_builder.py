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

def build_sql(p: Parsed) -> Tuple[str, List]:
    # 컬럼명 검증 (SQL 인젝션 방지)
    if p.col and p.col not in ALLOWED_COLS:
        raise ValueError(f"허용되지 않은 컬럼: {p.col}")
    
    where_sql, params = _build_where_clause(p)
    
    # 집계 함수 매핑
    agg_fn = {"avg": "AVG", "min": "MIN", "max": "MAX", "count": "COUNT"}
    fn = agg_fn.get(p.agg)

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
            select_col = f"{group_expr} AS {group_col}, COUNT(*) AS n"
            order_col = group_col
        else:
            select_col = f"{group_expr} AS {group_col}, {fn}({p.col}) AS value"
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
            select_col = f"{group_col}, COUNT(*) AS n"
            order_by = order_col if len(p.trace_ids) > 1 or len(p.step_names) > 1 else "n DESC"
        else:
            select_col = f"{group_col}, {fn}({p.col}) AS value"
            order_by = order_col if len(p.trace_ids) > 1 or len(p.step_names) > 1 else "value DESC"
        
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
        sql = f"SELECT {fn}({p.col}) AS value FROM traces {where_sql}"
    return sql, params
