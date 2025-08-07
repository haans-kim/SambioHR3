# 근무시간 추정률 메트릭 통합 완료

## 구현 완료 사항

### 1. 핵심 모듈 생성
- **ActivityDensityAnalyzer** (`src/analysis/activity_density_analyzer.py`)
  - 실제 활동(O태그, Knox 데이터) 밀도 계산
  - 무활동 구간 감지 (30분 이상)
  - 꼬리물기 패턴 감지 (입문 후 2시간 활동 없음)
  
- **WorkTimeEstimator** (`src/analysis/work_time_estimator.py`)
  - 직군별 기본 추정률 (생산직 85%, 사무직 65%)
  - 데이터 품질 평가 (태그 커버리지, 활동 밀도, 시간 연속성, 위치 다양성)
  - 신뢰구간 및 분산 계산
  
- **ImprovedActivityClassifier** (`src/analysis/improved_classifier.py`)
  - 활동 밀도 기반 실근무/비근무 분류
  - 개선 효과 측정

### 2. UI 컴포넌트
- **EstimationDisplay** (`src/ui/components/estimation_display.py`)
  - 게이지 차트로 추정 신뢰도 표시
  - 데이터 품질 세부 항목 표시
  - 근무시간 추정 범위 시각화

### 3. 개인별 대시보드 통합
- **IndividualDashboard** (`src/ui/components/individual_dashboard.py`)
  - WorkTimeEstimator 연동
  - execute_analysis에서 추정 메트릭 계산
  - Gantt 차트 상단에 추정률 표시

## 주요 기능

### 추정률 계산 로직
```python
# 1. 직군 판별
job_type = identify_job_type(daily_data, employee_info)
# 생산직: G1 태그 50% 이상 또는 O태그 20% 이상
# 사무직: G1 태그 30% 미만 및 O태그 10% 미만

# 2. 데이터 품질 평가 (0-1 점수)
- tag_coverage: 시간당 태그 수 (10개/시간 = 100%)
- activity_density: O태그/Knox 비율 (33% = 100%)  
- time_continuity: 태그 간격 중앙값 (10분 이하 = 100%)
- location_diversity: 방문 위치 수 (10개 이상 = 100%)

# 3. 추정률 조정
base_rate * (1 + (quality_score - 0.5) * 0.4)
# 품질 0.5 기준으로 ±20% 조정

# 4. 신뢰구간
95% 신뢰수준 = adjusted_rate ± 1.96 * sqrt(variance)
```

### UI 표시 내용
1. **메인 게이지**: 추정 신뢰도 퍼센트
2. **근무 유형**: 생산직/사무직/미분류
3. **데이터 품질**: 종합 품질 점수
4. **신뢰구간**: 95% 신뢰수준 범위
5. **추정 분산**: 낮음/보통/높음
6. **품질 상세**: 4개 항목별 점수 및 진행바
7. **추정 근무시간**: 최소/추정/최대 시간

## 사용자에게 제공되는 가치

### 1. 추정 정확도 파악
- 데이터 품질에 따른 신뢰도 표시
- 직군별 특성을 반영한 추정

### 2. 개선 방향 제시
- 품질 항목별 점수로 문제점 파악
- 구체적인 개선 권장사항 제공
  - 태그 리더기 추가 설치
  - 시스템 로그 연동 확대
  - 태그 인식 간격 개선
  - 이동 경로 태그 포인트 보강

### 3. 설명 가능한 분석
- 담당자에게 추정 근거 설명 가능
- 시각적 지표로 이해도 향상

## 테스트 방법

1. Streamlit 앱 실행
```bash
streamlit run src/ui/streamlit_app.py
```

2. 개인별 분석 탭 선택

3. 직원 선택 및 날짜 지정

4. 분석 실행 버튼 클릭

5. 상단에 표시되는 "📊 근무시간 추정 신뢰도" 섹션 확인

## 향후 개선 사항

1. **조직 전체 배치 분석 적용**
   - ImprovedClassifier의 batch_analyze_organization 활용
   - 부서별/팀별 추정률 집계

2. **추정률 히스토리 추적**
   - 시간에 따른 데이터 품질 개선 추이
   - 개선 효과 측정

3. **실시간 알림**
   - 추정률이 특정 임계값 이하일 때 경고
   - 데이터 수집 문제 실시간 감지