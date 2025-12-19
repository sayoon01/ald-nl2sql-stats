"""
결과 요약 생성 서비스
"""
from typing import List, Dict


def make_summary(parsed: dict, rows: list) -> str:
    """쿼리 결과를 자연어 요약으로 변환"""
    agg_kr_map = {
        "avg": "평균", "min": "최소", "max": "최대", "count": "개수",
        "std": "표준편차", "stddev": "표준편차", "p50": "중앙값", "median": "중앙값",
        "p95": "95퍼센타일", "p99": "99퍼센타일", "null_ratio": "결측률"
    }
    agg = parsed.get("agg") or parsed.get("metric", "avg")
    agg_kr = agg_kr_map.get(agg, agg)
    col = parsed.get("col") or "*"
    scope = []
    if parsed.get("trace_id"):
        scope.append(parsed["trace_id"])
    if parsed.get("step_name"):
        scope.append(f"step={parsed['step_name']}")
    scope_txt = (", ".join(scope) + " 기준 ") if scope else ""

    if not rows:
        return f"결과가 없습니다. ({scope_txt}{col} {agg_kr})"

    if parsed.get("group_by"):
        top = rows[0]
        key = parsed["group_by"]
        key_kr = "공정 ID" if key == "trace_id" else ("단계명" if key == "step_name" else key)
        
        # 요청한 top_n과 실제 반환된 개수 비교
        requested_top_n = parsed.get("top_n")
        actual_count = len(rows)
        
        if requested_top_n and actual_count < requested_top_n:
            summary = f"{scope_txt}{col} {agg_kr} ({key_kr}별 Top {requested_top_n} 요청, 실제 {actual_count}개 반환). 1위={top.get(key)}: {top.get('value')}"
            summary += f" (데이터가 {requested_top_n}개보다 적습니다)"
        else:
            summary = f"{scope_txt}{col} {agg_kr} ({key_kr}별 Top {actual_count}). 1위={top.get(key)}: {top.get('value')}"
        
        # 추가 통계 정보 (n, std, min, max)가 있으면 표시
        if "n" in top:
            summary += f" (n={top['n']})"
        if "std" in top and top.get("std"):
            summary += f" [std={top['std']}]"
        if "min_val" in top and "max_val" in top:
            summary += f" [범위: {top['min_val']} ~ {top['max_val']}]"
        return summary
    
    # trace 비교 케이스
    if parsed.get("is_trace_compare") and rows:
        top = rows[0]
        trace_ids = parsed.get("trace_ids", [])
        if len(trace_ids) >= 2:
            step_name = top.get('step_name', '')
            diff_val = top.get('diff', 0)
            trace1_avg = top.get('trace1_avg', 0)
            trace2_avg = top.get('trace2_avg', 0)
            
            # 해석 추가
            diff_str = f"{diff_val:.1f}" if isinstance(diff_val, (int, float)) else str(diff_val)
            trace1_str = f"{trace_ids[0]}"
            trace2_str = f"{trace_ids[1]}"
            
            # 해석 텍스트 생성
            interpretation = ""
            if step_name == "STANDBY":
                interpretation = "이는 대기 단계에서 진공 안정화 또는 배기 제어 차이가 있었을 가능성을 시사합니다."
            elif step_name in ["B.FILL", "B.FILL4", "B.FILL5"]:
                interpretation = "이는 충진 단계에서 압력 제어 프로파일 차이가 있었을 가능성을 시사합니다."
            elif step_name in ["B.UP", "B.DOWN"]:
                interpretation = "이는 압력 변화 단계에서 제어 속도 또는 목표값 차이가 있었을 가능성을 시사합니다."
            else:
                interpretation = "이는 해당 단계에서 공정 조건 또는 제어 파라미터 차이가 있었을 가능성을 시사합니다."
            
            summary = f"{step_name} 단계에서 trace 간 pressact 차이가 가장 큽니다 (차이: ≈{diff_str} mTorr, {trace1_str}: {trace1_avg:.1f} mTorr, {trace2_str}: {trace2_avg:.1f} mTorr). {interpretation}"
            return summary
    
    # 이상치 탐지 케이스
    if parsed.get("is_outlier"):
        if not rows:
            return "이상치가 발견되지 않았습니다. (z-score > 1.0 기준)"
        top = rows[0]
        summary = f"이상치 비율 Top {len(rows)}. 1위 trace={top.get('trace_id')}: {top.get('value')}% (n={top.get('n')}, 이상치={top.get('outlier_count')})"
        return summary

    r0 = rows[0]
    if "value" in r0:
        summary = f"{scope_txt}{col} {agg_kr}={r0['value']}"
        if "n" in r0:
            summary += f" (n={r0['n']})"
        if "std" in r0 and r0.get("std"):
            summary += f" [std={r0['std']}]"
        return summary
    if "n" in r0:
        return f"{scope_txt}{col} {agg_kr}={r0['n']}"
    return "요약 생성 실패"

