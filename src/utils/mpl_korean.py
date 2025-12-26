"""
Matplotlib 한글 폰트 설정 유틸리티
모듈 import 시 1회만 실행
"""
import matplotlib  # type: ignore
matplotlib.use("Agg")  # 서버 환경에서 필요한 백엔드 설정
import matplotlib.pyplot as plt  # type: ignore
import matplotlib.font_manager as fm  # type: ignore


def setup_korean_font():
    """한글 폰트 설정 (Linux 환경)"""
    plt.rcParams["axes.unicode_minus"] = False  # 음수 기호 깨짐 방지
    
    font_list = [f.name for f in fm.fontManager.ttflist]
    candidates = [
        "NanumGothic",
        "NanumBarunGothic",
        "Noto Sans CJK KR",
        "Noto Sans CJK",
    ]
    
    selected = None
    for c in candidates:
        if c in font_list:
            selected = c
            break
        for name in font_list:
            if c.lower() in name.lower():
                selected = name
                break
        if selected:
            break
    
    plt.rcParams["font.family"] = selected or "DejaVu Sans"
    if selected:
        print(f"[Font] 한글 폰트 설정: {selected}")
    else:
        print("[Font] 한글 폰트를 찾을 수 없어 DejaVu Sans 사용 (한글 깨짐 가능)")

