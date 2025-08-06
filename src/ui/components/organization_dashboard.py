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
                
                self.logger.info(f"조직 {org_name}({org_level})에서 직원 {len(employees) if employees else 0}명 발견")
                if employees:
                    self.logger.info(f"직원 목록 (처음 5명): {employees[:5]}")
                
                if not employees:
                    st.warning(f"{org_name}에 속한 직원이 없습니다.")
                    return
                
                st.info(f"{org_name} 소속 {len(employees)}명의 직원 분석을 시작합니다.")
                
                # 선택한 직원 목록 표시
                st.markdown("### 📋 분석 대상 직원 목록")
                employees_df = pd.DataFrame({
                    '순번': range(1, len(employees) + 1),
                    '사번': employees,
                    '상태': ['대기중'] * len(employees)
                })
                employees_table = st.empty()
                employees_table.dataframe(employees_df, use_container_width=True)
                
                # Progress bar
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # 실시간 분석 결과 테이블
                st.markdown("### 📊 실시간 분석 결과")
                results_table = st.empty()
                current_results = []
                
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
                pickle_mgr = PickleManager(base_path="data/pickles")  # 명시적 경로 지정
                individual_analyzer = IndividualAnalyzer(db_mgr, None)
                individual_analyzer.pickle_manager = pickle_mgr
                
                # 각 직원별로 분석 수행
                analyzed_count = 0
                failed_count = 0
                total_work_hours = 0
                total_actual_work_time = 0
                total_days = 0  # 총 분석 일수
                employee_results = []  # 개인별 분석 결과 저장
                
                for idx, employee_id in enumerate(employees):
                    try:
                        # Progress 업데이트
                        progress = (idx + 1) / len(employees)
                        progress_bar.progress(progress)
                        status_text.text(f"분석 중... ({idx + 1}/{len(employees)}) - {employee_id}")
                        
                        # 직원 상태 업데이트 (분석 중)
                        employees_df.loc[idx, '상태'] = '분석중'
                        employees_table.dataframe(employees_df, use_container_width=True)
                        
                        # 개인별 분석 수행 - 임시로 간단한 더미 데이터 사용
                        # start_date와 end_date가 tuple인 경우 처리
                        if isinstance(start_date, tuple):
                            start_dt = start_date[0] if len(start_date) > 0 else date.today()
                        else:
                            start_dt = start_date
                            
                        if isinstance(end_date, tuple):
                            end_dt = end_date[-1] if len(end_date) > 0 else date.today()
                        else:
                            end_dt = end_date
                        
                        # 개인별 분석 수행 - individual_dashboard와 동일한 방식 사용
                        analysis_results = self._analyze_employee(
                            employee_id,
                            start_dt,
                            end_dt
                        )
                        
                        if analysis_results and len(analysis_results) > 0:
                            analyzed_count += 1
                            
                            # 분석 결과 저장
                            self._save_employee_analysis(analysis_results)
                            
                            # 직원 상태 업데이트 (완료)
                            employees_df.loc[idx, '상태'] = f'완료 ({len(analysis_results)}건)'
                            employees_table.dataframe(employees_df, use_container_width=True)
                            
                            # 전체 통계 계산용 데이터 수집
                            for result in analysis_results:
                                work_hours = result.get('attendance_hours', 0)
                                actual_hours = result.get('actual_work_hours', 0)
                                
                                # 디버깅 로그
                                if idx < 5:  # 처음 5명만 로그
                                    self.logger.info(f"직원 {employee_id}: 근태={work_hours:.1f}h, 실제={actual_hours:.1f}h")
                                
                                total_work_hours += work_hours
                                total_actual_work_time += actual_hours
                                total_days += 1
                                
                                # 개인별 결과를 리스트에 저장하고 실시간 업데이트
                                new_result = {
                                    '사번': employee_id,
                                    '날짜': result.get('analysis_date', ''),
                                    '근태기록시간': f"{work_hours:.1f}h",
                                    '실제작업시간': f"{actual_hours:.1f}h",
                                    '작업시간추정률': f"{result.get('work_estimation_rate', 0):.1f}%",
                                    '회의시간': f"{result.get('meeting_time', 0):.1f}h",
                                    '식사시간': f"{result.get('meal_time', 0):.1f}h",
                                    '이동시간': f"{result.get('movement_time', 0):.1f}h",
                                    '휴식시간': f"{result.get('rest_time', 0):.1f}h",
                                    '데이터신뢰도': f"{result.get('data_reliability', 0):.1f}점"
                                }
                                employee_results.append(new_result)
                                current_results.append(new_result)
                                
                                # 실시간 결과 테이블 업데이트
                                if current_results:
                                    results_df = pd.DataFrame(current_results)
                                    results_table.dataframe(results_df, use_container_width=True)
                        else:
                            # 분석 실패
                            employees_df.loc[idx, '상태'] = '실패 (데이터 없음)'
                            employees_table.dataframe(employees_df, use_container_width=True)
                    
                    except Exception as e:
                        failed_count += 1
                        # 분석 실패 상태 업데이트
                        employees_df.loc[idx, '상태'] = f'오류: {str(e)[:30]}...'
                        employees_table.dataframe(employees_df, use_container_width=True)
                        
                        self.logger.warning(f"직원 {employee_id} 분석 실패: {e}")
                        st.error(f"직원 {employee_id} 분석 실패: {e}")
                        import traceback
                        self.logger.error(traceback.format_exc())
                        continue
                
                # Progress 완료
                progress_bar.progress(1.0)
                status_text.text("")
                
                # 분석 결과 요약
                if analyzed_count > 0 and total_days > 0:
                    # 일 평균으로 계산
                    avg_work_hours = total_work_hours / total_days
                    avg_actual_work = total_actual_work_time / total_days
                    
                    # 효율성 계산
                    if avg_work_hours > 0:
                        utilization_rate = (avg_actual_work / avg_work_hours * 100)
                    else:
                        # 근태 기록이 없으면 실제 작업시간 기준으로 계산
                        utilization_rate = (avg_actual_work / 8) * 100  # 8시간 기준
                    
                    efficiency_score = min(100, utilization_rate * 0.95)
                    
                    self.logger.info(f"분석 완료: 직원 {analyzed_count}명, 총 {total_days}일")
                    self.logger.info(f"평균 근태: {avg_work_hours:.1f}h, 평균 실제: {avg_actual_work:.1f}h")
                    self.logger.info(f"가동률: {utilization_rate:.1f}%, 효율성: {efficiency_score:.1f}점")
                    
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
                        if pd.isna(avg_work_hours) or avg_work_hours == 0:
                            st.metric("평균 근무시간", "데이터 없음")
                        else:
                            st.metric("평균 근무시간", f"{avg_work_hours:.1f}시간")
                    
                    with col3:
                        if pd.isna(utilization_rate):
                            st.metric("가동률", "계산 불가")
                        else:
                            st.metric("가동률", f"{utilization_rate:.1f}%")
                    
                    with col4:
                        if pd.isna(efficiency_score):
                            st.metric("효율성 점수", "계산 불가")
                        else:
                            st.metric("효율성 점수", f"{efficiency_score:.1f}점")
                    
                    # 최종 분석 결과 요약
                    if employee_results:
                        st.markdown("### 📊 최종 분석 결과 요약")
                        st.markdown("*DB에 저장된 데이터*")
                        
                        # DataFrame으로 변환
                        final_results_df = pd.DataFrame(employee_results)
                        
                        # 최종 테이블 표시 (스크롤 가능)
                        st.dataframe(
                            final_results_df,
                            use_container_width=True,
                            height=400  # 높이 제한으로 스크롤 가능
                        )
                        
                        # CSV 다운로드 버튼
                        csv = final_results_df.to_csv(index=False, encoding='utf-8-sig')
                        st.download_button(
                            label="📥 CSV로 다운로드",
                            data=csv,
                            file_name=f"{org_name}_분석결과_{start_date}_{end_date}.csv",
                            mime="text/csv"
                        )
                    
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
            
            # pickle 데이터에서 조직 정보 가져오기
            org_df = self.pickle_manager.load_dataframe('organization_data')
            if org_df is None or org_df.empty:
                self.logger.warning("organization_data를 찾을 수 없습니다. organization 시도")
                org_df = self.pickle_manager.load_dataframe('organization')
                if org_df is None or org_df.empty:
                    self.logger.warning("organization도 찾을 수 없습니다")
                    return []
            
            self.logger.info(f"조직 데이터 로드 성공: {len(org_df)}행, 컬럼: {list(org_df.columns)}")
            
            # 조직 레벨에 따른 필터링
            if org_level == 'center':
                if '센터' in org_df.columns:
                    filtered = org_df[org_df['센터'] == org_name]
                    self.logger.info(f"'센터' 컬럼으로 필터링: {len(filtered)}명")
                elif 'center' in org_df.columns:
                    filtered = org_df[org_df['center'] == org_name]
                    self.logger.info(f"'center' 컬럼으로 필터링: {len(filtered)}명")
                else:
                    self.logger.warning("센터 컬럼을 찾을 수 없습니다")
                    return []
            elif org_level == 'group':
                if '그룹' in org_df.columns:
                    filtered = org_df[org_df['그룹'] == org_name]
                elif 'group_name' in org_df.columns:
                    filtered = org_df[org_df['group_name'] == org_name]
                else:
                    self.logger.warning("그룹 컬럼을 찾을 수 없습니다")
                    return []
            else:  # team
                if '팀' in org_df.columns:
                    filtered = org_df[org_df['팀'] == org_name]
                elif 'team' in org_df.columns:
                    filtered = org_df[org_df['team'] == org_name]
                else:
                    self.logger.warning("팀 컬럼을 찾을 수 없습니다")
                    return []
            
            # 직원 ID 추출
            employee_list = []
            if '사번' in filtered.columns:
                employee_list = filtered['사번'].dropna().unique().tolist()
            elif 'employee_no' in filtered.columns:
                employee_list = filtered['employee_no'].dropna().unique().tolist()
            elif 'employee_id' in filtered.columns:
                employee_list = filtered['employee_id'].dropna().unique().tolist()
            
            # 문자열로 변환
            employee_list = [str(emp_id) for emp_id in employee_list]
            
            self.logger.info(f"조회된 직원 수: {len(employee_list)}")
            if len(employee_list) > 0:
                self.logger.info(f"첫 5명: {employee_list[:5]}")
            
            return employee_list
                
        except Exception as e:
            self.logger.error(f"직원 목록 조회 오류: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
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
    
    def _analyze_employee(self, employee_id: str, start_date, end_date):
        """개인별 분석 수행 - individual_dashboard의 실제 로직 사용"""
        try:
            self.logger.info(f"직원 {employee_id} 분석 시작: {start_date} ~ {end_date}")
            
            # IndividualDashboard 인스턴스 생성
            from .individual_dashboard import IndividualDashboard
            from src.analysis.individual_analyzer import IndividualAnalyzer
            
            # IndividualAnalyzer 생성
            individual_analyzer = IndividualAnalyzer(self.db_manager, None)
            individual_analyzer.pickle_manager = self.pickle_manager
            
            # IndividualDashboard 생성 
            individual_dash = IndividualDashboard(individual_analyzer)
            
            # 날짜별 분석 결과 수집
            daily_results = []
            current_date = start_date
            
            while current_date <= end_date:
                try:
                    self.logger.info(f"  {current_date}: individual_dashboard.execute_analysis 호출")
                    
                    # 먼저 해당 날짜에 데이터가 있는지 확인
                    daily_tag_data = individual_dash.get_daily_tag_data(employee_id, current_date)
                    if daily_tag_data is None or daily_tag_data.empty:
                        self.logger.warning(f"  {current_date}: 해당 날짜에 태그 데이터가 없습니다")
                        continue
                    
                    self.logger.info(f"  {current_date}: 태그 데이터 {len(daily_tag_data)}건 발견")
                    
                    # individual_dashboard의 execute_analysis 메서드 호출 
                    # 반드시 employee_id와 selected_date를 설정해야 meal_data를 제대로 가져올 수 있음
                    self.logger.info(f"  {current_date}: execute_analysis 호출 전 파라미터: employee_id={employee_id}, selected_date={current_date}")
                    analysis_result = individual_dash.execute_analysis(
                        employee_id=employee_id,
                        selected_date=current_date,
                        return_data=True  # 데이터만 반환, UI 렌더링 안함
                    )
                    
                    self.logger.info(f"  {current_date}: analysis_result 타입: {type(analysis_result)}")
                    if analysis_result:
                        self.logger.info(f"  {current_date}: analysis_result 키들: {list(analysis_result.keys()) if isinstance(analysis_result, dict) else 'dict가 아님'}")
                        # 분석 결과를 DB 저장용 형식으로 변환
                        db_result = self._convert_to_db_format(analysis_result, employee_id, current_date)
                        if db_result:
                            daily_results.append(db_result)
                            self.logger.info(f"  {current_date}: 분석 완료 (DB 결과: {db_result.keys()})")
                        else:
                            self.logger.warning(f"  {current_date}: _convert_to_db_format 결과 없음")
                    else:
                        self.logger.warning(f"  {current_date}: analysis_result가 None 또는 빈 값")
                        # None이 반환된 이유를 더 자세히 조사
                        self.logger.info(f"  {current_date}: 직접 analyze_daily_data 호출 시도")
                        try:
                            # 먼저 meal_data가 있는지 확인
                            meal_data = individual_dash.get_meal_data(employee_id, current_date)
                            if meal_data is not None and not meal_data.empty:
                                self.logger.info(f"  {current_date}: meal_data {len(meal_data)}건 발견")
                            else:
                                self.logger.info(f"  {current_date}: meal_data 없음")
                            
                            classified_data = individual_dash.classify_activities(daily_tag_data, employee_id, current_date)
                            self.logger.info(f"  {current_date}: classify_activities 결과: {len(classified_data) if classified_data is not None else 0}건")
                            
                            if classified_data is not None and not classified_data.empty:
                                # M1, M2 태그 확인
                                m1_count = len(classified_data[classified_data.get('Tag_Code', '') == 'M1'])
                                m2_count = len(classified_data[classified_data.get('Tag_Code', '') == 'M2'])
                                meal_activities = len(classified_data[classified_data.get('activity_code', '').isin(['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL'])])
                                self.logger.info(f"  {current_date}: M1 태그: {m1_count}건, M2 태그: {m2_count}건, 식사 활동: {meal_activities}건")
                                
                                analysis_result = individual_dash.analyze_daily_data(employee_id, current_date, classified_data)
                                self.logger.info(f"  {current_date}: analyze_daily_data 결과: {type(analysis_result)}")
                                
                                if analysis_result:
                                    self.logger.info(f"  {current_date}: analysis_result 키들: {list(analysis_result.keys())}")
                                    
                                    # 식사 관련 데이터 확인
                                    if 'activity_summary' in analysis_result:
                                        act_sum = analysis_result['activity_summary']
                                        self.logger.info(f"  {current_date}: 식사 활동 - BREAKFAST:{act_sum.get('BREAKFAST',0)}, LUNCH:{act_sum.get('LUNCH',0)}, DINNER:{act_sum.get('DINNER',0)}")
                                    
                                    if 'meal_time_analysis' in analysis_result:
                                        meal_analysis = analysis_result['meal_time_analysis']
                                        self.logger.info(f"  {current_date}: meal_time_analysis: {meal_analysis}")
                                    
                                    db_result = self._convert_to_db_format(analysis_result, employee_id, current_date)
                                    if db_result:
                                        daily_results.append(db_result)
                                        self.logger.info(f"  {current_date}: 직접 호출로 분석 완료")
                                else:
                                    self.logger.warning(f"  {current_date}: analyze_daily_data가 None 반환")
                        except Exception as direct_e:
                            self.logger.error(f"  {current_date}: 직접 호출도 실패: {direct_e}")
                            import traceback
                            self.logger.error(f"  {current_date}: 직접 호출 스택 트레이스:\n{traceback.format_exc()}")
                    
                except Exception as e:
                    self.logger.error(f"  {current_date} 분석 실패: {e}")
                    import traceback
                    self.logger.error(f"  {current_date} 전체 스택 트레이스:\n{traceback.format_exc()}")
                
                current_date += timedelta(days=1)
            
            self.logger.info(f"직원 {employee_id}: {len(daily_results)}일치 데이터 분석 완료")
            return daily_results if daily_results else None
            
        except Exception as e:
            self.logger.error(f"직원 {employee_id} 분석 실패: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None
    
    def _convert_to_db_format(self, analysis_result, employee_id, work_date):
        """individual_dashboard의 분석 결과를 DB 저장 형식으로 변환"""
        try:
            # 디버깅을 위한 로그
            self.logger.info(f"분석 결과 구조 - 직원 {employee_id}:")
            self.logger.info(f"  전체 키들: {list(analysis_result.keys())}")
            
            # work_time_analysis에서 데이터 추출
            work_analysis = analysis_result.get('work_time_analysis', {})
            activity_summary = analysis_result.get('activity_summary', {})
            meal_analysis = analysis_result.get('meal_time_analysis', {})
            
            # 디버깅 정보
            self.logger.info(f"  work_analysis 키들: {list(work_analysis.keys()) if work_analysis else '없음'}")
            self.logger.info(f"  activity_summary 키들: {list(activity_summary.keys()) if activity_summary else '없음'}")
            self.logger.info(f"  meal_analysis 키들: {list(meal_analysis.keys()) if meal_analysis else '없음'}")
            
            if activity_summary:
                self.logger.info(f"  activity_summary 값들: {activity_summary}")
            if meal_analysis:
                self.logger.info(f"  meal_analysis 값들: {meal_analysis}")
            
            # 근태 시간과 실제 작업 시간
            attendance_hours = work_analysis.get('claimed_work_hours', 0)
            actual_work_hours = work_analysis.get('actual_work_hours', 0)
            
            # 활동별 시간 계산 (분 -> 시간)
            meeting_hours = activity_summary.get('MEETING', 0) / 60
            movement_hours = activity_summary.get('MOVEMENT', 0) / 60
            rest_hours = (activity_summary.get('REST', 0) + activity_summary.get('IDLE', 0)) / 60
            
            # 식사 시간 - 개인별 분석과 동일한 방식으로 meal_data에서 직접 계산
            # 1. activity_summary에서 직접
            breakfast_hours = activity_summary.get('BREAKFAST', 0) / 60
            lunch_hours = activity_summary.get('LUNCH', 0) / 60  
            dinner_hours = activity_summary.get('DINNER', 0) / 60
            midnight_meal_hours = activity_summary.get('MIDNIGHT_MEAL', 0) / 60
            
            # 2. meal_data 테이블에서 직접 계산 (개인별 분석 방식과 동일)
            try:
                from .individual_dashboard import IndividualDashboard
                from src.analysis.individual_analyzer import IndividualAnalyzer
                
                # IndividualDashboard 인스턴스 생성 (이미 생성되어 있다면 재사용)
                individual_analyzer = IndividualAnalyzer(self.db_manager, None)
                individual_analyzer.pickle_manager = self.pickle_manager
                individual_dash = IndividualDashboard(individual_analyzer)
                
                # meal_data에서 직접 식사 데이터 가져오기
                meal_data = individual_dash.get_meal_data(employee_id, work_date)
                if meal_data is not None and not meal_data.empty:
                    self.logger.info(f"  meal_data에서 {len(meal_data)}건의 식사 데이터 발견")
                    
                    # 실제 식사별로 시간 계산 (개인별 분석과 동일한 로직)
                    calculated_meal_minutes = 0
                    date_column = '취식일시' if '취식일시' in meal_data.columns else 'meal_datetime'
                    
                    for _, meal in meal_data.iterrows():
                        meal_type = meal.get('식사대분류', meal.get('meal_category', ''))
                        배식구 = meal.get('배식구', '')
                        테이크아웃 = meal.get('테이크아웃', '')
                        
                        # 배식구 기준 테이크아웃 판단
                        is_takeout = (테이크아웃 == 'Y') or ('테이크아웃' in str(배식구))
                        
                        if is_takeout:
                            # 테이크아웃은 10분 고정
                            calculated_meal_minutes += 10
                        else:
                            # 현장 식사는 30분 기본, 야식은 20분
                            if meal_type == '야식':
                                calculated_meal_minutes += 20
                            else:
                                calculated_meal_minutes += 30
                    
                    if calculated_meal_minutes > 0:
                        meal_hours = calculated_meal_minutes / 60
                        self.logger.info(f"  meal_data에서 직접 계산한 식사시간: {calculated_meal_minutes}분 ({meal_hours:.1f}시간)")
                    else:
                        # activity_summary에서 계산
                        meal_hours = breakfast_hours + lunch_hours + dinner_hours + midnight_meal_hours
                        self.logger.info(f"  activity_summary에서 계산한 식사시간: {meal_hours:.1f}시간")
                else:
                    # meal_data가 없으면 activity_summary에서 계산
                    meal_hours = breakfast_hours + lunch_hours + dinner_hours + midnight_meal_hours
                    self.logger.info(f"  meal_data 없음 - activity_summary에서 계산한 식사시간: {meal_hours:.1f}시간")
            except Exception as meal_e:
                self.logger.warning(f"  meal_data 계산 실패: {meal_e}")
                # activity_summary에서 계산
                meal_hours = breakfast_hours + lunch_hours + dinner_hours + midnight_meal_hours
                self.logger.info(f"  meal_data 오류로 activity_summary에서 계산한 식사시간: {meal_hours:.1f}시간")
            
            # 3. meal_time_analysis에서 시도 (보조)
            if meal_analysis and 'total_meal_time' in meal_analysis:
                total_meal_minutes = meal_analysis.get('total_meal_time', 0)
                if total_meal_minutes > 0:
                    meal_hours_from_analysis = total_meal_minutes / 60
                    self.logger.info(f"  meal_analysis에서 식사시간: {total_meal_minutes}분 ({meal_hours_from_analysis:.1f}시간)")
                    # 더 높은 값을 선택 (데이터 누락 방지)
                    if meal_hours_from_analysis > meal_hours:
                        meal_hours = meal_hours_from_analysis
            
            # 4. 개별 식사 패턴에서 시도 (meal_time_analysis 내부)
            if meal_analysis and 'meal_patterns' in meal_analysis:
                meal_patterns = meal_analysis['meal_patterns']
                total_meal_from_patterns = 0
                for meal_type, pattern in meal_patterns.items():
                    if isinstance(pattern, dict) and 'avg_duration' in pattern and 'frequency' in pattern:
                        total_meal_from_patterns += pattern['avg_duration'] * pattern['frequency']
                if total_meal_from_patterns > 0:
                    meal_hours_from_patterns = total_meal_from_patterns / 60
                    self.logger.info(f"  meal_patterns에서 계산한 식사시간: {total_meal_from_patterns}분 ({meal_hours_from_patterns:.1f}시간)")
                    # 더 높은 값을 선택 (데이터 누락 방지)
                    if meal_hours_from_patterns > meal_hours:
                        meal_hours = meal_hours_from_patterns
            
            # 데이터 신뢰도
            data_reliability = work_analysis.get('confidence_score', 0)
            if data_reliability == 0:
                # 태그 수 기반으로 계산
                total_tags = analysis_result.get('total_tags', 0)
                data_reliability = min(100, (total_tags / 80) * 100)
            
            # 효율성 계산
            work_efficiency = 0
            if attendance_hours > 0:
                work_efficiency = (actual_work_hours / attendance_hours) * 100
            
            return {
                'employee_id': employee_id,
                'analysis_date': work_date,
                'attendance_hours': attendance_hours,
                'actual_work_hours': actual_work_hours,
                'work_estimation_rate': work_efficiency,
                'meeting_time': meeting_hours,  # 시간 단위로 통일
                'meal_time': meal_hours,
                'movement_time': movement_hours,
                'rest_time': rest_hours,
                'breakfast_time': breakfast_hours,
                'lunch_time': lunch_hours,
                'dinner_time': dinner_hours,
                'midnight_meal_time': midnight_meal_hours,
                'shift_type': work_analysis.get('shift_type', '주간'),
                'cross_day_flag': work_analysis.get('cross_day', False),
                'data_reliability': data_reliability,
                'tag_count': analysis_result.get('total_tags', 0),
                'data_completeness': data_reliability,
                'work_efficiency': work_efficiency,
                'productivity_score': min(100, (actual_work_hours / 8) * 100) if actual_work_hours > 0 else 0
            }
            
        except Exception as e:
            self.logger.error(f"결과 변환 실패: {e}")
            return None
    
    # 기존 코드는 더 이상 사용하지 않음 - 삭제 예정
    def _analyze_employee_old(self, employee_id: str, start_date, end_date):
        """이전 버전 - 삭제 예정"""
        # 이 함수는 더 이상 사용되지 않습니다
        # _analyze_employee 함수를 사용하세요
        pass
    
    def _calculate_daily_metrics(self, employee_id, work_date, tag_data, claim_data, meal_data, emp_info):
        """일일 메트릭 계산 - individual_dashboard의 로직 사용"""
        try:
            # 디버깅 로그
            self.logger.debug(f"메트릭 계산 시작: {employee_id} - {work_date}")
            self.logger.debug(f"  tag_data: {len(tag_data) if tag_data is not None else 0}개")
            self.logger.debug(f"  claim_data type: {type(claim_data)}")
            # 출퇴근 시간 찾기
            first_in = None
            last_out = None
            
            if not tag_data.empty:
                sorted_tags = tag_data.sort_values('datetime')
                
                # 출근 시간 (첫 입문 또는 첫 태그)
                in_tags = sorted_tags[sorted_tags['INOUT_GB'] == '입문'] if 'INOUT_GB' in sorted_tags.columns else pd.DataFrame()
                if not in_tags.empty:
                    first_in = pd.to_datetime(in_tags.iloc[0]['datetime'])
                elif len(sorted_tags) > 0:
                    first_in = pd.to_datetime(sorted_tags.iloc[0]['datetime'])
                
                # 퇴근 시간 (마지막 출문 또는 마지막 태그)
                out_tags = sorted_tags[sorted_tags['INOUT_GB'] == '출문'] if 'INOUT_GB' in sorted_tags.columns else pd.DataFrame()
                if not out_tags.empty:
                    last_out = pd.to_datetime(out_tags.iloc[-1]['datetime'])
                elif len(sorted_tags) > 0:
                    last_out = pd.to_datetime(sorted_tags.iloc[-1]['datetime'])
            
            # 체류시간 계산
            total_hours = 0
            if first_in and last_out:
                total_hours = (last_out - first_in).total_seconds() / 3600
            
            # 근태기록시간 (claim 데이터에서)
            attendance_hours = 0
            if claim_data is not None:
                # claim_data가 Series인 경우
                if isinstance(claim_data, pd.Series):
                    # 가능한 모든 컬럼명 체크
                    possible_columns = ['claimed_work_hours', '실제근무시간', '근무시간', '근태시간', 
                                      'actual_work_hours', 'work_hours', '총근무시간']
                    for col in possible_columns:
                        if col in claim_data and pd.notna(claim_data[col]):
                            try:
                                value = claim_data[col]
                                if isinstance(value, str):
                                    # '11.5h' 또는 '11.5시간' 형태 처리
                                    attendance_hours = float(value.replace('h', '').replace('시간', '').strip())
                                else:
                                    attendance_hours = float(value)
                                if attendance_hours > 0:
                                    self.logger.debug(f"    근태시간 발견 ({col}): {attendance_hours}h")
                                    break
                            except Exception as e:
                                self.logger.debug(f"    {col} 파싱 실패: {e}")
                                continue
                # DataFrame인 경우
                elif isinstance(claim_data, pd.DataFrame) and not claim_data.empty:
                    row = claim_data.iloc[0]
                    possible_columns = ['claimed_work_hours', '실제근무시간', '근무시간', '근태시간', 
                                      'actual_work_hours', 'work_hours', '총근무시간']
                    for col in possible_columns:
                        if col in row and pd.notna(row[col]):
                            try:
                                value = row[col]
                                if isinstance(value, str):
                                    attendance_hours = float(value.replace('h', '').replace('시간', '').strip())
                                else:
                                    attendance_hours = float(value)
                                if attendance_hours > 0:
                                    break
                            except:
                                continue
            
            # 활동별 시간 집계 (태그 기반)
            work_minutes = 0
            meal_minutes = 0
            rest_minutes = 0
            movement_minutes = 0
            meeting_minutes = 0
            
            if not tag_data.empty:
                # 시간 간격 계산
                sorted_tags = tag_data.sort_values('datetime').copy()
                sorted_tags['datetime'] = pd.to_datetime(sorted_tags['datetime'])
                sorted_tags['next_datetime'] = sorted_tags['datetime'].shift(-1)
                sorted_tags['duration_minutes'] = (
                    (sorted_tags['next_datetime'] - sorted_tags['datetime']).dt.total_seconds() / 60
                ).fillna(0)
                
                # 위치별 시간 집계
                for idx, row in sorted_tags.iterrows():
                    duration = row['duration_minutes']
                    location = str(row.get('DR_NM', ''))
                    inout = str(row.get('INOUT_GB', ''))
                    
                    # 식사 판별 (CAFETERIA 또는 식당)
                    if 'CAFETERIA' in location.upper() or '식당' in location:
                        meal_minutes += duration
                    # 회의실 판별
                    elif '회의' in location or 'MEETING' in location.upper():
                        meeting_minutes += duration
                    # 휴게 판별
                    elif '휴게' in location or '화장실' in location or 'REST' in location.upper():
                        rest_minutes += duration
                    # 이동 판별 (짧은 출문)
                    elif inout == '출문' and duration < 15:
                        movement_minutes += duration
                    # 나머지는 작업
                    else:
                        work_minutes += duration
                
                # 최대값 제한 (체류시간 기준)
                total_minutes = total_hours * 60
                if total_minutes > 0:
                    # 각 활동 시간이 체류시간을 초과하지 않도록 조정
                    work_minutes = min(work_minutes, total_minutes * 0.8)  # 최대 80%
                    meal_minutes = min(meal_minutes, 120)  # 최대 2시간
                    rest_minutes = min(rest_minutes, 60)  # 최대 1시간
                    movement_minutes = min(movement_minutes, 60)  # 최대 1시간
                    meeting_minutes = min(meeting_minutes, 240)  # 최대 4시간
            
            # 시간을 시간 단위로 변환
            actual_work_hours = work_minutes / 60
            meal_hours = meal_minutes / 60
            rest_hours = rest_minutes / 60
            movement_hours = movement_minutes / 60
            meeting_hours = meeting_minutes / 60
            
            # 식사 세부 시간 (meal_data에서)
            breakfast_time = 0
            lunch_time = 0
            dinner_time = 0
            midnight_meal_time = 0
            
            if meal_data is not None and isinstance(meal_data, pd.DataFrame) and not meal_data.empty:
                for _, meal in meal_data.iterrows():
                    meal_type = meal.get('meal_category', meal.get('식사대분류', ''))
                    배식구 = meal.get('배식구', '')
                    is_takeout = 'takeout' in str(배식구).lower() or '테이크아웃' in str(배식구)
                    
                    # 테이크아웃은 10분, 일반은 30분
                    meal_duration = 10 if is_takeout else 30
                    
                    if '조식' in meal_type or 'breakfast' in meal_type.lower():
                        breakfast_time += meal_duration
                    elif '중식' in meal_type or 'lunch' in meal_type.lower():
                        lunch_time += meal_duration
                    elif '석식' in meal_type or 'dinner' in meal_type.lower():
                        dinner_time += meal_duration
                    elif '야식' in meal_type or 'midnight' in meal_type.lower():
                        midnight_meal_time += meal_duration
                
                # 실제 식사 데이터가 있으면 그것을 사용
                if breakfast_time + lunch_time + dinner_time + midnight_meal_time > 0:
                    meal_hours = (breakfast_time + lunch_time + dinner_time + midnight_meal_time) / 60
            
            # 분을 시간으로 변환
            breakfast_hours = breakfast_time / 60
            lunch_hours = lunch_time / 60
            dinner_hours = dinner_time / 60
            midnight_meal_hours = midnight_meal_time / 60
            
            # 작업시간 추정율
            work_estimation_rate = 0
            if attendance_hours > 0:
                work_estimation_rate = (actual_work_hours / attendance_hours) * 100
            
            # 데이터 신뢰도 (태그 수 기반)
            tag_count = len(tag_data)
            # 하루 8시간 근무 기준으로 5분마다 태그가 있으면 96개
            # 80개 이상이면 100%
            data_reliability = min(100, (tag_count / 80) * 100)
            
            # 데이터 완전성
            data_completeness = min(100, (tag_count / 50) * 100)  # 50개 태그를 100%로
            
            # 업무 효율성
            work_efficiency = work_estimation_rate
            
            # 생산성 점수 (실제 작업시간 기준)
            productivity_score = min(100, (actual_work_hours / 8) * 100) if actual_work_hours > 0 else 0
            
            # 교대 근무 정보
            shift_type = '주간'  # 기본값
            cross_day_flag = False
            
            if first_in and last_out:
                # 야간 근무 판별 (20시 이후 출근 또는 8시 이전 퇴근)
                if first_in.hour >= 20 or last_out.hour <= 8:
                    shift_type = '야간'
                # 날짜 교차 판별
                if first_in.date() != last_out.date():
                    cross_day_flag = True
            
            # 결과 반환
            return {
                'employee_id': employee_id,
                'employee_name': emp_info.get('name', emp_info.get('성명', '')) if emp_info is not None else '',
                'department': emp_info.get('dept_name', emp_info.get('부서명', '')) if emp_info is not None else '',
                'center': emp_info.get('center', emp_info.get('센터', '')) if emp_info is not None else '',
                'team': emp_info.get('team', emp_info.get('팀', '')) if emp_info is not None else '',
                'analysis_date': work_date,
                'attendance_hours': attendance_hours,
                'actual_work_hours': actual_work_hours,
                'work_estimation_rate': work_estimation_rate,
                'meeting_hours': meeting_hours,
                'meal_hours': meal_hours,
                'movement_hours': movement_hours,
                'rest_hours': rest_hours,
                'breakfast_time': breakfast_hours,
                'lunch_time': lunch_hours,
                'dinner_time': dinner_hours,
                'midnight_meal_time': midnight_meal_hours,
                'shift_type': shift_type,
                'cross_day_flag': cross_day_flag,
                'data_reliability': data_reliability,
                'tag_count': tag_count,
                'data_completeness': data_completeness,
                'work_efficiency': work_efficiency,
                'productivity_score': productivity_score
            }
            
        except Exception as e:
            self.logger.error(f"일일 메트릭 계산 실패: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None
    
    def _save_employee_analysis(self, analysis_results):
        """분석 결과를 데이터베이스에 저장"""
        session = None
        try:
            from ...database.schema import DailyWorkData
            
            # get_session()이 context manager를 반환하므로 with 문 사용
            with self.db_manager.get_session() as session:
                saved_count = 0
                for result in analysis_results:
                    try:
                        # 기존 데이터 확인 및 업데이트/삽입
                        existing = session.query(DailyWorkData).filter_by(
                            employee_id=result['employee_id'],
                            work_date=result['analysis_date']
                        ).first()
                        
                        if existing:
                            # 업데이트
                            existing.shift_type = result.get('shift_type', '주간')
                            existing.actual_work_time = result.get('actual_work_hours', 0)
                            existing.work_time = result.get('attendance_hours', 0)
                            existing.rest_time = result.get('rest_hours', 0)
                            existing.non_work_time = result.get('rest_hours', 0) + result.get('meal_hours', 0)
                            existing.meal_time = result.get('meal_hours', 0)
                            existing.breakfast_time = result.get('breakfast_time', 0)
                            existing.lunch_time = result.get('lunch_time', 0)
                            existing.dinner_time = result.get('dinner_time', 0)
                            existing.midnight_meal_time = result.get('midnight_meal_time', 0)
                            existing.cross_day_flag = result.get('cross_day_flag', False)
                            existing.efficiency_ratio = result.get('work_efficiency', 0)
                            existing.data_quality_score = result.get('data_reliability', 0)
                            saved_count += 1
                        else:
                            # 새로 삽입
                            daily_data = DailyWorkData(
                                employee_id=result['employee_id'],
                                work_date=result['analysis_date'],
                                shift_type=result.get('shift_type', '주간'),
                                actual_work_time=result.get('actual_work_hours', 0),
                                work_time=result.get('attendance_hours', 0),
                                rest_time=result.get('rest_hours', 0),
                                non_work_time=result.get('rest_hours', 0) + result.get('meal_hours', 0),
                                meal_time=result.get('meal_hours', 0),
                                breakfast_time=result.get('breakfast_time', 0),
                                lunch_time=result.get('lunch_time', 0),
                                dinner_time=result.get('dinner_time', 0),
                                midnight_meal_time=result.get('midnight_meal_time', 0),
                                cross_day_flag=result.get('cross_day_flag', False),
                                efficiency_ratio=result.get('work_efficiency', 0),
                                data_quality_score=result.get('data_reliability', 0)
                            )
                            session.add(daily_data)
                            saved_count += 1
                    except Exception as e:
                        self.logger.error(f"개별 레코드 저장 실패: {e}")
                        import traceback
                        self.logger.error(traceback.format_exc())
                        continue
                
                if saved_count > 0:
                    session.commit()
                    self.logger.info(f"{saved_count}개 레코드 저장 완료")
                
                return True
                
        except Exception as e:
            self.logger.error(f"분석 결과 저장 실패: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False