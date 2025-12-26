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
TRACE_PLACEHOLDER_RE = re.compile(r"\b(trace\s*[12]|trace1|trace2)\b", re.IGNORECASE)  # trace1, trace2 매핑용
STEP_RE = re.compile(r"step\s*[:=]\s*([a-z0-9_]+)", re.IGNORECASE)
STEP_FILTER_RE = re.compile(r"\b([A-Z0-9\.\-_]+)\s*(?:스텝|단계)\b", re.IGNORECASE)  # "B.FILL 스텝" 같은 필터
STEP_NAME_ONLY_RE = re.compile(r"\b([A-Z][A-Z0-9\.\-_]{2,})\b")  # "B.FILL", "PURGE" 같은 단독 step 이름 (최소 3자, "B." 제외)
STEP_GROUP_RE = re.compile(r"(?:스텝별|단계별|step\s*별|step\s*by\s*step)", re.IGNORECASE)  # "스텝별" 같은 그룹핑 ("별" 필수)
# top5, top 5, 상위 5, 5개, 5개 알려주세요 등 다양한 패턴 지원
TOP_RE = re.compile(r"(?:top\s*(\d+)|상위\s*(\d+)|(\d+)\s*개)", re.IGNORECASE)
DATE_RE = re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})")
# 비교 키워드
COMPARE_KEYWORDS = ["비교", "차이", "vs", "대비", "difference", "compare"]

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
            
            # 1. 키 직접 매칭 (가중치: 3.0)
            if key.lower() in text_lower:
                matched_cols.append((len(key) * 3.0, key))
            
            # 2. 동의어 매칭 (가중치: 2.5, alias 히트 우대)
            for alias in col_def.aliases:
                alias_lower = alias.lower()
                if alias_lower in text_lower:
                    # 공통명사 감점 (유량, 압력, 온도 등)
                    common_words = {"유량", "압력", "온도", "밸브", "게이지", "스텝", "단계", "공정", "트레이스"}
                    weight = 2.5
                    if alias_lower in common_words:
                        weight = 0.5  # 공통명사는 감점
                    matched_cols.append((len(alias) * weight, key))
            
            # 3. 도메인명 매칭 (가중치: 1.2)
            domain_name_lower = col_def.domain_name.lower()
            if domain_name_lower in text_lower:
                matched_cols.append((len(col_def.domain_name) * 1.2, key))
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
    
    # 가중치가 높은 매칭을 우선
    if matched_cols:
        matched_cols.sort(reverse=True)  # (점수, 컬럼명) 튜플 정렬
        
        # 여러 컬럼이 매칭되었을 때 resolution 규칙 적용
        if len(matched_cols) > 1:
            # 매칭된 모든 컬럼 후보
            candidate_cols = [col for _, col in matched_cols]
            
            # resolution 규칙으로 모호성 해결 시도
            # 구체적인 컬럼(vg11, vg12, vg13)이 있으면 pressact 제거
            specific_cols = [col for col in candidate_cols if col in ["vg11", "vg12", "vg13", "vg14", "vg15"]]
            if specific_cols and "pressact" in candidate_cols:
                # 구체적인 게이지가 있으면 pressact 제거하고 구체적인 컬럼 반환
                return specific_cols[0]
            
            # 타입 기반 tie-break: 동일 점수면 더 구체적인 컬럼(가스/MFC 계열) 우선
            top_score = matched_cols[0][0]
            top_candidates = [col for score, col in matched_cols if abs(score - top_score) < 0.1]
            if len(top_candidates) > 1:
                # MFC/가스 계열 우선
                flow_cols = [col for col in top_candidates if "mfc" in col or "nh3" in col or "n2" in col]
                if flow_cols:
                    return flow_cols[0]
            
            # resolution 규칙 적용
            top_col = matched_cols[0][1]
            resolved = resolve_column_from_text(text, top_col)
            if resolved:
                return resolved
        
        return matched_cols[0][1]
    
    return None

