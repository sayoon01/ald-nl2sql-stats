"""
SQL Builder: Parsed → SQL

구조:
1. parse → (metric, group_by, filters, semantic_target, topN, compare)
2. resolver(semantic → physical)  # TODO: semantic_resolver 통합
3. 템플릿 SQL 생성

모든 쿼리는 FROM traces_dedup 사용
"""
from typing import Tuple, List, Optional
from src.nl_parse import Parsed

# 허용된 컬럼명 화이트리스트 (SQL 인젝션 방지)
# TODO: semantic_resolver로 교체 예정
# TODO: catalog_physical.json에서 자동 로드하도록 개선 필요
ALLOWED_COLS = {
    "pressact", "pressset", "vg11", "vg12", "vg13", 
    "apcvalvemon", "apcvalveset",
    "mfcmon_n2_1", "mfcmon_f_pwr", "tempact_u",  # 테스트용 추가
    "mfcmon_nh3", "tempact_l",  # semantic_resolver 지원 추가
}
ALLOWED_GROUP_BY = {"trace_id", "step_name"}

# 테이블명: 모든 쿼리는 traces_dedup 사용
TABLE_NAME = "traces_dedup"

def _build_filters(p: Parsed) -> Tuple[str, List]:
    """
    WHERE 절과 파라미터 생성
    
    Returns:
        (where_sql, params)
    """
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

def _resolve_column(col: str) -> str:
    """
    Semantic ID → Physical Column 변환
    
    TODO: semantic_resolver 통합 예정
    현재는 허용된 컬럼명만 검증
    """
    if col and col not in ALLOWED_COLS:
        raise ValueError(f"허용되지 않은 컬럼: {col}")
    return col

def _build_sql_template_time_group(
    metric: str,
    group_expr: str,
    group_col: str,
    where_sql: str,
    limit: Optional[int],
    order: Optional[str],
    agg: str,
    col: Optional[str]
) -> Tuple[str, List]:
    """시간 기반 그룹핑 SQL 템플릿 (일별, 시간별)"""
    select_parts = [f"{group_expr} AS {group_col}"]
    
    if agg == "count":
        select_parts.append("COUNT(*) AS n")
    else:
        select_parts.append(f"{metric} AS value")
        select_parts.append("COUNT(*) AS n")
        if col and agg not in ("std", "stddev", "null_ratio"):
            select_parts.append(f"STDDEV({col}) AS std")
    
    select_col = ", ".join(select_parts)
    
    sql = f"""
    SELECT {select_col}
    FROM {TABLE_NAME}
    {where_sql}
    GROUP BY {group_expr}
    ORDER BY {group_col} ASC
    """
    
    order_dir = order.upper() if order else "DESC"
    if limit:
        sql = f"SELECT * FROM ({sql}) ORDER BY {'n' if agg == 'count' else 'value'} {order_dir} LIMIT {int(limit)}"
    
    return sql, []

def _build_sql_template_group_by(
    group_col: str,
    metric: str,
    where_sql: str,
    limit: Optional[int],
    order: Optional[str],
    agg: str,
    include_stats: bool,
    col: Optional[str],
    compare_mode: bool = False
) -> Tuple[str, List]:
    """그룹별 집계 SQL 템플릿 (trace_id, step_name 등)"""
    select_parts = [group_col]
    
    if agg == "count":
        select_parts.append("COUNT(*) AS n")
    else:
        select_parts.append(f"{metric} AS value")
        if include_stats and col:
            select_parts.append("COUNT(*) AS n")
            if agg not in ("std", "stddev", "null_ratio"):
                select_parts.append(f"STDDEV({col}) AS std")
                # 스텝별이면 min/max도 추가
                if group_col == "step_name":
                    select_parts.append(f"MIN({col}) AS min_val")
                    select_parts.append(f"MAX({col}) AS max_val")
    
    select_col = ", ".join(select_parts)
    
    # 정렬 방향 결정: order가 있으면 그대로 사용, 없으면 DESC 기본값
    order_dir = order.upper() if order else "DESC"
    
    # 비교 모드면 알파벳 순, 아니면 값 기준 정렬
    if compare_mode:
        order_by = f"{group_col} ASC"
    else:
        order_col = "n" if agg == "count" else "value"
        order_by = f"{order_col} {order_dir}"
    
    sql = f"""
    SELECT {select_col}
    FROM {TABLE_NAME}
    {where_sql}
    GROUP BY {group_col}
    ORDER BY {order_by}
    """
    
    if limit:
        sql += f" LIMIT {int(limit)}"
    
    return sql, []

