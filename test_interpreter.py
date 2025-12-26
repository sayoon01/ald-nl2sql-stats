#!/usr/bin/env python3
"""
해석 레이어 통합 테스트

테스트 항목:
1. 단일 값 해석 (정상 범위 포함)
2. 그룹별 해석 (step별)
3. 정상 범위 체크 동작
4. RANGE 없는 컬럼 처리
5. UI 통합 확인
"""
import duckdb
from pathlib import Path
from src.nl_parse import parse_question
from src.sql_builder import build_sql
from src.interpreter import interpret, interpret_single, interpret_group
from src.app import make_summary

db_path = Path.home() / "ald_app" / "data_out" / "ald.duckdb"
con = duckdb.connect(str(db_path))

print("=" * 80)
print("해석 레이어 통합 테스트")
print("=" * 80)

# 테스트 케이스 정의
test_cases = [
    {
        "name": "단일 값 해석 (정상 범위 포함 - pressact)",
        "query": "압력 평균",
        "must_contain": ["챔버 압력", "Torr", "정상 범위", "표본"],
        "must_not_contain": [],
    },
    {
        "name": "단일 값 해석 (RANGE 없는 컬럼)",
        "query": "질소 1 유량 평균",
        "must_contain": ["질소", "평균", "표본"],
        "must_not_contain": ["정상 범위"],  # RANGE 없는 컬럼은 범위 체크 안 됨
    },
    {
        "name": "단일 값 해석 (최대값 - 범위 체크 안 됨)",
        "query": "압력 최대",
        "must_contain": ["최대값"],
        "must_not_contain": ["정상 범위"],  # 최대값은 범위 체크 안 됨
    },
    {
        "name": "그룹별 해석 (step별)",
        "query": "스텝별 압력 평균",
        "must_contain": ["단계명별", "총", "그룹", "값 범위", "상위 5개", "표본"],
        "must_not_contain": [],
    },
]

passed = 0
failed = 0

for i, test in enumerate(test_cases, 1):
    print(f"\n[테스트 {i}/{len(test_cases)}] {test['name']}")
    print("-" * 80)
    print(f"질문: {test['query']}")
    
    try:
        # 파싱 및 SQL 실행
        p = parse_question(test['query'])
        sql, params = build_sql(p)
        df = con.execute(sql, params).df()
        
        if df.empty:
            print("❌ FAIL: 결과가 없습니다")
            failed += 1
            continue
        
        # 해석 실행
        result = interpret(p, df, topn=5)
        print(f"\n결과:\n{result}")
        
        # 체크 실행
        all_passed = True
        
        # must_contain 체크
        for keyword in test.get('must_contain', []):
            if keyword not in result:
                all_passed = False
                print(f"  ❌ 체크 실패: '{keyword}' 문자열이 없음")
        
        # must_not_contain 체크
        for keyword in test.get('must_not_contain', []):
            if keyword in result:
                all_passed = False
                print(f"  ❌ 체크 실패: '{keyword}' 문자열이 있으면 안 됨")
        
        if all_passed:
            print("\n✅ PASS")
            passed += 1
        else:
            print("\n❌ FAIL: 일부 체크 실패")
            failed += 1
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        failed += 1

print("\n" + "=" * 80)
print("UI 통합 테스트 (make_summary)")
print("=" * 80)

ui_test_cases = [
    "압력 평균",
    "스텝별 압력 평균",
]

for q in ui_test_cases:
    print(f"\n질문: {q}")
    print("-" * 80)
    try:
        p = parse_question(q)
        sql, params = build_sql(p)
        df = con.execute(sql, params).df()
        rows = df.to_dict('records')
        
        parsed_dict = p.__dict__
        summary = make_summary(parsed_dict, rows)
        print(f"UI 요약: {summary}")
        
        # UI 요약이 자연어 형태인지 체크
        if "=" in summary and "[" in summary and "]" in summary:
            # 기계식 출력이 남아있으면 실패
            if summary.count("=") > 2:  # 일부는 정상 (예: "≈412")
                print("⚠️  WARNING: 기계식 출력 형식이 남아있을 수 있음")
        else:
            print("✅ 자연어 형태로 출력됨")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

con.close()

print("\n" + "=" * 80)
print(f"테스트 결과: {passed}개 통과, {failed}개 실패 (총 {len(test_cases)}개)")
print("=" * 80)

if failed == 0:
    print("✅ 모든 테스트 통과!")
    exit(0)
else:
    print("❌ 일부 테스트 실패")
    exit(1)

