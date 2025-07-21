"""
간단한 Streamlit 애플리케이션 (안정성 테스트용)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """메인 애플리케이션"""
    # 페이지 설정
    st.set_page_config(
        page_title="Sambio Human Analytics",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # 메인 타이틀
    st.title("🏭 Sambio Human Analytics")
    st.markdown("### 2교대 근무 시스템 실근무시간 분석 대시보드")
    
    # 사이드바
    with st.sidebar:
        st.header("📋 Navigation")
        
        page = st.selectbox(
            "페이지 선택",
            [
                "🏠 홈",
                "👤 개인 분석",
                "🏢 조직 분석",
                "📊 비교 분석",
                "📤 데이터 업로드",
                "⚙️ 모델 설정"
            ]
        )
        
        st.markdown("---")
        st.markdown("### 📊 시스템 정보")
        st.success("🟢 애플리케이션 실행중")
        st.success("🟢 데이터베이스 연결됨")
        st.success("🟢 HMM 모델 로드됨")
        
        st.markdown("---")
        st.markdown("**Version:** 1.0.0")
        st.markdown("**Status:** 🟢 정상 운영")
    
    # 메인 콘텐츠
    if page == "🏠 홈":
        render_home()
    elif page == "👤 개인 분석":
        render_individual_analysis()
    elif page == "🏢 조직 분석":
        render_organization_analysis()
    elif page == "📊 비교 분석":
        render_comparison_analysis()
    elif page == "📤 데이터 업로드":
        render_data_upload()
    elif page == "⚙️ 모델 설정":
        render_model_config()

def render_home():
    """홈 페이지"""
    st.markdown("## 🏠 홈 대시보드")
    
    # 주요 KPI 카드
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📊 분석 완료 직원",
            value="1,234",
            delta="12"
        )
    
    with col2:
        st.metric(
            label="🏭 활성 조직",
            value="56",
            delta="3"
        )
    
    with col3:
        st.metric(
            label="⚡ 평균 효율성",
            value="89.5%",
            delta="2.3%"
        )
    
    with col4:
        st.metric(
            label="🎯 데이터 품질",
            value="94.2%",
            delta="1.8%"
        )
    
    # 시스템 개요
    st.markdown("---")
    st.markdown("## 📋 시스템 개요")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 🎯 주요 기능
        - **개인별 분석**: 2교대 근무 패턴 분석
        - **조직별 분석**: 팀/부서 단위 생산성 분석
        - **실시간 모니터링**: 태그 데이터 실시간 처리
        - **HMM 모델**: 활동 상태 자동 분류
        - **4번 식사시간**: 조식/중식/석식/야식 추적
        """)
    
    with col2:
        st.markdown("""
        ### 📊 분석 범위
        - **태그 데이터**: 위치 기반 활동 추적
        - **ABC 활동**: 실제 작업 분류 데이터
        - **Claim 데이터**: 근무시간 신고 데이터
        - **근태 데이터**: 공식 출퇴근 기록
        - **교대 근무**: 주간/야간 교대 분석
        """)
    
    # 샘플 차트
    st.markdown("---")
    st.markdown("## 📈 실시간 현황")
    
    # 샘플 데이터 생성
    dates = pd.date_range(start=date.today()-timedelta(days=30), end=date.today(), freq='D')
    sample_data = pd.DataFrame({
        'date': dates,
        'efficiency': np.random.uniform(80, 95, len(dates)),
        'work_hours': np.random.uniform(7.5, 8.5, len(dates)),
        'employees': np.random.randint(1200, 1300, len(dates))
    })
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig1 = px.line(sample_data, x='date', y='efficiency', title='월간 효율성 트렌드')
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        fig2 = px.bar(sample_data.tail(7), x='date', y='work_hours', title='주간 근무시간')
        st.plotly_chart(fig2, use_container_width=True)

def render_individual_analysis():
    """개인 분석 페이지"""
    st.markdown("## 👤 개인별 분석")
    
    # 직원 선택
    col1, col2, col3 = st.columns(3)
    
    with col1:
        employee_id = st.selectbox(
            "직원 선택",
            ["E001234", "E001235", "E001236", "E001237", "E001238"]
        )
    
    with col2:
        date_range = st.date_input(
            "분석 기간",
            value=(date.today() - timedelta(days=7), date.today())
        )
    
    with col3:
        analysis_type = st.selectbox(
            "분석 유형",
            ["근무시간 분석", "교대 근무 분석", "식사시간 분석", "효율성 분석"]
        )
    
    # 분석 실행
    if st.button("🔍 분석 실행", type="primary"):
        with st.spinner("분석 중..."):
            # 샘플 결과 표시
            st.success("분석 완료!")
            
            # 개인 KPI
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("실제 근무시간", "8.5h", "0.5h")
            
            with col2:
                st.metric("효율성", "89.5%", "2.3%")
            
            with col3:
                st.metric("생산성 점수", "87.2점", "1.8점")
            
            with col4:
                st.metric("데이터 품질", "94%", "1.5%")
            
            # 타임라인 차트
            st.markdown("### 📅 일일 활동 타임라인")
            
            # 샘플 타임라인 데이터
            timeline_data = pd.DataFrame({
                'time': pd.date_range(start='08:00', end='17:00', freq='30min'),
                'activity': np.random.choice(['근무', '회의', '이동', '휴식'], 19),
                'confidence': np.random.uniform(70, 100, 19)
            })
            
            fig = px.scatter(timeline_data, x='time', y='activity', 
                           size='confidence', color='activity',
                           title='일일 활동 패턴')
            st.plotly_chart(fig, use_container_width=True)

