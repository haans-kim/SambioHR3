"""
Streamlit 테마 및 스타일 시스템
"""

class Theme:
    """애플리케이션 테마 설정"""
    
    # 색상 팔레트
    COLORS = {
        # Primary colors
        'primary': '#2E86AB',
        'primary_dark': '#1E5F8E',
        'primary_light': '#4A9BC6',
        
        # Secondary colors  
        'secondary': '#F7F9FC',
        'secondary_dark': '#E5E9F0',
        
        # Semantic colors
        'success': '#10B981',
        'warning': '#F59E0B', 
        'error': '#EF4444',
        'info': '#3B82F6',
        
        # Text colors
        'text_primary': '#1F2937',
        'text_secondary': '#6B7280',
        'text_muted': '#9CA3AF',
        'text_inverse': '#FFFFFF',
        
        # Background colors
        'bg_primary': '#FFFFFF',
        'bg_secondary': '#F7F9FC',
        'bg_tertiary': '#E5E7EB',
        'bg_card': '#FFFFFF',
        'bg_hover': '#F3F4F6',
        
        # Border colors
        'border_primary': '#E5E7EB',
        'border_secondary': '#D1D5DB',
        
        # Chart colors (활동 분류용)
        'work': '#2E86AB',
        'meeting': '#8B5CF6',
        'meal': '#F59E0B',
        'rest': '#10B981',
        'movement': '#3B82F6',
        'idle': '#9CA3AF',
    }
    
    # 다크 모드 색상
    DARK_COLORS = {
        'primary': '#4A9BC6',
        'primary_dark': '#2E86AB',
        'primary_light': '#6BB3D6',
        
        'text_primary': '#F9FAFB',
        'text_secondary': '#D1D5DB',
        'text_muted': '#9CA3AF',
        
        'bg_primary': '#111827',
        'bg_secondary': '#1F2937',
        'bg_tertiary': '#374151',
        'bg_card': '#1F2937',
        'bg_hover': '#374151',
        
        'border_primary': '#374151',
        'border_secondary': '#4B5563',
    }
    
    # 폰트 설정
    FONTS = {
        'primary': '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        'monospace': '"JetBrains Mono", "Fira Code", Consolas, monospace',
    }
    
    # 크기 설정
    SIZES = {
        'text_xs': '0.75rem',    # 12px
        'text_sm': '0.875rem',   # 14px
        'text_base': '1rem',     # 16px
        'text_lg': '1.125rem',   # 18px
        'text_xl': '1.25rem',    # 20px
        'text_2xl': '1.5rem',    # 24px
        'text_3xl': '1.875rem',  # 30px
        
        'spacing_xs': '0.25rem',  # 4px
        'spacing_sm': '0.5rem',   # 8px
        'spacing_md': '1rem',     # 16px
        'spacing_lg': '1.5rem',   # 24px
        'spacing_xl': '2rem',     # 32px
        
        'radius_sm': '0.25rem',   # 4px
        'radius_md': '0.5rem',    # 8px
        'radius_lg': '0.75rem',   # 12px
        'radius_xl': '1rem',      # 16px
        'radius_full': '9999px',  # 완전 둥근
    }
    
    # 그림자 설정
    SHADOWS = {
        'sm': '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        'md': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
        'lg': '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
        'xl': '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
        'inner': 'inset 0 2px 4px 0 rgba(0, 0, 0, 0.06)',
    }
    
    # 애니메이션 설정
    TRANSITIONS = {
        'fast': 'all 0.15s ease-in-out',
        'normal': 'all 0.3s ease-in-out',
        'slow': 'all 0.5s ease-in-out',
    }
    
    @classmethod
    def get_css_variables(cls, dark_mode=False):
        """CSS 변수 문자열 생성"""
        colors = cls.DARK_COLORS if dark_mode else cls.COLORS
        
        css_vars = []
        
        # 색상 변수
        for key, value in colors.items():
            css_vars.append(f"--color-{key.replace('_', '-')}: {value};")
        
        # 크기 변수
        for key, value in cls.SIZES.items():
            css_vars.append(f"--{key.replace('_', '-')}: {value};")
        
        # 그림자 변수
        for key, value in cls.SHADOWS.items():
            css_vars.append(f"--shadow-{key}: {value};")
        
        # 폰트 변수
        for key, value in cls.FONTS.items():
            css_vars.append(f"--font-{key}: {value};")
        
        return "\n".join(css_vars)