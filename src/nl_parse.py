import re
from dataclasses import dataclass
from typing import Optional, Literal, List
from datetime import datetime

Agg = Literal["avg", "min", "max", "count"]
GroupBy = Optional[Literal["trace_id", "step_name", "date", "hour", "day"]]

AGG_MAP = [
    (r"(평균|avg|mean)", "avg"),
    (r"(최대|max)", "max"),
    (r"(최소|min)", "min"),
    (r"(개수|건수|count)", "count"),
]

COL_SYNONYMS = {
    "pressact": [r"pressact", r"챔버\s*압력", r"압력\s*실측", r"현재\s*압력", r"압력"],
    "pressset": [r"pressset", r"압력\s*설정", r"set\s*pressure"],
    "vg11": [r"vg11"],
    "vg12": [r"vg12"],
    "vg13": [r"vg13"],
    "apcvalvemon": [r"apcvalvemon", r"apc\s*밸브\s*모니터", r"apc\s*모니터"],
    "apcvalveset": [r"apcvalveset", r"apc\s*밸브\s*설정", r"apc\s*설정"],
}

TRACE_RE = re.compile(r"(standard_trace_\d{3})", re.IGNORECASE)
# step=STANDBY, step:STANDBY, 스텝 STANDBY 등
STEP_RE = re.compile(r"(step|스텝|단계)\s*[:=]?\s*([a-z0-9_]+)", re.IGNORECASE)

TOP_RE = re.compile(r"(top\s*(\d+)|상위\s*(\d+))", re.IGNORECASE)

# 날짜 패턴: 2024-01-01, 2024/01/01
DATE_RE = re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})")

# 시간 그룹핑: 일별, 시간별, 시간대별 (정규식은 직접 사용하므로 변수 제거)

def _pick_agg(text: str) -> Agg:
    for pat, agg in AGG_MAP:
        if re.search(pat, text, re.IGNORECASE):
            return agg  # type: ignore
    return "avg"

def _pick_col(text: str) -> Optional[str]:
    for col, pats in COL_SYNONYMS.items():
        for pat in pats:
            if re.search(pat, text, re.IGNORECASE):
                return col
    return None

def _pick_group_by(text: str) -> GroupBy:
    # 시간 그룹핑 우선 확인
    if re.search(r"(일별|day|날짜별)", text, re.IGNORECASE):
        return "day"
    if re.search(r"(시간별|hour|시간대별)", text, re.IGNORECASE):
        return "hour"
    
    # 기존 그룹핑
    if re.search(r"(스텝별|단계별|step별)", text, re.IGNORECASE):
        return "step_name"
    if re.search(r"(공정별|trace별|트레이스별)", text, re.IGNORECASE):
        return "trace_id"
    return None

def _pick_top_n(text: str) -> Optional[int]:
    m = TOP_RE.search(text)
    if not m:
        return None
    n = m.group(2) or m.group(3)
    return int(n) if n else None

def _pick_date_range(text: str) -> tuple[Optional[str], Optional[str]]:
    """날짜 범위 추출: '2024-01-01부터' 또는 '2024-01-01 ~ 2024-01-31'"""
    dates = DATE_RE.findall(text)
    if not dates:
        return None, None
    
    # 첫 번째 날짜는 시작일
    start_date = "-".join([dates[0][0], dates[0][1].zfill(2), dates[0][2].zfill(2)])
    
    # 두 번째 날짜가 있으면 종료일
    end_date = None
    if len(dates) > 1:
        end_date = "-".join([dates[1][0], dates[1][1].zfill(2), dates[1][2].zfill(2)])
    elif re.search(r"부터|~|-|to", text, re.IGNORECASE):
        # "부터"가 있으면 오늘까지로 간주하거나, 시작일만 사용
        pass
    
    return start_date, end_date

def _pick_multiple_traces(text: str) -> List[str]:
    """여러 trace_id 추출: 'standard_trace_001과 standard_trace_002'"""
    traces = TRACE_RE.findall(text)
    return traces if traces else []

def _pick_multiple_steps(text: str) -> List[str]:
    """여러 step_name 추출"""
    steps = STEP_RE.findall(text)
    return [s[1] for s in steps] if steps else []

@dataclass
class Parsed:
    agg: Agg
    col: Optional[str]
    trace_id: Optional[str]  # 단일 trace_id
    trace_ids: List[str]  # 여러 trace_id 비교용
    step_name: Optional[str]  # 단일 step_name
    step_names: List[str]  # 여러 step_name 비교용
    group_by: GroupBy
    top_n: Optional[int]
    date_start: Optional[str]  # YYYY-MM-DD
    date_end: Optional[str]  # YYYY-MM-DD
    chart_type: Optional[Literal["line", "bar", "box", "heatmap"]]  # 차트 타입

def parse_question(q: str) -> Parsed:
    text = q.strip()

    agg = _pick_agg(text)
    col = _pick_col(text)

    # 여러 trace_id 추출 (비교용)
    trace_ids = _pick_multiple_traces(text)
    trace_id = trace_ids[0] if len(trace_ids) == 1 else None
    
    # 여러 step_name 추출 (비교용)
    step_names = _pick_multiple_steps(text)
    step_name = step_names[0] if len(step_names) == 1 else None

    group_by = _pick_group_by(text)
    top_n = _pick_top_n(text)
    date_start, date_end = _pick_date_range(text)
    
    # 차트 타입 추론
    chart_type = None
    if group_by in ("day", "hour", "date") or date_start or date_end:
        chart_type = "line"  # 시계열 데이터는 라인 차트
    elif len(trace_ids) > 1 or len(step_names) > 1:
        chart_type = "bar"  # 비교는 바 차트
    elif re.search(r"(분포|box|박스)", text, re.IGNORECASE):
        chart_type = "box"
    elif re.search(r"(히트맵|heatmap|매트릭스)", text, re.IGNORECASE):
        chart_type = "heatmap"

    if agg != "count" and col is None:
        raise ValueError("지표를 못 찾았어. 예: 'pressact 평균', '압력 최대'")

    return Parsed(
        agg=agg,
        col=col,
        trace_id=trace_id,
        trace_ids=trace_ids,
        step_name=step_name,
        step_names=step_names,
        group_by=group_by,
        top_n=top_n,
        date_start=date_start,
        date_end=date_end,
        chart_type=chart_type,
    )
