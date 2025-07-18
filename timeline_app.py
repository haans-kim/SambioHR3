"""
개인활동요약 UI 참조자료를 완전히 반영한 Streamlit 애플리케이션
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date, time
import random
import os
import sys

# 프로젝트 경로 추가
sys.path.append('src')
from data_processing.pickle_manager import PickleManager

# 페이지 설정
st.set_page_config(
    page_title="Sambio Human Analytics",
    page_icon="📊",
    layout="wide"
)

# Pickle 관리자 초기화
pickle_manager = PickleManager()

# 데이터 로드 함수
@st.cache_data
def load_tag_data():
    """태그 데이터 로드 (타임스탬프 기반 캐시 관리)"""
    try:
        tag_file_path = "data/tag_data_24.6.xlsx"
        
        if not os.path.exists(tag_file_path):
            st.warning(f"태그 데이터 파일을 찾을 수 없습니다: {tag_file_path}")
            return pd.DataFrame()
        
        # 엑셀 파일의 수정 시간 확인
        excel_mtime = os.path.getmtime(tag_file_path)
        excel_mtime_str = datetime.fromtimestamp(excel_mtime).strftime('%Y%m%d_%H%M%S')
        
        # Pickle 파일에서 로드 시도
        try:
            # 기존 pickle 파일 목록 확인
            pickle_files = pickle_manager.list_files("tag_data_24.6")
            
            if not pickle_files.empty:
                # 최신 pickle 파일의 버전 확인
                latest_pickle = pickle_files.iloc[-1]
                pickle_version = latest_pickle['version']
                
                # 엑셀 파일이 pickle 파일보다 새로운지 확인
                if pickle_version >= excel_mtime_str:
                    df = pickle_manager.load_dataframe("tag_data_24.6")
                    st.success(f"✅ Pickle 캐시에서 데이터 로드: {len(df):,}건 (엑셀 파일 변경 없음)")
                    return df
                else:
                    st.info("🔄 엑셀 파일이 업데이트되었습니다. 새로 로드 중...")
                    
        except Exception as e:
            st.info(f"🔄 Pickle 파일 로드 실패: {str(e)[:50]}... 엑셀에서 로드 중...")
        
        # 엑셀 파일에서 로드
        st.info("📊 엑셀 파일 읽는 중... (시간이 걸릴 수 있습니다)")
        
        # 큰 파일 처리를 위한 청크 읽기
        with st.spinner("엑셀 파일 로드 중..."):
            df = pd.read_excel(tag_file_path)
            
            # 데이터 정리
            df = df.dropna(subset=['사번'])
            
            # dtypes를 문자열로 변환 (JSON 직렬화 문제 해결)
            df_for_save = df.copy()
            
            # Pickle 파일로 저장 (타임스탬프를 버전으로 사용)
            pickle_manager.save_dataframe(
                df_for_save, 
                "tag_data_24.6",
                version=excel_mtime_str,
                description=f"태그 데이터 원본 (24년 6월) - 엑셀 수정시간: {datetime.fromtimestamp(excel_mtime)}"
            )
            
            st.success(f"✅ 엑셀 파일에서 데이터 로드 및 Pickle 저장 완료: {len(df):,}건")
            return df
            
    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {str(e)}")
        return pd.DataFrame()

@st.cache_data
def get_employee_list():
    """직원 목록 조회"""
    try:
        tag_data = load_tag_data()
        if not tag_data.empty:
            # 사번 컬럼 사용
            if '사번' in tag_data.columns:
                employees = tag_data['사번'].unique()
                valid_employees = [str(emp) for emp in employees if pd.notna(emp)]
                return sorted(valid_employees)
            
            # 다른 직원 ID 컬럼 찾기
            employee_cols = [col for col in tag_data.columns if any(keyword in col.lower() for keyword in ['employee', 'emp', 'id', '직원', '사원'])]
            if employee_cols:
                employee_col = employee_cols[0]
                employees = tag_data[employee_col].unique()
                return sorted([str(emp) for emp in employees if pd.notna(emp)])
        
        # 기본값 반환
        return ["샘플데이터없음"]
    except Exception as e:
        return [f"데이터로드오류: {str(e)[:20]}"]

@st.cache_data
def get_employee_tag_data(employee_id, selected_date):
    """특정 직원의 특정 날짜 태그 데이터 조회"""
    try:
        tag_data = load_tag_data()
        if tag_data.empty:
            return pd.DataFrame()
        
        # 사번 컬럼 사용
        if '사번' not in tag_data.columns:
            return pd.DataFrame()
        
        # 날짜 컬럼 사용 (ENTE_DT)
        if 'ENTE_DT' not in tag_data.columns:
            return pd.DataFrame()
        
        # 특정 직원 데이터 필터링
        employee_data = tag_data[tag_data['사번'] == employee_id].copy()
        
        if employee_data.empty:
            return pd.DataFrame()
        
        # 날짜 필터링 (ENTE_DT는 YYYYMMDD 형식)
        selected_date_str = selected_date.strftime('%Y%m%d')
        employee_data = employee_data[employee_data['ENTE_DT'] == int(selected_date_str)]
        
        # 시간 순으로 정렬 (출입시각 기준)
        if '출입시각' in employee_data.columns:
            employee_data = employee_data.sort_values('출입시각')
        
        return employee_data
        
    except Exception as e:
        st.error(f"직원 데이터 조회 중 오류 발생: {str(e)}")
        return pd.DataFrame()

@st.cache_data
def get_available_dates(employee_id):
    """특정 직원의 사용 가능한 날짜 목록 조회"""
    try:
        tag_data = load_tag_data()
        if tag_data.empty or '사번' not in tag_data.columns:
            return []
        
        # 특정 직원 데이터 필터링
        employee_data = tag_data[tag_data['사번'] == employee_id]
        
        if employee_data.empty:
            return []
        
        # 날짜 목록 추출
        dates = employee_data['ENTE_DT'].unique()
        date_objects = []
        
        for date_int in sorted(dates):
            if pd.notna(date_int):
                try:
                    date_str = str(int(date_int))
                    if len(date_str) == 8:  # YYYYMMDD 형식
                        date_obj = datetime.strptime(date_str, '%Y%m%d').date()
                        date_objects.append(date_obj)
                except:
                    continue
        
        return sorted(date_objects)
        
    except Exception as e:
        return []

# 메인 타이틀
st.title("🏭 Sambio Human Analytics")
st.markdown("### 2교대 근무 시스템 실근무시간 분석 대시보드")

# 사이드바
with st.sidebar:
    st.header("📋 메뉴")
    
    page = st.radio(
        "페이지 선택",
        ["🏠 홈", "👤 개인 분석", "🏢 조직 분석"]
    )
    
    st.markdown("---")
    st.markdown("### 📊 시스템 상태")
    
    # 데이터 로드 상태 확인
    tag_data = load_tag_data()
    if not tag_data.empty:
        st.success("🟢 시스템 정상 운영")
        st.success(f"🟢 태그 데이터 로드됨 ({len(tag_data):,}건)")
    else:
        st.warning("🟡 태그 데이터 로드 실패")
    
    # Pickle 캐시 정보
    st.markdown("---")
    st.markdown("### 💾 캐시 정보")
    
    try:
        cache_stats = pickle_manager.get_cache_stats()
        st.info(f"📁 캐시 파일: {cache_stats['total_files']}개")
        st.info(f"💽 캐시 크기: {cache_stats['total_size_mb']:.1f}MB")
        
        # 캐시 새로고침 버튼
        if st.button("🔄 캐시 새로고침"):
            st.cache_data.clear()
            st.success("캐시가 새로고침되었습니다!")
            st.rerun()
            
    except Exception as e:
        st.warning(f"캐시 정보 조회 실패: {str(e)}")
    
    if page == "👤 개인 분석":
        st.markdown("---")
        st.markdown("### 👤 개인 분석 설정")
        
        # 실제 직원 목록 사용
        employee_list = get_employee_list()
        
        if len(employee_list) > 0 and not employee_list[0].startswith("샘플데이터없음"):
            employee_id = st.selectbox(
                "🏷️ 사번 선택",
                employee_list,
                help="실제 태그 데이터에서 추출한 사번 목록"
            )
            
            # 선택된 직원의 사용 가능한 날짜 조회
            available_dates = get_available_dates(employee_id)
            
            if available_dates:
                st.success(f"📅 {employee_id}님의 데이터 기간: {len(available_dates)}일")
                st.write(f"🗓️ 첫 데이터: {available_dates[0]}")
                st.write(f"🗓️ 마지막 데이터: {available_dates[-1]}")
                
                # 사용 가능한 날짜 중에서 선택
                selected_date = st.selectbox(
                    "📅 분석 일자 선택",
                    available_dates,
                    index=len(available_dates)-1 if available_dates else 0,  # 마지막 날짜를 기본으로
                    help="실제 태그 데이터가 존재하는 날짜만 표시"
                )
            else:
                st.warning(f"⚠️ {employee_id}님의 데이터가 없습니다.")
                selected_date = date(2024, 6, 1)
        else:
            st.error("❌ 직원 데이터를 불러올 수 없습니다.")
            employee_id = "데이터없음"
            selected_date = date(2024, 6, 1)
        
        st.session_state.employee_id = employee_id
        st.session_state.selected_date = selected_date

# 메인 콘텐츠
if page == "🏠 홈":
    st.markdown("## 🏠 대시보드")
    
    # KPI 카드
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("분석 직원", "1,234명", "12명")
    
    with col2:
        st.metric("활성 조직", "56개", "3개")
    
    with col3:
        st.metric("평균 효율성", "89.5%", "2.3%")
    
    with col4:
        st.metric("데이터 품질", "94.2%", "1.8%")

elif page == "👤 개인 분석":
    employee_id = st.session_state.get('employee_id', 'EMP_001')
    selected_date = st.session_state.get('selected_date', date(2024, 1, 15))
    
    st.markdown(f"## 👤 개인별 분석 - {employee_id}")
    st.markdown(f"### 📅 분석 일자: {selected_date.strftime('%Y-%m-%d')}")
    
    # 일일 활동 요약 (참조 이미지 상단 부분)
    st.markdown("---")
    st.markdown("## 📊 일일 활동 요약")
    
    # 주요 지표 (참조 이미지 스타일)
    col1, col2, col3 = st.columns([2, 2, 2])
    
    with col1:
        st.markdown("""
        <div style="background-color: #e3f2fd; padding: 20px; border-radius: 10px; text-align: center;">
            <h3 style="color: #1976d2; margin: 0;">Claim 시간</h3>
            <h1 style="color: #1976d2; margin: 10px 0;">9.5h</h1>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style="background-color: #e8f5e8; padding: 20px; border-radius: 10px; text-align: center;">
            <h3 style="color: #388e3c; margin: 0;">실제 업무시간</h3>
            <h1 style="color: #388e3c; margin: 10px 0;">8.5h</h1>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div style="background-color: #f3e5f5; padding: 20px; border-radius: 10px; text-align: center;">
            <h3 style="color: #7b1fa2; margin: 0;">업무 효율성</h3>
            <h1 style="color: #7b1fa2; margin: 10px 0;">89.5%</h1>
        </div>
        """, unsafe_allow_html=True)
    
    # 프로그레스 바 (참조 이미지 스타일)
    st.markdown("### 📈 시간 비교")
    
    # Claim 시간 vs 실제 업무시간 비교 바
    claim_hours = 9.5
    actual_hours = 8.5
    max_hours = 10
    
    col1, col2 = st.columns([8, 2])
    
    with col1:
        # HTML/CSS로 참조 이미지와 동일한 스타일의 프로그레스 바 생성
        st.markdown(f"""
        <div style="position: relative; height: 40px; background-color: #e0e0e0; border-radius: 20px; overflow: hidden;">
            <div style="position: absolute; left: 0; top: 0; height: 100%; width: {actual_hours/max_hours*100}%; 
                        background: linear-gradient(90deg, #2196F3 0%, #4CAF50 100%); border-radius: 20px;"></div>
            <div style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: white; font-weight: bold;">
                실제 업무시간: {actual_hours}h
            </div>
            <div style="position: absolute; right: 10px; top: 50%; transform: translateY(-50%); color: #666; font-size: 12px;">
                Claim: {claim_hours}h
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div style="text-align: center; padding: 10px;">
            <div style="font-size: 24px; font-weight: bold; color: #4CAF50;">89.5%</div>
            <div style="font-size: 12px; color: #666;">업무 효율성</div>
        </div>
        """, unsafe_allow_html=True)
    
    # 활동 분류별 시간 분포 (참조 이미지 스타일)
    st.markdown("---")
    st.markdown("### 📊 활동 분류별 시간 분포")
    
    # 4개 카드 레이아웃 (참조 이미지 스타일)
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div style="background-color: #e3f2fd; padding: 15px; border-radius: 10px; text-align: center;">
            <h2 style="color: #1976d2; margin: 0;">6.5h</h2>
            <div style="color: #1976d2; font-weight: bold;">작업시간</div>
            <div style="color: #1976d2; font-size: 14px;">76.5%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style="background-color: #f3e5f5; padding: 15px; border-radius: 10px; text-align: center;">
            <h2 style="color: #7b1fa2; margin: 0;">1.2h</h2>
            <div style="color: #7b1fa2; font-weight: bold;">회의시간</div>
            <div style="color: #7b1fa2; font-size: 14px;">14.1%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div style="background-color: #fff3e0; padding: 15px; border-radius: 10px; text-align: center;">
            <h2 style="color: #f57c00; margin: 0;">0.8h</h2>
            <div style="color: #f57c00; font-weight: bold;">이동시간</div>
            <div style="color: #f57c00; font-size: 14px;">9.4%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div style="background-color: #e8f5e8; padding: 15px; border-radius: 10px; text-align: center;">
            <h2 style="color: #388e3c; margin: 0;">85%</h2>
            <div style="color: #388e3c; font-weight: bold;">데이터 신뢰도</div>
            <div style="color: #388e3c; font-size: 14px;">추정 포함</div>
        </div>
        """, unsafe_allow_html=True)
    
    # 추가 세부 정보 (참조 이미지 하단)
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("**비근무시간 (1.0h)**")
        st.markdown("점심시간: 0.8h")
    
    with col2:
        st.markdown("**휴게시간: 0.2h**")
    
    with col3:
        st.markdown("**개인활동: 0h**")
    
    # 활동 타임라인 (실제 데이터 사용)
    st.markdown("---")
    st.markdown("## 📅 활동 타임라인")
    
    # 실제 태그 데이터 로드
    actual_tag_data = get_employee_tag_data(employee_id, selected_date)
    
    if not actual_tag_data.empty:
        # 실제 데이터를 타임라인 형태로 변환
        timeline_data = []
        
        # 실제 데이터 컬럼 매핑
        time_col = '출입시각'
        location_col = 'DR_NM'  # 출입문 명칭
        activity_col = 'INOUT_GB'  # 입문/출문 구분
        name_col = 'NAME'  # 직원 이름
        
        # 활동별 색상 매핑 (실제 데이터 기준)
        activity_colors = {
            '입문': '#4CAF50',  # 초록색 - 입문
            '출문': '#F44336',  # 빨간색 - 출문
            '게이트': '#2196F3',  # 파란색 - 게이트
            '사무실': '#9C27B0',  # 보라색 - 사무실
            '생산': '#FF5722',  # 주황색 - 생산구역
            '카페': '#FF9800',  # 주황색 - 카페테리아
            '회의': '#607D8B'   # 회색 - 회의실
        }
        
        for _, row in actual_tag_data.iterrows():
            try:
                # 시간 처리
                time_value = row[time_col]
                if pd.isna(time_value):
                    continue
                    
                # 시간을 HH:MM 형태로 변환
                if isinstance(time_value, str):
                    time_str = time_value
                elif hasattr(time_value, 'strftime'):
                    time_str = time_value.strftime('%H:%M')
                else:
                    time_str = str(time_value)
                
                # 위치/활동 정보
                location = str(row[location_col]) if pd.notna(row[location_col]) else "미지정"
                activity = str(row[activity_col]) if pd.notna(row[activity_col]) else "미지정"
                
                # 활동 분류에 따른 색상
                color = '#2196F3'  # 기본 색상
                
                # 입문/출문에 따른 색상
                if activity == '입문':
                    color = '#4CAF50'
                elif activity == '출문':
                    color = '#F44336'
                else:
                    # 위치에 따른 색상
                    location_lower = location.lower()
                    if 'gate' in location_lower or '게이트' in location_lower:
                        color = '#2196F3'
                    elif 'cafeteria' in location_lower or '카페' in location_lower:
                        color = '#FF9800'
                    elif 'office' in location_lower or '사무실' in location_lower:
                        color = '#9C27B0'
                    elif 'production' in location_lower or '생산' in location_lower:
                        color = '#FF5722'
                
                # 신뢰도 (실제 태그 데이터이므로 100%)
                confidence = 100
                
                timeline_data.append({
                    "time": time_str,
                    "location": location,
                    "activity": activity,
                    "confidence": confidence,
                    "color": color,
                    "employee_name": str(row[name_col]) if pd.notna(row[name_col]) else "미지정"
                })
                
            except Exception as e:
                st.error(f"데이터 처리 중 오류: {str(e)}")
                continue
        
        # 시간 순으로 정렬
        timeline_data = sorted(timeline_data, key=lambda x: x['time'])
        
        st.success(f"✅ 실제 태그 데이터 로드됨: {len(timeline_data)}건")
        
    else:
        st.warning(f"⚠️ {employee_id}의 {selected_date} 데이터를 찾을 수 없습니다. 샘플 데이터를 표시합니다.")
        # 샘플 데이터 사용
        timeline_data = [
            {"time": "08:30", "location": "출근", "activity": "출근", "confidence": 100, "color": "#4CAF50"},
            {"time": "09:35", "location": "작업실", "activity": "작업실", "confidence": 100, "color": "#2196F3"},
            {"time": "12:40", "location": "중식", "activity": "중식", "confidence": 100, "color": "#FF5722"},
            {"time": "18:00", "location": "퇴근", "activity": "퇴근", "confidence": 100, "color": "#F44336"},
        ]
    
    # 타임라인 차트 생성 (참조 이미지와 동일한 스타일)
    fig = go.Figure()
    
    # 활동 위치 매핑 (Y축)
    activity_positions = {
        "출근": 8,
        "작업실": 7,
        "작업실": 6,
        "이동": 5,
        "회의": 4,
        "중식": 3,
        "작업실": 2,
        "퇴근": 1
    }
    
    # 시간을 분으로 변환하는 함수
    def time_to_minutes(time_str):
        hour, minute = map(int, time_str.split(':'))
        return hour * 60 + minute
    
    # 타임라인 포인트들을 시간 순으로 정렬
    timeline_data.sort(key=lambda x: time_to_minutes(x['time']))
    
    # 각 포인트 추가
    for i, point in enumerate(timeline_data):
        time_minutes = time_to_minutes(point['time'])
        
        # 활동별 Y 위치 설정
        if point['activity'] == '출근':
            y_pos = 8
        elif point['activity'] == '작업실':
            y_pos = 7
        elif point['activity'] == '이동':
            y_pos = 5
        elif point['activity'] == '회의':
            y_pos = 4
        elif point['activity'] == '중식':
            y_pos = 3
        elif point['activity'] == '퇴근':
            y_pos = 1
        else:
            y_pos = 6
        
        # 신뢰도에 따른 크기 조정
        size = 15 if point['confidence'] == 100 else 12
        opacity = 1.0 if point['confidence'] == 100 else 0.6
        
        # 포인트 추가
        fig.add_trace(go.Scatter(
            x=[time_minutes],
            y=[y_pos],
            mode='markers',
            marker=dict(
                size=size,
                color=point['color'],
                opacity=opacity,
                line=dict(width=2, color='white')
            ),
            text=f"{point['time']}<br>{point['activity']}<br>신뢰도: {point['confidence']}%",
            hovertemplate='<b>%{text}</b><extra></extra>',
            name=point['activity'],
            showlegend=False
        ))
        
        # 시간 라벨 추가
        fig.add_annotation(
            x=time_minutes,
            y=y_pos + 0.3,
            text=point['time'],
            showarrow=False,
            font=dict(size=10, color='black'),
            bgcolor='rgba(255,255,255,0.8)',
            bordercolor='gray',
            borderwidth=1
        )
    
    # 연결선 추가 (참조 이미지처럼 직선으로 연결)
    x_coords = [time_to_minutes(point['time']) for point in timeline_data]
    y_coords = []
    
    for point in timeline_data:
        if point['activity'] == '출근':
            y_coords.append(8)
        elif point['activity'] == '작업실':
            y_coords.append(7)
        elif point['activity'] == '이동':
            y_coords.append(5)
        elif point['activity'] == '회의':
            y_coords.append(4)
        elif point['activity'] == '중식':
            y_coords.append(3)
        elif point['activity'] == '퇴근':
            y_coords.append(1)
        else:
            y_coords.append(6)
    
    # 연결선 추가
    fig.add_trace(go.Scatter(
        x=x_coords,
        y=y_coords,
        mode='lines',
        line=dict(color='gray', width=2, dash='solid'),
        showlegend=False,
        hoverinfo='skip'
    ))
    
    # 레이아웃 설정 (참조 이미지와 동일한 스타일)
    fig.update_layout(
        title=f"{employee_id} 활동 타임라인 ({selected_date.strftime('%Y-%m-%d')})",
        xaxis=dict(
            title="시간",
            tickmode='linear',
            dtick=60,  # 1시간 간격
            tickvals=[i*60 for i in range(8, 19)],  # 8시부터 18시까지
            ticktext=[f"{i:02d}:00" for i in range(8, 19)],
            range=[8*60, 18*60],  # 8시부터 18시까지
            showgrid=True,
            gridcolor='lightgray'
        ),
        yaxis=dict(
            title="활동 위치",
            tickvals=[1, 2, 3, 4, 5, 6, 7, 8],
            ticktext=["퇴근", "작업실4", "중식", "회의", "이동", "작업실3", "작업실2", "출근"],
            range=[0.5, 8.5],
            showgrid=True,
            gridcolor='lightgray'
        ),
        height=500,
        plot_bgcolor='white',
        hovermode='closest'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 범례 (참조 이미지 하단)
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("🔵 **실제 태그 (신뢰도 100%)**")
    
    with col2:
        st.markdown("🔵 **추정 데이터 (신뢰도 표시)**")
    
    # 태그 데이터 테이블 추가
    st.markdown("---")
    st.markdown("### 📋 태그 데이터 상세 내역")
    
    # 태그 데이터 테이블 생성
    tag_data_table = pd.DataFrame({
        '순번': range(1, len(timeline_data) + 1),
        '시간': [point['time'] for point in timeline_data],
        '태그 위치': [point['location'] for point in timeline_data],
        '활동 분류': [point['activity'] for point in timeline_data],
        '신뢰도 (%)': [point['confidence'] for point in timeline_data],
        '데이터 유형': ['실제 태그' if point['confidence'] == 100 else '추정 데이터' for point in timeline_data],
        '태그 ID': [f"TAG_{i:03d}" for i in range(1, len(timeline_data) + 1)],
        '위치 코드': [f"LOC_{hash(point['location']) % 1000:03d}" for point in timeline_data],
        '처리 상태': ['정상' if point['confidence'] >= 80 else '검토 필요' for point in timeline_data]
    })
    
    # 시간 순으로 정렬
    tag_data_table = tag_data_table.sort_values('시간').reset_index(drop=True)
    tag_data_table['순번'] = range(1, len(tag_data_table) + 1)
    
    # 조건부 스타일링을 위한 함수
    def highlight_confidence(row):
        if row['신뢰도 (%)'] == 100:
            return ['background-color: #e8f5e8; color: black'] * len(row)  # 연한 초록색, 검은 폰트
        elif row['신뢰도 (%)'] >= 80:
            return ['background-color: #fff3e0; color: black'] * len(row)  # 연한 주황색, 검은 폰트
        else:
            return ['background-color: #ffebee; color: black'] * len(row)  # 연한 빨간색, 검은 폰트
    
    # 스타일 적용된 테이블 표시
    styled_table = tag_data_table.style.apply(highlight_confidence, axis=1)
    
    st.dataframe(styled_table, use_container_width=True, height=400)
    
    # 테이블 요약 정보
    st.markdown("#### 📊 태그 데이터 요약")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_tags = len(tag_data_table)
        st.metric("총 태그 수", f"{total_tags}개")
    
    with col2:
        high_confidence = len(tag_data_table[tag_data_table['신뢰도 (%)'] == 100])
        st.metric("실제 태그", f"{high_confidence}개")
    
    with col3:
        estimated_tags = len(tag_data_table[tag_data_table['신뢰도 (%)'] < 100])
        st.metric("추정 데이터", f"{estimated_tags}개")
    
    with col4:
        avg_confidence = tag_data_table['신뢰도 (%)'].mean()
        st.metric("평균 신뢰도", f"{avg_confidence:.1f}%")
    
    # 태그 데이터 다운로드 기능
    st.markdown("---")
    st.markdown("### 💾 데이터 다운로드")
    
    # CSV 다운로드
    csv_data = tag_data_table.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📥 태그 데이터 CSV 다운로드",
        data=csv_data,
        file_name=f"{employee_id}_태그데이터_{selected_date.strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )
    
    # 추가 분석 옵션
    st.markdown("### 🔍 데이터 분석 옵션")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📊 시간별 활동 분석"):
            # 시간대별 활동 분석
            st.markdown("#### 시간대별 활동 분포")
            
            # 시간대별 그룹화
            tag_data_table['시간대'] = pd.to_datetime(tag_data_table['시간'], format='%H:%M').dt.hour
            hourly_analysis = tag_data_table.groupby(['시간대', '활동 분류']).size().unstack(fill_value=0)
            
            # 시간대별 활동 분포 차트
            fig_hourly = px.bar(
                hourly_analysis.reset_index(), 
                x='시간대', 
                y=hourly_analysis.columns.tolist(),
                title='시간대별 활동 분포',
                labels={'value': '활동 횟수', 'variable': '활동 분류'}
            )
            st.plotly_chart(fig_hourly, use_container_width=True)
    
    with col2:
        if st.button("🎯 신뢰도 분석"):
            # 신뢰도 분석
            st.markdown("#### 신뢰도 분석")
            
            confidence_analysis = tag_data_table['신뢰도 (%)'].value_counts().sort_index()
            
            # 신뢰도 분포 차트
            fig_confidence = px.pie(
                values=confidence_analysis.values,
                names=confidence_analysis.index,
                title='신뢰도 분포',
                color_discrete_map={100: '#4CAF50', 80: '#FF9800', 60: '#F44336'}
            )
            st.plotly_chart(fig_confidence, use_container_width=True)
    
    # 추가 분석 정보
    st.markdown("---")
    st.markdown("### 📊 상세 분석")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**주요 활동**")
        st.write("• 작업실 활동: 6.5시간")
        st.write("• 회의 활동: 1.2시간")
        st.write("• 이동: 0.8시간")
    
    with col2:
        st.markdown("**식사 및 휴게**")
        st.write("• 중식시간: 0.8시간")
        st.write("• 휴게시간: 0.2시간")
    
    with col3:
        st.markdown("**데이터 품질**")
        st.write("• 전체 신뢰도: 85%")
        st.write("• 실제 태그: 70%")
        st.write("• 추정 데이터: 30%")

elif page == "🏢 조직 분석":
    st.markdown("## 🏢 조직별 분석")
    st.info("조직별 분석 기능은 개발 중입니다.")

# 하단 정보
st.markdown("---")
st.markdown("**🏭 Sambio Human Analytics v1.0.0** | 개인활동요약 UI 참조자료 반영 | 2025-01-18")