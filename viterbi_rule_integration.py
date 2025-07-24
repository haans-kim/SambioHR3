"""
Viterbi 알고리즘과 룰 시스템 통합 분석
"""

import streamlit as st
import pandas as pd
import numpy as np
from src.hmm.hmm_model import HMMModel
from src.hmm.viterbi import ViterbiAlgorithm
from src.rules.rule_manager import RuleManager

def explain_viterbi_rule_relationship():
    """Viterbi 알고리즘과 룰의 관계 설명"""
    
    st.title("Viterbi 알고리즘과 전이 룰의 관계")
    
    st.markdown("""
    ## 🔄 현재 시스템 구조
    
    ### 1. Viterbi 알고리즘이 사용하는 것
    - **전이 확률 행렬 (Transition Matrix)**: `hmm_model.transition_matrix[i, j]`
    - **방출 확률 행렬 (Emission Matrix)**: `hmm_model.emission_matrix`
    - **초기 확률 (Initial Probabilities)**: `hmm_model.initial_probabilities`
    
    ### 2. 룰 시스템이 제공하는 것
    - **조건부 전이 확률**: 시간, 위치, 상황에 따른 동적 확률
    - **도메인 지식**: 식사 시간, 교대 패턴 등
    """)
    
    # HMM 모델과 룰 관리자 초기화
    hmm_model = HMMModel()
    rule_manager = RuleManager()
    viterbi = ViterbiAlgorithm(hmm_model)
    
    # 현재 구조 분석
    st.markdown("### 📊 현재 구조 분석")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Viterbi 알고리즘 (`viterbi.py:156-158`)")
        st.code("""
# 현재: 고정된 전이 확률 사용
for i in range(N):
    transition_prob = self.hmm_model.transition_matrix[i, j]
    score = log_delta[t-1, i] + np.log(transition_prob + 1e-10)
        """, language='python')
    
    with col2:
        st.markdown("#### 개선된 구조 (룰 기반)")
        st.code("""
# 제안: 컨텍스트 기반 동적 확률
for i in range(N):
    context = self._get_context(t, observation_sequence)
    transition_prob = self.hmm_model.get_transition_probability_with_conditions(
        from_state=self.hmm_model.index_to_state[i],
        to_state=self.hmm_model.index_to_state[j],
        context=context
    )
    score = log_delta[t-1, i] + np.log(transition_prob + 1e-10)
        """, language='python')
    
    # 룰 통계 표시
    st.markdown("### 📈 룰 시스템 통계")
    rules = rule_manager.load_all_rules()
    stats = rule_manager.get_rule_statistics()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("전체 룰", len(rules))
    with col2:
        st.metric("조건부 룰", sum(1 for r in rules if len(r.conditions) > 0))
    with col3:
        st.metric("평균 조건 수", f"{stats['avg_conditions_per_rule']:.1f}")
    
    # 예시: 점심시간 전이
    st.markdown("### 🍽️ 예시: 점심시간 전이 확률")
    
    lunch_example = {
        'current_time': '12:30',
        'location': 'CAFETERIA',
        'shift_type': '주간'
    }
    
    # 룰 기반 확률 계산
    work_to_lunch_prob = hmm_model.get_transition_probability_with_conditions(
        '근무', '중식', lunch_example
    )
    
    # 기본 확률과 비교
    if hmm_model.transition_matrix is not None:
        base_prob = hmm_model.transition_matrix[
            hmm_model.state_to_index['근무'],
            hmm_model.state_to_index['중식']
        ]
    else:
        base_prob = 0.2  # 기본값
    
    comparison_df = pd.DataFrame({
        '방법': ['고정 확률 (현재)', '룰 기반 확률 (개선)'],
        '확률': [base_prob, work_to_lunch_prob],
        '설명': [
            'Viterbi가 현재 사용하는 고정된 전이 확률',
            '시간과 위치를 고려한 동적 전이 확률'
        ]
    })
    
    st.dataframe(comparison_df)
    
    # 개선 방안
    st.markdown("""
    ### 🚀 통합 방안
    
    1. **Viterbi 알고리즘 수정**
       - `_viterbi_algorithm` 메서드에서 룰 기반 확률 사용
       - 각 시점의 컨텍스트 정보 추가
    
    2. **컨텍스트 추출**
       - 현재 시간, 위치, 교대 타입 등을 observation에서 추출
       - 컨텍스트를 룰 매니저에 전달
    
    3. **동적 확률 계산**
       - 룰이 있으면 조건부 확률 사용
       - 룰이 없으면 기본 전이 확률 사용 (fallback)
    """)
    
    # 코드 예시
    st.markdown("### 💻 구현 예시")
    st.code("""
# viterbi.py 수정 제안
def _viterbi_algorithm_with_rules(self, observation_sequence):
    # ... 초기화 코드 ...
    
    for t in range(1, T):
        # 현재 관측값에서 컨텍스트 추출
        context = {
            'current_time': observation_sequence[t].get('timestamp', '').time(),
            'location': observation_sequence[t].get('태그위치', ''),
            'shift_type': observation_sequence[t].get('shift_type', '주간'),
            'duration_minutes': self._calculate_duration(t, observation_sequence)
        }
        
        for j in range(N):
            transition_scores = []
            for i in range(N):
                # 룰 기반 전이 확률 사용
                from_state = self.hmm_model.index_to_state[i]
                to_state = self.hmm_model.index_to_state[j]
                
                # 조건부 확률 계산
                transition_prob = self.hmm_model.get_transition_probability_with_conditions(
                    from_state, to_state, context
                )
                
                score = log_delta[t-1, i] + np.log(transition_prob + 1e-10)
                transition_scores.append(score)
            
            # ... 나머지 코드 ...
    """, language='python')
    
    st.markdown("""
    ### ✅ 장점
    1. **정확도 향상**: 상황별 맞춤 확률로 예측 정확도 상승
    2. **유연성**: UI에서 룰 수정 시 즉시 반영
    3. **도메인 지식 활용**: 업무 패턴을 룰로 쉽게 표현
    4. **디버깅 용이**: 어떤 룰이 적용되었는지 추적 가능
    """)

if __name__ == "__main__":
    st.set_page_config(page_title="Viterbi-Rule Integration", layout="wide")
    explain_viterbi_rule_relationship()