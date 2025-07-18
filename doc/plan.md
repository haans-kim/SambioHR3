# 실근무시간 산정 시스템 구체적 실행계획

## 프로젝트 개요
정원인력 산정을 위한 로그데이터 기반 실근무시간 산정 프로그램

## 1단계: 프로젝트 초기 설정 및 구조 구축 (1-2주)

### 1.1 프로젝트 구조 설정
```
Sambio_human/
├── src/
│   ├── data_processing/
│   │   ├── excel_loader.py
│   │   ├── data_transformer.py
│   │   └── pickle_manager.py
│   ├── database/
│   │   ├── schema.py
│   │   ├── db_manager.py
│   │   └── models.py
│   ├── hmm/
│   │   ├── hmm_model.py
│   │   ├── baum_welch.py
│   │   ├── viterbi.py
│   │   └── rule_editor.py
│   ├── analysis/
│   │   ├── individual_analyzer.py
│   │   └── organization_analyzer.py
│   └── ui/
│       ├── streamlit_app.py
│       └── components/
├── data/
│   ├── raw/
│   ├── processed/
│   └── pickles/
├── tests/
├── config/
└── requirements.txt
```

### 1.2 가상환경 및 의존성 설정
- Python 3.9+ 가상환경 생성
- requirements.txt 작성:
  ```
  pandas>=1.5.0
  numpy>=1.21.0
  sqlite3
  streamlit>=1.25.0
  matplotlib>=3.5.0
  seaborn>=0.11.0
  openpyxl>=3.0.0
  scikit-learn>=1.1.0
  hmmlearn>=0.2.8
  plotly>=5.10.0
  ```

## 2단계: 데이터 처리 파이프라인 구축 (2-3주)

### 2.1 엑셀 데이터 로더 구현
- `excel_loader.py`: 100MB+ 엑셀 파일 효율적 로딩
- 청크 단위 읽기 및 메모리 최적화
- 데이터 검증 및 오류 처리

### 2.2 데이터 변환 및 전처리
- `data_transformer.py`: 태깅데이터 시계열 정렬
- 꼬리물기 현상 처리 알고리즘 구현
- 누락 구간 탐지 및 보간 로직

### 2.3 Pickle 파일 관리
- `pickle_manager.py`: 데이터프레임 직렬화/역직렬화
- 버전 관리 및 캐싱 전략

### 2.4 데이터 타입별 처리 로직
- 태깅데이터: 시계열 정렬 및 중복 제거
- 근태데이터: 출입시간 매칭
- 년월차데이터: 휴가 기간 식별
- 장비조작데이터: 작업시간 구간 매칭
- 조직구성데이터: 계층 구조 파싱

## 3단계: 데이터베이스 설계 및 구현 (1-2주)

### 3.1 SQLite 데이터베이스 스키마 설계
```sql
-- 개인별 일간 데이터
CREATE TABLE daily_work_data (
    id INTEGER PRIMARY KEY,
    employee_id TEXT,
    date DATE,
    actual_work_time REAL,
    work_time REAL,
    rest_time REAL,
    non_work_time REAL,
    efficiency_ratio REAL,
    created_at TIMESTAMP
);

-- 조직별 집계 데이터
CREATE TABLE organization_summary (
    id INTEGER PRIMARY KEY,
    org_id TEXT,
    date DATE,
    avg_work_time REAL,
    operation_rate REAL,
    total_employees INTEGER,
    created_at TIMESTAMP
);

-- 태그 로그 데이터
CREATE TABLE tag_logs (
    id INTEGER PRIMARY KEY,
    employee_id TEXT,
    timestamp TIMESTAMP,
    tag_location TEXT,
    action_type TEXT
);
```

### 3.2 데이터베이스 매니저 구현
- `db_manager.py`: 연결 관리 및 쿼리 실행
- 트랜잭션 처리 및 오류 복구
- 대용량 데이터 배치 처리

## 4단계: HMM 모델 구현 (3-4주)

### 4.1 HMM 모델 기본 구조
- `hmm_model.py`: 상태 정의 및 모델 초기화
- 상태: 근무, 집중근무, 이동, 식사, 피트니스, 출근/퇴근, 연차, 장비조작, 회의, 휴식, 작업준비, 작업중
- 관측값: 태그 위치, 시간 간격, 요일, 시간대

### 4.2 전이 규칙 (Transition Rules) 정의
- 상태 간 전이 확률 매트릭스
- 시간대별 전이 확률 조정
- 개인별/조직별 전이 패턴 학습

### 4.3 방출 규칙 (Emission Rules) 정의
- 각 상태별 태그 위치 확률
- 시간 간격별 방출 확률
- 다차원 관측값 처리

