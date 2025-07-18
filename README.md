# Sambio Human Analytics System

## 📋 프로젝트 개요

2교대 근무 시스템을 반영한 실근무시간 산정 프로그램입니다. 태깅 데이터 기반 HMM 모델을 활용하여 근무 활동을 분석하고, 4번 식사시간(조식/중식/석식/야식)을 포함한 정확한 근무시간 산정을 제공합니다.

## 🏗️ 시스템 아키텍처

```
src/
├── data_processing/     # 데이터 처리 파이프라인
│   ├── excel_loader.py      # 대용량 엑셀 파일 로더
│   ├── data_transformer.py  # 2교대 근무 데이터 변환
│   └── pickle_manager.py    # 데이터 캐싱
├── database/           # 데이터베이스 관리
│   ├── schema.py           # 13개 테이블 스키마
│   ├── db_manager.py       # 데이터베이스 매니저
│   └── models.py           # 비즈니스 로직 모델
├── hmm/               # HMM 모델 구현
│   ├── hmm_model.py        # 메인 HMM 모델
│   ├── baum_welch.py       # 학습 알고리즘
│   ├── viterbi.py          # 예측 알고리즘
│   └── rule_editor.py      # 규칙 편집기
├── analysis/          # 분석 엔진
│   ├── individual_analyzer.py  # 개인별 분석
│   └── organization_analyzer.py # 조직별 분석
└── ui/                # 사용자 인터페이스
    ├── streamlit_app.py    # 메인 애플리케이션
    └── components/         # UI 컴포넌트들
```

## 🎯 주요 기능

### 1. 2교대 근무 시스템 지원
- **주간/야간 교대** 자동 구분
- **자정 이후 시간 연속성** 처리
- **출근일 ≠ 퇴근일** 상황 처리
- **교대별 근무 효율성** 비교 분석

### 2. 4번 식사시간 추적
- **조식**: 06:30-09:00 + CAFETERIA
- **중식**: 11:20-13:20 + CAFETERIA
- **석식**: 17:00-20:00 + CAFETERIA
- **야식**: 23:30-01:00 + CAFETERIA

### 3. HMM 기반 활동 분류
- **17개 활동 상태** 자동 분류
- **10개 관측 특성** 기반 예측
- **Baum-Welch 학습** 알고리즘
- **Viterbi 예측** 알고리즘

### 4. 실시간 분석 대시보드
- **개인별 활동 요약** (UI 참조자료 반영)
- **조직별 성과 분석**
- **교대별 비교 분석**
- **데이터 품질 모니터링**

## 📊 데이터 구조

### 지원 데이터 형식
1. **태깅 데이터** (`tag_data_24.6.xlsx`)
2. **ABC 활동 데이터** (`data_ABC데이터 리스트_2506.xlsx`)
3. **근무시간 Claim 데이터** (`data_근무시간(claim)_전사_2506.xlsx`)
4. **근태 사용 데이터** (`data_근태 사용_2506.xlsx`)
5. **비근무시간 데이터** (`data_임직원 비근무시간 raw data_2506.xlsx`)
6. **직원 정보** (`25년 6월말 인원현황.xlsx`)
7. **태깅 지점 마스터** (`마스터파일_태깅지점_20250718.xlsx`)
8. **조직 매핑** (`조직,인원,R&R matching_250709.xlsx`)

### 데이터베이스 스키마
- **13개 테이블** 구조
- **2교대 근무 반영** 필드
- **4번 식사시간 추적** 필드
- **SQLite 기반** 경량 데이터베이스

## 🚀 설치 및 실행

### 1. 환경 설정
```bash
# 가상환경 생성
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 애플리케이션 실행
```bash
# Streamlit 대시보드 실행
streamlit run src/ui/streamlit_app.py

# 또는 메인 애플리케이션 실행
python src/ui/streamlit_app.py
```

### 3. 데이터 업로드
1. 웹 브라우저에서 `http://localhost:8501` 접속
2. **데이터 업로드** 메뉴 선택
3. 엑셀 파일 업로드 및 처리

## 🔧 구성 요소

