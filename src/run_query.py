import duckdb
from pathlib import Path
from src.nl_parse import parse_question
from src.sql_builder import build_sql

DB = Path.home() / "ald_app" / "data_out" / "ald.duckdb"

def main():
    q = input("질문: ").strip()
    parsed = parse_question(q)
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
