# 하이브리드 태그 분류 시스템 개선 계획

## 개요
현재의 확정적 규칙 기반 시스템의 한계를 극복하고, HMM의 장점을 결합한 하이브리드 접근법을 통해 더 정확하고 유연한 직원 활동 분류 시스템을 구축한다.

## 1. 핵심 개선 사항

### 1.1 3단계 분류 아키텍처

```
입력 데이터 → [1단계: 확정적 규칙] → [2단계: 확률적 추론] → [3단계: 컨텍스트 보정] → 최종 상태
```

#### 1단계: 확정적 규칙 (Deterministic Rules)
- **목적**: 100% 확실한 상태를 즉시 확정
- **적용 대상**:
  - O 태그가 있는 경우 → 업무 확정
  - M1 태그 + 식사 시간대 → 식사 확정
  - T2/T3 태그 + 출퇴근 시간대 → 출입 확정
- **신뢰도**: 0.95 ~ 1.0

#### 2단계: 확률적 추론 (Probabilistic Inference)
- **목적**: 모호한 상황에 대한 확률적 판단
- **적용 대상**:
  - G1 → G1 장시간 체류
  - T1 → T1 이동 패턴
  - 태그 누락 구간
- **방법**: 베이지안 추론 + 시간 가중치
- **신뢰도**: 0.6 ~ 0.94

#### 3단계: 컨텍스트 보정 (Context Adjustment)
- **목적**: 개인/부서/시간대별 특성 반영
- **고려 사항**:
  - 직무 특성 (생산직/사무직/연구직)
  - 근무 패턴 (주간/야간/교대)
  - 협업 네트워크
- **신뢰도 조정**: ±0.1 ~ 0.2

### 1.2 신뢰도 기반 상태 표현

```python
@dataclass
class StateWithConfidence:
    state: ActivityState          # 분류된 상태
    confidence: float             # 신뢰도 (0.0 ~ 1.0)
    evidence: List[Evidence]      # 판단 근거
    alternative_states: List[Tuple[ActivityState, float]]  # 대안 상태들
    
@dataclass
class Evidence:
    type: str                     # 'rule', 'probability', 'context'
    description: str              # 판단 근거 설명
    weight: float                # 근거의 가중치
```

## 2. 상세 구현 계획

### 2.1 Phase 1: 핵심 인프라 구축 (2주)

#### Week 1: 기본 구조 구현
1. **StateWithConfidence 시스템 구현**
   - `src/tag_system/confidence_state.py` 생성
   - 신뢰도 계산 로직 구현
   - Evidence 추적 시스템

2. **시간 정규화 시스템**
   - `src/utils/time_normalizer.py` 생성
   - UTC 기반 내부 처리
   - 야간 근무자 전용 시간 변환

3. **태그 전처리 파이프라인**
   - `src/data_processing/tag_preprocessor.py` 개선
   - 중복 제거 알고리즘
   - 누락 보간 로직
   - 이상치 탐지

#### Week 2: 확정적 규칙 엔진
1. **규칙 엔진 구현**
   ```python
   class DeterministicRuleEngine:
       def apply_rules(self, tag_sequence: List[Tag]) -> Optional[StateWithConfidence]:
           # O 태그 규칙
           if self._has_o_tag(tag_sequence):
               return StateWithConfidence(
                   state=ActivityState.WORK_CONFIRMED,
                   confidence=0.98,
                   evidence=[Evidence('rule', 'O 태그 존재', 1.0)]
               )
           # M1 태그 + 식사 시간
           if self._is_meal_pattern(tag_sequence):
               return StateWithConfidence(...)
   ```

2. **규칙 우선순위 관리**
   - 규칙 충돌 해결
   - 우선순위 기반 적용

### 2.2 Phase 2: 확률적 추론 엔진 (3주)

#### Week 3-4: 베이지안 추론 구현
1. **전이 확률 학습**
   ```python
   class ProbabilisticInferenceEngine:
       def __init__(self):
           self.transition_probs = {}  # 학습된 전이 확률
           self.duration_models = {}   # 체류 시간 분포
           
       def infer_state(self, tag_sequence: List[Tag], 
                      context: Context) -> StateWithConfidence:
           # 베이지안 추론
           prior = self._get_prior(context)
           likelihood = self._calculate_likelihood(tag_sequence)
           posterior = self._bayesian_update(prior, likelihood)
           
           return self._create_state_with_confidence(posterior)
   ```

2. **시간 기반 가중치**
   - 체류 시간 분포 모델링
   - 시간대별 활동 패턴

#### Week 5: 컨텍스트 엔진
1. **개인/부서 프로파일링**
   ```python
   class ContextEngine:
       def adjust_confidence(self, 
                           initial_state: StateWithConfidence,
                           employee_profile: EmployeeProfile,
                           temporal_context: TemporalContext) -> StateWithConfidence:
           # 직무별 조정
           job_adjustment = self._get_job_adjustment(
               employee_profile.job_type, 
               initial_state.state
           )
           # 시간대별 조정
           time_adjustment = self._get_temporal_adjustment(
               temporal_context, 
               initial_state.state
           )
           
           # 신뢰도 조정
           adjusted_confidence = initial_state.confidence * (1 + job_adjustment + time_adjustment)
           return StateWithConfidence(..., confidence=adjusted_confidence)
   ```

