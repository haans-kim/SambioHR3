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
import time

from ..database import get_database_manager, get_pickle_manager
from ..analysis.individual_analyzer import IndividualAnalyzer
from ..analysis.organization_analyzer import OrganizationAnalyzer

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
            # 날짜 선택 (데이터가 있는 6월로 기본값 설정)
            default_date = date(2025, 6, 15)
            selected_date = st.date_input(
                "분석 날짜",
                value=default_date,
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
                analyzed_employees = total_stats.get('analyzed_employees', 0) or 0
                st.metric(
                    label="총 분석 인원",
                    value=f"{int(analyzed_employees):,}" if analyzed_employees is not None else "0"
                )
            with col2:
                avg_efficiency = total_stats.get('avg_efficiency', 0) or 0
                efficiency_change = total_stats.get('efficiency_change')
                st.metric(
                    label="평균 근무율",
                    value=f"{float(avg_efficiency):.1f}%" if avg_efficiency is not None else "0.0%",
                    delta=f"{float(efficiency_change):.1f}%" if efficiency_change is not None else None
                )
            
            # 센터별 현황
            st.markdown("### 전체 현황")
            center_data = self.get_center_summary(selected_date)
            
            if center_data is not None and not center_data.empty:
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
            # 데이터가 있는 6월 날짜를 기본값으로 설정
            default_date = date(2025, 6, 15)
            selected_date = st.date_input(
                "분석 날짜",
                value=default_date,
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
            
            # 상단 요약 (team_stats가 없어도 표시)
            st.markdown(f"### {selected_center} 현황")
            
            if team_stats:
                col1, col2 = st.columns(2)
                with col1:
                    total_employees = team_stats.get('total_employees', 0) or 0
                    st.metric(
                        label="총 분석 인원",
                        value=f"{int(total_employees):,}" if total_employees is not None else "0"
                    )
                with col2:
                    avg_efficiency = team_stats.get('avg_efficiency', 0) or 0
                    st.metric(
                        label="평균 근무율",
                        value=f"{float(avg_efficiency):.1f}%" if avg_efficiency is not None else "0.0%"
                    )
            else:
                st.info("데이터베이스에 저장된 통계가 없습니다. 아래 버튼으로 실시간 분석을 실행하세요.")
            
            # 팀별 카드 그리드
            st.markdown(f"### {selected_center} 팀별 현황")
            team_data = self.get_team_summary(selected_date, selected_center)
            
            if team_data is not None and not team_data.empty:
                self.render_team_cards(team_data)
            else:
                st.info("팀별 데이터가 없습니다.")
            
            # 상세 분석 실행 버튼 추가 (항상 표시)
            st.markdown("---")
            st.markdown("### 실시간 분석")
            
            # 고속 배치 처리 자동 사용
            st.info("🚀 고속 배치 처리 모드 (Process 기반 병렬 처리)")
            
            # 워커 수 선택
            num_workers = st.slider("병렬 워커 수", 1, 8, 4, key="num_workers_simple")
            
            # 분석 실행 버튼
            if st.button("🔍 상세 분석 실행", type="primary", use_container_width=True):
                # 고속 배치 처리로 실행
                self.run_detailed_analysis_with_timing(selected_date, selected_center, True, "fast", num_workers)
    
    def render_group_analysis(self):
        """그룹별 분석 화면"""
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            # 데이터가 있는 6월 날짜를 기본값으로 설정
            default_date = date(2025, 6, 15)
            selected_date = st.date_input(
                "분석 날짜",
                value=default_date,
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
                    total_employees = group_stats.get('total_employees', 0) or 0
                    st.metric(
                        label="총 분석 인원",
                        value=f"{int(total_employees):,}" if total_employees is not None else "0"
                    )
                with col2:
                    avg_efficiency = group_stats.get('avg_efficiency', 0) or 0
                    st.metric(
                        label="평균 근무율",
                        value=f"{float(avg_efficiency):.1f}%" if avg_efficiency is not None else "0.0%"
                    )
                
                # 그룹별 카드 그리드
                st.markdown(f"### {selected_center} 현황")
                group_data = self.get_group_summary(selected_date, selected_center)
                
                if group_data is not None and not group_data.empty:
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
                    efficiency = efficiency if efficiency is not None else 0
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
        
        # Handle None efficiency
        efficiency_text = f"{efficiency:.0f}%" if efficiency is not None else "0%"
        
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
                    {efficiency_text}
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
                        efficiency = team['avg_efficiency_ratio'] if team['avg_efficiency_ratio'] is not None else 0
                        employees = team['analyzed_employees'] if team['analyzed_employees'] is not None else 0
                        color = self.get_efficiency_color(efficiency)
                        self.render_team_card(
                            team['team_name'],
                            efficiency,
                            employees,
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
        
        # Handle None efficiency
        efficiency_text = f"{efficiency:.1f}%" if efficiency is not None else "0.0%"
        
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
                        {efficiency_text}
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
                        efficiency = group['avg_efficiency_ratio'] if group['avg_efficiency_ratio'] is not None else 0
                        employees = group['analyzed_employees'] if group['analyzed_employees'] is not None else 0
                        color = self.get_efficiency_color(efficiency)
                        self.render_group_card(
                            group['group_name'],
                            efficiency,
                            employees,
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
        if efficiency is None:
            efficiency = 0
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
    
    def run_detailed_analysis_with_timing(self, selected_date: date, selected_center: str, use_batch: bool = False, batch_type: str = None, num_workers: int = 4):
        """상세 분석 실행 및 소요시간 측정"""
        st.markdown("### 상세 분석 실행 중...")
        
        # 분석기 초기화
        individual_analyzer = IndividualAnalyzer(self.db_manager, None)
        
        # 조직 데이터에서 해당 센터의 직원 목록 가져오기
        org_df = self.pickle_manager.load_dataframe('organization_data')
        center_employees = org_df[org_df['센터'] == selected_center]
        
        # 팀별로 그룹화
        teams = center_employees['팀'].dropna().unique()
        
        st.write(f"분석 대상: {len(teams)}개 팀, {len(center_employees)}명")
        
        # 배치 처리 사용 시
        if use_batch and batch_type:
            st.info(f"배치 처리 모드: {batch_type}")
            
            if batch_type == "simple":
                # SimpleBatchProcessor 사용
                try:
                    from ..analysis.simple_batch_processor import SimpleBatchProcessor
                    
                    # 매개변수로 받은 num_workers 사용
                    st.info(f"병렬 워커 수: {num_workers}개")
                    
                    with st.spinner("배치 프로세서 초기화 중..."):
                        batch_processor = SimpleBatchProcessor(num_workers=num_workers)
                except Exception as e:
                    st.error(f"SimpleBatchProcessor 초기화 실패: {str(e)}")
                    logger.error(f"SimpleBatchProcessor 초기화 실패: {e}", exc_info=True)
                    return
                
                # 직원 ID 리스트 생성
                employee_ids = center_employees['사번'].astype(str).tolist()
                
                st.info(f"분석 대상: {len(employee_ids)}명")
                
                try:
                    # 진행 상황 표시를 위한 placeholder
                    progress_placeholder = st.empty()
                    status_placeholder = st.empty()
                    
                    # 배치 분석 실행 및 시간 측정
                    start_time = time.time()
                    
                    progress_placeholder.progress(0.3)
                    status_placeholder.info(f"📊 {len(employee_ids)}명 분석 시작...")
                    
                    batch_results = batch_processor.batch_analyze_employees(employee_ids, selected_date)
                    
                    progress_placeholder.progress(0.7)
                    status_placeholder.info(f"💾 데이터베이스에 저장 중...")
                    
                    # 결과 저장
                    saved_count = batch_processor.save_results_to_db(batch_results)
                    
                    total_time = time.time() - start_time
                    
                    progress_placeholder.progress(1.0)
                    status_placeholder.success(f"✅ 분석 완료! {len(batch_results)}명 처리, {saved_count}건 저장")
                except Exception as e:
                    st.error(f"배치 분석 실패: {str(e)}")
                    logger.error(f"배치 분석 실패: {e}", exc_info=True)
                    return
                
                # 결과 표시
                st.success(f"✅ 배치 분석 완료!")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("총 분석 인원", f"{len(batch_results)}명")
                with col2:
                    st.metric("DB 저장", f"{saved_count}건")
                with col3:
                    st.metric("총 소요시간", f"{total_time:.1f}초")
                with col4:
                    st.metric("처리 속도", f"{len(batch_results)/total_time:.1f}명/초")
                
                # 결과 DataFrame 생성 및 표시
                st.markdown("### 📊 분석 결과 상세")
                
                # 디버깅 정보
                st.write(f"분석 결과: {len(batch_results)}건")
                
                result_list = []
                success_count = 0
                no_data_count = 0
                error_count = 0
                
                for result in batch_results:
                    status = result.get('status', 'unknown')
                    
                    # 직원 정보 매칭
                    emp_info = center_employees[center_employees['사번'].astype(str) == result['employee_id']]
                    if not emp_info.empty:
                        emp_info = emp_info.iloc[0]
                        emp_name = str(emp_info.get('성명', ''))
                        emp_team = str(emp_info.get('팀', ''))
                        emp_grade = str(emp_info.get('직급명', ''))
                    else:
                        emp_name = ''
                        emp_team = ''
                        emp_grade = ''
                    
                    if status == 'success':
                        success_count += 1
                        result_list.append({
                            '팀': emp_team,
                            '사번': result['employee_id'],
                            '성명': emp_name,
                            '직급': emp_grade,
                            '근무시간': f"{result['work_time_analysis']['actual_work_hours']:.1f}시간",
                            '효율성': f"{result['work_time_analysis']['efficiency_ratio']:.1f}%",
                            '태그수': result.get('tag_count', 0),
                            '상태': '✅ 성공'
                        })
                    elif status == 'no_data':
                        no_data_count += 1
                        result_list.append({
                            '팀': emp_team,
                            '사번': result['employee_id'],
                            '성명': emp_name,
                            '직급': emp_grade,
                            '근무시간': '-',
                            '효율성': '-',
                            '태그수': 0,
                            '상태': '⚠️ 데이터 없음'
                        })
                    else:
                        error_count += 1
                        result_list.append({
                            '팀': emp_team,
                            '사번': result['employee_id'],
                            '성명': emp_name,
                            '직급': emp_grade,
                            '근무시간': '-',
                            '효율성': '-',
                            '태그수': 0,
                            '상태': f'❌ 오류: {result.get("error", "알 수 없음")[:20]}'
                        })
                
                # 상태 요약
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("✅ 성공", f"{success_count}명")
                with col2:
                    st.metric("⚠️ 데이터 없음", f"{no_data_count}명")
                with col3:
                    st.metric("❌ 오류", f"{error_count}명")
                
                # 결과 테이블 표시
                if result_list:
                    result_df = pd.DataFrame(result_list)
                    
                    # 정렬 (팀 > 사번)
                    result_df = result_df.sort_values(['팀', '사번'])
                    
                    # Streamlit 버전에 따라 hide_index 파라미터 처리
                    try:
                        st.dataframe(
                            result_df,
                            use_container_width=True,
                            height=600,
                            hide_index=True
                        )
                    except TypeError:
                        # 구버전 Streamlit은 hide_index를 지원하지 않음
                        st.dataframe(
                            result_df,
                            use_container_width=True,
                            height=600
                        )
                    
                    # CSV 다운로드
                    csv = result_df.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="📥 결과 다운로드 (CSV)",
                        data=csv,
                        file_name=f"batch_analysis_{selected_center}_{selected_date}.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("분석 결과가 없습니다.")
            
            elif batch_type == "fast":
                # FastBatchProcessor 사용  
                try:
                    from ..analysis.fast_batch_processor import FastBatchProcessor
                    
                    # 매개변수로 받은 num_workers 사용
                    st.info(f"🚀 Process 기반 병렬 워커: {num_workers}개")
                    
                    with st.spinner("고속 배치 프로세서 초기화 중..."):
                        batch_processor = FastBatchProcessor(num_workers=num_workers)
                except Exception as e:
                    st.error(f"FastBatchProcessor 초기화 실패: {str(e)}")
                    logger.error(f"FastBatchProcessor 초기화 실패: {e}", exc_info=True)
                    return
                
                # 직원 ID 리스트 생성
                employee_ids = center_employees['사번'].astype(str).tolist()
                
                st.info(f"분석 대상: {len(employee_ids)}명")
                
                try:
                    # 진행 상황 표시
                    progress_placeholder = st.empty()
                    status_placeholder = st.empty()
                    
                    # 배치 분석 실행
                    start_time = time.time()
                    
                    progress_placeholder.progress(0.3)
                    status_placeholder.info(f"🚀 {len(employee_ids)}명 고속 분석 시작...")
                    
                    batch_results = batch_processor.batch_analyze_employees(employee_ids, selected_date)
                    
                    progress_placeholder.progress(0.7)
                    status_placeholder.info(f"💾 데이터베이스에 저장 중...")
                    
                    # 결과 저장
                    saved_count = batch_processor.save_results_to_db(batch_results)
                    
                    total_time = time.time() - start_time
                    
                    progress_placeholder.progress(1.0)
                    status_placeholder.success(f"✅ 고속 분석 완료! {len(batch_results)}명 처리, {saved_count}건 저장")
                except Exception as e:
                    st.error(f"고속 배치 분석 실패: {str(e)}")
                    logger.error(f"고속 배치 분석 실패: {e}", exc_info=True)
                    return
                
                # 결과 표시
                st.success(f"✅ 고속 배치 분석 완료!")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("총 분석 인원", f"{len(batch_results)}명")
                with col2:
                    st.metric("DB 저장", f"{saved_count}건")
                with col3:
                    st.metric("총 소요시간", f"{total_time:.1f}초")
                with col4:
                    st.metric("처리 속도", f"{len(batch_results)/total_time:.1f}명/초")
                
                # 결과 DataFrame 생성 및 표시
                st.markdown("### 📊 분석 결과 상세")
                
                result_list = []
                for result in batch_results:
                    status = result.get('status', 'unknown')
                    
                    # 직원 정보 매칭
                    emp_info = center_employees[center_employees['사번'].astype(str) == result['employee_id']]
                    if not emp_info.empty:
                        emp_info = emp_info.iloc[0]
                        emp_name = str(emp_info.get('성명', ''))
                        emp_team = str(emp_info.get('팀', ''))
                        emp_grade = str(emp_info.get('직급명', ''))
                    else:
                        emp_name = ''
                        emp_team = ''
                        emp_grade = ''
                    
                    if status == 'success':
                        result_list.append({
                            '팀': emp_team,
                            '사번': result['employee_id'],
                            '성명': emp_name,
                            '직급': emp_grade,
                            '근무시간': f"{result['work_time_analysis']['actual_work_hours']:.1f}시간",
                            '효율성': f"{result['work_time_analysis']['efficiency_ratio']:.1f}%",
                            '태그수': result.get('tag_count', 0),
                            '상태': '✅ 성공'
                        })
                    elif status == 'no_data':
                        result_list.append({
                            '팀': emp_team,
                            '사번': result['employee_id'],
                            '성명': emp_name,
                            '직급': emp_grade,
                            '근무시간': '-',
                            '효율성': '-',
                            '태그수': 0,
                            '상태': '⚠️ 데이터 없음'
                        })
                    else:
                        result_list.append({
                            '팀': emp_team,
                            '사번': result['employee_id'],
                            '성명': emp_name,
                            '직급': emp_grade,
                            '근무시간': '-',
                            '효율성': '-',
                            '태그수': 0,
                            '상태': '❌ 오류'
                        })
                
                if result_list:
                    result_df = pd.DataFrame(result_list)
                    result_df = result_df.sort_values(['팀', '사번'])
                    
                    try:
                        st.dataframe(
                            result_df,
                            use_container_width=True,
                            height=600,
                            hide_index=True
                        )
                    except TypeError:
                        st.dataframe(
                            result_df,
                            use_container_width=True,
                            height=600
                        )
                    
                    # CSV 다운로드
                    csv = result_df.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="📥 결과 다운로드 (CSV)",
                        data=csv,
                        file_name=f"fast_batch_analysis_{selected_center}_{selected_date}.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("분석 결과가 없습니다.")
                
            else:  # optimized
                # OptimizedBatchProcessor 사용
                from ..analysis.optimized_batch_processor import OptimizedBatchProcessor
                
                # 설정 옵션
                col1, col2, col3 = st.columns(3)
                with col1:
                    db_type = st.selectbox("DB 타입", ["sqlite", "postgresql", "hybrid"], key="db_type")
                with col2:
                    cache_type = st.selectbox("캐시 타입", ["memory", "redis", "shared_memory"], key="cache_type")
                with col3:
                    num_workers = st.slider("병렬 워커 수", 1, 12, 8, key="opt_workers")
                
                try:
                    batch_processor = OptimizedBatchProcessor(
                        db_type=db_type,
                        cache_type=cache_type,
                        num_workers=num_workers
                    )
                    
                    # 배치 분석 실행
                    start_time = time.time()
                    results = batch_processor.batch_analyze_optimized(selected_date)
                    total_time = time.time() - start_time
                    
                    # 결과 표시
                    st.success(f"✅ 최적화 배치 분석 완료!")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("총 분석 인원", f"{len(results)}명")
                    with col2:
                        st.metric("총 소요시간", f"{total_time:.1f}초")
                    with col3:
                        st.metric("처리 속도", f"{len(results)/total_time:.1f}명/초")
                    
                    # 결과 테이블
                    if results:
                        result_df = pd.DataFrame(results)
                        st.dataframe(result_df, use_container_width=True, height=400)
                        
                except Exception as e:
                    st.error(f"최적화 배치 처리 실패: {str(e)}")
                    st.info("PostgreSQL 또는 Redis가 설치되지 않은 경우 'sqlite'와 'memory' 옵션을 사용하세요.")
            
            # 배치 처리 완료 - return 제거하여 UI가 유지되도록 함
        
        # 기존 개별 처리 방식 (배치 처리 미사용 시에만 실행)
        elif not use_batch:
            # 진행률 표시
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # 결과 저장
            results = []
            
            # 날짜 범위 설정
            start_date = datetime.combine(selected_date, datetime.min.time())
            end_date = datetime.combine(selected_date, datetime.max.time())
            
            total_employees = len(center_employees)
            processed = 0
            
            # 팀별로 처리
            for team in teams:
                team_employees = center_employees[center_employees['팀'] == team]
                team_results = []
                
                for idx, row in team_employees.iterrows():
                    emp_id = row['사번']
                    emp_name = row['성명']
                    
                    status_text.text(f"분석 중: {team} - {emp_name} ({processed+1}/{total_employees})")
                    
                    # 개인별 분석 실행 및 시간 측정
                    start_time = time.time()
                    try:
                        analysis_result = individual_analyzer.analyze_individual(
                            str(emp_id), start_date, end_date
                        )
                        elapsed_time = time.time() - start_time
                        
                        # 결과 저장 (None 값 처리)
                        work_hours = analysis_result.get('work_time_analysis', {}).get('actual_work_hours', 0) or 0
                        efficiency = analysis_result.get('efficiency_analysis', {}).get('work_efficiency', 0) or 0
                        
                        team_results.append({
                            '팀': str(team) if team is not None else '',
                            '사번': str(emp_id) if emp_id is not None else '',
                            '성명': str(emp_name) if emp_name is not None else '',
                            '직급': str(row.get('직급명', '')) if row.get('직급명') is not None else '',
                            '근무시간': f"{float(work_hours):.1f}시간" if work_hours is not None else "0.0시간",
                            '효율성': f"{float(efficiency):.1f}%" if efficiency is not None else "0.0%",
                            '분석시간': f"{elapsed_time:.3f}초",
                            '상태': '성공'
                        })
                        
                    except Exception as e:
                        elapsed_time = time.time() - start_time
                        team_results.append({
                            '팀': str(team) if team is not None else '',
                            '사번': str(emp_id) if emp_id is not None else '',
                            '성명': str(emp_name) if emp_name is not None else '',
                            '직급': str(row.get('직급명', '')) if row.get('직급명') is not None else '',
                            '근무시간': '-',
                            '효율성': '-',
                            '분석시간': f"{elapsed_time:.3f}초",
                            '상태': f'실패: {str(e)[:30]}'
                        })
                    
                    processed += 1
                    progress_bar.progress(processed / total_employees)
                
                # 팀 결과 추가
                results.extend(team_results)
                
                # 팀별 요약 표시
                if team_results:
                    avg_time = sum(float(r['분석시간'].replace('초', '')) for r in team_results) / len(team_results)
                    st.write(f"**{team}**: {len(team_results)}명 분석 완료 (평균 {avg_time:.3f}초/명)")
            
            # 전체 결과 테이블 표시
            st.markdown("### 분석 결과")
            
            if results:
                # DataFrame 생성
                result_df = pd.DataFrame(results)
                
                # 요약 통계
                success_count = len([r for r in results if r['상태'] == '성공'])
                fail_count = len(results) - success_count
                total_time = sum(float(r['분석시간'].replace('초', '')) for r in results)
                avg_time = total_time / len(results) if results else 0
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("총 분석 인원", f"{len(results)}명")
                with col2:
                    st.metric("성공/실패", f"{success_count}/{fail_count}")
                with col3:
                    st.metric("총 소요시간", f"{total_time:.1f}초")
                with col4:
                    st.metric("평균 시간", f"{avg_time:.3f}초/명")
                
                # 결과 테이블 표시
                st.dataframe(
                    result_df,
                    use_container_width=True,
                    height=600
                )
                
                # CSV 다운로드 버튼
                csv = result_df.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 결과 다운로드 (CSV)",
                    data=csv,
                    file_name=f"analysis_result_{selected_center}_{selected_date}.csv",
                    mime="text/csv"
                )
            
            status_text.text("분석 완료!")
            progress_bar.empty()