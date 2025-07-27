"""
Streamlit 스타일 매니저 - CSS 주입 및 테마 관리
"""

import streamlit as st
from .theme import Theme

class StyleManager:
    """Streamlit 앱의 스타일 관리 클래스"""
    
    def __init__(self):
        self.theme = Theme()
        
    def inject_custom_css(self, dark_mode=False):
        """커스텀 CSS를 Streamlit 앱에 주입"""
        
        # CSS 변수 생성
        css_variables = self.theme.get_css_variables(dark_mode)
        
        # 기본 CSS 스타일
        custom_css = f"""
        <style>
        /* CSS 변수 정의 */
        :root {{
            {css_variables}
        }}
        
        /* 폰트 임포트 */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');
        
        /* 전역 스타일 */
        html, body, [class*="st-"] {{
            font-family: var(--font-primary);
        }}
        
        /* 메인 컨테이너 */
        .stApp {{
            background-color: var(--color-bg-primary);
            color: var(--color-text-primary);
        }}
        
        /* 사이드바 */
        section[data-testid="stSidebar"] {{
            background-color: var(--color-bg-secondary);
            border-right: 1px solid var(--color-border-primary);
        }}
        
        /* 헤더 스타일링 */
        h1, h2, h3, h4, h5, h6 {{
            color: var(--color-text-primary);
            font-weight: 600;
            line-height: 1.2;
            margin-top: 0;
        }}
        
        h1 {{ font-size: var(--text-3xl); }}
        h2 {{ font-size: var(--text-2xl); }}
        h3 {{ font-size: var(--text-xl); }}
        
        /* 카드 컨테이너 */
        .card {{
            background-color: var(--color-bg-card);
            border-radius: var(--radius-lg);
            padding: var(--spacing-lg);
            box-shadow: var(--shadow-md);
            border: 1px solid var(--color-border-primary);
            transition: var(--transition-normal);
        }}
        
        .card:hover {{
            box-shadow: var(--shadow-lg);
            transform: translateY(-2px);
        }}
        
        /* 메트릭 카드 */
        .metric-card {{
            background-color: var(--color-bg-card);
            border-radius: var(--radius-md);
            padding: var(--spacing-md);
            box-shadow: var(--shadow-sm);
            border: 1px solid var(--color-border-primary);
            text-align: center;
            transition: var(--transition-fast);
        }}
        
        .metric-value {{
            font-size: var(--text-2xl);
            font-weight: 700;
            color: var(--color-primary);
            margin-bottom: var(--spacing-xs);
        }}
        
        .metric-label {{
            font-size: var(--text-sm);
            color: var(--color-text-secondary);
            font-weight: 500;
        }}
        
        .metric-sublabel {{
            font-size: var(--text-xs);
            color: var(--color-text-muted);
            margin-top: var(--spacing-xs);
        }}
        
        /* 버튼 스타일 */
        .stButton > button {{
            background-color: var(--color-primary);
            color: var(--color-text-inverse);
            border: none;
            border-radius: var(--radius-md);
            padding: var(--spacing-sm) var(--spacing-lg);
            font-weight: 500;
            transition: var(--transition-fast);
            box-shadow: var(--shadow-sm);
        }}
        
        .stButton > button:hover {{
            background-color: var(--color-primary-dark);
            box-shadow: var(--shadow-md);
            transform: translateY(-1px);
        }}
        
        /* 보조 버튼 스타일 */
        .secondary-button > button {{
            background-color: transparent;
            color: var(--color-primary);
            border: 1px solid var(--color-primary);
        }}
        
        .secondary-button > button:hover {{
            background-color: var(--color-primary);
            color: var(--color-text-inverse);
        }}
        
        /* 입력 필드 */
        .stTextInput > div > div > input,
        .stSelectbox > div > div > select,
        .stDateInput > div > div > input {{
            background-color: var(--color-bg-primary);
            border: 1px solid var(--color-border-primary);
            border-radius: var(--radius-md);
            color: var(--color-text-primary);
            transition: var(--transition-fast);
        }}
        
        .stTextInput > div > div > input:focus,
        .stSelectbox > div > div > select:focus,
        .stDateInput > div > div > input:focus {{
            border-color: var(--color-primary);
            box-shadow: 0 0 0 3px rgba(46, 134, 171, 0.1);
        }}
        
        /* 데이터프레임 스타일 */
        .dataframe {{
            background-color: var(--color-bg-card);
            border: 1px solid var(--color-border-primary);
            border-radius: var(--radius-md);
            overflow: hidden;
        }}
        
        .dataframe thead tr {{
            background-color: var(--color-bg-secondary);
        }}
        
        .dataframe tbody tr:hover {{
            background-color: var(--color-bg-hover);
        }}
        
        /* 탭 스타일 */
        .stTabs [data-baseweb="tab-list"] {{
            background-color: var(--color-bg-secondary);
            border-radius: var(--radius-md);
            padding: var(--spacing-xs);
        }}
        
        .stTabs [data-baseweb="tab"] {{
            border-radius: var(--radius-sm);
            color: var(--color-text-secondary);
            transition: var(--transition-fast);
        }}
        
        .stTabs [aria-selected="true"] {{
            background-color: var(--color-bg-primary);
            color: var(--color-primary);
            box-shadow: var(--shadow-sm);
        }}
        
        /* 프로그레스 바 */
        .stProgress > div > div > div {{
            background-color: var(--color-primary);
        }}
        
        /* 경고/정보 박스 */
        .stAlert {{
            border-radius: var(--radius-md);
            border-width: 1px;
        }}
        
        .success-box {{
            background-color: rgba(16, 185, 129, 0.1);
            border: 1px solid var(--color-success);
            color: var(--color-success);
            padding: var(--spacing-md);
            border-radius: var(--radius-md);
        }}
        
        .warning-box {{
            background-color: rgba(245, 158, 11, 0.1);
            border: 1px solid var(--color-warning);
            color: var(--color-warning);
            padding: var(--spacing-md);
            border-radius: var(--radius-md);
        }}
        
        .error-box {{
            background-color: rgba(239, 68, 68, 0.1);
            border: 1px solid var(--color-error);
            color: var(--color-error);
            padding: var(--spacing-md);
            border-radius: var(--radius-md);
        }}
        
        .info-box {{
            background-color: rgba(59, 130, 246, 0.1);
            border: 1px solid var(--color-info);
            color: var(--color-info);
            padding: var(--spacing-md);
            border-radius: var(--radius-md);
        }}
        
        /* 차트 컨테이너 */
        .chart-container {{
            background-color: var(--color-bg-card);
            border-radius: var(--radius-lg);
            padding: var(--spacing-lg);
            box-shadow: var(--shadow-sm);
            border: 1px solid var(--color-border-primary);
        }}
        
        /* 통계 그리드 */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: var(--spacing-md);
            margin-bottom: var(--spacing-xl);
        }}
        
        /* 활동 타임라인 */
        .timeline-item {{
            display: flex;
            align-items: center;
            padding: var(--spacing-sm);
            border-radius: var(--radius-sm);
            transition: var(--transition-fast);
        }}
        
        .timeline-item:hover {{
            background-color: var(--color-bg-hover);
        }}
        
        /* 스크롤바 스타일 */
        ::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}
        
        ::-webkit-scrollbar-track {{
            background: var(--color-bg-secondary);
        }}
        
        ::-webkit-scrollbar-thumb {{
            background: var(--color-border-secondary);
            border-radius: 4px;
        }}
        
        ::-webkit-scrollbar-thumb:hover {{
            background: var(--color-text-muted);
        }}
        
        /* 반응형 디자인 */
        @media (max-width: 768px) {{
            .stats-grid {{
                grid-template-columns: 1fr;
            }}
            
            .card {{
                padding: var(--spacing-md);
            }}
        }}
        
        /* 애니메이션 */
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        
        .fade-in {{
            animation: fadeIn 0.5s ease-out;
        }}
        
        /* 다크모드 특별 스타일 */
        {self._get_dark_mode_specific_styles() if dark_mode else ''}
        </style>
        """
        
        st.markdown(custom_css, unsafe_allow_html=True)
    
    def _get_dark_mode_specific_styles(self):
        """다크모드 전용 추가 스타일"""
        return """
        /* 다크모드에서 코드 블록 스타일 */
        code, pre {{
            background-color: var(--color-bg-tertiary);
            border: 1px solid var(--color-border-primary);
        }}
        
        /* 다크모드에서 그림자 조정 */
        .card {{
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
        }}
        
        .card:hover {{
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.4);
        }}
        """
    
    def create_theme_toggle(self):
        """테마 토글 버튼 생성"""
        if 'dark_mode' not in st.session_state:
            st.session_state.dark_mode = False
        
        # 더 큰 버튼으로 명확하게 표시
        button_text = "🌙 다크모드" if not st.session_state.dark_mode else "☀️ 라이트모드"
        
        if st.button(button_text, 
                    help="클릭하여 테마 전환",
                    key="theme_toggle",
                    use_container_width=True):
            st.session_state.dark_mode = not st.session_state.dark_mode
            st.rerun()
        
        return st.session_state.dark_mode