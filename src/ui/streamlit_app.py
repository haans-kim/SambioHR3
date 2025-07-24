"""
Streamlit 기반 메인 애플리케이션
2교대 근무 시스템 분석 대시보드
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta, date
import logging
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.database import DatabaseManager
from src.hmm import HMMModel
from src.analysis import IndividualAnalyzer, OrganizationAnalyzer
from src.ui.components.individual_dashboard import IndividualDashboard
from src.ui.components.organization_dashboard import OrganizationDashboard
from src.ui.components.data_upload import DataUploadComponent
from src.ui.components.model_config import ModelConfigComponent
from src.ui.components.transition_rule_editor import TransitionRuleEditor
from src.ui.components.network_analysis_dashboard import NetworkAnalysisDashboard

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SambioHumanApp:
    """메인 애플리케이션 클래스"""
    
    def __init__(self):
        self.db_manager = None
        self.hmm_model = None
        self.individual_analyzer = None
        self.organization_analyzer = None
        self.initialize_components()
    
    def initialize_components(self):
        """컴포넌트 초기화"""
        try:
            # 데이터베이스 매니저 초기화
            self.db_manager = DatabaseManager()
            
            # HMM 모델 초기화
            self.hmm_model = HMMModel("sambio_work_activity_hmm")
            self.hmm_model.initialize_parameters("domain_knowledge")
            
            # 분석기 초기화
            self.individual_analyzer = IndividualAnalyzer(self.db_manager, self.hmm_model)
            self.organization_analyzer = OrganizationAnalyzer(self.db_manager, self.individual_analyzer)
            
            # UI 컴포넌트 초기화
            self.individual_dashboard = IndividualDashboard(self.individual_analyzer)
            self.organization_dashboard = OrganizationDashboard(self.organization_analyzer)
            self.data_upload = DataUploadComponent(self.db_manager)
            self.model_config = ModelConfigComponent(self.hmm_model)
            self.transition_rule_editor = TransitionRuleEditor()
            self.network_analysis_dashboard = NetworkAnalysisDashboard(self.db_manager)
            
            logger.info("애플리케이션 컴포넌트 초기화 완료")
            
        except Exception as e:
            logger.error(f"컴포넌트 초기화 실패: {e}")
            st.error(f"애플리케이션 초기화 중 오류 발생: {e}")
    
    def run(self):
        """애플리케이션 실행"""
        # 페이지 설정
        st.set_page_config(
            page_title="Sambio Human Analytics",
            page_icon="📊",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # 사이드바 네비게이션
        self.render_sidebar()
        
        # 메인 콘텐츠 렌더링 (타이틀은 각 페이지에서 처리)
        self.render_main_content()
    
    def render_sidebar(self):
        """사이드바 렌더링"""
        with st.sidebar:
            st.header("📋 Navigation")
            
            # 메뉴 버튼들을 직접 나열 (홈을 맨 위로)
            if st.button("🏠 홈", use_container_width=True):
                st.session_state.current_page = "🏠 홈"
                
            if st.button("📤 데이터 업로드", use_container_width=True):
                st.session_state.current_page = "📤 데이터 업로드"
                
            if st.button("👤 개인 분석", use_container_width=True):
                st.session_state.current_page = "👤 개인 분석"
                
            if st.button("🏢 조직 분석", use_container_width=True):
                st.session_state.current_page = "🏢 조직 분석"
                
            if st.button("📊 비교 분석", use_container_width=True):
                st.session_state.current_page = "📊 비교 분석"
                
            if st.button("⚙️ 모델 설정", use_container_width=True):
                st.session_state.current_page = "⚙️ 모델 설정"
                
            if st.button("🔄 전이 룰 관리", use_container_width=True):
                st.session_state.current_page = "🔄 전이 룰 관리"
                
            if st.button("🌐 네트워크 분석", use_container_width=True):
                st.session_state.current_page = "🌐 네트워크 분석"
                
            if st.button("📈 실시간 모니터링", use_container_width=True):
                st.session_state.current_page = "📈 실시간 모니터링"
            
            # 현재 페이지가 없으면 홈으로 설정
            if 'current_page' not in st.session_state:
                st.session_state.current_page = "🏠 홈"
            
            # 시스템 정보
            st.markdown("---")
            st.markdown("### 📊 시스템 정보")
            
            # 데이터베이스 상태
            if self.db_manager:
                try:
                    with self.db_manager.get_session() as session:
                        st.success("🟢 데이터베이스 연결됨")
                except:
                    st.error("🔴 데이터베이스 연결 실패")
            
            # HMM 모델 상태
            if self.hmm_model:
                if self.hmm_model.transition_matrix is not None:
                    st.success("🟢 HMM 모델 로드됨")
                else:
                    st.warning("🟡 HMM 모델 미초기화")
            
            # 버전 정보
            st.markdown("---")
            st.markdown("**Version:** 1.0.0")
            st.markdown("**Updated:** 2025-01-18")
    
    def render_main_content(self):
        """메인 콘텐츠 렌더링"""
        current_page = st.session_state.get('current_page', '🏠 홈')
        
        if current_page == '🏠 홈':
            self.render_home_page()
        elif current_page == '👤 개인 분석':
            self.render_individual_analysis()
        elif current_page == '🏢 조직 분석':
            self.render_organization_analysis()
        elif current_page == '📊 비교 분석':
            self.render_comparison_analysis()
        elif current_page == '📤 데이터 업로드':
            self.render_data_upload()
        elif current_page == '⚙️ 모델 설정':
            self.render_model_config()
        elif current_page == '🔄 전이 룰 관리':
            self.render_transition_rules()
        elif current_page == '🌐 네트워크 분석':
            self.render_network_analysis()
        elif current_page == '📈 실시간 모니터링':
            self.render_real_time_monitoring()
    
    def render_home_page(self):
        """홈 페이지 렌더링"""
        st.title("🏭 Sambio Human Analytics")
        st.markdown("---")
        
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
        
        # 최근 활동 로그
        st.markdown("---")
        st.markdown("## 📝 최근 활동")
        
        # 샘플 활동 로그
        recent_activities = [
            {"시간": "2025-01-18 14:30", "활동": "개인 분석 완료", "대상": "직원 ID: E001234", "결과": "성공"},
            {"시간": "2025-01-18 14:15", "활동": "데이터 업로드", "대상": "tag_data_24.6.xlsx", "결과": "성공"},
            {"시간": "2025-01-18 13:45", "활동": "HMM 모델 학습", "대상": "100개 시퀀스", "결과": "성공"},
            {"시간": "2025-01-18 13:30", "활동": "조직 분석", "대상": "Production Team", "결과": "성공"},
        ]
        
        df_activities = pd.DataFrame(recent_activities)
        st.dataframe(df_activities, use_container_width=True)
    
    def render_individual_analysis(self):
        """개인 분석 페이지 렌더링"""
        st.markdown("## 👤 개인별 분석")
        
        if self.individual_dashboard:
            self.individual_dashboard.render()
        else:
            st.error("개인 분석 컴포넌트가 초기화되지 않았습니다.")
    
    def render_organization_analysis(self):
        """조직 분석 페이지 렌더링"""
        st.markdown("## 🏢 조직별 분석")
        
        if self.organization_dashboard:
            self.organization_dashboard.render()
        else:
            st.error("조직 분석 컴포넌트가 초기화되지 않았습니다.")
    
    def render_comparison_analysis(self):
        """비교 분석 페이지 렌더링"""
        st.markdown("## 📊 비교 분석")
        
        # 비교 유형 선택
        comparison_type = st.selectbox(
            "비교 유형 선택",
            ["개인간 비교", "조직간 비교", "시기별 비교", "교대별 비교"]
        )
        
        if comparison_type == "개인간 비교":
            self.render_individual_comparison()
        elif comparison_type == "조직간 비교":
            self.render_organization_comparison()
        elif comparison_type == "시기별 비교":
            self.render_time_comparison()
        elif comparison_type == "교대별 비교":
            self.render_shift_comparison()
    
    def render_individual_comparison(self):
        """개인간 비교 분석"""
        st.markdown("### 👥 개인간 비교")
        
        # 직원 선택
        col1, col2 = st.columns(2)
        
        with col1:
            employee_ids = st.multiselect(
                "비교할 직원 선택",
                ["E001234", "E001235", "E001236", "E001237"],
                default=["E001234", "E001235"]
            )
        
        with col2:
            date_range = st.date_input(
                "분석 기간",
                value=(date.today() - timedelta(days=30), date.today()),
                key="individual_comparison_date"
            )
        
        if employee_ids and len(employee_ids) >= 2:
            # 비교 차트 생성
            self.create_individual_comparison_charts(employee_ids, date_range)
    
    def render_organization_comparison(self):
        """조직간 비교 분석"""
        st.markdown("### 🏢 조직간 비교")
        
        # 조직 선택
        col1, col2 = st.columns(2)
        
        with col1:
            organizations = st.multiselect(
                "비교할 조직 선택",
                ["Production Team A", "Production Team B", "Quality Team", "Maintenance Team"],
                default=["Production Team A", "Production Team B"]
            )
        
        with col2:
            date_range = st.date_input(
                "분석 기간",
                value=(date.today() - timedelta(days=30), date.today()),
                key="org_comparison_date"
            )
        
        if organizations and len(organizations) >= 2:
            # 비교 차트 생성
            self.create_organization_comparison_charts(organizations, date_range)
    
    def render_time_comparison(self):
        """시기별 비교 분석"""
        st.markdown("### 📅 시기별 비교")
        
        # 기간 선택
        col1, col2 = st.columns(2)
        
        with col1:
            period_type = st.selectbox(
                "비교 단위",
                ["주간", "월간", "분기"]
            )
        
        with col2:
            target_selection = st.selectbox(
                "분석 대상",
                ["전체 조직", "특정 팀", "특정 개인"]
            )
        
        # 시기별 트렌드 차트
        self.create_time_trend_charts(period_type, target_selection)
    
    def render_shift_comparison(self):
        """교대별 비교 분석"""
        st.markdown("### 🌅🌙 교대별 비교")
        
        # 교대 비교 설정
        col1, col2 = st.columns(2)
        
        with col1:
            shift_metrics = st.multiselect(
                "비교 지표",
                ["생산성", "효율성", "근무시간", "식사시간", "활동 분포"],
                default=["생산성", "효율성"]
            )
        
        with col2:
            date_range = st.date_input(
                "분석 기간",
                value=(date.today() - timedelta(days=30), date.today()),
                key="shift_comparison_date"
            )
        
        # 교대별 비교 차트
        self.create_shift_comparison_charts(shift_metrics, date_range)
    
    def render_data_upload(self):
        """데이터 업로드 페이지 렌더링"""
        if self.data_upload:
            self.data_upload.render()
        else:
            st.error("데이터 업로드 컴포넌트가 초기화되지 않았습니다.")
    
    def render_model_config(self):
        """모델 설정 페이지 렌더링"""
        st.markdown("## ⚙️ 모델 설정")
        
        if self.model_config:
            self.model_config.render()
        else:
            st.error("모델 설정 컴포넌트가 초기화되지 않았습니다.")
    
    def render_transition_rules(self):
        """전이 룰 관리 페이지 렌더링"""
        if self.transition_rule_editor:
            self.transition_rule_editor.render()
        else:
            st.error("전이 룰 에디터 컴포넌트가 초기화되지 않았습니다.")
    
    def render_network_analysis(self):
        """네트워크 분석 페이지 렌더링"""
        st.markdown("## 🌐 네트워크 분석")
        
        if self.network_analysis_dashboard:
            self.network_analysis_dashboard.render()
        else:
            st.error("네트워크 분석 컴포넌트가 초기화되지 않았습니다.")
    
    def render_real_time_monitoring(self):
        """실시간 모니터링 페이지 렌더링"""
        st.markdown("## 📈 실시간 모니터링")
        
        # 실시간 데이터 표시
        st.markdown("### 📊 실시간 시스템 상태")
        
        # 메트릭 표시
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("활성 태그", "1,234", "12")
        
        with col2:
            st.metric("처리 중인 데이터", "56", "-3")
        
        with col3:
            st.metric("시스템 부하", "23%", "5%")
        
        # 실시간 차트
        st.markdown("### 📈 실시간 활동 모니터링")
        
        # 샘플 실시간 데이터
        timestamps = pd.date_range(start=datetime.now()-timedelta(hours=1), 
                                 end=datetime.now(), freq='1min')
        activity_data = pd.DataFrame({
            'timestamp': timestamps,
            'activity_count': np.random.randint(10, 100, len(timestamps)),
            'efficiency': np.random.uniform(0.7, 0.95, len(timestamps))
        })
        
        # 활동 수 차트
        fig1 = px.line(activity_data, x='timestamp', y='activity_count', 
                      title='실시간 활동 수')
        st.plotly_chart(fig1, use_container_width=True)
        
        # 효율성 차트
        fig2 = px.line(activity_data, x='timestamp', y='efficiency', 
                      title='실시간 효율성')
        st.plotly_chart(fig2, use_container_width=True)
    
    def create_individual_comparison_charts(self, employee_ids, date_range):
        """개인간 비교 차트 생성"""
        # 샘플 데이터 생성
        comparison_data = []
        for emp_id in employee_ids:
            comparison_data.append({
                'employee_id': emp_id,
                'productivity': np.random.uniform(60, 95),
                'efficiency': np.random.uniform(70, 90),
                'work_hours': np.random.uniform(7, 9),
                'focus_time': np.random.uniform(60, 85)
            })
        
        df_comparison = pd.DataFrame(comparison_data)
        
        # 생산성 비교
        fig1 = px.bar(df_comparison, x='employee_id', y='productivity', 
                     title='개인별 생산성 비교')
        st.plotly_chart(fig1, use_container_width=True)
        
        # 효율성 비교
        fig2 = px.bar(df_comparison, x='employee_id', y='efficiency', 
                     title='개인별 효율성 비교')
        st.plotly_chart(fig2, use_container_width=True)
    
    def create_organization_comparison_charts(self, organizations, date_range):
        """조직간 비교 차트 생성"""
        # 샘플 데이터 생성
        org_data = []
        for org in organizations:
            org_data.append({
                'organization': org,
                'avg_productivity': np.random.uniform(70, 90),
                'workforce_utilization': np.random.uniform(85, 95),
                'total_work_hours': np.random.uniform(200, 400),
                'efficiency_score': np.random.uniform(75, 90)
            })
        
        df_org = pd.DataFrame(org_data)
        
        # 조직별 생산성 비교
        fig1 = px.bar(df_org, x='organization', y='avg_productivity', 
                     title='조직별 평균 생산성 비교')
        st.plotly_chart(fig1, use_container_width=True)
        
        # 인력 가동률 비교
        fig2 = px.bar(df_org, x='organization', y='workforce_utilization', 
                     title='조직별 인력 가동률 비교')
        st.plotly_chart(fig2, use_container_width=True)
    
    def create_time_trend_charts(self, period_type, target_selection):
        """시기별 트렌드 차트 생성"""
        # 샘플 시계열 데이터
        if period_type == "주간":
            dates = pd.date_range(start=date.today()-timedelta(weeks=12), 
                                 end=date.today(), freq='W')
        elif period_type == "월간":
            dates = pd.date_range(start=date.today()-timedelta(days=365), 
                                 end=date.today(), freq='M')
        else:  # 분기
            dates = pd.date_range(start=date.today()-timedelta(days=730), 
                                 end=date.today(), freq='Q')
        
        trend_data = pd.DataFrame({
            'date': dates,
            'productivity': np.random.uniform(70, 90, len(dates)),
            'efficiency': np.random.uniform(75, 85, len(dates)),
            'work_hours': np.random.uniform(7.5, 8.5, len(dates))
        })
        
        # 트렌드 차트
        fig = px.line(trend_data, x='date', y=['productivity', 'efficiency'], 
                     title=f'{period_type} 트렌드 분석')
        st.plotly_chart(fig, use_container_width=True)
    
    def create_shift_comparison_charts(self, shift_metrics, date_range):
        """교대별 비교 차트 생성"""
        # 샘플 교대 데이터
        shift_data = pd.DataFrame({
            'shift': ['주간', '야간'],
            'productivity': [np.random.uniform(80, 90), np.random.uniform(70, 85)],
            'efficiency': [np.random.uniform(85, 95), np.random.uniform(75, 85)],
            'work_hours': [np.random.uniform(8, 9), np.random.uniform(7.5, 8.5)],
            'meal_time': [np.random.uniform(45, 60), np.random.uniform(50, 70)]
        })
        
        # 교대별 비교 차트
        for metric in shift_metrics:
            if metric == "생산성":
                fig = px.bar(shift_data, x='shift', y='productivity', 
                           title='교대별 생산성 비교')
                st.plotly_chart(fig, use_container_width=True)
            elif metric == "효율성":
                fig = px.bar(shift_data, x='shift', y='efficiency', 
                           title='교대별 효율성 비교')
                st.plotly_chart(fig, use_container_width=True)


def main():
    """메인 함수"""
    app = SambioHumanApp()
    app.run()


if __name__ == "__main__":
    main()