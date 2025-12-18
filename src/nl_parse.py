import re
from dataclasses import dataclass
from typing import Optional, Literal, List
from datetime import datetime
from domain.rules.normalization import normalize
from domain.rules.resolution import resolve_column_from_text

Agg = Literal["avg", "min", "max", "count", "std", "stddev", "p50", "median", "p95", "p99", "null_ratio"]
GroupBy = Optional[Literal["trace_id", "step_name", "date", "hour", "day"]]
AnalysisType = Literal["ranking", "group_profile", "comparison", "stability"]

AGG_MAP = [
    (r"(평균|avg|mean)", "avg"),
    (r"(최대|max)", "max"),
    (r"(최소|min)", "min"),
    (r"(개수|건수|count)", "count"),
    (r"(표준편차|std|stddev|표준편차)", "std"),
    (r"(중앙값|median|p50|50퍼센타일)", "p50"),
    (r"(p95|95퍼센타일|95퍼센트)", "p95"),
    (r"(p99|99퍼센타일|99퍼센트)", "p99"),
    (r"(결측률|null.*비율|missing.*ratio)", "null_ratio"),
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
    chart_type: Optional[Literal["line", "bar", "box", "heatmap"]]  # 차트 타입 (deprecated: analysis_type 사용)
    analysis_type: AnalysisType  # 분석 유형: ranking, group_profile, comparison, stability
    # 공정 친화 지표 플래그
    is_stable_avg: bool = False  # 안정화 구간 평균
    is_overshoot: bool = False  # overshoot (최대-설정)
    is_dwell_time: bool = False  # 체류시간
    is_variability: bool = False  # 변동성
    is_outlier: bool = False  # 이상치 탐지
    is_trace_compare: bool = False  # 두 trace 비교

def parse_question(question: str) -> Parsed:
    # 정규화 적용
    norm = normalize(question)
    q = norm.text
    
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
    
    # 공정 친화 지표 감지 (bool로 변환)
    is_stable_avg = bool(re.search(r"(안정|안정화|stable)", text, re.IGNORECASE))
    is_overshoot = bool(re.search(r"(overshoot|오버슈트|초과)", text, re.IGNORECASE))
    is_dwell_time = bool(re.search(r"(체류|dwell|시간|time)", text, re.IGNORECASE) and group_by == "step_name")
    is_variability = bool(re.search(r"(변동|variability|안정성)", text, re.IGNORECASE))
    
    # 이상치 탐지 감지 (bool로 변환)
    is_outlier = bool(re.search(r"(이상치|outlier|이상)", text, re.IGNORECASE))
    
    # 비교 기능 감지 (두 trace 비교)
    is_trace_compare = len(trace_ids) >= 2 and bool(re.search(r"(비교|차이|compare|diff)", text, re.IGNORECASE))
    
    # 분석 유형 결정 (질문 의도 기반)
    # C. 두 공정 비교 (우선순위 1: 가장 명확함)
    if is_trace_compare:
        analysis_type = "comparison"
    # D. 이상치/안정성 (우선순위 2)
    elif is_outlier or is_overshoot or is_stable_avg or is_dwell_time or is_variability:
        analysis_type = "stability"
    # A. 랭킹/비교 (top_n이 있고, group_by가 있으면 랭킹)
    elif top_n is not None and group_by is not None:
        analysis_type = "ranking"
    # B. 그룹별 분포 (하나의 trace_id 안에서 step_name별로 분석)
    elif trace_id and group_by == "step_name":
        analysis_type = "group_profile"
    # 기본값: group_by가 있으면 분포, 없으면 랭킹
    elif group_by is not None:
        analysis_type = "group_profile"
    else:
        analysis_type = "ranking"
    
    # 모호성 해결 (예: "VG11 압력" => vg11, pressact 제거)
    col = resolve_column_from_text(text, col)
    
    # overshoot, 이상치 탐지, trace 비교는 pressact 기본값 사용
    if (is_overshoot or is_outlier or is_trace_compare) and col is None:
        col = "pressact"
    
    # 컬럼이 없으면 기본값 사용 (정규화된 텍스트에서는 컬럼이 이미 변환되었을 수 있음)
    if col is None:
        col = "pressact"  # 기본 컬럼

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
        analysis_type=analysis_type,  # 분석 유형 추가
        is_stable_avg=is_stable_avg,
        is_overshoot=is_overshoot,
        is_dwell_time=is_dwell_time,
        is_variability=is_variability,
        is_outlier=is_outlier,
        is_trace_compare=is_trace_compare,
    )
