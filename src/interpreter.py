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
    """그룹별 결과 해석기 (group_by가 있을 때) - 자연스러운 문장으로 개선"""
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
    group_label = "공정" if g == "trace_id" else ("단계" if g == "step_name" else g)
    
    # 단위 가져오기
    metadata = get_metadata_by_physical_column(p.col) if p.col else None
    unit = metadata.get("unit", "") if metadata else ""

    # 값 포맷팅 헬퍼
    def format_val(v):
        if abs(v) >= 1000:
            return f"{v:.1f}"
        elif abs(v) >= 1:
            return f"{v:.2f}"
        else:
            return f"{v:.3f}".rstrip('0').rstrip('.')

    # 자연스러운 요약 생성
    if total_groups == 1:
        # 단일 그룹
        r = df.iloc[0]
        val_str = format_val(r['value'])
        n_val = int(r['n']) if 'n' in df.columns else None
        unit_str = f" {unit}" if unit else ""
        summary = f"{r[g]}의 {name} {agg_kor}은 {val_str}{unit_str}입니다"
        if n_val:
            summary += f" (표본 {n_val:,}개)"
        return summary
    
    # 여러 그룹: 상위 결과 중심으로 자연스럽게 설명
    top1 = top.iloc[0]
    top1_name = top1[g]
    top1_val = format_val(top1['value'])
    top1_n = int(top1['n']) if 'n' in df.columns else None
    
    unit_str = f" {unit}" if unit else ""
    
    # 메인 메시지: 1위 중심
    if topn == 1 or len(top) == 1:
        summary = f"총 {total_groups}개 {group_label} 중 {name} {agg_kor}이 가장 높은 {group_label}은 {top1_name}({top1_val}{unit_str})입니다"
    else:
        # 상위 N개 나열
        top_names = [str(r[g]) for _, r in top.iterrows()]
        if len(top_names) <= 3:
            top_list = ", ".join(top_names)
            summary = f"총 {total_groups}개 {group_label} 중 상위 {len(top_names)}개는 {top_list}이며, 1위 {top1_name}의 {agg_kor}은 {top1_val}{unit_str}입니다"
        else:
            summary = f"총 {total_groups}개 {group_label} 중 1위는 {top1_name}({top1_val}{unit_str})이며, 상위 {len(top)}개 {group_label}는 다음과 같습니다"
    
    # 표본 수 추가
    if top1_n:
        summary += f" (표본 {top1_n:,}개)"
    
    # 상위 N개 상세 (topn이 1보다 크고 실제 top이 여러 개일 때)
    if topn > 1 and len(top) > 1:
        summary += "\n\n상위 순위:"
        for idx, (_, r) in enumerate(top.iterrows(), 1):
            val_str = format_val(r['value'])
            n_val = int(r['n']) if 'n' in df.columns else None
            n_str = f" (표본 {n_val:,}개)" if n_val else ""
            summary += f"\n{idx}. {r[g]}: {val_str}{unit_str}{n_str}"
    
    # 범위 정보 (간단히)
    if total_groups > 1:
        min_str = format_val(overall_min)
        max_str = format_val(overall_max)
        summary += f"\n\n전체 범위: {min_str} ~ {max_str}{unit_str}"

    return summary

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

