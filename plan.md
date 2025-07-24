# HRM Analytics System Implementation Plan
# 정원인력 산정 시스템 구현 계획

## 1. 프로젝트 개요 (Project Overview)

### 목적 (Purpose)
- 태그 데이터를 기반으로 한 실제 근무시간 산정 시스템 개발
- HMM(Hidden Markov Model) 모델을 활용한 활동 분류 및 시간 분석
- 개인별/조직별 근무 패턴 분석 및 가동률 계산

### 핵심 기능 (Core Features)
- 태그 데이터 전처리 및 시계열 분석
- HMM 모델 기반 활동 분류 (근무, 휴식, 이동 등)
- 실시간 근무시간 계산 및 데이터베이스 저장
- 조직/개인별 데이터 시각화 및 리포트 생성
- HMM 규칙 편집기 구현

## 2. 시스템 아키텍처 (System Architecture)

### 프로젝트 구조 (Project Structure)
```
Sambio_human/
├── src/
│   ├── data/                    # 데이터 처리 모듈
│   │   ├── __init__.py
│   │   ├── loader.py           # Excel/Pickle 데이터 로더
│   │   ├── preprocessor.py     # 데이터 전처리
│   │   └── validator.py        # 데이터 검증
│   ├── models/                  # HMM 모델 구현
│   │   ├── __init__.py
│   │   ├── hmm_model.py        # HMM 메인 클래스
│   │   ├── baum_welch.py       # 학습 알고리즘
│   │   ├── viterbi.py          # 예측 알고리즘
│   │   └── model_utils.py      # 모델 유틸리티
│   ├── analysis/                # 분석 엔진
│   │   ├── __init__.py
│   │   ├── activity_classifier.py  # 활동 분류기
│   │   ├── time_aggregator.py     # 시간 집계
│   │   ├── pattern_analyzer.py    # 패턴 분석
│   │   └── network_analyzer.py    # 네트워크 분석
│   ├── database/                # 데이터베이스 레이어
│   │   ├── __init__.py
│   │   ├── sqlite_manager.py   # SQLite 매니저
│   │   ├── models.py          # DB 스키마
│   │   └── queries.py         # 쿼리 모음
│   └── ui/                     # 사용자 인터페이스
│       ├── __init__.py
│       ├── streamlit_app.py   # 메인 앱
│       ├── components/        # UI 컴포넌트
│       │   ├── dashboard.py   # 대시보드
│       │   ├── hmm_editor.py  # HMM 편집기
│       │   ├── visualizations.py  # 시각화
│       │   └── data_explorer.py   # 데이터 탐색
│       └── utils/
│           └── ui_helpers.py  # UI 헬퍼 함수
├── config/                     # 설정 파일
│   ├── hmm_rules.json         # HMM 규칙 설정
│   ├── activity_config.json   # 활동 카테고리 설정
│   └── app_config.yaml        # 애플리케이션 설정
├── tests/                     # 테스트 파일
│   ├── test_data/
│   ├── test_models/
│   ├── test_analysis/
│   └── test_ui/
├── docs/                      # 문서
│   ├── api_docs.md
│   ├── user_guide.md
│   └── deployment.md
├── scripts/                   # 스크립트
│   ├── setup_db.py           # DB 초기화
│   ├── data_migration.py     # 데이터 마이그레이션
│   └── batch_analysis.py     # 배치 분석
├── requirements.txt
├── setup.py
└── README.md
```

## 3. 데이터 모델 (Data Models)

### 활동 카테고리 (Activity Categories)
```python
ACTIVITY_STATES = {
    'WORK': '근무',
    'FOCUSED_WORK': '집중근무',
    'MOVEMENT': '이동',
    'MEAL': '식사',
    'FITNESS': '피트니스',
    'COMMUTE': '출근/퇴근',
    'LEAVE': '연차',
    'EQUIPMENT': '장비조작',
    'MEETING': '회의',
    'REST': '휴식',
    'WORK_PREP': '작업준비',
    'ACTIVE_WORK': '작업중'
}
```

