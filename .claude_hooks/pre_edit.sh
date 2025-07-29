#!/bin/bash
# Claude Code 편집 전 훅 - API 상태 캡처

PROJECT_ROOT=$(cd "$(dirname "$0")/.." && pwd)

# 변경 추적 스크립트 실행 (조용히)
python3 "$PROJECT_ROOT/scripts/track_changes.py" "$PROJECT_ROOT" > /dev/null 2>&1