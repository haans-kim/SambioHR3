"""
테마가 적용된 개인별 대시보드
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from ..styles.style_manager import StyleManager
from .custom_components import CustomComponents
from .individual_dashboard import IndividualDashboard
from ...analysis import IndividualAnalyzer

class StyledIndividualDashboard(IndividualDashboard):
    """스타일이 적용된 개인별 대시보드"""
    
    def __init__(self, analyzer: IndividualAnalyzer):
        super().__init__(analyzer)
        self.style_manager = StyleManager()
        self.components = CustomComponents()
    
    def render(self, employee_id: str, selected_date: datetime.date):
        """스타일이 적용된 대시보드 렌더링"""
        # 상단에 테마 토글 버튼 배치
        col1, col2, col3 = st.columns([8, 2, 1])
        with col2:
            dark_mode = self.style_manager.create_theme_toggle()
        
        # CSS 주입
        self.style_manager.inject_custom_css(dark_mode)
        
        # 데이터 로드
        data = self._load_dashboard_data(employee_id, selected_date)
        
        if data is None:
            self.components.info_box(
                f"{employee_id}의 {selected_date} 데이터가 없습니다.",
                type="warning"
            )
            return
        
        # 상단 요약 통계
        self._render_summary_stats(data)
        
        # 메인 콘텐츠
        tab1, tab2, tab3, tab4 = st.tabs(["📊 활동 분석", "⏱️ 타임라인", "📈 추세 분석", "🎯 상세 정보"])
        
        with tab1:
            self._render_activity_analysis(data)
        
        with tab2:
            self._render_timeline_view(data)
        
        with tab3:
            self._render_trend_analysis(employee_id, selected_date)
        
        with tab4:
            self._render_detailed_info(data)
    
    def _load_dashboard_data(self, employee_id: str, selected_date: datetime.date) -> Optional[Dict]:
        """대시보드 데이터 로드"""
        try:
            # 기본 데이터 가져오기
            daily_data = self.get_daily_tag_data(employee_id, selected_date)
            if daily_data is None or daily_data.empty:
                return None
            
            # 활동 분류
            classified_data = self.classify_activities(daily_data, employee_id, selected_date)
            
            # 작업시간 분석
            work_time_analysis = self.analyzer.analyze_work_time(employee_id, selected_date, selected_date)
            
            # 활동 요약
            activity_summary = self.calculate_activity_summary(classified_data)
            
            # 태그 통계
            tag_stats = self.analyzer.calculate_tag_statistics(classified_data)
            
            return {
                'daily_data': daily_data,
                'classified_data': classified_data,
                'work_time_analysis': work_time_analysis,
                'activity_summary': activity_summary,
                'tag_stats': tag_stats,
                'employee_id': employee_id,
                'date': selected_date
            }
        except Exception as e:
            st.error(f"데이터 로드 중 오류: {str(e)}")
            return None
    
    def _render_summary_stats(self, data: Dict):
        """요약 통계 렌더링"""
        work_analysis = data['work_time_analysis']
        
        # 주요 메트릭
        stats = [
            {
                'value': f"{work_analysis.get('actual_work_hours', 0):.1f}h",
                'label': '실제 업무시간',
                'sublabel': f"체류시간: {work_analysis.get('total_stay_hours', 0):.1f}h",
                'delta': f"효율: {work_analysis.get('efficiency_percentage', 0):.1f}%"
            },
            {
                'value': f"{work_analysis.get('actual_work_hours', 0) - 8:.1f}h",
                'label': '초과/부족 시간',
                'sublabel': '기준: 8시간',
                'delta': '초과' if work_analysis.get('actual_work_hours', 0) > 8 else '부족',
                'delta_color': 'normal' if work_analysis.get('actual_work_hours', 0) > 8 else 'inverse'
            },
            {
                'value': f"{work_analysis.get('confidence_index', 0):.0f}%",
                'label': '데이터 신뢰도',
                'sublabel': '태그 품질'
            },
            {
                'value': f"{len(data['classified_data'])}건",
                'label': '총 활동 기록',
                'sublabel': f"평균 {len(data['classified_data']) / 24:.1f}건/시간"
            }
        ]
        
        self.components.stats_grid(stats)
    
    def _render_activity_analysis(self, data: Dict):
        """활동 분석 렌더링"""
        col1, col2 = st.columns([3, 2])
        
        with col1:
            # 활동별 시간 분포 카드
            st.markdown("<h3>활동별 시간 분포</h3>", unsafe_allow_html=True)
            self.components.activity_summary_cards(data['activity_summary'])
        
        with col2:
            # 도넛 차트
            activities = list(data['activity_summary'].keys())
            values = list(data['activity_summary'].values())
            
            fig = self.components.donut_chart(
                values=values,
                labels=activities,
                title="활동 비율"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    def _render_timeline_view(self, data: Dict):
        """타임라인 뷰 렌더링"""
        # 시간대별 활동 타임라인
        fig = self.components.timeline_chart(
            data['classified_data'],
            title="시간대별 활동 기록"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # 시간대별 상세 분석
        with st.expander("시간대별 상세 분석", expanded=True):
            hourly_analysis = self._calculate_hourly_analysis(data['classified_data'])
            
            cols = st.columns(4)
            periods = [
                ("오전 (6-12시)", range(6, 12)),
                ("오후 (12-18시)", range(12, 18)),
                ("저녁 (18-24시)", range(18, 24)),
                ("새벽 (0-6시)", range(0, 6))
            ]
            
            for col, (period_name, hours) in zip(cols, periods):
                with col:
                    period_data = {k: v for k, v in hourly_analysis.items() if k in hours}
                    total_minutes = sum(period_data.values())
                    
                    self.components.metric_card(
                        value=f"{total_minutes/60:.1f}h",
                        label=period_name,
                        sublabel=f"{len(period_data)}시간 활동"
                    )
    
    def _render_trend_analysis(self, employee_id: str, selected_date: datetime.date):
        """추세 분석 렌더링"""
        # 최근 7일간 데이터 비교
        end_date = selected_date
        start_date = selected_date - timedelta(days=6)
        
        trend_data = []
        for i in range(7):
            date = start_date + timedelta(days=i)
            daily_analysis = self.analyzer.analyze_work_time(employee_id, date, date)
            
            if daily_analysis:
                trend_data.append({
                    'date': date,
                    'work_hours': daily_analysis.get('actual_work_hours', 0),
                    'efficiency': daily_analysis.get('efficiency_percentage', 0),
                    'confidence': daily_analysis.get('confidence_index', 0)
                })
        
        if trend_data:
            df = pd.DataFrame(trend_data)
            
            # 작업시간 추세
            import plotly.graph_objects as go
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(
                x=df['date'],
                y=df['work_hours'],
                mode='lines+markers',
                name='작업시간',
                line=dict(color='#2E86AB', width=3),
                marker=dict(size=8)
            ))
            
            fig1.add_hline(y=8, line_dash="dash", line_color="gray", 
                          annotation_text="기준시간 (8h)")
            
            fig1.update_layout(
                title="주간 작업시간 추세",
                xaxis_title="날짜",
                yaxis_title="시간",
                height=300,
                margin=dict(l=40, r=40, t=60, b=40)
            )
            
            st.plotly_chart(fig1, use_container_width=True)
            
            # 효율성 & 신뢰도 추세
            from plotly.subplots import make_subplots
            fig2 = make_subplots(specs=[[{"secondary_y": True}]])
            
            fig2.add_trace(go.Scatter(
                x=df['date'],
                y=df['efficiency'],
                mode='lines+markers',
                name='효율성',
                line=dict(color='#10B981', width=2)
            ), secondary_y=False)
            
            fig2.add_trace(go.Scatter(
                x=df['date'],
                y=df['confidence'],
                mode='lines+markers',
                name='신뢰도',
                line=dict(color='#8B5CF6', width=2)
            ), secondary_y=True)
            
            fig2.update_layout(
                title="효율성 & 신뢰도 추세",
                height=300,
                margin=dict(l=40, r=40, t=60, b=40)
            )
            
            fig2.update_yaxes(title_text="효율성 (%)", secondary_y=False)
            fig2.update_yaxes(title_text="신뢰도 (%)", secondary_y=True)
            
            st.plotly_chart(fig2, use_container_width=True)
    
    def _render_detailed_info(self, data: Dict):
        """상세 정보 렌더링"""
        # 태그 통계
        with st.expander("태그 통계", expanded=True):
            tag_df = pd.DataFrame([
                {'태그': tag, '개수': count} 
                for tag, count in data['tag_stats'].items()
            ]).sort_values('개수', ascending=False)
            
            self.components.styled_dataframe(tag_df, height=300)
        
        # 장소별 체류 시간
        with st.expander("장소별 체류 시간", expanded=True):
            location_summary = data['classified_data'].groupby('location')['duration_minutes'].sum()
            location_df = pd.DataFrame({
                '장소': location_summary.index,
                '체류시간(분)': location_summary.values,
                '체류시간(시간)': location_summary.values / 60
            }).sort_values('체류시간(분)', ascending=False)
            
            self.components.styled_dataframe(location_df, height=300)
        
        # 원본 데이터 (선택적)
        with st.expander("원본 데이터", expanded=False):
            sample_data = data['classified_data'].head(100)
            self.components.styled_dataframe(sample_data, height=400)
    
    def _calculate_hourly_analysis(self, classified_data: pd.DataFrame) -> Dict[int, float]:
        """시간대별 분석"""
        hourly_minutes = {}
        
        for _, row in classified_data.iterrows():
            hour = row['datetime'].hour
            hourly_minutes[hour] = hourly_minutes.get(hour, 0) + row['duration_minutes']
        
        return hourly_minutes