### 데이터베이스 스키마 (Database Schema)
```sql
-- 직원 정보
CREATE TABLE employees (
    employee_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT,
    position TEXT,
    start_date DATE
);

-- 일일 근무 요약
CREATE TABLE daily_work_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT,
    date DATE,
    total_time INTEGER,           -- 총 시간 (분)
    work_time INTEGER,            -- 근무 시간
    focused_work_time INTEGER,    -- 집중근무 시간
    rest_time INTEGER,            -- 휴식 시간
    movement_time INTEGER,        -- 이동 시간
    meal_time INTEGER,            -- 식사 시간
    meeting_time INTEGER,         -- 회의 시간
    utilization_rate REAL,        -- 가동률
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
);

-- 조직 요약 데이터
CREATE TABLE org_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id TEXT,
    date DATE,
    avg_work_time REAL,
    avg_utilization_rate REAL,
    total_employees INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 태그 데이터 (전처리된)
CREATE TABLE processed_tag_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT,
    timestamp TIMESTAMP,
    location TEXT,
    activity_state TEXT,
    confidence_score REAL,
    FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
);

-- HMM 모델 설정
CREATE TABLE hmm_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT UNIQUE,
    transition_matrix TEXT,       -- JSON 형태
    emission_matrix TEXT,         -- JSON 형태
    states TEXT,                  -- JSON 형태
    observations TEXT,            -- JSON 형태
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 네트워크 분석 데이터
CREATE TABLE interaction_networks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE,
    time_window TEXT,            -- 시간대 (morning, afternoon, evening, night)
    employee1_id TEXT,
    employee2_id TEXT,
    interaction_type TEXT,       -- co-location, meeting, collaboration
    duration INTEGER,            -- 상호작용 시간 (분)
    location TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee1_id) REFERENCES employees (employee_id),
    FOREIGN KEY (employee2_id) REFERENCES employees (employee_id)
);

-- 공간 이동 네트워크
CREATE TABLE movement_networks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT,
    date DATE,
    from_location TEXT,
    to_location TEXT,
    movement_time TIMESTAMP,
    transition_count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
);
```

## 4. HMM 모델 설계 (HMM Model Design)

### 모델 구조
- **States (상태)**: 12개 활동 카테고리
- **Observations (관찰)**: 태그 위치, 시간대, 체류 시간
- **Transition Matrix (전이 행렬)**: 12x12 확률 행렬
- **Emission Matrix (방출 행렬)**: 위치→활동 확률 행렬

### 알고리즘 구현
```python
# HMM 클래스 구조
class HMMWorkAnalyzer:
    def __init__(self, n_states=12, n_observations=None):
        self.n_states = n_states
        self.transition_matrix = None
        self.emission_matrix = None
        self.initial_probs = None
        
    def fit(self, sequences):
        """Baum-Welch 알고리즘으로 모델 학습"""
        pass
        
    def predict(self, sequence):
        """Viterbi 알고리즘으로 상태 예측"""
        pass
        
    def decode_activities(self, tag_sequence):
        """태그 시퀀스를 활동으로 디코딩"""
        pass
```

## 5. 데이터 처리 파이프라인 (Data Processing Pipeline)

### 단계별 처리 과정
1. **데이터 로딩**: Excel → Pickle → DataFrame
2. **전처리**: 
   - 결측값 처리
   - 시간 정규화
   - 꼬리물기 현상 보정
3. **특성 추출**:
   - 위치 변화 패턴
   - 체류 시간 계산
   - 시간대별 특성
4. **HMM 학습**:
   - 초기 모델 설정
   - Baum-Welch 학습
   - 모델 검증
5. **활동 분류**:
   - Viterbi 예측
   - 신뢰도 계산
   - 후처리 규칙 적용
6. **시간 집계**:
   - 활동별 시간 계산
   - 일일 요약 생성
   - 조직 단위 집계

## 6. 네트워크 분석 (Network Analysis)

### 네트워크 분석의 목적
태그 데이터의 시계열 정보를 활용하여 조직 내 상호작용 패턴과 업무 흐름을 이해하고, 협업 효율성을 개선하기 위한 인사이트를 도출합니다.

### 분석 유형

#### 1. 직원 간 상호작용 네트워크 (Employee Interaction Network)
- **Co-location 분석**: 같은 공간에 동시에 있었던 직원들의 관계
- **협업 강도**: 상호작용 빈도와 지속 시간
- **부서 간 협업 매트릭스**: 부서별 상호작용 패턴
- **영향력 있는 직원 식별**: 네트워크 중심성 분석

#### 2. 공간 이동 네트워크 (Movement Network)
- **위치 간 전이 확률**: 어느 공간에서 어느 공간으로 이동하는지
- **병목 지점 발견**: 과도하게 집중되는 공간 식별
- **이동 경로 최적화**: 비효율적 동선 개선
- **시간대별 공간 활용도**: 공간의 시간대별 사용 패턴

