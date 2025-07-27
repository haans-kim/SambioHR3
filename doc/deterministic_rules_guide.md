# 확정적 규칙 엔진 가이드

## 개요

확정적 규칙 엔진은 100% 확실한 상태를 즉시 확정하는 규칙 기반 시스템입니다. 
HMM의 확률적 접근법과 달리, 명확한 조건과 규칙으로 직원의 활동 상태를 분류합니다.

## 주요 특징

### 1. 우선순위 기반 규칙 처리
- **CRITICAL**: O 태그 등 최우선 규칙 (신뢰도 0.98)
- **HIGH**: 식사, 출퇴근 등 명확한 규칙 (신뢰도 0.95)
- **MEDIUM**: 회의, 교육, 준비 등 (신뢰도 0.90)
- **LOW**: 휴게, 경유 등 기본 규칙

### 2. 식사 시간 규칙
- **M1 (현장 식사)**: 다음 태그까지의 실제 시간 또는 최대 60분
- **M2 (테이크아웃)**: 고정 30분
- 법적 검토 후 설정 변경 가능

### 3. 신뢰도 기반 상태 표현
```python
StateWithConfidence(
    state=ActivityState.MEAL,
    confidence=0.98,
    evidence=[Evidence(...)],
    alternative_states=[]
)
```

## 사용 방법

### 기본 사용
```python
from src.tag_system.rule_integration import apply_rules_to_tags

# 태그 데이터
tags = [
    {'tag': 'T2', 'timestamp': datetime(2025, 7, 27, 8, 0)},
    {'tag': 'G2', 'timestamp': datetime(2025, 7, 27, 8, 5)},
    {'tag': 'O', 'timestamp': datetime(2025, 7, 27, 8, 10)},
]

# 규칙 적용
states = apply_rules_to_tags(tags)

for state in states:
    if state:
        print(f"{state.state.value} (신뢰도: {state.confidence})")
```

### 설정 관리
```python
from src.tag_system.rule_integration import get_rule_integration

integration = get_rule_integration()

# 현재 설정 확인
print(f"M1 최대 시간: {integration.rule_engine.config.meal_max_duration_minutes}분")

# 설정 변경
integration.update_config(
    meal_max_duration_minutes=50,
    takeout_fixed_duration_minutes=25
)
```

### JSON 설정 파일
`config/rules/deterministic_rules.json`에서 규칙을 관리합니다:

```json
{
  "config": {
    "meal_max_duration_minutes": 60,
    "takeout_fixed_duration_minutes": 30,
    "critical_confidence": 0.98,
    "high_confidence": 0.95,
    "medium_confidence": 0.90
  }
}
```

## 규칙 정의

### O 태그 규칙 (최우선)
- O 태그 존재 → 업무(확실) (0.98)
- O → G1/G2/G3 → 업무 (0.95)

### 식사 규칙
- M1 → 식사 (실제 시간 또는 최대 60분)
- M2 → 경유 (테이크아웃, 30분 고정)
- M2 → N2 → 휴게 (테이크아웃 후 휴게실 식사)

### 출입 규칙
- T2/T3 + 출근 시간대 → 출입(IN)
- T2/T3 + 퇴근 시간대 → 출입(OUT)

### 회의 규칙
- G3 + 30분 이상 → 회의
- 교대 시간 + G1/G3 → 회의(인수인계)

## 통합 아키텍처

```
태그 데이터
    ↓
[1단계: 확정적 규칙 엔진]
    ↓
확실한 상태는 즉시 확정 (신뢰도 0.9+)
    ↓
미확정 상태
    ↓
[2단계: 확률적 추론] (향후 구현)
    ↓
[3단계: 컨텍스트 보정] (향후 구현)
    ↓
최종 상태
```

## 파일 구조

```
src/tag_system/
├── confidence_state.py      # 신뢰도 기반 상태 클래스
├── rule_engine.py          # 확정적 규칙 엔진
├── rule_loader.py          # JSON 설정 로더
└── rule_integration.py     # 시스템 통합

config/rules/
└── deterministic_rules.json # 규칙 설정 파일

tests/
├── test_confidence_state.py
├── test_rule_engine.py
└── test_rule_loader.py
```

## 주의 사항

1. **법적 검토**: 식사 시간 규칙은 법적 검토가 필요합니다
2. **우선순위**: 높은 우선순위 규칙이 먼저 적용됩니다
3. **미확정 상태**: 확정적 규칙에 매칭되지 않는 경우 None 반환

## 향후 개선 계획

1. **Phase 2**: 확률적 추론 엔진 추가
2. **Phase 3**: 컨텍스트 기반 보정
3. **Phase 4**: A/B 테스트 프레임워크
4. **Phase 5**: 실시간 이상 탐지