"""
pytest 기반 파서 회귀 테스트
질문 타입별로 분류된 200개 테스트 케이스 실행
"""
import json
import pytest
from pathlib import Path
from typing import Dict, Any, List

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent.parent
import sys
sys.path.insert(0, str(PROJECT_ROOT))

from src.nl_parse_v2 import parse_question, Parsed


QUESTIONS_FILE = PROJECT_ROOT / "tests" / "questions.jsonl"


def load_test_cases() -> List[Dict[str, Any]]:
    """테스트 케이스 로드"""
    test_cases = []
    
    if not QUESTIONS_FILE.exists():
        pytest.skip(f"{QUESTIONS_FILE} 파일이 없습니다.")
        return test_cases
    
    with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                case = json.loads(line)
                case['_line'] = line_num
                case['_id'] = len(test_cases) + 1
                test_cases.append(case)
            except json.JSONDecodeError as e:
                pytest.skip(f"{QUESTIONS_FILE}:{line_num} JSON 파싱 오류: {e}")
    
    return test_cases


def normalize_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """딕셔너리 정규화 (None 제거, 빈 리스트 정리)"""
    if d is None:
        return {}
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
                differences.append(f"{key}: 예상={expected_val}, 실제={actual_val}")
    
    # filters 비교
    if "filters" in expected_dict:
        actual_filters = actual_dict.get("filters", {})
        expected_filters = expected_dict.get("filters", {})
        
        # filters가 문자열인 경우 (예: "date_range") 처리
        if isinstance(expected_filters, str):
            if expected_filters == "date_range":
                # date_start 또는 date_end가 있으면 통과
                if "date_start" in actual_filters or "date_end" in actual_filters:
                    pass  # 통과
                else:
                    is_match = False
                    differences.append(f"filters: 예상=date_range (date_start 또는 date_end 필요), 실제={actual_filters}")
            else:
                is_match = False
                differences.append(f"filters: 예상={expected_filters}, 실제={actual_filters}")
        else:
            # filters가 딕셔너리인 경우
            for key in expected_filters:
                actual_val = actual_filters.get(key)
                expected_val = expected_filters[key]
                
                # step_names, trace_ids는 파서에서 정렬되어 반환되므로 순서 비교 가능
                if actual_val != expected_val:
                    is_match = False
                    differences.append(f"filters.{key}: 예상={expected_val}, 실제={actual_val}")
    
    # flags 비교
    if "flags" in expected_dict:
        actual_flags = actual_dict.get("flags", {})
        expected_flags = expected_dict.get("flags", {})
        
        for key in expected_flags:
            if actual_flags.get(key) != expected_flags.get(key):
                is_match = False
                differences.append(f"flags.{key}: 예상={expected_flags[key]}, 실제={actual_flags.get(key)}")
    
    return is_match, differences


# pytest fixture로 테스트 케이스 로드
@pytest.fixture(scope="module")
def test_cases():
    """모든 테스트 케이스 로드"""
    return load_test_cases()


# 파라미터화된 테스트
@pytest.mark.parametrize("test_case", load_test_cases(), ids=lambda x: f"line{x['_line']}:{x['q'][:30]}")
def test_parse_question(test_case):
    """
    질문 파싱 테스트
    각 질문이 예상된 Parsed 객체로 변환되는지 확인
    """
    question = test_case.get("q", "")
    expected = test_case.get("expect", {})
    line_num = test_case.get("_line", 0)
    test_id = test_case.get("_id", 0)
    
    # 파싱 실행
    try:
        parsed = parse_question(question)
    except Exception as e:
        pytest.fail(f"[테스트 #{test_id}, 라인 {line_num}] '{question}' 파싱 오류: {e}")
    
    # 비교
    is_match, differences = compare_parsed(parsed, expected)
    
    if not is_match:
        error_msg = f"[테스트 #{test_id}, 라인 {line_num}] '{question}'\n"
        error_msg += f"예상: {expected}\n"
        error_msg += f"실제: {parsed.to_dict()}\n"
        if differences:
            error_msg += "차이점:\n"
            for diff in differences:
                error_msg += f"  - {diff}\n"
        pytest.fail(error_msg)


# 통계 출력 (pytest hook)
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """테스트 종료 시 통계 출력"""
    if 'test_parse_question' in terminalreporter.stats:
        passed = len(terminalreporter.stats.get('passed', []))
        failed = len(terminalreporter.stats.get('failed', []))
        total = passed + failed
        
        if total > 0:
            terminalreporter.write_sep("=", "파서 테스트 결과")
            terminalreporter.write_line(f"✅ 통과: {passed}/{total} ({passed*100//total}%)")
            if failed > 0:
                terminalreporter.write_line(f"❌ 실패: {failed}/{total} ({failed*100//total}%)")

