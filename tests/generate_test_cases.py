"""
질문 타입별 테스트 케이스 생성 스크립트
200개 질문을 8개 타입으로 분류하여 생성
"""
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_FILE = PROJECT_ROOT / "tests" / "questions.jsonl"

# 질문 타입별 테스트 케이스 정의
TEST_CASES = {
    # 타입 1: 단일 집계 (30개)
    "single_agg": [
        {"q": "챔버 압력 평균", "expect": {"metric": "avg", "column": "pressact", "analysis_type": "ranking"}},
        {"q": "압력 최대", "expect": {"metric": "max", "column": "pressact", "analysis_type": "ranking"}},
        {"q": "압력 최소", "expect": {"metric": "min", "column": "pressact", "analysis_type": "ranking"}},
        {"q": "압력 표준편차", "expect": "std"},
        {"q": "pressact 평균", "expect": {"metric": "avg", "column": "pressact", "analysis_type": "ranking"}},
        {"q": "pressact 최대", "expect": {"metric": "max", "column": "pressact", "analysis_type": "ranking"}},
        {"q": "vg11 평균", "expect": {"metric": "avg", "column": "vg11", "analysis_type": "ranking"}},
        {"q": "vg11 표준편차", "expect": {"metric": "std", "column": "vg11", "analysis_type": "ranking"}},
        {"q": "vg12 최대", "expect": {"metric": "max", "column": "vg12", "analysis_type": "ranking"}},
        {"q": "vg13 최소", "expect": {"metric": "min", "column": "vg13", "analysis_type": "ranking"}},
        {"q": "apcvalvemon 평균", "expect": {"metric": "avg", "column": "apcvalvemon", "analysis_type": "ranking"}},
        {"q": "질소 유량 평균", "expect": {"metric": "avg", "column": "mfcmon_n2_1", "analysis_type": "ranking"}},
        {"q": "n2 유량 최대", "expect": {"metric": "max", "column": "mfcmon_n2_1", "analysis_type": "ranking"}},
        {"q": "nh3 유량 평균", "expect": {"metric": "avg", "column": "mfcmon_n2_1", "analysis_type": "ranking"}},
        {"q": "암모니아 유량 최대", "expect": {"metric": "max", "column": "mfcmon_nh3", "analysis_type": "ranking"}},
        {"q": "상부 온도 평균", "expect": {"metric": "avg", "column": "tempact_u", "analysis_type": "ranking"}},
        {"q": "중앙 온도 최대", "expect": {"metric": "max", "column": "tempact_c", "analysis_type": "ranking"}},
        {"q": "압력 중앙값", "expect": {"metric": "p50", "column": "pressact", "analysis_type": "ranking"}},
        {"q": "압력 95퍼센타일", "expect": {"metric": "p95", "column": "pressact", "analysis_type": "ranking"}},
        {"q": "압력 결측률", "expect": {"metric": "null_ratio", "column": "pressact", "analysis_type": "ranking"}},
        {"q": "진공 평균", "expect": {"metric": "avg", "column": "pressact", "analysis_type": "ranking"}},
        {"q": "chamber pressure average", "expect": {"metric": "avg", "column": "pressact", "analysis_type": "ranking"}},
        {"q": "pressure max", "expect": {"metric": "max", "column": "pressact", "analysis_type": "ranking"}},
        {"q": "압력 개수", "expect": {"metric": "count", "column": "pressact", "analysis_type": "ranking"}},
        {"q": "pressact count", "expect": {"metric": "count", "column": "pressact", "analysis_type": "ranking"}},
        {"q": "vg11 개수", "expect": {"metric": "count", "column": "vg11", "analysis_type": "ranking"}},
        {"q": "압력 설정값 평균", "expect": {"metric": "avg", "column": "pressset", "analysis_type": "ranking"}},
        {"q": "pressset 최대", "expect": {"metric": "max", "column": "pressset", "analysis_type": "ranking"}},
        {"q": "apc 밸브 설정 평균", "expect": {"metric": "avg", "column": "apcvalveset", "analysis_type": "ranking"}},
        {"q": "게이지11 압력 평균", "expect": {"metric": "avg", "column": "vg11", "analysis_type": "ranking"}},
    ],
    
    # 타입 2: group by step (30개)
    "group_by_step": [
        {"q": "스텝별 pressact 평균", "expect": {"metric": "avg", "column": "pressact", "group_by": "step_name", "analysis_type": "group_profile"}},
        {"q": "단계별 압력 평균", "expect": {"metric": "avg", "column": "pressact", "group_by": "step_name", "analysis_type": "group_profile"}},
        {"q": "스텝별 압력 최대", "expect": {"metric": "max", "column": "pressact", "group_by": "step_name", "analysis_type": "group_profile"}},
        {"q": "단계별 vg11 평균", "expect": {"metric": "avg", "column": "vg11", "group_by": "step_name", "analysis_type": "group_profile"}},
        {"q": "스텝별 질소 유량 평균", "expect": {"metric": "avg", "column": "mfcmon_n2_1", "group_by": "step_name", "analysis_type": "group_profile"}},
        {"q": "standard_trace_001 스텝별 pressact 평균", "expect": {"metric": "avg", "column": "pressact", "group_by": "step_name", "filters": {"trace_id": "standard_trace_001"}, "analysis_type": "group_profile"}},
        {"q": "standard_trace_002 단계별 압력 최대", "expect": {"metric": "max", "column": "pressact", "group_by": "step_name", "filters": {"trace_id": "standard_trace_002"}, "analysis_type": "group_profile"}},
        {"q": "스텝별 pressact 평균 top10", "expect": {"metric": "avg", "column": "pressact", "group_by": "step_name", "top_n": 10, "analysis_type": "ranking"}},
        {"q": "단계별 압력 평균 상위 5개", "expect": {"metric": "avg", "column": "pressact", "group_by": "step_name", "top_n": 5, "analysis_type": "ranking"}},
        {"q": "스텝별 vg11 표준편차", "expect": {"metric": "std", "column": "vg11", "group_by": "step_name", "analysis_type": "group_profile"}},
        {"q": "step별 pressact 평균", "expect": {"metric": "avg", "column": "pressact", "group_by": "step_name", "analysis_type": "group_profile"}},
        {"q": "각 단계별 압력 평균", "expect": {"metric": "avg", "column": "pressact", "group_by": "step_name", "analysis_type": "group_profile"}},
        {"q": "스텝별 apcvalvemon 평균", "expect": {"metric": "avg", "column": "apcvalvemon", "group_by": "step_name", "analysis_type": "group_profile"}},
        {"q": "단계별 온도 평균", "expect": {"metric": "avg", "column": "tempact_u", "group_by": "step_name", "analysis_type": "group_profile"}},
        {"q": "스텝별 pressact 개수", "expect": {"metric": "count", "column": "pressact", "group_by": "step_name", "analysis_type": "group_profile"}},
        {"q": "2024-01-01부터 스텝별 압력 평균", "expect": {"metric": "avg", "column": "pressact", "group_by": "step_name", "filters": {"date_start": "2024-01-01"}, "analysis_type": "group_profile"}},
        {"q": "standard_trace_001과 standard_trace_002 스텝별 압력 비교", "expect": {"metric": "avg", "column": "pressact", "group_by": "step_name", "filters": {"trace_ids": ["standard_trace_001", "standard_trace_002"]}, "flags": {"is_trace_compare": True}, "analysis_type": "comparison"}},
        {"q": "스텝별 pressact 평균은 높은거 10개", "expect": {"metric": "avg", "column": "pressact", "group_by": "step_name", "top_n": 10, "analysis_type": "ranking"}},
        {"q": "단계별 압력 최소값", "expect": {"metric": "min", "column": "pressact", "group_by": "step_name", "analysis_type": "group_profile"}},
        {"q": "스텝별 vg12 최대", "expect": {"metric": "max", "column": "vg12", "group_by": "step_name", "analysis_type": "group_profile"}},
        {"q": "각 스텝에서 pressact 평균", "expect": {"metric": "avg", "column": "pressact", "group_by": "step_name", "analysis_type": "group_profile"}},
        {"q": "단계별 질소 유량 최대", "expect": {"metric": "max", "column": "mfcmon_n2_1", "group_by": "step_name", "analysis_type": "group_profile"}},
        {"q": "스텝별 암모니아 유량 평균", "expect": {"metric": "avg", "column": "mfcmon_nh3", "group_by": "step_name", "analysis_type": "group_profile"}},
        {"q": "standard_trace_003 스텝별 vg11 평균", "expect": {"metric": "avg", "column": "vg11", "group_by": "step_name", "filters": {"trace_id": "standard_trace_003"}, "analysis_type": "group_profile"}},
        {"q": "스텝별 pressact 중앙값", "expect": {"metric": "p50", "column": "pressact", "group_by": "step_name", "analysis_type": "group_profile"}},
        {"q": "단계별 압력 95퍼센타일", "expect": {"metric": "p95", "column": "pressact", "group_by": "step_name", "analysis_type": "group_profile"}},
        {"q": "스텝별 pressact 결측률", "expect": {"metric": "null_ratio", "column": "pressact", "group_by": "step_name", "analysis_type": "group_profile"}},
        {"q": "각 단계에서 vg13 평균", "expect": {"metric": "avg", "column": "vg13", "group_by": "step_name", "analysis_type": "group_profile"}},
        {"q": "스텝별 apc 밸브 모니터 평균", "expect": {"metric": "avg", "column": "apcvalvemon", "group_by": "step_name", "analysis_type": "group_profile"}},
        {"q": "단계별 상부 온도 최대", "expect": {"metric": "max", "column": "tempact_u", "group_by": "step_name", "analysis_type": "group_profile"}},
    ],
    
    # 타입 3: group by trace (30개)
    "group_by_trace": [
        {"q": "공정별 pressact 평균 top5", "expect": {"metric": "avg", "column": "pressact", "group_by": "trace_id", "top_n": 5, "analysis_type": "ranking"}},
        {"q": "공정별 압력 평균", "expect": {"metric": "avg", "column": "pressact", "group_by": "trace_id", "analysis_type": "group_profile"}},
        {"q": "공정별 압력 최대", "expect": {"metric": "max", "column": "pressact", "group_by": "trace_id", "analysis_type": "group_profile"}},
        {"q": "공정별 vg11 평균 top10", "expect": {"metric": "avg", "column": "vg11", "group_by": "trace_id", "top_n": 10, "analysis_type": "ranking"}},
        {"q": "공정별 압력 평균은 높은거 5개 알려주세요", "expect": {"metric": "avg", "column": "pressact", "group_by": "trace_id", "top_n": 5, "analysis_type": "ranking"}},
        {"q": "trace별 pressact 평균", "expect": {"metric": "avg", "column": "pressact", "group_by": "trace_id", "analysis_type": "group_profile"}},
        {"q": "각 공정에서 압력 평균", "expect": {"metric": "avg", "column": "pressact", "group_by": "trace_id", "analysis_type": "group_profile"}},
        {"q": "공정별 질소 유량 평균 top3", "expect": {"metric": "avg", "column": "mfcmon_n2_1", "group_by": "trace_id", "top_n": 3, "analysis_type": "ranking"}},
        {"q": "공정별 암모니아 유량 최대", "expect": {"metric": "max", "column": "mfcmon_nh3", "group_by": "trace_id", "analysis_type": "group_profile"}},
        {"q": "공정별 온도 평균", "expect": {"metric": "avg", "column": "tempact_u", "group_by": "trace_id", "analysis_type": "group_profile"}},
        {"q": "공정별 pressact 표준편차", "expect": {"metric": "std", "column": "pressact", "group_by": "trace_id", "analysis_type": "group_profile"}},
        {"q": "공정별 vg12 최소", "expect": {"metric": "min", "column": "vg12", "group_by": "trace_id", "analysis_type": "group_profile"}},
        {"q": "공정별 apcvalvemon 평균 top7", "expect": {"metric": "avg", "column": "apcvalvemon", "group_by": "trace_id", "top_n": 7, "analysis_type": "ranking"}},
        {"q": "각 공정의 압력 평균", "expect": {"metric": "avg", "column": "pressact", "group_by": "trace_id", "analysis_type": "group_profile"}},
        {"q": "공정별 pressact 개수", "expect": {"metric": "count", "column": "pressact", "group_by": "trace_id", "analysis_type": "group_profile"}},
        {"q": "trace별 vg11 최대", "expect": {"metric": "max", "column": "vg11", "group_by": "trace_id", "analysis_type": "group_profile"}},
        {"q": "공정별 압력 중앙값", "expect": {"metric": "p50", "column": "pressact", "group_by": "trace_id", "analysis_type": "group_profile"}},
        {"q": "공정별 pressact 95퍼센타일", "expect": {"metric": "p95", "column": "pressact", "group_by": "trace_id", "analysis_type": "group_profile"}},
        {"q": "공정별 압력 결측률", "expect": {"metric": "null_ratio", "column": "pressact", "group_by": "trace_id", "analysis_type": "group_profile"}},
        {"q": "공정별 질소 유량 최소", "expect": {"metric": "min", "column": "mfcmon_n2_1", "group_by": "trace_id", "analysis_type": "group_profile"}},
        {"q": "각 trace에서 pressact 평균", "expect": {"metric": "avg", "column": "pressact", "group_by": "trace_id", "analysis_type": "group_profile"}},
        {"q": "공정별 vg13 평균 top15", "expect": {"metric": "avg", "column": "vg13", "group_by": "trace_id", "top_n": 15, "analysis_type": "ranking"}},
        {"q": "공정별 상부 온도 최대", "expect": {"metric": "max", "column": "tempact_u", "group_by": "trace_id", "analysis_type": "group_profile"}},
        {"q": "공정별 중앙 온도 평균", "expect": {"metric": "avg", "column": "tempact_c", "group_by": "trace_id", "analysis_type": "group_profile"}},
        {"q": "공정별 apc 밸브 설정 평균", "expect": {"metric": "avg", "column": "apcvalveset", "group_by": "trace_id", "analysis_type": "group_profile"}},
        {"q": "공정별 pressact 평균 상위 20개", "expect": {"metric": "avg", "column": "pressact", "group_by": "trace_id", "top_n": 20, "analysis_type": "ranking"}},
        {"q": "trace별 압력 최대 top5", "expect": {"metric": "max", "column": "pressact", "group_by": "trace_id", "top_n": 5, "analysis_type": "ranking"}},
        {"q": "공정별 vg11 표준편차 top10", "expect": {"metric": "std", "column": "vg11", "group_by": "trace_id", "top_n": 10, "analysis_type": "ranking"}},
        {"q": "각 공정의 질소 유량 평균", "expect": {"metric": "avg", "column": "mfcmon_n2_1", "group_by": "trace_id", "analysis_type": "group_profile"}},
        {"q": "공정별 암모니아 유량 평균 top8", "expect": {"metric": "avg", "column": "mfcmon_nh3", "group_by": "trace_id", "top_n": 8, "analysis_type": "ranking"}},
    ],
    
    # 타입 4: 비교 (20개)
    "comparison": [
        {"q": "standard_trace_001과 standard_trace_002 pressact 비교", "expect": {"metric": "avg", "column": "pressact", "filters": {"trace_ids": ["standard_trace_001", "standard_trace_002"]}, "flags": {"is_trace_compare": True}, "analysis_type": "comparison"}},
        {"q": "standard_trace_001 vs standard_trace_002 압력 비교", "expect": {"metric": "avg", "column": "pressact", "filters": {"trace_ids": ["standard_trace_001", "standard_trace_002"]}, "flags": {"is_trace_compare": True}, "analysis_type": "comparison"}},
        {"q": "trace1과 trace2 pressact 차이", "expect": {"metric": "avg", "column": "pressact", "flags": {"is_trace_compare": True}, "analysis_type": "comparison"}},
        {"q": "standard_trace_001과 standard_trace_003 vg11 비교", "expect": {"metric": "avg", "column": "vg11", "filters": {"trace_ids": ["standard_trace_001", "standard_trace_003"]}, "flags": {"is_trace_compare": True}, "analysis_type": "comparison"}},
        {"q": "두 공정의 압력 비교", "expect": {"metric": "avg", "column": "pressact", "flags": {"is_trace_compare": True}, "analysis_type": "comparison"}},
        {"q": "standard_trace_002와 standard_trace_003 질소 유량 비교", "expect": {"metric": "avg", "column": "mfcmon_n2_1", "filters": {"trace_ids": ["standard_trace_002", "standard_trace_003"]}, "flags": {"is_trace_compare": True}, "analysis_type": "comparison"}},
        {"q": "trace1 trace2 pressact 차이", "expect": {"metric": "avg", "column": "pressact", "flags": {"is_trace_compare": True}, "analysis_type": "comparison"}},
        {"q": "standard_trace_001과 standard_trace_002 스텝별 압력 비교", "expect": {"metric": "avg", "column": "pressact", "group_by": "step_name", "filters": {"trace_ids": ["standard_trace_001", "standard_trace_002"]}, "flags": {"is_trace_compare": True}, "analysis_type": "comparison"}},
        {"q": "두 공정의 vg11 차이", "expect": {"metric": "avg", "column": "vg11", "flags": {"is_trace_compare": True}, "analysis_type": "comparison"}},
        {"q": "standard_trace_001 vs standard_trace_002 온도 비교", "expect": {"metric": "avg", "column": "tempact_u", "filters": {"trace_ids": ["standard_trace_001", "standard_trace_002"]}, "flags": {"is_trace_compare": True}, "analysis_type": "comparison"}},
        {"q": "trace1과 trace2 apcvalvemon 비교", "expect": {"metric": "avg", "column": "apcvalvemon", "flags": {"is_trace_compare": True}, "analysis_type": "comparison"}},
        {"q": "두 공정의 암모니아 유량 차이", "expect": {"metric": "avg", "column": "mfcmon_nh3", "flags": {"is_trace_compare": True}, "analysis_type": "comparison"}},
        {"q": "standard_trace_001과 standard_trace_003 pressact 비교", "expect": {"metric": "avg", "column": "pressact", "filters": {"trace_ids": ["standard_trace_001", "standard_trace_003"]}, "flags": {"is_trace_compare": True}, "analysis_type": "comparison"}},
        {"q": "trace1 trace2 vg12 차이", "expect": {"metric": "avg", "column": "vg12", "flags": {"is_trace_compare": True}, "analysis_type": "comparison"}},
        {"q": "standard_trace_002와 standard_trace_003 스텝별 vg11 비교", "expect": {"metric": "avg", "column": "vg11", "group_by": "step_name", "filters": {"trace_ids": ["standard_trace_002", "standard_trace_003"]}, "flags": {"is_trace_compare": True}, "analysis_type": "comparison"}},
        {"q": "두 공정의 압력 설정값 비교", "expect": {"metric": "avg", "column": "pressset", "flags": {"is_trace_compare": True}, "analysis_type": "comparison"}},
        {"q": "trace1과 trace2 중앙 온도 비교", "expect": {"metric": "avg", "column": "tempact_c", "flags": {"is_trace_compare": True}, "analysis_type": "comparison"}},
        {"q": "standard_trace_001 vs standard_trace_002 vg13 차이", "expect": {"metric": "avg", "column": "vg13", "filters": {"trace_ids": ["standard_trace_001", "standard_trace_002"]}, "flags": {"is_trace_compare": True}, "analysis_type": "comparison"}},
        {"q": "두 공정의 질소 유량 비교", "expect": {"metric": "avg", "column": "mfcmon_n2_1", "flags": {"is_trace_compare": True}, "analysis_type": "comparison"}},
        {"q": "trace1 trace2 상부 온도 차이", "expect": {"metric": "avg", "column": "tempact_u", "flags": {"is_trace_compare": True}, "analysis_type": "comparison"}},
    ],
    
    # 타입 5: 시간 집계 (20개)
    "temporal": [
        {"q": "pressact 일별 평균", "expect": {"metric": "avg", "column": "pressact", "group_by": "date", "analysis_type": "group_profile"}},
        {"q": "압력 일별 최대", "expect": {"metric": "max", "column": "pressact", "group_by": "date", "analysis_type": "group_profile"}},
        {"q": "pressact 시간별 평균", "expect": {"metric": "avg", "column": "pressact", "group_by": "hour", "analysis_type": "group_profile"}},
        {"q": "압력 시간별 최대", "expect": {"metric": "max", "column": "pressact", "group_by": "hour", "analysis_type": "group_profile"}},
        {"q": "vg11 일별 평균", "expect": {"metric": "avg", "column": "vg11", "group_by": "date", "analysis_type": "group_profile"}},
        {"q": "질소 유량 시간별 평균", "expect": {"metric": "avg", "column": "mfcmon_n2_1", "group_by": "hour", "analysis_type": "group_profile"}},
        {"q": "일별 pressact 최소", "expect": {"metric": "min", "column": "pressact", "group_by": "date", "analysis_type": "group_profile"}},
        {"q": "시간별 압력 표준편차", "expect": {"metric": "std", "column": "pressact", "group_by": "hour", "analysis_type": "group_profile"}},
        {"q": "2024-01-01부터 pressact 일별 평균", "expect": {"metric": "avg", "column": "pressact", "group_by": "date", "filters": {"date_start": "2024-01-01"}, "analysis_type": "group_profile"}},
        {"q": "2024-01-01부터 2024-01-31까지 압력 일별 평균", "expect": {"metric": "avg", "column": "pressact", "group_by": "date", "filters": {"date_start": "2024-01-01", "date_end": "2024-01-31"}, "analysis_type": "group_profile"}},
        {"q": "일별 vg12 최대", "expect": {"metric": "max", "column": "vg12", "group_by": "date", "analysis_type": "group_profile"}},
        {"q": "시간별 암모니아 유량 평균", "expect": {"metric": "avg", "column": "mfcmon_nh3", "group_by": "hour", "analysis_type": "group_profile"}},
        {"q": "pressact 일별 중앙값", "expect": {"metric": "p50", "column": "pressact", "group_by": "date", "analysis_type": "group_profile"}},
        {"q": "압력 시간별 95퍼센타일", "expect": {"metric": "p95", "column": "pressact", "group_by": "hour", "analysis_type": "group_profile"}},
        {"q": "일별 온도 평균", "expect": {"metric": "avg", "column": "tempact_u", "group_by": "date", "analysis_type": "group_profile"}},
        {"q": "시간별 apcvalvemon 최대", "expect": {"metric": "max", "column": "apcvalvemon", "group_by": "hour", "analysis_type": "group_profile"}},
        {"q": "2024-01-15부터 pressact 시간별 평균", "expect": {"metric": "avg", "column": "pressact", "group_by": "hour", "filters": {"date_start": "2024-01-15"}, "analysis_type": "group_profile"}},
        {"q": "일별 vg13 표준편차", "expect": {"metric": "std", "column": "vg13", "group_by": "date", "analysis_type": "group_profile"}},
        {"q": "시간별 질소 유량 최소", "expect": {"metric": "min", "column": "mfcmon_n2_1", "group_by": "hour", "analysis_type": "group_profile"}},
        {"q": "일별 pressact 개수", "expect": {"metric": "count", "column": "pressact", "group_by": "date", "analysis_type": "group_profile"}},
    ],
    
    # 타입 6: 필터 (20개)
    "filter": [
        {"q": "standard_trace_001 step=STANDBY pressact 최대", "expect": {"metric": "max", "column": "pressact", "filters": {"trace_id": "standard_trace_001", "step_name": "STANDBY"}}},
        {"q": "standard_trace_001 STANDBY 단계 pressact 평균", "expect": {"metric": "avg", "column": "pressact", "filters": {"trace_id": "standard_trace_001", "step_name": "STANDBY"}}},
        {"q": "standard_trace_002 B.FILL pressact 최대", "expect": {"metric": "max", "column": "pressact", "filters": {"trace_id": "standard_trace_002", "step_name": "B.FILL"}}},
        {"q": "2024-01-01부터 pressact 평균", "expect": {"metric": "avg", "column": "pressact", "filters": {"date_start": "2024-01-01"}}},
        {"q": "2024-01-01부터 2024-01-31까지 압력 평균", "expect": {"metric": "avg", "column": "pressact", "filters": {"date_start": "2024-01-01", "date_end": "2024-01-31"}}},
        {"q": "standard_trace_001 pressact 평균", "expect": {"metric": "avg", "column": "pressact", "filters": {"trace_id": "standard_trace_001"}}},
        {"q": "STANDBY 단계 pressact 최대", "expect": {"metric": "max", "column": "pressact", "filters": {"step_name": "STANDBY"}}},
        {"q": "B.FILL 스텝 vg11 평균", "expect": {"metric": "avg", "column": "vg11", "filters": {"step_name": "B.FILL"}, "analysis_type": "ranking"}},
        {"q": "standard_trace_002 PROCESS 단계 압력 최소", "expect": {"metric": "min", "column": "pressact", "filters": {"trace_id": "standard_trace_002", "step_name": "PROCESS"}}},
        {"q": "standard_trace_003 PURGE pressact 평균", "expect": {"metric": "avg", "column": "pressact", "filters": {"trace_id": "standard_trace_003", "step_name": "PURGE"}}},
        {"q": "2024-01-10부터 standard_trace_001 pressact 평균", "expect": {"metric": "avg", "column": "pressact", "filters": {"trace_id": "standard_trace_001", "date_start": "2024-01-10"}}},
        {"q": "STANDBY와 B.FILL 단계 pressact 평균", "expect": {"metric": "avg", "column": "pressact", "filters": {"step_names": ["STANDBY", "B.FILL"]}}},
        {"q": "standard_trace_001과 standard_trace_002 STANDBY pressact 비교", "expect": {"metric": "avg", "column": "pressact", "filters": {"trace_ids": ["standard_trace_001", "standard_trace_002"], "step_name": "STANDBY"}, "flags": {"is_trace_compare": True}, "analysis_type": "comparison"}},
        {"q": "B.UP 단계 vg12 최대", "expect": {"metric": "max", "column": "vg12", "filters": {"step_name": "B.UP"}}},
        {"q": "B.DOWN 스텝 질소 유량 평균", "expect": {"metric": "avg", "column": "mfcmon_n2_1", "filters": {"step_name": "B.DOWN"}}},
        {"q": "2024-01-20까지 pressact 평균", "expect": {"metric": "avg", "column": "pressact", "filters": {"date_end": "2024-01-20"}}},
        {"q": "standard_trace_001 2024-01-01부터 2024-01-15까지 압력 최대", "expect": {"metric": "max", "column": "pressact", "filters": {"trace_id": "standard_trace_001", "date_start": "2024-01-01", "date_end": "2024-01-15"}}},
        {"q": "PROCESS와 PURGE 단계 vg11 평균", "expect": {"metric": "avg", "column": "vg11", "filters": {"step_names": ["PROCESS", "PURGE"]}}},
        {"q": "standard_trace_002 B.FILL4 pressact 표준편차", "expect": {"metric": "std", "column": "pressact", "filters": {"trace_id": "standard_trace_002", "step_name": "B.FILL4"}}},
        {"q": "2024-01-05부터 2024-01-10까지 standard_trace_003 pressact 평균", "expect": {"metric": "avg", "column": "pressact", "filters": {"trace_id": "standard_trace_003", "date_start": "2024-01-05", "date_end": "2024-01-10"}}},
    ],
    
    # 타입 7: 공정지표 - 이상치 (15개)
    "outlier": [
        {"q": "pressact 이상치 top5", "expect": {"metric": "avg", "column": "pressact", "top_n": 5, "flags": {"is_outlier": True}, "analysis_type": "stability"}},
        {"q": "압력 이상치", "expect": {"metric": "avg", "column": "pressact", "flags": {"is_outlier": True}, "analysis_type": "stability"}},
        {"q": "vg11 이상치 top10", "expect": {"metric": "avg", "column": "vg11", "top_n": 10, "flags": {"is_outlier": True}, "analysis_type": "stability"}},
        {"q": "질소 유량 이상치", "expect": {"metric": "avg", "column": "mfcmon_n2_1", "flags": {"is_outlier": True}, "analysis_type": "stability"}},
        {"q": "pressact 이상치 상위 3개", "expect": {"metric": "avg", "column": "pressact", "top_n": 3, "flags": {"is_outlier": True}, "analysis_type": "stability"}},
        {"q": "standard_trace_001 pressact 이상치", "expect": {"metric": "avg", "column": "pressact", "filters": {"trace_id": "standard_trace_001"}, "flags": {"is_outlier": True}, "analysis_type": "stability"}},
        {"q": "STANDBY 단계 pressact 이상치 top5", "expect": {"metric": "avg", "column": "pressact", "filters": {"step_name": "STANDBY"}, "top_n": 5, "flags": {"is_outlier": True}, "analysis_type": "stability"}},
        {"q": "vg12 이상치", "expect": {"metric": "avg", "column": "vg12", "flags": {"is_outlier": True}, "analysis_type": "stability"}},
        {"q": "압력 이상치 공정 top10", "expect": {"metric": "avg", "column": "pressact", "top_n": 10, "flags": {"is_outlier": True}, "analysis_type": "stability"}},
        {"q": "암모니아 유량 이상치", "expect": {"metric": "avg", "column": "mfcmon_nh3", "flags": {"is_outlier": True}, "analysis_type": "stability"}},
        {"q": "pressact 이상치 top20", "expect": {"metric": "avg", "column": "pressact", "top_n": 20, "flags": {"is_outlier": True}, "analysis_type": "stability"}},
        {"q": "온도 이상치", "expect": {"metric": "avg", "column": "tempact_u", "flags": {"is_outlier": True}, "analysis_type": "stability"}},
        {"q": "standard_trace_002 vg11 이상치 top7", "expect": {"metric": "avg", "column": "vg11", "filters": {"trace_id": "standard_trace_002"}, "top_n": 7, "flags": {"is_outlier": True}, "analysis_type": "stability"}},
        {"q": "B.FILL 단계 pressact 이상치", "expect": {"metric": "avg", "column": "pressact", "filters": {"step_name": "B.FILL"}, "flags": {"is_outlier": True}, "analysis_type": "stability"}},
        {"q": "apcvalvemon 이상치 top15", "expect": {"metric": "avg", "column": "apcvalvemon", "top_n": 15, "flags": {"is_outlier": True}, "analysis_type": "stability"}},
    ],
    
    # 타입 8: 공정지표 - overshoot/dwell/stable (15개)
    "process_metrics": [
        {"q": "pressact overshoot top10", "expect": {"metric": "avg", "column": "pressact", "top_n": 10, "flags": {"is_overshoot": True}, "analysis_type": "stability"}},
        {"q": "압력 오버슈트", "expect": {"metric": "avg", "column": "pressact", "flags": {"is_overshoot": True}, "analysis_type": "stability"}},
        {"q": "pressact overshoot top5", "expect": {"metric": "avg", "column": "pressact", "top_n": 5, "flags": {"is_overshoot": True}, "analysis_type": "stability"}},
        {"q": "vg11 오버슈트", "expect": {"metric": "avg", "column": "vg11", "flags": {"is_overshoot": True}, "analysis_type": "stability"}},
        {"q": "pressact 체류시간", "expect": {"metric": "avg", "column": "pressact", "flags": {"is_dwell_time": True}, "analysis_type": "stability"}},
        {"q": "압력 체류 시간", "expect": {"metric": "avg", "column": "pressact", "flags": {"is_dwell_time": True}, "analysis_type": "stability"}},
        {"q": "standard_trace_001 pressact 체류시간", "expect": {"metric": "avg", "column": "pressact", "filters": {"trace_id": "standard_trace_001"}, "flags": {"is_dwell_time": True}, "analysis_type": "stability"}},
        {"q": "pressact 안정화 구간 평균", "expect": {"metric": "avg", "column": "pressact", "flags": {"is_stable_avg": True}, "analysis_type": "stability"}},
        {"q": "압력 안정 평균", "expect": {"metric": "avg", "column": "pressact", "flags": {"is_stable_avg": True}, "analysis_type": "stability"}},
        {"q": "STANDBY 단계 pressact overshoot", "expect": {"metric": "avg", "column": "pressact", "filters": {"step_name": "STANDBY"}, "flags": {"is_overshoot": True}, "analysis_type": "stability"}},
        {"q": "pressact overshoot 상위 7개", "expect": {"metric": "avg", "column": "pressact", "top_n": 7, "flags": {"is_overshoot": True}, "analysis_type": "stability"}},
        {"q": "vg12 체류시간 top10", "expect": {"metric": "avg", "column": "vg12", "top_n": 10, "flags": {"is_dwell_time": True}, "analysis_type": "stability"}},
        {"q": "standard_trace_002 pressact 안정화 평균", "expect": {"metric": "avg", "column": "pressact", "filters": {"trace_id": "standard_trace_002"}, "flags": {"is_stable_avg": True}, "analysis_type": "stability"}},
        {"q": "B.FILL 단계 pressact overshoot top5", "expect": {"metric": "avg", "column": "pressact", "filters": {"step_name": "B.FILL"}, "top_n": 5, "flags": {"is_overshoot": True}, "analysis_type": "stability"}},
        {"q": "pressact 안정 구간 평균", "expect": {"metric": "avg", "column": "pressact", "flags": {"is_stable_avg": True}, "analysis_type": "stability"}},
    ],
    
    # 타입 9: Top N 변형 (10개)
    "top_n": [
        {"q": "상위 3개", "expect": {"top_n": 3}},
        {"q": "3개 알려주세요", "expect": {"top_n": 3}},
        {"q": "top5", "expect": {"top_n": 5}},
        {"q": "top 10", "expect": {"top_n": 10}},
        {"q": "상위 5개", "expect": {"top_n": 5}},
        {"q": "10개만", "expect": {"top_n": 10}},
        {"q": "압력 평균 top7", "expect": {"metric": "avg", "column": "pressact", "top_n": 7, "analysis_type": "ranking"}},
        {"q": "vg11 최대 top15", "expect": {"metric": "max", "column": "vg11", "top_n": 15, "analysis_type": "ranking"}},
        {"q": "질소 유량 평균 상위 20개", "expect": {"metric": "avg", "column": "mfcmon_n2_1", "top_n": 20, "analysis_type": "ranking"}},
        {"q": "pressact 평균 top3", "expect": {"metric": "avg", "column": "pressact", "top_n": 3, "analysis_type": "ranking"}},
    ],
}


def generate_questions_file():
    """질문 파일 생성"""
    all_cases = []
    
    for category, cases in TEST_CASES.items():
        for case in cases:
            # expect가 문자열인 경우 (예: "std") 처리
            if isinstance(case["expect"], str):
                # 간단한 필드만 있는 경우 처리
                if case["expect"] == "std":
                    case["expect"] = {"metric": "std", "column": "pressact", "analysis_type": "ranking"}
                elif case["expect"] == "date_range":
                    case["expect"] = {"metric": "avg", "column": "pressact", "filters": {"date_start": "2024-01-01", "date_end": "2024-01-31"}}
            all_cases.append(case)
    
    # JSONL 형식으로 저장
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for case in all_cases:
            f.write(json.dumps(case, ensure_ascii=False) + '\n')
    
    print(f"✅ {len(all_cases)}개 테스트 케이스를 {OUTPUT_FILE}에 생성했습니다.")
    print(f"\n질문 타입별 통계:")
    for category, cases in TEST_CASES.items():
        print(f"  - {category}: {len(cases)}개")


if __name__ == "__main__":
    generate_questions_file()

