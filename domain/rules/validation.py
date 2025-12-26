"""
도메인 규칙 검증
- 컬럼 존재 여부 확인
- 지표 유효성 확인
- 그룹핑 유효성 확인
"""
import yaml
from pathlib import Path
from typing import Optional, List

DOMAIN_ROOT = Path(__file__).parent.parent.parent / "domain"

def load_schema(file_path: Path) -> dict:
    """스키마 파일 로드 (하위 호환성용)"""
    if not file_path.exists():
        return {}
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}

class Validator:
    """도메인 규칙 검증 클래스"""
    
    def __init__(self):
        # YAML 기반 스키마 로드 (새 형식 우선)
        try:
            from domain.schema.load_schema import load_columns_yaml
            schema_path = DOMAIN_ROOT / "schema" / "columns.yaml"
            if schema_path.exists():
                self.schema = load_columns_yaml(schema_path)
                # 하위 호환성을 위해 dict 형태로도 제공
                self.columns = {
                    key: {
                        "domain_name": col_def.domain_name,
                        "unit": col_def.unit,
                        "type": col_def.physical_type,
                    }
                    for key, col_def in self.schema.columns.items()
                }
            else:
                self.columns = load_schema(DOMAIN_ROOT / "schema" / "columns.yaml")
                self.schema = None
        except Exception as e:
            # Fallback: 기존 방식
            import traceback
            print(f"[Validator] 스키마 로드 실패: {e}")
            traceback.print_exc()
            self.columns = load_schema(DOMAIN_ROOT / "schema" / "columns.yaml")
            self.schema = None
        
        self.metrics = load_schema(DOMAIN_ROOT / "schema" / "metrics.yaml")
        self.groups = load_schema(DOMAIN_ROOT / "schema" / "groups.yaml")
    
    def is_valid_column(self, column: str) -> bool:
        """컬럼이 유효한지 확인"""
        if self.schema:
            return column in self.schema.columns
        return column in self.columns
    
    def is_valid_metric(self, metric: str) -> bool:
        """지표가 유효한지 확인"""
        return metric in self.metrics
    
    def is_valid_group(self, group: str) -> bool:
        """그룹핑이 유효한지 확인"""
        return group in self.groups
    
    def get_column_info(self, column: str) -> Optional[dict]:
        """컬럼 메타데이터 반환"""
        return self.columns.get(column)
    
    def get_metric_info(self, metric: str) -> Optional[dict]:
        """지표 메타데이터 반환"""
        return self.metrics.get(metric)
    
    def get_group_info(self, group: str) -> Optional[dict]:
        """그룹핑 메타데이터 반환"""
        return self.groups.get(group)
    
    def get_all_columns(self) -> List[str]:
        """모든 유효한 컬럼 목록 반환"""
        if self.schema:
            return list(self.schema.columns.keys())
        # 메타 키 제외
        meta_keys = {"version", "dataset", "primary_table", "meta", "columns"}
        return [k for k in self.columns.keys() if k not in meta_keys]
    
    def get_all_metrics(self) -> List[str]:
        """모든 유효한 지표 목록 반환"""
        return list(self.metrics.keys())
    
    def get_all_groups(self) -> List[str]:
        """모든 유효한 그룹핑 목록 반환"""
        return list(self.groups.keys())

# 전역 인스턴스
_validator = None

def get_validator() -> Validator:
    """싱글톤 패턴으로 Validator 반환"""
    global _validator
    if _validator is None:
        _validator = Validator()
    return _validator

