"""
파서 테스트 프레임워크
- questions.jsonl: 테스트 질문과 예상 결과
- expected_parsed.jsonl: 예상 파싱 결과 (선택사항)
- test_parser.py: 테스트 실행 스크립트
"""
import json
import sys
from pathlib import Path
from typing import Dict, Any, List

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.nl_parse_v2 import parse_question, Parsed
QUESTIONS_FILE = PROJECT_ROOT / "tests" / "questions.jsonl"
EXPECTED_FILE = PROJECT_ROOT / "tests" / "expected_parsed.jsonl"


def load_test_cases() -> List[Dict[str, Any]]:
    """테스트 케이스 로드"""
    test_cases = []
    
    if not QUESTIONS_FILE.exists():
        print(f"⚠️  {QUESTIONS_FILE} 파일이 없습니다.")
        return test_cases
    
    with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                case = json.loads(line)
                case['_line'] = line_num
                test_cases.append(case)
            except json.JSONDecodeError as e:
                print(f"⚠️  {QUESTIONS_FILE}:{line_num} JSON 파싱 오류: {e}")
    
    return test_cases


def normalize_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """딕셔너리 정규화 (None 제거, 빈 리스트 정리)"""
    result = {}
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, dict):
            v = normalize_dict(v)
            if not v:  # 빈 딕셔너리 제거
                continue
        if isinstance(v, list) and len(v) == 0:
            continue
        result[k] = v
    return result


def compare_parsed(actual: Parsed, expected: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    파싱 결과 비교
    Returns: (일치 여부, 차이점 리스트)
    """
    actual_dict = normalize_dict(actual.to_dict())
    expected_dict = normalize_dict(expected)
    
    differences = []
    is_match = True
    
    # 필수 필드 확인
    for key in ["metric", "column", "group_by", "top_n", "analysis_type"]:
        if key in expected_dict:
            actual_val = actual_dict.get(key)
            expected_val = expected_dict.get(key)
            if actual_val != expected_val:
                is_match = False
                differences.append(f"  {key}: 예상={expected_val}, 실제={actual_val}")
    
    # filters 비교
    if "filters" in expected_dict:
        actual_filters = actual_dict.get("filters", {})
        expected_filters = expected_dict.get("filters", {})
        
        for key in expected_filters:
            actual_val = actual_filters.get(key)
            expected_val = expected_filters[key]
            
            # step_names, trace_ids는 파서에서 정렬되어 반환되므로 순서 비교 가능
            if actual_val != expected_val:
                is_match = False
                differences.append(f"  filters.{key}: 예상={expected_val}, 실제={actual_val}")
    
    # flags 비교
    if "flags" in expected_dict:
        actual_flags = actual_dict.get("flags", {})
        expected_flags = expected_dict.get("flags", {})
        
        for key in expected_flags:
            if actual_flags.get(key) != expected_flags.get(key):
                is_match = False
                differences.append(f"  flags.{key}: 예상={expected_flags[key]}, 실제={actual_flags.get(key)}")
    
    return is_match, differences


def run_tests(verbose: bool = False) -> tuple[int, int]:
    """
    테스트 실행
    Returns: (성공 개수, 전체 개수)
    """
    test_cases = load_test_cases()
    
    if not test_cases:
        print("❌ 테스트 케이스가 없습니다.")
        return 0, 0
    
    print(f"🧪 {len(test_cases)}개 테스트 케이스 실행 중...\n")
    
    passed = 0
    failed = 0
    
    for i, case in enumerate(test_cases, 1):
        question = case.get("q", "")
        expected = case.get("expect", {})
        line_num = case.get("_line", i)
        
        try:
            # 파싱 실행
            parsed = parse_question(question)
            
            # 비교
            is_match, differences = compare_parsed(parsed, expected)
            
            if is_match:
                passed += 1
                if verbose:
                    print(f"✅ [{i}/{len(test_cases)}] {question}")
                    print(f"   → {parsed.to_dict()}")
            else:
                failed += 1
                print(f"❌ [{i}/{len(test_cases)}] {question}")
                print(f"   예상: {expected}")
                print(f"   실제: {parsed.to_dict()}")
                if differences:
                    print("   차이점:")
                    for diff in differences:
                        print(diff)
                print()
        
        except Exception as e:
            failed += 1
            print(f"❌ [{i}/{len(test_cases)}] {question}")
            print(f"   오류: {e}")
            print()
    
    total = passed + failed
    print("=" * 60)
    print(f"결과: {passed}/{total} 통과 ({passed*100//total if total > 0 else 0}%)")
    print("=" * 60)
    
    return passed, total


def update_expected():
    """실제 파싱 결과를 expected_parsed.jsonl로 저장"""
    test_cases = load_test_cases()
    
    if not test_cases:
        print("❌ 테스트 케이스가 없습니다.")
        return
    
    results = []
    for case in test_cases:
        question = case.get("q", "")
        try:
            parsed = parse_question(question)
            results.append({
                "q": question,
                "parsed": parsed.to_dict()
            })
        except Exception as e:
            print(f"⚠️  '{question}' 파싱 오류: {e}")
    
    with open(EXPECTED_FILE, 'w', encoding='utf-8') as f:
        for result in results:
            f.write(json.dumps(result, ensure_ascii=False) + '\n')
    
    print(f"✅ {len(results)}개 파싱 결과를 {EXPECTED_FILE}에 저장했습니다.")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="파서 테스트 실행")
    parser.add_argument("--verbose", "-v", action="store_true", help="상세 출력")
    parser.add_argument("--update", "-u", action="store_true", help="예상 결과 업데이트")
    
    args = parser.parse_args()
    
    if args.update:
        update_expected()
    else:
        passed, total = run_tests(verbose=args.verbose)
        sys.exit(0 if passed == total else 1)

