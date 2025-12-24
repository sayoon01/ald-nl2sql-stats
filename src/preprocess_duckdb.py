import duckdb  # type: ignore
from pathlib import Path
import re

# 프로젝트 루트 경로 설정
PROJECT_ROOT = Path(__file__).parent.parent
IN_GLOB = str(Path.home() / "standard_traces" / "*.csv")  # CSV 파일 위치는 사용자 홈 디렉토리 기준
OUT_DB = PROJECT_ROOT / "data_out" / "ald.duckdb"

def slugify(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"\s+", "_", name)         # spaces -> _
    name = re.sub(r"[^a-z0-9_]+", "_", name) # .,-,() etc -> _
    name = re.sub(r"_+", "_", name).strip("_")
    if name and name[0].isdigit():
        name = "c_" + name
    return name

def main():
    con = duckdb.connect(str(OUT_DB))

    # 1) CSV 전체를 읽되, filename도 함께 붙임
    con.execute(f"""
    CREATE OR REPLACE TABLE raw AS
    SELECT
      *,
      filename AS _filename
    FROM read_csv_auto('{IN_GLOB}', filename=true);
    """)

    # 2) 컬럼명 slugify해서 새 테이블로 옮김 + trace_id + timestamp 생성
    #    - Date는 DuckDB가 DATE로 읽었고, Time은 TIME으로 읽었음 (네 DESCRIBE 결과 그대로)
    #    - timestamp = Date + Time
    desc = con.execute("DESCRIBE raw").fetchall()
    cols = [row[0] for row in desc]  # column_name list

    # Unnamed 같은 컬럼 제거
    cols = [c for c in cols if not c.lower().startswith("unnamed")]

    # 컬럼 선택 SQL 만들기
    select_parts = []
    for c in cols:
        safe = slugify(c)
        select_parts.append(f'"{c}" AS {safe}')

    # trace_id: 파일명에서 standard_trace_001 같은 stem만 뽑기
    # _filename 예: /Users/lyune/standard_traces/standard_trace_001.csv
    select_parts.append(
        "regexp_extract(_filename, '([^/]+)\\\\.csv$', 1) AS trace_id"
    )
    select_parts.append("(date + time) AS timestamp")

    con.execute(f"""
    CREATE OR REPLACE TABLE traces AS
    SELECT
      {", ".join(select_parts)}
    FROM raw;
    """)
    
    # 누락된 컬럼 추가 (YAML에 정의되어 있지만 CSV에 없는 경우)
    # 필요한 컬럼 목록 (columns.yaml 기준)
    required_cols = {
        'mfcmon_n2_1': 'DOUBLE',
        'mfcmon_n2_2': 'DOUBLE', 
        'mfcmon_nh3': 'DOUBLE',
        'tempact_c': 'DOUBLE',
        'tempact_u': 'DOUBLE',
    }
    
    # 현재 traces 테이블의 컬럼 확인
    existing_cols = set(row[0].lower() for row in con.execute("DESCRIBE traces").fetchall())
    
    # 누락된 컬럼 추가
    for col_name, col_type in required_cols.items():
        if col_name.lower() not in existing_cols:
            # NULL로 초기화 (나중에 데이터가 있으면 업데이트 가능)
            con.execute(f"ALTER TABLE traces ADD COLUMN {col_name} {col_type} DEFAULT NULL")
            print(f"  추가된 컬럼: {col_name} ({col_type})")

    # 인덱스는 DuckDB에선 선택 사항. 대신 분석용 뷰 하나 만들어둠.
    # 모든 주요 컬럼 포함 (누락된 컬럼도 포함)
    con.execute("""
    CREATE OR REPLACE VIEW traces_key AS
    SELECT trace_id, step_name, timestamp, pressact, pressset, vg11, vg12, vg13,
           apcvalvemon, apcvalveset,
           COALESCE(mfcmon_n2_1, 0.0) as mfcmon_n2_1,
           COALESCE(mfcmon_n2_2, 0.0) as mfcmon_n2_2,
           COALESCE(mfcmon_nh3, 0.0) as mfcmon_nh3,
           COALESCE(tempact_c, 0.0) as tempact_c,
           COALESCE(tempact_u, 0.0) as tempact_u
    FROM traces;
    """)

    n_rows = con.execute("SELECT COUNT(*) FROM traces").fetchone()[0]
    n_cols = con.execute("SELECT COUNT(*) FROM (DESCRIBE traces)").fetchone()[0]

    print("DB:", OUT_DB)
    print("rows:", n_rows)
    print("cols:", n_cols)
    print(con.execute("SELECT trace_id, COUNT(*) n FROM traces GROUP BY trace_id ORDER BY trace_id LIMIT 5").df())

if __name__ == "__main__":
    main()
