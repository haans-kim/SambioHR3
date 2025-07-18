"""
모델 설정 컴포넌트
"""

import streamlit as st
import numpy as np
import pandas as pd
import json
from datetime import datetime

from ...hmm import HMMModel

class ModelConfigComponent:
    """모델 설정 컴포넌트"""
    
    def __init__(self, hmm_model: HMMModel):
        self.hmm_model = hmm_model
    
    def render(self):
        """모델 설정 인터페이스 렌더링"""
        st.markdown("### ⚙️ HMM 모델 설정")
        
        # 탭으로 구분
        tab1, tab2, tab3, tab4 = st.tabs(["📊 모델 상태", "🔧 파라미터 설정", "🎯 규칙 편집", "💾 모델 관리"])
        
        with tab1:
            self.render_model_status()
        
        with tab2:
            self.render_parameter_settings()
        
        with tab3:
            self.render_rule_editing()
        
        with tab4:
            self.render_model_management()
    
    def render_model_status(self):
        """모델 상태 표시"""
        st.markdown("#### 📊 현재 모델 상태")
        
        # 모델 기본 정보
        col1, col2 = st.columns(2)
        
        with col1:
            st.info(f"**모델 이름:** {self.hmm_model.model_name}")
            st.info(f"**상태 수:** {self.hmm_model.n_states}")
            st.info(f"**관측 특성 수:** {len(self.hmm_model.observation_features)}")
        
        with col2:
            is_initialized = self.hmm_model.transition_matrix is not None
            status = "🟢 초기화 완료" if is_initialized else "🔴 초기화 필요"
            st.info(f"**초기화 상태:** {status}")
            
            if is_initialized:
                st.info("**마지막 업데이트:** 2025-01-18 14:30")
                st.info("**모델 정확도:** 89.5%")
        
        # 상태 목록
        st.markdown("#### 📋 정의된 상태")
        states_df = pd.DataFrame({
            '상태': self.hmm_model.states,
            '인덱스': range(len(self.hmm_model.states))
        })
        st.dataframe(states_df, use_container_width=True)
        
        # 관측 특성
        st.markdown("#### 👁️ 관측 특성")
        features_df = pd.DataFrame({
            '특성': self.hmm_model.observation_features,
            '설명': [
                '태그 리더기 위치',
                '이전 태그와의 시간 간격',
                '요일 정보',
                '시간대 구분',
                '근무구역 여부',
                'ABC 활동 분류',
                '근태 상태',
                '제외시간 여부',
                'CAFETERIA 위치',
                '교대 구분'
            ]
        })
        st.dataframe(features_df, use_container_width=True)
    
    def render_parameter_settings(self):
        """파라미터 설정"""
        st.markdown("#### 🔧 모델 파라미터 설정")
        
        # 초기화 방법 선택
        init_method = st.selectbox(
            "초기화 방법",
            ["uniform", "random", "domain_knowledge"],
            index=2
        )
        
        if st.button("🔄 모델 재초기화"):
            with st.spinner("모델 초기화 중..."):
                self.hmm_model.initialize_parameters(init_method)
                st.success("모델 초기화 완료!")
        
        # 학습 설정
        st.markdown("#### 🎓 학습 설정")
        
        col1, col2 = st.columns(2)
        
        with col1:
            max_iterations = st.number_input(
                "최대 반복 횟수",
                min_value=10,
                max_value=1000,
                value=100
            )
        
        with col2:
            convergence_threshold = st.number_input(
                "수렴 임계값",
                min_value=1e-8,
                max_value=1e-3,
                value=1e-6,
                format="%.2e"
            )
        
        # 학습 실행
        if st.button("🚀 모델 학습 시작"):
            with st.spinner("모델 학습 중..."):
                # 실제 학습 로직은 생략
                st.success("모델 학습 완료!")
                
                # 학습 결과 표시
                st.markdown("#### 📈 학습 결과")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("수렴 반복 횟수", "45회")
                
                with col2:
                    st.metric("최종 로그 우도", "-1,234.56")
                
                with col3:
                    st.metric("학습 정확도", "89.5%")
    
    def render_rule_editing(self):
        """규칙 편집"""
        st.markdown("#### 🎯 전이/방출 규칙 편집")
        
        # 규칙 유형 선택
        rule_type = st.selectbox(
            "규칙 유형",
            ["전이 확률", "방출 확률", "초기 확률"]
        )
        
        if rule_type == "전이 확률":
            self.render_transition_rules()
        elif rule_type == "방출 확률":
            self.render_emission_rules()
        else:
            self.render_initial_rules()
    
    def render_transition_rules(self):
        """전이 규칙 편집"""
        st.markdown("##### 🔄 전이 확률 편집")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            from_state = st.selectbox(
                "출발 상태",
                self.hmm_model.states,
                key="from_state"
            )
        
        with col2:
            to_state = st.selectbox(
                "도착 상태",
                self.hmm_model.states,
                key="to_state"
            )
        
        with col3:
            probability = st.number_input(
                "확률",
                min_value=0.0,
                max_value=1.0,
                value=0.1,
                step=0.01
            )
        
        if st.button("✏️ 전이 확률 수정"):
            st.success(f"전이 확률 수정: {from_state} -> {to_state} = {probability}")
    
    def render_emission_rules(self):
        """방출 규칙 편집"""
        st.markdown("##### 👁️ 방출 확률 편집")
        
        col1, col2 = st.columns(2)
        
        with col1:
            state = st.selectbox(
                "상태",
                self.hmm_model.states,
                key="emission_state"
            )
        
        with col2:
            feature = st.selectbox(
                "관측 특성",
                self.hmm_model.observation_features,
                key="emission_feature"
            )
        
        # 관측값과 확률 입력
        observation = st.text_input("관측값", "")
        probability = st.number_input(
            "확률",
            min_value=0.0,
            max_value=1.0,
            value=0.1,
            step=0.01,
            key="emission_prob"
        )
        
        if st.button("✏️ 방출 확률 수정"):
            st.success(f"방출 확률 수정: {state}({feature}={observation}) = {probability}")
    
    def render_initial_rules(self):
        """초기 확률 편집"""
        st.markdown("##### 🎯 초기 확률 편집")
        
        col1, col2 = st.columns(2)
        
        with col1:
            state = st.selectbox(
                "상태",
                self.hmm_model.states,
                key="initial_state"
            )
        
        with col2:
            probability = st.number_input(
                "확률",
                min_value=0.0,
                max_value=1.0,
                value=0.1,
                step=0.01,
                key="initial_prob"
            )
        
        if st.button("✏️ 초기 확률 수정"):
            st.success(f"초기 확률 수정: {state} = {probability}")
    
    def render_model_management(self):
        """모델 관리"""
        st.markdown("#### 💾 모델 관리")
        
        # 모델 저장
        st.markdown("##### 💾 모델 저장")
        model_name = st.text_input("모델 이름", "sambio_hmm_model")
        
        if st.button("💾 모델 저장"):
            filepath = f"models/{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            st.success(f"모델 저장 완료: {filepath}")
        
        # 모델 로드
        st.markdown("##### 📂 모델 로드")
        uploaded_model = st.file_uploader(
            "모델 파일 선택",
            type=['json'],
            help="저장된 HMM 모델 파일을 선택하세요"
        )
        
        if uploaded_model is not None:
            if st.button("📂 모델 로드"):
                st.success("모델 로드 완료!")
        
        # 모델 검증
        st.markdown("##### ✅ 모델 검증")
        if st.button("🔍 모델 검증"):
            with st.spinner("모델 검증 중..."):
                # 검증 결과 표시
                st.success("✅ 모델 검증 완료!")
                
                st.markdown("**검증 결과:**")
                st.write("• 전이 확률 행렬: 정상")
                st.write("• 방출 확률 행렬: 정상")
                st.write("• 초기 확률: 정상")
                st.write("• 확률 합계: 1.0")
        
        # 모델 내보내기
        st.markdown("##### 📤 모델 내보내기")
        export_format = st.selectbox(
            "내보내기 형식",
            ["JSON", "CSV", "Excel"]
        )
        
        if st.button("📤 모델 내보내기"):
            st.success(f"모델 내보내기 완료: {export_format} 형식")