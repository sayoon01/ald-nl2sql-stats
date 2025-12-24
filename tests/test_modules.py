"""
각 모듈별 단위 테스트
프로젝트의 각 컴포넌트가 독립적으로 잘 작동하는지 확인
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import duckdb
from src.nl_parse_v2 import parse_question, Parsed
from src.sql_builder import build_sql
from src.process_metrics import (
    build_stable_avg_sql,
    build_overshoot_sql,
    build_dwell_time_sql,
    build_outlier_detection_sql,
    build_trace_compare_sql,
)
from src.charts.renderer import render_chart
from src.services.summary import make_summary
from domain.rules.normalization import normalize

# 테스트용 DB 경로
DB = PROJECT_ROOT / "data_out" / "ald.duckdb"


def test_parser():
    """파서 모듈 테스트"""
    print("\n=== 1. 파서 모듈 테스트 ===")
    
    tests = [
        "압력 평균",
        "공정별 압력 평균 top5",
        "trace1 trace2 압력 비교",
        "B.FILL 스텝 vg11 평균",
    ]
    
    for q in tests:
        try:
            parsed = parse_question(q)
            print(f"✅ '{q}'")
            print(f"   -> column: {parsed.column}, metric: {parsed.metric}, analysis_type: {parsed.analysis_type}")
        except Exception as e:
            print(f"❌ '{q}': {e}")


def test_sql_builder():
    """SQL 빌더 모듈 테스트"""
    print("\n=== 2. SQL 빌더 모듈 테스트 ===")
    
    # 간단한 Parsed 객체 생성
    parsed = Parsed(
        metric="avg",
        column="pressact",
        group_by=None,
        filters={},
        top_n=None,
        analysis_type="ranking",
        flags={}
    )
    
    try:
        sql, params = build_sql(parsed)
        print(f"✅ 기본 SQL 빌드")
        print(f"   SQL: {sql[:100]}...")
        print(f"   Params: {params}")
    except Exception as e:
        print(f"❌ SQL 빌드 실패: {e}")
    
    # group_by 테스트
    parsed_group = Parsed(
        metric="avg",
        column="pressact",
        group_by="trace_id",
        filters={},
        top_n=5,
        analysis_type="ranking",
        flags={}
    )
    
    try:
        sql, params = build_sql(parsed_group)
        print(f"✅ Group by SQL 빌드")
        print(f"   SQL: {sql[:100]}...")
    except Exception as e:
        print(f"❌ Group by SQL 빌드 실패: {e}")


def test_query_execution():
    """쿼리 실행 모듈 테스트"""
    print("\n=== 3. 쿼리 실행 테스트 ===")
    
    if not DB.exists():
        print(f"⚠️  DB 파일이 없습니다: {DB}")
        print("   preprocess_duckdb.py를 먼저 실행하세요")
        return
    
    try:
        con = duckdb.connect(str(DB))
        
        # 간단한 쿼리 테스트
        result = con.execute("SELECT COUNT(*) as n FROM traces").fetchone()
        print(f"✅ DB 연결 성공")
        print(f"   총 레코드 수: {result[0]}")
        
        # 파싱 + SQL 빌드 + 실행 파이프라인 테스트
        parsed = parse_question("압력 평균")
        sql, params = build_sql(parsed)
        df = con.execute(sql, params).df()
        print(f"✅ 파이프라인 테스트 성공")
        print(f"   결과 행 수: {len(df)}")
        
        con.close()
    except Exception as e:
        print(f"❌ 쿼리 실행 실패: {e}")


def test_process_metrics():
    """공정 지표 모듈 테스트"""
    print("\n=== 4. 공정 지표 모듈 테스트 ===")
    
    # 이상치 탐지
    parsed_outlier = Parsed(
        metric="avg",
        column="pressact",
        filters={},
        flags={"is_outlier": True},
        analysis_type="stability"
    )
    
    try:
        sql, params = build_outlier_detection_sql(parsed_outlier)
        print(f"✅ 이상치 탐지 SQL")
        print(f"   SQL: {sql[:100]}...")
    except Exception as e:
        print(f"❌ 이상치 탐지 실패: {e}")
    
    # Trace 비교
    parsed_compare = Parsed(
        metric="avg",
        column="pressact",
        filters={"trace_ids": ["standard_trace_001", "standard_trace_002"]},
        flags={"is_trace_compare": True},
        analysis_type="comparison"
    )
    
    try:
        sql, params = build_trace_compare_sql(parsed_compare)
        print(f"✅ Trace 비교 SQL")
        print(f"   SQL: {sql[:100]}...")
    except Exception as e:
        print(f"❌ Trace 비교 실패: {e}")


def test_chart_rendering():
    """차트 렌더링 모듈 테스트"""
    print("\n=== 5. 차트 렌더링 모듈 테스트 ===")
    
    if not DB.exists():
        print(f"⚠️  DB 파일이 없습니다: {DB}")
        return
    
    try:
        con = duckdb.connect(str(DB))
        
        # 샘플 데이터 생성
        import pandas as pd
        sample_data = pd.DataFrame({
            'trace_id': ['trace1', 'trace2', 'trace3'],
            'value': [10.5, 20.3, 15.7]
        })
        
        parsed = Parsed(
            metric="avg",
            column="pressact",
            group_by="trace_id",
            analysis_type="group_profile"
        )
        
        # 차트 렌더링 테스트
        chart_bytes = render_chart(parsed, sample_data)
        print(f"✅ 차트 렌더링 성공")
        print(f"   차트 크기: {len(chart_bytes)} bytes")
        
        con.close()
    except Exception as e:
        print(f"❌ 차트 렌더링 실패: {e}")


def test_summary():
    """요약 생성 모듈 테스트"""
    print("\n=== 6. 요약 생성 모듈 테스트 ===")
    
    import pandas as pd
    sample_data = pd.DataFrame({
        'value': [10.5, 20.3, 15.7, 12.1, 18.9]
    })
    
    parsed = Parsed(
        metric="avg",
        column="pressact",
        analysis_type="ranking"
    )
    
    try:
        summary = make_summary(parsed, sample_data)
        print(f"✅ 요약 생성 성공")
        print(f"   요약: {summary}")
    except Exception as e:
        print(f"❌ 요약 생성 실패: {e}")


def test_normalization():
    """정규화 모듈 테스트"""
    print("\n=== 7. 정규화 모듈 테스트 ===")
    
    tests = [
        "압력 평균",
        "암모니아가스 유량",
        "스텝별 pressact 평균 top10",
    ]
    
    for q in tests:
        try:
            norm = normalize(q)
            print(f"✅ '{q}'")
            print(f"   -> '{norm.text}'")
        except Exception as e:
            print(f"❌ '{q}': {e}")


def main():
    """모든 모듈 테스트 실행"""
    print("=" * 60)
    print("모듈별 단위 테스트")
    print("=" * 60)
    
    test_parser()
    test_sql_builder()
    test_query_execution()
    test_process_metrics()
    test_chart_rendering()
    test_summary()
    test_normalization()
    
    print("\n" + "=" * 60)
    print("테스트 완료")
    print("=" * 60)


if __name__ == "__main__":
    main()