def _build_sql_template_single_value(
    metric: str,
    where_sql: str,
    agg: str,
    include_stats: bool,
    col: Optional[str]
) -> Tuple[str, List]:
    """단일 값 집계 SQL 템플릿 (그룹 없음)"""
    if agg == "count":
        sql = f"SELECT COUNT(*) AS n FROM {TABLE_NAME} {where_sql}"
        return sql, []
    
    select_parts = [f"{metric} AS value"]
    if include_stats and col:
        select_parts.append("COUNT(*) AS n")
        if agg not in ("std", "stddev", "null_ratio"):
            select_parts.append(f"STDDEV({col}) AS std")
    
    select_col = ", ".join(select_parts)
    sql = f"SELECT {select_col} FROM {TABLE_NAME} {where_sql}"
    return sql, []

def build_sql(p: Parsed, include_stats: bool = True) -> Tuple[str, List]:
    """
    SQL 생성 (구조화된 템플릿 기반)
    
    중요: 이 함수는 Parsed 객체만 받습니다. 문자열을 받지 않습니다.
    올바른 사용법:
        from src.nl_parse import parse_question
        from src.sql_builder import build_sql
        
        p = parse_question("압력 평균")
        sql, params = build_sql(p)
    
    구조:
    1. Filters: WHERE 절 생성
    2. Column: semantic → physical 변환 (TODO)
    3. Metric: 집계 함수 생성
    4. Template: SQL 템플릿 적용
    
    Args:
        p: Parsed 객체 (parse_question 결과). 문자열이 아닌 Parsed 객체만 허용.
        include_stats: True면 n, std 등 추가 통계 포함
    
    Returns:
        (sql, params): SQL 쿼리 문자열과 파라미터 리스트
    
    Raises:
        TypeError: p가 Parsed 객체가 아닌 경우
    """
    # 타입 검증: 문자열 체크 (가장 흔한 실수 방지)
    if isinstance(p, str):
        raise ValueError("build_sql expects Parsed object, got string. Use: p = parse_question('질문'); sql, params = build_sql(p)")
    
    # 타입 검증: Parsed 객체만 허용
    if not isinstance(p, Parsed):
        raise TypeError(
            f"build_sql()은 Parsed 객체만 받습니다. 전달된 타입: {type(p).__name__}. "
            f"사용법: p = parse_question('질문'); sql, params = build_sql(p)"
        )
    
    # 1. Filters: WHERE 절 생성
    where_sql, params = _build_filters(p)
    
    # 2. Column: 컬럼명 검증 및 변환 (TODO: semantic_resolver 통합)
    physical_col = _resolve_column(p.col) if p.col else None
    
    # 3. Metric: 집계 함수 생성
    metric = _get_agg_function(p.agg, physical_col) if physical_col else "COUNT(*)"
    
    # 4. Template: SQL 템플릿 적용
    # 시간 기반 그룹핑 (일별, 시간별)
    if p.group_by == "day":
        group_expr = "DATE(timestamp)"
        group_col = "date"
        sql, _ = _build_sql_template_time_group(
            metric, group_expr, group_col, where_sql, p.limit, p.order, p.agg, physical_col
        )
        return sql, params
    elif p.group_by == "hour":
        group_expr = "EXTRACT(HOUR FROM timestamp)"
        group_col = "hour"
        sql, _ = _build_sql_template_time_group(
            metric, group_expr, group_col, where_sql, p.limit, p.order, p.agg, physical_col
        )
        return sql, params
    
    # 여러 trace_id/step_name 비교 쿼리
    compare_mode = len(p.trace_ids) > 1 or len(p.step_names) > 1
    if len(p.trace_ids) > 1:
        group_col = "trace_id"
    elif len(p.step_names) > 1:
        group_col = "step_name"
    elif p.group_by and p.group_by in ALLOWED_GROUP_BY:
        group_col = p.group_by
    else:
        group_col = None
    
    if group_col:
        sql, _ = _build_sql_template_group_by(
            group_col, metric, where_sql, p.limit, p.order, p.agg,
            include_stats, physical_col, compare_mode
        )
        return sql, params
    
    # 그룹이 없으면 단일 값
    sql, _ = _build_sql_template_single_value(
        metric, where_sql, p.agg, include_stats, physical_col
    )
    return sql, params