def _pick_group_by(text: str, validator) -> GroupBy:
    """
    그룹핑 추출 (도메인 메타데이터 기반)
    주의: "스텝별"은 group_by, "B.FILL 스텝"은 filter로 구분
    """
    groups = validator.get_all_groups()
    text_lower = text.lower()
    
    # "스텝별", "단계별" 같은 명시적 그룹핑 키워드 확인 (최우선)
    if STEP_GROUP_RE.search(text):
        # "스텝별"이 있으면 step_name 그룹핑
        return "step_name"  # type: ignore
    
    # "각 스텝에서", "각 단계에서" 같은 표현도 group_by로 처리
    if re.search(r"각\s*(?:스텝|단계)\s*(?:에서|별)", text_lower):
        return "step_name"  # type: ignore
    if re.search(r"각\s*(?:공정|trace)\s*(?:에서|별)", text_lower):
        return "trace_id"  # type: ignore
    
    # 정규화된 텍스트에서 그룹 찾기 (긴 것부터 매칭)
    matched_groups = []
    for group in groups:
        group_info = validator.get_group_info(group)
        if not group_info:
            continue
        
        label = group_info.get("label", "").lower()
        # "스텝"/"단계" 단독은 제외 (필터와 구분하기 위해)
        # "스텝별", "단계별", "공정별" 같은 "별"이 붙은 것만 group_by로 처리
        if label and label in text_lower:
            # "스텝" 또는 "단계" 단독이면 제외 (필터로 처리해야 함)
            if group == "step_name" and label in {"스텝", "단계"} and "별" not in text_lower:
                continue
            matched_groups.append((len(label), group))
        
        # 그룹명 자체도 확인 (step_name은 제외 - 필터와 충돌 방지)
        if group in text_lower and group != "step_name":
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
    """
    날짜 범위 추출
    - "2024-01-01부터" -> date_start
    - "2024-01-31까지" -> date_end
    - "2024-01-01부터 2024-01-31까지" -> 둘 다
    """
    dates = DATE_RE.findall(text)
    if not dates:
        return None, None
    
    start_date = None
    end_date = None
    
    # "부터", "부터" 키워드 확인
    has_from = "부터" in text or "from" in text.lower()
    has_to = "까지" in text or "to" in text.lower() or "~" in text
    
    if len(dates) == 1:
        # 날짜가 하나면 "부터"면 start, "까지"면 end
        date_str = "-".join([dates[0][0], dates[0][1].zfill(2), dates[0][2].zfill(2)])
        if has_from:
            start_date = date_str
        elif has_to:
            end_date = date_str
        else:
            # 키워드가 없으면 첫 번째 날짜는 start로 간주
            start_date = date_str
    elif len(dates) >= 2:
        # 날짜가 두 개면 첫 번째는 start, 두 번째는 end
        start_date = "-".join([dates[0][0], dates[0][1].zfill(2), dates[0][2].zfill(2)])
        end_date = "-".join([dates[1][0], dates[1][1].zfill(2), dates[1][2].zfill(2)])
    
    return start_date, end_date

def _pick_multiple_traces(text: str) -> List[str]:
    """
    여러 trace_id 추출 (실제 trace_id만 반환)
    - standard_trace_001 형식만 추출
    - trace1, trace2 같은 placeholder는 추출하지 않음 (토큰으로만 처리)
    """
    traces = []
    
    # 실제 trace_id 형식만 추출
    found_traces = TRACE_RE.findall(text)
    traces.extend(found_traces)
    
    return traces

def _has_trace_placeholder(text: str) -> bool:
    """
    trace1, trace2 같은 placeholder가 있는지 확인
    (실제 trace_id는 아니지만 비교 의도 표시)
    """
    return bool(TRACE_PLACEHOLDER_RE.search(text))

