"""
개선된 Gantt 차트 컴포넌트
활동 타임라인을 좀 더 시각적으로 표현
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta
import streamlit as st

def render_improved_gantt_chart(analysis_result: dict):
    """개선된 활동 타임라인 Gantt 차트"""
    
    segments = analysis_result.get('activity_segments', [])
    if not segments:
        st.info("활동 데이터가 없습니다.")
        return
    
    # # 디버깅: 첫 번째 세그먼트의 confidence 확인 (필요시 주석 해제)
    # if segments:
    #     st.write(f"DEBUG: 첫 번째 세그먼트 confidence: {segments[0].get('confidence', 'NONE')}")
    
    # 활동별 색상 및 정보
    activity_info = {
        'COMMUTE_IN': {'name': '출근', 'color': '#4CAF50', 'y_pos': 7, 'category': 'commute'},
        'WORK_PREPARATION': {'name': '작업준비', 'color': '#8BC34A', 'y_pos': 6, 'category': 'work'},
        'WORK': {'name': '작업중', 'color': '#2196F3', 'y_pos': 5, 'category': 'work'},
        'FOCUSED_WORK': {'name': '집중작업', 'color': '#1976D2', 'y_pos': 5, 'category': 'work'},
        'EQUIPMENT_OPERATION': {'name': '장비작업', 'color': '#0D47A1', 'y_pos': 5, 'category': 'work'},
        'MOVEMENT': {'name': '이동중', 'color': '#00BCD4', 'y_pos': 4, 'category': 'movement'},
        'MEETING': {'name': '회의중', 'color': '#9C27B0', 'y_pos': 3, 'category': 'meeting'},
        'BREAKFAST': {'name': '조식', 'color': '#FF9800', 'y_pos': 2, 'category': 'meal'},
        'LUNCH': {'name': '중식', 'color': '#FF9800', 'y_pos': 2, 'category': 'meal'},
        'DINNER': {'name': '석식', 'color': '#FF9800', 'y_pos': 2, 'category': 'meal'},
        'MIDNIGHT_MEAL': {'name': '야식', 'color': '#FF9800', 'y_pos': 2, 'category': 'meal'},
        'REST': {'name': '휴식', 'color': '#4CAF50', 'y_pos': 1, 'category': 'rest'},
        'FITNESS': {'name': '운동', 'color': '#4CAF50', 'y_pos': 1, 'category': 'rest'},
        'NON_WORK': {'name': '비근무', 'color': '#FF6B6B', 'y_pos': 1, 'category': 'non_work'},
        'COMMUTE_OUT': {'name': '퇴근', 'color': '#F44336', 'y_pos': 0, 'category': 'commute'},
        'UNKNOWN': {'name': '기타', 'color': '#9E9E9E', 'y_pos': 3, 'category': 'other'}
    }
    
    # Y축 레이블
    y_labels = ['퇴근', '휴게', '식사', '회의', '이동', '작업', '준비', '출근']
    
    # work_start와 work_end가 datetime 객체인지 확인
    work_start = analysis_result['work_start']
    work_end = analysis_result['work_end']
    
    # datetime 객체가 아닌 경우 변환
    if isinstance(work_start, str):
        work_start = pd.to_datetime(work_start)
    if isinstance(work_end, str):
        work_end = pd.to_datetime(work_end)
    
    fig = go.Figure()
    
    # 배경 그리드 추가 (시간대별)
    total_hours = int((work_end - work_start).total_seconds() / 3600) + 1
    for i in range(total_hours + 1):
        hour_time = work_start + timedelta(hours=i)
        # 정시는 실선으로, 나머지는 점선으로
        if hour_time.hour % 2 == 0:  # 2시간마다 실선
            fig.add_vline(
                x=hour_time, 
                line_dash="solid", 
                line_color="rgba(0, 0, 0, 0.15)",
                line_width=1
            )
        else:  # 홀수 시간은 점선
            fig.add_vline(
                x=hour_time, 
                line_dash="dot", 
                line_color="rgba(0, 0, 0, 0.1)",
                line_width=1
            )
    
    # 각 세그먼트를 원과 연결선으로 표시
    prev_segment = None
    
    # 디버깅: 출퇴근 활동 확인
    commute_segments = [seg for seg in segments if seg.get('activity_code') in ['COMMUTE_IN', 'COMMUTE_OUT']]
    if commute_segments:
        print(f"출퇴근 세그먼트 발견: {len(commute_segments)}개")
        for seg in commute_segments:
            print(f"  - {seg['start_time']} : {seg['activity_code']} @ {seg.get('location', 'N/A')}")
    
    for i, segment in enumerate(segments):
        if pd.notna(segment['start_time']) and pd.notna(segment['end_time']):
            activity_code = segment.get('activity_code', 'UNKNOWN')
            
            # activity_type을 activity_code로 매핑 (필요시)
            if activity_code in ['work', 'meeting', 'movement', 'rest', 'breakfast', 'lunch', 'dinner', 'midnight_meal', 'commute', 'non_work']:
                # activity_type을 activity_code로 변환
                type_to_code = {
                    'work': 'WORK',
                    'meeting': 'MEETING',
                    'movement': 'MOVEMENT',
                    'rest': 'REST',
                    'breakfast': 'BREAKFAST',
                    'lunch': 'LUNCH',
                    'dinner': 'DINNER',
                    'midnight_meal': 'MIDNIGHT_MEAL',
                    'commute': 'COMMUTE_IN',
                    'non_work': 'NON_WORK'
                }
                activity_code = type_to_code.get(activity_code, activity_code)
            
            activity = activity_info.get(activity_code, activity_info['UNKNOWN'])
            
            # 시작과 끝 시간의 중간점 계산
            mid_time = segment['start_time'] + (segment['end_time'] - segment['start_time']) / 2
            
            # 신뢰도에 따른 투명도 설정
            confidence = segment.get('confidence', 80)
            if isinstance(confidence, str):
                try:
                    confidence = float(confidence)
                except:
                    confidence = 80
            elif pd.isna(confidence):
                confidence = 80
            
            # # 디버깅 (필요시 주석 해제)
            # print(f"Activity: {activity_code}, Confidence: {confidence}")
            
            opacity = 0.4 + (confidence / 100) * 0.6  # 0.4 ~ 1.0
            
            # 테이크아웃 여부 확인 - 여러 방법으로 판단
            is_takeout = segment.get('is_takeout', False)
            # 위치명에 '테이크아웃'이 포함된 경우도 테이크아웃으로 처리
            if not is_takeout and '테이크아웃' in str(segment.get('location', '')):
                is_takeout = True
            
            # 원 추가 (활동 표시)
            # 테이크아웃인 경우 다른 마커 모양과 색상 사용
            if is_takeout and activity['category'] == 'meal':
                marker_symbol = 'diamond'  # 테이크아웃은 다이아몬드
                marker_size = 25
                marker_color = '#FFA726'  # 테이크아웃은 더 밝은 주황색
            else:
                marker_symbol = 'circle'  # 일반 식사는 원
                marker_size = 20
                marker_color = activity['color']  # 일반 색상 사용
                
            fig.add_trace(go.Scatter(
                x=[segment['start_time']],  # 태깅 시점에 마커 표시
                y=[activity['y_pos']],
                mode='markers+text',
                marker=dict(
                    size=marker_size,
                    color=marker_color,
                    opacity=opacity,
                    line=dict(color='white', width=2),
                    symbol=marker_symbol
                ),
                text=f"{confidence:.0f}%" if confidence < 100 else "",
                textposition="top center",
                textfont=dict(size=10, color='red' if confidence < 80 else 'black'),
                hovertemplate=(
                    f"<b>{activity['name']}{' (테이크아웃)' if is_takeout and activity['category'] == 'meal' else ''}</b><br>" +
                    f"시간: {segment['start_time'].strftime('%H:%M')} - {segment['end_time'].strftime('%H:%M')}<br>" +
                    f"위치: {segment.get('location', 'N/A')}<br>" +
                    f"체류: {segment.get('duration_minutes', 0):.0f}분<br>" +
                    f"신뢰도: {confidence}%<extra></extra>"
                ),
                showlegend=False
            ))
            
            # 활동 구간을 막대로 표시
            # 작업 관련 활동은 다음 태그까지 길게 표시
            if activity['category'] == 'work':
                # 다음 세그먼트 확인
                if i < len(segments) - 1:
                    next_segment = segments[i + 1]
                    # 작업 활동은 다음 태그 시작 시점까지 연장
                    extended_end_time = next_segment['start_time']
                else:
                    # 마지막 세그먼트인 경우 원래 종료 시간 사용
                    extended_end_time = segment['end_time']
                
                fig.add_trace(go.Scatter(
                    x=[segment['start_time'], extended_end_time],
                    y=[activity['y_pos'], activity['y_pos']],
                    mode='lines',
                    line=dict(
                        color=activity['color'],
                        width=40,
                        dash='solid'
                    ),
                    opacity=opacity * 0.3,  # 막대는 더 투명하게
                    hoverinfo='skip',
                    showlegend=False
                ))
            else:
                # 작업이 아닌 활동은 기존대로
                fig.add_trace(go.Scatter(
                    x=[segment['start_time'], segment['end_time']],
                    y=[activity['y_pos'], activity['y_pos']],
                    mode='lines',
                    line=dict(
                        color=activity['color'],
                        width=40,
                        dash='solid'
                    ),
                    opacity=opacity * 0.3,  # 막대는 더 투명하게
                    hoverinfo='skip',
                    showlegend=False
                ))
            
            # 이전 활동과 연결선 그리기
            if prev_segment and pd.notna(prev_segment['end_time']):
                prev_activity = activity_info.get(
                    prev_segment.get('activity_code', 'UNKNOWN'), 
                    activity_info['UNKNOWN']
                )
                
                # 현재 활동이 이동인 경우에만 수직선 표시
                if activity['category'] == 'movement' and prev_activity['y_pos'] != activity['y_pos']:
                    # 수직선은 이동 시작 시간에 그림
                    fig.add_trace(go.Scatter(
                        x=[segment['start_time'], segment['start_time']],
                        y=[prev_activity['y_pos'], activity['y_pos']],
                        mode='lines',
                        line=dict(
                            color='gray',
                            width=2,
                            dash='dot'
                        ),
                        opacity=0.7,
                        hoverinfo='skip',
                        showlegend=False
                    ))
            
            prev_segment = segment
    
    # 레전드 추가 (활동 카테고리별)
    legend_added = set()
    for code, info in activity_info.items():
        category = info['category']
        if category not in legend_added and any(seg.get('activity_code') == code for seg in segments):
            fig.add_trace(go.Scatter(
                x=[None],
                y=[None],
                mode='markers',
                marker=dict(size=15, color=info['color']),
                name=info['name'],
                showlegend=True
            ))
            legend_added.add(category)
    
    # 테이크아웃 레전드 추가 (테이크아웃 식사가 있는 경우)
    # 식사 활동 중에서 테이크아웃이 있는 경우만 확인
    has_takeout_meal = any(
        seg.get('is_takeout', False) and 
        seg.get('activity_code', '') in ['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL']
        for seg in segments
    )
    if has_takeout_meal:
        fig.add_trace(go.Scatter(
            x=[None],
            y=[None],
            mode='markers',
            marker=dict(size=15, color='#FFA726', symbol='diamond'),
            name='테이크아웃',
            showlegend=True
        ))
    
    # 레이아웃 설정
    fig.update_layout(
        title={
            'text': f"{analysis_result['employee_id']} 활동 타임라인 ({analysis_result['analysis_date']})",
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 20}
        },
        xaxis=dict(
            title="",
            tickformat='%H:%M',
            dtick=3600000,  # 1시간 간격 (밀리초)
            range=[work_start - timedelta(minutes=30), work_end + timedelta(minutes=30)],
            showgrid=False
        ),
        yaxis=dict(
            title="",
            tickmode='array',
            tickvals=list(range(len(y_labels))),
            ticktext=y_labels,
            range=[-0.5, 7.5],
            showgrid=True,
            gridcolor='rgba(0, 0, 0, 0.2)',  # 더 진한 회색 가로선
            gridwidth=1,
            zeroline=True,
            zerolinecolor='rgba(0, 0, 0, 0.3)',
            zerolinewidth=1
        ),
        height=600,
        plot_bgcolor='white',
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5,
            itemsizing='constant'
        ),
        margin=dict(l=100, r=50, t=80, b=100)
    )
    
    # 현재 시간 표시 (분석 날짜가 오늘인 경우)
    if analysis_result['analysis_date'] == datetime.now().date():
        current_time = datetime.now()
        if work_start <= current_time <= work_end:
            fig.add_vline(
                x=current_time,
                line_dash="dash",
                line_color="red",
                line_width=2,
                annotation_text="현재",
                annotation_position="top"
            )
    
    # 식사 시간대 하이라이트
    meal_times = [
        {'name': '조식', 'start': '06:30', 'end': '09:00', 'color': 'rgba(255, 152, 0, 0.1)'},
        {'name': '중식', 'start': '11:20', 'end': '13:20', 'color': 'rgba(255, 152, 0, 0.1)'},
        {'name': '석식', 'start': '17:00', 'end': '20:00', 'color': 'rgba(255, 152, 0, 0.1)'},
        {'name': '야식', 'start': '23:30', 'end': '01:00', 'color': 'rgba(255, 152, 0, 0.1)'}
    ]
    
    for meal in meal_times:
        meal_start = datetime.combine(analysis_result['analysis_date'], 
                                    datetime.strptime(meal['start'], '%H:%M').time())
        meal_end = datetime.combine(analysis_result['analysis_date'], 
                                  datetime.strptime(meal['end'], '%H:%M').time())
        
        # 야식의 경우 다음날로 넘어가는 처리
        if meal['name'] == '야식' and meal_end < meal_start:
            meal_end += timedelta(days=1)
        
        if meal_start <= work_end and meal_end >= work_start:
            fig.add_vrect(
                x0=max(meal_start, work_start),
                x1=min(meal_end, work_end),
                fillcolor=meal['color'],
                layer="below",
                line_width=0,
            )
    
    return fig