def render_organization_analysis():
    """조직 분석 페이지"""
    st.markdown("## 🏢 조직별 분석")
    
    # 조직 선택
    col1, col2 = st.columns(2)
    
    with col1:
        org_type = st.selectbox(
            "조직 유형",
            ["팀", "부서", "센터", "전체"]
        )
    
    with col2:
        org_name = st.selectbox(
            "조직 선택",
            ["Production Team A", "Production Team B", "Quality Team", "Maintenance Team"]
        )
    
    # 분석 실행
    if st.button("🔍 조직 분석 실행", type="primary"):
        with st.spinner("조직 분석 중..."):
            st.success("조직 분석 완료!")
            
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
            
            # 조직 분석 차트
            st.markdown("### 📊 조직 성과 분석")
            
            # 샘플 데이터
            employees = [f"직원{i+1}" for i in range(10)]
            productivity = np.random.uniform(70, 95, 10)
            
            fig = px.bar(x=employees, y=productivity, title="개인별 생산성 점수")
            st.plotly_chart(fig, use_container_width=True)

def render_comparison_analysis():
    """비교 분석 페이지"""
    st.markdown("## 📊 비교 분석")
    
    comparison_type = st.selectbox(
        "비교 유형",
        ["개인간 비교", "조직간 비교", "시기별 비교", "교대별 비교"]
    )
    
    st.markdown(f"### {comparison_type} 분석")
    
    # 샘플 비교 차트
    if comparison_type == "교대별 비교":
        shifts = ['주간', '야간']
        productivity = [85.3, 82.1]
        
        fig = px.bar(x=shifts, y=productivity, 
                    title="교대별 평균 생산성",
                    color=shifts,
                    color_discrete_map={'주간': '#87CEEB', '야간': '#4169E1'})
        st.plotly_chart(fig, use_container_width=True)

def render_data_upload():
    """데이터 업로드 페이지"""
    st.markdown("## 📤 데이터 업로드")
    
    upload_type = st.selectbox(
        "업로드 데이터 유형",
        [
            "태깅 데이터 (tag_data)",
            "ABC 활동 데이터 (abc_data)",
            "근무시간 Claim 데이터 (claim_data)",
            "근태 사용 데이터 (attendance_data)"
        ]
    )
    
    uploaded_file = st.file_uploader(
        "엑셀 파일 선택",
        type=['xlsx', 'xls'],
        help="지원 형식: .xlsx, .xls"
    )
    
    if uploaded_file is not None:
        st.success(f"파일 업로드 완료: {uploaded_file.name}")
        
        if st.button("🚀 데이터 처리 시작", type="primary"):
            with st.spinner("데이터 처리 중..."):
                progress = st.progress(0)
                for i in range(100):
                    progress.progress(i + 1)
                
                st.success("✅ 데이터 처리 완료!")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("처리된 레코드", "1,234개")
                with col2:
                    st.metric("처리 시간", "2.3초")
                with col3:
                    st.metric("성공률", "100%")

def render_model_config():
    """모델 설정 페이지"""
    st.markdown("## ⚙️ 모델 설정")
    
    tab1, tab2, tab3 = st.tabs(["📊 모델 상태", "🔧 파라미터", "💾 관리"])
    
    with tab1:
        st.markdown("### 📊 HMM 모델 상태")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.info("**모델 이름:** sambio_work_activity_hmm")
            st.info("**상태 수:** 17개")
            st.info("**관측 특성 수:** 10개")
        
        with col2:
            st.info("**초기화 상태:** 🟢 완료")
            st.info("**마지막 업데이트:** 2025-01-18")
            st.info("**모델 정확도:** 89.5%")
    
    with tab2:
        st.markdown("### 🔧 파라미터 설정")
        
        init_method = st.selectbox(
            "초기화 방법",
            ["uniform", "random", "domain_knowledge"]
        )
        
        if st.button("🔄 모델 재초기화"):
            with st.spinner("모델 초기화 중..."):
                st.success("모델 초기화 완료!")
    
    with tab3:
        st.markdown("### 💾 모델 관리")
        
        if st.button("💾 모델 저장"):
            st.success("모델 저장 완료!")
        
        if st.button("🔍 모델 검증"):
            st.success("✅ 모델 검증 완료!")

if __name__ == "__main__":
    main()