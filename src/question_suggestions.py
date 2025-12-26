"""
Question Suggestions: 질문 추천 및 자동완성
"""
from typing import List, Dict

# 예시 질문 템플릿
QUESTION_TEMPLATES = [
    # 단일값 질문
    ("압력 평균", "단일값"),
    ("질소 1 유량 평균", "단일값"),
    ("rf 전력 평균", "단일값"),
    ("vg11 표준편차", "단일값"),
    ("상단 온도 최대", "단일값"),
    ("하단 온도 최소", "단일값"),
    
    # 그룹별 질문
    ("스텝별 압력 평균", "그룹별"),
    ("스텝별 압력 평균 상위 5개", "그룹별"),
    ("스텝별 압력 평균 하위 3개", "그룹별"),
    ("공정별 압력 평균", "그룹별"),
    
    # 변동성/이상치 질문
    ("변동 큰 스텝", "변동성"),
    ("압력 이상치 상위 10개", "변동성"),
    ("스텝별 압력 변동 큰 상위 5개", "변동성"),
    
    # 비교 질문
    ("standard_trace_001과 standard_trace_002 압력 비교", "비교"),
    
    # 공정 지표
    ("압력 오버슈트", "공정지표"),
    ("스텝별 체류시간", "공정지표"),
    ("안정화 구간 평균", "공정지표"),
]

# 카테고리별 추천 질문
CATEGORY_QUESTIONS = {
    "압력": [
        "압력 평균",
        "스텝별 압력 평균",
        "압력 이상치 상위 10개",
        "변동 큰 스텝",
    ],
    "온도": [
        "상단 온도 평균",
        "하단 온도 평균",
        "스텝별 온도 평균",
    ],
    "유량": [
        "질소 1 유량 평균",
        "암모니아 유량 평균",
    ],
    "RF": [
        "rf 전력 평균",
        "스텝별 rf 전력 평균",
    ],
    "비교": [
        "standard_trace_001과 standard_trace_002 압력 비교",
    ],
    "공정지표": [
        "압력 오버슈트",
        "스텝별 체류시간",
    ],
}

def get_suggestions(query: str = "", limit: int = 10) -> List[Dict[str, str]]:
    """
    질문 추천 목록 반환
    
    Args:
        query: 검색어 (부분 매칭)
        limit: 반환할 최대 개수
    
    Returns:
        질문 목록: [{"question": "...", "category": "..."}, ...]
    """
    suggestions = []
    
    # 검색어가 있으면 부분 매칭
    if query:
        query_lower = query.lower()
        for q, cat in QUESTION_TEMPLATES:
            if query_lower in q.lower():
                suggestions.append({"question": q, "category": cat})
    
    # 검색어가 없거나 매칭 결과가 적으면 전체 목록 반환
    if not query or len(suggestions) < limit:
        for q, cat in QUESTION_TEMPLATES:
            if not any(s["question"] == q for s in suggestions):
                suggestions.append({"question": q, "category": cat})
    
    return suggestions[:limit]

def get_category_suggestions(category: str = None) -> List[str]:
    """
    카테고리별 질문 목록 반환
    
    Args:
        category: 카테고리명 (None이면 전체)
    
    Returns:
        질문 목록: ["질문1", "질문2", ...]
    """
    if category and category in CATEGORY_QUESTIONS:
        return CATEGORY_QUESTIONS[category]
    
    # 전체 카테고리 질문 합치기
    all_questions = []
    for questions in CATEGORY_QUESTIONS.values():
        all_questions.extend(questions)
    
    return list(set(all_questions))  # 중복 제거

def get_popular_questions(limit: int = 5) -> List[str]:
    """
    인기 질문 목록 (자주 사용되는 질문)
    
    Returns:
        질문 목록
    """
    return [
        "압력 평균",
        "스텝별 압력 평균",
        "변동 큰 스텝",
        "압력 이상치 상위 10개",
        "standard_trace_001과 standard_trace_002 압력 비교",
    ][:limit]

