# Git LFS 상세 가이드

## Git LFS란?

Git LFS(Large File Storage)는 대용량 파일을 Git으로 효율적으로 관리하는 확장 기능입니다.
- 실제 파일은 별도 서버에 저장
- Git에는 포인터 파일만 저장
- 필요할 때만 실제 파일 다운로드

## 장단점

### 장점
- 대용량 파일도 Git으로 버전 관리 가능
- 저장소 크기 최소화
- 필요한 파일만 선택적 다운로드

### 단점
- GitHub 무료 계정: 1GB 저장소, 월 1GB 대역폭 제한
- 추가 비용 발생 가능
- 팀원 모두 Git LFS 설치 필요

## 설치 및 설정 방법

### 1. Git LFS 설치

```bash
# macOS (Homebrew)
brew install git-lfs

# 설치 확인
git lfs version
```

### 2. 프로젝트에서 Git LFS 초기화

```bash
# 프로젝트 디렉토리에서
cd /Users/hanskim/Projects/SambioHR2

# Git LFS 초기화
git lfs install
```

### 3. 추적할 파일 패턴 지정

```bash
# 데이터베이스 파일 추적
git lfs track "*.db"
git lfs track "data/*.db"

# Excel 파일 추적
git lfs track "*.xlsx"
git lfs track "data/*.xlsx"

# 특정 파일만 추적
git lfs track "data/sambio_human.db"
```

### 4. .gitattributes 파일 커밋

```bash
# .gitattributes 파일이 생성됨
git add .gitattributes
git commit -m "Add Git LFS tracking for large files"
```

### 5. 기존 대용량 파일 추가

```bash
# .gitignore에서 제외된 파일 패턴 제거 필요
# .gitignore 수정 후

# 대용량 파일 추가
git add data/sambio_human.db
git add data/*.xlsx

# 커밋
git commit -m "Add large data files with Git LFS"

# 푸시
git push
```

## 현재 프로젝트에 적용 시 고려사항

### 파일 크기
- `data/sambio_human.db`: 640MB
- Excel 파일들: 총 348MB
- **총 988MB** → GitHub 무료 한도 초과

### 권장 방안

#### 1. 선택적 LFS 사용 (권장)
```bash
# 가장 중요한 파일만 LFS로 관리
git lfs track "data/sambio_human.db"

# 나머지는 .gitignore 유지
```

#### 2. 데이터 분리
- 샘플 데이터만 Git에 포함
- 전체 데이터는 클라우드 스토리지

#### 3. 현재 방식 유지
- .gitignore로 제외
- README에 데이터 획득 방법 문서화

## Git LFS 사용 예시

```bash
# 1. LFS 설치 및 초기화
brew install git-lfs
git lfs install

# 2. 데이터베이스만 LFS로 관리
git lfs track "data/sambio_human.db"
git add .gitattributes
git commit -m "Configure Git LFS for database file"

# 3. .gitignore 수정 (해당 파일 제거)
# *.db 라인 제거 또는 주석 처리

# 4. 데이터베이스 추가
git add data/sambio_human.db
git commit -m "Add database file via Git LFS"

# 5. 푸시
git push
```

## 팀원을 위한 안내

```markdown
# README.md에 추가

## Git LFS 사용
이 프로젝트는 대용량 파일 관리를 위해 Git LFS를 사용합니다.

### 설정 방법
1. Git LFS 설치: `brew install git-lfs`
2. 초기화: `git lfs install`
3. 저장소 클론: `git clone <repo-url>`
4. LFS 파일 다운로드: `git lfs pull`
```

## 결론

현재 프로젝트의 경우:
1. **데이터 파일이 988MB로 GitHub 무료 한도 초과**
2. **현재 .gitignore 방식이 더 적합**
3. 필요시 중요 파일만 선택적으로 LFS 사용 고려