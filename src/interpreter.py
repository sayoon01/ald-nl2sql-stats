"""
해석 레이어: SQL 결과를 사람이 읽기 쉬운 문장으로 변환

원칙:
1. SQL을 모른다 → df columns만 보고 말한다
2. 해석 분기는 (p.col, p.agg, p.group_by)로 결정
3. df 스키마를 build_sql이 항상 일정하게 보장
4. 메타데이터(단위, 정상범위)는 semantic_registry.yaml에서 가져옴
"""
from typing import Optional
import pandas as pd
from src.nl_parse import Parsed
from src.semantic_resolver import get_metadata_by_physical_column

# 컬럼 한글 라벨은 semantic_registry에서 가져옴
def _get_column_label(physical_col: Optional[str]) -> str:
    """Physical Column의 한글 라벨 가져오기 (semantic_registry에서)"""
    if not physical_col:
        return "값"
    metadata = get_metadata_by_physical_column(physical_col)
    if metadata and "description" in metadata:
        return metadata["description"]
    # 폴백: 컬럼명 그대로
    return physical_col

# 집계 함수 한글 라벨
AGG_LABEL = {
    "avg": "평균",
    "max": "최대",
    "min": "최소",
    "std": "표준편차",
    "stddev": "표준편차",
    "count": "개수",
    "median": "중앙값",
    "p50": "중앙값",
    "p95": "95퍼센타일",
    "p99": "99퍼센타일",
    "null_ratio": "결측률",
}

# 정상 범위는 이제 semantic_registry.yaml에서 가져옴

def interpret_single(p: Parsed, df: pd.DataFrame) -> str:
    """단일 값 해석기 (group_by가 None일 때)"""
    if df is None or df.empty:
        return "결과가 없습니다."

    name = _get_column_label(p.col)
    agg_kor = AGG_LABEL.get(p.agg, p.agg)

    # build_sql 스키마: value, n, std
    v = df["value"].iloc[0] if "value" in df.columns else None
    n = int(df["n"].iloc[0]) if "n" in df.columns else None
    std = df["std"].iloc[0] if "std" in df.columns else None

    # "평균은", "최대값은", "최소값은" 형태로 자연스럽게
    if agg_kor in ("최대", "최소"):
        msg = f"{name} {agg_kor}값은"
    else:
        msg = f"{name} {agg_kor}은"
    
    if v is not None:
        # 값 포맷팅 (소수점 3자리까지, 필요시 과학적 표기법)
        if abs(v) >= 1000:
            v_str = f"{v:.1f}"
        elif abs(v) >= 1:
            v_str = f"{v:.3f}"
        else:
            v_str = f"{v:.6f}".rstrip('0').rstrip('.')
        
        # 메타데이터 가져오기 (semantic_registry.yaml에서)
        metadata = get_metadata_by_physical_column(p.col) if p.col else None
        unit = metadata.get("unit", "") if metadata else ""
        normal_range = metadata.get("normal_range") if metadata else None
        
        # 정상 범위 체크 조건:
        # 1. normal_range가 있어야 함
        # 2. unit이 있어야 함 (불명확하면 범위 판정 안 함)
        # 3. agg == "avg" (평균일 때만)
        # 4. min_val과 max_val이 모두 있어야 함
        
        can_check_range = (
            normal_range is not None
            and unit  # unit이 있으면 True (빈 문자열이면 False)
            and p.agg == "avg"
            and normal_range.get("min") is not None
            and normal_range.get("max") is not None
        )
        
        if can_check_range:
            min_val = normal_range.get("min")
            max_val = normal_range.get("max")
            
            # 단위 포함해서 값 표시
            msg += f" {v_str} {unit}로"
            
            # 상태 판정
            if v < min_val:
                status = "낮음"
            elif v > max_val:
                status = "높음"
            else:
                status = "정상"
            
            msg += f" {status} 범위({min_val}~{max_val} {unit})입니다."
        else:
            # 범위 체크 불가: 단위만 표시 (또는 단위도 없으면 값만)
            if unit:
                msg += f" {v_str} {unit}입니다"
            else:
                msg += f" {v_str}입니다"
    else:
        msg += " 결과입니다"

    if n is not None:
        msg += f" (표본 {n:,}개"
        if std is not None and p.agg not in ("std", "stddev"):
            # 표준편차 포맷팅
            if abs(std) >= 1000:
                std_str = f"{std:.1f}"
            elif abs(std) >= 1:
                std_str = f"{std:.3f}"
            else:
                std_str = f"{std:.6f}".rstrip('0').rstrip('.')
            msg += f", 표준편차 {std_str}"
        msg += ")"
    
    return msg

def interpret_group(p: Parsed, df: pd.DataFrame, topn: int = 5) -> str:
    """그룹별 결과 해석기 (group_by가 있을 때)"""
    if df is None or df.empty:
        return "결과가 없습니다."

    name = _get_column_label(p.col)
    agg_kor = AGG_LABEL.get(p.agg, p.agg)
    g = p.group_by

    # 안전: 컬럼 체크
    if g not in df.columns or "value" not in df.columns:
        return f"해석 불가: 결과 컬럼에 필요한 정보가 없습니다. (columns={list(df.columns)})"

    # 요약 통계
    total_groups = len(df)
    overall_min = df["value"].min()
    overall_max = df["value"].max()

    # TopN: value 기준 내림차순
    top = df.sort_values("value", ascending=False).head(topn)

    # 그룹명 한글화
    group_label = "공정 ID" if g == "trace_id" else ("단계명" if g == "step_name" else g)

    lines = []
    lines.append(f"{group_label}별 {name} {agg_kor} 결과입니다. (총 {total_groups}개 그룹)")
    
    # 값 범위 포맷팅
    min_str = f"{overall_min:.3f}".rstrip('0').rstrip('.') if overall_min else "0"
    max_str = f"{overall_max:.3f}".rstrip('0').rstrip('.') if overall_max else "0"
    lines.append(f"값 범위: {min_str} ~ {max_str}")
    
    lines.append(f"상위 {topn}개:")
    for _, r in top.iterrows():
        n_val = int(r['n']) if 'n' in df.columns else 'NA'
        val = r['value']
        # 값 포맷팅
        if abs(val) >= 1000:
            val_str = f"{val:.1f}"
        elif abs(val) >= 1:
            val_str = f"{val:.3f}"
        else:
            val_str = f"{val:.6f}".rstrip('0').rstrip('.')
        lines.append(f"  • {r[g]}: {val_str} (표본 {n_val:,}개)")

    return "\n".join(lines)

def interpret(p: Parsed, df: pd.DataFrame, topn: int = 5) -> str:
    """
    통합 해석기: (p.col, p.agg, p.group_by)로 분기
    
    Args:
        p: Parsed 객체
        df: SQL 실행 결과 DataFrame
        topn: 그룹 해석 시 상위 N개 (기본값: 5)
    
    Returns:
        사람이 읽기 쉬운 해석 문장
    """
    if p.group_by is None:
        return interpret_single(p, df)
    else:
        return interpret_group(p, df, topn=topn)

