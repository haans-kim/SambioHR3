"""
Test script to verify rule editor functionality
"""

import streamlit as st
from src.ui.components.transition_rule_editor import TransitionRuleEditor

st.set_page_config(page_title="Rule Editor Test", layout="wide")

st.title("전이 룰 에디터 테스트")

# Initialize and render the rule editor
editor = TransitionRuleEditor()

# Display rule statistics
st.sidebar.markdown("### 룰 통계")
rules = editor.rule_manager.load_all_rules()
st.sidebar.metric("전체 룰", len(rules))
st.sidebar.metric("활성 룰", len([r for r in rules if r.is_active]))

# Render the editor
editor.render()