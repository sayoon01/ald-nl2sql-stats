"""
도메인 메타데이터 기반 자연어 파서
- YAML 기반 메타데이터 사용
- 확장 가능한 구조
- 표준 JSON 스키마 준수
"""
import re
from dataclasses import dataclass, field
from typing import Optional, Literal, List
from datetime import datetime

# 도메인 메타데이터 모듈
from domain import (
    normalize,
    get_validator,
    get_default_metric,
    get_default_column,
)
from domain.rules.resolution import resolve_column_from_text

Agg = Literal["avg", "min", "max", "count", "std", "stddev", "p50", "median", "p95", "p99", "null_ratio"]
GroupBy = Optional[Literal["trace_id", "step_name", "date", "hour", "day"]]
AnalysisType = Literal["ranking", "group_profile", "comparison", "stability"]

# 정규식 패턴
TRACE_RE = re.compile(r"(standard_trace_\d{3})", re.IGNORECASE)
STEP_RE = re.compile(r"step\s*[:=]\s*([a-z0-9_]+)", re.IGNORECASE)
# top5, top 5, 상위 5, 5개, 5개 알려주세요 등 다양한 패턴 지원
TOP_RE = re.compile(r"(?:top\s*(\d+)|상위\s*(\d+)|(\d+)\s*개)", re.IGNORECASE)
DATE_RE = re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})")

def _pick_agg(text: str, validator) -> Agg:
    """집계 함수 추출 (도메인 메타데이터 기반)"""
    metrics = validator.get_all_metrics()
    text_lower = text.lower()
    
    # 정규화된 텍스트에서 지표 찾기 (긴 것부터 매칭)
    matched_metrics = []
    for metric in metrics:
        metric_info = validator.get_metric_info(metric)
        if not metric_info:
            continue
        
        label = metric_info.get("label", "").lower()
        if label and label in text_lower:
            matched_metrics.append((len(label), metric))
        
        # 지표명 자체도 확인
        if metric in text_lower:
            matched_metrics.append((len(metric), metric))
    
    # 가장 긴 매칭을 우선
    if matched_metrics:
        matched_metrics.sort(reverse=True)
        return matched_metrics[0][1]  # type: ignore
    
    return get_default_metric()  # type: ignore

def _pick_col(text: str, validator) -> Optional[str]:
    """컬럼 추출 (도메인 메타데이터 기반)"""
    text_lower = text.lower()
    matched_cols = []
    
    # 메타 키워드 제외 (version, dataset, primary_table, meta 등)
    meta_keys = {"version", "dataset", "primary_table", "meta", "columns"}
    
    # 새 스키마 형식 사용
    if hasattr(validator, 'schema') and validator.schema:
        for key, col_def in validator.schema.columns.items():
            # 메타 키 제외
            if key in meta_keys:
                continue
            
            # 1. 키 직접 매칭
            if key.lower() in text_lower:
                matched_cols.append((len(key), key))
            
            # 2. 동의어 매칭
            for alias in col_def.aliases:
                if alias.lower() in text_lower:
                    matched_cols.append((len(alias), key))
            
            # 3. 도메인명 매칭
            if col_def.domain_name.lower() in text_lower:
                matched_cols.append((len(col_def.domain_name), key))
    else:
        # 기존 방식 (하위 호환)
        columns = validator.get_all_columns()
        for col in columns:
            if col in meta_keys:
                continue
                
            col_info = validator.get_column_info(col)
            if not col_info or not isinstance(col_info, dict):
                continue
            
            domain_name = col_info.get("domain_name", "").lower()
            if domain_name and domain_name in text_lower:
                matched_cols.append((len(domain_name), col))
            
            # 컬럼명 자체도 확인
            if col in text_lower:
                matched_cols.append((len(col), col))
    
    # 가장 긴 매칭을 우선
    if matched_cols:
        matched_cols.sort(reverse=True)
        return matched_cols[0][1]
    
    return None

def _pick_group_by(text: str, validator) -> GroupBy:
    """그룹핑 추출 (도메인 메타데이터 기반)"""
    groups = validator.get_all_groups()
    text_lower = text.lower()
    
    # 정규화된 텍스트에서 그룹 찾기 (긴 것부터 매칭)
    matched_groups = []
    for group in groups:
        group_info = validator.get_group_info(group)
        if not group_info:
            continue
        
        label = group_info.get("label", "").lower()
        if label and label in text_lower:
            matched_groups.append((len(label), group))
        
        # 그룹명 자체도 확인
        if group in text_lower:
            matched_groups.append((len(group), group))
    
    # 가장 긴 매칭을 우선
    if matched_groups:
        matched_groups.sort(reverse=True)
        selected = matched_groups[0][1]
        # date와 day는 동일하게 처리 (day를 date로 통일)
        if selected == "day":
            return "date"  # type: ignore
        return selected  # type: ignore
    
    return None

