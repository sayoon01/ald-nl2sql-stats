"""
질문 정규화 규칙
- 소문자 변환
- 동의어 치환
- 패턴 정규화
"""
import re
from dataclasses import dataclass
from typing import Dict, List, Optional
import yaml
from pathlib import Path

# 프로젝트 루트
DOMAIN_ROOT = Path(__file__).parent.parent.parent / "domain"

def load_synonyms(file_path: Path) -> Dict[str, List[str]]:
    """YAML 파일에서 동의어 사전 로드"""
    if not file_path.exists():
        return {}
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}

def load_patterns(file_path: Path) -> Dict:
    """패턴 정의 로드"""
    if not file_path.exists():
        return {}
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}

class Normalizer:
    """질문 정규화 클래스"""
    
    def __init__(self):
        # YAML 기반 스키마 로드 (columns.yaml 우선)
        try:
            from domain.schema.load_schema import load_columns_yaml
            schema_path = DOMAIN_ROOT / "schema" / "columns.yaml"
            if schema_path.exists():
                self.schema = load_columns_yaml(schema_path)
                # 스키마에서 aliases 추출
                self.column_synonyms = {
                    key: col_def.aliases 
                    for key, col_def in self.schema.columns.items()
                }
            else:
                # Fallback: 기존 YAML 파일 사용
                self.column_synonyms = load_synonyms(DOMAIN_ROOT / "synonyms" / "columns.yaml")
                self.schema = None
        except Exception as e:
            # Fallback: 기존 방식
            self.column_synonyms = load_synonyms(DOMAIN_ROOT / "synonyms" / "columns.yaml")
            self.schema = None
        
        # 기존 동의어 사전 로드 (metrics, groups)
        self.metric_synonyms = load_synonyms(DOMAIN_ROOT / "synonyms" / "metrics.yaml")
        self.group_synonyms = load_synonyms(DOMAIN_ROOT / "synonyms" / "groups.yaml")
        self.patterns = load_patterns(DOMAIN_ROOT / "synonyms" / "patterns.yaml")
        
        # 동의어 치환 맵 생성 (역방향: 동의어 -> 표준명)
        self._build_synonym_map()
        self._build_pattern_regex()
    
    def _build_synonym_map(self):
        """동의어 -> 표준명 맵 생성"""
        self.synonym_to_standard = {}
        
        # 컬럼 동의어
        for std_name, synonyms in self.column_synonyms.items():
            for synonym in synonyms:
                self.synonym_to_standard[synonym.lower()] = ("column", std_name)
        
        # 지표 동의어
        for std_name, synonyms in self.metric_synonyms.items():
            for synonym in synonyms:
                self.synonym_to_standard[synonym.lower()] = ("metric", std_name)
        
        # 그룹 동의어
        for std_name, synonyms in self.group_synonyms.items():
            for synonym in synonyms:
                self.synonym_to_standard[synonym.lower()] = ("group", std_name)
    
    def _build_pattern_regex(self):
        """패턴 정규식 컴파일"""
        self.compiled_patterns = {}
        
        if not self.patterns:
            return
        
        for pattern_name, pattern_def in self.patterns.items():
            if "patterns" not in pattern_def:
                continue
            
            compiled = []
            for pat_str in pattern_def["patterns"]:
                try:
                    compiled.append(re.compile(pat_str, re.IGNORECASE))
                except:
                    pass
            
            self.compiled_patterns[pattern_name] = {
                "regexes": compiled,
                "normalize": pattern_def.get("normalize", "")
            }
    
    def _replace_synonyms_internal(self, text: str) -> str:
        """
        내부 동의어 치환 메서드 (normalize()에서 사용)
        사용자 제공 코드의 로직 활용: 단순 replace로 더 정확한 매칭
        """
        # 동의어를 길이 순으로 정렬 (긴 것 우선) - 부분 매칭 방지
        sorted_synonyms = sorted(
            self.synonym_to_standard.items(),
            key=lambda x: len(x[0]),
            reverse=True
        )
        
        for synonym, (category, std_name) in sorted_synonyms:
            # 단순 replace 사용 (사용자 코드 방식)
            # 소문자로 변환된 텍스트에서 소문자 동의어로 매칭
            synonym_lower = synonym.lower()
            if synonym_lower in text:
                # 그룹핑은 "group:" 접두사 추가
                if category == "group":
                    replacement = f"group:{std_name}"
                else:
                    replacement = std_name
                # 단순 replace (긴 것부터 매칭하므로 부분 매칭 문제 최소화)
                text = text.replace(synonym_lower, replacement)
        
        return text
    
    def normalize(self, text: str) -> str:
        """
        질문 정규화 (하위 호환성용, Normalized 객체 반환 권장)
        """
        normalized = self._replace_synonyms_internal(text)
        normalized = self._normalize_patterns(normalized)
        return normalized
    
    def _normalize_patterns(self, text: str) -> str:
        """패턴 기반 정규화"""
        result = text
        
        # top_n 패턴
        if "top_n" in self.compiled_patterns:
            for regex in self.compiled_patterns["top_n"]["regexes"]:
                def replace_top(match):
                    n = match.group(1) or match.group(2) if match.lastindex >= 2 else match.group(1)
                    return f" top{n}"
                result = regex.sub(replace_top, result)
        
        # step_filter 패턴 (더 정확한 처리)
        if "step_filter" in self.compiled_patterns:
            for regex in self.compiled_patterns["step_filter"]["regexes"]:
                def replace_step(match):
                    # 그룹 인덱스 확인
                    if match.lastindex and match.lastindex >= 2:
                        step = match.group(2)
                    elif match.lastindex and match.lastindex >= 1:
                        step = match.group(1)
                    else:
                        return match.group(0)  # 매칭 실패시 원본 반환
                    return f" step={step.upper()}"
                result = regex.sub(replace_step, result)
        
        # trace_id 패턴 (그대로 유지)
        # date_range 패턴 (그대로 유지, 나중에 파싱)
        
        return result

