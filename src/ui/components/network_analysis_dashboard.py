"""
네트워크 분석 대시보드 컴포넌트
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

from ...analysis.network_analyzer import NetworkAnalyzer
from ...database import DatabaseManager

class NetworkAnalysisDashboard:
    """네트워크 분석 대시보드 컴포넌트"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        self.network_analyzer = NetworkAnalyzer("data/sambio_human.db")
        self._tag_data_cache = None
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
        
        # 분석 유형 선택
        analysis_type = st.selectbox(
            "분석 유형 선택",
            ["직원 간 상호작용 네트워크", "공간 이동 네트워크", "시계열 동적 네트워크", "활동 기반 네트워크"]
        )
        
        # 기간 선택
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
        
        if analysis_type == "직원 간 상호작용 네트워크":
            self.render_interaction_network(start_date, end_date)
        elif analysis_type == "공간 이동 네트워크":
            self.render_movement_network(start_date, end_date)
        elif analysis_type == "시계열 동적 네트워크":
            self.render_temporal_network(start_date, end_date)
        elif analysis_type == "활동 기반 네트워크":
            self.render_activity_network(start_date, end_date)
    
    def render_interaction_network(self, start_date: date, end_date: date):
        """직원 간 상호작용 네트워크 분석"""
        st.subheader("👥 직원 간 상호작용 네트워크")
        
        # 분석 옵션
        col1, col2, col3 = st.columns(3)
        with col1:
            interaction_threshold = st.slider(
                "최소 상호작용 시간 (분)",
                min_value=5,
                max_value=60,
                value=10,
                step=5
            )
        with col2:
            department_filter = st.selectbox(
                "부서 필터",
                ["전체"] + self.get_departments()
            )
        with col3:
            visualization_type = st.selectbox(
                "시각화 유형",
                ["Force-directed", "Circular", "Hierarchical"]
            )
        
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
    
    def render_movement_network(self, start_date: date, end_date: date):
        """공간 이동 네트워크 분석"""
        st.subheader("🏢 공간 이동 네트워크")
        
        # 분석 옵션
        col1, col2 = st.columns(2)
        with col1:
            analysis_level = st.selectbox(
                "분석 수준",
                ["개인별", "부서별", "전체"]
            )
        with col2:
            time_window = st.selectbox(
                "시간대",
                ["전체", "주간(08:00-20:00)", "야간(20:00-08:00)", 
                 "오전(06:00-12:00)", "오후(12:00-18:00)", "저녁(18:00-24:00)"]
            )
        
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
    
    def render_temporal_network(self, start_date: date, end_date: date):
        """시계열 동적 네트워크 분석"""
        st.subheader("📈 시계열 동적 네트워크")
        
        # 분석 옵션
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
    
    def render_activity_network(self, start_date: date, end_date: date):
        """활동 기반 네트워크 분석"""
        st.subheader("⚡ 활동 기반 네트워크")
        
        # 활동 유형 선택
        activity_types = st.multiselect(
            "분석할 활동 유형",
            ["업무", "회의", "식사", "휴식", "이동"],
            default=["업무", "회의"]
        )
        
        # 네트워크 구성 방법
        network_method = st.selectbox(
            "네트워크 구성 방법",
            ["동시 활동", "순차 활동", "활동 전환"]
        )
        
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
    
    def analyze_interactions(self, start_date: date, end_date: date, 
                           threshold: int, department: str) -> Optional[Dict]:
        """직원 간 상호작용 분석"""
        try:
            # Pickle 파일에서 태그 데이터 로드
            from ...data_processing import PickleManager
            pickle_manager = PickleManager()
            tag_data = pickle_manager.load_dataframe(name='tag_data')
            
            if tag_data is None or tag_data.empty:
                return None
            
            # 날짜 필터링
            start_str = start_date.strftime('%Y%m%d')
            end_str = end_date.strftime('%Y%m%d')
            
            # ENTE_DT를 정수로 변환
            tag_data['ENTE_DT'] = pd.to_numeric(tag_data['ENTE_DT'], errors='coerce')
            filtered_data = tag_data[
                (tag_data['ENTE_DT'] >= int(start_str)) & 
                (tag_data['ENTE_DT'] <= int(end_str))
            ].copy()
            
            if filtered_data.empty:
                return None
            
            # 부서 필터링
            if department != "전체":
                filtered_data = filtered_data[filtered_data['TEAM'] == department]
            
            # 시간 문자열을 datetime으로 변환
            # 출입시각을 6자리 문자열로 변환 (HHMMSS 형식)
            filtered_data['time'] = filtered_data['출입시각'].astype(str).str.zfill(6)
            filtered_data['timestamp'] = pd.to_datetime(
                filtered_data['ENTE_DT'].astype(str) + ' ' + filtered_data['time'],
                format='%Y%m%d %H%M%S',
                errors='coerce'
            )
            
            # 상호작용 찾기 - 같은 시간(threshold 분 이내), 같은 장소에 있는 직원들
            interactions = []
            
            # 위치별로 그룹화
            for location, location_group in filtered_data.groupby('DR_NM'):
                # 시간순으로 정렬
                location_group = location_group.sort_values('timestamp')
                
                # 각 레코드에 대해 threshold 시간 내의 다른 직원 찾기
                for i, row1 in location_group.iterrows():
                    for j, row2 in location_group.iterrows():
                        if i >= j:  # 중복 방지
                            continue
                        
                        if row1['사번'] == row2['사번']:  # 같은 직원 제외
                            continue
                        
                        # 시간 차이 계산
                        time_diff = abs((row2['timestamp'] - row1['timestamp']).total_seconds() / 60)
                        
                        if time_diff <= threshold:
                            interactions.append({
                                'employee1': str(row1['사번']),
                                'employee2': str(row2['사번']),
                                'timestamp': row1['timestamp'],
                                'location': location,
                                'time_diff': time_diff
                            })
            
            if not interactions:
                return None
            
            df = pd.DataFrame(interactions)
            
            # 네트워크 그래프 생성
            G = nx.Graph()
            
            # 노드와 엣지 추가
            for _, row in df.iterrows():
                G.add_edge(
                    row['employee1'], 
                    row['employee2'], 
                    weight=row['interaction_count']
                )
            
            # 중심성 계산
            degree_centrality = nx.degree_centrality(G)
            betweenness_centrality = nx.betweenness_centrality(G)
            closeness_centrality = nx.closeness_centrality(G)
            
            return {
                'graph': G,
                'interactions': df,
                'degree_centrality': degree_centrality,
                'betweenness_centrality': betweenness_centrality,
                'closeness_centrality': closeness_centrality,
                'num_nodes': G.number_of_nodes(),
                'num_edges': G.number_of_edges(),
                'density': nx.density(G) if G.number_of_nodes() > 0 else 0
            }
            
        except Exception as e:
            self.logger.error(f"상호작용 분석 중 오류: {e}")
            return None
    
    def analyze_movement_patterns(self, start_date: date, end_date: date,
                                level: str, time_window: str) -> Optional[Dict]:
        """공간 이동 패턴 분석"""
        try:
            # Pickle 파일에서 태그 데이터 로드
            from ...data_processing import PickleManager
            pickle_manager = PickleManager()
            tag_data = pickle_manager.load_dataframe(name='tag_data')
            
            if tag_data is None or tag_data.empty:
                return None
            
            # 날짜 필터링
            start_str = start_date.strftime('%Y%m%d')
            end_str = end_date.strftime('%Y%m%d')
            
            # ENTE_DT를 정수로 변환
            tag_data['ENTE_DT'] = pd.to_numeric(tag_data['ENTE_DT'], errors='coerce')
            filtered_data = tag_data[
                (tag_data['ENTE_DT'] >= int(start_str)) & 
                (tag_data['ENTE_DT'] <= int(end_str))
            ].copy()
            
            if filtered_data.empty:
                return None
            
            # 시간 문자열을 datetime으로 변환
            # 출입시각을 6자리 문자열로 변환 (HHMMSS 형식)
            filtered_data['time'] = filtered_data['출입시각'].astype(str).str.zfill(6)
            filtered_data['timestamp'] = pd.to_datetime(
                filtered_data['ENTE_DT'].astype(str) + ' ' + filtered_data['time'],
                format='%Y%m%d %H%M%S',
                errors='coerce'
            )
            
            # 시간대 필터링
            if time_window != "전체":
                hour = filtered_data['timestamp'].dt.hour
                if time_window == "주간(08:00-20:00)":
                    filtered_data = filtered_data[(hour >= 8) & (hour < 20)]
                elif time_window == "야간(20:00-08:00)":
                    filtered_data = filtered_data[(hour >= 20) | (hour < 8)]
                elif time_window == "오전(06:00-12:00)":
                    filtered_data = filtered_data[(hour >= 6) & (hour < 12)]
                elif time_window == "오후(12:00-18:00)":
                    filtered_data = filtered_data[(hour >= 12) & (hour < 18)]
                elif time_window == "저녁(18:00-24:00)":
                    filtered_data = filtered_data[(hour >= 18) & (hour < 24)]
            
            # 직원별로 정렬
            df = filtered_data.sort_values(['사번', 'timestamp'])
            
            # 이전 위치 계산
            df['prev_location'] = df.groupby('사번')['DR_NM'].shift(1)
            df['employee_id'] = df['사번'].astype(str)
            df['location'] = df['DR_NM']
            
            # 이동 분석
            movements = df[df['prev_location'].notna() & (df['location'] != df['prev_location'])].copy()
            
            # 디버깅 정보
            with st.expander("이동 데이터 분석", expanded=False):
                st.write(f"전체 레코드 수: {len(df)}")
                st.write(f"이동 감지 수 (위치 변경): {len(movements)}")
                if len(movements) > 0:
                    st.write("이동 샘플 (처음 5개):")
                    st.dataframe(movements[['employee_id', 'prev_location', 'location']].head())
            
            # 건물 매핑
            movements['from_building'] = movements['prev_location'].apply(
                self.network_analyzer.mapper.get_building_from_location
            )
            movements['to_building'] = movements['location'].apply(
                self.network_analyzer.mapper.get_building_from_location
            )
            
            # 건물 매핑 확인
            with st.expander("건물 매핑 결과", expanded=False):
                st.write(f"건물 매핑 전: {len(movements)}")
                st.write(f"from_building null: {movements['from_building'].isna().sum()}")
                st.write(f"to_building null: {movements['to_building'].isna().sum()}")
                
                # 매핑 실패 샘플
                failed_mapping = movements[movements['from_building'].isna() | movements['to_building'].isna()]
                if len(failed_mapping) > 0:
                    st.write("매핑 실패 샘플:")
                    st.dataframe(failed_mapping[['prev_location', 'location', 'from_building', 'to_building']].head(10))
            
            # 유효한 이동만 필터링
            valid_movements = movements[
                movements['from_building'].notna() & 
                movements['to_building'].notna()
            ]
            
            st.write(f"유효한 건물 간 이동: {len(valid_movements)}")
            
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
        
        node_trace = go.Scatter(
            x=[pos[node][0] for node in G.nodes()],
            y=[pos[node][1] for node in G.nodes()],
            mode='markers+text',
            text=[str(node) for node in G.nodes()],
            textposition="top center",
            hoverinfo='text',
            marker=dict(
                size=[10 + interaction_data['degree_centrality'][node] * 50 for node in G.nodes()],
                color=[interaction_data['betweenness_centrality'][node] for node in G.nodes()],
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(
                    thickness=15,
                    title='Betweenness<br>Centrality',
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
        
        # 상위 10명의 중심 인물
        centrality_df = pd.DataFrame({
            'Employee': list(interaction_data['degree_centrality'].keys()),
            'Degree Centrality': list(interaction_data['degree_centrality'].values()),
            'Betweenness Centrality': [interaction_data['betweenness_centrality'][k] 
                                      for k in interaction_data['degree_centrality'].keys()],
            'Closeness Centrality': [interaction_data['closeness_centrality'][k] 
                                   for k in interaction_data['degree_centrality'].keys()]
        })
        
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
            labels[node] = f"{node}\\n({count})"
        
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
    
    def get_departments(self) -> List[str]:
        """부서 목록 가져오기"""
        try:
            # Pickle 파일에서 부서 정보 가져오기
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
    
    def display_community_detection(self, interaction_data: Dict):
        """커뮤니티 탐지 결과 표시"""
        st.markdown("#### 👥 커뮤니티 탐지")
        
        G = interaction_data['graph']
        
        # Louvain 알고리즘으로 커뮤니티 탐지
        try:
            import community as community_louvain
            communities = community_louvain.best_partition(G)
            
            # 커뮤니티별 멤버 수
            community_sizes = {}
            for node, comm in communities.items():
                if comm not in community_sizes:
                    community_sizes[comm] = 0
                community_sizes[comm] += 1
            
            # 커뮤니티 정보 표시
            st.write(f"발견된 커뮤니티 수: {len(community_sizes)}")
            
            # 커뮤니티 크기 분포
            fig = px.bar(x=list(community_sizes.keys()), 
                        y=list(community_sizes.values()),
                        labels={'x': '커뮤니티 ID', 'y': '멤버 수'},
                        title='커뮤니티별 크기 분포')
            st.plotly_chart(fig, use_container_width=True)
            
        except ImportError:
            st.info("커뮤니티 탐지를 위해 python-louvain 패키지가 필요합니다.")
    
    def analyze_temporal_network(self, start_date: date, end_date: date,
                               time_granularity: str, network_type: str) -> Optional[Dict]:
        """시계열 네트워크 데이터 분석"""
        try:
            # Pickle 파일에서 태그 데이터 로드
            from ...data_processing import PickleManager
            pickle_manager = PickleManager()
            tag_data = pickle_manager.load_dataframe(name='tag_data')
            
            if tag_data is None or tag_data.empty:
                st.error("태그 데이터를 로드할 수 없습니다.")
                return None
            
            # 날짜 필터링
            start_str = start_date.strftime('%Y%m%d')
            end_str = end_date.strftime('%Y%m%d')
            
            # 디버깅 정보 표시
            with st.expander("데이터 확인", expanded=False):
                st.write(f"선택한 기간: {start_str} ~ {end_str}")
                st.write(f"전체 데이터 수: {len(tag_data)}")
                
            tag_data['ENTE_DT'] = pd.to_numeric(tag_data['ENTE_DT'], errors='coerce')
            filtered_data = tag_data[
                (tag_data['ENTE_DT'] >= int(start_str)) & 
                (tag_data['ENTE_DT'] <= int(end_str))
            ].copy()
            
            if filtered_data.empty:
                st.warning(f"선택한 기간({start_str} ~ {end_str})에 데이터가 없습니다.")
                return None
            
            # 시간 정보 생성
            # 출입시각을 6자리 문자열로 변환 (HHMMSS 형식)
            filtered_data['time'] = filtered_data['출입시각'].astype(str).str.zfill(6)
            filtered_data['timestamp'] = pd.to_datetime(
                filtered_data['ENTE_DT'].astype(str) + ' ' + filtered_data['time'],
                format='%Y%m%d %H%M%S',
                errors='coerce'
            )
            
            # 시간 단위별로 그룹화
            if time_granularity == "시간별":
                filtered_data['time_group'] = filtered_data['timestamp'].dt.floor('H')
            elif time_granularity == "일별":
                filtered_data['time_group'] = filtered_data['timestamp'].dt.date
            else:  # 주별
                filtered_data['time_group'] = filtered_data['timestamp'].dt.to_period('W')
            
            # 디버깅 정보 추가
            with st.expander("시간 그룹 정보", expanded=False):
                st.write(f"필터링된 데이터 수: {len(filtered_data)}")
                st.write(f"고유 시간 그룹 수: {filtered_data['time_group'].nunique()}")
                
            # 시간별 네트워크 생성
            temporal_networks = {}
            
            for time_group, group_data in filtered_data.groupby('time_group'):
                if network_type == "상호작용":
                    # 같은 시간, 같은 장소의 직원들
                    G = nx.Graph()
                    for location, loc_group in group_data.groupby('DR_NM'):
                        employees = loc_group['사번'].unique()
                        for i, emp1 in enumerate(employees):
                            for emp2 in employees[i+1:]:
                                G.add_edge(str(emp1), str(emp2))
                elif network_type == "이동":
                    # 이동 네트워크
                    G = nx.DiGraph()
                    for emp_id, emp_data in group_data.groupby('사번'):
                        emp_data = emp_data.sort_values('timestamp')
                        for i in range(len(emp_data) - 1):
                            loc1 = emp_data.iloc[i]['DR_NM']
                            loc2 = emp_data.iloc[i+1]['DR_NM']
                            if loc1 != loc2:
                                G.add_edge(loc1, loc2)
                else:  # 협업
                    G = nx.Graph()
                    # 간단한 협업 네트워크 (같은 장소에 있는 직원들)
                    for location, loc_group in group_data.groupby('DR_NM'):
                        employees = loc_group['사번'].unique()
                        for i, emp1 in enumerate(employees):
                            for emp2 in employees[i+1:]:
                                G.add_edge(str(emp1), str(emp2))
                
                temporal_networks[str(time_group)] = {
                    'graph': G,
                    'num_nodes': G.number_of_nodes(),
                    'num_edges': G.number_of_edges(),
                    'density': nx.density(G) if G.number_of_nodes() > 0 else 0
                }
            
            # 네트워크가 비어있는지 확인
            if not temporal_networks:
                st.info("생성된 네트워크가 없습니다. 다른 시간 단위나 네트워크 유형을 시도해보세요.")
                return None
                
            return {
                'networks': temporal_networks,
                'time_granularity': time_granularity,
                'network_type': network_type
            }
            
        except Exception as e:
            self.logger.error(f"시계열 네트워크 분석 중 오류: {e}")
            return None
    
    def analyze_activity_network(self, start_date: date, end_date: date,
                               activity_types: List[str], network_method: str) -> Optional[Dict]:
        """활동 기반 네트워크 분석"""
        try:
            # 여기서는 간단히 위치 기반으로 활동을 추정
            # 실제로는 HMM 모델 결과나 활동 분류 결과를 사용해야 함
            
            from ...data_processing import PickleManager
            pickle_manager = PickleManager()
            tag_data = pickle_manager.load_dataframe(name='tag_data')
            
            if tag_data is None or tag_data.empty:
                return None
            
            # 날짜 필터링
            start_str = start_date.strftime('%Y%m%d')
            end_str = end_date.strftime('%Y%m%d')
            
            tag_data['ENTE_DT'] = pd.to_numeric(tag_data['ENTE_DT'], errors='coerce')
            filtered_data = tag_data[
                (tag_data['ENTE_DT'] >= int(start_str)) & 
                (tag_data['ENTE_DT'] <= int(end_str))
            ].copy()
            
            if filtered_data.empty:
                return None
            
            # timestamp 생성
            # 출입시각을 6자리 문자열로 변환 (HHMMSS 형식)
            filtered_data['time'] = filtered_data['출입시각'].astype(str).str.zfill(6)
            filtered_data['timestamp'] = pd.to_datetime(
                filtered_data['ENTE_DT'].astype(str) + ' ' + filtered_data['time'],
                format='%Y%m%d %H%M%S',
                errors='coerce'
            )
            
            # 간단한 활동 분류 (위치 기반)
            filtered_data['activity'] = '업무'  # 기본값
            filtered_data.loc[filtered_data['DR_NM'].str.contains('식당|CAFETERIA', case=False, na=False), 'activity'] = '식사'
            filtered_data.loc[filtered_data['DR_NM'].str.contains('회의|MEETING', case=False, na=False), 'activity'] = '회의'
            filtered_data.loc[filtered_data['DR_NM'].str.contains('휴게|REST', case=False, na=False), 'activity'] = '휴식'
            filtered_data.loc[filtered_data['DR_GB'] == '출입게이트', 'activity'] = '이동'
            
            # 선택된 활동만 필터링
            filtered_data = filtered_data[filtered_data['activity'].isin(activity_types)]
            
            if filtered_data.empty:
                return None
            
            # 네트워크 생성
            G = nx.Graph()
            
            if network_method == "동시 활동":
                # 같은 시간, 같은 활동을 하는 직원들
                filtered_data['time_slot'] = filtered_data['timestamp'].dt.floor('30min')
                
                for (activity, time_slot), group in filtered_data.groupby(['activity', 'time_slot']):
                    employees = group['사번'].unique()
                    for i, emp1 in enumerate(employees):
                        for emp2 in employees[i+1:]:
                            if G.has_edge(str(emp1), str(emp2)):
                                G[str(emp1)][str(emp2)]['weight'] += 1
                            else:
                                G.add_edge(str(emp1), str(emp2), weight=1, activity=activity)
            
            elif network_method == "순차 활동":
                # 같은 활동을 순차적으로 하는 직원들
                for activity in activity_types:
                    activity_data = filtered_data[filtered_data['activity'] == activity]
                    for location, loc_group in activity_data.groupby('DR_NM'):
                        loc_group = loc_group.sort_values('timestamp')
                        employees = loc_group['사번'].tolist()
                        for i in range(len(employees) - 1):
                            G.add_edge(str(employees[i]), str(employees[i+1]), activity=activity)
            
            else:  # 활동 전환
                # 활동 전환 패턴이 유사한 직원들
                # 간단히 구현: 같은 활동 시퀀스를 가진 직원들
                pass
            
            # 활동별 통계
            activity_stats = filtered_data['activity'].value_counts().to_dict()
            
            return {
                'graph': G,
                'activity_stats': activity_stats,
                'num_nodes': G.number_of_nodes(),
                'num_edges': G.number_of_edges(),
                'network_method': network_method
            }
            
        except Exception as e:
            self.logger.error(f"활동 네트워크 분석 중 오류: {e}")
            return None
    
    def display_network_evolution_metrics(self, temporal_data: Dict):
        """네트워크 진화 메트릭 표시"""
        st.markdown("#### 📊 네트워크 진화 메트릭")
        
        networks = temporal_data['networks']
        
        # 시간별 메트릭 계산
        time_points = sorted(networks.keys())
        metrics = {
            'nodes': [networks[t]['num_nodes'] for t in time_points],
            'edges': [networks[t]['num_edges'] for t in time_points],
            'density': [networks[t]['density'] for t in time_points]
        }
        
        # 메트릭 시각화
        fig = make_subplots(
            rows=3, cols=1,
            subplot_titles=('노드 수 변화', '엣지 수 변화', '네트워크 밀도 변화')
        )
        
        fig.add_trace(
            go.Scatter(x=time_points, y=metrics['nodes'], mode='lines+markers'),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(x=time_points, y=metrics['edges'], mode='lines+markers'),
            row=2, col=1
        )
        
        fig.add_trace(
            go.Scatter(x=time_points, y=metrics['density'], mode='lines+markers'),
            row=3, col=1
        )
        
        fig.update_layout(height=900, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    
    def visualize_animated_network(self, temporal_data: Dict, animation_speed: int):
        """애니메이션 네트워크 시각화"""
        st.markdown("#### 🎬 네트워크 애니메이션")
        st.info("시간에 따른 네트워크 변화를 보여줍니다.")
        
        # 간단한 정적 시각화로 대체
        networks = temporal_data['networks']
        if networks:
            # 첫 번째와 마지막 네트워크 비교
            time_points = sorted(networks.keys())
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"시작 시점: {time_points[0]}")
                st.write(f"노드: {networks[time_points[0]]['num_nodes']}, 엣지: {networks[time_points[0]]['num_edges']}")
            
            with col2:
                st.write(f"종료 시점: {time_points[-1]}")
                st.write(f"노드: {networks[time_points[-1]]['num_nodes']}, 엣지: {networks[time_points[-1]]['num_edges']}")
    
    def display_temporal_patterns(self, temporal_data: Dict):
        """시간대별 패턴 분석 표시"""
        st.markdown("#### 🕐 시간대별 패턴")
        
        networks = temporal_data['networks']
        
        # 시간대별 활동 패턴
        if temporal_data['time_granularity'] == "시간별":
            # 시간대별 네트워크 크기
            hourly_stats = {}
            for time_str, network in networks.items():
                try:
                    hour = pd.to_datetime(time_str).hour
                    if hour not in hourly_stats:
                        hourly_stats[hour] = []
                    hourly_stats[hour].append(network['num_edges'])
                except:
                    pass
            
            if hourly_stats:
                avg_edges_by_hour = {h: np.mean(edges) for h, edges in hourly_stats.items()}
                
                fig = px.bar(
                    x=list(avg_edges_by_hour.keys()),
                    y=list(avg_edges_by_hour.values()),
                    labels={'x': '시간', 'y': '평균 연결 수'},
                    title='시간대별 평균 네트워크 활동'
                )
                st.plotly_chart(fig, use_container_width=True)
    
    def display_anomaly_detection(self, temporal_data: Dict):
        """이상 패턴 탐지 결과 표시"""
        st.markdown("#### 🔍 이상 패턴 탐지")
        
        networks = temporal_data['networks']
        
        # 간단한 이상치 탐지 (평균에서 2 표준편차 이상 벗어난 경우)
        edge_counts = [n['num_edges'] for n in networks.values()]
        
        if len(edge_counts) > 3:
            mean_edges = np.mean(edge_counts)
            std_edges = np.std(edge_counts)
            
            anomalies = []
            for time_point, network in networks.items():
                if abs(network['num_edges'] - mean_edges) > 2 * std_edges:
                    anomalies.append({
                        'time': time_point,
                        'edges': network['num_edges'],
                        'deviation': (network['num_edges'] - mean_edges) / std_edges
                    })
            
            if anomalies:
                st.warning(f"{len(anomalies)}개의 이상 패턴이 감지되었습니다.")
                anomaly_df = pd.DataFrame(anomalies)
                st.dataframe(anomaly_df)
            else:
                st.success("이상 패턴이 감지되지 않았습니다.")
        else:
            st.info("이상 패턴 탐지를 위한 데이터가 충분하지 않습니다.")
    
    def display_activity_statistics(self, activity_data: Dict):
        """활동 네트워크 통계 표시"""
        st.markdown("#### 📊 활동 통계")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("참여 직원 수", activity_data['num_nodes'])
        with col2:
            st.metric("활동 연결 수", activity_data['num_edges'])
        with col3:
            st.metric("네트워크 방식", activity_data['network_method'])
        
        # 활동별 분포
        if activity_data['activity_stats']:
            fig = px.pie(
                values=list(activity_data['activity_stats'].values()),
                names=list(activity_data['activity_stats'].keys()),
                title='활동 유형별 분포'
            )
            st.plotly_chart(fig, use_container_width=True)
    
    def visualize_activity_network(self, activity_data: Dict):
        """활동 네트워크 시각화"""
        st.markdown("#### 🌐 활동 네트워크")
        
        G = activity_data['graph']
        
        if G.number_of_nodes() > 0:
            # 레이아웃 계산
            pos = nx.spring_layout(G)
            
            # 엣지 그리기
            edge_trace = []
            for edge in G.edges():
                x0, y0 = pos[edge[0]]
                x1, y1 = pos[edge[1]]
                edge_trace.append(go.Scatter(
                    x=[x0, x1, None],
                    y=[y0, y1, None],
                    mode='lines',
                    line=dict(width=1, color='#888'),
                    hoverinfo='none'
                ))
            
            # 노드 그리기
            node_trace = go.Scatter(
                x=[pos[node][0] for node in G.nodes()],
                y=[pos[node][1] for node in G.nodes()],
                mode='markers+text',
                text=[str(node) for node in G.nodes()],
                textposition="top center",
                marker=dict(size=10, color='lightblue'),
                hoverinfo='text'
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
        else:
            st.info("네트워크를 시각화할 데이터가 없습니다.")
    
    def display_activity_clusters(self, activity_data: Dict):
        """활동 클러스터 분석 표시"""
        st.markdown("#### 👥 활동 클러스터")
        
        G = activity_data['graph']
        
        if G.number_of_nodes() > 0:
            # 연결된 컴포넌트 찾기
            components = list(nx.connected_components(G))
            
            st.write(f"발견된 클러스터 수: {len(components)}")
            
            # 클러스터 크기 분포
            cluster_sizes = [len(c) for c in components]
            
            fig = px.histogram(
                x=cluster_sizes,
                nbins=20,
                labels={'x': '클러스터 크기', 'y': '개수'},
                title='클러스터 크기 분포'
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # 가장 큰 클러스터 정보
            if components:
                largest_cluster = max(components, key=len)
                st.write(f"가장 큰 클러스터: {len(largest_cluster)}명")
    
    def display_activity_efficiency(self, activity_data: Dict):
        """활동 효율성 분석 표시"""
        st.markdown("#### 📈 활동 효율성")
        
        # 간단한 효율성 메트릭
        if activity_data['num_nodes'] > 0:
            avg_connections = (2 * activity_data['num_edges']) / activity_data['num_nodes']
            st.metric("평균 연결 수", f"{avg_connections:.2f}")
            
            # 네트워크 밀도
            G = activity_data['graph']
            if G.number_of_nodes() > 1:
                density = nx.density(G)
                st.metric("네트워크 밀도", f"{density:.3f}")
                
                # 효율성 평가
                if density > 0.5:
                    st.success("높은 협업 밀도를 보이고 있습니다.")
                elif density > 0.2:
                    st.info("적절한 협업 수준을 유지하고 있습니다.")
                else:
                    st.warning("협업 밀도가 낮습니다. 팀워크 향상이 필요할 수 있습니다.")