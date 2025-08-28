#!/bin/bash

echo "🚀 Git 업로드 준비 중..."

# 1. Python 캐시 제거
echo "1. Python 캐시 파일 정리..."
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyo" -delete 2>/dev/null || true

# 2. 임시 파일 제거
echo "2. 임시 파일 제거..."
find . -name "*.tmp" -delete 2>/dev/null || true
find . -name "*.temp" -delete 2>/dev/null || true
find . -name ".DS_Store" -delete 2>/dev/null || true
rm -f tag_data.pkl 2>/dev/null || true

# 3. 테스트 파일 제거
echo "3. 테스트 파일 정리..."
rm -f test_*.py viterbi_rule_integration.py 2>/dev/null || true

# 4. 포함될 파일 확인
echo "4. 포함될 주요 파일들:"
echo "   📦 Pickle 파일들:"
ls -lh data/pickles/*.pkl.gz 2>/dev/null | awk '{print "      " $9 " (" $5 ")"}'
echo "   ⚙️  설정 파일들:"
ls -lh config/*.json 2>/dev/null | awk '{print "      " $9}'

# 5. 제외될 파일 확인
echo "5. 제외될 파일들 확인:"
echo "   🚫 Excel 파일: $(find . -name "*.xlsx" -o -name "*.xls" | wc -l)개"
echo "   🚫 DB 파일: $(find . -name "*.db" | wc -l)개"
echo "   🚫 Python 캐시: 제거됨"

# 6. Git 상태
echo "6. Git 상태:"
git status --short

echo ""
echo "✅ 준비 완료! 다음 명령어로 커밋하세요:"
echo "   git add ."
echo "   git commit -m \"커밋 메시지\""
echo "   git push"