# 전역 인스턴스
_normalizer = None

def get_normalizer() -> Normalizer:
    """싱글톤 패턴으로 Normalizer 반환"""
    global _normalizer
    if _normalizer is None:
        _normalizer = Normalizer()
    return _normalizer

@dataclass(frozen=True)
class Normalized:
    """정규화 결과"""
    raw: str
    text: str

def _collapse_spaces(text: str) -> str:
    """공백 정리"""
    return re.sub(r"\s+", " ", text).strip()

def _normalize_topn(text: str) -> str:
    """
    - 'top 5', 'TOP5', '상위 5개', '상위5', '5개', '5개 알려주세요' -> 'top5'
    """
    def repl_top(m: re.Match) -> str:
        num = re.findall(r"\d+", m.group(0))[0]
        return f"top{num}"
    
    def repl_num(m: re.Match) -> str:
        num = m.group(1)
        return f"top{num}"

    # 기존 top 패턴
    text = re.sub(r"\btop\s*(\d+)\b", repl_top, text, flags=re.IGNORECASE)
    # 상위 N개 패턴
    text = re.sub(r"상위\s*(\d+)\s*개?", repl_top, text)
    # N개 패턴 (앞뒤에 단어가 없거나 특정 키워드가 있을 때)
    text = re.sub(r"\b(\d+)\s*개\b", repl_num, text)
    
    return text

def _normalize_step_filter(text: str) -> str:
    """
    - 'step=STANDBY', 'step standby', 'standby 단계', 'standby 스텝' -> 'step=standby'
    """
    # explicit: step=xxx or step xxx
    text = re.sub(r"\bstep\s*=?\s*([a-z0-9\.\-_]+)", r"step=\1", text, flags=re.IGNORECASE)

    # Korean patterns: 'XXX 단계', 'XXX 스텝'
    text = re.sub(r"\b([a-z0-9\.\-_]+)\s*(단계|스텝)\b", r"step=\1", text, flags=re.IGNORECASE)

    return text

def normalize(raw_text: str) -> Normalized:
    """
    Deterministic normalization:
    1) lowercase
    2) normalize whitespace
    3) normalize top-n (5개 -> top5)
    4) normalize filters (step=...)
    5) replace synonyms (columns, metrics, groups)
    
    Returns: Normalized 객체 (raw, text)
    """
    text = raw_text.strip().lower()
    text = _collapse_spaces(text)

    # 패턴 정규화 (동의어 치환 전에 수행)
    text = _normalize_topn(text)
    text = _normalize_step_filter(text)

    # 동의어 치환 (YAML 기반)
    normalizer = get_normalizer()
    text = normalizer._replace_synonyms_internal(text)

    text = _collapse_spaces(text)

    return Normalized(raw=raw_text, text=text)

