"""
Streamlit 기반 메인 애플리케이션 (깔끔한 비즈니스 버전)
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

from src.database import get_database_manager
from src.analysis import IndividualAnalyzer, OrganizationAnalyzer
from src.ui.components.individual_dashboard import IndividualDashboard
from src.ui.components.organization_dashboard import OrganizationDashboard
from src.ui.components.data_upload import DataUploadComponent
from src.ui.components.model_config import ModelConfigComponent
from src.ui.components.transition_rule_editor import TransitionRuleEditor
from src.ui.components.rule_editor import RuleEditorComponent
try:
    from src.ui.components.network_analysis_dashboard_optimized import NetworkAnalysisDashboard
except ImportError:
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
            # 싱글톤 데이터베이스 매니저 사용
            self.db_manager = get_database_manager()
            
            # HMM 모델 초기화 제거 - 태그 기반 시스템 사용
            self.hmm_model = None
            
            # 분석기 초기화 (HMM 없이)
            self.individual_analyzer = IndividualAnalyzer(self.db_manager, None)
            self.organization_analyzer = OrganizationAnalyzer(self.db_manager, self.individual_analyzer)
            
            # UI 컴포넌트 초기화
            self.individual_dashboard = IndividualDashboard(self.individual_analyzer)
            self.organization_dashboard = OrganizationDashboard(self.organization_analyzer)
            self.data_upload = DataUploadComponent(self.db_manager)
            self.model_config = ModelConfigComponent(None)  # HMM 없이
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
        
        # 메인 콘텐츠 렌더링
        self.render_main_content()
    
    def render_sidebar(self):
        """사이드바 렌더링"""
        with st.sidebar:
            st.header("Navigation")
            
            # 메뉴 버튼들
            if st.button("홈", use_container_width=True):
                st.session_state.current_page = "홈"
                
            if st.button("데이터 업로드", use_container_width=True):
                st.session_state.current_page = "데이터 업로드"
                
            if st.button("개인별 분석", use_container_width=True):
                st.session_state.current_page = "개인별 분석"
                
            if st.button("조직 분석", use_container_width=True):
                st.session_state.current_page = "조직 분석"
                
            if st.button("모델 설정", use_container_width=True):
                st.session_state.current_page = "모델 설정"
                
            if st.button("활동 분류 규칙 관리", use_container_width=True):
                st.session_state.current_page = "활동 분류 규칙 관리"
                
            if st.button("네트워크 분석", use_container_width=True):
                st.session_state.current_page = "네트워크 분석"
                
            if st.button("실시간 모니터링", use_container_width=True):
                st.session_state.current_page = "실시간 모니터링"
            
            # 현재 페이지가 없으면 홈으로 설정
            if 'current_page' not in st.session_state:
                st.session_state.current_page = "홈"
            
            # 시스템 정보
            st.markdown("---")
            st.markdown("### 시스템 정보")
            
            # 데이터베이스 상태
            if self.db_manager:
                try:
                    with self.db_manager.get_session() as session:
                        st.success("데이터베이스 연결됨")
                except:
                    st.error("데이터베이스 연결 실패")
            
            # 태그 기반 시스템 상태
            st.success("태그 기반 활동 분류 시스템 활성")
            
            # 버전 정보
            st.markdown("---")
            st.markdown("**Version:** 1.0.0")
            st.markdown("**Updated:** 2025-01-18")
    
    def render_main_content(self):
        """메인 콘텐츠 렌더링"""
        current_page = st.session_state.get('current_page', '홈')
        
        if current_page == '홈':
            self.render_home_page()
        elif current_page == '개인별 분석':
            self.render_individual_analysis()
        elif current_page == '조직 분석':
            self.render_organization_analysis()
        elif current_page == '데이터 업로드':
            self.render_data_upload()
        elif current_page == '모델 설정':
            self.render_model_config()
        elif current_page == '활동 분류 규칙 관리':
            self.render_activity_rules()
        elif current_page == '네트워크 분석':
            self.render_network_analysis()
        elif current_page == '실시간 모니터링':
            self.render_real_time_monitoring()
    
    def render_home_page(self):
        """홈 페이지 렌더링"""
        # 깔끔한 비즈니스 스타일 헤더
        st.markdown("""
        <div style="background: linear-gradient(90deg, #2E86AB 0%, #4A9BC6 100%); padding: 2rem; border-radius: 10px; margin-bottom: 2rem;">
            <h1 style="color: white; margin: 0; font-size: 2.5rem; font-weight: 600;">
                Sambio Human Analytics
            </h1>
            <p style="color: rgba(255,255,255,0.9); margin: 0.5rem 0 0 0; font-size: 1.1rem;">
                Enterprise Workforce Intelligence Platform
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # 주요 KPI 카드
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="분석 완료 직원",
                value="1,234",
                delta="12"
            )
        
        with col2:
            st.metric(
                label="활성 조직",
                value="56",
                delta="3"
            )
        
        with col3:
            st.metric(
                label="평균 효율성",
                value="89.5%",
                delta="2.3%"
            )
        
        with col4:
            st.metric(
                label="시스템 가동률",
                value="99.8%",
                delta="0.1%"
            )
        
        # 시스템 개요
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            <div style="background: #f8f9fa; 
                        border-left: 3px solid #2E86AB; 
                        padding: 1rem 1.5rem; 
                        border-radius: 0 8px 8px 0; 
                        margin: 1rem 0;">
                <h4 style="margin: 0; color: #2E86AB; font-weight: 600; font-size: 1.1rem;">
                    주요 기능
                </h4>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            • 개인별 분석: 2교대 근무 패턴 분석
            • 조직별 분석: 팀/부서 단위 생산성 분석  
            • 조직 분석: 워크플로우 최적화 분석
            • 4번 식사시간: 정교한 활동 분류 처리
            """)
        
        with col2:
            st.markdown("""
            <div style="background: #f8f9fa; 
                        border-left: 3px solid #2E86AB; 
                        padding: 1rem 1.5rem; 
                        border-radius: 0 8px 8px 0; 
                        margin: 1rem 0;">
                <h4 style="margin: 0; color: #2E86AB; font-weight: 600; font-size: 1.1rem;">
                    분석 범위
                </h4>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            • 태그 데이터: 위치 기반 활동 추적
            • 근무시간 분석: 실제 작업시간 신뢰도 측정
            • 조직 효율성: 부서별 성과 지표 
            • 교대 근무: 주간/야간 교대 최적화
            """)
        
        # 최근 활동
        st.markdown("---")
        st.markdown("""
        <div style="background: #f8f9fa; 
                    border-left: 3px solid #6c757d; 
                    padding: 0.8rem 1.2rem; 
                    border-radius: 0 6px 6px 0; 
                    margin: 1rem 0 0.5rem 0;">
            <h4 style="margin: 0; color: #495057; font-weight: 600; font-size: 1.1rem;">
                최근 활동
            </h4>
        </div>
        """, unsafe_allow_html=True)
        
        recent_activities = [
            {"시간": "2025-01-18 14:30", "활동": "개인별 분석 완료", "대상": "직원 ID: E001234", "결과": "성공"},
            {"시간": "2025-01-18 14:15", "활동": "데이터 업로드", "대상": "tag_data_24.6.xlsx", "결과": "성공"},
            {"시간": "2025-01-18 13:45", "활동": "태그 분류 처리", "대상": "100개 태그", "결과": "성공"},
            {"시간": "2025-01-18 13:30", "활동": "조직 분석", "대상": "Production Team", "결과": "성공"}
        ]
        
        df_activities = pd.DataFrame(recent_activities)
        st.dataframe(df_activities, use_container_width=True)
    
    def render_individual_analysis(self):
        """개인 분석 페이지 렌더링"""
        # 세련된 비즈니스 스타일 헤더
        st.markdown("""
        <div style="background: linear-gradient(90deg, #2E86AB 0%, #4A9BC6 100%); padding: 1.5rem; border-radius: 8px; margin-bottom: 1.5rem;">
            <h2 style="color: white; margin: 0; font-size: 1.8rem; font-weight: 600;">
                Individual Analysis
            </h2>
            <p style="color: rgba(255,255,255,0.9); margin: 0.3rem 0 0 0; font-size: 0.95rem;">
                개인별 근무 패턴 및 생산성 분석
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        if self.individual_dashboard:
            self.individual_dashboard.render()
        else:
            st.error("개인 분석 컴포넌트가 초기화되지 않았습니다.")
    
    def render_organization_analysis(self):
        """조직 분석 페이지 렌더링"""
        # 세련된 비즈니스 스타일 헤더
        st.markdown("""
        <div style="background: linear-gradient(90deg, #2E86AB 0%, #4A9BC6 100%); padding: 1.5rem; border-radius: 8px; margin-bottom: 1.5rem;">
            <h2 style="color: white; margin: 0; font-size: 1.8rem; font-weight: 600;">
                Organization Analysis
            </h2>
            <p style="color: rgba(255,255,255,0.9); margin: 0.3rem 0 0 0; font-size: 0.95rem;">
                조직별 생산성 및 효율성 분석
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        if self.organization_dashboard:
            self.organization_dashboard.render()
        else:
            st.error("조직 분석 컴포넌트가 초기화되지 않았습니다.")
    
    def render_data_upload(self):
        """데이터 업로드 페이지 렌더링"""
        # 세련된 비즈니스 스타일 헤더
        st.markdown("""
        <div style="background: linear-gradient(90deg, #2E86AB 0%, #4A9BC6 100%); padding: 1.5rem; border-radius: 8px; margin-bottom: 1.5rem;">
            <h2 style="color: white; margin: 0; font-size: 1.8rem; font-weight: 600;">
                Data Upload
            </h2>
            <p style="color: rgba(255,255,255,0.9); margin: 0.3rem 0 0 0; font-size: 0.95rem;">
                데이터 업로드 및 관리
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        if self.data_upload:
            self.data_upload.render()
        else:
            st.error("데이터 업로드 컴포넌트가 초기화되지 않았습니다.")
    
    def render_model_config(self):
        """모델 설정 페이지 렌더링"""
        # 세련된 비즈니스 스타일 헤더
        st.markdown("""
        <div style="background: linear-gradient(90deg, #2E86AB 0%, #4A9BC6 100%); padding: 1.5rem; border-radius: 8px; margin-bottom: 1.5rem;">
            <h2 style="color: white; margin: 0; font-size: 1.8rem; font-weight: 600;">
                Model Configuration
            </h2>
            <p style="color: rgba(255,255,255,0.9); margin: 0.3rem 0 0 0; font-size: 0.95rem;">
                분석 모델 설정 및 관리
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        if self.model_config:
            self.model_config.render()
        else:
            st.error("모델 설정 컴포넌트가 초기화되지 않았습니다.")
    
    def render_activity_rules(self):
        """활동 분류 규칙 관리 페이지 렌더링"""
        rule_editor = RuleEditorComponent()
        rule_editor.render()
    
    def render_network_analysis(self):
        """네트워크 분석 페이지 렌더링"""
        # 세련된 비즈니스 스타일 헤더
        st.markdown("""
        <div style="background: linear-gradient(90deg, #2E86AB 0%, #4A9BC6 100%); padding: 1.5rem; border-radius: 8px; margin-bottom: 1.5rem;">
            <h2 style="color: white; margin: 0; font-size: 1.8rem; font-weight: 600;">
                Network Analysis
            </h2>
            <p style="color: rgba(255,255,255,0.9); margin: 0.3rem 0 0 0; font-size: 0.95rem;">
                조직 네트워크 및 상호작용 분석
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        if self.network_analysis_dashboard:
            self.network_analysis_dashboard.render()
        else:
            st.error("네트워크 분석 대시보드가 초기화되지 않았습니다.")
    
    def render_real_time_monitoring(self):
        """실시간 모니터링 페이지 렌더링"""
        # 세련된 비즈니스 스타일 헤더
        st.markdown("""
        <div style="background: linear-gradient(90deg, #2E86AB 0%, #4A9BC6 100%); padding: 1.5rem; border-radius: 8px; margin-bottom: 1.5rem;">
            <h2 style="color: white; margin: 0; font-size: 1.8rem; font-weight: 600;">
                Real-time Monitoring
            </h2>
            <p style="color: rgba(255,255,255,0.9); margin: 0.3rem 0 0 0; font-size: 0.95rem;">
                실시간 생산성 모니터링
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # 실시간 데이터 시뮬레이션
        import time
        import random
        
        # 자동 새로고침 설정
        auto_refresh = st.checkbox("자동 새로고침 (5초)", value=True)
        
        if auto_refresh:
            time.sleep(5)
            st.rerun()
        
        # 실시간 메트릭
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            current_efficiency = random.uniform(85, 95)
            st.metric(
                "현재 전체 효율성",
                f"{current_efficiency:.1f}%",
                f"{random.uniform(-2, 2):.1f}%"
            )
        
        with col2:
            active_workers = random.randint(1200, 1250)
            st.metric(
                "활성 근무자",
                active_workers,
                random.randint(-5, 5)
            )
        
        with col3:
            alert_count = random.randint(0, 3)
            st.metric(
                "알림 개수",
                alert_count,
                random.randint(-1, 1)
            )
        
        with col4:
            system_health = random.uniform(95, 100)
            st.metric(
                "시스템 상태",
                f"{system_health:.1f}%",
                f"{random.uniform(-0.5, 0.5):.1f}%"
            )
        
        # 실시간 차트
        st.markdown("""
        <div style="background: #f8f9fa; 
                    border-left: 3px solid #2E86AB; 
                    padding: 0.8rem 1.2rem; 
                    border-radius: 0 6px 6px 0; 
                    margin: 1rem 0 0.5rem 0;">
            <h4 style="margin: 0; color: #2E86AB; font-weight: 600; font-size: 1.1rem;">
                Real-time Productivity Monitoring
            </h4>
        </div>
        """, unsafe_allow_html=True)
        
        # 샘플 시계열 데이터
        hours = list(range(24))
        productivity = [random.uniform(80, 95) for _ in hours]
        
        fig = px.line(
            x=hours, 
            y=productivity,
            title="시간대별 생산성 추이",
            labels={'x': '시간', 'y': '생산성 (%)'}
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # 알림 패널
        st.markdown("""
        <div style="background: #f8f9fa; 
                    border-left: 3px solid #6c757d; 
                    padding: 0.8rem 1.2rem; 
                    border-radius: 0 6px 6px 0; 
                    margin: 1rem 0 0.5rem 0;">
            <h4 style="margin: 0; color: #495057; font-weight: 600; font-size: 1.1rem;">
                Real-time Alerts
            </h4>
        </div>
        """, unsafe_allow_html=True)
        
        alerts = [
            {"time": "14:30", "type": "warning", "message": "Team B 효율성 임계값 이하"},
            {"time": "14:25", "type": "info", "message": "데이터 동기화 완료"},
            {"time": "14:20", "type": "success", "message": "Team A 목표 달성"}
        ]
        
        for alert in alerts:
            if alert["type"] == "warning":
                st.warning(f"[{alert['time']}] {alert['message']}")
            elif alert["type"] == "info":
                st.info(f"[{alert['time']}] {alert['message']}")
            elif alert["type"] == "success":
                st.success(f"[{alert['time']}] {alert['message']}")


def main():
    """메인 함수"""
    app = SambioHumanApp()
    app.run()


if __name__ == "__main__":
    main()