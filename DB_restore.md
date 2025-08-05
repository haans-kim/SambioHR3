# DB 복원 가이드

이 문서는 암호화되어 GitHub에 백업된 데이터베이스를 복원하는 방법을 설명합니다.

## 백업 정보

- **백업 날짜**: 2025-08-06
- **백업 브랜치**: `db-backup-20250806`
- **원본 DB 크기**: 672MB
- **암호화 청크 수**: 3개
- **비밀번호**: `sambio2025`

## 복원 방법

### 1. 백업 브랜치 가져오기

```bash
# 원격 브랜치 정보 업데이트
git fetch origin

# 백업 브랜치로 체크아웃
git checkout db-backup-20250806
```

### 2. 필요한 패키지 설치

```bash
# cryptography 패키지가 없는 경우
pip install cryptography
```

### 3. DB 복원 실행

```bash
# 암호화된 청크를 복호화하고 병합
python scripts/encrypt_db.py decrypt \
  --encrypted-dir data/encrypted_chunks \
  --output data/sambio_human.db \
  --password sambio2025
```

### 4. 원래 브랜치로 돌아가기

```bash
# feature 브랜치로 복귀
git checkout feature/organization-dashboard-design

# 또는 main 브랜치로
git checkout main
```

## 새로운 백업 생성하기

### 자동 백업 (권장)

```bash
# 백업 스크립트 실행
./scripts/backup_db.sh
```

### 수동 백업

1. **DB 암호화 및 분할**
```bash
python scripts/encrypt_db.py encrypt \
  --db-path data/sambio_human.db \
  --chunk-size 50 \
  --password "your_password"
```

2. **GitHub에 업로드**
```bash
# 새 백업 브랜치 생성
git checkout -b db-backup-$(date +%Y%m%d)

# 암호화된 파일 추가
git add data/encrypted_chunks/

# 커밋
git commit -m "🔐 Encrypted DB backup - $(date +%Y-%m-%d)"

# 푸시
git push origin db-backup-$(date +%Y%m%d)
```

## 백업 파일 구조

```
data/encrypted_chunks/
├── sambio_human.enc.000    # 암호화된 청크 1
├── sambio_human.enc.001    # 암호화된 청크 2
├── sambio_human.enc.002    # 암호화된 청크 3
└── sambio_human.metadata.json  # 메타데이터
```

## 주의사항

1. **비밀번호 관리**: 비밀번호는 안전하게 보관하세요. 분실시 복원 불가능합니다.
2. **브랜치 관리**: 백업 브랜치는 정기적으로 정리하여 저장소 크기를 관리하세요.
3. **정기 백업**: 중요한 작업 후에는 항상 백업을 생성하세요.
4. **복원 테스트**: 백업 후 복원이 제대로 되는지 테스트하세요.

## 문제 해결

### "No module named 'cryptography'" 오류
```bash
pip install cryptography
```

### 권한 오류
```bash
chmod +x scripts/backup_db.sh
chmod +x scripts/restore_db.sh
```

### 메타데이터 파일을 찾을 수 없음
백업 브랜치가 제대로 체크아웃되었는지 확인:
```bash
git branch  # 현재 브랜치 확인
ls data/encrypted_chunks/  # 파일 존재 확인
```

## 백업 이력

| 날짜 | 브랜치 | 청크 수 | 비고 |
|------|--------|---------|------|
| 2025-08-06 | db-backup-20250806 | 3 | 초기 백업, Phase 4 완료 후 |