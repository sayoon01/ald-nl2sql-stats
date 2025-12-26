#!/bin/bash
# API 테스트 스크립트

echo "=========================================="
echo "API 테스트 스크립트"
echo "=========================================="
echo ""
echo "서버가 실행 중이어야 합니다:"
echo "  uvicorn src.app:app --reload --host 0.0.0.0 --port 8000"
echo ""
read -p "서버가 실행 중입니까? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "서버를 먼저 실행해주세요."
    exit 1
fi

BASE_URL="http://127.0.0.1:8000"

echo ""
echo "=========================================="
echo "[4단계] /api/query 응답 확인"
echo "=========================================="

echo ""
echo "단일값 테스트:"
curl -s -G "${BASE_URL}/api/query" \
  --data-urlencode "q=압력 평균" \
  | python3 -m json.tool | head -n 80

echo ""
echo "그룹형 테스트:"
curl -s -G "${BASE_URL}/api/query" \
  --data-urlencode "q=스텝별 압력 평균" \
  | python3 -m json.tool | head -n 120

echo ""
echo "=========================================="
echo "[5단계] Plotly bar meta 확인"
echo "=========================================="

curl -s -G "${BASE_URL}/api/query" \
  --data-urlencode "q=스텝별 압력 평균" \
  | python3 << 'PY'
import sys, json
try:
    obj = json.load(sys.stdin)
    meta = obj.get("meta", {})
    print(f"chart: {meta.get('chart')}")
    print(f"x: {meta.get('x')}")
    print(f"y: {meta.get('y')}")
    print(f"data_rows: {len(obj.get('data', []))}")
    print(f"title: {meta.get('title')}")
    print(f"unit: {meta.get('unit')}")
except json.JSONDecodeError as e:
    print(f"JSON 파싱 오류: {e}")
    sys.exit(1)
PY

echo ""
echo "=========================================="
echo "[6단계] Matplotlib PNG endpoint 확인"
echo "=========================================="

echo "시계열 plot 테스트..."
curl -s -o /tmp/plot_test.png "${BASE_URL}/api/plot?q=$(python3 -c "import urllib.parse; print(urllib.parse.quote('압력 평균'))")" 2>/dev/null
if [ -f /tmp/plot_test.png ] && [ -s /tmp/plot_test.png ]; then
    file /tmp/plot_test.png
    echo "✅ PNG 파일 생성 성공"
    ls -lh /tmp/plot_test.png
else
    echo "❌ PNG 파일 생성 실패"
    echo "응답 확인:"
    curl -s "${BASE_URL}/api/plot?q=$(python3 -c "import urllib.parse; print(urllib.parse.quote('압력 평균'))")" | head -n 5
fi

echo ""
echo "=========================================="
echo "테스트 완료"
echo "=========================================="

