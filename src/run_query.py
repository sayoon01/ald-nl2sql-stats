import duckdb  # type: ignore
from pathlib import Path
from src.nl_parse import parse_question
from src.sql_builder import build_sql
from src.process_metrics import (
    build_stable_avg_sql,
    build_overshoot_sql,
    build_dwell_time_sql,
    build_outlier_detection_sql,
    build_trace_compare_sql,
)

# 프로젝트 루트 기준 경로
PROJECT_ROOT = Path(__file__).parent.parent
DB = PROJECT_ROOT / "data_out" / "ald.duckdb"

def main():
    q = input("질문: ").strip()
    parsed = parse_question(q)
    
    # 공정 친화 지표 또는 이상치 탐지 처리
    if parsed.is_trace_compare:
        sql, params = build_trace_compare_sql(parsed)
    elif parsed.is_overshoot:
        sql, params = build_overshoot_sql(parsed)
    elif parsed.is_outlier:
        sql, params = build_outlier_detection_sql(parsed)
    elif parsed.is_dwell_time:
        sql, params = build_dwell_time_sql(parsed)
    elif parsed.is_stable_avg:
        sql, params = build_stable_avg_sql(parsed)
    else:
        sql, params = build_sql(parsed)

    con = duckdb.connect(str(DB))
    df = con.execute(sql, params).df()

    print("\n[PARSED]")
    print(parsed)
    print("\n[SQL]")
    print(sql.strip())
    print("\n[RESULT]")
    print(df)

if __name__ == "__main__":
    main()
