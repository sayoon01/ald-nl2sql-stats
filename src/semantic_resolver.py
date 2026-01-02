"""Semantic ID → Physical Column Resolver"""
import yaml
import re
from pathlib import Path
from typing import Optional, Dict, Any

PROJECT_ROOT = Path(__file__).parent.parent
REGISTRY_FILE = PROJECT_ROOT / "semantic_registry.yaml"

# Registry 캐싱
_registry_cache: Optional[Dict[str, Any]] = None
_alias_map_cache: Optional[Dict[str, str]] = None
_physical_to_semantic_cache: Optional[Dict[str, str]] = None

def load_registry() -> Dict[str, Any]:
    """semantic_registry.yaml 로드 (캐싱)"""
    global _registry_cache
    if _registry_cache is None:
        if not REGISTRY_FILE.exists():
            raise FileNotFoundError(f"semantic_registry.yaml not found: {REGISTRY_FILE}")
        with open(REGISTRY_FILE, 'r', encoding='utf-8') as f:
            _registry_cache = yaml.safe_load(f)
    return _registry_cache

def build_alias_map() -> Dict[str, str]:
    """Alias → Semantic ID 매핑 생성 (캐싱)"""
    global _alias_map_cache
    if _alias_map_cache is None:
        registry = load_registry()
        _alias_map_cache = {}
        
        def extract_aliases(data: Dict[str, Any], prefix: str = ""):
            """중첩된 딕셔너리에서 alias 추출"""
            for key, value in data.items():
                current_path = f"{prefix}.{key}" if prefix else key
                if isinstance(value, dict):
                    if "aliases" in value:
                        # 최종 semantic ID
                        physical_cols = value.get("physical_columns", [])
                        if physical_cols:
                            for alias in value["aliases"]:
                                # 정규화된 alias (소문자, 공백 제거, 특수문자 제거)
                                normalized = re.sub(r'[^\w]', '', alias.lower())
                                if normalized not in _alias_map_cache:
                                    _alias_map_cache[normalized] = physical_cols[0]  # 첫 번째 physical column
                    else:
                        # 하위 레벨
                        extract_aliases(value, current_path)
        
        extract_aliases(registry)
    return _alias_map_cache

def build_physical_to_semantic_map() -> Dict[str, str]:
    """Physical Column → Semantic ID 경로 매핑 생성 (캐싱)"""
    global _physical_to_semantic_cache
    if _physical_to_semantic_cache is None:
        registry = load_registry()
        _physical_to_semantic_cache = {}
        
        def extract_physical_cols(data: Dict[str, Any], prefix: str = ""):
            """중첩된 딕셔너리에서 physical column과 semantic ID 경로 추출"""
            for key, value in data.items():
                current_path = f"{prefix}.{key}" if prefix else key
                if isinstance(value, dict):
                    if "physical_columns" in value:
                        # 최종 semantic ID
                        physical_cols = value.get("physical_columns", [])
                        for physical_col in physical_cols:
                            if physical_col not in _physical_to_semantic_cache:
                                _physical_to_semantic_cache[physical_col] = current_path
                    else:
                        # 하위 레벨
                        extract_physical_cols(value, current_path)
        
        extract_physical_cols(registry)
    return _physical_to_semantic_cache

def resolve_semantic_to_physical(text: str) -> Optional[str]:
    """
    자연어 텍스트에서 semantic ID를 찾아 physical column으로 변환
    
    Args:
        text: 자연어 텍스트 (예: "챔버 압력", "pressact", "압력")
    
    Returns:
        physical column 이름 (예: "pressact") 또는 None
    """
    alias_map = build_alias_map()
    
    # 정규화된 텍스트에서 매칭
    normalized = re.sub(r'[^\w]', '', text.lower())
    
    # 직접 매칭
    if normalized in alias_map:
        return alias_map[normalized]
    
    # 부분 매칭 (공백 제거 후 검색)
    for alias, physical_col in alias_map.items():
        if alias in normalized or normalized in alias:
            return physical_col
    
    return None

def get_physical_column_by_semantic_id(semantic_id: str) -> Optional[str]:
    """
    Semantic ID 경로로 physical column 찾기
    
    Args:
        semantic_id: 점으로 구분된 semantic ID (예: "pressure.chamber.act")
    
    Returns:
        physical column 이름 (예: "pressact") 또는 None
    """
    registry = load_registry()
    parts = semantic_id.split('.')
    current = registry
    
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    
    # 최종 노드에서 physical_columns 추출
    if isinstance(current, dict) and "physical_columns" in current:
        cols = current["physical_columns"]
        return cols[0] if cols else None
    
    return None

def get_semantic_id_by_physical_column(physical_col: str) -> Optional[str]:
    """
    Physical Column로 Semantic ID 경로 찾기
    
    Args:
        physical_col: physical column 이름 (예: "pressact")
    
    Returns:
        semantic ID 경로 (예: "pressure.chamber.act") 또는 None
    """
    physical_to_semantic = build_physical_to_semantic_map()
    return physical_to_semantic.get(physical_col)

def get_metadata_by_physical_column(physical_col: str) -> Optional[Dict[str, Any]]:
    """
    Physical Column로 메타데이터 (unit, normal_range, description) 찾기
    
    Args:
        physical_col: physical column 이름 (예: "pressact")
    
    Returns:
        메타데이터 딕셔너리:
        {
            "unit": "mTorr",
            "normal_range": {"min": 100, "max": 800},
            "description": "챔버 압력"
        }
        또는 None
    """
    semantic_id = get_semantic_id_by_physical_column(physical_col)
    if not semantic_id:
        return None
    
    registry = load_registry()
    parts = semantic_id.split('.')
    current = registry
    
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    
    # 최종 노드에서 메타데이터 추출
    if isinstance(current, dict):
        metadata = {}
        if "unit" in current:
            metadata["unit"] = current["unit"]
        if "scale" in current:
            metadata["scale"] = current["scale"]
        if "normal_range" in current:
            metadata["normal_range"] = current["normal_range"]
        if "range_source" in current:
            metadata["range_source"] = current["range_source"]
        if "description" in current:
            metadata["description"] = current["description"]
        elif "aliases" in current and current["aliases"]:
            # description이 없으면 첫 번째 alias를 사용
            metadata["description"] = current["aliases"][0]
        
        return metadata if metadata else None
    
    return None
