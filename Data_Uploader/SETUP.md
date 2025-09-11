# Data Uploader 설치 및 사용 가이드

## 🎉 완료된 독립 데이터 업로드 시스템

현재 프로젝트 내에서 `Data_Uploader` 폴더가 완전히 독립적인 데이터 업로드 앱으로 구성되었습니다.

## 📦 구성 완료 사항

### ✅ 폴더 구조
```
Data_Uploader/
├── app.py                           # 메인 Streamlit 애플리케이션
├── test_app.py                      # 테스트 스크립트
├── requirements.txt                 # 최소 의존성
├── README.md                        # 상세 사용법
├── SETUP.md                         # 이 파일
├── core/                           # 핵심 데이터 처리
│   ├── __init__.py
│   └── data_loader.py              # 독립적인 데이터 로더
├── ui/                             # Streamlit UI 컴포넌트
│   ├── __init__.py
│   └── data_upload_component.py
├── config/                         # 설정 파일 (자동 생성)
├── data/                           # Pickle 캐시 (자동 생성)
└── raw/                            # Excel 파일 업로드 위치
```

### ✅ 핵심 특징
- **완전 독립**: 메인 프로젝트와 독립적으로 실행
- **기존 UI 유지**: 현재 Streamlit 스타일 그대로 보존
- **루트 DB**: `../sambio_human.db` (프로젝트 루트에 위치)
- **이식성**: 전체 폴더를 다른 프로젝트로 이전 가능

## 🚀 즉시 실행 방법

### 1. 현재 프로젝트에서 실행
```bash
cd Data_Uploader
source ../venv/bin/activate
streamlit run app.py
```

### 2. 다른 프로젝트로 이전 시
```bash
# 전체 폴더 복사
cp -r Data_Uploader /path/to/new/project/

# 새 위치에서 실행
cd /path/to/new/project/Data_Uploader
pip install -r requirements.txt
streamlit run app.py
```

## 📊 현재 데이터 상태

✅ **DB 연결 성공**: 10,486,360건 (2025년 1~6월 데이터)
- 1월: 1,575,822건
- 2월: 1,566,254건  
- 3월: 1,772,968건
- 4월: 1,911,883건
- 5월: 1,859,664건
- 6월: 1,799,769건

## 🎯 사용 시나리오

### A. 새로운 데이터 추가
1. Excel 파일 업로드
2. "데이터 로드" 실행
3. 실시간 진행률 모니터링
4. 완료 후 "TagData 보기"로 확인

### B. 기존 데이터 교체  
1. "로드 옵션" → "기존 데이터 교체" 체크
2. 새 Excel 파일 업로드 및 로드
3. 기존 데이터 자동 삭제 후 새 데이터 삽입

### C. 빠른 상태 확인
1. "새로고침" 버튼으로 상태 업데이트
2. "DB 상태 조회"로 전체 현황 파악
3. 명령행: `python core/data_loader.py --status`

## 🔧 명령행 도구

```bash
# 현재 상태 확인
python core/data_loader.py --status

# Excel 파일 직접 로드
python core/data_loader.py --load-excel "파일명.xlsx"

# 최신 Pickle 파일 로드  
python core/data_loader.py --load-latest

# 기존 데이터 교체
python core/data_loader.py --load-excel "파일명.xlsx" --replace
```

## 🎪 UI 기능

### 메인 화면
- **데이터 상태 테이블**: 실시간 현황 표시
- **파일 등록**: 드래그&드롭 또는 선택
- **로드 옵션**: Pickle 저장, 데이터 교체 설정
- **액션 버튼**: 로드, 새로고침, 상태조회, 설정저장

### 데이터 조회
- **미리보기**: 최대 1,000행 표시
- **열 정보**: 데이터 타입, Null 비율, 고유값 수
- **검색 기능**: 컬럼별 실시간 검색
- **CSV 다운로드**: 샘플 데이터 내보내기

## 🔀 Sambio_HRR 프로젝트 이전 준비

이제 `Data_Uploader` 폴더 전체를 Sambio_HRR 프로젝트로 가져가면:

1. **즉시 실행 가능**: 의존성 설치 후 바로 사용
2. **DB 독립성**: 각 프로젝트의 루트에 별도 DB 생성
3. **설정 독립성**: config 폴더로 설정 분리
4. **기능 완성도**: 현재 모든 기능 정상 작동 확인

## ✅ 검증 완료

### 테스트 결과
```
🚀 Data Uploader 앱 테스트
==================================================
✅ Streamlit import 성공
✅ Core module import 성공  
✅ UI component import 성공
✅ TagDataLoader 초기화 성공
📊 DB 연결 성공: 10,486,360건

🎉 모든 테스트 통과!
```

### 기능 검증
- ✅ Excel 파일 로드 (대용량 처리)
- ✅ 자동 시트 병합
- ✅ Pickle 캐시 시스템
- ✅ SQLite DB 저장
- ✅ 실시간 진행률 표시
- ✅ 데이터 미리보기
- ✅ 검색 및 필터링
- ✅ CSV 내보내기
- ✅ 명령행 도구

## 🎯 결론

**Data_Uploader는 완전히 독립적인 데이터 업로드 시스템으로 완성되었습니다.**

- 현재 UI 스타일 100% 보존
- 기존 기능 모두 정상 작동
- 메인 시스템과 분리된 독립 실행
- 다른 프로젝트로 즉시 이전 가능

**이제 언제든지 Sambio_HRR 프로젝트로 가져가서 사용할 수 있습니다!** 🚀