"""
Plot Generator: 시계열 Plot 생성 (Matplotlib)
"""
import matplotlib
matplotlib.use('Agg')  # 서버 환경에서 필요한 백엔드 설정
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import pandas as pd
from typing import Optional
import io

# 한글 폰트 설정 (macOS에서 사용 가능한 폰트 우선 사용)
plt.rcParams['font.family'] = 'Apple SD Gothic Neo'  # macOS 기본 한글 폰트
plt.rcParams['axes.unicode_minus'] = False  # 음수 기호 깨짐 방지


def plot_timeseries(
    df: pd.DataFrame,
    title: str = "Time Series",
    x_col: str = "timestamp",
    y_col: str = "value",
    unit: str = ""
) -> io.BytesIO:
    """
    시계열 Plot 생성 (Matplotlib)
    
    Args:
        df: DataFrame (timestamp, value 컬럼 포함)
        title: 차트 제목
        x_col: X축 컬럼명 (timestamp, epoch_ms, time_bucket_second 등)
        y_col: Y축 컬럼명 (value)
        unit: Y축 단위 (예: "Torr", "sccm")
    
    Returns:
        BytesIO: PNG 이미지 데이터
    """
    if df.empty or y_col not in df.columns or x_col not in df.columns:
        # 빈 차트 반환
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.text(0.5, 0.5, "데이터가 없습니다", ha='center', va='center', transform=ax.transAxes)
        ax.set_title(title)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)
        return buf
    
    fig, ax = plt.subplots(figsize=(12, 5))
    
    # timestamp 컬럼을 datetime으로 변환 (아직 datetime이 아닌 경우)
    if x_col == "timestamp" and df[x_col].dtype != 'datetime64[ns]':
        try:
            df[x_col] = pd.to_datetime(df[x_col])
        except:
            pass
    
    # 시계열 플롯
    ax.plot(df[x_col], df[y_col], linewidth=1.5, color='#6366f1')
    
    ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel("Time", fontsize=12)
    ylabel = f"Value ({unit})" if unit else "Value"
    ax.set_ylabel(ylabel, fontsize=12)
    
    # 그리드 추가
    ax.grid(True, alpha=0.3, linestyle='--')
    
    # X축 라벨 회전 (날짜가 길면)
    plt.xticks(rotation=45, ha='right')
    
    plt.tight_layout()
    
    # PNG로 저장
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    
    return buf

