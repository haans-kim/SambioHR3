"""
네트워크 분석 대시보드 컴포넌트 - 성능 최적화 버전
조직 전체의 네트워크 분석 및 시각화
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
from functools import lru_cache
import concurrent.futures
from collections import defaultdict

from ...analysis.network_analyzer import NetworkAnalyzer
from ...database import DatabaseManager
from .common.organization_selector import OrganizationSelector

class NetworkAnalysisDashboard:
    """네트워크 분석 대시보드 컴포넌트 - 성능 최적화"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        self.network_analyzer = NetworkAnalyzer("data/sambio_human.db")
        self._tag_data_cache = None
        self._cache_date = None
        self._date_range_cache = None
        self.org_selector = OrganizationSelector()
        
    @property
    def tag_data(self):
        """태그 데이터 캐싱"""
        if self._tag_data_cache is None:
            from ...data_processing import PickleManager
            pickle_manager = PickleManager()
            self._tag_data_cache = pickle_manager.load_dataframe(name='tag_data')
            
            if self._tag_data_cache is not None:
                # 날짜와 시간 컬럼 사전 처리
                self._tag_data_cache['ENTE_DT'] = pd.to_numeric(self._tag_data_cache['ENTE_DT'], errors='coerce')
                self._tag_data_cache['time_str'] = self._tag_data_cache['출입시각'].astype(str).str.zfill(6)
                # timestamp를 미리 생성
                self._tag_data_cache['timestamp'] = pd.to_datetime(
                    self._tag_data_cache['ENTE_DT'].astype(str) + ' ' + self._tag_data_cache['time_str'],
                    format='%Y%m%d %H%M%S',
                    errors='coerce'
                )
                # 인덱스 설정으로 빠른 검색
                self._tag_data_cache.set_index('timestamp', inplace=True, drop=False)
                
        return self._tag_data_cache
    
    def get_data_date_range(self):
        """데이터가 존재하는 날짜 범위 반환"""
        if self._date_range_cache is not None:
            return self._date_range_cache
            
        if self.tag_data is None or self.tag_data.empty:
            return None, None
            
        try:
            # 타임스탬프에서 날짜 추출
            dates = self.tag_data['timestamp'].dt.date
            min_date = dates.min()
            max_date = dates.max()
            
            # 날짜별 데이터 개수 계산
            date_counts = dates.value_counts().sort_index()
            
            self._date_range_cache = (min_date, max_date, date_counts)
            return min_date, max_date, date_counts
            
        except Exception as e:
            self.logger.error(f"날짜 범위 계산 중 오류: {e}")
            return None, None, pd.Series()
    
    def render(self):
        """네트워크 분석 대시보드 렌더링"""
        st.markdown("### 🌐 조직 네트워크 분석")
        
        # 데이터 로드 상태 표시
        if self.tag_data is None:
            st.error("데이터를 로드할 수 없습니다.")
            return
        
        # 데이터 날짜 범위 확인
        min_date, max_date, date_counts = self.get_data_date_range()
        
        if min_date is None or max_date is None:
            st.error("데이터의 날짜 범위를 확인할 수 없습니다.")
            return
        
        # 데이터 기간 정보 표시
        st.info(f"📅 데이터 기간: {min_date.strftime('%Y-%m-%d')} ~ {max_date.strftime('%Y-%m-%d')} (총 {len(date_counts)}일)")
        
        # 탭 설정 - 분석 설정/결과와 분석 이력
        tab1, tab2 = st.tabs(["📋 네트워크 분석", "📁 분석 이력"])
        
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
            
            # 분석 범위 설정
            st.markdown("##### 🎯 분석 범위 설정")
            
            col1, col2 = st.columns(2)
            with col1:
                analysis_scope = st.radio(
                    "분석 범위",
                    ["전체 조직", "특정 조직", "특정 개인"],
                    help="분석할 대상의 범위를 선택하세요."
                )
            
            with col2:
                selected_targets = []
                org_selection = {}
                
                if analysis_scope == "특정 조직":
                    # 계층적 조직 선택
                    st.markdown("##### 🏢 조직 선택")
                    org_selection = self.org_selector.render_selection(
                        key_prefix="network_org",
                        allow_multiple=False,
                        show_employee_count=True
                    )
                    
                    # 선택된 조직 표시 이름
                    selected_targets = [self.org_selector.get_selection_display_name(org_selection)]
                    
                elif analysis_scope == "특정 개인":
                    # 개인 선택
                    employees = self.get_employees_cached()
                    
                    # 검색 기능
                    search_term = st.text_input(
                        "직원 검색",
                        placeholder="이름 또는 사번으로 검색",
                        help="직원 이름이나 사번을 입력하여 검색하세요."
                    )
                    
                    # 검색 결과 필터링
                    if search_term:
                        filtered_employees = [
                            emp for emp in employees 
                            if search_term.lower() in emp.lower()
                        ]
                    else:
                        filtered_employees = employees[:20]  # 처음 20명만 표시
                    
                    selected_employees = st.multiselect(
                        "직원 선택",
                        filtered_employees,
                        help="분석할 직원을 선택하세요. 복수 선택 가능합니다."
                    )
                    selected_targets = selected_employees
            
            # 선택된 범위 확인
            if analysis_scope == "특정 조직" and org_selection.get('center') == "전체":
                st.warning("특정 조직을 선택해주세요. '전체' 선택 시 전체 조직 분석을 사용하세요.")
                return
            elif analysis_scope == "특정 개인" and not selected_targets:
                st.warning("분석할 직원을 선택해주세요.")
                return
            
            # 분석 유형별 추가 설정
            st.markdown("##### ⚙️ 세부 설정")
            
            if analysis_type == "직원 간 상호작용 네트워크":
                col1, col2, col3 = st.columns(3)
                with col1:
                    interaction_threshold = st.slider(
                        "시간 단위 (분)",
                        min_value=15,
                        max_value=60,
                        value=30,
                        step=15,
                        help="같은 위치에서 이 시간 내에 있으면 상호작용으로 간주"
                    )
                with col2:
                    department_filter = st.selectbox(
                        "부서 필터",
                        ["전체"] + self.get_departments_cached()
                    )
                with col3:
                    visualization_type = st.selectbox(
                        "시각화 유형",
                        ["Force-directed", "Circular", "Hierarchical"]
                    )
            
            elif analysis_type == "공간 이동 네트워크":
                col1, col2 = st.columns(2)
                with col1:
                    # 기존 analysis_level을 삭제하고 위의 analysis_scope로 대체
                    pass
                with col2:
                    time_window = st.selectbox(
                        "시간대",
                        ["전체", "주간(08:00-20:00)", "야간(20:00-08:00)"]
                    )
            
            elif analysis_type == "시계열 동적 네트워크":
                col1, col2, col3 = st.columns(3)
                with col1:
                    time_granularity = st.selectbox(
                        "시간 단위",
                        ["시간별", "일별", "주별"]
                    )
                with col2:
                    network_type = st.selectbox(
                        "네트워크 유형",
                        ["상호작용", "이동", "협업"]
                    )
                with col3:
                    animation_speed = st.slider(
                        "애니메이션 속도",
                        min_value=100,
                        max_value=2000,
                        value=500,
                        step=100
                    )
            
            elif analysis_type == "활동 기반 네트워크":
                activity_types = st.multiselect(
                    "분석할 활동 유형",
                    ["업무", "회의", "식사", "휴식", "이동"],
                    default=["업무", "회의"]
                )
                network_method = st.selectbox(
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
            if analyze_button or st.session_state.get('rerun_analysis', False):
                # 분석 파라미터를 세션 상태에 저장
                st.session_state['network_analysis_params'] = {
                    'analysis_type': analysis_type,
                    'start_date': start_date,
                    'end_date': end_date,
                    'timestamp': datetime.now(),
                    'analysis_scope': analysis_scope,
                    'selected_targets': selected_targets,
                    'org_selection': org_selection if analysis_scope == "특정 조직" else None
                }
                
                # 분석 유형별 추가 파라미터 저장
                if analysis_type == "직원 간 상호작용 네트워크":
                    st.session_state['network_analysis_params'].update({
                        'interaction_threshold': interaction_threshold,
                        'department_filter': department_filter,
                        'visualization_type': visualization_type
                    })
                elif analysis_type == "공간 이동 네트워크":
                    st.session_state['network_analysis_params'].update({
                        'time_window': time_window
                    })
                elif analysis_type == "시계열 동적 네트워크":
                    st.session_state['network_analysis_params'].update({
                        'time_granularity': time_granularity,
                        'network_type': network_type,
                        'animation_speed': animation_speed
                    })
                elif analysis_type == "활동 기반 네트워크":
                    st.session_state['network_analysis_params'].update({
                        'activity_types': activity_types,
                        'network_method': network_method
                    })
                
                # 분석 즉시 실행
                st.session_state['network_analysis_running'] = True
            
            # 분석 시작 버튼이 눌렸거나 진행 중인 경우 결과 표시
            if st.session_state.get('network_analysis_running', False):
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
                    
                    for i, step in enumerate(steps):
                        progress = (i + 1) / len(steps)
                        progress_bar.progress(progress)
                        status_text.text(f"🔄 {step} ({int(progress * 100)}%)")
                        
                        # 실제 분석 수행 (단계별로)
                        if i == len(steps) - 1:
                            # 마지막 단계에서 실제 분석 수행
                            try:
                                if params['analysis_type'] == "직원 간 상호작용 네트워크":
                                    self.render_interaction_network_with_params(params)
                                elif params['analysis_type'] == "공간 이동 네트워크":
                                    self.render_movement_network_with_params(params)
                                elif params['analysis_type'] == "시계열 동적 네트워크":
                                    self.render_temporal_network_with_params(params)
                                elif params['analysis_type'] == "활동 기반 네트워크":
                                    self.render_activity_network_with_params(params)
                                
                                # 완료 상태
                                progress_bar.progress(1.0)
                                status_text.text("✅ 분석 완료!")
                                
                                # 분석 완료
                                st.session_state['network_analysis_running'] = False
                                
                                # 분석 이력 저장
                                if 'network_analysis_history' not in st.session_state:
                                    st.session_state['network_analysis_history'] = []
                                
                                # 현재 분석 결과를 이력에 추가
                                history_entry = {
                                    **params,
                                    'completed_at': datetime.now(),
                                    'id': len(st.session_state['network_analysis_history'])
                                }
                                st.session_state['network_analysis_history'].append(history_entry)
                                
                            except Exception as e:
                                st.error(f"분석 중 오류가 발생했습니다: {str(e)}")
                                st.session_state['network_analysis_running'] = False
        
        with tab2:
            # 분석 이력 탭
            st.markdown("#### 📁 분석 이력")
            
            if 'network_analysis_history' in st.session_state and st.session_state['network_analysis_history']:
                # 이력을 최신순으로 정렬
                history = sorted(st.session_state['network_analysis_history'], 
                               key=lambda x: x['completed_at'], reverse=True)
                
                # 이력 필터링 옵션
                col1, col2 = st.columns([2, 1])
                with col1:
                    filter_type = st.selectbox(
                        "분석 유형 필터",
                        ["전체"] + ["직원 간 상호작용 네트워크", "공간 이동 네트워크", 
                         "시계열 동적 네트워크", "활동 기반 네트워크"]
                    )
                
                # 필터링된 이력
                if filter_type != "전체":
                    filtered_history = [h for h in history if h['analysis_type'] == filter_type]
                else:
                    filtered_history = history
                
                # 이력 표시
                for idx, entry in enumerate(filtered_history[:10]):  # 최근 10건만 표시
                    with st.expander(
                        f"{entry['analysis_type']} - "
                        f"{entry['completed_at'].strftime('%Y-%m-%d %H:%M:%S')}",
                        expanded=False
                    ):
                        # 분석 상세 정보
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.write(f"**기간**: {entry['start_date']} ~ {entry['end_date']}")
                        with col2:
                            st.write(f"**분석 범위**: {entry.get('analysis_scope', '전체 조직')}")
                        with col3:
                            if entry.get('analysis_scope') == "특정 조직" and entry.get('org_selection'):
                                org_name = self.org_selector.get_selection_display_name(entry['org_selection'])
                                st.write(f"**대상**: {org_name}")
                            elif entry.get('selected_targets'):
                                st.write(f"**대상**: {', '.join(entry['selected_targets'][:3])}...")
                        
                        # 설정 상세
                        if entry['analysis_type'] == "직원 간 상호작용 네트워크":
                            st.write(f"- 상호작용 시간: {entry.get('interaction_threshold', 30)}분")
                            st.write(f"- 부서 필터: {entry.get('department_filter', '전체')}")
                            st.write(f"- 시각화: {entry.get('visualization_type', 'Force-directed')}")
                        
                        # 다시 실행 버튼
                        if st.button(f"🔄 이 설정으로 다시 분석", key=f"rerun_{entry['id']}_{idx}"):
                            # 이전 설정을 현재 설정으로 복사
                            st.session_state['network_analysis_params'] = entry.copy()
                            st.session_state['network_analysis_params']['timestamp'] = datetime.now()
                            st.session_state['rerun_analysis'] = True
                            st.rerun()
                
                # 이력 삭제 버튼
                if st.button("🗑️ 전체 이력 삭제", type="secondary"):
                    if st.checkbox("정말 삭제하시겠습니까?"):
                        st.session_state['network_analysis_history'] = []
                        st.success("분석 이력이 삭제되었습니다.")
                        st.rerun()
            else:
                st.info("아직 분석 이력이 없습니다. 네트워크 분석을 실행하면 이곳에 기록됩니다.")
        
        # 이전 분석 설정으로 돌아가기
        if st.session_state.get('rerun_analysis', False):
            st.session_state['rerun_analysis'] = False
            # 첫 번째 탭으로 전환하고 분석 실행
            st.session_state['network_analysis_running'] = True
    
    def get_filtered_data(self, start_date: date, end_date: date, department: str = None,
                         analysis_scope: str = None, selected_targets: List[str] = None,
                         org_selection: Dict = None) -> pd.DataFrame:
        """날짜와 범위로 필터링된 데이터 반환 - 최적화"""
        if self.tag_data is None:
            return pd.DataFrame()
            
        # 날짜를 timestamp로 변환
        start_timestamp = pd.Timestamp(start_date)
        end_timestamp = pd.Timestamp(end_date) + pd.Timedelta(days=1)
        
        # 인덱스를 사용한 빠른 필터링
        filtered = self.tag_data.loc[start_timestamp:end_timestamp].copy()
        
        # 분석 범위에 따른 필터링
        if analysis_scope == "특정 조직" and org_selection:
            # 조직 선택에 따른 직원 목록 가져오기
            employees = self.org_selector.get_employees_by_selection(org_selection)
            employee_ids = [emp['id'] for emp in employees]
            filtered = filtered[filtered['사번'].astype(str).isin(employee_ids)]
        elif analysis_scope == "특정 개인" and selected_targets:
            # 사번만 추출 ("사번 - 이름" 형식에서)
            employee_ids = []
            for target in selected_targets:
                if ' - ' in target:
                    employee_ids.append(target.split(' - ')[0])
                else:
                    employee_ids.append(target)
            filtered = filtered[filtered['사번'].astype(str).isin(employee_ids)]
        
        # 부서 필터링 (기존 로직 유지)
        if department and department != "전체":
            filtered = filtered[filtered['TEAM'] == department]
            
        return filtered
    
    def analyze_interactions_optimized(self, start_date: date, end_date: date, 
                                     threshold: int, department: str,
                                     analysis_scope: str = None, selected_targets: List[str] = None,
                                     org_selection: Dict = None) -> Optional[Dict]:
        """직원 간 상호작용 분석 - 최적화 버전"""
        try:
            # 필터링된 데이터 가져오기
            filtered_data = self.get_filtered_data(start_date, end_date, department, analysis_scope, selected_targets, org_selection)
            
            if filtered_data.empty:
                return None
            
            # 위치별, 시간대별로 그룹화 (30분 단위)
            filtered_data['time_slot'] = filtered_data['timestamp'].dt.floor('30min')
            
            # 벡터화된 연산으로 상호작용 찾기
            interactions = []
            
            # 위치와 시간대별로 그룹화
            grouped = filtered_data.groupby(['DR_NM', 'time_slot'])
            
            # 병렬 처리로 상호작용 계산
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = []
                
                for (location, time_slot), group in grouped:
                    if len(group) < 2:
                        continue
                    futures.append(
                        executor.submit(self._process_interaction_group, group, location, threshold)
                    )
                
                # 결과 수집
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        interactions.extend(result)
            
            if not interactions:
                return None
            
            # DataFrame 생성 및 집계
            df_interactions = pd.DataFrame(interactions)
            
            # 상호작용 횟수 집계
            interaction_counts = df_interactions.groupby(['employee1', 'employee2']).size().reset_index(name='interaction_count')
            
            # 네트워크 그래프 생성
            G = nx.Graph()
            
            for _, row in interaction_counts.iterrows():
                G.add_edge(
                    str(row['employee1']), 
                    str(row['employee2']), 
                    weight=row['interaction_count']
                )
            
            # 사번-이름 매핑 가져오기
            name_mapping = self.get_employee_name_mapping()
            
            # 중심성 계산 (노드가 충분할 때만)
            if G.number_of_nodes() > 0:
                degree_centrality = nx.degree_centrality(G)
                betweenness_centrality = nx.betweenness_centrality(G) if G.number_of_nodes() > 2 else {}
                closeness_centrality = nx.closeness_centrality(G) if nx.is_connected(G) else {}
            else:
                degree_centrality = {}
                betweenness_centrality = {}
                closeness_centrality = {}
            
            return {
                'graph': G,
                'interactions': df_interactions,
                'interaction_counts': interaction_counts,
                'degree_centrality': degree_centrality,
                'betweenness_centrality': betweenness_centrality,
                'closeness_centrality': closeness_centrality,
                'num_nodes': G.number_of_nodes(),
                'num_edges': G.number_of_edges(),
                'density': nx.density(G) if G.number_of_nodes() > 0 else 0,
                'name_mapping': name_mapping
            }
            
        except Exception as e:
            self.logger.error(f"상호작용 분석 중 오류: {e}")
            return None
    
    def _process_interaction_group(self, group: pd.DataFrame, location: str, threshold: int) -> List[Dict]:
        """그룹 내 상호작용 처리 - 헬퍼 함수"""
        interactions = []
        employees = group['사번'].unique()
        
        # 직원 쌍 생성 (중복 제거)
        for i, emp1 in enumerate(employees):
            for emp2 in employees[i+1:]:
                interactions.append({
                    'employee1': str(emp1),
                    'employee2': str(emp2),
                    'location': location,
                    'timestamp': group['timestamp'].iloc[0]
                })
        
        return interactions
    
    def render_interaction_network_with_params(self, params: dict):
        """파라미터를 사용한 상호작용 네트워크 렌더링"""
        self.render_interaction_network(
            params['start_date'],
            params['end_date'],
            params.get('interaction_threshold', 30),
            params.get('department_filter', "전체"),
            params.get('visualization_type', "Force-directed"),
            params.get('analysis_scope', "전체 조직"),
            params.get('selected_targets', []),
            params.get('org_selection', {})
        )
    
    def render_movement_network_with_params(self, params: dict):
        """파라미터를 사용한 이동 네트워크 렌더링"""
        self.render_movement_network(
            params['start_date'],
            params['end_date'],
            params.get('analysis_level', "전체"),
            params.get('time_window', "전체"),
            params.get('analysis_scope', "전체 조직"),
            params.get('selected_targets', []),
            params.get('org_selection', {})
        )
    
    def render_temporal_network_with_params(self, params: dict):
        """파라미터를 사용한 시계열 네트워크 렌더링"""
        self.render_temporal_network(
            params['start_date'],
            params['end_date']
        )
    
    def render_activity_network_with_params(self, params: dict):
        """파라미터를 사용한 활동 네트워크 렌더링"""
        self.render_activity_network(
            params['start_date'],
            params['end_date']
        )
    
    def render_interaction_network(self, start_date: date, end_date: date,
                                 interaction_threshold: int = None,
                                 department_filter: str = None,
                                 visualization_type: str = None,
                                 analysis_scope: str = None,
                                 selected_targets: List[str] = None,
                                 org_selection: Dict = None):
        """직원 간 상호작용 네트워크 분석"""
        st.subheader("👥 직원 간 상호작용 네트워크")
        
        # 파라미터가 제공되지 않은 경우 기본값 사용
        if interaction_threshold is None:
            interaction_threshold = 30
        if department_filter is None:
            department_filter = "전체"
        if visualization_type is None:
            visualization_type = "Force-directed"
        if analysis_scope is None:
            analysis_scope = "전체 조직"
        if selected_targets is None:
            selected_targets = []
        
        # 분석 범위 표시
        if analysis_scope == "특정 조직":
            st.info(f"🏢 분석 대상 부서: {', '.join(selected_targets)}")
        elif analysis_scope == "특정 개인":
            st.info(f"👤 분석 대상 직원: {', '.join(selected_targets)}")
        
        # 상호작용 데이터 분석
        interaction_data = self.analyze_interactions_optimized(
            start_date, end_date, interaction_threshold, department_filter,
            analysis_scope, selected_targets, org_selection
        )
        
        if interaction_data and interaction_data['num_nodes'] > 0:
            # 네트워크 메트릭 표시
            self.display_network_metrics(interaction_data)
            
            # 네트워크 시각화
            self.visualize_interaction_network(interaction_data, visualization_type)
            
            # 중심성 분석
            if interaction_data['degree_centrality']:
                self.display_centrality_analysis(interaction_data)
            
            # 커뮤니티 탐지
            if interaction_data['num_nodes'] > 3:
                self.display_community_detection(interaction_data)
        else:
            st.info("선택한 기간에 분석할 상호작용 데이터가 없습니다.")
    
    def analyze_movement_patterns_optimized(self, start_date: date, end_date: date,
                                          level: str, time_window: str,
                                          analysis_scope: str = None, selected_targets: List[str] = None,
                                          org_selection: Dict = None) -> Optional[Dict]:
        """공간 이동 패턴 분석 - 최적화 버전"""
        try:
            # 필터링된 데이터 가져오기
            filtered_data = self.get_filtered_data(start_date, end_date, None, analysis_scope, selected_targets, org_selection)
            
            if filtered_data.empty:
                return None
            
            # 시간대 필터링 (벡터화)
            if time_window != "전체":
                hour = filtered_data['timestamp'].dt.hour
                if time_window == "주간(08:00-20:00)":
                    filtered_data = filtered_data[(hour >= 8) & (hour < 20)]
                elif time_window == "야간(20:00-08:00)":
                    filtered_data = filtered_data[(hour >= 20) | (hour < 8)]
                # ... 기타 시간대 처리
            
            # 이동 분석을 위한 데이터 준비
            df = filtered_data.reset_index(drop=True)
            df = df.sort_values(['사번', 'timestamp'])
            
            # 벡터화된 이전 위치 계산
            df['prev_location'] = df.groupby('사번')['DR_NM'].shift(1)
            df['location'] = df['DR_NM']
            
            # 이동만 필터링 (위치가 변경된 경우)
            movements = df[df['prev_location'].notna() & (df['location'] != df['prev_location'])].copy()
            
            if movements.empty:
                return None
            
            # 건물 매핑 (벡터화)
            movements['from_building'] = movements['prev_location'].apply(
                self.network_analyzer.mapper.get_building_from_location
            )
            movements['to_building'] = movements['location'].apply(
                self.network_analyzer.mapper.get_building_from_location
            )
            
            # 유효한 이동만 필터링
            valid_movements = movements[
                movements['from_building'].notna() & 
                movements['to_building'].notna()
            ]
            
            # 이동 통계 계산
            movement_counts = valid_movements.groupby(
                ['from_building', 'to_building']
            ).size().reset_index(name='count')
            
            # 건물별 방문 통계
            building_visits = valid_movements['to_building'].value_counts()
            
            return {
                'movements': valid_movements,
                'movement_counts': movement_counts,
                'building_visits': building_visits,
                'total_movements': len(valid_movements),
                'unique_paths': len(movement_counts)
            }
            
        except Exception as e:
            self.logger.error(f"이동 패턴 분석 중 오류: {e}")
            return None
    
    def render_movement_network(self, start_date: date, end_date: date,
                              analysis_level: str = None, time_window: str = None,
                              analysis_scope: str = None, selected_targets: List[str] = None,
                              org_selection: Dict = None):
        """공간 이동 네트워크 분석"""
        st.subheader("🏢 공간 이동 네트워크")
        
        # 파라미터가 제공되지 않은 경우 기본값 사용
        if analysis_level is None:
            analysis_level = "전체"
        if time_window is None:
            time_window = "전체"
        if analysis_scope is None:
            analysis_scope = "전체 조직"
        if selected_targets is None:
            selected_targets = []
        
        # 분석 범위 표시
        if analysis_scope == "특정 조직":
            st.info(f"🏢 분석 대상 부서: {', '.join(selected_targets)}")
        elif analysis_scope == "특정 개인":
            st.info(f"👤 분석 대상 직원: {', '.join(selected_targets)}")
        
        # 이동 데이터 분석
        movement_data = self.analyze_movement_patterns_optimized(
            start_date, end_date, analysis_level, time_window,
            analysis_scope, selected_targets, org_selection
        )
        
        if movement_data and movement_data['total_movements'] > 0:
            # 전체 이동 통계
            self.display_movement_statistics(movement_data)
            
            # 공간 이동 맵 시각화
            self.visualize_movement_map(movement_data)
            
            # 이동 패턴 분석
            self.display_movement_patterns(movement_data)
        else:
            st.info("선택한 기간에 분석할 이동 데이터가 없습니다.")
    
    @lru_cache(maxsize=1)
    def get_departments_cached(self) -> List[str]:
        """부서 목록 가져오기 - 캐싱"""
        try:
            if self.tag_data is not None and 'TEAM' in self.tag_data.columns:
                departments = self.tag_data['TEAM'].dropna().unique().tolist()
                return sorted(departments)
            return []
        except Exception as e:
            self.logger.error(f"부서 목록 가져오기 오류: {e}")
            return []
    
    @lru_cache(maxsize=1)
    def get_employees_cached(self) -> List[str]:
        """직원 목록 가져오기 - 캐싱"""
        try:
            if self.tag_data is not None:
                # 사번과 이름이 있다면 결합하여 표시
                if '사번' in self.tag_data.columns:
                    employees = self.tag_data['사번'].dropna().unique()
                    # 이름 정보가 있다면 추가
                    if '성명' in self.tag_data.columns:
                        emp_info = self.tag_data[['사번', '성명']].drop_duplicates()
                        emp_list = []
                        for _, row in emp_info.iterrows():
                            if pd.notna(row['사번']) and pd.notna(row['성명']):
                                emp_list.append(f"{row['사번']} - {row['성명']}")
                            elif pd.notna(row['사번']):
                                emp_list.append(str(row['사번']))
                        return sorted(emp_list)
                    else:
                        return sorted([str(emp) for emp in employees])
            return []
        except Exception as e:
            self.logger.error(f"직원 목록 가져오기 오류: {e}")
            return []
    
    @lru_cache(maxsize=1)
    def get_employee_name_mapping(self) -> Dict[str, str]:
        """사번-이름 매핑 딕셔너리 반환"""
        try:
            mapping = {}
            
            # 태그 데이터에서 매핑 정보 가져오기
            if self.tag_data is not None and '사번' in self.tag_data.columns:
                if '성명' in self.tag_data.columns:
                    emp_info = self.tag_data[['사번', '성명']].drop_duplicates()
                    for _, row in emp_info.iterrows():
                        if pd.notna(row['사번']) and pd.notna(row['성명']):
                            mapping[str(row['사번'])] = row['성명']
                    return mapping
            
            # 조직 데이터에서 매핑 정보 가져오기 (태그 데이터에 없는 경우)
            if not mapping:
                from ...data_processing import PickleManager
                pickle_manager = PickleManager()
                org_data = pickle_manager.load_dataframe(name='organization_data')
                
                if org_data is not None and '사번' in org_data.columns and '성명' in org_data.columns:
                    for _, row in org_data.iterrows():
                        if pd.notna(row['사번']) and pd.notna(row['성명']):
                            mapping[str(row['사번'])] = row['성명']
            
            return mapping
            
        except Exception as e:
            self.logger.error(f"사번-이름 매핑 가져오기 오류: {e}")
            return {}
    
    def display_network_metrics(self, interaction_data: Dict):
        """네트워크 메트릭 표시"""
        st.markdown("#### 📊 네트워크 메트릭")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("노드 수", interaction_data['num_nodes'])
        with col2:
            st.metric("엣지 수", interaction_data['num_edges'])
        with col3:
            st.metric("네트워크 밀도", f"{interaction_data['density']:.3f}")
        with col4:
            avg_degree = (2 * interaction_data['num_edges']) / interaction_data['num_nodes'] if interaction_data['num_nodes'] > 0 else 0
            st.metric("평균 연결도", f"{avg_degree:.2f}")
    
    def visualize_interaction_network(self, interaction_data: Dict, viz_type: str):
        """상호작용 네트워크 시각화"""
        st.markdown("#### 🌐 네트워크 시각화")
        
        G = interaction_data['graph']
        
        # 노드가 너무 많으면 샘플링
        if G.number_of_nodes() > 100:
            st.warning(f"노드가 {G.number_of_nodes()}개로 많아 상위 100개만 표시합니다.")
            # 연결이 많은 상위 100개 노드만 선택
            degree_dict = dict(G.degree())
            top_nodes = sorted(degree_dict.keys(), key=lambda x: degree_dict[x], reverse=True)[:100]
            G = G.subgraph(top_nodes)
        
        # 레이아웃 선택
        if viz_type == "Force-directed":
            pos = nx.spring_layout(G, k=1/np.sqrt(G.number_of_nodes()), iterations=50)
        elif viz_type == "Circular":
            pos = nx.circular_layout(G)
        else:  # Hierarchical
            pos = nx.kamada_kawai_layout(G)
        
        # Plotly 그래프 생성
        edge_trace = []
        for edge in G.edges(data=True):
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_trace.append(go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                mode='lines',
                line=dict(width=0.5 + edge[2]['weight']/10, color='#888'),
                hoverinfo='none'
            ))
        
        # 노드 크기 계산
        node_sizes = []
        for node in G.nodes():
            degree = G.degree(node)
            size = 10 + min(degree * 2, 50)  # 최대 크기 제한
            node_sizes.append(size)
        
        # 사번-이름 매핑 가져오기
        name_mapping = interaction_data.get('name_mapping', {})
        
        # 노드 라벨 생성 (이름 우선, 없으면 사번)
        node_labels = []
        hover_texts = []
        for node in G.nodes():
            name = name_mapping.get(str(node), str(node))
            node_labels.append(name)
            # 호버 텍스트에는 사번과 이름 모두 표시
            hover_texts.append(f"사번: {node}<br>이름: {name}<br>연결도: {G.degree(node)}")
        
        node_trace = go.Scatter(
            x=[pos[node][0] for node in G.nodes()],
            y=[pos[node][1] for node in G.nodes()],
            mode='markers+text',
            text=node_labels,
            textposition="top center",
            hoverinfo='text',
            hovertext=hover_texts,
            marker=dict(
                size=node_sizes,
                color=[interaction_data['degree_centrality'].get(node, 0) for node in G.nodes()],
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(
                    thickness=15,
                    title='Degree<br>Centrality',
                    xanchor='left',
                    titleside='right'
                )
            )
        )
        
        fig = go.Figure(data=edge_trace + [node_trace])
        fig.update_layout(
            showlegend=False,
            hovermode='closest',
            margin=dict(b=0, l=0, r=0, t=0),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            height=600
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def display_centrality_analysis(self, interaction_data: Dict):
        """중심성 분석 결과 표시"""
        st.markdown("#### 🎯 중심성 분석")
        
        # 사번-이름 매핑 가져오기
        name_mapping = interaction_data.get('name_mapping', {})
        
        # 상위 10명의 중심 인물
        centrality_data = []
        for emp_id in interaction_data['degree_centrality'].keys():
            name = name_mapping.get(str(emp_id), str(emp_id))
            centrality_data.append({
                'Employee': f"{name} ({emp_id})",
                'Degree Centrality': interaction_data['degree_centrality'][emp_id],
                'Betweenness Centrality': interaction_data['betweenness_centrality'].get(emp_id, 0),
                'Closeness Centrality': interaction_data['closeness_centrality'].get(emp_id, 0)
            })
        
        centrality_df = pd.DataFrame(centrality_data)
        
        # 상위 10명만 표시
        top_central = centrality_df.nlargest(10, 'Degree Centrality')
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig1 = px.bar(top_central, x='Employee', y='Degree Centrality',
                         title='연결 중심성 상위 10명')
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            fig2 = px.bar(top_central, x='Employee', y='Betweenness Centrality',
                         title='매개 중심성 상위 10명')
            st.plotly_chart(fig2, use_container_width=True)
    
    def visualize_movement_map(self, movement_data: Dict):
        """공간 이동 맵 시각화"""
        facility_image_path = Path(__file__).parent.parent.parent.parent / 'data' / 'Sambio.png'
        
        if not facility_image_path.exists():
            st.warning("시설 이미지를 찾을 수 없습니다.")
            return
        
        # 이동 네트워크 생성
        G = nx.DiGraph()
        
        movement_counts = movement_data['movement_counts']
        for _, row in movement_counts.iterrows():
            G.add_edge(row['from_building'], row['to_building'], weight=row['count'])
        
        # matplotlib 시각화
        from PIL import Image
        img = Image.open(facility_image_path)
        
        fig, ax = plt.subplots(figsize=(20, 12))
        ax.imshow(img, alpha=0.7)
        
        # 노드 위치 설정
        img_width, img_height = img.size
        pos = {}
        for node in G.nodes():
            coords = self.network_analyzer.mapper.get_coordinates(node, img_width, img_height)
            if coords:
                pos[node] = coords
        
        # 노드 크기 (방문 횟수 기반)
        node_sizes = []
        for node in G.nodes():
            if node in movement_data['building_visits']:
                size = 500 + movement_data['building_visits'][node] * 10
            else:
                size = 500
            node_sizes.append(size)
        
        # 네트워크 그리기
        nx.draw_networkx_nodes(G, pos, node_size=node_sizes, 
                             node_color='lightblue', alpha=0.8, ax=ax)
        
        # 엣지 그리기
        edges = G.edges()
        weights = [G[u][v]['weight'] for u, v in edges]
        max_weight = max(weights) if weights else 1
        
        nx.draw_networkx_edges(G, pos, width=[1 + (w/max_weight)*5 for w in weights],
                             edge_color='blue', alpha=0.6, arrows=True,
                             arrowsize=20, ax=ax)
        
        # 레이블
        labels = {}
        for node in G.nodes():
            count = movement_data['building_visits'].get(node, 0)
            labels[node] = f"{node}\n({count})"
        
        nx.draw_networkx_labels(G, pos, labels, font_size=12, font_weight='bold', ax=ax)
        
        ax.set_title("공간 이동 네트워크", fontsize=16)
        ax.axis('off')
        
        st.pyplot(fig, use_container_width=True)
        plt.close()
    
    def display_movement_statistics(self, movement_data: Dict):
        """이동 통계 표시"""
        st.markdown("#### 📊 이동 통계")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("총 이동 횟수", movement_data['total_movements'])
        with col2:
            st.metric("고유 이동 경로", movement_data['unique_paths'])
        with col3:
            st.metric("방문 건물 수", len(movement_data['building_visits']))
        
        # 상위 이동 경로
        st.markdown("##### 🔝 상위 이동 경로")
        top_paths = movement_data['movement_counts'].nlargest(10, 'count')
        
        fig = px.bar(top_paths, 
                    x='count', 
                    y=top_paths['from_building'] + ' → ' + top_paths['to_building'],
                    orientation='h',
                    title='가장 빈번한 이동 경로 Top 10')
        st.plotly_chart(fig, use_container_width=True)
    
    def display_movement_patterns(self, movement_data: Dict):
        """이동 패턴 분석 표시"""
        st.markdown("#### 🔄 이동 패턴")
        
        # 시간대별 이동 패턴
        movements = movement_data['movements']
        movements['hour'] = movements['timestamp'].dt.hour
        
        hourly_movements = movements.groupby('hour').size()
        
        fig = px.line(x=hourly_movements.index, y=hourly_movements.values,
                     labels={'x': '시간', 'y': '이동 횟수'},
                     title='시간대별 이동 패턴')
        st.plotly_chart(fig, use_container_width=True)
    
    def render_temporal_network(self, start_date: date, end_date: date):
        """시계열 동적 네트워크 분석 - 간소화"""
        st.subheader("📈 시계열 동적 네트워크")
        
        st.info("대용량 데이터 처리를 위해 간소화된 분석을 제공합니다.")
        
        # 기간별 네트워크 메트릭 변화 표시
        filtered_data = self.get_filtered_data(start_date, end_date)
        
        if not filtered_data.empty:
            # 일별 활동량 추이
            daily_activity = filtered_data.groupby(filtered_data['timestamp'].dt.date).size()
            
            fig = px.line(x=daily_activity.index, y=daily_activity.values,
                         labels={'x': '날짜', 'y': '활동 수'},
                         title='일별 활동량 추이')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("선택한 기간에 데이터가 없습니다.")
    
    def render_activity_network(self, start_date: date, end_date: date):
        """활동 기반 네트워크 분석 - 간소화"""
        st.subheader("⚡ 활동 기반 네트워크")
        
        filtered_data = self.get_filtered_data(start_date, end_date)
        
        if not filtered_data.empty:
            # 위치 기반 활동 분류
            activity_counts = filtered_data['DR_NM'].value_counts().head(20)
            
            fig = px.bar(x=activity_counts.values, y=activity_counts.index,
                        orientation='h',
                        labels={'x': '방문 횟수', 'y': '위치'},
                        title='주요 활동 위치')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("선택한 기간에 데이터가 없습니다.")
    
    def display_community_detection(self, interaction_data: Dict):
        """커뮤니티 탐지 결과 표시"""
        st.markdown("#### 👥 커뮤니티 탐지")
        
        G = interaction_data['graph']
        
        try:
            # Greedy modularity communities (networkx 내장)
            from networkx.algorithms.community import greedy_modularity_communities
            
            communities = list(greedy_modularity_communities(G))
            
            # 커뮤니티별 멤버 수
            community_sizes = [len(c) for c in communities]
            
            st.write(f"발견된 커뮤니티 수: {len(communities)}")
            
            # 커뮤니티 크기 분포
            fig = px.bar(x=list(range(len(community_sizes))), 
                        y=community_sizes,
                        labels={'x': '커뮤니티 ID', 'y': '멤버 수'},
                        title='커뮤니티별 크기 분포')
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.info("커뮤니티 탐지를 수행할 수 없습니다.")