#### 3. 시계열 동적 네트워크 (Temporal Dynamic Network)
- **시간대별 네트워크 변화**: 아침, 점심, 저녁, 야간 패턴
- **요일별 협업 패턴**: 주중/주말, 요일별 특성
- **프로젝트 기간별 분석**: 특정 기간 동안의 협업 강도 변화
- **실시간 네트워크 모니터링**: 현재 협업 상태 시각화

#### 4. 활동 기반 네트워크 (Activity-based Network)
- **업무 중심 네트워크**: 동일한 업무를 수행하는 직원들의 관계
- **식사 네트워크**: 함께 식사하는 그룹 분석
- **회의 네트워크**: 회의 참여 패턴 분석
- **휴식 네트워크**: 휴식 시간 상호작용 패턴

### 네트워크 분석 알고리즘

```python
class NetworkAnalyzer:
    def __init__(self):
        self.interaction_threshold = 5  # 최소 상호작용 시간 (분)
        
    def build_interaction_network(self, tag_data, time_window):
        """시간 윈도우 내 상호작용 네트워크 구축"""
        # 같은 시간, 같은 장소에 있었던 직원 쌍 추출
        # 상호작용 강도 계산
        # 네트워크 그래프 생성
        pass
        
    def analyze_centrality(self, network):
        """네트워크 중심성 분석"""
        # Degree centrality: 연결 수
        # Betweenness centrality: 중개자 역할
        # Closeness centrality: 접근성
        # Eigenvector centrality: 영향력
        pass
        
    def detect_communities(self, network):
        """커뮤니티 탐지 - 자연스럽게 형성된 그룹"""
        # Louvain algorithm
        # Modularity optimization
        pass
        
    def temporal_network_analysis(self, tag_data, time_granularity='hour'):
        """시계열 네트워크 분석"""
        # 시간대별 네트워크 스냅샷 생성
        # 네트워크 진화 패턴 분석
        # 이상 패턴 탐지
        pass
```

### 네트워크 메트릭

1. **개인 수준 메트릭**
   - Degree (연결 수): 얼마나 많은 동료와 상호작용하는가
   - Clustering coefficient: 연결된 동료들끼리도 연결되어 있는가
   - Bridge score: 서로 다른 그룹을 연결하는 역할

2. **조직 수준 메트릭**
   - Network density: 전체적인 연결 정도
   - Average path length: 정보 전달 효율성
   - Modularity: 부서/팀 구분의 명확성
   - Assortativity: 유사한 직급/부서끼리 상호작용하는 정도

### 시각화 전략

1. **네트워크 그래프**
   - Force-directed layout
   - 노드 크기: 중심성
   - 엣지 두께: 상호작용 강도
   - 색상: 부서/직급

2. **시계열 히트맵**
   - X축: 시간
   - Y축: 직원/공간
   - 색상 강도: 활동량/상호작용

3. **Sankey 다이어그램**
   - 공간 간 이동 흐름
   - 부서 간 협업 흐름

4. **애니메이션 네트워크**
   - 시간에 따른 네트워크 변화
   - 실시간 업데이트

### 기술 스택 추가
```python
# 네트워크 분석
networkx>=2.6.0
igraph>=0.9.0
community>=1.0.0
python-louvain>=0.15

# 시각화
pyvis>=0.2.0
bokeh>=2.4.0
holoviews>=1.14.0
```

## 7. UI/UX 설계 (UI/UX Design)

### 메인 대시보드
- **조직 개요**: 팀별 가동률, 평균 근무시간
- **실시간 현황**: 현재 활동 상태, 알림
- **트렌드 분석**: 주간/월간 트렌드 차트
- **네트워크 뷰**: 실시간 협업 네트워크 시각화

### 개인 상세 뷰
- **일일 활동 타임라인**: 시간대별 활동 시각화
- **월간 패턴 분석**: 캘린더 히트맵
- **개인 통계**: 평균 근무시간, 집중도 지수
- **개인 네트워크**: 협업 관계도, 상호작용 패턴

### 네트워크 분석 뷰
- **협업 네트워크**: 부서/팀/개인 단위 네트워크 그래프
- **이동 경로 맵**: 공간 이동 패턴 시각화
- **시계열 네트워크**: 시간에 따른 네트워크 변화 애니메이션
- **네트워크 메트릭**: 중심성, 밀도, 모듈성 등 지표

### HMM 규칙 편집기
- **전이 행렬 편집**: 인터랙티브 매트릭스 편집
- **방출 확률 설정**: 위치별 활동 확률 조정
- **모델 검증**: 테스트 데이터로 성능 확인

## 8. 기술 스택 (Technology Stack)

