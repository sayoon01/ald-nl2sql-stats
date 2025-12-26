"""
차트 헬퍼 함수: Others 추가, 정렬, top_n 처리
"""
import pandas as pd  # type: ignore
from typing import Tuple, Optional


def get_xy_columns(df: pd.DataFrame) -> Tuple[str, str]:
    """x축, y축 컬럼 추출"""
    x_col = df.columns[0]
    y_col = "value" if "value" in df.columns else ("n" if "n" in df.columns else df.columns[-1])
    return x_col, y_col


def apply_top_n_limit(df: pd.DataFrame, top_n: Optional[int], max_rows: int = 100) -> pd.DataFrame:
    """Top N 제한 적용"""
    if top_n and len(df) > top_n:
        return df.head(top_n)
    elif len(df) > max_rows:
        return df.head(max_rows)
    return df


def prepare_chart_data_for_others(
    df: pd.DataFrame, 
    parsed: dict, 
    config: dict
) -> Tuple[pd.DataFrame, Optional[pd.DataFrame], bool]:
    """
    Others 추가를 위한 데이터 준비
    Returns: (df_processed, df_all_for_others, add_others_flag)
    """
    # Rule: step 개수 > 12면 → 요약 그래프 (group_profile이지만 step이 많을 때)
    add_others_for_chart = False
    df_all_for_others = None
    
    if (parsed.get("analysis_type") == "group_profile" 
        and parsed.get("group_by") == "step_name" 
        and len(df) > 12):
        # 요약 모드로 전환: Top 7 + Others
        if not parsed.get("top_n"):  # 사용자가 명시하지 않았으면
            config["chart_type"] = "horizontal_bar"  # 가로 막대로
            parsed["top_n"] = 7  # Top 7만 표시
            add_others_for_chart = True
            # 나머지는 Others로 묶기 위해 원본 저장 (값 기준 정렬 필요)
            df_all_for_others = df.copy()
            x_col, y_col = get_xy_columns(df)
            # 값 기준으로 정렬 (내림차순)
            df = df.sort_values(y_col, ascending=False).head(7) if len(df) > 7 else df.sort_values(y_col, ascending=False)
    
    return df, df_all_for_others, add_others_for_chart


def add_others_to_chart(
    df: pd.DataFrame, 
    df_all_for_others: Optional[pd.DataFrame], 
    x_col: str, 
    y_col: str
) -> pd.DataFrame:
    """차트용 Others 행 추가"""
    if df_all_for_others is None or len(df_all_for_others) <= len(df):
        return df
    
    others_df = df_all_for_others.sort_values(y_col, ascending=False).iloc[len(df):]
    if others_df.empty:
        return df
    
    others_value_sum = sum(r for r in others_df[y_col].astype(float).tolist())
    others_avg = others_value_sum / len(others_df) if len(others_df) > 0 else 0
    others_row = {x_col: f"Others ({len(others_df)}개)", y_col: others_avg}
    
    return pd.concat([df, pd.DataFrame([others_row])], ignore_index=True)

