# 하이브리드 시스템 실행 계획

## 즉시 시작 (Week 1) - 기초 인프라 구축

### 1. StateWithConfidence 클래스 구현

**파일 생성**: `src/tag_system/confidence_state.py`

```python
from dataclasses import dataclass
from typing import List, Tuple, Optional
from enum import Enum
from datetime import datetime

@dataclass
class Evidence:
    """상태 판단 근거"""
    type: str  # 'rule', 'probability', 'context'
    description: str
    weight: float
    timestamp: datetime

@dataclass
class StateWithConfidence:
    """신뢰도를 포함한 상태 정보"""
    state: str  # ActivityState
    confidence: float  # 0.0 ~ 1.0
    evidence: List[Evidence]
    alternative_states: List[Tuple[str, float]]
    
    def to_dict(self):
        return {
            'state': self.state,
            'confidence': self.confidence,
            'evidence': [e.__dict__ for e in self.evidence],
            'alternatives': self.alternative_states
        }
```

**작업 순서**:
1. 기본 클래스 구조 구현
2. 신뢰도 계산 메서드 추가
3. Evidence 추적 시스템 구현
4. 단위 테스트 작성

### 2. 시간 정규화 시스템

**파일 생성**: `src/utils/time_normalizer.py`

```python
import pytz
from datetime import datetime, time, timedelta

class TimeNormalizer:
    """시간 정규화 및 야간 근무 처리"""
    
    def __init__(self, timezone='Asia/Seoul'):
        self.timezone = pytz.timezone(timezone)
        
    def normalize_to_utc(self, local_time: datetime) -> datetime:
        """로컬 시간을 UTC로 변환"""
        return self.timezone.localize(local_time).astimezone(pytz.UTC)
        
    def get_work_date(self, timestamp: datetime, is_night_shift: bool) -> datetime:
        """야간 근무자의 경우 근무 날짜 조정"""
        if is_night_shift and timestamp.hour < 12:
            # 오전 시간은 전날 근무로 간주
            return (timestamp - timedelta(days=1)).date()
        return timestamp.date()
        
    def is_in_meal_window(self, timestamp: datetime, meal_type: str) -> bool:
        """식사 시간대 판별 (자정 넘는 경우 처리)"""
        meal_windows = {
            'breakfast': [(6, 30), (9, 0)],
            'lunch': [(11, 20), (13, 20)],
            'dinner': [(17, 0), (20, 0)],
            'midnight': [(23, 30), (25, 0)]  # 25:00 = 다음날 01:00
        }
        # 구현...
```

**작업 순서**:
1. UTC 변환 로직 구현
2. 야간 근무자 날짜 처리
3. 자정 넘는 시간대 처리
4. 통합 테스트

### 3. 태그 전처리 파이프라인 개선

**파일 수정**: `src/data_processing/tag_preprocessor.py`

```python
class TagPreprocessor:
    """태그 데이터 전처리 파이프라인"""
    
    def __init__(self):
        self.duplicate_threshold = timedelta(seconds=30)
        self.gap_threshold = timedelta(hours=3)
        
    def preprocess(self, raw_tags: pd.DataFrame) -> pd.DataFrame:
        """전처리 파이프라인 실행"""
        tags = raw_tags.copy()
        
        # 1. 중복 제거
        tags = self._remove_duplicates(tags)
        
        # 2. 시간 정규화
        tags = self._normalize_times(tags)
        
        # 3. 누락 보간
        tags = self._interpolate_missing(tags)
        
        # 4. 이상치 탐지
        tags = self._detect_anomalies(tags)
        
        return tags
        
    def _remove_duplicates(self, tags: pd.DataFrame) -> pd.DataFrame:
        """30초 내 동일 위치 태그 제거"""
        # 구현...
        
    def _interpolate_missing(self, tags: pd.DataFrame) -> pd.DataFrame:
        """3시간 이상 공백 시 경로 추정"""
        # 구현...
```

## Week 2 - 확정적 규칙 엔진

### 4. 규칙 엔진 구현

**파일 생성**: `src/tag_system/rule_engine.py`