### 4.4 Baum-Welch 학습 알고리즘 구현
- `baum_welch.py`: 파라미터 최적화
- 수렴 조건 설정 및 성능 모니터링
- 정규화 및 수치 안정성 확보

### 4.5 Viterbi 예측 알고리즘 구현
- `viterbi.py`: 최적 상태 시퀀스 추정
- 로그 확률 계산으로 언더플로우 방지
- 실시간 예측 성능 최적화

### 4.6 규칙 에디터 구현
- `rule_editor.py`: 전이/방출 규칙 수정 인터페이스
- 규칙 검증 및 일관성 검사
- 규칙 버전 관리

## 5단계: 분석 엔진 구현 (2-3주)

### 5.1 개인별 분석기
- `individual_analyzer.py`: 일간/월간 개인 데이터 분석
- HMM 모델 적용 및 상태 시퀀스 생성
- 실근무시간 vs Claim 시간 비교 분석

### 5.2 조직별 분석기
- `organization_analyzer.py`: 조직 단위 데이터 집계
- 평균 근무시간 및 가동율 계산
- 조직 간 비교 분석

### 5.3 배치 처리 시스템
- 대용량 데이터 처리를 위한 배치 작업
- 진행률 모니터링 및 오류 처리
- 병렬 처리 및 성능 최적화

## 6단계: UI 개발 (2-3주)

### 6.1 Streamlit 기반 초기 UI
- `streamlit_app.py`: 메인 애플리케이션
- 사이드바 네비게이션 구성
- 데이터 업로드 및 처리 인터페이스

### 6.2 대시보드 화면
- 조직별/직급별 요약 데이터 시각화
- 시계열 차트 및 히트맵
- 필터링 및 드릴다운 기능

### 6.3 개인 상세 화면
- 개인별 일간/월간 데이터 표시
- 실근무시간 vs Claim 시간 비교
- 상태별 시간 분포 차트

### 6.4 HMM 규칙 편집 화면
- 전이 규칙 매트릭스 편집기
- 방출 규칙 편집기
- 규칙 시각화 및 검증

### 6.5 설정 및 관리 화면
- 데이터 소스 관리
- 모델 파라미터 설정
- 배치 작업 모니터링

## 7단계: 테스트 및 검증 (1-2주)

### 7.1 단위 테스트
- 각 모듈별 테스트 케이스 작성
- 데이터 처리 로직 검증
- HMM 알고리즘 정확성 테스트

### 7.2 통합 테스트
- 전체 파이프라인 동작 검증
- 대용량 데이터 처리 성능 테스트
- UI 사용성 테스트

### 7.3 데이터 검증
- 실제 데이터 기반 모델 성능 평가
- 분석 결과 정확성 검증
- 도메인 전문가 리뷰

## 8단계: 배포 및 운영 (1주)

### 8.1 배포 환경 설정
- 프로덕션 환경 구성
- 데이터베이스 백업 및 복구 전략
- 모니터링 및 로깅 시스템

### 8.2 사용자 교육
- 사용자 매뉴얼 작성
- 교육 자료 준비
- 피드백 수집 체계 구축

## 9단계: 고도화 계획 (장기)

### 9.1 React/TSX 기반 웹 UI
- 현재 Streamlit UI를 React로 전환
- shadcn UI 컴포넌트 적용
- RESTful API 설계 및 구현

### 9.2 머신러닝 모델 고도화
- 딥러닝 모델 적용 검토
- 앙상블 모델 구현
- 자동 하이퍼파라미터 튜닝

### 9.3 실시간 처리 시스템
- 실시간 태그 데이터 처리
- 스트리밍 분석 파이프라인
- 알림 및 예외 처리 시스템

## 성공 지표 및 KPI

- **데이터 처리 성능**: 100MB+ 엑셀 파일 10분 이내 처리
- **HMM 모델 정확도**: 90% 이상의 상태 분류 정확도
- **시스템 응답 속도**: 대시보드 로딩 3초 이내
- **사용자 만족도**: 사용성 테스트 4.0/5.0 이상
- **데이터 품질**: 99% 이상의 데이터 무결성 보장

## 리스크 관리

- **데이터 품질 리스크**: 데이터 검증 로직 강화
- **성능 리스크**: 병렬 처리 및 캐싱 전략
- **모델 정확도 리스크**: 도메인 전문가 협력
- **기술 리스크**: 프로토타입 기반 검증
- **일정 리스크**: 단계별 마일스톤 관리

## 예상 일정

총 소요 기간: **12-16주**
- 1-4단계: 6-8주 (기반 구축)
- 5-6단계: 4-6주 (핵심 기능)
- 7-9단계: 2-2주 (완성도 제고)