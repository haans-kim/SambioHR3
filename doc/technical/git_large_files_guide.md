# Git 대용량 파일 관리 가이드

## 현재 상황

프로젝트에 100MB 이상의 대용량 파일이 있습니다:
- `data/sambio_human.db` (640MB)
- `data/입출문기록(25.6).xlsx` (131MB)
- `data/tag_data_24.6.xlsx` (113MB)
- `data/식사 250401-0630.xlsx` (104MB)

이 파일들은 이미 `.gitignore`에 포함되어 있어 Git에 추가되지 않습니다.

## 해결 방법

### 1. 현재 설정 확인 (권장)

`.gitignore` 파일에 이미 다음 규칙이 있습니다:
```
*.xlsx
*.db
data/*.xlsx
data/*.db
```

따라서 대용량 파일들은 자동으로 제외됩니다.

### 2. Git 상태 확인

```bash
# 추적되지 않는 파일 확인 (대용량 파일 제외)
git status

# 특정 파일이 무시되는지 확인
git check-ignore data/sambio_human.db
```

### 3. 안전한 커밋 방법

```bash
# 1. 스테이징할 파일 확인
git status

# 2. 필요한 파일만 추가
git add .claude_hooks/
git add doc/
git add scripts/README.md
git add scripts/cleanup_scripts.sh
git add scripts/config.py
git add scripts/track_changes.py

# 3. 커밋
git commit -m "개발 문서화 시스템 및 스크립트 정리"

# 4. 푸시
git push
```

### 4. 실수로 대용량 파일을 추가한 경우

```bash
# 스테이징에서 제거
git reset HEAD data/large_file.xlsx

# 커밋 히스토리에서 제거 (주의!)
git filter-branch --tree-filter 'rm -f data/large_file.xlsx' HEAD
```

## 대용량 파일 공유 방법

### 옵션 1: 클라우드 스토리지
- Google Drive, Dropbox 등에 업로드
- README에 다운로드 링크 추가

### 옵션 2: Git LFS (Large File Storage)
```bash
# Git LFS 설치
brew install git-lfs

# 초기화
git lfs install

# 대용량 파일 추적
git lfs track "*.db"
git lfs track "data/*.xlsx"

# .gitattributes 커밋
git add .gitattributes
git commit -m "Add Git LFS tracking"
```

### 옵션 3: 데이터 샘플만 포함
- 전체 데이터 대신 샘플 데이터만 Git에 포함
- 전체 데이터는 별도 저장소에 보관

## 권장사항

1. **현재 .gitignore 설정 유지**: 대용량 파일은 이미 제외됨
2. **데이터 파일 위치 문서화**: README에 데이터 파일 획득 방법 명시
3. **정기적인 확인**: `git status`로 대용량 파일이 추가되지 않았는지 확인

## 팀 협업 시

```markdown
# README.md에 추가할 내용

## 데이터 파일
이 프로젝트는 대용량 데이터 파일을 사용합니다.
Git에는 포함되지 않으므로 별도로 다운로드하세요:

1. `data/sambio_human.db` - [다운로드 링크]
2. `data/tag_data_24.6.xlsx` - [다운로드 링크]
3. 기타 Excel 파일들 - [다운로드 링크]

파일을 다운로드 후 `data/` 디렉토리에 배치하세요.
```