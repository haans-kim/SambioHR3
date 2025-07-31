#!/bin/bash
# DB 백업 및 GitHub 업로드 스크립트

set -e

# 설정
DB_PATH="data/sambio_human.db"
CHUNK_SIZE=50  # MB
ENCRYPTED_DIR="data/encrypted_chunks"
BACKUP_BRANCH="db-backup"

echo "🔐 SambioHR2 DB 백업 시작..."

# 1. 암호화 및 분할
echo "1. DB 파일 암호화 중..."
python scripts/encrypt_db.py encrypt --db-path "$DB_PATH" --chunk-size $CHUNK_SIZE

# 2. Git 브랜치 생성/체크아웃
echo "2. 백업 브랜치 준비 중..."
git checkout -b $BACKUP_BRANCH 2>/dev/null || git checkout $BACKUP_BRANCH

# 3. 암호화된 청크 추가
echo "3. 암호화된 파일 Git에 추가 중..."
git add $ENCRYPTED_DIR/
git commit -m "🔐 Encrypted DB backup - $(date +%Y%m%d_%H%M%S)"

# 4. Push
echo "4. GitHub에 푸시 중..."
git push origin $BACKUP_BRANCH

# 5. 정리
echo "5. 로컬 암호화 파일 정리..."
read -p "로컬 암호화 파일을 삭제하시겠습니까? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf $ENCRYPTED_DIR
fi

# 원래 브랜치로 복귀
git checkout main

echo "✅ 백업 완료!"
echo "   브랜치: $BACKUP_BRANCH"
echo "   청크 파일: $ENCRYPTED_DIR/"