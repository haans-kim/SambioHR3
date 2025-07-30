#!/bin/bash
# Claude Code 편집 후 훅 - API 변경사항 감지

PROJECT_ROOT=$(cd "$(dirname "$0")/.." && pwd)

echo "🔍 API 변경사항 확인 중..."

# 변경 추적 스크립트 실행
OUTPUT=$(python3 "$PROJECT_ROOT/scripts/track_changes.py" "$PROJECT_ROOT" 2>&1)

# 변경사항이 있으면 출력
if [[ $OUTPUT != *"변경사항이 없습니다"* ]]; then
    echo "$OUTPUT"
    echo ""
    echo "📝 변경사항이 문서화되었습니다: doc/changes/LATEST.md"
fi