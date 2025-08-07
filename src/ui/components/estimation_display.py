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
        <div style="background: #f8f9fa;
                    border-left: 4px solid #0066cc;
                    padding: 1rem 1.5rem;
                    margin-bottom: 1rem;">
            <h3 style="margin: 0; color: #333; font-weight: 500;">
                <span style="color: #0066cc; margin-right: 8px;">▎</span>
                근무시간 추정 신뢰도
            </h3>
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
        with st.expander("데이터 품질 상세 분석", expanded=False):
            render_quality_breakdown(metrics.get('quality_breakdown', {}))
        
        # 근무시간 추정 범위
        if work_hours is not None:
            render_estimated_hours(metrics, work_hours)


def create_gauge_chart(estimation_rate: float) -> go.Figure:
    """추정률 게이지 차트 생성"""
    
    # 색상 결정 (비즈니스 스타일)
    if estimation_rate >= 90:
        color = "#0066cc"  # 진한 파랑 (매우 신뢰)
    elif estimation_rate >= 80:
        color = "#0099cc"  # 파랑 (신뢰)
    elif estimation_rate >= 70:
        color = "#66b3ff"  # 연한 파랑 (양호)
    elif estimation_rate >= 60:
        color = "#ff9933"  # 주황 (주의)
    else:
        color = "#cc3333"  # 빨강 (위험)
    
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
                {'range': [0, 60], 'color': "#f5f5f5"},
                {'range': [60, 70], 'color': "#f0f0f0"},
                {'range': [70, 80], 'color': "#e8f0f8"},
                {'range': [80, 90], 'color': "#e0ebf5"},
                {'range': [90, 100], 'color': "#d6e6f5"}
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
                color = "●"  # 높음
                color_style = "color: #0066cc;"
            elif score >= 0.6:
                color = "●"  # 보통
                color_style = "color: #ff9933;"
            else:
                color = "●"  # 낮음
                color_style = "color: #cc3333;"
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"<span style='{color_style}'>{color}</span> **{label}** - {description}", unsafe_allow_html=True)
                st.progress(score)
            with col2:
                st.markdown(f"**{score_pct:.1f}%**")


def render_estimated_hours(metrics: Dict, actual_hours: float):
    """추정 근무시간 범위 표시"""
    estimation_rate = metrics.get('estimation_rate', 50) / 100
    variance = metrics.get('variance', 0.02)
    
    # 정규분포 기반 추정값 계산
    import numpy as np
    estimated_hours = actual_hours * estimation_rate
    std_dev = np.sqrt(variance) * actual_hours
    
    # 68% 신뢰구간 (1 표준편차)
    one_sigma_lower = max(0, estimated_hours - std_dev)
    one_sigma_upper = min(actual_hours, estimated_hours + std_dev)
    
    # 95% 신뢰구간 (2 표준편차)
    two_sigma_lower = max(0, estimated_hours - 2*std_dev)
    two_sigma_upper = min(actual_hours, estimated_hours + 2*std_dev)
    
    st.markdown("---")
    st.markdown("""
    <div style="margin-top: 1rem;">
        <h4 style="color: #333; font-weight: 500;">
            <span style="color: #0066cc;">▎</span> 실제 근무시간 추정
        </h4>
    </div>
    """, unsafe_allow_html=True)
    
    # 전체 시간과 추정 시간 구분 표시
    st.info(f"📍 전체 체류시간: {actual_hours:.1f}시간 (출근~퇴근)")
    
    # 사무직 특별 안내
    if metrics.get('estimation_type') == 'office':
        st.info("""
        💼 **사무직 근무 특성 안내**
        - 사무직은 주로 자리에서 PC 작업을 수행하여 이동 태그가 적습니다
        - 표준 근무시간(8시간) 대비 약 82%를 실근무로 추정합니다
        - 점심시간 및 정규 휴식시간은 이미 반영되었습니다
        """)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="예상 범위 (68%)",
            value=f"{one_sigma_lower:.1f}~{one_sigma_upper:.1f}시간",
            help="정규분포 1σ 구간 (68% 확률)"
        )
    
    with col2:
        st.metric(
            label="추정 실근무",
            value=f"{estimated_hours:.1f}시간",
            delta=f"±{std_dev:.1f}시간",
            help="평균값 ± 표준편차"
        )
    
    with col3:
        st.metric(
            label="최대 범위 (95%)",
            value=f"{two_sigma_lower:.1f}~{two_sigma_upper:.1f}시간",
            help="정규분포 2σ 구간 (95% 확률)"
        )
    
    # 정규분포 시각화
    fig = go.Figure()
    
    # 정규분포 곡선 생성
    x_range = np.linspace(max(0, estimated_hours - 4*std_dev), 
                         min(actual_hours, estimated_hours + 4*std_dev), 100)
    y_normal = (1/(std_dev * np.sqrt(2*np.pi))) * np.exp(-0.5*((x_range - estimated_hours)/std_dev)**2)
    
    # 정규분포 곡선
    fig.add_trace(go.Scatter(
        x=x_range,
        y=y_normal,
        mode='lines',
        name='확률분포',
        line=dict(color='#0066cc', width=2),
        fill='tozeroy',
        fillcolor='rgba(0, 102, 204, 0.1)'
    ))
    
    # 1σ 구간 강조
    x_1sigma = x_range[(x_range >= one_sigma_lower) & (x_range <= one_sigma_upper)]
    y_1sigma = (1/(std_dev * np.sqrt(2*np.pi))) * np.exp(-0.5*((x_1sigma - estimated_hours)/std_dev)**2)
    fig.add_trace(go.Scatter(
        x=x_1sigma,
        y=y_1sigma,
        fill='tozeroy',
        fillcolor='rgba(0, 102, 204, 0.3)',
        line=dict(width=0),
        showlegend=False,
        hoverinfo='skip'
    ))
    
    # 추정값 표시
    fig.add_vline(x=estimated_hours, line_dash="solid", line_color="#0066cc",
                  annotation_text=f"추정: {estimated_hours:.1f}h",
                  annotation_position="top")
    
    # 체류시간 표시
    fig.add_vline(x=actual_hours, line_dash="dash", line_color="gray",
                  annotation_text=f"체류: {actual_hours:.1f}h",
                  annotation_position="top right")
    
    fig.update_layout(
        height=200,
        showlegend=False,
        xaxis_title="근무시간 (시간)",
        yaxis_title="확률밀도",
        margin=dict(l=0, r=0, t=40, b=40),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0.02)',
        xaxis=dict(range=[max(0, estimated_hours - 3*std_dev), 
                          min(actual_hours * 1.1, estimated_hours + 3*std_dev)])
    )
    
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})


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
    
    with st.expander("데이터 품질 개선 제안", expanded=False):
        for rec in recommendations:
            st.markdown(f"• {rec}")