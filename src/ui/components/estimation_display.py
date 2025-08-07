"""
근무시간 추정률 표시 컴포넌트
"""

import streamlit as st
import plotly.graph_objects as go
from typing import Dict, Optional


def render_estimation_metrics(metrics: Dict, work_hours: float = None):
    """
    추정률 메트릭 표시
    
    Args:
        metrics: 추정 지표 딕셔너리
        work_hours: 실제 근무시간
    """
    if not metrics:
        return
    
    # 메인 컨테이너
    with st.container():
        st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 1.5rem;
                    border-radius: 10px;
                    color: white;
                    margin-bottom: 1rem;">
            <h3 style="margin: 0; color: white;">📊 근무시간 추정 신뢰도</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # 추정률과 신뢰구간
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            # 게이지 차트로 추정률 표시
            fig = create_gauge_chart(metrics['estimation_rate'])
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        
        with col2:
            # 추정 타입
            job_type_kr = {
                'production': '🏭 생산직',
                'office': '💼 사무직',
                'unknown': '❓ 미분류'
            }.get(metrics.get('estimation_type', 'unknown'))
            
            st.metric(
                label="근무 유형",
                value=job_type_kr
            )
            
            # 데이터 품질
            quality_score = metrics.get('data_quality_score', 0) * 100
            st.metric(
                label="데이터 품질",
                value=f"{quality_score:.1f}%",
                delta=get_quality_delta(quality_score)
            )
        
        with col3:
            # 신뢰구간
            lower, upper = metrics.get('confidence_interval', (0, 0))
            st.metric(
                label="신뢰구간 (95%)",
                value=f"{lower:.1f}% - {upper:.1f}%"
            )
            
            # 분산
            variance = metrics.get('variance', 0)
            variance_level = "낮음" if variance < 0.02 else "보통" if variance < 0.04 else "높음"
            st.metric(
                label="추정 분산",
                value=variance_level,
                help=f"분산값: {variance:.4f}"
            )
        
        # 품질 세부 항목
        with st.expander("📈 데이터 품질 상세 분석", expanded=False):
            render_quality_breakdown(metrics.get('quality_breakdown', {}))
        
        # 근무시간 추정 범위
        if work_hours is not None:
            render_estimated_hours(metrics, work_hours)


def create_gauge_chart(estimation_rate: float) -> go.Figure:
    """추정률 게이지 차트 생성"""
    
    # 색상 결정
    if estimation_rate >= 90:
        color = "#2E7D32"
    elif estimation_rate >= 80:
        color = "#43A047"
    elif estimation_rate >= 70:
        color = "#FFA726"
    elif estimation_rate >= 60:
        color = "#EF5350"
    else:
        color = "#B71C1C"
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=estimation_rate,
        title={'text': "추정 신뢰도", 'font': {'size': 20}},
        domain={'x': [0, 1], 'y': [0, 1]},
        number={'suffix': "%", 'font': {'size': 40}},
        gauge={
            'axis': {'range': [None, 100], 'tickwidth': 1},
            'bar': {'color': color},
            'steps': [
                {'range': [0, 60], 'color': "#ffebee"},
                {'range': [60, 70], 'color': "#fff3e0"},
                {'range': [70, 80], 'color': "#fff8e1"},
                {'range': [80, 90], 'color': "#f1f8e9"},
                {'range': [90, 100], 'color': "#e8f5e9"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 80
            }
        }
    ))
    
    fig.update_layout(
        height=250,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    
    return fig


def render_quality_breakdown(breakdown: Dict):
    """데이터 품질 세부 항목 표시"""
    if not breakdown:
        st.info("품질 세부 정보가 없습니다.")
        return
    
    # 각 항목을 진행 바로 표시
    quality_items = [
        ('tag_coverage', '태그 커버리지', '시간당 태그 수집 빈도'),
        ('activity_density', '활동 밀도', 'O태그 및 Knox 데이터 비율'),
        ('time_continuity', '시간 연속성', '태그 간 시간 간격 일관성'),
        ('location_diversity', '위치 다양성', '방문 위치의 다양성')
    ]
    
    for key, label, description in quality_items:
        if key in breakdown:
            score = breakdown[key]
            score_pct = score * 100
            
            # 색상 결정
            if score >= 0.8:
                color = "🟢"
            elif score >= 0.6:
                color = "🟡"
            else:
                color = "🔴"
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"{color} **{label}** - {description}")
                st.progress(score)
            with col2:
                st.markdown(f"**{score_pct:.1f}%**")


def render_estimated_hours(metrics: Dict, actual_hours: float):
    """추정 근무시간 범위 표시"""
    lower_rate = metrics['confidence_interval'][0] / 100
    upper_rate = metrics['confidence_interval'][1] / 100
    
    lower_hours = actual_hours * lower_rate
    upper_hours = actual_hours * upper_rate
    
    st.markdown("---")
    st.markdown("### ⏰ 추정 근무시간")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="최소 추정",
            value=f"{lower_hours:.1f}시간",
            help="95% 신뢰수준 하한"
        )
    
    with col2:
        st.metric(
            label="추정 근무시간",
            value=f"{actual_hours:.1f}시간",
            delta=f"±{(upper_hours-lower_hours)/2:.1f}시간"
        )
    
    with col3:
        st.metric(
            label="최대 추정",
            value=f"{upper_hours:.1f}시간",
            help="95% 신뢰수준 상한"
        )
    
    # 시각적 범위 표시
    fig = go.Figure()
    
    # 신뢰구간 박스
    fig.add_trace(go.Box(
        x=[lower_hours, actual_hours, actual_hours, actual_hours, upper_hours],
        name="추정 범위",
        boxmean='sd',
        marker_color='lightblue',
        showlegend=False
    ))
    
    # 실제 값 표시
    fig.add_trace(go.Scatter(
        x=[actual_hours],
        y=[0],
        mode='markers',
        name='추정값',
        marker=dict(size=15, color='red', symbol='diamond'),
        showlegend=False
    ))
    
    fig.update_layout(
        height=150,
        showlegend=False,
        xaxis_title="근무시간 (시간)",
        yaxis_visible=False,
        margin=dict(l=0, r=0, t=20, b=40),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0.05)'
    )
    
    st.plotly_chart(fig, use_container_width=True)


def get_quality_delta(score: float) -> str:
    """품질 점수에 따른 delta 표시"""
    if score >= 80:
        return "우수"
    elif score >= 60:
        return "양호"
    elif score >= 40:
        return "보통"
    else:
        return "개선필요"


def render_recommendations(recommendations: list):
    """개선 권장사항 표시"""
    if not recommendations:
        return
    
    with st.expander("💡 데이터 품질 개선 제안", expanded=False):
        for rec in recommendations:
            st.markdown(f"• {rec}")