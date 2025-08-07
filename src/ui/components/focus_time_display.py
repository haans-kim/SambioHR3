"""
집중근무 시간대 표시 컴포넌트
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, List
import pandas as pd
import numpy as np


def render_focus_time_analysis(focus_data: Dict):
    """
    집중근무 시간대 분석 표시
    
    Args:
        focus_data: 집중 시간대 분석 결과
    """
    if not focus_data:
        st.info("집중근무 시간대 데이터가 없습니다.")
        return
    
    # 헤더
    st.markdown("""
    <div style="background: #f8f9fa;
                border-left: 4px solid #0066cc;
                padding: 1rem 1.5rem;
                margin-bottom: 1rem;">
        <h3 style="margin: 0; color: #333; font-weight: 500;">
            <span style="color: #0066cc; margin-right: 8px;">▎</span>
            집중근무 시간대 분석
        </h3>
    </div>
    """, unsafe_allow_html=True)
    
    # 직군 정보 및 집중도 점수
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        job_type_kr = {
            'production': '🏭 생산직',
            'office': '💼 사무직',
            'shift': '🔄 교대근무',
            'unknown': '❓ 미분류'
        }.get(focus_data.get('job_type', 'unknown'))
        st.metric("근무 유형", job_type_kr)
    
    with col2:
        focus_score = focus_data.get('focus_score', 0)
        focus_level = get_focus_level(focus_score)
        st.metric("집중도 점수", f"{focus_score:.1f}점", delta=focus_level)
    
    with col3:
        pattern = focus_data.get('work_pattern', 'unknown')
        pattern_kr = get_pattern_korean(pattern)
        st.metric("근무 패턴", pattern_kr)
    
    with col4:
        peak_hours = focus_data.get('peak_hours', [])
        if peak_hours:
            peak_str = format_peak_hours(peak_hours)
            st.metric("피크 시간", peak_str)
        else:
            st.metric("피크 시간", "없음")
    
    # 탭 구성
    tab1, tab2, tab3 = st.tabs(["📊 시간대별 활동", "🎯 집중 구간", "📈 패턴 분석"])
    
    with tab1:
        render_hourly_heatmap(focus_data)
    
    with tab2:
        render_concentration_periods(focus_data)
    
    with tab3:
        render_pattern_analysis(focus_data)


def render_hourly_heatmap(focus_data: Dict):
    """시간대별 활동 히트맵"""
    hourly_density = focus_data.get('hourly_density', {})
    
    if not hourly_density:
        st.info("시간대별 활동 데이터가 없습니다.")
        return
    
    # 히트맵 데이터 준비
    hours = list(range(24))
    densities = [hourly_density.get(h, 0) for h in hours]
    
    # 직군별 색상 스키마
    job_type = focus_data.get('job_type', 'unknown')
    if job_type == 'production':
        colorscale = 'Blues'  # 생산직: 파란색
    elif job_type == 'office':
        colorscale = 'Greens'  # 사무직: 초록색
    else:
        colorscale = 'Viridis'  # 기타: 기본
    
    # 히트맵 생성
    fig = go.Figure()
    
    # 막대 그래프로 표현
    colors = []
    for d in densities:
        if d >= 0.7:
            colors.append('#0066cc')  # 높음
        elif d >= 0.4:
            colors.append('#66b3ff')  # 중간
        elif d > 0:
            colors.append('#cce5ff')  # 낮음
        else:
            colors.append('#f0f0f0')  # 없음
    
    fig.add_trace(go.Bar(
        x=hours,
        y=densities,
        marker_color=colors,
        text=[f"{d*100:.0f}%" for d in densities],
        textposition='outside',
        hovertemplate='%{x}시: %{y:.2f}<extra></extra>'
    ))
    
    # 피크 시간대 표시
    peak_hours = focus_data.get('peak_hours', [])
    for hour in peak_hours:
        fig.add_vline(x=hour, line_dash="dash", line_color="red", 
                     opacity=0.3, line_width=1)
    
    # 레이아웃
    fig.update_layout(
        title="시간대별 활동 밀도",
        xaxis_title="시간",
        yaxis_title="활동 밀도",
        xaxis=dict(
            tickmode='linear',
            tick0=0,
            dtick=1,
            ticktext=[f"{h:02d}" for h in hours],
            tickvals=hours
        ),
        yaxis=dict(range=[0, 1.1]),
        height=300,
        margin=dict(l=0, r=0, t=40, b=40),
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 시간대별 설명
    if job_type == 'production':
        st.info("""
        **생산직 특성**
        - 높은 활동 밀도는 장비 조작 및 작업 집중을 의미
        - 일반적으로 오전/오후 작업 시간에 피크 형성
        - 휴식 시간에는 활동이 급격히 감소
        """)
    elif job_type == 'office':
        st.info("""
        **사무직 특성**
        - 활동 밀도가 낮아도 정상 (PC 작업 중심)
        - 회의 시간대에 활동 증가
        - 점심시간 전후로 활동 패턴 변화
        """)


def render_concentration_periods(focus_data: Dict):
    """집중 구간 분석"""
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🎯 연속 집중 구간")
        concentration = focus_data.get('concentration_periods', [])
        
        if concentration:
            for i, period in enumerate(concentration[:5], 1):  # 상위 5개
                start = period['start'].strftime('%H:%M')
                end = period['end'].strftime('%H:%M')
                duration = period.get('duration_hours', 0)
                intensity = period.get('intensity', 0)
                
                # 집중도에 따른 색상
                if intensity >= 0.8:
                    color = "🔴"  # 매우 높음
                elif intensity >= 0.6:
                    color = "🟠"  # 높음
                else:
                    color = "🟡"  # 보통
                
                st.markdown(f"""
                **{color} 구간 {i}**: {start} - {end} ({duration:.1f}시간)
                - 활동 수: {period.get('activities', 0)}개
                - 집중도: {intensity*100:.0f}%
                """)
        else:
            st.info("연속 집중 구간이 감지되지 않았습니다.")
    
    with col2:
        st.subheader("⚠️ 분산/공백 구간")
        distraction = focus_data.get('distraction_periods', [])
        
        if distraction:
            gap_types = {}
            for period in distraction:
                gap_type = period.get('type', 'unknown')
                if gap_type not in gap_types:
                    gap_types[gap_type] = []
                gap_types[gap_type].append(period)
            
            for gap_type, periods in gap_types.items():
                type_kr = {
                    'lunch_break': '🍽️ 점심시간',
                    'short_break': '☕ 짧은 휴식',
                    'medium_break': '🚶 중간 휴식',
                    'long_absence': '❌ 긴 부재'
                }.get(gap_type, '❓ 기타')
                
                total_minutes = sum(p['gap_minutes'] for p in periods)
                st.markdown(f"""
                **{type_kr}**: {len(periods)}회 (총 {total_minutes:.0f}분)
                """)
                
                # 상세 내역 (접기)
                with st.expander(f"{type_kr} 상세"):
                    for period in periods[:3]:  # 상위 3개
                        start = period['start'].strftime('%H:%M')
                        end = period['end'].strftime('%H:%M')
                        gap = period['gap_minutes']
                        st.text(f"  {start} - {end}: {gap:.0f}분")
        else:
            st.success("공백 구간이 없습니다. 연속적인 활동!")


def render_pattern_analysis(focus_data: Dict):
    """패턴 분석 시각화"""
    # 근무 패턴 설명
    pattern = focus_data.get('work_pattern', 'unknown')
    pattern_desc = get_pattern_description(pattern)
    
    st.markdown(f"""
    ### 근무 패턴: {get_pattern_korean(pattern)}
    {pattern_desc}
    """)
    
    # 집중도 게이지
    focus_score = focus_data.get('focus_score', 0)
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=focus_score,
        title={'text': "업무 집중도"},
        domain={'x': [0, 1], 'y': [0, 1]},
        gauge={
            'axis': {'range': [None, 100]},
            'bar': {'color': get_gauge_color(focus_score)},
            'steps': [
                {'range': [0, 20], 'color': '#ffebee'},
                {'range': [20, 40], 'color': '#fff3e0'},
                {'range': [40, 60], 'color': '#fff9c4'},
                {'range': [60, 80], 'color': '#e8f5e9'},
                {'range': [80, 100], 'color': '#e3f2fd'}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 60
            }
        }
    ))
    
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)
    
    # 직군별 인사이트
    job_type = focus_data.get('job_type', 'unknown')
    
    if job_type == 'production':
        st.markdown("""
        ### 💡 생산직 인사이트
        - **높은 집중도 (80점 이상)**: 효율적인 작업 진행, 장비 활용도 높음
        - **중간 집중도 (40-80점)**: 일반적인 작업 패턴, 적절한 휴식
        - **낮은 집중도 (40점 미만)**: 작업 중단 빈번, 개선 필요
        """)
    elif job_type == 'office':
        st.markdown("""
        ### 💡 사무직 인사이트
        - **높은 집중도 (60점 이상)**: 회의/결재 등 활발한 업무 활동
        - **중간 집중도 (30-60점)**: 일반적인 사무 업무 패턴
        - **낮은 집중도 (30점 미만)**: 정상적인 집중 업무 수행 중
        """)
    
    # 개선 제안
    suggestions = get_improvement_suggestions(focus_data)
    if suggestions:
        st.markdown("### 📋 개선 제안")
        for suggestion in suggestions:
            st.markdown(f"- {suggestion}")


def get_focus_level(score: float) -> str:
    """집중도 수준 텍스트"""
    if score >= 80:
        return "⬆️ 매우 높음"
    elif score >= 60:
        return "⬆️ 높음"
    elif score >= 40:
        return "➡️ 보통"
    elif score >= 20:
        return "⬇️ 낮음"
    else:
        return "⬇️ 매우 낮음"


def get_pattern_korean(pattern: str) -> str:
    """패턴 한글 변환"""
    patterns = {
        'regular_day': '정규 주간',
        'night_shift': '야간 교대',
        'extended_hours': '장시간',
        'minimal_activity': '최소 활동',
        'irregular': '불규칙',
        'no_pattern': '패턴 없음'
    }
    return patterns.get(pattern, '알 수 없음')


def get_pattern_description(pattern: str) -> str:
    """패턴 상세 설명"""
    descriptions = {
        'regular_day': '표준 근무 시간(07:00-19:00) 내에서 활동이 집중되어 있습니다.',
        'night_shift': '야간 시간대에 주요 활동이 이루어지는 교대 근무 패턴입니다.',
        'extended_hours': '12시간 이상의 장시간 근무 패턴이 감지되었습니다.',
        'minimal_activity': '활동량이 매우 적어 정확한 패턴 분석이 어렵습니다.',
        'irregular': '일정한 패턴 없이 불규칙한 활동이 감지되었습니다.',
        'no_pattern': '분석 가능한 패턴이 감지되지 않았습니다.'
    }
    return descriptions.get(pattern, '')


def format_peak_hours(hours: List[int]) -> str:
    """피크 시간대 포맷팅"""
    if not hours:
        return "없음"
    
    # 연속된 시간대 그룹화
    groups = []
    current = [hours[0]]
    
    for h in hours[1:]:
        if h == current[-1] + 1:
            current.append(h)
        else:
            groups.append(current)
            current = [h]
    groups.append(current)
    
    # 포맷팅
    formatted = []
    for group in groups:
        if len(group) == 1:
            formatted.append(f"{group[0]:02d}시")
        else:
            formatted.append(f"{group[0]:02d}-{group[-1]:02d}시")
    
    return ", ".join(formatted[:2])  # 상위 2개 그룹만


def get_gauge_color(score: float) -> str:
    """게이지 색상 결정"""
    if score >= 80:
        return '#2e7d32'  # 진한 초록
    elif score >= 60:
        return '#43a047'  # 초록
    elif score >= 40:
        return '#ffa726'  # 주황
    elif score >= 20:
        return '#ef5350'  # 빨강
    else:
        return '#b71c1c'  # 진한 빨강


def get_improvement_suggestions(focus_data: Dict) -> List[str]:
    """개선 제안 생성"""
    suggestions = []
    
    focus_score = focus_data.get('focus_score', 0)
    job_type = focus_data.get('job_type', 'unknown')
    pattern = focus_data.get('work_pattern', 'unknown')
    distraction = focus_data.get('distraction_periods', [])
    
    # 집중도 기반 제안
    if focus_score < 40:
        if job_type == 'production':
            suggestions.append("작업 중단이 빈번합니다. 연속 작업 시간을 늘려보세요.")
        elif job_type == 'office':
            suggestions.append("회의나 협업 활동을 특정 시간대에 집중시켜보세요.")
    
    # 패턴 기반 제안
    if pattern == 'extended_hours':
        suggestions.append("장시간 근무가 감지되었습니다. 적절한 휴식이 필요합니다.")
    elif pattern == 'irregular':
        suggestions.append("불규칙한 근무 패턴입니다. 일정한 루틴 확립이 도움될 수 있습니다.")
    
    # 공백 시간 기반 제안
    long_gaps = [d for d in distraction if d.get('type') == 'long_absence']
    if len(long_gaps) > 2:
        suggestions.append("긴 공백 시간이 자주 발생합니다. 업무 연속성 개선이 필요합니다.")
    
    return suggestions