from typing import Tuple, List, Optional
from pathlib import Path
from src.nl_parse import Parsed

# 프로젝트 루트 경로 설정
PROJECT_ROOT = Path(__file__).parent.parent

# columns.yaml 로드 및 도메인키 → 실제 컬럼명 변환
def _load_schema():
    """columns.yaml 로드 (싱글톤)"""
    global _schema_cache
    if '_schema_cache' not in globals():
        from domain.schema.load_schema import load_columns_yaml
        schema_path = PROJECT_ROOT / "domain" / "schema" / "columns.yaml"
        _schema_cache = load_columns_yaml(schema_path)
    return _schema_cache

def _get_csv_column(domain_key: Optional[str]) -> Optional[str]:
    """
    도메인키 → 실제 DB 컬럼명 변환
    예: "pressact" → "pressact" (현재는 동일하지만 확장성 고려)
    """
    if not domain_key:
        return None
    
    schema = _load_schema()
    col_def = schema.columns.get(domain_key)
    if col_def and col_def.csv_columns:
        return col_def.csv_columns[0]  # 첫 번째 컬럼명 반환
    return domain_key  # 매핑이 없으면 도메인키 그대로 반환 (하위 호환성)

def _get_group_by_csv_column(group_by: Optional[str]) -> Optional[str]:
    """
    그룹핑 도메인키 → 실제 DB 컬럼명 변환
    예: "step_name" → "step_name"
    """
    if not group_by:
        return None
    
    schema = _load_schema()
    meta = schema.meta.get(group_by)
    if meta and meta.get("csv_columns"):
        return meta["csv_columns"][0]
    return group_by  # 매핑이 없으면 그대로 반환

# 허용된 컬럼명 화이트리스트 (SQL 인젝션 방지) - 도메인키 기준
ALLOWED_COLS = {"pressact", "pressset", "vg11", "vg12", "vg13", "apcvalvemon", "apcvalveset", 
                "mfcmon_n2_1", "mfcmon_n2_2", "mfcmon_nh3", "tempact_u", "tempact_c"}
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

def _get_agg_function(agg: str, csv_col: str) -> str:
    """집계 함수 SQL 생성 (실제 컬럼명 사용)"""
    if agg == "count":
        return "COUNT(*)"
    elif agg == "std" or agg == "stddev":
        return f"STDDEV({csv_col})"
    elif agg == "p50" or agg == "median":
        return f"QUANTILE_CONT({csv_col}, 0.5)"
    elif agg == "p95":
        return f"QUANTILE_CONT({csv_col}, 0.95)"
    elif agg == "p99":
        return f"QUANTILE_CONT({csv_col}, 0.99)"
    elif agg == "null_ratio":
        # 결측률: NULL 값 비율 (퍼센트)
        return f"CAST(COUNT(*) FILTER (WHERE {csv_col} IS NULL) AS DOUBLE) / COUNT(*) * 100"
    else:
        agg_fn = {"avg": "AVG", "min": "MIN", "max": "MAX"}
        fn_name = agg_fn.get(agg, "AVG")
        return f"{fn_name}({csv_col})"

def build_sql(p: Parsed, include_stats: bool = True) -> Tuple[str, List]:
    """
    SQL 생성
    include_stats: True면 n, std 등 추가 통계 포함 (기본값: True)
    """
    # 컬럼명 검증 (SQL 인젝션 방지) - 도메인키 기준
    if p.col and p.col not in ALLOWED_COLS:
        raise ValueError(f"허용되지 않은 컬럼: {p.col}")
    
    # 도메인키 → 실제 컬럼명 변환
    csv_col = _get_csv_column(p.col) if p.col else None
    
    where_sql, params = _build_where_clause(p)
    
    # 기본 집계 함수 (실제 컬럼명 사용)
    main_agg = _get_agg_function(p.agg, csv_col) if csv_col else "COUNT(*)"

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
            # 추가 통계 (n, std) - 실제 컬럼명 사용
            if include_stats and csv_col:
                select_parts.append(f"COUNT(*) AS n")
                if p.agg not in ("std", "stddev", "null_ratio"):
                    select_parts.append(f"STDDEV({csv_col}) AS std")
        
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
        # 실제 컬럼명으로 변환
        group_col = _get_group_by_csv_column("trace_id") or "trace_id"
        order_col = f"{group_col} ASC"
    elif len(p.step_names) > 1:
        # 실제 컬럼명으로 변환
        group_col = _get_group_by_csv_column("step_name") or "step_name"
        order_col = f"{group_col} ASC"
    elif p.group_by and p.group_by in ALLOWED_GROUP_BY:
        # 그룹핑도 실제 컬럼명으로 변환
        group_col = _get_group_by_csv_column(p.group_by) or p.group_by
        order_col = "value DESC" if p.agg != "count" else "n DESC"
    else:
        group_col = None
    
    if group_col:
        if p.agg == "count":
            select_parts = [group_col, "COUNT(*) AS n"]
        else:
            select_parts = [group_col, f"{main_agg} AS value"]
            # 스텝별 통계 확장: n, std, min, max 추가 - 실제 컬럼명 사용
            if include_stats and csv_col:
                select_parts.append("COUNT(*) AS n")
                if p.agg not in ("std", "stddev", "null_ratio"):
                    select_parts.append(f"STDDEV({csv_col}) AS std")
                    # 스텝별이면 min/max도 추가
                    if group_col == "step_name":
                        select_parts.append(f"MIN({csv_col}) AS min_val")
                        select_parts.append(f"MAX({csv_col}) AS max_val")
        
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
        # 추가 통계 (n, std) - 실제 컬럼명 사용
        if include_stats and csv_col:
            select_parts.append("COUNT(*) AS n")
            if p.agg not in ("std", "stddev", "null_ratio"):
                select_parts.append(f"STDDEV({csv_col}) AS std")
        select_col = ", ".join(select_parts)
        sql = f"SELECT {select_col} FROM traces {where_sql}"
    return sql, params
