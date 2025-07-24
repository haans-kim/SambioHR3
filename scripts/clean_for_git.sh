#!/bin/bash

echo "🧹 Git 업로드를 위한 정리 시작..."

# Python 캐시 파일 제거
echo "1. Python 캐시 파일 제거 중..."
find . -name "*.pyc" -exec rm {} + 2>/dev/null || true
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyo" -exec rm {} + 2>/dev/null || true

# 임시 파일 제거
echo "2. 임시 파일 제거 중..."
find . -name "*.tmp" -exec rm {} + 2>/dev/null || true
find . -name "*.temp" -exec rm {} + 2>/dev/null || true
find . -name ".DS_Store" -exec rm {} + 2>/dev/null || true

# 대용량 파일 확인
echo "3. 100MB 이상 파일 확인..."
find . -size +100M -type f 2>/dev/null | grep -v ".git" | while read file; do
    echo "⚠️  대용량 파일: $file ($(du -h "$file" | cut -f1))"
done

# Git 상태 확인
echo "4. Git 상태 확인..."
git status --porcelain | wc -l | xargs -I {} echo "📝 변경된 파일 수: {}"

# .gitignore 검증
echo "5. .gitignore 검증..."
git check-ignore data/pickles/*.pkl.gz >/dev/null 2>&1 && echo "✅ Pickle 파일들이 제대로 무시됨" || echo "❌ Pickle 파일 무시 설정 확인 필요"

echo "✨ 정리 완료!"