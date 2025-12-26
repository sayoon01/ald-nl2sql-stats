"""
테스트용 더미 데이터 생성 스크립트
CSV 파일이 없을 때 사용할 수 있는 샘플 데이터를 생성합니다.
"""
import duckdb
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta
import random

# 프로젝트 루트 경로 설정
PROJECT_ROOT = Path(__file__).parent.parent
OUT_DB = PROJECT_ROOT / "data_out" / "ald.duckdb"

def create_dummy_data():
    """더미 데이터 생성"""
    print("더미 데이터 생성 중...")
    
    # 데이터베이스 연결
    con = duckdb.connect(str(OUT_DB))
    
    # 샘플 데이터 생성
    trace_ids = ['standard_trace_001', 'standard_trace_002', 'standard_trace_003']
    step_names = ['STANDBY', 'B.FILL', 'B.FILL4', 'B.FILL5', 'B.UP', 'B.DOWN', 'PROCESS', 'PURGE']
    
    rows = []
    base_time = datetime(2024, 1, 1, 0, 0, 0)
    
    for trace_id in trace_ids:
        for step_idx, step_name in enumerate(step_names):
            # 각 단계마다 50-100개의 데이터 포인트 생성
            n_points = random.randint(50, 100)
            for i in range(n_points):
                timestamp = base_time + timedelta(
                    days=random.randint(0, 30),
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59),
                    seconds=random.randint(0, 59)
                )
                
                # 단계별로 다른 압력 범위 설정
                if step_name == 'STANDBY':
                    pressact = random.uniform(0.1, 0.5)
                    pressset = 0.3
                elif step_name in ['B.FILL', 'B.FILL4', 'B.FILL5']:
                    pressact = random.uniform(1.0, 5.0)
                    pressset = 3.0
                elif step_name in ['B.UP', 'B.DOWN']:
                    pressact = random.uniform(5.0, 10.0)
                    pressset = 7.5
                else:
                    pressact = random.uniform(2.0, 8.0)
                    pressset = 5.0
                
                # MFC 유량 데이터 (단계별로 다른 범위)
                if step_name in ['B.FILL', 'B.FILL4', 'B.FILL5', 'PROCESS']:
                    mfcmon_n2_1 = random.uniform(10.0, 50.0)  # 질소 유량
                    mfcmon_n2_2 = random.uniform(5.0, 30.0)   # 질소 유량 2
                    mfcmon_nh3 = random.uniform(1.0, 20.0)   # 암모니아 유량
                else:
                    mfcmon_n2_1 = random.uniform(0.0, 10.0)
                    mfcmon_n2_2 = random.uniform(0.0, 5.0)
                    mfcmon_nh3 = random.uniform(0.0, 2.0)
                
                # 온도 데이터
                tempact_c = random.uniform(20.0, 80.0)  # 중앙 온도
                tempact_u = random.uniform(25.0, 85.0)  # 상부 온도
                
                rows.append({
                    'trace_id': trace_id,
                    'step_name': step_name,
                    'timestamp': timestamp,
                    'pressact': round(pressact, 3),
                    'pressset': round(pressset, 3),
                    'vg11': round(random.uniform(0.0, 100.0), 2),
                    'vg12': round(random.uniform(0.0, 100.0), 2),
                    'vg13': round(random.uniform(0.0, 100.0), 2),
                    'apcvalvemon': round(random.uniform(0.0, 100.0), 2),
                    'apcvalveset': round(random.uniform(0.0, 100.0), 2),
                    # 추가 컬럼
                    'mfcmon_n2_1': round(mfcmon_n2_1, 1),
                    'mfcmon_n2_2': round(mfcmon_n2_2, 1),
                    'mfcmon_nh3': round(mfcmon_nh3, 1),
                    'tempact_c': round(tempact_c, 1),
                    'tempact_u': round(tempact_u, 1),
                })
    
    # DataFrame 생성
    df = pd.DataFrame(rows)
    
    # DuckDB에 테이블 생성
    con.execute("""
        CREATE OR REPLACE TABLE traces AS
        SELECT * FROM df
    """)
    
    # 분석용 뷰 생성 (모든 주요 컬럼 포함)
    con.execute("""
        CREATE OR REPLACE VIEW traces_key AS
        SELECT trace_id, step_name, timestamp, pressact, pressset, vg11, vg12, vg13,
               mfcmon_n2_1, mfcmon_n2_2, mfcmon_nh3, tempact_c, tempact_u
        FROM traces
    """)
    
    # 결과 확인
    n_rows = con.execute("SELECT COUNT(*) FROM traces").fetchone()[0]
    n_traces = con.execute("SELECT COUNT(DISTINCT trace_id) FROM traces").fetchone()[0]
    n_steps = con.execute("SELECT COUNT(DISTINCT step_name) FROM traces").fetchone()[0]
    
    print(f"\n✅ 더미 데이터 생성 완료!")
    print(f"DB: {OUT_DB}")
    print(f"총 행 수: {n_rows:,}")
    print(f"공정 ID 개수: {n_traces}")
    print(f"단계명 개수: {n_steps}")
    print(f"\n공정 ID별 데이터 개수:")
    print(con.execute("SELECT trace_id, COUNT(*) n FROM traces GROUP BY trace_id ORDER BY trace_id").df())
    
    con.close()

if __name__ == "__main__":
    # data_out 디렉토리 생성
    OUT_DB.parent.mkdir(parents=True, exist_ok=True)
    
    create_dummy_data()

