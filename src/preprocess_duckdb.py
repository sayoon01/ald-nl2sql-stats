import duckdb  # type: ignore
from pathlib import Path
import re
import json
from collections import defaultdict

<<<<<<< HEAD
# 프로젝트 내부의 CSV 파일 사용
PROJECT_ROOT = Path(__file__).parent.parent
IN_GLOB = str(PROJECT_ROOT / "data_in" / "*.csv")
=======
# 프로젝트 루트 경로 설정
PROJECT_ROOT = Path(__file__).parent.parent
IN_GLOB = str(Path.home() / "standard_traces" / "*.csv")  # CSV 파일 위치는 사용자 홈 디렉토리 기준
>>>>>>> 378f42a2115c8718668a2287e9ab54018ecf432a
OUT_DB = PROJECT_ROOT / "data_out" / "ald.duckdb"

def slugify(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"\s+", "_", name)         # spaces -> _
    name = re.sub(r"[^a-z0-9_]+", "_", name) # .,-,() etc -> _
    name = re.sub(r"_+", "_", name).strip("_")
    if name and name[0].isdigit():
        name = "c_" + name
    return name

def _generate_catalog(con: duckdb.DuckDBPyConnection, project_root: Path) -> None:
    """컬럼 목록을 자동 분류하여 catalog_physical.json 생성"""
    catalog_file = project_root / "catalog_physical.json"
    
    # 컬럼 목록 가져오기 (traces_dedup에서)
    cols = con.execute("DESCRIBE traces_dedup").df()
    col_names = cols['column_name'].tolist()
    
    # 분류 규칙 적용
    catalog = defaultdict(list)
    
    for col in col_names:
        col_lower = col.lower()
        
        # meta (우선순위 높음)
        if any([
            col in ['trace_id', 'timestamp', 'date', 'time', 'step_id', 'step_name', 'recipe_table_name'],
            col.startswith('filename'),
            col == 'no'
        ]):
            catalog['meta'].append(col)
            continue
        
        # rf (gas보다 우선순위 높음 - f_pwr, l_pos, p_pos 관련)
        if any([
            'f_pwr' in col_lower or 'f.pwr' in col_lower,
            'l_pos' in col_lower or 'l.pos' in col_lower,
            'p_pos' in col_lower or 'p.pos' in col_lower
        ]):
            catalog['rf'].append(col)
            continue
        
        # apc
        if any([
            col in ['apcvalvemon', 'apcvalveset'],
            col.startswith('auxmon_apc')
        ]):
            catalog['apc'].append(col)
            continue
        
        # pressure
        if any([
            col.startswith('press'),
            col in ['vg11', 'vg12', 'vg13'],
            (col.startswith('auxmon_vg') and not col.startswith('auxmon_apc'))  # apc 제외
        ]):
            catalog['pressure'].append(col)
            continue
        
        # temp
        if any([
            col.startswith('tempact_'),
            col.startswith('tempset_'),
            col.startswith('heatertc_'),
            col.startswith('cascadetc_'),
            '_ht_' in col_lower or col.startswith('tempact_ht') or col.startswith('temptarg_ht') or col.startswith('power_ht') or col.startswith('o_ht_'),
            '_pr_' in col_lower or col.startswith('tempact_pr') or col.startswith('temptarg_pr'),
            col.startswith('overheat')
        ]):
            catalog['temp'].append(col)
            continue
        
        # valve
        if any([
            col.startswith('valveact_'),
            col.startswith('valveset_'),
            col.startswith('valvectrl_')
        ]):
            catalog['valve'].append(col)
            continue
        
        # gas (mfc 관련, rf 제외 - 이미 rf에서 걸렀으므로 여기선 제외할 필요 없음)
        if any([
            col.startswith('mfcmon_'),
            col.startswith('mfcinput_'),
            col.startswith('mfcramp_'),
            col.startswith('mfcrcpset_'),
            col.startswith('mfcset_')
        ]):
            catalog['gas'].append(col)
            continue
        
        # aux (auxmon_* 나머지)
        if col.startswith('auxmon_'):
            catalog['aux'].append(col)
            continue
        
        # 기타 (분류 안된 것들)
        catalog['other'].append(col)
    
    # 딕셔너리로 변환 (정렬된 순서 유지)
    result = {
        'meta': sorted(catalog['meta']),
        'pressure': sorted(catalog['pressure']),
        'temp': sorted(catalog['temp']),
        'gas': sorted(catalog['gas']),
        'apc': sorted(catalog['apc']),
        'rf': sorted(catalog['rf']),
        'valve': sorted(catalog['valve']),
        'aux': sorted(catalog['aux']),
    }
    
    # other가 있으면 추가
    if catalog['other']:
        result['other'] = sorted(catalog['other'])
    
    # JSON 파일 저장
    with open(catalog_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    total_cols = sum(len(v) for v in result.values())
    print(f"✅ catalog_physical.json 생성 완료 ({total_cols}개 컬럼, {len(result)}개 카테고리)")

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
        "regexp_extract(_filename, '([^/]+)\\.csv$', 1) AS trace_id"
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

<<<<<<< HEAD
    # 중복 제거 뷰 생성: (trace_id, timestamp) 중복 시 마지막 행 선택
    # 컬럼 목록 동적 생성 (rn 제외)
    desc = con.execute("DESCRIBE traces").fetchall()
    col_names = [row[0] for row in desc]
    col_list = ", ".join(col_names)
    
    # 시간 축 표준화: timestamp를 기본으로 사용하고, 필요시 사용할 수 있는 추가 컬럼 제공
    con.execute(f"""
    CREATE OR REPLACE VIEW traces_dedup AS
    SELECT 
        {col_list},
        -- 시간 축 표준화 컬럼 (2Hz 샘플링 기준)
        date_trunc('second', timestamp) AS time_bucket_second,
        EXTRACT(EPOCH FROM timestamp) * 1000 AS epoch_ms
    FROM (
        SELECT *,
            ROW_NUMBER() OVER (
                PARTITION BY trace_id, timestamp 
                ORDER BY filename DESC, time DESC, no DESC
            ) as rn
        FROM traces
    )
    WHERE rn = 1;
    """)
    
    # 분석용 뷰 (기존 유지)
    con.execute("""
    CREATE OR REPLACE VIEW traces_key AS
    SELECT trace_id, step_name, timestamp, pressact, pressset, vg11, vg12, vg13
    FROM traces_dedup;
=======
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
>>>>>>> 378f42a2115c8718668a2287e9ab54018ecf432a
    """)

    n_rows = con.execute("SELECT COUNT(*) FROM traces_dedup").fetchone()[0]
    n_cols = con.execute("SELECT COUNT(*) FROM (DESCRIBE traces)").fetchone()[0]

    # 데이터 무결성 검증
    null_check = con.execute("""
        SELECT COUNT(*) as null_count
        FROM traces
        WHERE trace_id IS NULL OR trace_id = ''
    """).fetchone()[0]
    
    if null_check > 0:
        raise ValueError(f"데이터 무결성 오류: trace_id가 비어있는 행이 {null_check}개 있습니다. 전처리를 다시 확인하세요.")

    # 중복 제거 뷰 검증
    dedup_rows = con.execute("SELECT COUNT(*) FROM traces_dedup").fetchone()[0]
    dedup_check = con.execute("""
        SELECT COUNT(*) as duplicates
        FROM (
            SELECT trace_id, timestamp, COUNT(*) as cnt
            FROM traces_dedup
            GROUP BY trace_id, timestamp
            HAVING COUNT(*) > 1
        )
    """).fetchone()[0]
    
    print("DB:", OUT_DB)
    print("rows (original):", n_rows)
    print("rows (dedup):", dedup_rows)
    print("cols:", n_cols)
    print("✅ 데이터 무결성 검증 통과")
    print(f"✅ 중복 제거 완료 (중복: {n_rows - dedup_rows}개, 남은 중복: {dedup_check}개)")
    print(con.execute("SELECT trace_id, COUNT(*) n FROM traces_dedup GROUP BY trace_id ORDER BY trace_id LIMIT 5").df())
    
    # catalog_physical.json 생성
    _generate_catalog(con, PROJECT_ROOT)
    
    con.close()

if __name__ == "__main__":
    main()