```python
class DeterministicRuleEngine:
    """확정적 규칙 기반 분류 엔진"""
    
    def __init__(self):
        self.rules = self._initialize_rules()
        
    def apply_rules(self, tag_data: dict) -> Optional[StateWithConfidence]:
        """규칙 적용하여 상태 분류"""
        
        # O 태그 확인
        if tag_data.get('has_o_tag'):
            return StateWithConfidence(
                state='업무',
                confidence=0.98,
                evidence=[Evidence(
                    type='rule',
                    description='O 태그 존재로 업무 확정',
                    weight=1.0,
                    timestamp=datetime.now()
                )],
                alternative_states=[]
            )
            
        # M1 태그 + 식사 시간
        if tag_data['tag'] == 'M1' and self._is_meal_time(tag_data['timestamp']):
            return StateWithConfidence(
                state='식사',
                confidence=1.0,
                evidence=[Evidence(
                    type='rule',
                    description=f"M1 태그 + {self._get_meal_type(tag_data['timestamp'])} 시간",
                    weight=1.0,
                    timestamp=datetime.now()
                )],
                alternative_states=[]
            )
            
        # T2/T3 출퇴근
        if tag_data['tag'] in ['T2', 'T3']:
            return self._classify_entry_exit(tag_data)
            
        return None  # 확정적 규칙 미적용
```

## Week 3-4 - 확률적 추론 엔진

### 5. 베이지안 추론 구현

**파일 생성**: `src/tag_system/probabilistic_engine.py`

```python
import numpy as np
from scipy import stats

class ProbabilisticInferenceEngine:
    """베이지안 기반 확률적 추론 엔진"""
    
    def __init__(self):
        self.transition_matrix = self._load_transition_matrix()
        self.duration_models = self._load_duration_models()
        
    def infer_state(self, tag_sequence: List[dict], context: dict) -> StateWithConfidence:
        """태그 시퀀스로부터 상태 추론"""
        
        # 사전 확률
        prior = self._calculate_prior(context)
        
        # 우도 계산
        likelihood = self._calculate_likelihood(tag_sequence)
        
        # 베이지안 업데이트
        posterior = self._bayesian_update(prior, likelihood)
        
        # 상위 3개 상태 선택
        top_states = self._get_top_states(posterior, n=3)
        
        return StateWithConfidence(
            state=top_states[0][0],
            confidence=top_states[0][1],
            evidence=[
                Evidence(
                    type='probability',
                    description=f'베이지안 추론 (prior={prior[top_states[0][0]]:.2f})',
                    weight=0.8,
                    timestamp=datetime.now()
                )
            ],
            alternative_states=top_states[1:]
        )
```

## 즉시 실행 가능한 작업들

### 오늘 시작할 수 있는 것:

1. **StateWithConfidence 클래스 작성** (2-3시간)
   ```bash
   # 파일 생성 및 기본 구조 구현
   touch src/tag_system/confidence_state.py
   # 테스트 파일 작성
   touch tests/test_confidence_state.py
   ```

2. **시간 정규화 모듈 개발** (3-4시간)
   ```bash
   # 야간 근무자 시간 처리 버그 수정 포함
   touch src/utils/time_normalizer.py
   touch tests/test_time_normalizer.py
   ```

3. **기존 버그 수정** (1-2시간)
   - GATE 이동 경로 문제 (TODO.md에 언급)
   - 야간 근무자 날짜 처리

### 이번 주 내 완료 목표:

1. **Week 1 작업 완료**
   - 3개 핵심 모듈 구현
   - 단위 테스트 작성
   - 기존 시스템과 통합 준비

2. **파일럿 데이터 준비**
   - 테스트용 직원 선정
   - 비교 분석용 데이터셋 구성

### 점진적 통합 전략:

```python
# config/settings.py
FEATURE_FLAGS = {
    'USE_HYBRID_CLASSIFIER': False,  # 초기값
    'HYBRID_PILOT_EMPLOYEES': [],    # 파일럿 직원 ID
    'CONFIDENCE_THRESHOLD': 0.8,     # 신뢰도 임계값
}

# 기존 코드에 통합
def classify_activity(tag_data):
    if FEATURE_FLAGS['USE_HYBRID_CLASSIFIER']:
        return hybrid_classifier.classify(tag_data)
    else:
        return legacy_classifier.classify(tag_data)
```

이렇게 단계별로 진행하면서 기존 시스템의 안정성을 유지하며 점진적으로 개선할 수 있습니다.

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"id": "1", "content": "Week 1: StateWithConfidence \ud074\ub798\uc2a4 \uad6c\ud604", "status": "completed", "priority": "high"}, {"id": "7", "content": "\uc624\ub298: StateWithConfidence \ud074\ub798\uc2a4 \uc791\uc131 (2-3\uc2dc\uac04)", "status": "pending", "priority": "high"}, {"id": "8", "content": "\uc624\ub298: \uc2dc\uac04 \uc815\uaddc\ud654 \ubaa8\ub4c8 \uac1c\ubc1c (3-4\uc2dc\uac04)", "status": "pending", "priority": "high"}, {"id": "9", "content": "\uc624\ub298: GATE \uc774\ub3d9 \uacbd\ub85c \ubc84\uadf8 \uc218\uc815 (1-2\uc2dc\uac04)", "status": "pending", "priority": "high"}]