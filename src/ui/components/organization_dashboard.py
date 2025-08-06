"""
조직별 대시보드 컴포넌트
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
from sqlalchemy import text

from ...database import DatabaseManager
from ...data_processing import PickleManager

class OrganizationDashboard:
    """조직별 대시보드 컴포넌트"""
    
    def __init__(self, db_manager: DatabaseManager, pickle_manager: PickleManager):
        self.db_manager = db_manager
        self.pickle_manager = pickle_manager
        self.logger = logging.getLogger(__name__)
        self._organizations_cache = {}
    
    def get_organizations_by_level(self, org_level: str) -> list:
        """조직 레벨에 따른 조직 목록 조회"""
        try:
            # 캐시 확인
            if org_level in self._organizations_cache:
                return self._organizations_cache[org_level]
            
            # 데이터베이스에서 조직 목록 조회
            from sqlalchemy import text
            
            query = text("""
            SELECT DISTINCT org_code, org_name 
            FROM organization_master 
            WHERE org_level = :org_level 
                AND is_active = 1
            ORDER BY org_name
            """)
            
            with self.db_manager.get_session() as session:
                result = session.execute(query, {"org_level": org_level})
                # 조직명만 표시 (코드는 내부적으로만 사용)
                organizations = [(row[0], row[1]) for row in result.fetchall()]
                
            # 캐시 저장
            self._organizations_cache[org_level] = organizations
            return organizations
            
        except Exception as e:
            st.error(f"조직 목록 조회 실패: {e}")
            # 폴백으로 샘플 데이터 반환
            if org_level == "team":
                return ["Production_A", "Production_B", "Quality_Team", "Maintenance"]
            elif org_level == "group":
                return ["Group_A", "Group_B", "Group_C"]
            elif org_level == "center":
                return ["Center_1", "Center_2"]
            return []
    
    def get_organization_statistics(self, org_id: str, org_level: str, start_date, end_date):
        """조직 통계 데이터 조회 - 실제 데이터베이스에서 조회"""
        try:
            # 조직 정보 조회
            org_query = text("""
                SELECT org_name FROM organization_master
                WHERE org_code = :org_code
            """)
            
            with self.db_manager.get_session() as session:
                result = session.execute(org_query, {'org_code': org_id}).fetchone()
                if result:
                    org_name = result[0]
                else:
                    # org_id가 이미 조직명일 수 있음
                    org_name = org_id
                
                # 직원 수 조회 - 실제 데이터베이스에서
                if org_level == 'center':
                    count_query = text("""
                        SELECT COUNT(DISTINCT employee_id) FROM employees
                        WHERE center_name = :org_name
                    """)
                elif org_level == 'group':
                    count_query = text("""
                        SELECT COUNT(DISTINCT employee_id) FROM employees
                        WHERE group_name = :org_name
                    """)
                else:  # team
                    count_query = text("""
                        SELECT COUNT(DISTINCT employee_id) FROM employees
                        WHERE team_name = :org_name
                    """)
                
                result = session.execute(count_query, {'org_name': org_name}).fetchone()
                total_employees = result[0] if result else 0
                
                # 근무 데이터 조회 - daily_work_data 테이블에서
                if org_level == 'center':
                    work_query = text("""
                        SELECT 
                            AVG(dwd.actual_work_time) as avg_work_hours,
                            COUNT(DISTINCT dwd.employee_id) as active_employees
                        FROM daily_work_data dwd
                        JOIN employees e ON dwd.employee_id = e.employee_id
                        WHERE e.center_name = :org_name
                        AND dwd.work_date BETWEEN :start_date AND :end_date
                    """)
                elif org_level == 'group':
                    work_query = text("""
                        SELECT 
                            AVG(dwd.actual_work_time) as avg_work_hours,
                            COUNT(DISTINCT dwd.employee_id) as active_employees
                        FROM daily_work_data dwd
                        JOIN employees e ON dwd.employee_id = e.employee_id
                        WHERE e.group_name = :org_name
                        AND dwd.work_date BETWEEN :start_date AND :end_date
                    """)
                else:  # team
                    work_query = text("""
                        SELECT 
                            AVG(dwd.actual_work_time) as avg_work_hours,
                            COUNT(DISTINCT dwd.employee_id) as active_employees
                        FROM daily_work_data dwd
                        JOIN employees e ON dwd.employee_id = e.employee_id
                        WHERE e.team_name = :org_name
                        AND dwd.work_date BETWEEN :start_date AND :end_date
                    """)
                
                work_result = conn.execute(work_query, {
                    'org_name': org_name,
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d')
                }).fetchone()
                
                avg_work_hours = 0
                utilization_rate = 0
                efficiency_score = 0
                
                if work_result and work_result[0]:
                    avg_work_hours = work_result[0]
                    # 가동률 계산 (실제근무시간 / 8시간 기준)
                    utilization_rate = min(100, (avg_work_hours / 8) * 100)
                    # 효율성 점수 계산
                    efficiency_score = min(100, utilization_rate * 0.95)
                else:
                    # Pickle 데이터 폴백 - organization_data 사용
                    org_data = self.pickle_manager.load_dataframe('organization_data')
                    if org_data is not None:
                        # 조직 레벨에 따른 필터링
                        if org_level == 'center' and '센터' in org_data.columns:
                            filtered_data = org_data[org_data['센터'] == org_name]
                        elif org_level == 'team' and '팀' in org_data.columns:
                            filtered_data = org_data[org_data['팀'] == org_name]
                        elif org_level == 'group' and '그룹' in org_data.columns:
                            filtered_data = org_data[org_data['그룹'] == org_name]
                        else:
                            filtered_data = org_data
                        
                        # claim_data에서 근무 통계 계산
                        claim_data = self.pickle_manager.load_dataframe('claim_data')
                        if claim_data is not None and not claim_data.empty:
                            # 날짜 필터링
                            if '근무일' in claim_data.columns:
                                claim_data['근무일'] = pd.to_datetime(claim_data['근무일'])
                                mask = (claim_data['근무일'].dt.date >= start_date) & (claim_data['근무일'].dt.date <= end_date)
                                period_data = claim_data[mask]
                                
                                # 직원 ID 리스트
                                employee_ids = filtered_data['사번'].tolist() if '사번' in filtered_data.columns else []
                                
                                if employee_ids and '사번' in period_data.columns:
                                    # 해당 조직 직원들의 데이터만 필터링
                                    org_claim_data = period_data[period_data['사번'].isin(employee_ids)]
                                    
                                    if not org_claim_data.empty and '실제근무시간' in org_claim_data.columns:
                                        avg_work_hours = org_claim_data['실제근무시간'].mean()
                                        
                                        if '기준근무시간' in org_claim_data.columns and org_claim_data['기준근무시간'].mean() > 0:
                                            utilization_rate = (avg_work_hours / org_claim_data['기준근무시간'].mean()) * 100
                                        else:
                                            utilization_rate = (avg_work_hours / 8) * 100
                                        
                                        efficiency_score = min(100, utilization_rate * 0.9)
            
            return {
                'total_employees': total_employees,
                'avg_work_hours': avg_work_hours if avg_work_hours else 0,
                'utilization_rate': utilization_rate if utilization_rate else 0,
                'efficiency_score': efficiency_score if efficiency_score else 0,
                'org_name': org_name,
                'org_level': org_level
            }
            
        except Exception as e:
            self.logger.error(f"조직 통계 조회 오류: {e}", exc_info=True)
            return None
    
    def get_available_date_range(self):
        """데이터베이스에서 사용 가능한 날짜 범위 가져오기"""
        try:
            # 태깅 데이터에서 날짜 범위 추출
            tag_data = self.pickle_manager.load_dataframe(name='tag_data')
            if tag_data is not None and 'ENTE_DT' in tag_data.columns:
                # YYYYMMDD 형식을 date 객체로 변환
                dates = pd.to_datetime(tag_data['ENTE_DT'].astype(str), format='%Y%m%d', errors='coerce')
                dates = dates.dropna()
                
                if not dates.empty:
                    min_date = dates.min().date()
                    max_date = dates.max().date()
                    self.logger.info(f"사용 가능한 날짜 범위: {min_date} ~ {max_date}")
                    return (min_date, max_date)
            
            # 대체 데이터 소스 시도 (claim_data)
            claim_data = self.pickle_manager.load_dataframe(name='claim_data')
            if claim_data is not None and '근무일' in claim_data.columns:
                dates = pd.to_datetime(claim_data['근무일'])
                if not dates.empty:
                    min_date = dates.min().date()
                    max_date = dates.max().date()
                    return (min_date, max_date)
            
            return None
        except Exception as e:
            self.logger.warning(f"날짜 범위 로드 실패: {e}")
            return None
    
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
                    ["team", "group", "center"],
                    format_func=lambda x: {"team": "팀", "group": "그룹", "center": "센터"}.get(x, x),
                    key="org_level_select"
                )
            
            with col2:
                # 실제 데이터베이스에서 조직 목록 가져오기
                organizations = self.get_organizations_by_level(org_level)
                if organizations:
                    # 조직 코드를 인덱스로, 조직명을 표시 텍스트로 사용
                    org_options = {org[0]: org[1] for org in organizations}
                    org_id = st.selectbox(
                        "조직 선택",
                        options=list(org_options.keys()),
                        format_func=lambda x: org_options[x],
                        key="org_id_select"
                    )
                else:
                    org_id = st.selectbox(
                        "조직 선택",
                        ["데이터 없음"],
                        key="org_id_select"
                    )
            
            with col3:
                # 데이터베이스에서 사용 가능한 날짜 범위 가져오기
                available_dates = self.get_available_date_range()
                if available_dates:
                    min_date, max_date = available_dates
                    # 기본값 설정 (최근 30일 또는 가능한 범위)
                    default_start = max(min_date, max_date - timedelta(days=30))
                    default_end = max_date
                    
                    date_range = st.date_input(
                        "분석 기간",
                        value=(default_start, default_end),
                        min_value=min_date,
                        max_value=max_date,
                        key="org_date_range"
                    )
                else:
                    st.warning("사용 가능한 데이터가 없습니다.")
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
        """조직 분석 실행 - 개인별 분석 수행 후 DB 저장"""
        with st.spinner("조직 분석 중..."):
            try:
                # 날짜 처리
                if isinstance(date_range, tuple) and len(date_range) == 2:
                    start_date, end_date = date_range
                else:
                    # 단일 날짜인 경우
                    start_date = end_date = date_range
                
                # 조직 정보 가져오기
                if org_level == 'center':
                    # org_id가 CENTER_003 같은 코드인 경우
                    org_query = text("""
                        SELECT org_name FROM organization_master
                        WHERE org_code = :org_code
                    """)
                    with self.db_manager.get_session() as session:
                        result = session.execute(org_query, {'org_code': org_id}).fetchone()
                        org_name = result[0] if result else org_id
                else:
                    org_name = org_id  # 이미 조직명일 수 있음
                
                # 조직에 속한 직원들 가져오기
                employees = self._get_organization_employees(org_name, org_level)
                
                if not employees:
                    st.warning(f"{org_name}에 속한 직원이 없습니다.")
                    return
                
                st.info(f"{org_name} 소속 {len(employees)}명의 직원 분석을 시작합니다.")
                
                # Progress bar
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # 개인별 분석기 초기화
                import sys
                from pathlib import Path
                # 프로젝트 루트 경로 추가
                project_root = Path(__file__).parent.parent.parent.parent
                if str(project_root) not in sys.path:
                    sys.path.append(str(project_root))
                
                from src.analysis.individual_analyzer import IndividualAnalyzer
                from src.data_processing import PickleManager
                from src.database import DatabaseManager
                from datetime import datetime
                
                # 새로운 인스턴스 생성 (싱글톤 사용하지 않음)
                db_mgr = DatabaseManager()
                pickle_mgr = PickleManager()
                individual_analyzer = IndividualAnalyzer(db_mgr, None)
                individual_analyzer.pickle_manager = pickle_mgr
                
                # 각 직원별로 분석 수행
                analyzed_count = 0
                failed_count = 0
                total_work_hours = 0
                total_actual_work_time = 0
                
                for idx, employee_id in enumerate(employees):
                    try:
                        # Progress 업데이트
                        progress = (idx + 1) / len(employees)
                        progress_bar.progress(progress)
                        status_text.text(f"분석 중... ({idx + 1}/{len(employees)}) - {employee_id}")
                        
                        # 개인별 분석 수행
                        # start_date와 end_date가 tuple인 경우 처리
                        if isinstance(start_date, tuple):
                            start_dt = start_date[0] if len(start_date) > 0 else date.today()
                        else:
                            start_dt = start_date
                            
                        if isinstance(end_date, tuple):
                            end_dt = end_date[-1] if len(end_date) > 0 else date.today()
                        else:
                            end_dt = end_date
                        
                        analysis_result = individual_analyzer.analyze_individual(
                            employee_id, 
                            datetime.combine(start_dt, datetime.min.time()),
                            datetime.combine(end_dt, datetime.max.time())
                        )
                        
                        if analysis_result:
                            analyzed_count += 1
                            # 근무시간 집계
                            if 'work_time_analysis' in analysis_result:
                                work_analysis = analysis_result['work_time_analysis']
                                total_work_hours += work_analysis.get('total_work_hours', 0)
                                total_actual_work_time += work_analysis.get('actual_work_time', 0)
                    
                    except Exception as e:
                        failed_count += 1
                        self.logger.warning(f"직원 {employee_id} 분석 실패: {e}")
                        st.error(f"직원 {employee_id} 분석 실패: {e}")
                        import traceback
                        self.logger.error(traceback.format_exc())
                        continue
                
                # Progress 완료
                progress_bar.progress(1.0)
                status_text.text("")
                
                # 분석 결과 요약
                if analyzed_count > 0:
                    avg_work_hours = total_work_hours / analyzed_count
                    avg_actual_work = total_actual_work_time / analyzed_count
                    utilization_rate = (avg_actual_work / avg_work_hours * 100) if avg_work_hours > 0 else 0
                    efficiency_score = min(100, utilization_rate * 0.95)
                    
                    # 조직 분석 결과 DB 저장
                    self._save_organization_analysis_result(
                        org_id, org_name, org_level, start_date, end_date,
                        analyzed_count, avg_work_hours, utilization_rate, efficiency_score
                    )
                    
                    st.success(f"분석 완료! 성공: {analyzed_count}명, 실패: {failed_count}명")
                    
                    # 조직 KPI 표시
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("분석 인원", f"{analyzed_count}명")
                    
                    with col2:
                        st.metric("평균 근무시간", f"{avg_work_hours:.1f}시간")
                    
                    with col3:
                        st.metric("가동률", f"{utilization_rate:.1f}%")
                    
                    with col4:
                        st.metric("효율성 점수", f"{efficiency_score:.1f}점")
                    
                else:
                    st.error("분석에 성공한 직원이 없습니다.")
                    
            except Exception as e:
                st.error(f"분석 중 오류 발생: {e}")
                self.logger.error(f"조직 분석 오류: {e}", exc_info=True)
    
    def render_organization_charts(self):
        """조직 차트 렌더링 (샘플 데이터)"""
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
    
    def _get_organization_name(self, org_id: str) -> str:
        """조직 ID로 조직명 가져오기"""
        try:
            org_query = text("""
                SELECT org_name FROM organization_master
                WHERE org_code = :org_code
            """)
            
            with self.db_manager.get_session() as session:
                result = session.execute(org_query, {'org_code': org_id}).fetchone()
                if result:
                    return result[0]
                else:
                    # org_id가 이미 조직명일 수 있음
                    return org_id
        except Exception as e:
            self.logger.error(f"조직명 조회 오류: {e}")
            return org_id
    
    def _get_organization_employees(self, org_name: str, org_level: str) -> List[str]:
        """조직에 속한 직원 ID 목록 가져오기"""
        try:
            self.logger.info(f"조직 직원 조회: {org_name} ({org_level})")
            
            if org_level == 'center':
                query = text("""
                    SELECT DISTINCT employee_id 
                    FROM employees
                    WHERE center_name = :org_name
                """)
            elif org_level == 'group':
                query = text("""
                    SELECT DISTINCT employee_id 
                    FROM employees
                    WHERE group_name = :org_name
                """)
            else:  # team
                query = text("""
                    SELECT DISTINCT employee_id 
                    FROM employees
                    WHERE team_name = :org_name
                """)
            
            with self.db_manager.get_session() as session:
                result = session.execute(query, {'org_name': org_name}).fetchall()
                employee_list = [row[0] for row in result]
                self.logger.info(f"조회된 직원 수: {len(employee_list)}")
                return employee_list
                
        except Exception as e:
            self.logger.error(f"직원 목록 조회 오류: {e}")
            return []
    
    def _save_organization_analysis_result(self, org_id: str, org_name: str, org_level: str,
                                          start_date, end_date, employee_count: int,
                                          avg_work_hours: float, utilization_rate: float,
                                          efficiency_score: float):
        """조직 분석 결과를 DB에 저장"""
        try:
            # organization_daily_stats 테이블에 저장
            insert_query = text("""
                INSERT OR REPLACE INTO organization_daily_stats 
                (org_code, work_date, total_employees, avg_actual_work_hours, 
                 avg_work_efficiency, created_at, updated_at)
                VALUES (:org_code, :work_date, :total_employees, :avg_actual_work_hours,
                        :avg_work_efficiency, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """)
            
            with self.db_manager.get_session() as session:
                # 기간의 각 날짜별로 저장
                current_date = start_date
                while current_date <= end_date:
                    session.execute(insert_query, {
                        'org_code': org_id,
                        'work_date': current_date.strftime('%Y-%m-%d'),
                        'total_employees': employee_count,
                        'avg_actual_work_hours': avg_work_hours,
                        'avg_work_efficiency': efficiency_score
                    })
                    current_date += timedelta(days=1)
                session.commit()
                
            self.logger.info(f"조직 분석 결과 저장 완료: {org_name}")
            
        except Exception as e:
            self.logger.error(f"조직 분석 결과 저장 오류: {e}")
    
    def render_organization_charts_with_data(self, org_stats: dict):
        """실제 데이터로 조직 차트 렌더링"""
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
        
        filtered_data = org_stats.get('filtered_data')
        
        if filtered_data is not None and not filtered_data.empty:
            # 직급별 인원 분포
            if '직급명' in filtered_data.columns:
                grade_counts = filtered_data['직급명'].value_counts().head(10)
                fig1 = px.bar(x=grade_counts.index, y=grade_counts.values, 
                             title=f"{org_stats['org_name']} 직급별 인원 분포",
                             labels={'x': '직급', 'y': '인원수'})
                st.plotly_chart(fig1, use_container_width=True)
            
            # 성별 분포
            if '성별' in filtered_data.columns:
                gender_counts = filtered_data['성별'].value_counts()
                fig2 = px.pie(values=gender_counts.values, names=gender_counts.index,
                             title=f"{org_stats['org_name']} 성별 분포")
                st.plotly_chart(fig2, use_container_width=True)
            
            # 입사연도별 분포
            if '입사년도' in filtered_data.columns:
                year_counts = filtered_data['입사년도'].value_counts().sort_index().tail(10)
                fig3 = px.bar(x=year_counts.index, y=year_counts.values,
                             title=f"{org_stats['org_name']} 최근 10년 입사 현황",
                             labels={'x': '입사년도', 'y': '인원수'})
                st.plotly_chart(fig3, use_container_width=True)
        else:
            # 데이터가 없을 경우 기본 차트 표시
            self.render_organization_charts()
    
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
        
        # 월 선택 - 데이터베이스의 날짜 범위 기반
        col1, col2 = st.columns([2, 6])
        with col1:
            # 사용 가능한 날짜 범위 가져오기
            available_dates = self.get_available_date_range()
            
            if available_dates:
                min_date, max_date = available_dates
                min_year = min_date.year
                max_year = max_date.year
                current_year = date.today().year if min_year <= date.today().year <= max_year else max_year
                current_month = date.today().month if current_year == date.today().year else max_date.month
            else:
                # 데이터가 없을 경우 기본값
                current_year = date.today().year
                current_month = date.today().month
                min_year = 2024
                max_year = current_year
            
            # 연도 선택
            year = st.selectbox(
                "연도",
                options=list(range(min_year, max_year + 1)),
                index=list(range(min_year, max_year + 1)).index(current_year) if current_year in range(min_year, max_year + 1) else 0,
                key="year_select"
            )
            
            # 월 선택 - 선택된 연도에서 사용 가능한 월만 표시
            if available_dates:
                if year == min_year and year == max_year:
                    # 같은 연도인 경우
                    available_months = list(range(min_date.month, max_date.month + 1))
                elif year == min_year:
                    # 최소 연도인 경우
                    available_months = list(range(min_date.month, 13))
                elif year == max_year:
                    # 최대 연도인 경우
                    available_months = list(range(1, max_date.month + 1))
                else:
                    # 중간 연도인 경우
                    available_months = list(range(1, 13))
                
                # 현재 월이 사용 가능한 월에 있는지 확인
                if current_month in available_months:
                    default_month_index = available_months.index(current_month)
                else:
                    default_month_index = len(available_months) - 1  # 가장 최근 월
            else:
                available_months = list(range(1, 13))
                default_month_index = current_month - 1
            
            month = st.selectbox(
                "월",
                options=available_months,
                format_func=lambda x: f"{x}월",
                index=default_month_index,
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
                st.markdown(f"**최소: {month_data['실제근무시간'].min():.2f}h | 최대: {month_data['실제근무시간'].max():.2f}h**")
                
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
                
                styled_df = total_pivot.style.format("{:.1f}").applymap(color_cells)
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
                st.markdown(f"**최소: {min_hours:.1f}h | 최대: {max_hours:.1f}h**")
                
                # 스타일 적용
                styled_weekly = weekly_df.style.format("{:.1f}").applymap(color_cells)
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