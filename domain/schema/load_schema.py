# domain/schema/load_schema.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any, Optional
import yaml


@dataclass(frozen=True)
class ColumnDef:
    key: str
    domain_name: str
    physical_type: str
    unit: str
    csv_columns: List[str]
    aliases: List[str]


@dataclass(frozen=True)
class DomainSchema:
    columns: Dict[str, ColumnDef]
    meta: Dict[str, Any]


def load_columns_yaml(path: str | Path) -> DomainSchema:
    """columns.yaml 파일 로드"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Schema file not found: {path}")
    
    data = yaml.safe_load(p.read_text(encoding="utf-8"))

    cols: Dict[str, ColumnDef] = {}
    for key, d in data.get("columns", {}).items():
        cols[key] = ColumnDef(
            key=key,
            domain_name=d.get("domain_name", key),
            physical_type=d.get("physical_type", "unknown"),
            unit=d.get("unit", ""),
            csv_columns=d.get("csv_columns", []),
            aliases=d.get("aliases", []),
        )

    meta = data.get("meta", {})
    return DomainSchema(columns=cols, meta=meta)


def get_column_by_csv_name(schema: DomainSchema, csv_name: str) -> Optional[ColumnDef]:
    """CSV 컬럼명으로 도메인 키 찾기"""
    for col_def in schema.columns.values():
        if csv_name in col_def.csv_columns:
            return col_def
    return None


def get_csv_column(schema: DomainSchema, domain_key: str) -> Optional[str]:
    """도메인 키로 CSV 컬럼명 가져오기 (첫 번째)"""
    col_def = schema.columns.get(domain_key)
    if col_def and col_def.csv_columns:
        return col_def.csv_columns[0]
    return None

