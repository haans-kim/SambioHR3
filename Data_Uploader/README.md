# SAMBIO Data Uploader

독립적인 데이터 업로드 및 관리 시스템

## 🎯 목적

- **기존 시스템과 분리**: 메인 Sambio HR 시스템과 독립적으로 실행
- **데이터 로딩 전용**: TagData (입출문 데이터) 업로드 및 관리에 특화
- **이식성**: 전체 폴더를 다른 프로젝트로 쉽게 이전 가능

## 📁 폴더 구조

```
Data_Uploader/
├── app.py                    # 메인 Streamlit 애플리케이션
├── requirements.txt          # 의존성 목록
├── README.md                # 이 파일
├── core/                    # 핵심 데이터 처리 모듈
│   ├── __init__.py
│   └── data_loader.py       # 독립적인 데이터 로더
├── ui/                      # UI 컴포넌트
│   ├── __init__.py
│   └── data_upload_component.py
├── config/                  # 설정 파일 (자동 생성)
│   └── upload_config.json
├── data/                    # Pickle 캐시 (자동 생성)
│   └── *.pkl.gz
└── raw/                     # Excel 파일 업로드 위치
    └── *.xlsx
```

## 🚀 설치 및 실행

### 1. 의존성 설치

```bash
cd Data_Uploader
pip install -r requirements.txt
```

### 2. 애플리케이션 실행

```bash
streamlit run app.py
```

### 3. 웹 브라우저 접속

- 기본 주소: http://localhost:8501
- 자동으로 브라우저가 열립니다

## 📊 주요 기능

### 1. Excel 파일 업로드
- **다중 파일 지원**: 여러 Excel 파일 동시 업로드
- **자동 시트 병합**: 복수 시트를 하나로 통합
- **대용량 처리**: 150만건+ 데이터 효율적 처리

### 2. 데이터 관리
- **Pickle 캐시**: 빠른 재로딩을 위한 압축 저장
- **SQLite DB**: 구조화된 데이터베이스 저장
- **상태 모니터링**: 실시간 로딩 진행률 표시

### 3. 데이터 조회
- **미리보기**: 로드된 데이터 즉시 확인
- **검색 기능**: 컬럼별 데이터 검색
- **통계 정보**: 기본적인 데이터 분석
- **CSV 다운로드**: 샘플 데이터 내보내기

## 🔧 사용법

### 기본 워크플로우

1. **파일 준비**
   - Excel 파일을 `raw/` 폴더에 배치하거나
   - 웹 인터페이스에서 직접 업로드

2. **파일 등록**
   - "파일 선택" → 업로드할 Excel 파일들 선택
   - "파일 추가" 버튼으로 등록 목록에 추가

3. **로드 옵션 설정**
   - **Pickle 파일 저장**: 빠른 재로딩을 위해 권장
   - **기존 데이터 교체**: 중복 방지 또는 데이터 갱신

4. **데이터 로드 실행**
   - "데이터 로드" 버튼 클릭
   - 진행률 모니터링
   - 완료 후 상태 테이블 확인

5. **결과 확인**
   - "새로고침"으로 상태 업데이트
   - "DB 상태 조회"로 전체 현황 파악
   - "TagData 보기"로 데이터 미리보기

### 명령행 도구 (선택사항)

```bash
# 현재 상태 확인
python core/data_loader.py --status

# Excel 파일에서 직접 로드
python core/data_loader.py --load-excel "파일명.xlsx"

# 최신 Pickle 파일 로드
python core/data_loader.py --load-latest

# 기존 데이터 교체
python core/data_loader.py --load-excel "파일명.xlsx" --replace
```

## 🗄️ 데이터베이스

### 위치
- **DB 파일**: `../sambio_human.db` (프로젝트 루트)
- **공유 DB**: 메인 시스템과 동일한 데이터베이스 사용

### 테이블 구조
- **tag_data**: 태깅 데이터 메인 테이블 (15개 컬럼)
- 자동 생성: 첫 실행 시 필요한 테이블 자동 생성

## 📦 이식성

### 다른 프로젝트로 이전하기

1. **전체 폴더 복사**
   ```bash
   cp -r Data_Uploader /path/to/new/project/
   ```

2. **의존성 설치**
   ```bash
   cd /path/to/new/project/Data_Uploader
   pip install -r requirements.txt
   ```

3. **즉시 실행 가능**
   ```bash
   streamlit run app.py
   ```

### 주의사항
- DB 파일은 프로젝트 루트에 생성됩니다
- 기존 데이터가 있다면 자동으로 인식합니다
- 설정 파일은 독립적으로 관리됩니다

## 🔍 문제 해결

### 자주 발생하는 문제

1. **모듈을 찾을 수 없음**
   ```bash
   # 해결: Data_Uploader 폴더에서 실행하는지 확인
   cd Data_Uploader
   streamlit run app.py
   ```

2. **Excel 파일 로드 실패**
   - 파일 형식 확인 (.xlsx, .xls)
   - 파일이 다른 프로그램에서 열려있지 않은지 확인
   - 충분한 메모리 확보

3. **데이터베이스 오류**
   - 다른 애플리케이션에서 DB 파일 사용 중인지 확인
   - 디스크 공간 확인

### 로그 확인
- 콘솔에서 실시간 로그 확인 가능
- 상세한 오류 정보는 터미널에 출력됩니다

## 🚧 제한사항

- **TagData만 지원**: 현재는 태깅 데이터 전용
- **SQLite 전용**: PostgreSQL 등 다른 DB 미지원
- **단일 세션**: 동시에 여러 로딩 작업 불가

## 🔄 향후 개선 계획

- [ ] 다중 데이터 유형 지원
- [ ] PostgreSQL 연동
- [ ] 실시간 진행률 WebSocket
- [ ] 배치 작업 스케줄링
- [ ] 데이터 검증 기능 강화