### 핵심 라이브러리
```python
# 데이터 처리
pandas>=1.5.0
numpy>=1.21.0
openpyxl>=3.0.0
pickle

# 머신러닝
scikit-learn>=1.0.0
hmmlearn>=0.2.7
scipy>=1.7.0

# 데이터베이스
sqlite3
sqlalchemy>=1.4.0

# 웹 UI
streamlit>=1.25.0
plotly>=5.0.0
matplotlib>=3.5.0
seaborn>=0.11.0

# 유틸리티
pydantic>=1.8.0
python-dateutil>=2.8.0
pytz>=2021.3

# 네트워크 분석
networkx>=2.6.0
igraph>=0.9.0
community>=1.0.0
python-louvain>=0.15

# 네트워크 시각화
pyvis>=0.2.0
bokeh>=2.4.0
holoviews>=1.14.0
```

### 개발 도구
- **IDE**: VSCode / PyCharm
- **버전 관리**: Git
- **테스팅**: pytest, unittest
- **문서화**: Sphinx, mkdocs
- **코드 품질**: black, flake8, mypy

## 9. 구현 단계 (Implementation Phases)

### Phase 1: 기본 인프라 구축 (2주)
- [ ] 프로젝트 구조 설정
- [ ] 데이터 로더 구현
- [ ] SQLite 데이터베이스 설정
- [ ] 기본 UI 프레임워크 구축

### Phase 2: 데이터 처리 및 전처리 (2주)
- [ ] 태그 데이터 전처리 로직 구현
- [ ] 데이터 검증 및 정제
- [ ] 시계열 데이터 특성 추출
- [ ] 배치 처리 시스템 구현

### Phase 3: HMM 모델 구현 (3주)
- [ ] HMM 클래스 기본 구조 구현
- [ ] Baum-Welch 학습 알고리즘 구현
- [ ] Viterbi 예측 알고리즘 구현
- [ ] 모델 성능 평가 시스템

### Phase 4: 분석 엔진 개발 (3주)
- [ ] 활동 분류 로직 구현
- [ ] 시간 집계 및 요약 기능
- [ ] 패턴 분석 알고리즘
- [ ] 조직 단위 집계 기능
- [ ] 네트워크 분석 엔진 구현
- [ ] 시계열 네트워크 분석 기능

### Phase 5: UI 개발 (4주)
- [ ] Streamlit 기반 대시보드
- [ ] 데이터 시각화 컴포넌트
- [ ] HMM 규칙 편집기
- [ ] 개인/조직별 리포트 뷰
- [ ] 네트워크 시각화 컴포넌트
- [ ] 시계열 네트워크 애니메이션

### Phase 6: 테스트 및 최적화 (1주)
- [ ] 단위 테스트 작성
- [ ] 통합 테스트 수행
- [ ] 성능 최적화
- [ ] 배포 준비

## 10. 위험 요소 및 대응 방안 (Risk Management)

### 기술적 위험
- **대용량 데이터 처리**: 청크 단위 처리, 메모리 최적화
- **HMM 모델 성능**: 하이퍼파라미터 튜닝, 교차 검증
- **실시간 처리**: 비동기 처리, 캐싱 시스템

### 데이터 품질 위험
- **꼬리물기 현상**: 통계적 보정 알고리즘 적용
- **결측 데이터**: 보간법 및 예측 모델 사용
- **노이즈 데이터**: 이상치 탐지 및 필터링

## 11. 성공 지표 (Success Metrics)

### 기술적 지표
- HMM 모델 정확도: >85%
- 데이터 처리 속도: <5분 (일일 데이터)
- 시스템 가용성: >99%

### 비즈니스 지표
- 근무시간 정확도: 실제 대비 ±5% 이내
- 사용자 만족도: 4.0/5.0 이상
- 시스템 채택률: 조직 내 80% 이상

## 12. 배포 및 운영 (Deployment & Operations)

### 배포 환경
- **개발**: 로컬 개발 환경
- **테스트**: Docker 컨테이너
- **운영**: 클라우드 또는 온프레미스

### 모니터링
- **시스템 모니터링**: 리소스 사용량, 응답 시간
- **데이터 품질 모니터링**: 데이터 무결성, 처리 성공률
- **비즈니스 메트릭**: 분석 정확도, 사용자 활동

---

**마지막 업데이트**: 2025-07-23  
**작성자**: Claude Code Assistant  
**버전**: 1.1  
**변경사항**: 네트워크 분석 섹션 추가 (시계열 협업 패턴, 공간 이동 네트워크, 동적 네트워크 분석)