### 2.3 Phase 3: 통합 및 최적화 (2주)

#### Week 6: 시스템 통합
1. **하이브리드 분류기 구현**
   ```python
   class HybridStateClassifier:
       def __init__(self):
           self.rule_engine = DeterministicRuleEngine()
           self.prob_engine = ProbabilisticInferenceEngine()
           self.context_engine = ContextEngine()
           
       def classify(self, tag_sequence: List[Tag], 
                   context: Context) -> StateWithConfidence:
           # 1단계: 확정적 규칙
           rule_result = self.rule_engine.apply_rules(tag_sequence)
           if rule_result and rule_result.confidence >= 0.95:
               return rule_result
               
           # 2단계: 확률적 추론
           prob_result = self.prob_engine.infer_state(tag_sequence, context)
           
           # 3단계: 컨텍스트 보정
           final_result = self.context_engine.adjust_confidence(
               prob_result, context.employee_profile, context.temporal
           )
           
           return final_result
   ```

2. **캐싱 및 성능 최적화**
   - 결과 캐싱
   - 배치 처리 최적화

#### Week 7: A/B 테스트 프레임워크
1. **비교 분석 도구**
   ```python
   class ABTestFramework:
       def compare_systems(self, test_data: DataFrame) -> ComparisonReport:
           old_results = self.old_system.classify_batch(test_data)
           new_results = self.new_system.classify_batch(test_data)
           
           return ComparisonReport(
               agreement_rate=self._calculate_agreement(old_results, new_results),
               confidence_improvement=self._analyze_confidence(old_results, new_results),
               edge_cases=self._identify_edge_cases(old_results, new_results)
           )
   ```

### 2.4 Phase 4: 배포 및 모니터링 (2주)

#### Week 8-9: 점진적 배포
1. **Feature Toggle 시스템**
   ```python
   HYBRID_SYSTEM_ENABLED = {
       'default': False,
       'departments': {
           'production_team_a': True,  # 파일럿 그룹
           'research_team': True
       },
       'rollout_percentage': 10  # 전체의 10%만 새 시스템 사용
   }
   ```

2. **모니터링 대시보드**
   - 실시간 정확도 추적
   - 신뢰도 분포 시각화
   - 에러 케이스 알림

## 3. 데이터 마이그레이션 전략

### 3.1 기존 데이터 변환
```python
class DataMigrator:
    def migrate_historical_data(self):
        # 1. 기존 HMM 결과 백업
        self.backup_existing_results()
        
        # 2. 새 시스템으로 재처리
        for batch in self.get_data_batches():
            old_results = batch['hmm_results']
            new_results = self.hybrid_classifier.classify_batch(batch['raw_data'])
            
            # 3. 차이 분석 및 검증
            if self._validate_results(old_results, new_results):
                self.save_new_results(new_results)
            else:
                self.log_discrepancy(batch, old_results, new_results)
```

### 3.2 실시간 전환 계획
1. **Shadow Mode 운영** (2주)
   - 두 시스템 병행 실행
   - 결과만 기록, UI에는 기존 시스템 표시

2. **Canary Deployment** (2주)
   - 선택된 부서만 새 시스템 사용
   - 피드백 수집 및 개선

3. **Full Rollout** (1주)
   - 전체 전환
   - 롤백 계획 준비

## 4. 성공 지표 (KPI)

### 4.1 정량적 지표
- **분류 정확도**: 85% → 92% (목표)
- **평균 신뢰도**: 0.7 → 0.85 (목표)
- **처리 속도**: 현재 대비 30% 향상
- **에러율**: 5% → 2% (목표)

### 4.2 정성적 지표
- 현장 관리자 만족도
- 규칙 수정 용이성
- 시스템 투명성 (판단 근거 명확성)

## 5. 위험 관리

### 5.1 기술적 위험
| 위험 | 영향도 | 대응 방안 |
|------|--------|-----------|
| 성능 저하 | High | 캐싱 강화, 비동기 처리 |
| 데이터 불일치 | High | Shadow mode 검증 |
| 복잡도 증가 | Medium | 모듈화, 문서화 |

### 5.2 운영적 위험
| 위험 | 영향도 | 대응 방안 |
|------|--------|-----------|
| 사용자 저항 | Medium | 단계적 교육, 파일럿 운영 |
| 롤백 필요성 | Low | Feature toggle, 백업 |

## 6. 타임라인 요약

```
Week 1-2:  기본 인프라 구축
Week 3-5:  확률적 추론 엔진 개발
Week 6-7:  시스템 통합 및 A/B 테스트
Week 8-9:  점진적 배포
Week 10:   전체 전환 및 안정화
```

## 7. 다음 단계

1. **즉시 시작 가능한 작업**
   - StateWithConfidence 클래스 구현
   - 시간 정규화 모듈 개발
   - 태그 전처리 파이프라인 개선

2. **준비 필요한 작업**
   - 베이지안 추론 엔진 설계 상세화
   - A/B 테스트 데이터셋 준비
   - 파일럿 부서 선정

3. **장기 과제**
   - ML 기반 패턴 학습 연구
   - 실시간 이상 탐지 시스템
   - 예측 분석 기능 개발