def _pick_top_n(text: str) -> Optional[int]:
    """Top N 추출 (top5, 상위 5, 5개 등 다양한 패턴 지원)"""
    m = TOP_RE.search(text)
    if not m:
        return None
    
    # 그룹 1: top 5
    # 그룹 2: 상위 5
    # 그룹 3: 5개
    n = m.group(1) or m.group(2) or m.group(3)
    if n:
        try:
            return int(n)
        except:
            return None
    return None

def _pick_date_range(text: str) -> tuple[Optional[str], Optional[str]]:
    """날짜 범위 추출"""
    dates = DATE_RE.findall(text)
    if not dates:
        return None, None
    
    start_date = "-".join([dates[0][0], dates[0][1].zfill(2), dates[0][2].zfill(2)])
    
    end_date = None
    if len(dates) > 1:
        end_date = "-".join([dates[1][0], dates[1][1].zfill(2), dates[1][2].zfill(2)])
    
    return start_date, end_date

def _pick_multiple_traces(text: str) -> List[str]:
    """여러 trace_id 추출"""
    traces = TRACE_RE.findall(text)
    return traces if traces else []

def _pick_multiple_steps(text: str) -> List[str]:
    """여러 step_name 추출 (step=STANDBY 형식만)"""
    steps = []
    for m in STEP_RE.finditer(text):
        step = m.group(1).upper()
        # 유효한 step_name인지 확인 (너무 짧거나 특수문자면 제외)
        if step and len(step) > 1 and step not in ["STEP", "_NAME", "별"]:
            if step not in steps:
                steps.append(step)
    return steps

@dataclass
class Parsed:
    """
    파싱 결과 - 표준 JSON 스키마 준수
    이 구조는 절대 변경되지 않아야 하는 중간 표현입니다.
    """
    metric: Agg = "avg"
    column: Optional[str] = None
    group_by: GroupBy = None
    filters: dict = field(default_factory=dict)
    top_n: Optional[int] = None
    analysis_type: AnalysisType = "ranking"
    flags: dict = field(default_factory=dict)
    
    # 하위 호환성을 위한 속성 (deprecated, column/metric 사용 권장)
    @property
    def col(self) -> Optional[str]:
        """하위 호환성: column의 별칭"""
        return self.column
    
    @property
    def agg(self) -> Agg:
        """하위 호환성: metric의 별칭"""
        return self.metric
    
    @property
    def trace_id(self) -> Optional[str]:
        """하위 호환성: filters.trace_id"""
        return self.filters.get("trace_id")
    
    @property
    def trace_ids(self) -> List[str]:
        """하위 호환성: filters.trace_ids"""
        return self.filters.get("trace_ids", [])
    
    @property
    def step_name(self) -> Optional[str]:
        """하위 호환성: filters.step_name"""
        return self.filters.get("step_name")
    
    @property
    def step_names(self) -> List[str]:
        """하위 호환성: filters.step_names"""
        return self.filters.get("step_names", [])
    
    @property
    def date_start(self) -> Optional[str]:
        """하위 호환성: filters.date_start"""
        return self.filters.get("date_start")
    
    @property
    def date_end(self) -> Optional[str]:
        """하위 호환성: filters.date_end"""
        return self.filters.get("date_end")
    
    @property
    def is_trace_compare(self) -> bool:
        """하위 호환성: flags.is_trace_compare"""
        return self.flags.get("is_trace_compare", False)
    
    @property
    def is_outlier(self) -> bool:
        """하위 호환성: flags.is_outlier"""
        return self.flags.get("is_outlier", False)
    
    @property
    def is_dwell_time(self) -> bool:
        """하위 호환성: flags.is_dwell_time"""
        return self.flags.get("is_dwell_time", False)
    
    @property
    def is_overshoot(self) -> bool:
        """하위 호환성: flags.is_overshoot"""
        return self.flags.get("is_overshoot", False)
    
    @property
    def is_stable_avg(self) -> bool:
        """하위 호환성: flags.is_stable_avg"""
        return self.flags.get("is_stable_avg", False)
    
    def to_dict(self) -> dict:
        """표준 JSON 형식으로 변환"""
        result = {
            "metric": self.metric,
            "column": self.column,
            "group_by": self.group_by,
            "filters": self.filters.copy(),
            "top_n": self.top_n,
            "analysis_type": self.analysis_type,
            "flags": self.flags.copy()
        }
        # None 값과 빈 딕셔너리 제거
        return {k: v for k, v in result.items() if v is not None and v != {}}
    
    @classmethod
    def from_dict(cls, data: dict) -> "Parsed":
        """표준 JSON 형식에서 생성"""
        return cls(
            metric=data.get("metric", "avg"),
            column=data.get("column"),
            group_by=data.get("group_by"),
            filters=data.get("filters", {}),
            top_n=data.get("top_n"),
            analysis_type=data.get("analysis_type", "ranking"),
            flags=data.get("flags", {})
        )

