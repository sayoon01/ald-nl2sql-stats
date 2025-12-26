#!/usr/bin/env python3
"""
테이블 구조 확인 스크립트
DB에 실제로 어떤 컬럼들이 있는지, YAML과 일치하는지 확인
"""
import sys
from pathlib import Path

# 프로젝트 루트를 경로에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import duckdb
from domain.schema.load_schema import load_columns_yaml

def check_table_structure():
    """테이블 구조 확인"""
    db = Path('data_out/ald.duckdb')
    
    if not db.exists():
        print(f"❌ DB 파일 없음: {db.absolute()}")
        return
    
    con = duckdb.connect(str(db))
    
    print("=" * 70)
    print("테이블 구조 확인")
    print("=" * 70)
    
    # 1. DESCRIBE로 구조 확인
    print("\n1. DESCRIBE traces 결과:")
    print("-" * 70)
    columns = con.execute('DESCRIBE traces').df()
    for idx, row in columns.iterrows():
        print(f"{idx+1:2d}. {row['column_name']:20s} {row['column_type']:15s}")
    print(f"\n총 {len(columns)}개 컬럼")
    
    # 2. DB 컬럼 vs YAML 컬럼 비교
    print("\n2. DB vs YAML 컬럼 비교:")
    print("-" * 70)
    
    db_columns = set(columns['column_name'].str.lower())
    
    schema = load_columns_yaml(Path('domain/schema/columns.yaml'))
    yaml_columns = set()
    yaml_column_map = {}  # csv_col -> domain_key
    
    for col_key, col_def in schema.columns.items():
        for csv_col in col_def.csv_columns:
            yaml_columns.add(csv_col.lower())
            yaml_column_map[csv_col.lower()] = col_key
    
    print(f"DB 컬럼 수: {len(db_columns)}")
    print(f"YAML 컬럼 수: {len(yaml_columns)}")
    
    # DB에만 있는 컬럼 (메타데이터 컬럼)
    only_db = db_columns - yaml_columns
    if only_db:
        print(f"\n📋 DB에만 있는 컬럼 ({len(only_db)}개) - 메타데이터:")
        for col in sorted(only_db):
            print(f"   ✅ {col} (필터/그룹핑용)")
    
    # YAML에만 있는 컬럼 (DB에 없는 컬럼)
    only_yaml = yaml_columns - db_columns
    if only_yaml:
        print(f"\n⚠️  YAML에만 있는 컬럼 ({len(only_yaml)}개) - DB에 없음:")
        for col in sorted(only_yaml):
            domain_key = yaml_column_map.get(col, '?')
            col_def = schema.columns.get(domain_key)
            domain_name = col_def.domain_name if col_def else '?'
            print(f"   ❌ {col:20s} (도메인키: {domain_key}, 이름: {domain_name})")
        print("\n   → 이 컬럼들은 질문할 수 없습니다 (DB에 데이터가 없음)")
    
    # 일치하는 컬럼
    matched = db_columns & yaml_columns
    print(f"\n✅ 질문 가능한 컬럼 ({len(matched)}개):")
    for col in sorted(matched):
        domain_key = yaml_column_map.get(col, '?')
        col_def = schema.columns.get(domain_key)
        domain_name = col_def.domain_name if col_def else '?'
        aliases = col_def.aliases[:3] if col_def else []
        print(f"   • {col:20s} -> {domain_name} (예: {', '.join(aliases[:2])})")
    
    # 3. 샘플 데이터
    print("\n3. 샘플 데이터 (각 컬럼의 실제 값):")
    print("-" * 70)
    sample = con.execute('SELECT * FROM traces LIMIT 3').df()
    for col in sample.columns:
        non_null_count = sample[col].notna().sum()
        values = sample[col].tolist()[:3]
        print(f"{col:20s} -> {values} (NULL: {3-non_null_count}개)")
    
    # 4. 통계 정보
    print("\n4. 컬럼별 통계 (DOUBLE 타입만):")
    print("-" * 70)
    numeric_cols = columns[columns['column_type'] == 'DOUBLE']['column_name']
    for col in numeric_cols:
        stats = con.execute(f'''
            SELECT 
                COUNT(*) as n,
                COUNT(DISTINCT {col}) as unique_vals,
                MIN({col}) as min_val,
                MAX({col}) as max_val,
                AVG({col}) as avg_val
            FROM traces
            WHERE {col} IS NOT NULL
        ''').fetchone()
        if stats[0] > 0:
            print(f"{col:20s} -> n={stats[0]:,}, unique={stats[1]:,}, "
                  f"range=[{stats[2]:.2f}, {stats[3]:.2f}], avg={stats[4]:.2f}")
    
    con.close()
    
    print("\n" + "=" * 70)
    print("확인 완료")
    print("=" * 70)

if __name__ == "__main__":
    check_table_structure()

