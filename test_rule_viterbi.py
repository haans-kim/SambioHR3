"""
룰 기반 Viterbi 테스트
"""

import streamlit as st
from datetime import datetime, time
from src.hmm.hmm_model import HMMModel
from src.hmm.viterbi_with_rules import RuleBasedViterbiAlgorithm
from src.hmm.viterbi import ViterbiAlgorithm

st.set_page_config(page_title="Rule-based Viterbi Test", layout="wide")

st.title("룰 기반 Viterbi vs 기본 Viterbi 비교")

# 테스트 데이터 생성
test_observations = [
    {
        'timestamp': datetime(2025, 1, 24, 8, 0),
        '태그위치': 'OFFICE',
        'shift_type': '주간'
    },
    {
        'timestamp': datetime(2025, 1, 24, 12, 30),
        '태그위치': 'CAFETERIA',
        'shift_type': '주간'
    },
    {
        'timestamp': datetime(2025, 1, 24, 13, 0),
        '태그위치': 'CAFETERIA',
        'shift_type': '주간'
    },
    {
        'timestamp': datetime(2025, 1, 24, 13, 30),
        '태그위치': 'OFFICE',
        'shift_type': '주간'
    }
]

# HMM 모델 초기화
col1, col2 = st.columns(2)

with col1:
    st.markdown("### 🔵 기본 Viterbi (고정 확률)")
    hmm_basic = HMMModel(use_rules=False)
    hmm_basic.initialize_parameters("domain_knowledge")
    viterbi_basic = ViterbiAlgorithm(hmm_basic)
    
    # 예측
    result_basic = viterbi_basic.predict(test_observations)
    
    st.write("예측 상태:")
    for i, (obs, state) in enumerate(zip(test_observations, result_basic['states'])):
        st.write(f"{obs['timestamp'].strftime('%H:%M')} - {obs['태그위치']} → **{state}**")
    
    st.metric("신뢰도", f"{result_basic['confidence']:.2%}")

with col2:
    st.markdown("### 🟢 룰 기반 Viterbi (조건부 확률)")
    hmm_rules = HMMModel(use_rules=True)
    hmm_rules.initialize_parameters("domain_knowledge")
    viterbi_rules = RuleBasedViterbiAlgorithm(hmm_rules)
    
    # 예측
    result_rules = viterbi_rules.predict(test_observations)
    
    st.write("예측 상태:")
    for i, (obs, state) in enumerate(zip(test_observations, result_rules['states'])):
        st.write(f"{obs['timestamp'].strftime('%H:%M')} - {obs['태그위치']} → **{state}**")
    
    st.metric("신뢰도", f"{result_rules['confidence']:.2%}")
    
    # 적용된 룰 표시
    if 'applied_rules' in result_rules and result_rules['applied_rules']:
        st.markdown("#### 적용된 룰:")
        for rule in result_rules['applied_rules']:
            st.write(f"- {rule['from_state']} → {rule['to_state']} (신뢰도 {rule['confidence']}%)")

# 비교 분석
st.markdown("---")
st.markdown("### 📊 비교 분석")

# 12:30 CAFETERIA에서의 전이 확률 비교
if hmm_basic.transition_matrix is not None:
    basic_prob = hmm_basic.transition_matrix[
        hmm_basic.state_to_index.get('근무', 0),
        hmm_basic.state_to_index.get('중식', 0)
    ]
else:
    basic_prob = 0.2

context = {
    'current_time': datetime(2025, 1, 24, 12, 30),
    'location': 'CAFETERIA',
    'shift_type': '주간'
}
rule_prob = hmm_rules.get_transition_probability_with_conditions('근무', '중식', context)

comparison_data = {
    '방법': ['기본 Viterbi', '룰 기반 Viterbi'],
    '근무→중식 확률': [f"{basic_prob:.2f}", f"{rule_prob:.2f}"],
    '설명': [
        '고정된 전이 확률 사용',
        '12:30 + CAFETERIA 조건 반영'
    ]
}

st.dataframe(comparison_data)

st.info("""
💡 **차이점**:
- **기본 Viterbi**: 모든 상황에서 동일한 전이 확률 사용
- **룰 기반 Viterbi**: 시간, 위치, 교대 타입에 따라 동적으로 확률 조정
- **에디터에서 룰 수정 시**: 룰 기반 Viterbi의 예측이 즉시 변경됨
""")