def _pick_multiple_steps(text: str) -> List[str]:
    """
    여러 step_name 추출
    - step=STANDBY 형식
    - "B.FILL 스텝", "STANDBY 단계" 같은 필터 형식
    - "STANDBY와 B.FILL 단계" 같은 복수 형식
    """
    steps = []
    
    # 1. step=STANDBY 형식
    for m in STEP_RE.finditer(text):
        step = m.group(1).upper()
        if step and len(step) > 1 and step not in ["STEP", "_NAME", "별"]:
            if step not in steps:
                steps.append(step)
    
    # 2. "B.FILL 스텝", "STANDBY 단계" 같은 필터 형식
    for m in STEP_FILTER_RE.finditer(text):
        step = m.group(1).upper()
        if step and len(step) > 1:
            if step not in steps:
                steps.append(step)
    
    # 3. "STANDBY와 B.FILL 단계" 같은 복수 형식 처리
    # "와", "과"로 연결된 step 이름들 추출
    step_with_and = re.findall(r"\b([A-Z0-9\.\-_]+)\s*(?:와|과)\s*([A-Z0-9\.\-_]+)\s*(?:스텝|단계)", text, re.IGNORECASE)
    for step1, step2 in step_with_and:
        if step1 and step1 not in steps:
            steps.append(step1.upper())
        if step2 and step2 not in steps:
            steps.append(step2.upper())
    
    # 4. "B.FILL", "PURGE" 같은 단독 step 이름 추출 (대문자로 시작하는 알려진 step 이름)
    # 주의: 너무 짧거나 일반적인 단어는 제외
    known_steps = ["STANDBY", "B.FILL", "B.FILL4", "PURGE", "PROCESS", "B.UP", "B.DOWN"]
    for m in STEP_NAME_ONLY_RE.finditer(text):
        step_candidate = m.group(1)
        # 알려진 step 이름이거나 대문자로 시작하는 패턴이면 추가
        if step_candidate in known_steps or (step_candidate.startswith("B.") or step_candidate in ["PURGE", "PROCESS", "STANDBY"]):
            if step_candidate not in steps:
                steps.append(step_candidate.upper())
    
    # 일관된 순서로 정렬 (알파벳 순)
    return sorted(steps)

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
    original_raw = q  # 원본 (대소문자 유지, step 필터 확인용)
    
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
    
    # Trace ID 추출 (실제 trace_id만)
    traces = _pick_multiple_traces(original)
    has_trace_placeholder = _has_trace_placeholder(original)
    
    if len(traces) == 1:
        filters["trace_id"] = traces[0]
    # 2개 이상이면 아래 비교 의도 감지에서 처리
    
    # Step Name 추출 (필터용, group_by와 구분)
    # 원본 텍스트에서 먼저 찾기 (정규화 과정에서 대문자 step 이름이 소문자로 변환될 수 있음)
    steps = _pick_multiple_steps(original_raw)
    if not steps:
        steps = _pick_multiple_steps(normalized)
    if not steps:
        steps = _pick_multiple_steps(original)
    
    # group_by가 step_name이면 step 필터는 걸지 않는다 (스텝별 집계니까)
    if group_by != "step_name":
        if steps:
            if len(steps) == 1:
                filters["step_name"] = steps[0]
            else:
                filters["step_names"] = steps
                flags["is_step_compare"] = True  # 여러 step 비교
    
    # 날짜 범위 추출
    date_start, date_end = _pick_date_range(original)
    if date_start:
        filters["date_start"] = date_start
    if date_end:
        filters["date_end"] = date_end
    
    # 비교 의도 감지 (최우선)
    has_compare_keyword = any(keyword in original for keyword in COMPARE_KEYWORDS)
    has_multiple_traces = len(traces) >= 2
    has_placeholder = has_trace_placeholder
    has_generic_compare = "두 공정" in original or "두 trace" in original.lower()
    
    # 비교 의도가 있으면 무조건 comparison
    if has_compare_keyword or has_multiple_traces or has_placeholder or has_generic_compare:
        flags["is_trace_compare"] = True
        # 실제 trace_id가 2개 이상 발견된 경우에만 trace_ids 채우기
        if has_multiple_traces:
            filters["trace_ids"] = traces
        # trace1/trace2나 "두 공정" 같은 경우는 trace_ids 채우지 않음
    
    # 특수 지표 감지
    if "이상치" in original or "outlier" in original.lower():
        flags["is_outlier"] = True
    if "체류" in original or "dwell" in original.lower():
        flags["is_dwell_time"] = True
    if "오버슈트" in original or "overshoot" in original.lower():
        flags["is_overshoot"] = True
    if "안정" in original or "stable" in original.lower():
        flags["is_stable_avg"] = True
    
    # 분석 유형 결정 (우선순위: comparison > stability > ranking > group_profile)
    # 정책: 단일 집계도 ranking으로 통일 (항상 표 형태로 반환)
    if flags.get("is_trace_compare") or flags.get("is_step_compare"):
        analysis_type = "comparison"
    elif flags.get("is_outlier") or flags.get("is_overshoot") or flags.get("is_stable_avg") or flags.get("is_dwell_time"):
        analysis_type = "stability"
    elif group_by and top_n:
        # group_by + top_n이면 ranking (상위 N개 그룹)
        analysis_type = "ranking"
    elif group_by:
        # group_by만 있으면 group_profile (모든 그룹)
        analysis_type = "group_profile"
    else:
        # 그 외는 전부 ranking (단일 집계도 ranking으로 통일)
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
    # 여러 컬럼이 매칭되었을 때 우선순위로 선택
    if column:
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
