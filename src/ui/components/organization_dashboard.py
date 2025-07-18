"""
조직별 대시보드 컴포넌트
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta, date

from ...analysis import OrganizationAnalyzer

class OrganizationDashboard:
    """조직별 대시보드 컴포넌트"""
    
    def __init__(self, organization_analyzer: OrganizationAnalyzer):
        self.analyzer = organization_analyzer
    
    def render(self):
        """대시보드 렌더링"""
        st.markdown("### 🏢 조직별 근무 분석")
        
        # 조직 선택 및 기간 설정
        col1, col2, col3 = st.columns(3)
        
        with col1:
            org_level = st.selectbox(
                "조직 레벨",
                ["center", "bu", "team", "group_name", "part"],
                key="org_level_select"
            )
        
        with col2:
            org_id = st.selectbox(
                "조직 선택",
                ["Production_A", "Production_B", "Quality_Team", "Maintenance"],
                key="org_id_select"
            )
        
        with col3:
            date_range = st.date_input(
                "분석 기간",
                value=(date.today() - timedelta(days=30), date.today()),
                key="org_date_range"
            )
        
        # 분석 실행
        if st.button("🔍 조직 분석 실행", type="primary"):
            self.execute_organization_analysis(org_id, org_level, date_range)
    
    def execute_organization_analysis(self, org_id: str, org_level: str, date_range: tuple):
        """조직 분석 실행"""
        with st.spinner("조직 분석 중..."):
            # 샘플 결과 표시
            st.success("분석 완료!")
            
            # 조직 KPI
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("총 인원", "45명", "3명")
            
            with col2:
                st.metric("평균 생산성", "87.3%", "2.1%")
            
            with col3:
                st.metric("가동률", "92.1%", "1.5%")
            
            with col4:
                st.metric("효율성 점수", "84.5점", "3.2점")
            
            # 차트 표시
            self.render_organization_charts()
    
    def render_organization_charts(self):
        """조직 차트 렌더링"""
        st.markdown("### 📊 조직 성과 분석")
        
        # 샘플 데이터
        employees = [f"직원{i+1}" for i in range(10)]
        productivity = np.random.uniform(70, 95, 10)
        
        # 개인별 생산성 차트
        fig = px.bar(x=employees, y=productivity, title="개인별 생산성 점수")
        st.plotly_chart(fig, use_container_width=True)
        
        # 교대별 분석
        shifts = ['주간', '야간']
        shift_productivity = [85.3, 82.1]
        
        fig2 = px.bar(x=shifts, y=shift_productivity, title="교대별 평균 생산성")
        st.plotly_chart(fig2, use_container_width=True)