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
from ...database import get_database_manager, get_pickle_manager

class OrganizationDashboard:
    """조직별 대시보드 컴포넌트"""
    
    def __init__(self, organization_analyzer: OrganizationAnalyzer):
        self.analyzer = organization_analyzer
        self.pickle_manager = get_pickle_manager()
        self.db_manager = get_database_manager()
    
    def render(self):
        """대시보드 렌더링"""
        st.markdown("### 조직별 근무 분석")
        
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
            if st.button("조직 분석 실행", type="primary"):
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
        st.markdown("""
        <div style="background: #f8f9fa; 
                    border-left: 3px solid #2E86AB; 
                    padding: 0.8rem 1.2rem; 
                    border-radius: 0 6px 6px 0; 
                    margin: 1rem 0 0.5rem 0;">
            <h4 style="margin: 0; color: #2E86AB; font-weight: 600; font-size: 1.1rem;">
                Organization Performance Analysis
            </h4>
            <p style="margin: 0.3rem 0 0 0; color: #6c757d; font-size: 0.9rem;">
                조직 성과 분석
            </p>
        </div>
        """, unsafe_allow_html=True)
        
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
        st.markdown("""
        <div style="background: #f8f9fa; 
                    border-left: 3px solid #2E86AB; 
                    padding: 0.8rem 1.2rem; 
                    border-radius: 0 6px 6px 0; 
                    margin: 1rem 0 0.5rem 0;">
            <h4 style="margin: 0; color: #2E86AB; font-weight: 600; font-size: 1.1rem;">
                Center-Grade Weekly Analysis
            </h4>
            <p style="margin: 0.3rem 0 0 0; color: #6c757d; font-size: 0.9rem;">
                센터-직급별 주간 근무시간 비교
            </p>
        </div>
        """, unsafe_allow_html=True)
        
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
        if st.button("분석 실행", type="primary", key="analyze_center_grade"):
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
                
                # 조직현황 데이터 로드하여 센터 정보 매핑
                org_df = self.pickle_manager.load_dataframe('organization_data')
                if org_df is None:
                    # organization_data로 찾을 수 없으면 organization으로 시도
                    org_df = self.pickle_manager.load_dataframe('organization')
                
                if org_df is not None and '부서명' in org_df.columns and '센터' in org_df.columns:
                    # 부서별 센터 매핑 생성
                    dept_center_map = org_df.drop_duplicates(subset=['부서명'])[['부서명', '센터']].set_index('부서명')['센터'].to_dict()
                    
                    # 센터 정보 매핑
                    month_data['센터'] = month_data['부서'].map(dept_center_map).fillna('Unknown')
                    
                    # 센터 목록 가져오기
                    valid_centers = sorted(org_df['센터'].dropna().unique().tolist())
                else:
                    st.error("조직현황 데이터를 찾을 수 없습니다. 데이터를 먼저 업로드해주세요.")
                    return
                
                # 데이터 확인을 위한 로그
                with st.expander("데이터 확인"):
                    st.write(f"총 데이터 행 수: {len(month_data)}")
                    unique_centers = month_data['센터'].unique()
                    st.write(f"센터 개수: {len(unique_centers)}")
                    st.write(f"센터 목록: {sorted(unique_centers)}")
                    
                    # 센터별 데이터 개수 확인
                    center_counts = month_data['센터'].value_counts()
                    st.write("센터별 데이터 수:")
                    st.dataframe(center_counts.head(20))
                    
                    st.write(f"실제근무시간 통계:")
                    st.write(month_data['실제근무시간'].describe())
                
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
                
                st.markdown("""
                <div style="background: #f8f9fa; 
                            border-left: 3px solid #28a745; 
                            padding: 0.8rem 1.2rem; 
                            border-radius: 0 6px 6px 0; 
                            margin: 1rem 0 0.5rem 0;">
                    <h4 style="margin: 0; color: #28a745; font-weight: 600; font-size: 1.1rem;">
                        {}년 {}월 센터-직급별 평균 근무시간
                    </h4>
                </div>
                """.format(year, month), unsafe_allow_html=True)
                min_val = month_data['실제근무시간'].min()
                max_val = month_data['실제근무시간'].max()
                if pd.notna(min_val) and pd.notna(max_val):
                    st.markdown(f"**최소: {min_val:.2f}h | 최대: {max_val:.2f}h**")
                else:
                    st.markdown("**데이터가 없습니다**")
                
                # 평균 행과 열 추가
                # 열 평균 (센터 평균) 계산
                center_avg = total_pivot.mean(axis=0)
                total_pivot.loc['센터 평균'] = center_avg
                
                # 행 평균 (전체 평균) 계산
                total_pivot['전체 평균'] = total_pivot.mean(axis=1)
                
                # 스타일링된 데이터프레임 표시 - 256 레벨 그라데이션
                def color_cells(val):
                    """색상 지정 함수 - 더 세밀한 그라데이션"""
                    if pd.isna(val):
                        return ''
                    
                    # 최소값과 최대값 기준으로 정규화 (35-50 시간 범위)
                    min_val, max_val = 35, 50
                    normalized = (val - min_val) / (max_val - min_val)
                    normalized = max(0, min(1, normalized))  # 0-1 범위로 제한
                    
                    # 256 레벨 색상 계산
                    if val >= 47:  # 매우 높은 값 - 진한 빨간색
                        r = 255
                        g = int(107 - normalized * 60)
                        b = int(107 - normalized * 60)
                        return f'background-color: rgb({r}, {g}, {b}); color: white; font-weight: bold'
                    elif val >= 44:  # 높은 값 - 빨간색 계열
                        intensity = (val - 44) / 3 * 255
                        r = 255
                        g = int(160 - intensity * 0.3)
                        b = int(160 - intensity * 0.3)
                        return f'background-color: rgb({r}, {g}, {b})'
                    elif val >= 40:  # 중간 값 - 연한 빨간색
                        intensity = (val - 40) / 4 * 100
                        r = 255
                        g = int(200 - intensity * 0.4)
                        b = int(200 - intensity * 0.4)
                        return f'background-color: rgb({r}, {g}, {b})'
                    elif val >= 37:  # 정상 범위 - 연한 색
                        gray = int(245 - (val - 37) * 10)
                        return f'background-color: rgb({gray}, {gray}, {gray})'
                    else:  # 낮은 값 - 회색
                        gray = int(230 + (37 - val) * 3)
                        gray = min(245, gray)
                        return f'background-color: rgb({gray}, {gray}, {gray})'
                
                # None 값 처리를 위한 포맷 함수
                def format_value(val):
                    if pd.isna(val):
                        return "-"
                    return f"{val:.1f}"
                
                styled_df = total_pivot.style.format(format_value).applymap(color_cells)
                st.dataframe(styled_df, use_container_width=True)
                
                # 주차별 상세 데이터를 하나의 통합 테이블로 표시
                st.markdown("""
                <div style="background: #f8f9fa; 
                            border-left: 3px solid #6f42c1; 
                            padding: 0.8rem 1.2rem; 
                            border-radius: 0 6px 6px 0; 
                            margin: 1rem 0 0.5rem 0;">
                    <h4 style="margin: 0; color: #6f42c1; font-weight: 600; font-size: 1.1rem;">
                        Weekly Working Hours Comparison
                    </h4>
                    <p style="margin: 0.3rem 0 0 0; color: #6c757d; font-size: 0.9rem;">
                        센터-월별 주간 근무시간 비교
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
                # 모든 주차 데이터를 하나의 테이블로 통합
                weeks_in_month = sorted(month_data['주차'].unique())
                
                # 주차별 평균을 센터별로 정리
                weekly_summary = {}
                for center in sorted(month_data['센터'].unique()):
                    weekly_summary[center] = {}
                    for week in weeks_in_month:
                        week_data = month_data[(month_data['센터'] == center) & (month_data['주차'] == week)]
                        if not week_data.empty:
                            # 직원별로 주간 합계를 구한 후 평균
                            employee_week_sum = week_data.groupby('사번')['실제근무시간'].sum()
                            weekly_summary[center][f'{month}.{week}주'] = employee_week_sum.mean()
                        else:
                            weekly_summary[center][f'{month}.{week}주'] = None
                
                # DataFrame으로 변환
                weekly_df = pd.DataFrame(weekly_summary).T
                
                # 평균 열 추가
                weekly_df['월 평균'] = weekly_df.mean(axis=1)
                
                # 평균 행 추가
                weekly_df.loc['센터 평균'] = weekly_df.mean(axis=0)
                
                # 날짜 정보 추가 (최소/최대)
                min_hours = weekly_df.min().min()
                max_hours = weekly_df.max().max()
                
                # None 체크 추가
                if pd.notna(min_hours) and pd.notna(max_hours):
                    st.markdown(f"**최소: {min_hours:.1f}h | 최대: {max_hours:.1f}h**")
                else:
                    st.markdown("**데이터가 없습니다**")
                
                # 스타일 적용
                styled_weekly = weekly_df.style.format(format_value).applymap(color_cells)
                st.dataframe(styled_weekly, use_container_width=True)
                
                # 시각화
                st.markdown("""
                <div style="background: #f8f9fa; 
                            border-left: 3px solid #fd7e14; 
                            padding: 0.8rem 1.2rem; 
                            border-radius: 0 6px 6px 0; 
                            margin: 1rem 0 0.5rem 0;">
                    <h4 style="margin: 0; color: #fd7e14; font-weight: 600; font-size: 1.1rem;">
                        Data Visualization
                    </h4>
                    <p style="margin: 0.3rem 0 0 0; color: #6c757d; font-size: 0.9rem;">
                        데이터 시각화
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
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