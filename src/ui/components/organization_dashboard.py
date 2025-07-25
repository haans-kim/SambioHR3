"""
조직별 대시보드 컴포넌트
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta, date
import calendar

from ...analysis import OrganizationAnalyzer
from ...data_processing.pickle_manager import PickleManager
from ...database.db_manager import DatabaseManager

class OrganizationDashboard:
    """조직별 대시보드 컴포넌트"""
    
    def __init__(self, organization_analyzer: OrganizationAnalyzer):
        self.analyzer = organization_analyzer
        self.pickle_manager = PickleManager()
        self.db_manager = DatabaseManager()
    
    def render(self):
        """대시보드 렌더링"""
        st.markdown("### 🏢 조직별 근무 분석")
        
        # 탭 생성
        tab1, tab2, tab3 = st.tabs(["센터-직급별 분석", "기존 조직 분석", "상세 분석"])
        
        with tab1:
            self.render_center_grade_analysis()
        
        with tab2:
            # 기존 조직 선택 및 기간 설정
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
        
        with tab3:
            st.info("상세 분석 기능은 개발 중입니다.")
    
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
    
    def render_center_grade_analysis(self):
        """센터-직급별 근무시간 분석"""
        st.markdown("#### 📊 센터-직급별 주간 근무시간 비교")
        
        # 월 선택
        col1, col2 = st.columns([2, 6])
        with col1:
            current_year = date.today().year
            current_month = date.today().month
            
            # 연도 선택
            year = st.selectbox(
                "연도",
                options=list(range(2024, current_year + 1)),
                index=list(range(2024, current_year + 1)).index(current_year),
                key="year_select"
            )
            
            # 월 선택
            month = st.selectbox(
                "월",
                options=list(range(1, 13)),
                format_func=lambda x: f"{x}월",
                index=current_month - 1,
                key="month_select"
            )
        
        # 분석 실행 버튼
        if st.button("📊 분석 실행", key="analyze_center_grade"):
            self.analyze_center_grade_data(year, month)
    
    def analyze_center_grade_data(self, year: int, month: int):
        """센터-직급별 데이터 분석"""
        with st.spinner("Claim 데이터 분석 중..."):
            try:
                # Claim 데이터 로드
                claim_df = self.pickle_manager.load_dataframe('claim_data')
                
                if claim_df is None:
                    st.error("Claim 데이터를 찾을 수 없습니다. 데이터를 먼저 업로드해주세요.")
                    return
                
                # 선택한 월의 데이터만 필터링
                claim_df['근무일'] = pd.to_datetime(claim_df['근무일'])
                month_data = claim_df[(claim_df['근무일'].dt.year == year) & 
                                     (claim_df['근무일'].dt.month == month)].copy()
                
                if month_data.empty:
                    st.warning(f"{year}년 {month}월 데이터가 없습니다.")
                    return
                
                # 부서에서 센터 정보 추출 (첫 번째 단어를 센터로 가정)
                month_data['센터'] = month_data['부서'].str.split().str[0]
                
                # 데이터 확인을 위한 로그
                st.write(f"총 데이터 행 수: {len(month_data)}")
                st.write(f"센터 목록: {month_data['센터'].unique()[:10]}")  # 처음 10개만
                st.write(f"실제근무시간 범위: {month_data['실제근무시간'].describe()}")
                
                # 직급 그룹화 (Lv.1~4로 그룹핑)
                def grade_to_level(grade):
                    if pd.isna(grade):
                        return 'Unknown'
                    grade_str = str(grade)
                    if 'E1' in grade_str or 'O1' in grade_str or 'S1' in grade_str or 'G1' in grade_str:
                        return 'Lv. 1'
                    elif 'E2' in grade_str or 'O2' in grade_str or 'S2' in grade_str or 'G2' in grade_str:
                        return 'Lv. 2'
                    elif 'E3' in grade_str or 'O3' in grade_str or 'S3' in grade_str or 'G3' in grade_str:
                        return 'Lv. 3'
                    elif 'E4' in grade_str or 'O4' in grade_str or 'S4' in grade_str or 'G4' in grade_str:
                        return 'Lv. 4'
                    else:
                        return 'Unknown'
                
                month_data['직급레벨'] = month_data['직급'].apply(grade_to_level)
                
                # 주차별로 그룹화하여 평균 근무시간 계산
                month_data['주차'] = month_data['근무일'].dt.isocalendar().week
                
                # 센터별, 직급별, 주차별 평균 근무시간 계산
                # 먼저 직원별, 주차별로 합계를 구한 후 평균을 계산
                employee_weekly = month_data.groupby(['사번', '센터', '직급레벨', '주차'])['실제근무시간'].sum().reset_index()
                weekly_avg = employee_weekly.groupby(['센터', '직급레벨', '주차'])['실제근무시간'].mean().reset_index()
                
                # 피벗 테이블 생성
                pivot_tables = {}
                for level in ['Lv. 1', 'Lv. 2', 'Lv. 3', 'Lv. 4']:
                    level_data = weekly_avg[weekly_avg['직급레벨'] == level]
                    if not level_data.empty:
                        pivot = level_data.pivot(index='주차', columns='센터', values='실제근무시간')
                        pivot_tables[level] = pivot
                
                # 결과 표시
                st.success("분석 완료!")
                
                # 전체 평균 표시 - 직원별로 월 합계를 구한 후 평균 계산
                employee_monthly = month_data.groupby(['사번', '센터', '직급레벨'])['실제근무시간'].sum().reset_index()
                total_avg = employee_monthly.groupby(['센터', '직급레벨'])['실제근무시간'].mean().reset_index()
                total_pivot = total_avg.pivot(index='직급레벨', columns='센터', values='실제근무시간')
                
                st.markdown(f"### {year}년 {month}월 센터-직급별 평균 근무시간")
                st.markdown(f"**최소: {month_data['실제근무시간'].min():.2f}h | 최대: {month_data['실제근무시간'].max():.2f}h**")
                
                # 스타일링된 데이터프레임 표시
                def color_cells(val):
                    """색상 지정 함수"""
                    if pd.isna(val):
                        return ''
                    if val >= 47:
                        return 'background-color: #ff6b6b; color: white'
                    elif val >= 45:
                        return 'background-color: #ff8787'
                    elif val >= 43:
                        return 'background-color: #ffa0a0'
                    elif val >= 41:
                        return 'background-color: #ffb8b8'
                    elif val >= 39:
                        return 'background-color: #ffd0d0'
                    elif val >= 37:
                        return 'background-color: #f5f5f5'
                    else:
                        return 'background-color: #e8e8e8'
                
                styled_df = total_pivot.style.format("{:.1f}").applymap(color_cells)
                st.dataframe(styled_df, use_container_width=True)
                
                # 주차별 상세 데이터 표시
                st.markdown("### 📅 주차별 상세 데이터")
                
                # 주차 정보 계산
                weeks_in_month = sorted(month_data['주차'].unique())
                
                for week_num in weeks_in_month:
                    week_start = month_data[month_data['주차'] == week_num]['근무일'].min()
                    week_end = month_data[month_data['주차'] == week_num]['근무일'].max()
                    
                    with st.expander(f"{week_num}주차 ({week_start.strftime('%m.%d')} - {week_end.strftime('%m.%d')})"):
                        week_data = weekly_avg[weekly_avg['주차'] == week_num]
                        if not week_data.empty:
                            week_pivot = week_data.pivot(index='직급레벨', columns='센터', values='실제근무시간')
                            styled_week = week_pivot.style.format("{:.1f}").applymap(color_cells)
                            st.dataframe(styled_week, use_container_width=True)
                        else:
                            st.info("해당 주차의 데이터가 없습니다.")
                
                # 시각화
                st.markdown("### 📈 시각화")
                
                # 센터별 평균 근무시간 차트
                center_avg = month_data.groupby('센터')['실제근무시간'].mean().sort_values(ascending=False)
                fig1 = px.bar(x=center_avg.index, y=center_avg.values, 
                             title="센터별 평균 근무시간",
                             labels={'x': '센터', 'y': '평균 근무시간(h)'})
                st.plotly_chart(fig1, use_container_width=True)
                
                # 직급별 평균 근무시간 차트
                grade_avg = month_data.groupby('직급레벨')['실제근무시간'].mean().sort_values(ascending=False)
                fig2 = px.bar(x=grade_avg.index, y=grade_avg.values, 
                             title="직급별 평균 근무시간",
                             labels={'x': '직급', 'y': '평균 근무시간(h)'})
                st.plotly_chart(fig2, use_container_width=True)
                
            except Exception as e:
                st.error(f"데이터 분석 중 오류가 발생했습니다: {str(e)}")
                import traceback
                st.text(traceback.format_exc())