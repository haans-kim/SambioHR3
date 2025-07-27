"""
테마가 적용된 Streamlit 앱 예제
"""

import streamlit as st
from datetime import datetime, timedelta
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.ui.styles.style_manager import StyleManager
from src.ui.components.custom_components import CustomComponents
from src.ui.components.styled_individual_dashboard import StyledIndividualDashboard
from src.database import get_database_manager, get_pickle_manager
from src.analysis import IndividualAnalyzer

# 페이지 설정
st.set_page_config(
    page_title="Sambio HR Analytics - Premium",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

def main():
    # 스타일 매니저 초기화
    style_manager = StyleManager()
    components = CustomComponents()
    
    # 테마 토글 (사이드바에 배치)
    with st.sidebar:
        st.markdown("### 🎨 테마 설정")
        st.markdown("---")
        dark_mode = style_manager.create_theme_toggle()
        st.markdown("---")
    
    # CSS 주입
    style_manager.inject_custom_css(dark_mode)
    
    # 헤더
    st.markdown("""
    <div style="text-align: center; padding: 2rem 0;">
        <h1 style="font-size: 2.5rem; font-weight: 700; margin: 0;">
            🏢 Sambio Human Analytics
        </h1>
        <p style="font-size: 1.125rem; color: var(--color-text-secondary); margin-top: 0.5rem;">
            프리미엄 근태 분석 시스템
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # 데이터베이스 매니저 초기화
    try:
        db_manager = get_database_manager()
        pickle_manager = get_pickle_manager()
        analyzer = IndividualAnalyzer(db_manager)
        dashboard = StyledIndividualDashboard(analyzer)
    except Exception as e:
        components.info_box(
            f"시스템 초기화 중 오류가 발생했습니다: {str(e)}",
            type="error"
        )
        return
    
    # 사이드바 설정
    with st.sidebar:
        st.markdown("### 분석 설정")
        
        # 직원 선택
        employees = dashboard.get_available_employees()
        if not employees:
            components.info_box(
                "직원 데이터가 없습니다. 먼저 데이터를 업로드해주세요.",
                type="warning"
            )
            return
        
        selected_employee_label = st.selectbox(
            "직원 선택",
            options=employees,
            help="분석할 직원을 선택하세요"
        )
        # 사번 추출 (형식: "20110122 - 홍길동")
        selected_employee_id = selected_employee_label.split(' - ')[0] if ' - ' in selected_employee_label else selected_employee_label
        
        # 날짜 선택
        st.markdown("### 날짜 선택")
        date_selection_mode = st.radio(
            "선택 모드",
            ["단일 날짜", "기간 선택"],
            horizontal=True
        )
        
        if date_selection_mode == "단일 날짜":
            selected_date = st.date_input(
                "분석 날짜",
                value=datetime.now().date() - timedelta(days=1),
                max_value=datetime.now().date()
            )
            
            # 대시보드 렌더링
            dashboard.render(selected_employee_id, selected_date)
            
        else:
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input(
                    "시작일",
                    value=datetime.now().date() - timedelta(days=7),
                    max_value=datetime.now().date()
                )
            with col2:
                end_date = st.date_input(
                    "종료일",
                    value=datetime.now().date() - timedelta(days=1),
                    max_value=datetime.now().date()
                )
            
            if start_date > end_date:
                components.info_box(
                    "시작일이 종료일보다 늦을 수 없습니다.",
                    type="error"
                )
                return
            
            # 기간 분석 렌더링
            _render_period_analysis(analyzer, selected_employee_id, start_date, end_date, components)
        
        # 추가 옵션
        st.markdown("### 추가 옵션")
        show_raw_data = st.checkbox("원본 데이터 표시", value=False)
        show_debug_info = st.checkbox("디버그 정보 표시", value=False)
        
        if show_debug_info:
            st.markdown("### 디버그 정보")
            st.json({
                "employee_id": selected_employee_id,
                "dark_mode": dark_mode,
                "db_connected": db_manager is not None
            })

def _render_period_analysis(analyzer, employee_id, start_date, end_date, components):
    """기간 분석 렌더링"""
    # 기간 분석 데이터 가져오기
    work_analysis = analyzer.analyze_work_time(employee_id, start_date, end_date)
    
    if not work_analysis:
        components.info_box(
            f"선택한 기간에 데이터가 없습니다.",
            type="warning"
        )
        return
    
    # 요약 통계
    total_days = (end_date - start_date).days + 1
    avg_work_hours = work_analysis.get('actual_work_hours', 0) / total_days
    
    stats = [
        {
            'value': f"{work_analysis.get('actual_work_hours', 0):.1f}h",
            'label': '총 업무시간',
            'sublabel': f"{total_days}일간"
        },
        {
            'value': f"{avg_work_hours:.1f}h",
            'label': '일평균 업무시간',
            'sublabel': '기준: 8시간/일'
        },
        {
            'value': f"{work_analysis.get('efficiency_percentage', 0):.1f}%",
            'label': '평균 효율성',
            'sublabel': '업무시간/체류시간'
        },
        {
            'value': f"{work_analysis.get('confidence_index', 0):.0f}%",
            'label': '데이터 신뢰도',
            'sublabel': '평균 신뢰도'
        }
    ]
    
    components.stats_grid(stats)
    
    # 일별 상세 분석
    st.markdown("### 📅 일별 분석")
    daily_data = []
    
    current_date = start_date
    while current_date <= end_date:
        daily_analysis = analyzer.analyze_work_time(employee_id, current_date, current_date)
        if daily_analysis:
            daily_data.append({
                '날짜': current_date,
                '업무시간': f"{daily_analysis.get('actual_work_hours', 0):.1f}h",
                '체류시간': f"{daily_analysis.get('total_stay_hours', 0):.1f}h",
                '효율성': f"{daily_analysis.get('efficiency_percentage', 0):.1f}%",
                '신뢰도': f"{daily_analysis.get('confidence_index', 0):.0f}%"
            })
        current_date += timedelta(days=1)
    
    if daily_data:
        import pandas as pd
        df = pd.DataFrame(daily_data)
        components.styled_dataframe(df)

if __name__ == "__main__":
    main()