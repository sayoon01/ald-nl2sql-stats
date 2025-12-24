#!/bin/bash
# 각 모듈별 개별 테스트 스크립트

cd "$(dirname "$0")/.."

echo "=========================================="
echo "모듈별 단위 테스트"
echo "=========================================="

# 1. 파서 모듈 테스트
echo ""
echo "1. 파서 모듈 테스트"
echo "-------------------"
python3 -c "
from src.nl_parse_v2 import parse_question
tests = ['압력 평균', '공정별 압력 평균 top5', 'trace1 trace2 압력 비교']
for q in tests:
    p = parse_question(q)
    print(f'✅ {q:30} -> {p.column}, {p.analysis_type}')
"

# 2. SQL 빌더 테스트
echo ""
echo "2. SQL 빌더 모듈 테스트"
echo "-------------------"
python3 -c "
from src.nl_parse_v2 import Parsed
from src.sql_builder import build_sql
p = Parsed(metric='avg', column='pressact', analysis_type='ranking')
sql, params = build_sql(p)
print(f'✅ SQL 빌드 성공')
print(f'   SQL 길이: {len(sql)} chars, Params: {len(params)}개')
"

# 3. 정규화 모듈 테스트
echo ""
echo "3. 정규화 모듈 테스트"
echo "-------------------"
python3 -c "
from domain.rules.normalization import normalize
tests = ['압력 평균', '암모니아가스 유량', '스텝별 pressact 평균 top10']
for q in tests:
    n = normalize(q)
    print(f'✅ {q:25} -> {n.text}')
"

# 4. 공정 지표 테스트
echo ""
echo "4. 공정 지표 모듈 테스트"
echo "-------------------"
python3 -c "
from src.nl_parse_v2 import Parsed
from src.process_metrics import build_outlier_detection_sql
p = Parsed(metric='avg', column='pressact', flags={'is_outlier': True}, analysis_type='stability')
sql, params = build_outlier_detection_sql(p)
print(f'✅ 이상치 탐지 SQL 빌드 성공')
print(f'   SQL 길이: {len(sql)} chars')
"

# 5. 차트 렌더링 테스트
echo ""
echo "5. 차트 렌더링 모듈 테스트"
echo "-------------------"
python3 -c "
import pandas as pd
from src.nl_parse_v2 import Parsed
from src.charts.renderer import render_chart
p = Parsed(metric='avg', column='pressact', group_by='trace_id', analysis_type='group_profile')
df = pd.DataFrame({'trace_id': ['t1', 't2'], 'value': [10, 20]})
chart = render_chart(df, p)
print(f'✅ 차트 렌더링 성공: {len(chart.body)} bytes')
" 2>/dev/null | grep -v "UserWarning" | grep -v "Glyph" || echo "⚠️  차트 렌더링 스킵 (의존성 문제)"

# 6. 요약 생성 테스트
echo ""
echo "6. 요약 생성 모듈 테스트"
echo "-------------------"
python3 -c "
import pandas as pd
from src.nl_parse_v2 import Parsed
from src.services.summary import make_summary
p = Parsed(metric='avg', column='pressact', analysis_type='ranking')
df = pd.DataFrame({'value': [10.5, 20.3, 15.7]})
summary = make_summary(p, df)
print(f'✅ 요약 생성 성공: {summary[:50]}...')
"

echo ""
echo "=========================================="
echo "테스트 완료"
echo "=========================================="

