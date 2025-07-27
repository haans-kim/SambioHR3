"""
재사용 가능한 커스텀 UI 컴포넌트
"""

import streamlit as st
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

class CustomComponents:
    """커스텀 UI 컴포넌트 모음"""
    
    @staticmethod
    def metric_card(value: str, label: str, sublabel: str = "", 
                   delta: Optional[str] = None, delta_color: str = "normal"):
        """스타일링된 메트릭 카드"""
        delta_html = ""
        if delta:
            color = {"normal": "#10B981", "inverse": "#EF4444"}.get(delta_color, "#10B981")
            delta_html = f'<div style="color: {color}; font-size: 0.875rem; margin-top: 0.25rem;">{delta}</div>'
        
        html = f"""
        <div class="metric-card">
            <div class="metric-value">{value}</div>
            <div class="metric-label">{label}</div>
            {f'<div class="metric-sublabel">{sublabel}</div>' if sublabel else ''}
            {delta_html}
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)
    
    @staticmethod
    def stats_grid(stats: List[Dict[str, Any]]):
        """통계 그리드 레이아웃"""
        st.markdown('<div class="stats-grid">', unsafe_allow_html=True)
        
        cols = st.columns(len(stats))
        for i, (col, stat) in enumerate(zip(cols, stats)):
            with col:
                CustomComponents.metric_card(
                    value=stat['value'],
                    label=stat['label'],
                    sublabel=stat.get('sublabel', ''),
                    delta=stat.get('delta'),
                    delta_color=stat.get('delta_color', 'normal')
                )
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    @staticmethod
    def card_container(title: str, content_func, icon: str = ""):
        """카드 스타일 컨테이너"""
        st.markdown(f"""
        <div class="card fade-in">
            <h3>{icon} {title}</h3>
        """, unsafe_allow_html=True)
        
        content_func()
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    @staticmethod
    def info_box(message: str, type: str = "info"):
        """정보 박스 (success, warning, error, info)"""
        st.markdown(f"""
        <div class="{type}-box fade-in">
            {message}
        </div>
        """, unsafe_allow_html=True)
    
    @staticmethod
    def progress_bar(value: float, label: str = "", max_value: float = 100):
        """커스텀 프로그레스 바"""
        percentage = (value / max_value) * 100
        
        html = f"""
        <div style="margin-bottom: 1rem;">
            {f'<div style="font-size: 0.875rem; color: var(--color-text-secondary); margin-bottom: 0.25rem;">{label}</div>' if label else ''}
            <div style="background-color: var(--color-bg-tertiary); border-radius: 9999px; height: 8px; overflow: hidden;">
                <div style="background-color: var(--color-primary); width: {percentage}%; height: 100%; transition: width 0.5s ease-out;"></div>
            </div>
            <div style="font-size: 0.75rem; color: var(--color-text-muted); margin-top: 0.25rem; text-align: right;">{value:.1f} / {max_value}</div>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)
    
    @staticmethod
    def timeline_chart(data: pd.DataFrame, title: str = "활동 타임라인"):
        """향상된 타임라인 차트"""
        fig = go.Figure()
        
        # 색상 매핑
        color_map = {
            'WORK': '#2E86AB',
            'MEETING': '#8B5CF6',
            'MEAL': '#F59E0B',
            'REST': '#10B981',
            'MOVEMENT': '#3B82F6',
            'IDLE': '#9CA3AF'
        }
        
        # 활동별로 trace 추가
        for activity in data['activity_code'].unique():
            activity_data = data[data['activity_code'] == activity]
            
            fig.add_trace(go.Scatter(
                x=activity_data['datetime'],
                y=[1] * len(activity_data),
                mode='markers',
                name=activity,
                marker=dict(
                    size=10,
                    color=color_map.get(activity, '#6B7280'),
                    symbol='square'
                ),
                hovertemplate='<b>%{text}</b><br>시간: %{x}<extra></extra>',
                text=activity_data['location']
            ))
        
        fig.update_layout(
            title=title,
            xaxis=dict(
                title="시간",
                type='date',
                tickformat='%H:%M'
            ),
            yaxis=dict(
                visible=False,
                range=[0, 2]
            ),
            height=200,
            margin=dict(l=0, r=0, t=40, b=40),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        
        return fig
    
    @staticmethod
    def donut_chart(values: List[float], labels: List[str], title: str = "", 
                   colors: Optional[List[str]] = None):
        """도넛 차트"""
        if colors is None:
            colors = ['#2E86AB', '#8B5CF6', '#F59E0B', '#10B981', '#3B82F6', '#9CA3AF']
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=.6,
            marker=dict(colors=colors),
            textinfo='label+percent',
            textposition='outside',
            hovertemplate='<b>%{label}</b><br>%{value:.1f}<br>%{percent}<extra></extra>'
        )])
        
        fig.update_layout(
            title=title,
            showlegend=False,
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        
        return fig
    
    @staticmethod
    def activity_summary_cards(activity_summary: Dict[str, float]):
        """활동 요약 카드 그리드"""
        # 활동 코드별 설정
        activity_config = {
            'WORK': {'label': '작업시간', 'icon': '💼', 'color': '#2E86AB'},
            'MEETING': {'label': '회의시간', 'icon': '👥', 'color': '#8B5CF6'},
            'MEAL': {'label': '식사시간', 'icon': '🍽️', 'color': '#F59E0B'},
            'REST': {'label': '휴식시간', 'icon': '☕', 'color': '#10B981'},
            'MOVEMENT': {'label': '이동시간', 'icon': '🚶', 'color': '#3B82F6'},
            'IDLE': {'label': '대기시간', 'icon': '⏸️', 'color': '#9CA3AF'}
        }
        
        # 총 시간 계산
        total_minutes = sum(activity_summary.values())
        
        # 카드 생성
        cols = st.columns(3)
        for i, (activity, minutes) in enumerate(activity_summary.items()):
            if activity in activity_config:
                config = activity_config[activity]
                hours = minutes / 60
                percentage = (minutes / total_minutes * 100) if total_minutes > 0 else 0
                
                with cols[i % 3]:
                    st.markdown(f"""
                    <div class="metric-card" style="border-left: 4px solid {config['color']};">
                        <div style="display: flex; align-items: center; justify-content: space-between;">
                            <div>
                                <div class="metric-value" style="color: {config['color']};">
                                    {hours:.1f}h
                                </div>
                                <div class="metric-label">
                                    {config['icon']} {config['label']}
                                </div>
                            </div>
                            <div style="font-size: 1.25rem; color: var(--color-text-muted);">
                                {percentage:.1f}%
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
    
    @staticmethod
    def expandable_section(title: str, content_func, expanded: bool = False):
        """확장 가능한 섹션"""
        with st.expander(title, expanded=expanded):
            content_func()
    
    @staticmethod
    def styled_dataframe(df: pd.DataFrame, height: Optional[int] = None):
        """스타일링된 데이터프레임"""
        # 스타일 적용
        styled_df = df.style.set_properties(**{
            'background-color': 'var(--color-bg-card)',
            'color': 'var(--color-text-primary)',
            'border': '1px solid var(--color-border-primary)'
        })
        
        # 헤더 스타일
        styled_df = styled_df.set_table_styles([
            {'selector': 'thead', 'props': [('background-color', 'var(--color-bg-secondary)')]},
            {'selector': 'tbody tr:hover', 'props': [('background-color', 'var(--color-bg-hover)')]}
        ])
        
        if height:
            st.dataframe(styled_df, height=height, use_container_width=True)
        else:
            st.dataframe(styled_df, use_container_width=True)
    
    @staticmethod
    def create_comparison_chart(data1: Dict[str, float], data2: Dict[str, float], 
                               label1: str, label2: str, title: str):
        """비교 차트 생성"""
        categories = list(set(data1.keys()) | set(data2.keys()))
        values1 = [data1.get(cat, 0) for cat in categories]
        values2 = [data2.get(cat, 0) for cat in categories]
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            name=label1,
            x=categories,
            y=values1,
            marker_color='#2E86AB'
        ))
        
        fig.add_trace(go.Bar(
            name=label2,
            x=categories,
            y=values2,
            marker_color='#8B5CF6'
        ))
        
        fig.update_layout(
            title=title,
            xaxis_tickangle=-45,
            barmode='group',
            height=400,
            margin=dict(l=40, r=40, t=60, b=80),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        return fig