def parse_question(q: str) -> Parsed:
    """
    질문 파싱 (도메인 메타데이터 기반)
    
    파이프라인:
    1. 정규화 (normalize)
    2. 도메인 파싱 (intent, slots)
    3. 검증 및 fallback
    """
    validator = get_validator()
    
    # 1. 정규화
    normalized_obj = normalize(q)
    normalized = normalized_obj.text  # 정규화된 텍스트
    original = q.lower()  # 원본 (소문자)
    
    # 2. 도메인 파싱
    # 필터와 플래그 초기화
    filters = {}
    flags = {}
    
    # 컬럼 추출
    column = _pick_col(normalized, validator)
    if not column:
        column = _pick_col(original, validator)  # 원본에서도 시도
    
    # 집계 함수 추출
    metric = _pick_agg(normalized, validator)
    
    # 그룹핑 추출
    group_by = _pick_group_by(normalized, validator)
    if not group_by:
        group_by = _pick_group_by(original, validator)
    
    # Top N 추출
    top_n = _pick_top_n(normalized) or _pick_top_n(original)
    
    # Trace ID 추출
    traces = _pick_multiple_traces(original)
    if len(traces) == 1:
        filters["trace_id"] = traces[0]
    elif len(traces) > 1:
        filters["trace_ids"] = traces
        flags["is_trace_compare"] = True
    
    # Step Name 추출
    steps = _pick_multiple_steps(normalized)
    if not steps:
        steps = _pick_multiple_steps(original)
    if len(steps) == 1:
        filters["step_name"] = steps[0]
    elif len(steps) > 1:
        filters["step_names"] = steps
    
    # 날짜 범위 추출
    date_start, date_end = _pick_date_range(original)
    if date_start:
        filters["date_start"] = date_start
    if date_end:
        filters["date_end"] = date_end
    
    # 특수 지표 감지
    if "이상치" in original or "outlier" in original.lower():
        flags["is_outlier"] = True
    if "체류" in original or "dwell" in original.lower():
        flags["is_dwell_time"] = True
    if "오버슈트" in original or "overshoot" in original.lower():
        flags["is_overshoot"] = True
    if "안정" in original or "stable" in original.lower():
        flags["is_stable_avg"] = True
    
    # 분석 유형 결정
    if flags.get("is_trace_compare"):
        analysis_type = "comparison"
    elif flags.get("is_outlier") or flags.get("is_overshoot") or flags.get("is_stable_avg") or flags.get("is_dwell_time"):
        analysis_type = "stability"
    elif group_by:
        if top_n:
            analysis_type = "ranking"
        else:
            analysis_type = "group_profile"
    else:
        analysis_type = "ranking"
    
    # 그룹핑이 있으면 분석 유형 업데이트
    if group_by == "step_name" and filters.get("trace_id"):
        analysis_type = "group_profile"
    
    # 3. Fallback 적용
    if not column:
        column = get_default_column()
    if not metric:
        metric = get_default_metric()  # type: ignore
    
    # 4. 모호성 해결 (예: "VG11 압력" => vg11, pressact 제거)
    column = resolve_column_from_text(normalized, column)
    
    # 5. 검증
    if column and not validator.is_valid_column(column):
        column = get_default_column()
    
    if metric and not validator.is_valid_metric(metric):
        metric = get_default_metric()  # type: ignore
    
    if group_by and not validator.is_valid_group(group_by):
        group_by = None
    
    # Parsed 객체 생성 (새 구조)
    parsed = Parsed(
        metric=metric,  # type: ignore
        column=column,
        group_by=group_by,  # type: ignore
        filters=filters,
        top_n=top_n,
        analysis_type=analysis_type,  # type: ignore
        flags=flags
    )
    
    return parsed
