#!/bin/bash
# DB 복원 스크립트

set -e

# 설정
ENCRYPTED_DIR="data/encrypted_chunks"
OUTPUT_PATH="data/sambio_human_restored.db"
BACKUP_BRANCH="db-backup"

echo "🔓 SambioHR2 DB 복원 시작..."

# 1. 백업 브랜치에서 암호화 파일 가져오기
echo "1. 백업 브랜치에서 파일 가져오는 중..."
git checkout $BACKUP_BRANCH
git pull origin $BACKUP_BRANCH

# 2. 복호화 및 병합
echo "2. DB 파일 복호화 중..."
python scripts/encrypt_db.py decrypt --encrypted-dir "$ENCRYPTED_DIR" --output "$OUTPUT_PATH"

# 3. 원래 브랜치로 복귀
git checkout main

echo "✅ 복원 완료!"
echo "   복원된 파일: $OUTPUT_PATH"
echo "   원본 파일과 교체하려면:"
echo "   mv $OUTPUT_PATH data/sambio_human.db"