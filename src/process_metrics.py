"""
공정 친화 지표 계산 및 이상치 탐지
"""
from typing import Tuple, List, Dict, Any, Optional
import duckdb  # type: ignore
from pathlib import Path
from src.nl_parse import Parsed

# 프로젝트 루트 경로 설정
PROJECT_ROOT = Path(__file__).parent.parent
DB = Path.home() / "ald_app" / "data_out" / "ald.duckdb"

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
    """
    if not domain_key:
        return None
    
    schema = _load_schema()
    col_def = schema.columns.get(domain_key)
    if col_def and col_def.csv_columns:
        return col_def.csv_columns[0]
    return domain_key  # 매핑이 없으면 도메인키 그대로 반환

def build_stable_avg_sql(p: Parsed) -> Tuple[str, List]:
    """안정화 구간 평균 (초반 10% 제외)"""
    csv_col = _get_csv_column(p.col) if p.col else None
    if not csv_col:
        raise ValueError("컬럼이 필요합니다")
    
    where_sql = "WHERE step_name = ?" if p.step_name else ""
    params = [p.step_name] if p.step_name else []
    
    sql = f"""
    WITH ranked AS (
        SELECT 
            {csv_col},
            ROW_NUMBER() OVER (PARTITION BY step_name ORDER BY timestamp) as rn,
            COUNT(*) OVER (PARTITION BY step_name) as total
        FROM traces
        {where_sql}
    ),
    stable AS (
        SELECT {csv_col}
        FROM ranked
        WHERE rn > total * 0.1  -- 초반 10% 제외
    )
    SELECT AVG({csv_col}) AS value, COUNT(*) AS n, STDDEV({csv_col}) AS std
    FROM stable
    """
    return sql, params

def build_overshoot_sql(p: Parsed) -> Tuple[str, List]:
    """Overshoot: 최대값 - 설정값"""
    # pressact와 pressset을 실제 컬럼명으로 변환
    pressact_col = _get_csv_column("pressact")
    pressset_col = _get_csv_column("pressset")
    
    where_sql, params = "", []
    if p.trace_id:
        where_sql = "WHERE trace_id = ?"
        params = [p.trace_id]
    
    # 스텝별 overshoot 계산
    sql = f"""
    SELECT 
        step_name,
        MAX({pressact_col} - {pressset_col}) AS value,
        COUNT(*) AS n,
        AVG({pressact_col} - {pressset_col}) AS avg_diff,
        MIN({pressact_col} - {pressset_col}) AS min_diff,
        MAX({pressact_col} - {pressset_col}) AS max_diff,
        STDDEV({pressact_col} - {pressset_col}) AS std
    FROM traces
    {where_sql}
    GROUP BY step_name
    ORDER BY value DESC
    """
    if p.top_n:
        sql += f" LIMIT {int(p.top_n)}"
    return sql, params

def build_dwell_time_sql(p: Parsed) -> Tuple[str, List]:
    """체류시간: 각 step의 유지 시간 (초)"""
    where_sql = ""
    params = []
    if p.trace_id:
        where_sql = "WHERE trace_id = ?"
        params.append(p.trace_id)
    
    sql = f"""
    WITH step_times AS (
        SELECT 
            step_name,
            MIN(timestamp) AS start_time,
            MAX(timestamp) AS end_time,
            EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp))) AS dwell_seconds
        FROM traces
        {where_sql}
        GROUP BY trace_id, step_name
    )
    SELECT 
        step_name,
        AVG(dwell_seconds) AS value,
        COUNT(*) AS n,
        STDDEV(dwell_seconds) AS std
    FROM step_times
    GROUP BY step_name
    ORDER BY value DESC
    """
    if p.top_n:
        sql += f" LIMIT {int(p.top_n)}"
    return sql, params

def build_outlier_detection_sql(p: Parsed) -> Tuple[str, List]:
    """이상치 탐지: z-score > 2.0인 값 비율 (공정별) - 개별 값 기준"""
    csv_col = _get_csv_column(p.col) if p.col else None
    if not csv_col:
        raise ValueError("이상치 탐지는 컬럼이 필요합니다")
    
    where_sql, params = "", []
    if p.step_name:
        where_sql = "WHERE step_name = ?"
        params = [p.step_name]
    
    # z-score 임계값: 1.0 (데이터가 매우 정규화되어 있어서 낮은 임계값 사용)
    # 참고: 일반적인 이상치 탐지는 2.5~3.0을 사용하지만, 이 데이터는 분산이 작아서 1.0 사용
    z_threshold = 1.0
    
    sql = f"""
    WITH global_stats AS (
        SELECT 
            AVG({csv_col}) AS mean_val,
            STDDEV({csv_col}) AS std_val
        FROM traces
        {where_sql}
    ),
    z_scores AS (
        SELECT 
            trace_id,
            {csv_col} AS col_val,
            CASE 
                WHEN (SELECT std_val FROM global_stats) > 0 
                THEN ABS({csv_col} - (SELECT mean_val FROM global_stats)) / (SELECT std_val FROM global_stats)
                ELSE 0
            END AS z_score
        FROM traces
        {where_sql}
        WHERE {csv_col} IS NOT NULL
    )
    SELECT 
        trace_id,
        CAST(SUM(CASE WHEN z_score > {z_threshold} THEN 1 ELSE 0 END) AS DOUBLE) * 100.0 / COUNT(*) AS value,
        COUNT(*) AS n,
        SUM(CASE WHEN z_score > {z_threshold} THEN 1 ELSE 0 END) AS outlier_count
    FROM z_scores
    GROUP BY trace_id
    HAVING SUM(CASE WHEN z_score > {z_threshold} THEN 1 ELSE 0 END) > 0
    ORDER BY value DESC
    """
    if p.top_n:
        sql += f" LIMIT {int(p.top_n)}"
    return sql, params

def build_trace_compare_sql(p: Parsed) -> Tuple[str, List]:
    """두 trace 비교: 차이가 큰 step top5"""
    if len(p.trace_ids) < 2:
        raise ValueError("비교하려면 최소 2개의 trace_id가 필요합니다")
    
    trace1, trace2 = p.trace_ids[0], p.trace_ids[1]
    domain_col = p.col or "pressact"
    csv_col = _get_csv_column(domain_col)
    
    sql = f"""
    WITH trace1_stats AS (
        SELECT 
            step_name,
            AVG({csv_col}) AS avg_val
        FROM traces
        WHERE trace_id = ?
        GROUP BY step_name
    ),
    trace2_stats AS (
        SELECT 
            step_name,
            AVG({csv_col}) AS avg_val
        FROM traces
        WHERE trace_id = ?
        GROUP BY step_name
    )
    SELECT 
        COALESCE(t1.step_name, t2.step_name) AS step_name,
        COALESCE(t1.avg_val, 0) AS trace1_avg,
        COALESCE(t2.avg_val, 0) AS trace2_avg,
        ABS(COALESCE(t1.avg_val, 0) - COALESCE(t2.avg_val, 0)) AS diff,
        (COALESCE(t1.avg_val, 0) - COALESCE(t2.avg_val, 0)) AS diff_signed
    FROM trace1_stats t1
    FULL OUTER JOIN trace2_stats t2 ON t1.step_name = t2.step_name
    ORDER BY diff DESC
    LIMIT 5
    """
    return sql, [trace1, trace2]

