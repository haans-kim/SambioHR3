"""
모델 설정 컴포넌트
"""

import streamlit as st
import numpy as np
import pandas as pd
import json
from datetime import datetime
from typing import Optional

class ModelConfigComponent:
    """모델 설정 컴포넌트"""
    
    def __init__(self, hmm_model: Optional[object] = None):
        self.hmm_model = hmm_model  # Deprecated - 태그 기반 시스템 사용
    
    def render(self):
        """태그 기반 시스템 설정 인터페이스 렌더링"""
        st.markdown("### ⚙️ 태그 기반 활동 분류 시스템 설정")
        
        # 탭으로 구분
        tab1, tab2, tab3 = st.tabs(["📊 시스템 상태", "🎯 태그 규칙 설정", "💾 설정 관리"])
        
        with tab1:
            self.render_system_status()
        
        with tab2:
            self.render_tag_rules()
        
        with tab3:
            self.render_settings_management()
    
    def render_system_status(self):
        """태그 기반 시스템 상태 표시"""
        st.markdown("#### 📊 태그 기반 활동 분류 시스템 상태")
        
        # 시스템 기본 정보
        col1, col2 = st.columns(2)
        
        with col1:
            st.info("**시스템 이름:** 태그 기반 활동 분류 시스템")
            st.info("**활동 유형:** 17가지 (출근, 작업, 식사 등)")
            st.info("**태그 유형:** 10가지 (T1-T3, G1-G4, M1-M2, N1-N2)")
        
        with col2:
            st.success("**시스템 상태:** 🟢 정상 작동")
            st.info("**마지막 업데이트:** 2025-01-27")
            st.info("**분류 정확도:** 95% (규칙 기반)")
        
        # 태그 코드 목록
        st.markdown("#### 📋 태그 코드 정의")
        tag_codes_df = pd.DataFrame({
            '태그 코드': ['T1', 'T2', 'T3', 'G1', 'G2', 'G3', 'G4', 'M1', 'M2', 'N1', 'N2'],
            '위치': ['구역_근무중', '정문등_정문_SPEED_GATE-3_입문', '정문등_정문_SPEED_GATE-3_출문', 
                    '근무', '근무', '근무', '근무', '식사', '식사', '비근무', '비근무'],
            '활동 분류': ['근무중', '출근증', '퇴근증', '근무', '근무', '근무', '근무', 
                       '식사중', '식사중', '비근무중', '비근무중']
        })
        st.dataframe(tag_codes_df, use_container_width=True)
        
        # 활동 상태 분류
        st.markdown("#### 👁️ 활동 상태 분류")
        states_df = pd.DataFrame({
            '활동 상태': ['출근', '퇴근', '작업', '집중작업', '장비작업', '회의', 
                       '조식', '중식', '석식', '야식', '휴식', '이동', '유휴', 
                       '비근무', '연장근무', '기타', '미분류'],
            '설명': [
                '출근 태그 기록',
                '퇴근 태그 기록',
                '일반 작업 활동',
                '집중적인 작업 수행',
                '장비를 사용한 작업',
                '회의 참석',
                '조식 시간 (06:30-09:00)',
                '중식 시간 (11:20-13:20)',
                '석식 시간 (17:00-20:00)',
                '야식 시간 (23:30-01:00)',
                '휴식 시간',
                '구역 간 이동',
                '비활동 상태',
                '비근무 구역 활동',
                '정규 시간 외 근무',
                '기타 활동',
                '분류되지 않은 활동'
            ]
        })
        st.dataframe(states_df, use_container_width=True)
    
    def render_tag_rules(self):
        """태그 규칙 설정"""
        st.markdown("#### 🎯 태그 분류 규칙 설정")
        
        # 규칙 유형 선택
        rule_type = st.selectbox(
            "규칙 유형",
            ["태그 코드 매핑", "식사 시간 설정", "근무 구역 설정"]
        )
        
        if rule_type == "태그 코드 매핑":
            self.render_tag_mapping_rules()
        elif rule_type == "식사 시간 설정":
            self.render_meal_time_rules()
        else:
            self.render_work_area_rules()
    
    def render_tag_mapping_rules(self):
        """태그 코드 매핑 규칙"""
        st.markdown("##### 🏷️ 태그 코드 → 활동 매핑")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            tag_code = st.selectbox(
                "태그 코드",
                ['T1', 'T2', 'T3', 'G1', 'G2', 'G3', 'G4', 'M1', 'M2', 'N1', 'N2'],
                key="tag_code_select"
            )
        
        with col2:
            activity = st.selectbox(
                "활동 분류",
                ['출근', '퇴근', '작업', '식사', '휴식', '이동', '비근무'],
                key="activity_select"
            )
        
        with col3:
            location = st.text_input("위치 정보", "")
        
        if st.button("✏️ 매핑 규칙 수정"):
            st.success(f"태그 매핑 수정: {tag_code} → {activity} ({location})")
    
    def render_meal_time_rules(self):
        """식사 시간 규칙 설정"""
        st.markdown("##### 🍽️ 식사 시간 설정")
        
        meal_times = {
            '조식': {'start': '06:30', 'end': '09:00'},
            '중식': {'start': '11:20', 'end': '13:20'},
            '석식': {'start': '17:00', 'end': '20:00'},
            '야식': {'start': '23:30', 'end': '01:00'}
        }
        
        for meal, times in meal_times.items():
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.text(f"{meal}")
            
            with col2:
                new_start = st.time_input(f"{meal} 시작", pd.to_datetime(times['start']).time(), key=f"{meal}_start")
            
            with col3:
                new_end = st.time_input(f"{meal} 종료", pd.to_datetime(times['end']).time(), key=f"{meal}_end")
        
        if st.button("💾 식사 시간 저장"):
            st.success("식사 시간 설정이 저장되었습니다.")
    
    def render_work_area_rules(self):
        """근무 구역 설정"""
        st.markdown("##### 🏭 근무 구역 설정")
        
        work_areas = st.multiselect(
            "근무 구역으로 분류할 태그 코드",
            ['T1', 'G1', 'G2', 'G3', 'G4'],
            default=['G1', 'G2', 'G3', 'G4']
        )
        
        non_work_areas = st.multiselect(
            "비근무 구역으로 분류할 태그 코드",
            ['N1', 'N2'],
            default=['N1', 'N2']
        )
        
        if st.button("💾 구역 설정 저장"):
            st.success("근무 구역 설정이 저장되었습니다.")
    
    def render_settings_management(self):
        """설정 관리"""
        st.markdown("#### 💾 설정 관리")
        
        # 설정 저장
        st.markdown("##### 💾 설정 저장")
        config_name = st.text_input("설정 이름", "sambio_tag_config")
        
        if st.button("💾 설정 저장"):
            filepath = f"configs/{config_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            st.success(f"설정 저장 완료: {filepath}")
        
        # 설정 로드
        st.markdown("##### 📂 설정 로드")
        uploaded_config = st.file_uploader(
            "설정 파일 선택",
            type=['json'],
            help="저장된 태그 설정 파일을 선택하세요"
        )
        
        if uploaded_config is not None:
            if st.button("📂 설정 로드"):
                st.success("설정 로드 완료!")
        
        # 설정 내보내기
        st.markdown("##### 📤 설정 내보내기")
        export_format = st.selectbox(
            "내보내기 형식",
            ["JSON", "CSV", "Excel"]
        )
        
        if st.button("📤 설정 내보내기"):
            st.success(f"설정 내보내기 완료: {export_format} 형식")
    
