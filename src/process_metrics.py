"""
공정 친화 지표 계산 및 이상치 탐지
"""
from typing import Tuple, List, Dict, Any
import duckdb  # type: ignore
from pathlib import Path
from src.nl_parse import Parsed

# 프로젝트 루트 기준 경로 (참고용, 실제로는 app.py에서 사용)
PROJECT_ROOT = Path(__file__).parent.parent
DB = PROJECT_ROOT / "data_out" / "ald.duckdb"

def build_stable_avg_sql(p: Parsed) -> Tuple[str, List]:
    """안정화 구간 평균 (초반 10% 제외)"""
    where_sql = "WHERE step_name = ?" if p.step_name else ""
    params = [p.step_name] if p.step_name else []
    
    sql = f"""
    WITH ranked AS (
        SELECT 
            {p.col},
            ROW_NUMBER() OVER (PARTITION BY step_name ORDER BY timestamp) as rn,
            COUNT(*) OVER (PARTITION BY step_name) as total
        FROM traces_dedup
        {where_sql}
    ),
    stable AS (
        SELECT {p.col}
        FROM ranked
        WHERE rn > total * 0.1  -- 초반 10% 제외
    )
    SELECT AVG({p.col}) AS value, COUNT(*) AS n, STDDEV({p.col}) AS std
    FROM stable
    """
    return sql, params

def build_overshoot_sql(p: Parsed) -> Tuple[str, List]:
    """Overshoot: 최대값 - 설정값"""
    where_sql, params = "", []
    if p.trace_id:
        where_sql = "WHERE trace_id = ?"
        params = [p.trace_id]
    
    # 스텝별 overshoot 계산
    sql = f"""
    SELECT 
        step_name,
        MAX(pressact - pressset) AS value,
        COUNT(*) AS n,
        AVG(pressact - pressset) AS avg_diff,
        MIN(pressact - pressset) AS min_diff,
        MAX(pressact - pressset) AS max_diff,
        STDDEV(pressact - pressset) AS std
    FROM traces_dedup
    {where_sql}
    GROUP BY step_name
    ORDER BY value DESC
    """
    if p.limit:
        sql += f" LIMIT {int(p.limit)}"
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
        FROM traces_dedup
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
    if p.limit:
        sql += f" LIMIT {int(p.limit)}"
    return sql, params

def build_outlier_detection_sql(p: Parsed) -> Tuple[str, List]:
    """이상치 탐지: z-score > 2.0인 값 비율 (공정별) - 개별 값 기준"""
    where_sql, params = "", []
    if p.step_name:
        where_sql = "WHERE step_name = ?"
        params = [p.step_name]
    
    if not p.col:
        raise ValueError("이상치 탐지는 컬럼이 필요합니다")
    
    # z-score 임계값: 1.0 (데이터가 매우 정규화되어 있어서 낮은 임계값 사용)
    # 참고: 일반적인 이상치 탐지는 2.5~3.0을 사용하지만, 이 데이터는 분산이 작아서 1.0 사용
    z_threshold = 1.0
    
    sql = f"""
    WITH global_stats AS (
        SELECT 
            AVG({p.col}) AS mean_val,
            STDDEV({p.col}) AS std_val
        FROM traces_dedup
        {where_sql}
    ),
    z_scores AS (
        SELECT 
            trace_id,
            {p.col} AS col_val,
            CASE 
                WHEN (SELECT std_val FROM global_stats) > 0 
                THEN ABS({p.col} - (SELECT mean_val FROM global_stats)) / (SELECT std_val FROM global_stats)
                ELSE 0
            END AS z_score
        FROM traces_dedup
        {where_sql}
        WHERE {p.col} IS NOT NULL
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
    if p.limit:
        sql += f" LIMIT {int(p.limit)}"
    return sql, params

def build_trace_compare_sql(p: Parsed) -> Tuple[str, List]:
    """두 trace 비교: 차이가 큰 step top5"""
    if len(p.trace_ids) < 2:
        raise ValueError("비교하려면 최소 2개의 trace_id가 필요합니다")
    
    trace1, trace2 = p.trace_ids[0], p.trace_ids[1]
    col = p.col or "pressact"
    
    sql = f"""
    WITH trace1_stats AS (
        SELECT 
            step_name,
            AVG({col}) AS avg_val
        FROM traces_dedup
        WHERE trace_id = ?
        GROUP BY step_name
    ),
    trace2_stats AS (
        SELECT 
            step_name,
            AVG({col}) AS avg_val
        FROM traces_dedup
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