### HMM 모델 구성
```python
# 17개 활동 상태
- 근무상태: 근무, 집중근무, 장비조작, 회의, 작업준비, 작업중
- 식사상태: 조식, 중식, 석식, 야식
- 이동상태: 이동, 출근, 퇴근
- 휴식상태: 휴식, 피트니스
- 비근무상태: 연차, 배우자출산

# 10개 관측 특성
- 태그위치, 시간간격, 요일, 시간대, 근무구역여부
- ABC작업분류, 근태상태, 제외시간여부, CAFETERIA위치, 교대구분
```

### 분석 지표
- **실근무시간 vs Claim 시간** 비교
- **교대별 근무 효율성** 분석
- **식사시간 패턴** 분석
- **데이터 품질** 평가
- **생산성 점수** 계산

## 📈 성능 지표

### 목표 KPI
- **데이터 처리 성능**: 100MB+ 엑셀 파일 10분 이내 처리
- **HMM 모델 정확도**: 90% 이상의 상태 분류 정확도
- **2교대 근무 처리 정확도**: 95% 이상
- **식사시간 인식 정확도**: 90% 이상
- **시스템 응답 속도**: 대시보드 로딩 3초 이내

### 데이터 품질
- **태그 데이터 완전성**: 90% 이상
- **Claim 데이터 정확성**: 95% 이상
- **전체 데이터 무결성**: 99% 이상

## 🎨 사용자 인터페이스

### 대시보드 구성
1. **홈 대시보드**: 전체 시스템 현황
2. **개인 분석**: 개인별 상세 분석 (UI 참조자료 반영)
3. **조직 분석**: 팀/부서별 성과 분석
4. **비교 분석**: 다차원 비교 분석
5. **데이터 업로드**: 실시간 데이터 처리
6. **모델 설정**: HMM 모델 관리

### 주요 시각화
- **24시간 타임라인** 차트
- **활동 분류별 시간 분포** (프로그레스 바)
- **교대별 성과 비교** 차트
- **데이터 신뢰도 시각화**
- **트렌드 분석** 차트

## 🛠️ 기술 스택

- **Backend**: Python 3.9+, SQLAlchemy, NumPy, Pandas
- **Machine Learning**: HMM (자체 구현), Scikit-learn
- **Frontend**: Streamlit, Plotly, Plotly Express
- **Database**: SQLite
- **Data Processing**: Openpyxl, Pickle
- **Visualization**: Matplotlib, Seaborn

## 📚 개발 가이드

### 새로운 분석 기능 추가
1. `src/analysis/` 폴더에 새 분석기 구현
2. 필요시 `src/database/schema.py`에 테이블 추가
3. `src/ui/components/`에 UI 컴포넌트 추가

### HMM 모델 개선
1. `src/hmm/hmm_model.py`에서 상태/관측값 추가
2. `src/hmm/rule_editor.py`에서 규칙 편집
3. 학습 데이터로 파라미터 튜닝

### 데이터 처리 확장
1. `src/data_processing/excel_loader.py`에 새 데이터 형식 지원
2. `src/data_processing/data_transformer.py`에 변환 로직 추가

## 🤝 기여 방법

1. 이슈 생성 및 논의
2. 브랜치 생성 (`feature/새기능명`)
3. 코드 구현 및 테스트
4. Pull Request 제출

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 👥 개발팀

- **Lead Developer**: Sambio Human Analytics Team
- **Version**: 1.0.0
- **Release Date**: 2025-01-18

---

## 🎉 구현 완료 사항

✅ **프로젝트 구조 설정** - 모듈화된 아키텍처  
✅ **데이터 처리 파이프라인** - 대용량 엑셀 처리  
✅ **데이터베이스 스키마** - 13개 테이블 구조  
✅ **HMM 모델 구현** - 완전한 학습/예측 시스템  
✅ **분석 엔진** - 개인별/조직별 분석  
✅ **Streamlit UI** - 직관적인 대시보드  
✅ **2교대 근무 지원** - 자정 이후 시간 처리  
✅ **4번 식사시간 추적** - CAFETERIA 위치 기반  
✅ **UI 참조자료 반영** - 개인활동요약 화면  

시스템이 완전히 구현되었으며, 바로 사용 가능한 상태입니다! 🚀