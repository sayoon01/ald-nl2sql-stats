"""
모호성 해결 규칙
- "VG11 압력" => vg11 (pressact 제거)
- "질소 유량" => mfcmon_n2_1
"""
import yaml
from pathlib import Path
from typing import Optional, List, Dict, Any

DOMAIN_ROOT = Path(__file__).parent.parent.parent / "domain"

def load_resolution_rules() -> Dict[str, Any]:
    """압력/유량 해결 규칙 로드"""
    rules_path = DOMAIN_ROOT / "rules" / "pressure_resolution.yaml"
    if not rules_path.exists():
        return {}
    
    with open(rules_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def resolve_column_ambiguity(tokens: List[str], current_column: Optional[str]) -> Optional[str]:
    """
    모호한 컬럼 선택 해결
    예: "VG11 압력" => vg11 (pressact 제거)
    예: "압력" => pressact (기본값)
    """
    rules = load_resolution_rules()
    resolution = rules.get("resolution", {})
    
    if not resolution:
        return current_column
    
    # 1. 컨텍스트 오버라이드 확인
    context_overrides = resolution.get("context_overrides", [])
    for rule in context_overrides:
        if_any_tokens = rule.get("if_any_tokens", [])
        prefer_column = rule.get("prefer_column")
        suppress_generic = rule.get("suppress_generic_pressure_token", False)
        
        # 토큰 중 하나라도 매칭되면
        if any(token.lower() in [t.lower() for t in tokens] for token in if_any_tokens):
            # pressact를 제거해야 하는 경우
            if suppress_generic and current_column == "pressact":
                return prefer_column
            # 아니면 선호 컬럼 반환
            return prefer_column
    
    # 2. 유량 채널 규칙 확인
    flow_rules = resolution.get("flow_channel_rules", [])
    for rule in flow_rules:
        if_any_tokens = rule.get("if_any_tokens", [])
        prefer_column = rule.get("prefer_column")
        
        if any(token.lower() in [t.lower() for t in tokens] for token in if_any_tokens):
            return prefer_column
    
    # 3. 기본값 적용
    defaults = resolution.get("defaults", {})
    # "압력"만 입력했을 때 기본값 사용
    if current_column is None or (current_column == "pressact" and "압력" in tokens and len(tokens) == 1):
        generic_pressure = defaults.get("generic_pressure_column")
        if generic_pressure:
            return generic_pressure
    
    return current_column


def resolve_column_from_text(text: str, current_column: Optional[str]) -> Optional[str]:
    """
    텍스트에서 컬럼 모호성 해결
    """
    # 토큰화 (간단한 공백 기준)
    tokens = text.lower().split()
    
    return resolve_column_ambiguity(tokens, current_column)

