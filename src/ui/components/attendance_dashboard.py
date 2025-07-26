"""
근태 데이터 대시보드 컴포넌트
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import logging

from ...database import get_database_manager

class AttendanceDashboard:
    """근태 데이터 대시보드"""
    
    def __init__(self):
        self.db_manager = get_database_manager()
        self.logger = logging.getLogger(__name__)
    
    def render(self):
        """대시보드 렌더링"""
        st.markdown("### 📋 근태 현황 분석")
        
        # 탭 생성
        tab1, tab2, tab3 = st.tabs(["근태 현황", "부서별 통계", "근태 유형별 분석"])
        
        with tab1:
            self._render_attendance_status()
        
        with tab2:
            self._render_department_stats()
            
        with tab3:
            self._render_attendance_type_analysis()
    
    def _get_attendance_data(self):
        """데이터베이스에서 근태 데이터 조회"""
        try:
            query = """
                SELECT * FROM attendance_data
                ORDER BY start_date DESC
            """
            result = self.db_manager.execute_query(query)
            if result:
                df = pd.DataFrame(result)
                # 날짜 컬럼 datetime으로 변환
                date_columns = ['start_date', 'end_date', 'created_date']
                for col in date_columns:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col])
                return df
            return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"근태 데이터 조회 실패: {e}")
            return pd.DataFrame()
    
    def _render_attendance_status(self):
        """근태 현황 표시"""
        df = self._get_attendance_data()
        
        if df.empty:
            st.info("📊 근태 데이터가 없습니다.")
            return
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_count = len(df)
            st.metric("전체 근태 신청", f"{total_count:,}건")
        
        with col2:
            # 현재 진행 중인 근태 (오늘 날짜가 시작일과 종료일 사이)
            today = pd.Timestamp.now().normalize()
            ongoing = df[(df['start_date'] <= today) & (df['end_date'] >= today)]
            st.metric("현재 진행 중", f"{len(ongoing):,}건")
        
        with col3:
            # 승인 완료된 건수
            approved = df[df['approval_status'] == '완결']
            st.metric("승인 완료", f"{len(approved):,}건")
        
        with col4:
            # 최근 30일 신청 건수
            recent_date = today - timedelta(days=30)
            recent = df[df['created_date'] >= recent_date]
            st.metric("최근 30일 신청", f"{len(recent):,}건")
        
        # 검색 필터
        st.markdown("#### 🔍 검색 필터")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # 부서 선택
            departments = ['전체'] + sorted(df['department_name'].dropna().unique().tolist())
            selected_dept = st.selectbox("부서", departments)
        
        with col2:
            # 근태 유형 선택
            attendance_types = ['전체'] + sorted(df['attendance_name'].dropna().unique().tolist())
            selected_type = st.selectbox("근태 유형", attendance_types)
        
        with col3:
            # 기간 선택
            date_range = st.date_input(
                "기간",
                value=(today - timedelta(days=30), today),
                max_value=today
            )
        
        # 필터링
        filtered_df = df.copy()
        
        if selected_dept != '전체':
            filtered_df = filtered_df[filtered_df['department_name'] == selected_dept]
        
        if selected_type != '전체':
            filtered_df = filtered_df[filtered_df['attendance_name'] == selected_type]
        
        if len(date_range) == 2:
            start_date, end_date = date_range
            filtered_df = filtered_df[
                (filtered_df['start_date'] >= pd.Timestamp(start_date)) &
                (filtered_df['start_date'] <= pd.Timestamp(end_date))
            ]
        
        # 데이터 테이블 표시
        st.markdown(f"#### 📋 근태 신청 목록 ({len(filtered_df):,}건)")
        
        # 표시할 컬럼 선택
        display_columns = [
            'employee_id', 'employee_name', 'department_name', 
            'attendance_name', 'start_date', 'end_date', 
            'attendance_days', 'reason_detail', 'approval_status'
        ]
        
        # 컬럼명 한글화
        column_names = {
            'employee_id': '사번',
            'employee_name': '성명',
            'department_name': '부서',
            'attendance_name': '근태유형',
            'start_date': '시작일',
            'end_date': '종료일',
            'attendance_days': '일수',
            'reason_detail': '사유',
            'approval_status': '상태'
        }
        
        display_df = filtered_df[display_columns].copy()
        display_df.rename(columns=column_names, inplace=True)
        
        # 날짜 포맷 변경
        display_df['시작일'] = display_df['시작일'].dt.strftime('%Y-%m-%d')
        display_df['종료일'] = display_df['종료일'].dt.strftime('%Y-%m-%d')
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            height=400
        )
    
    def _render_department_stats(self):
        """부서별 통계"""
        df = self._get_attendance_data()
        
        if df.empty:
            st.info("📊 근태 데이터가 없습니다.")
            return
        
        # 부서별 근태 신청 건수
        dept_stats = df.groupby('department_name').size().reset_index(name='count')
        dept_stats = dept_stats.sort_values('count', ascending=True)
        
        # 막대 차트
        fig = px.bar(
            dept_stats.tail(20),  # 상위 20개 부서만 표시
            x='count',
            y='department_name',
            orientation='h',
            title='부서별 근태 신청 건수 (상위 20개)',
            labels={'count': '신청 건수', 'department_name': '부서'}
        )
        
        fig.update_layout(height=600)
        st.plotly_chart(fig, use_container_width=True)
        
        # 부서별 근태 유형 분포
        st.markdown("#### 부서별 근태 유형 분포")
        
        selected_dept_for_type = st.selectbox(
            "부서 선택",
            sorted(df['department_name'].dropna().unique().tolist()),
            key='dept_type_dist'
        )
        
        dept_df = df[df['department_name'] == selected_dept_for_type]
        type_dist = dept_df.groupby('attendance_name').size().reset_index(name='count')
        
        # 파이 차트
        fig_pie = px.pie(
            type_dist,
            values='count',
            names='attendance_name',
            title=f'{selected_dept_for_type} 근태 유형 분포'
        )
        
        st.plotly_chart(fig_pie, use_container_width=True)
    
    def _render_attendance_type_analysis(self):
        """근태 유형별 분석"""
        df = self._get_attendance_data()
        
        if df.empty:
            st.info("📊 근태 데이터가 없습니다.")
            return
        
        # 근태 유형별 통계
        type_stats = df.groupby('attendance_name').agg({
            'employee_id': 'count',
            'attendance_days': 'sum'
        }).reset_index()
        
        type_stats.columns = ['근태유형', '신청건수', '총일수']
        type_stats = type_stats.sort_values('신청건수', ascending=False)
        
        # 두 개의 차트를 나란히 표시
        col1, col2 = st.columns(2)
        
        with col1:
            # 근태 유형별 신청 건수
            fig1 = px.bar(
                type_stats.head(10),
                x='신청건수',
                y='근태유형',
                orientation='h',
                title='근태 유형별 신청 건수 (Top 10)',
                text='신청건수'
            )
            fig1.update_traces(texttemplate='%{text}건', textposition='outside')
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            # 근태 유형별 총 일수
            fig2 = px.bar(
                type_stats.head(10),
                x='총일수',
                y='근태유형',
                orientation='h',
                title='근태 유형별 총 일수 (Top 10)',
                text='총일수',
                color='총일수',
                color_continuous_scale='Blues'
            )
            fig2.update_traces(texttemplate='%{text}일', textposition='outside')
            st.plotly_chart(fig2, use_container_width=True)
        
        # 월별 근태 신청 추이
        st.markdown("#### 📈 월별 근태 신청 추이")
        
        # 월별 집계
        df['year_month'] = df['start_date'].dt.to_period('M')
        monthly_stats = df.groupby(['year_month', 'attendance_name']).size().reset_index(name='count')
        monthly_stats['year_month'] = monthly_stats['year_month'].astype(str)
        
        # 주요 근태 유형만 선택 (상위 5개)
        top_types = type_stats.head(5)['근태유형'].tolist()
        monthly_filtered = monthly_stats[monthly_stats['attendance_name'].isin(top_types)]
        
        # 라인 차트
        fig_line = px.line(
            monthly_filtered,
            x='year_month',
            y='count',
            color='attendance_name',
            title='월별 주요 근태 유형 신청 추이',
            labels={'year_month': '년월', 'count': '신청 건수', 'attendance_name': '근태 유형'},
            markers=True
        )
        
        st.plotly_chart(fig_line, use_container_width=True)
        
        # 근태 사유 워드클라우드 (간단한 텍스트 분석)
        st.markdown("#### 💬 주요 근태 사유")
        
        # 근태 사유 텍스트 수집
        reasons = df['reason_detail'].dropna().tolist()
        
        if reasons:
            # 간단한 키워드 추출 (실제로는 워드클라우드 라이브러리 사용 권장)
            from collections import Counter
            import re
            
            # 모든 사유를 하나의 텍스트로 합치고 단어 추출
            all_text = ' '.join(reasons)
            words = re.findall(r'\b[가-힣]+\b', all_text)
            
            # 불용어 제거
            stopwords = ['위해', '인한', '위한', '및', '등', '년', '월', '일', '부탁', '드립니다']
            words = [w for w in words if len(w) > 1 and w not in stopwords]
            
            # 상위 20개 단어
            word_counts = Counter(words).most_common(20)
            
            # 데이터프레임으로 변환
            keyword_df = pd.DataFrame(word_counts, columns=['키워드', '빈도'])
            
            # 막대 차트로 표시
            fig_keywords = px.bar(
                keyword_df,
                x='빈도',
                y='키워드',
                orientation='h',
                title='근태 사유 주요 키워드',
                text='빈도'
            )
            fig_keywords.update_traces(texttemplate='%{text}', textposition='outside')
            st.plotly_chart(fig_keywords, use_container_width=True)