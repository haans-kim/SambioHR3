# API 설계 문서

## 개요
SambioHR2는 Streamlit 기반 웹 애플리케이션으로, REST API 대신 컴포넌트 기반 아키텍처를 사용합니다.

## 애플리케이션 진입점

### 1. 메인 애플리케이션 (`streamlit_app.py`)
```bash
streamlit run src/ui/streamlit_app.py
```

#### 페이지 라우팅
- **홈** - 메인 대시보드
- **데이터 업로드** - 파일 업로드 및 관리
- **개인별 분석** - 직원별 상세 분석
- **조직 분석** - 부서/팀 분석
- **모델 설정** - HMM 모델 설정
- **활동 분류 규칙 관리** - 태그 기반 규칙
- **네트워크 분석** - 조직 네트워크
- **실시간 모니터링** - 생산성 모니터링

### 2. 대체 진입점
- `timeline_app.py` - 타임라인 시각화
- `simple_app.py` - 단순화된 인터페이스
- `stable_app.py` - 안정화 버전

## 서비스 레이어 API

### 개인 분석 서비스 (`individual_analyzer.py`)

#### analyze_individual(employee_id, start_date, end_date)
개인별 종합 분석을 수행합니다.

**파라미터:**
- `employee_id`: 사번
- `start_date`: 시작일
- `end_date`: 종료일

**반환값:**
```python
{
    'work_time': {
        'total_hours': float,
        'actual_work_hours': float,
        'rest_hours': float,
        'efficiency_rate': float
    },
    'shift_patterns': {
        'day_count': int,
        'night_count': int,
        'pattern': str
    },
    'meal_times': {
        'breakfast': int,
        'lunch': int,
        'dinner': int,
        'midnight_meal': int
    },
    'activities': {
        'state_distribution': dict,
        'timeline': list
    }
}
```

### 조직 분석 서비스 (`organization_analyzer.py`)

#### analyze_organization(org_id, org_level, start_date, end_date)
조직 단위 분석을 수행합니다.

**파라미터:**
- `org_id`: 조직 ID
- `org_level`: 조직 레벨 (CENTER/BU/TEAM/GROUP/PART)
- `start_date`: 시작일
- `end_date`: 종료일

**반환값:**
```python
{
    'workforce': {
        'total_employees': int,
        'by_shift': dict,
        'by_department': dict
    },
    'productivity': {
        'average_efficiency': float,
        'work_hours_distribution': dict,
        'top_performers': list
    },
    'time_utilization': {
        'work': float,
        'rest': float,
        'meal': float,
        'movement': float
    }
}
```

## 데이터베이스 서비스 (`db_manager.py`)

### 주요 메서드

#### get_session()
데이터베이스 세션을 반환합니다.

#### execute_query(query, params)
SQL 쿼리를 실행합니다.

#### insert_dataframe(df, table_name)
데이터프레임을 테이블에 삽입합니다.

#### get_table_data(table_name, filters)
테이블 데이터를 조회합니다.

## 컴포넌트 인터페이스

### 1. 개인 대시보드
```python
class IndividualDashboard:
    def render(self):
        # 직원 선택
        # 기간 설정
        # 분석 실행
        # 결과 표시
```

### 2. 조직 대시보드
```python
class OrganizationDashboard:
    def render(self):
        # 조직 선택
        # 분석 유형 선택
        # 결과 시각화
```

### 3. 데이터 업로드
```python
class DataUploadComponent:
    def render(self):
        # 파일 유형 선택
        # 파일 업로드
        # 데이터 검증
        # DB 저장
```

## 데이터 플로우

```
Excel 파일 → Pickle 캐시 → SQLite DB → 분석 서비스 → Streamlit UI
```

### 1. 데이터 입력
- Excel 파일 업로드 (100MB+)
- Pickle 파일로 캐싱
- SQLite 데이터베이스 저장

### 2. 데이터 처리
- 2교대 근무 시간 변환
- 태그 데이터 분류
- HMM 모델 적용

### 3. 분석 및 출력
- 개인/조직 분석
- 시각화 차트 생성
- 리포트 출력

## 세션 상태 관리

Streamlit 세션 상태를 통한 데이터 유지:
```python
st.session_state['selected_employee'] = employee_id
st.session_state['analysis_results'] = results
st.session_state['filters'] = {...}
```

## 성능 최적화

### 1. Pickle 캐싱
대용량 Excel 파일 처리 시 pickle 파일로 중간 저장

### 2. 데이터베이스 인덱싱
주요 쿼리 성능 향상을 위한 인덱스

### 3. Progress Bar
장시간 작업 시 진행률 표시

## 에러 처리

### 1. 데이터 검증
- 파일 형식 검증
- 필수 컬럼 확인
- 데이터 타입 검증

### 2. 예외 처리
- try-except 블록
- 사용자 친화적 에러 메시지
- 로깅 시스템

## 보안 고려사항

### 1. 데이터 접근 제어
- 부서별 데이터 필터링
- 민감 정보 마스킹

### 2. 파일 업로드 제한
- 파일 크기 제한
- 파일 형식 검증