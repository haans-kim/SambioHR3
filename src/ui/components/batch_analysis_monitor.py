"""
배치 분석 모니터링 UI 컴포넌트
실시간 진행 상황 표시 및 병렬 처리 관리
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, date, timedelta
import time
import threading
from typing import Dict, Any, Optional
import psutil
import logging

from src.analysis.parallel_batch_analyzer import ParallelBatchAnalyzer
from src.database import get_database_manager, get_pickle_manager


class BatchAnalysisMonitor:
    """배치 분석 모니터링 대시보드"""
    
    def __init__(self):
        self.analyzer = None
        self.analysis_thread = None
        self.is_running = False
        
    def render(self):
        """메인 UI 렌더링"""
        st.title("🚀 대규모 배치 분석 모니터")
        
        # 시스템 상태 표시
        self._render_system_status()
        
        # 분석 설정
        with st.container():
            self._render_analysis_settings()
        
        # 실행 컨트롤
        self._render_controls()
        
        # 진행 상황 모니터
        if self.is_running or st.session_state.get('analysis_results'):
            self._render_progress_monitor()
        
        # 결과 표시
        if st.session_state.get('analysis_results'):
            self._render_results()
    
    def _render_system_status(self):
        """시스템 상태 표시"""
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            cpu_count = psutil.cpu_count()
            cpu_percent = psutil.cpu_percent(interval=1)
            st.metric("CPU 코어", f"{cpu_count}개", f"사용률 {cpu_percent}%")
        
        with col2:
            mem = psutil.virtual_memory()
            mem_available = mem.available / (1024**3)
            st.metric("사용 가능 메모리", f"{mem_available:.1f}GB", f"전체 {mem.total/(1024**3):.1f}GB")
        
        with col3:
            # 데이터 상태
            pickle_manager = get_pickle_manager()
            files = pickle_manager.list_pickle_files()
            st.metric("캐시된 데이터", f"{len(files)}개", "준비됨" if files else "없음")
        
        with col4:
            # 예상 처리 속도
            workers = min(cpu_count - 1, 12)
            expected_rate = workers * 0.8  # 워커당 0.8건/초 예상
            st.metric("예상 처리 속도", f"{expected_rate:.1f}건/초", f"워커 {workers}개")
    
    def _render_analysis_settings(self):
        """분석 설정 UI"""
        st.subheader("📋 분석 설정")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 날짜 선택
            analysis_date = st.date_input(
                "분석 날짜",
                value=date.today() - timedelta(days=1),
                key="batch_analysis_date"
            )
            
            # 날짜 범위 옵션
            use_date_range = st.checkbox("날짜 범위 분석")
            
            if use_date_range:
                date_range = st.date_input(
                    "날짜 범위",
                    value=(date.today() - timedelta(days=7), date.today() - timedelta(days=1)),
                    key="batch_date_range"
                )
        
        with col2:
            # 조직 선택
            st.selectbox(
                "센터 선택",
                options=["전체"] + self._get_centers(),
                key="batch_center"
            )
            
            st.selectbox(
                "그룹 선택",
                options=["전체"] + self._get_groups(),
                key="batch_group"
            )
            
            st.selectbox(
                "팀 선택",
                options=["전체"] + self._get_teams(),
                key="batch_team"
            )
        
        # 고급 설정
        with st.expander("⚙️ 고급 설정"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                num_workers = st.slider(
                    "워커 프로세스 수",
                    min_value=1,
                    max_value=psutil.cpu_count(),
                    value=min(psutil.cpu_count() - 1, 12),
                    key="batch_workers"
                )
            
            with col2:
                save_to_db = st.checkbox("DB 저장", value=True, key="batch_save_db")
                
            with col3:
                batch_size = st.number_input(
                    "배치 크기",
                    min_value=10,
                    max_value=1000,
                    value=100,
                    step=10,
                    key="batch_size"
                )
        
        # 예상 소요 시간 계산
        self._calculate_estimated_time()
    
    def _render_controls(self):
        """실행 컨트롤"""
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🚀 분석 시작", type="primary", disabled=self.is_running):
                self._start_analysis()
        
        with col2:
            if st.button("⏸️ 일시 정지", disabled=not self.is_running):
                self._pause_analysis()
        
        with col3:
            if st.button("🛑 중지", disabled=not self.is_running):
                self._stop_analysis()
    
    def _render_progress_monitor(self):
        """진행 상황 모니터"""
        st.subheader("📊 실시간 진행 상황")
        
        # 진행률 표시
        if 'batch_progress' in st.session_state:
            progress = st.session_state.batch_progress
            
            # 전체 진행률
            progress_pct = progress.get('completed', 0) / progress.get('total', 1)
            st.progress(progress_pct)
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("전체", f"{progress.get('total', 0):,}건")
            
            with col2:
                st.metric("완료", f"{progress.get('completed', 0):,}건", 
                         f"{progress_pct*100:.1f}%")
            
            with col3:
                st.metric("성공", f"{progress.get('success', 0):,}건",
                         f"{progress.get('success_rate', 0):.1f}%")
            
            with col4:
                elapsed = progress.get('elapsed_seconds', 0)
                if elapsed > 0:
                    rate = progress.get('completed', 0) / elapsed
                    remaining = (progress.get('total', 0) - progress.get('completed', 0)) / rate if rate > 0 else 0
                    st.metric("남은 시간", f"{remaining/60:.1f}분",
                             f"속도: {rate:.1f}건/초")
        
        # 실시간 차트
        self._render_live_charts()
    
    def _render_live_charts(self):
        """실시간 차트"""
        if 'batch_metrics' not in st.session_state:
            return
        
        metrics = st.session_state.batch_metrics
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 처리 속도 차트
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=metrics.get('timestamps', []),
                y=metrics.get('rates', []),
                mode='lines',
                name='처리 속도',
                line=dict(color='blue', width=2)
            ))
            fig.update_layout(
                title="처리 속도 (건/초)",
                xaxis_title="시간",
                yaxis_title="속도",
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # CPU/메모리 사용률
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=metrics.get('timestamps', []),
                y=metrics.get('cpu_usage', []),
                mode='lines',
                name='CPU',
                line=dict(color='red', width=2)
            ))
            fig.add_trace(go.Scatter(
                x=metrics.get('timestamps', []),
                y=metrics.get('memory_usage', []),
                mode='lines',
                name='메모리',
                line=dict(color='green', width=2)
            ))
            fig.update_layout(
                title="시스템 사용률 (%)",
                xaxis_title="시간",
                yaxis_title="사용률",
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)
    
    def _render_results(self):
        """분석 결과 표시"""
        st.subheader("📈 분석 결과")
        
        results = st.session_state.get('analysis_results', {})
        
        if not results:
            st.info("분석 결과가 없습니다.")
            return
        
        # 요약 정보
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("총 분석", f"{results.get('total_employees', 0):,}명")
        
        with col2:
            st.metric("성공", f"{results.get('analyzed_count', 0):,}명")
        
        with col3:
            st.metric("실패", f"{results.get('error_count', 0):,}명")
        
        with col4:
            st.metric("소요 시간", f"{results.get('elapsed_seconds', 0)/60:.1f}분")
        
        # 평균 지표
        if 'averages' in results:
            st.write("### 평균 지표")
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("평균 효율성", f"{results['averages']['efficiency_ratio']:.1f}%")
            
            with col2:
                st.metric("평균 실근무시간", f"{results['averages']['actual_work_hours']:.1f}시간")
        
        # 상세 결과 다운로드
        if st.button("📥 결과 다운로드"):
            self._download_results(results)
    
    def _start_analysis(self):
        """분석 시작"""
        self.is_running = True
        
        # 설정 가져오기
        analysis_date = st.session_state.batch_analysis_date
        num_workers = st.session_state.batch_workers
        center = st.session_state.batch_center if st.session_state.batch_center != "전체" else None
        group = st.session_state.batch_group if st.session_state.batch_group != "전체" else None
        team = st.session_state.batch_team if st.session_state.batch_team != "전체" else None
        save_to_db = st.session_state.batch_save_db
        
        # 분석기 생성
        self.analyzer = ParallelBatchAnalyzer(num_workers=num_workers)
        
        # 백그라운드 스레드에서 실행
        def run_analysis():
            try:
                # 진행 상황 초기화
                st.session_state.batch_progress = {
                    'total': 0,
                    'completed': 0,
                    'success': 0,
                    'error': 0,
                    'success_rate': 0,
                    'elapsed_seconds': 0
                }
                
                # 분석 실행
                results = self.analyzer.batch_analyze_parallel(
                    analysis_date,
                    center_id=center,
                    group_id=group,
                    team_id=team,
                    save_to_db=save_to_db
                )
                
                # 결과 저장
                st.session_state.analysis_results = results
                
            finally:
                self.is_running = False
        
        self.analysis_thread = threading.Thread(target=run_analysis)
        self.analysis_thread.start()
        
        st.success("분석이 시작되었습니다!")
        st.rerun()
    
    def _pause_analysis(self):
        """분석 일시 정지"""
        # 구현 예정
        st.info("일시 정지 기능은 준비 중입니다.")
    
    def _stop_analysis(self):
        """분석 중지"""
        self.is_running = False
        if self.analyzer:
            # 분석 중지 로직
            pass
        st.warning("분석이 중지되었습니다.")
    
    def _calculate_estimated_time(self):
        """예상 소요 시간 계산"""
        # 직원 수 추정
        pickle_manager = get_pickle_manager()
        org_data = pickle_manager.load_dataframe('organization_data')
        
        if org_data is not None:
            # 필터링된 직원 수
            total_employees = len(org_data)
            
            # 예상 처리 속도 (워커당 0.8건/초)
            workers = st.session_state.get('batch_workers', 12)
            rate = workers * 0.8
            
            estimated_seconds = total_employees / rate
            
            st.info(f"📊 예상: {total_employees:,}명 분석, 약 {estimated_seconds/60:.1f}분 소요")
    
    def _get_centers(self):
        """센터 목록 조회"""
        try:
            pickle_manager = get_pickle_manager()
            org_data = pickle_manager.load_dataframe('organization_data')
            if org_data is not None:
                return sorted(org_data['센터'].unique().tolist())
        except:
            pass
        return []
    
    def _get_groups(self):
        """그룹 목록 조회"""
        try:
            pickle_manager = get_pickle_manager()
            org_data = pickle_manager.load_dataframe('organization_data')
            if org_data is not None:
                center = st.session_state.get('batch_center')
                if center and center != "전체":
                    filtered = org_data[org_data['센터'] == center]
                    return sorted(filtered['그룹'].unique().tolist())
                return sorted(org_data['그룹'].unique().tolist())
        except:
            pass
        return []
    
    def _get_teams(self):
        """팀 목록 조회"""
        try:
            pickle_manager = get_pickle_manager()
            org_data = pickle_manager.load_dataframe('organization_data')
            if org_data is not None:
                group = st.session_state.get('batch_group')
                if group and group != "전체":
                    filtered = org_data[org_data['그룹'] == group]
                    return sorted(filtered['팀'].unique().tolist())
                return sorted(org_data['팀'].unique().tolist())
        except:
            pass
        return []
    
    def _download_results(self, results):
        """결과 다운로드"""
        import json
        
        # JSON으로 변환
        json_str = json.dumps(results, ensure_ascii=False, indent=2)
        
        st.download_button(
            label="JSON 다운로드",
            data=json_str,
            file_name=f"batch_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )