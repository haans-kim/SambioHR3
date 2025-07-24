# 데이터 파일 관리 가이드

## 🚨 중요 사항

이 프로젝트는 개인정보를 포함한 대용량 데이터 파일을 사용합니다.
보안과 성능을 위해 다음 파일들은 Git에 포함되지 않습니다:

### 제외된 파일들
- `data/pickles/*.pkl.gz` - 처리된 데이터 (19MB ~ 988KB)
- `*.xlsx` - Excel 원본 파일
- `*.db` - 데이터베이스 파일
- `config/upload_config.json` - 업로드 설정 (경로 정보 포함)

## 📦 초기 설정 방법

### 1. 데이터 파일 준비
프로젝트를 처음 실행하는 경우, 다음 중 하나를 선택하세요:

#### 옵션 A: Pickle 파일 복사 (권장)
```bash
# 기존 환경에서 pickle 파일들을 복사
cp -r /path/to/existing/data/pickles/* data/pickles/
```

#### 옵션 B: Excel 파일에서 새로 생성
1. Excel 파일들을 `data/` 폴더에 배치
2. Streamlit 앱 실행 후 데이터 업로드

### 2. 필수 디렉토리 생성
```bash
mkdir -p data/pickles
mkdir -p database
mkdir -p logs
```

## 🔧 Git 에러 해결

### 대용량 파일 에러
```bash
# 정리 스크립트 실행
./scripts/clean_for_git.sh

# 또는 수동으로
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -delete
git rm -r --cached data/pickles/*.pkl.gz
```

### Git LFS 사용 (선택사항)
대용량 파일을 Git에 포함하려면:
```bash
git lfs track "*.pkl.gz"
git lfs track "*.db"
git add .gitattributes
```

## 📊 데이터 파일 정보

| 파일명 | 크기 | 설명 |
|--------|------|------|
| tag_data_*.pkl.gz | ~19MB | 태깅 데이터 (1,799,769행) |
| meal_data_*.pkl.gz | ~16MB | 식사 데이터 (710,583행) |
| claim_data_*.pkl.gz | ~1.5MB | 근무시간 신고 데이터 |
| non_work_time_*.pkl.gz | ~988KB | 비근무시간 데이터 |

## 🛡️ 보안 주의사항

- **절대로** 실제 데이터가 포함된 pickle 파일을 공개 저장소에 업로드하지 마세요
- 테스트용 샘플 데이터만 사용하거나, 민감한 정보를 제거한 버전을 사용하세요
- 필요한 경우 별도의 private 데이터 저장소를 사용하세요