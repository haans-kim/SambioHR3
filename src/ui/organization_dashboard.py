"""
조직별 대시보드 UI 모듈
센터, 그룹, 팀별 통합 현황을 카드 기반 레이아웃으로 표시
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
import logging

from ..database import get_database_manager, get_pickle_manager

logger = logging.getLogger(__name__)


class OrganizationDashboard:
    """조직별 대시보드 클래스"""
    
    def __init__(self):
        self.db_manager = get_database_manager()
        self.pickle_manager = get_pickle_manager()
        
    def render(self):
        """대시보드 렌더링"""
        st.title("조직분석 통합 관리 시스템")
        
        # 탭 생성
        tab1, tab2, tab3 = st.tabs(["전체 개요", "팀별 분석", "그룹별 분석"])
        
        with tab1:
            self.render_center_overview()
            
        with tab2:
            self.render_team_analysis()
            
        with tab3:
            self.render_group_analysis()
    
    def render_center_overview(self):
        """전체 센터 개요 화면"""
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            # 날짜 선택
            selected_date = st.date_input(
                "분석 날짜",
                value=date.today() - timedelta(days=1),
                max_value=date.today()
            )
        
        # 전체 통계 조회
        total_stats = self.get_total_statistics(selected_date)
        
        if total_stats:
            # 상단 요약 카드
            st.markdown("### 조직별 분석")
            st.markdown(f"실시간 업무패턴 분석 및 근무 추정시간 모니터링")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric(
                    label="총 분석 인원",
                    value=f"{total_stats['analyzed_employees']:,}"
                )
            with col2:
                st.metric(
                    label="평균 근무율",
                    value=f"{total_stats['avg_efficiency']:.1f}%",
                    delta=f"{total_stats['efficiency_change']:.1f}%" if total_stats['efficiency_change'] else None
                )
            
            # 센터별 현황
            st.markdown("### 전체 현황")
            center_data = self.get_center_summary(selected_date)
            
            if center_data:
                # 직급별 그리드 표시
                self.render_grade_grid(center_data, "center")
            else:
                st.info("선택한 날짜의 데이터가 없습니다.")
                
            # 하단 요약 카드
            self.render_summary_cards()
    
    def render_team_analysis(self):
        """팀별 분석 화면"""
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            selected_date = st.date_input(
                "분석 날짜",
                value=date.today() - timedelta(days=1),
                max_value=date.today(),
                key="team_date"
            )
        
        with col2:
            # 센터 선택
            centers = self.get_center_list()
            if centers:
                selected_center = st.selectbox("센터 선택", centers)
            else:
                st.error("조직 데이터를 찾을 수 없습니다. 데이터 로드를 먼저 실행해주세요.")
                selected_center = None
        
        # 팀별 통계
        if selected_center:
            team_stats = self.get_team_statistics(selected_date, selected_center)
            
            if team_stats:
                # 상단 요약
                st.markdown(f"### {selected_center} 현황")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(
                        label="총 분석 인원",
                        value=f"{team_stats['total_employees']:,}"
                    )
                with col2:
                    st.metric(
                        label="평균 근무율",
                        value=f"{team_stats['avg_efficiency']:.1f}%"
                    )
                
                # 팀별 카드 그리드
                st.markdown(f"### {selected_center} 현황")
                team_data = self.get_team_summary(selected_date, selected_center)
                
                if team_data:
                    self.render_team_cards(team_data)
                else:
                    st.info("선택한 센터의 데이터가 없습니다.")
    
    def render_group_analysis(self):
        """그룹별 분석 화면"""
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            selected_date = st.date_input(
                "분석 날짜",
                value=date.today() - timedelta(days=1),
                max_value=date.today(),
                key="group_date"
            )
        
        with col2:
            # 센터 선택
            centers = self.get_center_list()
            if centers:
                selected_center = st.selectbox("센터 선택", centers, key="group_center")
            else:
                st.error("조직 데이터를 찾을 수 없습니다. 데이터 로드를 먼저 실행해주세요.")
                selected_center = None
        
        # 그룹별 통계
        if selected_center:
            group_stats = self.get_group_statistics(selected_date, selected_center)
            
            if group_stats:
                # 상단 요약
                st.markdown(f"### {selected_center} 현황")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(
                        label="총 분석 인원",
                        value=f"{group_stats['total_employees']:,}"
                    )
                with col2:
                    st.metric(
                        label="평균 근무율",
                        value=f"{group_stats['avg_efficiency']:.1f}%"
                    )
                
                # 그룹별 카드 그리드
                st.markdown(f"### {selected_center} 현황")
                group_data = self.get_group_summary(selected_date, selected_center)
                
                if group_data:
                    self.render_group_cards(group_data)
                else:
                    st.info("선택한 센터의 데이터가 없습니다.")
    
    def render_grade_grid(self, data: pd.DataFrame, level: str):
        """직급별 그리드 렌더링"""
        # 직급 순서 정의
        grade_order = ['Lv.4', 'Lv.3', 'Lv.2', 'Lv.1']
        grade_mapping = {'1': 'Lv.1', '2': 'Lv.2', '3': 'Lv.3', '4': 'Lv.4'}
        
        # 직급별로 그룹화
        grade_groups = {}
        for grade in grade_order:
            grade_groups[grade] = []
        
        # 센터별 데이터를 직급별로 분류
        centers = data['center_name'].unique()
        
        for center in centers:
            center_data = data[data['center_name'] == center]
            
            # 각 직급별 효율성 계산
            for grade_num, grade_label in grade_mapping.items():
                grade_data = center_data[center_data['job_grade'] == grade_num]
                
                if not grade_data.empty:
                    efficiency = grade_data['avg_efficiency_ratio'].iloc[0]
                    color = self.get_efficiency_color(efficiency)
                    trend = self.get_efficiency_trend(efficiency, 0)  # TODO: 이전 날짜 대비 계산
                    
                    grade_groups[grade_label].append({
                        'name': center,
                        'efficiency': efficiency,
                        'color': color,
                        'trend': trend
                    })
        
        # 직급별 행 렌더링
        for grade in grade_order:
            if grade_groups[grade]:
                cols = st.columns([1] + [2] * len(centers))
                
                # 직급 라벨
                with cols[0]:
                    st.markdown(f"**{grade}**")
                
                # 각 센터의 효율성 표시
                for i, center_info in enumerate(grade_groups[grade]):
                    with cols[i + 1]:
                        self.render_efficiency_cell(
                            center_info['efficiency'],
                            center_info['color'],
                            center_info['trend']
                        )
    
    def render_efficiency_cell(self, efficiency: float, color: str, trend: str):
        """효율성 셀 렌더링"""
        # 색상 맵핑
        color_map = {
            'green': '#4CAF50',
            'blue': '#2196F3',
            'red': '#F44336'
        }
        
        # 트렌드 심볼
        trend_symbol = {
            'up': '▲',
            'down': '▼',
            'stable': '●'
        }
        
        # HTML로 스타일 적용
        cell_color = color_map.get(color, '#999999')
        symbol = trend_symbol.get(trend, '')
        
        st.markdown(
            f"""
            <div style="
                background-color: {cell_color}20;
                border: 2px solid {cell_color};
                border-radius: 8px;
                padding: 10px;
                text-align: center;
            ">
                <span style="font-size: 20px; font-weight: bold; color: {cell_color};">
                    {efficiency:.0f}%
                </span>
                <span style="color: {cell_color};">
                    {symbol}
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    def render_team_cards(self, teams: pd.DataFrame):
        """팀별 카드 렌더링"""
        # 2x4 그리드로 표시
        for i in range(0, len(teams), 4):
            cols = st.columns(4)
            
            for j in range(4):
                if i + j < len(teams):
                    team = teams.iloc[i + j]
                    
                    with cols[j]:
                        color = self.get_efficiency_color(team['avg_efficiency_ratio'])
                        self.render_team_card(
                            team['team_name'],
                            team['avg_efficiency_ratio'],
                            team['analyzed_employees'],
                            color
                        )
    
    def render_team_card(self, name: str, efficiency: float, employees: int, color: str):
        """개별 팀 카드 렌더링"""
        color_map = {
            'green': '#4CAF50',
            'blue': '#2196F3', 
            'red': '#F44336'
        }
        
        bg_color = color_map.get(color, '#999999')
        
        st.markdown(
            f"""
            <div style="
                border: 2px solid {bg_color};
                border-radius: 15px;
                padding: 20px;
                margin: 5px;
                background-color: {bg_color}10;
            ">
                <h4 style="margin: 0; color: #333;">{name}</h4>
                <div style="margin: 10px 0;">
                    <span style="font-size: 24px; font-weight: bold; color: {bg_color};">
                        {efficiency:.1f}%
                    </span>
                    <br>
                    <span style="color: #666;">평균 효율성</span>
                </div>
                <div style="
                    background-color: {bg_color};
                    height: 8px;
                    border-radius: 4px;
                    margin: 10px 0;
                "></div>
                <div style="text-align: center; color: #666;">
                    <span style="font-size: 18px; font-weight: bold; color: #333;">
                        {employees}명
                    </span>
                    <br>
                    <span>팀원 수</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    def render_group_cards(self, groups: pd.DataFrame):
        """그룹별 카드 렌더링"""
        # 2열로 표시
        for i in range(0, len(groups), 2):
            cols = st.columns(2)
            
            for j in range(2):
                if i + j < len(groups):
                    group = groups.iloc[i + j]
                    
                    with cols[j]:
                        color = self.get_efficiency_color(group['avg_efficiency_ratio'])
                        self.render_group_card(
                            group['group_name'],
                            group['avg_efficiency_ratio'],
                            group['analyzed_employees'],
                            color
                        )
    
    def render_group_card(self, name: str, efficiency: float, employees: int, color: str):
        """개별 그룹 카드 렌더링"""
        # 팀 카드와 동일한 스타일 사용
        self.render_team_card(name, efficiency, employees, color)
    
    def render_summary_cards(self):
        """하단 요약 카드 렌더링"""
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(
                """
                <div style="
                    border-left: 5px solid #F44336;
                    padding: 20px;
                    background-color: #F4433610;
                    border-radius: 10px;
                ">
                    <h4 style="color: #F44336; margin: 0;">즉시 개입 필요</h4>
                    <p style="margin: 10px 0;">
                        실각한 과로 상태입니다. 업무량 재분배 및 인력 충원이 시급합니다.
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )
        
        with col2:
            st.markdown(
                """
                <div style="
                    border-left: 5px solid #4CAF50;
                    padding: 20px;
                    background-color: #4CAF5010;
                    border-radius: 10px;
                ">
                    <h4 style="color: #4CAF50; margin: 0;">모범 사례</h4>
                    <p style="margin: 10px 0;">
                        최적 범위의 근무율과 높은 효율성을 보이는 조직/직급입니다.
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )
        
        with col3:
            st.markdown(
                """
                <div style="
                    border-left: 5px solid #2196F3;
                    padding: 20px;
                    background-color: #2196F310;
                    border-radius: 10px;
                ">
                    <h4 style="color: #2196F3; margin: 0;">효율성 개선 대상</h4>
                    <p style="margin: 10px 0;">
                        Lv.4 직급의 실근무율이 낮습니다. [의사결정 프로세스 개선] 및 [관리 업무 간소화]가 필요합니다.
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )
    
    def get_efficiency_color(self, efficiency: float) -> str:
        """효율성에 따른 색상 결정"""
        if efficiency >= 90:
            return 'green'
        elif efficiency >= 80:
            return 'blue'
        else:
            return 'red'
    
    def get_efficiency_trend(self, current: float, previous: float) -> str:
        """효율성 트렌드 결정"""
        if current > previous + 1:
            return 'up'
        elif current < previous - 1:
            return 'down'
        else:
            return 'stable'
    
    # 데이터베이스 조회 메서드들
    def get_total_statistics(self, analysis_date: date) -> Optional[Dict]:
        """전체 통계 조회"""
        query = """
        SELECT 
            COUNT(DISTINCT employee_id) as analyzed_employees,
            ROUND(AVG(efficiency_ratio), 1) as avg_efficiency,
            0 as efficiency_change
        FROM daily_analysis_results
        WHERE analysis_date = :analysis_date
        """
        
        result = self.db_manager.execute_query(query, {'analysis_date': analysis_date.isoformat()})
        return result[0] if result else None
    
    def get_center_summary(self, analysis_date: date) -> Optional[pd.DataFrame]:
        """센터별 직급별 요약 조회"""
        query = """
        SELECT 
            center_id,
            center_name,
            job_grade,
            COUNT(DISTINCT employee_id) as employee_count,
            ROUND(AVG(efficiency_ratio), 1) as avg_efficiency_ratio
        FROM daily_analysis_results
        WHERE analysis_date = :analysis_date
        GROUP BY center_id, center_name, job_grade
        ORDER BY center_name, job_grade
        """
        
        result = self.db_manager.execute_query(query, {'analysis_date': analysis_date.isoformat()})
        return pd.DataFrame(result) if result else None
    
    def get_team_statistics(self, analysis_date: date, center: str) -> Optional[Dict]:
        """팀별 통계 조회"""
        query = """
        SELECT 
            COUNT(DISTINCT employee_id) as total_employees,
            ROUND(AVG(efficiency_ratio), 1) as avg_efficiency
        FROM daily_analysis_results
        WHERE analysis_date = :analysis_date
        AND center_name = :center
        """
        
        result = self.db_manager.execute_query(
            query, 
            {'analysis_date': analysis_date.isoformat(), 'center': center}
        )
        return result[0] if result else None
    
    def get_team_summary(self, analysis_date: date, center: str) -> Optional[pd.DataFrame]:
        """팀별 요약 조회"""
        query = """
        SELECT 
            team_id,
            team_name,
            COUNT(DISTINCT employee_id) as analyzed_employees,
            ROUND(AVG(efficiency_ratio), 1) as avg_efficiency_ratio
        FROM daily_analysis_results
        WHERE analysis_date = :analysis_date
        AND center_name = :center
        GROUP BY team_id, team_name
        ORDER BY avg_efficiency_ratio DESC
        """
        
        result = self.db_manager.execute_query(
            query, 
            {'analysis_date': analysis_date.isoformat(), 'center': center}
        )
        return pd.DataFrame(result) if result else None
    
    def get_group_statistics(self, analysis_date: date, center: str) -> Optional[Dict]:
        """그룹별 통계 조회"""
        query = """
        SELECT 
            COUNT(DISTINCT employee_id) as total_employees,
            ROUND(AVG(efficiency_ratio), 1) as avg_efficiency
        FROM daily_analysis_results
        WHERE analysis_date = :analysis_date
        AND center_name = :center
        """
        
        result = self.db_manager.execute_query(
            query, 
            {'analysis_date': analysis_date.isoformat(), 'center': center}
        )
        return result[0] if result else None
    
    def get_group_summary(self, analysis_date: date, center: str) -> Optional[pd.DataFrame]:
        """그룹별 요약 조회"""
        query = """
        SELECT 
            group_id,
            group_name,
            COUNT(DISTINCT employee_id) as analyzed_employees,
            ROUND(AVG(efficiency_ratio), 1) as avg_efficiency_ratio
        FROM daily_analysis_results
        WHERE analysis_date = :analysis_date
        AND center_name = :center
        GROUP BY group_id, group_name
        ORDER BY avg_efficiency_ratio DESC
        """
        
        result = self.db_manager.execute_query(
            query, 
            {'analysis_date': analysis_date.isoformat(), 'center': center}
        )
        return pd.DataFrame(result) if result else None
    
    def get_center_list(self) -> List[str]:
        """센터 목록 조회"""
        try:
            # pickle 데이터에서 조직 정보 가져오기
            org_data = self.pickle_manager.load_dataframe('organization_data')
            if org_data is None or org_data.empty:
                logger.warning("organization_data를 찾을 수 없습니다. organization 시도")
                org_data = self.pickle_manager.load_dataframe('organization')
                if org_data is None or org_data.empty:
                    logger.warning("organization도 찾을 수 없습니다")
                    return []
            
            # 센터 목록 추출
            if '센터' in org_data.columns:
                centers = org_data['센터'].dropna().unique().tolist()
                return sorted(centers)
            elif 'center' in org_data.columns:
                centers = org_data['center'].dropna().unique().tolist()
                return sorted(centers)
            else:
                logger.warning("센터 컬럼을 찾을 수 없습니다")
                return []
        except Exception as e:
            logger.error(f"센터 목록 조회 오류: {e}")
            # DB에서 시도
            query = """
            SELECT DISTINCT center_name
            FROM daily_analysis_results
            WHERE center_name IS NOT NULL
            ORDER BY center_name
            """
            
            result = self.db_manager.execute_query(query)
            return [row['center_name'] for row in result] if result else []