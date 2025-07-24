"""
네트워크 분석 대시보드 컴포넌트 - 수동 실행 버전
원본 네트워크 분석 대시보드에 개선된 UI 적용
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta, date
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import matplotlib.pyplot as plt
import networkx as nx
import sqlite3

from ...analysis.network_analyzer import NetworkAnalyzer
from ...database import DatabaseManager

class NetworkAnalysisDashboard:
    """네트워크 분석 대시보드 컴포넌트 - 수동 실행 UI"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        self.network_analyzer = NetworkAnalyzer("data/sambio_human.db")
        self._date_range_cache = None
    
    def get_data_date_range(self):
        """데이터가 존재하는 날짜 범위 반환"""
        if self._date_range_cache is not None:
            return self._date_range_cache
            
        try:
            from ...data_processing import PickleManager
            pickle_manager = PickleManager()
            tag_data = pickle_manager.load_dataframe(name='tag_data')
            
            if tag_data is None or tag_data.empty:
                return None, None, pd.Series()
            
            # 날짜 변환 및 범위 계산
            tag_data['ENTE_DT'] = pd.to_numeric(tag_data['ENTE_DT'], errors='coerce')
            tag_data['time_str'] = tag_data['출입시각'].astype(str).str.zfill(6)
            tag_data['timestamp'] = pd.to_datetime(
                tag_data['ENTE_DT'].astype(str) + ' ' + tag_data['time_str'],
                format='%Y%m%d %H%M%S',
                errors='coerce'
            )
            
            dates = tag_data['timestamp'].dt.date
            min_date = dates.min()
            max_date = dates.max()
            date_counts = dates.value_counts().sort_index()
            
            self._date_range_cache = (min_date, max_date, date_counts)
            return min_date, max_date, date_counts
            
        except Exception as e:
            self.logger.error(f"날짜 범위 계산 중 오류: {e}")
            return None, None, pd.Series()
    
    def render(self):
        """네트워크 분석 대시보드 렌더링"""
        st.markdown("### 🌐 조직 네트워크 분석")
        
        # 데이터 날짜 범위 확인
        min_date, max_date, date_counts = self.get_data_date_range()
        
        if min_date is None or max_date is None:
            st.error("데이터의 날짜 범위를 확인할 수 없습니다.")
            return
        
        # 데이터 기간 정보 표시
        st.info(f"📅 데이터 기간: {min_date.strftime('%Y-%m-%d')} ~ {max_date.strftime('%Y-%m-%d')} (총 {len(date_counts)}일)")
        
        # 탭으로 분석 설정과 결과 분리
        tab1, tab2 = st.tabs(["📋 분석 설정", "📊 분석 결과"])
        
        with tab1:
            st.markdown("#### 분석 파라미터 설정")
            
            # 분석 유형 선택
            analysis_type = st.selectbox(
                "분석 유형 선택",
                ["직원 간 상호작용 네트워크", "공간 이동 네트워크", "시계열 동적 네트워크", "활동 기반 네트워크"],
                help="분석하고자 하는 네트워크 유형을 선택하세요."
            )
            
            # 기간 설정 섹션
            st.markdown("##### 📅 분석 기간 설정")
            col1, col2 = st.columns(2)
            
            # 기본 날짜 설정 (전체 기간)
            default_end = max_date
            default_start = min_date
            
            with col1:
                start_date = st.date_input(
                    "시작 날짜",
                    value=default_start,
                    min_value=min_date,
                    max_value=max_date,
                    key="network_start_date",
                    help=f"데이터가 있는 날짜: {min_date} ~ {max_date}"
                )
            with col2:
                end_date = st.date_input(
                    "종료 날짜",
                    value=default_end,
                    min_value=min_date,
                    max_value=max_date,
                    key="network_end_date",
                    help=f"데이터가 있는 날짜: {min_date} ~ {max_date}"
                )
            
            # 날짜 유효성 검사
            if start_date > end_date:
                st.error("시작 날짜는 종료 날짜보다 이전이어야 합니다.")
                return
            
            # 선택한 기간에 데이터가 있는지 확인
            selected_dates = pd.date_range(start_date, end_date).date
            data_exists = any(d in date_counts.index for d in selected_dates)
            
            if not data_exists:
                st.warning(f"선택한 기간({start_date} ~ {end_date})에 데이터가 없습니다. 다른 날짜를 선택해주세요.")
                
                # 데이터가 있는 날짜 표시
                with st.expander("데이터가 있는 날짜 확인"):
                    # 월별로 그룹화하여 표시
                    monthly_data = date_counts.groupby(pd.Grouper(freq='M')).sum()
                    if not monthly_data.empty:
                        fig = px.bar(
                            x=monthly_data.index,
                            y=monthly_data.values,
                            labels={'x': '월', 'y': '데이터 개수'},
                            title='월별 데이터 분포'
                        )
                        st.plotly_chart(fig, use_container_width=True)
                return
            
            # 분석 유형별 추가 설정
            st.markdown("##### ⚙️ 세부 설정")
            analysis_params = {}
            
            if analysis_type == "직원 간 상호작용 네트워크":
                col1, col2, col3 = st.columns(3)
                with col1:
                    analysis_params['interaction_threshold'] = st.slider(
                        "최소 상호작용 시간 (분)",
                        min_value=5,
                        max_value=60,
                        value=10,
                        step=5,
                        help="같은 위치에서 이 시간 내에 있으면 상호작용으로 간주"
                    )
                with col2:
                    analysis_params['department_filter'] = st.selectbox(
                        "부서 필터",
                        ["전체"] + self.get_departments()
                    )
                with col3:
                    analysis_params['visualization_type'] = st.selectbox(
                        "시각화 유형",
                        ["Force-directed", "Circular", "Hierarchical"]
                    )
            
            elif analysis_type == "공간 이동 네트워크":
                col1, col2 = st.columns(2)
                with col1:
                    analysis_params['analysis_level'] = st.selectbox(
                        "분석 수준",
                        ["개인별", "부서별", "전체"]
                    )
                with col2:
                    analysis_params['time_window'] = st.selectbox(
                        "시간대",
                        ["전체", "주간(08:00-20:00)", "야간(20:00-08:00)", 
                         "오전(06:00-12:00)", "오후(12:00-18:00)", "저녁(18:00-24:00)"]
                    )
            
            elif analysis_type == "시계열 동적 네트워크":
                col1, col2, col3 = st.columns(3)
                with col1:
                    analysis_params['time_granularity'] = st.selectbox(
                        "시간 단위",
                        ["시간별", "일별", "주별"]
                    )
                with col2:
                    analysis_params['network_type'] = st.selectbox(
                        "네트워크 유형",
                        ["상호작용", "이동", "협업"]
                    )
                with col3:
                    analysis_params['animation_speed'] = st.slider(
                        "애니메이션 속도",
                        min_value=100,
                        max_value=2000,
                        value=500,
                        step=100
                    )
            
            elif analysis_type == "활동 기반 네트워크":
                analysis_params['activity_types'] = st.multiselect(
                    "분석할 활동 유형",
                    ["업무", "회의", "식사", "휴식", "이동"],
                    default=["업무", "회의"]
                )
                analysis_params['network_method'] = st.selectbox(
                    "네트워크 구성 방법",
                    ["동시 활동", "순차 활동", "활동 전환"]
                )
            
            # 분석 시작 버튼
            st.markdown("---")
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                analyze_button = st.button(
                    "🚀 분석 시작",
                    type="primary",
                    use_container_width=True,
                    help="설정한 파라미터로 네트워크 분석을 시작합니다."
                )
            
            # 분석 실행
            if analyze_button:
                # 분석 파라미터를 세션 상태에 저장
                st.session_state['network_analysis_params'] = {
                    'analysis_type': analysis_type,
                    'start_date': start_date,
                    'end_date': end_date,
                    'timestamp': datetime.now(),
                    **analysis_params
                }
                
                # 분석 시작 플래그 설정
                st.session_state['network_analysis_running'] = True
                st.rerun()
        
        with tab2:
            # 분석 결과 표시
            if 'network_analysis_running' in st.session_state and st.session_state['network_analysis_running']:
                params = st.session_state.get('network_analysis_params', {})
                
                # 분석 정보 표시
                st.markdown("#### 📊 분석 진행 중...")
                
                # 진행 상황 표시
                progress_container = st.container()
                with progress_container:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # 단계별 진행 상황
                    steps = [
                        "데이터 로딩 중...",
                        "데이터 전처리 중...",
                        "네트워크 구성 중...",
                        "메트릭 계산 중...",
                        "시각화 생성 중..."
                    ]
                    
                    import time
                    for i, step in enumerate(steps):
                        progress = (i + 1) / len(steps)
                        progress_bar.progress(progress)
                        status_text.text(f"🔄 {step} ({int(progress * 100)}%)")
                        time.sleep(0.5)  # 시뮬레이션
                        
                        # 마지막 단계에서 실제 분석 수행
                        if i == len(steps) - 1:
                            try:
                                # 실제 분석 수행
                                self.perform_analysis(params)
                                
                                # 완료 상태
                                progress_bar.progress(1.0)
                                status_text.text("✅ 분석 완료!")
                                
                                # 분석 완료 후 플래그 해제
                                st.session_state['network_analysis_running'] = False
                                
                            except Exception as e:
                                st.error(f"분석 중 오류가 발생했습니다: {str(e)}")
                                st.session_state['network_analysis_running'] = False
            
            elif 'network_analysis_params' in st.session_state:
                # 이전 분석 결과가 있는 경우
                params = st.session_state['network_analysis_params']
                st.info(f"마지막 분석: {params['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
                
                # 결과 다시 보기 버튼
                if st.button("📈 이전 결과 다시 보기"):
                    self.perform_analysis(params)
            else:
                st.info("분석을 시작하려면 '분석 설정' 탭에서 파라미터를 설정하고 '분석 시작' 버튼을 클릭하세요.")
    
    def perform_analysis(self, params: dict):
        """분석 수행"""
        analysis_type = params['analysis_type']
        start_date = params['start_date']
        end_date = params['end_date']
        
        if analysis_type == "직원 간 상호작용 네트워크":
            self.render_interaction_network(
                start_date, end_date,
                params.get('interaction_threshold', 10),
                params.get('department_filter', "전체"),
                params.get('visualization_type', "Force-directed")
            )
        elif analysis_type == "공간 이동 네트워크":
            self.render_movement_network(
                start_date, end_date,
                params.get('analysis_level', "전체"),
                params.get('time_window', "전체")
            )
        elif analysis_type == "시계열 동적 네트워크":
            self.render_temporal_network(
                start_date, end_date,
                params.get('time_granularity', "일별"),
                params.get('network_type', "상호작용"),
                params.get('animation_speed', 500)
            )
        elif analysis_type == "활동 기반 네트워크":
            self.render_activity_network(
                start_date, end_date,
                params.get('activity_types', ["업무", "회의"]),
                params.get('network_method', "동시 활동")
            )
    
    # 이하 render_interaction_network, render_movement_network 등의 메서드들은
    # 원본 network_analysis_dashboard.py에서 가져와서 파라미터만 수정
    
    def render_interaction_network(self, start_date: date, end_date: date,
                                 interaction_threshold: int, department_filter: str,
                                 visualization_type: str):
        """직원 간 상호작용 네트워크 분석"""
        st.subheader("👥 직원 간 상호작용 네트워크")
        
        # 상호작용 데이터 분석
        interaction_data = self.analyze_interactions(
            start_date, end_date, interaction_threshold, department_filter
        )
        
        if interaction_data:
            # 네트워크 메트릭 표시
            self.display_network_metrics(interaction_data)
            
            # 네트워크 시각화
            self.visualize_interaction_network(interaction_data, visualization_type)
            
            # 중심성 분석
            self.display_centrality_analysis(interaction_data)
            
            # 커뮤니티 탐지
            self.display_community_detection(interaction_data)
        else:
            st.info("선택한 기간에 분석할 상호작용 데이터가 없습니다.")
    
    def render_movement_network(self, start_date: date, end_date: date,
                              analysis_level: str, time_window: str):
        """공간 이동 네트워크 분석"""
        st.subheader("🏢 공간 이동 네트워크")
        
        # 이동 데이터 분석
        movement_data = self.analyze_movement_patterns(
            start_date, end_date, analysis_level, time_window
        )
        
        if movement_data:
            # 전체 이동 통계
            self.display_movement_statistics(movement_data)
            
            # 공간 이동 맵 시각화
            self.visualize_movement_map(movement_data)
            
            # 이동 패턴 분석
            self.display_movement_patterns(movement_data)
            
            # 병목 지점 분석
            self.display_bottleneck_analysis(movement_data)
        else:
            st.info("선택한 기간에 분석할 이동 데이터가 없습니다.")
    
    def render_temporal_network(self, start_date: date, end_date: date,
                              time_granularity: str, network_type: str,
                              animation_speed: int):
        """시계열 동적 네트워크 분석"""
        st.subheader("📈 시계열 동적 네트워크")
        
        # 시계열 네트워크 데이터 분석
        temporal_data = self.analyze_temporal_network(
            start_date, end_date, time_granularity, network_type
        )
        
        if temporal_data and temporal_data.get('networks'):
            # 네트워크 진화 메트릭
            self.display_network_evolution_metrics(temporal_data)
            
            # 애니메이션 네트워크 시각화
            self.visualize_animated_network(temporal_data, animation_speed)
            
            # 시간대별 패턴 분석
            self.display_temporal_patterns(temporal_data)
            
            # 이상 패턴 탐지
            self.display_anomaly_detection(temporal_data)
        else:
            st.info("선택한 기간에 분석할 시계열 데이터가 없습니다.")
    
    def render_activity_network(self, start_date: date, end_date: date,
                              activity_types: List[str], network_method: str):
        """활동 기반 네트워크 분석"""
        st.subheader("⚡ 활동 기반 네트워크")
        
        # 활동 네트워크 데이터 분석
        activity_data = self.analyze_activity_network(
            start_date, end_date, activity_types, network_method
        )
        
        if activity_data:
            # 활동 네트워크 통계
            self.display_activity_statistics(activity_data)
            
            # 활동 네트워크 시각화
            self.visualize_activity_network(activity_data)
            
            # 활동 클러스터 분석
            self.display_activity_clusters(activity_data)
            
            # 활동 효율성 분석
            self.display_activity_efficiency(activity_data)
        else:
            st.info("선택한 기간에 분석할 활동 데이터가 없습니다.")
    
    # 나머지 분석 메서드들은 원본에서 그대로 가져오기
    def get_departments(self) -> List[str]:
        """부서 목록 가져오기"""
        try:
            from ...data_processing import PickleManager
            pickle_manager = PickleManager()
            
            # 조직 데이터에서 부서 정보 가져오기
            org_data = pickle_manager.load_dataframe(name='organization_data')
            if org_data is not None and 'TEAM' in org_data.columns:
                departments = org_data['TEAM'].dropna().unique().tolist()
                return sorted(departments)
            
            # 태그 데이터에서 부서 정보 가져오기
            tag_data = pickle_manager.load_dataframe(name='tag_data')
            if tag_data is not None and 'TEAM' in tag_data.columns:
                departments = tag_data['TEAM'].dropna().unique().tolist()
                return sorted(departments)
            
            return []
        except Exception as e:
            self.logger.error(f"부서 목록 가져오기 오류: {e}")
            return []
    
    # 원본의 나머지 메서드들을 여기에 추가 (analyze_interactions, display_network_metrics 등)
    # 지면 관계상 생략하지만 원본 파일에서 그대로 복사해서 사용