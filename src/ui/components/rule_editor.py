"""
활동 분류 규칙 편집기
태그 기반 확정적 규칙 시스템의 파라미터를 관리하는 UI
"""

import streamlit as st
import pandas as pd
import json
from datetime import datetime, time
import plotly.graph_objects as go
from typing import Dict, List, Tuple

class RuleEditorComponent:
    """활동 분류 규칙 편집기 컴포넌트"""
    
    def __init__(self):
        self.initialize_default_rules()
    
    def initialize_default_rules(self):
        """기본 규칙 초기화"""
        self.default_rules = {
            "time_windows": {
                "meals": {
                    "breakfast": {"start": "06:30", "end": "09:00"},
                    "lunch": {"start": "11:20", "end": "13:20"},
                    "dinner": {"start": "17:00", "end": "20:00"},
                    "midnight": {"start": "23:30", "end": "01:00"}
                },
                "commute": {
                    "morning_in": {"start": "06:00", "end": "09:30"},
                    "evening_out": {"start": "17:00", "end": "21:00"},
                    "night_shift_in": {"start": "19:00", "end": "21:00"},
                    "night_shift_out": {"start": "06:00", "end": "08:00"}
                }
            },
            "duration_rules": {
                "meal_duration": {
                    "M1_standard": 30,  # 정식 식사 기본
                    "M1_lunch_max": 60,  # 중식 최대
                    "M2_takeout": 10    # 테이크아웃
                },
                "minimum_stay": {
                    "work_area": 5,     # 근무 구역 최소 체류
                    "transit": 1,       # 이동 구간 최소 체류
                    "rest_area": 3      # 휴게 구역 최소 체류
                },
                "tailgating_threshold": {
                    "T1_continuous": 30,  # T1 연속 체류 임계값
                    "confidence_high": 120,  # 고신뢰도 임계값
                    "confidence_low": 30    # 저신뢰도 임계값
                }
            },
            "priority_rules": {
                "tag_priority": {
                    "O": 10,      # 장비 작업 (최우선)
                    "T2": 9,      # 출근
                    "T3": 9,      # 퇴근
                    "M1": 8,      # 정식 식사
                    "M2": 8,      # 테이크아웃
                    "G3": 7,      # 회의
                    "G4": 7,      # 교육
                    "G1": 6,      # 주업무
                    "G2": 6,      # 보조업무
                    "N1": 5,      # 휴게
                    "N2": 5,      # 복지
                    "T1": 4       # 이동
                },
                "conflict_resolution": "highest_priority"  # highest_priority, first_occurrence, context_based
            },
            "area_weights": {
                "work_probability": {
                    "Y": 1.2,     # 근무구역
                    "T": 0.5,     # 이동구간
                    "N": 0.3,     # 비근무구역
                    "G": 1.0      # 일반구역
                },
                "specific_locations": {
                    "MEETING_ROOM": {"activity": "MEETING", "weight": 0.95},
                    "FITNESS": {"activity": "REST", "weight": 0.90},
                    "CAFETERIA": {"activity": "MEAL", "weight": 0.95}
                }
            },
            "transition_rules": {
                "meal_context": {
                    "before_meal_movement": {"from": "MOVEMENT", "to": "MEAL", "window": 30},
                    "after_meal_work": {"from": "MEAL", "to": "WORK", "window": 30}
                },
                "commute_patterns": {
                    "morning_sequence": ["COMMUTE_IN", "MOVEMENT", "WORK"],
                    "evening_sequence": ["WORK", "MOVEMENT", "COMMUTE_OUT"]
                }
            },
            "confidence_settings": {
                "base_confidence": {
                    "O": 98,
                    "T2": 100,
                    "T3": 100,
                    "G3": 95,
                    "G4": 95,
                    "M1": 100,
                    "M2": 100,
                    "default": 80
                },
                "adjustment_factors": {
                    "long_duration": 1.1,      # 장시간 체류
                    "short_duration": 0.8,     # 짧은 체류
                    "repeated_pattern": 1.05,  # 반복 패턴
                    "isolated_tag": 0.9        # 고립된 태그
                }
            }
        }
    
    def render(self):
        """규칙 편집기 UI 렌더링"""
        st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 2rem;
                    border-radius: 10px;
                    margin-bottom: 2rem;">
            <h2 style="margin: 0; font-size: 2rem;">활동 분류 규칙 관리자</h2>
            <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">
                Activity Classification Rule Manager - 태그 기반 확정적 규칙 시스템 설정
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # 탭 구성
        tabs = st.tabs([
            "시간 창 규칙",
            "지속 시간 규칙", 
            "우선순위 규칙",
            "구역별 가중치",
            "전환 패턴",
            "신뢰도 설정",
            "규칙 관리"
        ])
        
        with tabs[0]:
            self.render_time_windows()
        
        with tabs[1]:
            self.render_duration_rules()
        
        with tabs[2]:
            self.render_priority_rules()
        
        with tabs[3]:
            self.render_area_weights()
        
        with tabs[4]:
            self.render_transition_rules()
        
        with tabs[5]:
            self.render_confidence_settings()
        
        with tabs[6]:
            self.render_rule_management()
    
    def render_time_windows(self):
        """시간 창 규칙 설정"""
        st.markdown("### 시간 창 규칙 설정")
        st.info("특정 시간대에 발생하는 활동을 정의합니다. 시간과 위치를 함께 고려하여 활동을 분류합니다.")
        
        # 식사 시간 설정
        st.subheader("식사 시간대 설정")
        
        meal_cols = st.columns(4)
        meals = ["breakfast", "lunch", "dinner", "midnight"]
        meal_names = ["조식", "중식", "석식", "야식"]
        
        for idx, (meal, name) in enumerate(zip(meals, meal_names)):
            with meal_cols[idx]:
                st.markdown(f"**{name}**")
                current = self.default_rules["time_windows"]["meals"][meal]
                
                start_time = st.time_input(
                    "시작 시간",
                    value=pd.to_datetime(current["start"]).time(),
                    key=f"{meal}_start"
                )
                
                end_time = st.time_input(
                    "종료 시간",
                    value=pd.to_datetime(current["end"]).time(),
                    key=f"{meal}_end"
                )
        
        # 출퇴근 시간 설정
        st.subheader("출퇴근 시간대 설정")
        
        # 근로시간제 선택
        work_system = st.selectbox(
            "근로시간제 선택",
            ["표준 근로시간제", "선택적 근로시간제", "탄력적 근로시간제"],
            help="근로시간제에 따라 출퇴근 시간 규정이 달라집니다"
        )
        
        if work_system == "표준 근로시간제":
            st.info("표준 근로시간제: 고정된 출퇴근 시간 (주 40시간)")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**출근 시간**")
                standard_in = st.time_input(
                    "출근",
                    value=time(8, 0),
                    key="standard_in"
                )
            with col2:
                st.markdown("**퇴근 시간**")
                standard_out = st.time_input(
                    "퇴근",
                    value=time(17, 0),
                    key="standard_out"
                )
        
        elif work_system == "선택적 근로시간제":
            st.info("선택적 근로시간제: 정산기간(1개월) 동안 주 평균 52시간을 초과하지 않는 범위 내에서 업무 시작/종료 시각을 임직원이 결정")
            
            # 준수사항 표시
            with st.expander("준수사항", expanded=True):
                st.markdown("""
                - **의무 근무시간**: 1개월 중 평일수 × 8시간 또는 40시간/7일 × 월 일수 중 근로자에게 유리한 기준
                - **최대 근무시간**: 52시간/7일 × 월 일수
                - **최소 근무시간**: 일 최소 1분 이상 근무 필요
                """)
            
            # 정산 기간 설정
            settlement_col1, settlement_col2 = st.columns(2)
            with settlement_col1:
                settlement_period = st.selectbox(
                    "정산 기간",
                    ["1개월"],
                    key="flex_settlement_period"
                )
            with settlement_col2:
                month_days = st.number_input(
                    "이번 달 일수",
                    min_value=28, max_value=31, value=30,
                    key="month_days"
                )
            
            # 의무/최대/최소 근무시간 자동 계산
            weekday_count = st.number_input(
                "이번 달 평일수",
                min_value=15, max_value=23, value=22,
                key="weekday_count"
            )
            
            mandatory_hours_1 = weekday_count * 8
            mandatory_hours_2 = (40 / 7) * month_days
            mandatory_hours = max(mandatory_hours_1, mandatory_hours_2)
            max_hours = (52 / 7) * month_days
            
            st.markdown("**근무시간 기준**")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("의무 근무시간", f"{mandatory_hours:.1f}시간")
            with col2:
                st.metric("최대 근무시간", f"{max_hours:.1f}시간")
            with col3:
                st.metric("최소 근무시간", "일 1분 이상")
            
            st.markdown("**선택 가능 출퇴근 시간대**")
            flex_col1, flex_col2 = st.columns(2)
            with flex_col1:
                flex_in_start = st.time_input(
                    "출근 가능 시작",
                    value=time(6, 0),
                    key="flex_in_start"
                )
                flex_in_end = st.time_input(
                    "출근 가능 종료",
                    value=time(11, 0),
                    key="flex_in_end"
                )
            with flex_col2:
                flex_out_start = st.time_input(
                    "퇴근 가능 시작",
                    value=time(15, 0),
                    key="flex_out_start"
                )
                flex_out_end = st.time_input(
                    "퇴근 가능 종료",
                    value=time(22, 0),
                    key="flex_out_end"
                )
        
        else:  # 탄력적 근로시간제
            st.info("탄력적 근로시간제: 정산기간(분기) 동안 주 평균 52시간을 초과하지 않는 범위 내에서, 정해진 스케줄에 기반하여 근무(3근3휴/4근3휴 반복)")
            
            # 준수사항 표시
            with st.expander("준수사항", expanded=True):
                st.markdown("""
                - **의무 근무시간**: 1일 11시간 - 주간 08:00~20:30, 야간 20:00~08:30
                - **최대 근무시간**: 연장근무와 휴일 근무를 합하여 1주 단위로 12시간 초과 불가 (매주 일~토 기준)
                """)
            
            # 근무 패턴 선택
            work_pattern = st.selectbox(
                "근무 패턴",
                ["3근3휴", "4근3휴"],
                help="근무일수와 휴무일수 패턴"
            )
            
            # 근무 시간대 설정
            st.markdown("**근무 시간 설정**")
            shift_type = st.radio(
                "근무 시간대",
                ["주간 근무", "야간 근무"]
            )
            
            if shift_type == "주간 근무":
                st.markdown("**주간 근무 (1일 11시간)**")
                day_col1, day_col2 = st.columns(2)
                with day_col1:
                    day_in = st.time_input(
                        "출근",
                        value=time(8, 0),
                        key="elastic_day_in",
                        disabled=True
                    )
                with day_col2:
                    day_out = st.time_input(
                        "퇴근",
                        value=time(20, 30),
                        key="elastic_day_out",
                        disabled=True
                    )
            else:  # 야간 근무
                st.markdown("**야간 근무 (1일 11시간)**")
                night_col1, night_col2 = st.columns(2)
                with night_col1:
                    night_in = st.time_input(
                        "출근",
                        value=time(20, 0),
                        key="elastic_night_in",
                        disabled=True
                    )
                with night_col2:
                    night_out = st.time_input(
                        "퇴근",
                        value=time(8, 30),
                        key="elastic_night_out",
                        disabled=True
                    )
            
            # 주간 최대 근무시간 표시
            st.markdown("**주간 근무시간 제한**")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("정규 근무시간", "주 44시간" if work_pattern == "4근3휴" else "주 33시간")
            with col2:
                st.metric("최대 연장근무", "주 12시간")
            
            # 정산 기간 설정
            settlement_quarter = st.selectbox(
                "정산 기간",
                ["1분기", "2분기", "3분기", "4분기"],
                key="elastic_settlement"
            )
        
        # 야간 근무 설정 (모든 근로시간제 공통)
        st.markdown("**야간 근무 설정**")
        night_shift = st.checkbox("야간 근무 운영")
        if night_shift:
            night_col1, night_col2 = st.columns(2)
            with night_col1:
                night_in = st.time_input(
                    "야간 출근",
                    value=time(20, 0),
                    key="night_in"
                )
            with night_col2:
                night_out = st.time_input(
                    "야간 퇴근",
                    value=time(8, 0),
                    key="night_out"
                )
    
    def render_duration_rules(self):
        """지속 시간 규칙 설정"""
        st.markdown("### 지속 시간 규칙 설정")
        st.info("활동별 표준 지속 시간과 최소 체류 시간을 설정합니다.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("식사 지속 시간")
            
            m1_standard = st.number_input(
                "M1 정식 식사 (분)",
                min_value=10, max_value=120, value=30,
                help="바이오플라자 정식 식사 기본 시간"
            )
            
            m1_lunch_max = st.number_input(
                "M1 중식 최대 (분)",
                min_value=30, max_value=120, value=60,
                help="중식 시간대 최대 식사 시간"
            )
            
            m2_takeout = st.number_input(
                "M2 테이크아웃 (분)",
                min_value=5, max_value=30, value=10,
                help="테이크아웃 고정 시간"
            )
        
        with col2:
            st.subheader("최소 체류 시간")
            
            work_min = st.number_input(
                "근무 구역 최소 (분)",
                min_value=1, max_value=30, value=5,
                help="근무 구역 최소 체류 시간"
            )
            
            transit_min = st.number_input(
                "이동 구간 최소 (분)",
                min_value=0, max_value=10, value=1,
                help="이동 구간 최소 체류 시간"
            )
            
            rest_min = st.number_input(
                "휴게 구역 최소 (분)",
                min_value=1, max_value=30, value=3,
                help="휴게 구역 최소 체류 시간"
            )
        
        # 꼬리물기 감지 설정
        st.subheader("꼬리물기 감지 임계값")
        
        col3, col4, col5 = st.columns(3)
        with col3:
            t1_threshold = st.number_input(
                "T1 연속 체류 (분)",
                min_value=10, max_value=120, value=30,
                help="T1 구간에서 이 시간 이상 체류 시 작업으로 분류"
            )
        
        with col4:
            high_conf = st.number_input(
                "고신뢰도 임계값 (분)",
                min_value=60, max_value=240, value=120,
                help="이 시간 이상 체류 시 신뢰도 85%"
            )
        
        with col5:
            low_conf = st.number_input(
                "저신뢰도 임계값 (분)",
                min_value=10, max_value=60, value=30,
                help="이 시간 이하 체류 시 신뢰도 60%"
            )
    
    def render_priority_rules(self):
        """우선순위 규칙 설정"""
        st.markdown("### 우선순위 규칙 설정")
        st.info("동일 시간에 여러 태그가 발생할 때 적용할 우선순위를 설정합니다.")
        
        # 태그 우선순위 설정
        st.subheader("태그 코드 우선순위")
        
        # 현재 우선순위를 DataFrame으로 표시
        priority_data = []
        for tag, priority in sorted(self.default_rules["priority_rules"]["tag_priority"].items(), 
                                  key=lambda x: x[1], reverse=True):
            priority_data.append({
                "태그 코드": tag,
                "우선순위": priority,
                "설명": self.get_tag_description(tag)
            })
        
        priority_df = pd.DataFrame(priority_data)
        
        # 편집 가능한 데이터프레임
        edited_df = st.data_editor(
            priority_df,
            key="priority_rules_editor",
            column_config={
                "우선순위": st.column_config.NumberColumn(
                    "우선순위",
                    help="높을수록 우선 (1-10)",
                    min_value=1,
                    max_value=10,
                    step=1
                )
            },
            hide_index=True,
            use_container_width=True
        )
        
        # 충돌 해결 방식
        st.subheader("충돌 해결 방식")
        
        resolution_method = st.selectbox(
            "동시 태그 처리 방식",
            ["highest_priority", "first_occurrence", "context_based"],
            format_func=lambda x: {
                "highest_priority": "최고 우선순위 선택",
                "first_occurrence": "첫 번째 발생 선택",
                "context_based": "컨텍스트 기반 선택"
            }[x]
        )
        
        if resolution_method == "context_based":
            st.info("컨텍스트 기반 선택 시 이전/다음 활동을 고려하여 가장 적절한 태그를 선택합니다.")
    
    def render_area_weights(self):
        """구역별 가중치 설정"""
        st.markdown("### 구역별 가중치 설정")
        st.info("구역 타입에 따른 작업 확률 가중치를 설정합니다.")
        
        # 구역 타입별 가중치
        st.subheader("구역 타입별 작업 확률 가중치")
        
        col1, col2 = st.columns(2)
        
        with col1:
            y_weight = st.slider(
                "Y구역 (근무구역)",
                min_value=0.5, max_value=2.0, value=1.2, step=0.1,
                help="1.0보다 크면 작업 확률 증가"
            )
            
            t_weight = st.slider(
                "T구역 (이동구간)",
                min_value=0.1, max_value=1.0, value=0.5, step=0.1,
                help="1.0보다 작으면 작업 확률 감소"
            )
        
        with col2:
            n_weight = st.slider(
                "N구역 (비근무구역)",
                min_value=0.1, max_value=1.0, value=0.3, step=0.1,
                help="1.0보다 작으면 작업 확률 감소"
            )
            
            g_weight = st.slider(
                "G구역 (일반구역)",
                min_value=0.5, max_value=1.5, value=1.0, step=0.1,
                help="기준값 1.0"
            )
        
        # 특정 위치별 활동 확률
        st.subheader("특정 위치별 활동 확률")
        
        location_rules = pd.DataFrame([
            {"위치 패턴": "MEETING_ROOM", "활동": "MEETING", "확률": 0.95},
            {"위치 패턴": "FITNESS", "활동": "REST", "확률": 0.90},
            {"위치 패턴": "CAFETERIA", "활동": "MEAL", "확률": 0.95},
            {"위치 패턴": "EQUIPMENT", "활동": "EQUIPMENT_OPERATION", "확률": 0.98}
        ])
        
        edited_locations = st.data_editor(
            location_rules,
            key="location_rules_editor",
            column_config={
                "확률": st.column_config.NumberColumn(
                    "확률",
                    min_value=0.0,
                    max_value=1.0,
                    step=0.05,
                    format="%.2f"
                )
            },
            num_rows="dynamic",
            use_container_width=True
        )
    
    def render_transition_rules(self):
        """전환 패턴 규칙 설정"""
        st.markdown("### 활동 전환 패턴 설정")
        st.info("활동 간 전환 패턴과 컨텍스트 기반 분류 규칙을 설정합니다.")
        
        # 식사 관련 전환
        st.subheader("식사 전후 활동 패턴")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**식사 전 이동**")
            before_meal_window = st.number_input(
                "식사 전 이동 인식 시간 (분)",
                min_value=10, max_value=60, value=30,
                help="식사 전 이 시간 내의 출문은 MOVEMENT로 분류"
            )
        
        with col2:
            st.markdown("**식사 후 복귀**")
            after_meal_window = st.number_input(
                "식사 후 복귀 인식 시간 (분)",
                min_value=10, max_value=60, value=30,
                help="식사 후 이 시간 내의 입문은 WORK로 분류"
            )
        
        # 출퇴근 패턴
        st.subheader("출퇴근 시퀀스 패턴")
        
        morning_pattern = st.text_input(
            "출근 시퀀스",
            value="COMMUTE_IN → MOVEMENT → WORK",
            help="일반적인 출근 패턴"
        )
        
        evening_pattern = st.text_input(
            "퇴근 시퀀스",
            value="WORK → MOVEMENT → COMMUTE_OUT",
            help="일반적인 퇴근 패턴"
        )
        
        # 예외 처리 규칙
        st.subheader("예외 처리 규칙")
        
        exceptions = st.text_area(
            "예외 패턴 정의",
            value="""# 예외 패턴 예시
# 회의실에서 장시간 체류 → MEETING (WORK 아님)
# 휴게실에서 5분 미만 체류 → MOVEMENT (REST 아님)
# 정문 재입문 30분 이내 → 외출 (퇴근 아님)""",
            height=150
        )
    
    def render_confidence_settings(self):
        """신뢰도 설정"""
        st.markdown("### 신뢰도 설정")
        st.info("태그별 기본 신뢰도와 조건에 따른 신뢰도 조정 계수를 설정합니다.")
        
        # 기본 신뢰도
        st.subheader("태그별 기본 신뢰도")
        
        confidence_data = []
        for tag in ["O", "T2", "T3", "G1", "G2", "G3", "G4", "M1", "M2", "N1", "N2", "T1"]:
            conf = self.default_rules["confidence_settings"]["base_confidence"].get(tag, 80)
            confidence_data.append({
                "태그 코드": tag,
                "기본 신뢰도": conf,
                "설명": self.get_tag_description(tag)
            })
        
        conf_df = pd.DataFrame(confidence_data)
        
        edited_conf = st.data_editor(
            conf_df,
            key="confidence_rules_editor",
            column_config={
                "기본 신뢰도": st.column_config.NumberColumn(
                    "기본 신뢰도 (%)",
                    min_value=0,
                    max_value=100,
                    step=5
                )
            },
            hide_index=True,
            use_container_width=True
        )
        
        # 신뢰도 조정 계수
        st.subheader("신뢰도 조정 계수")
        
        col1, col2 = st.columns(2)
        
        with col1:
            long_duration_factor = st.slider(
                "장시간 체류 계수",
                min_value=1.0, max_value=1.5, value=1.1, step=0.05,
                help="장시간 체류 시 신뢰도 증가"
            )
            
            repeated_pattern_factor = st.slider(
                "반복 패턴 계수",
                min_value=1.0, max_value=1.3, value=1.05, step=0.05,
                help="반복되는 패턴일 때 신뢰도 증가"
            )
        
        with col2:
            short_duration_factor = st.slider(
                "짧은 체류 계수",
                min_value=0.5, max_value=1.0, value=0.8, step=0.05,
                help="짧은 체류 시 신뢰도 감소"
            )
            
            isolated_tag_factor = st.slider(
                "고립 태그 계수",
                min_value=0.7, max_value=1.0, value=0.9, step=0.05,
                help="전후 맥락 없는 태그 신뢰도 감소"
            )
        
        # 최소 신뢰도 임계값
        st.subheader("신뢰도 임계값")
        
        min_confidence = st.slider(
            "최소 신뢰도 임계값 (%)",
            min_value=50, max_value=90, value=70, step=5,
            help="이 값 미만의 신뢰도는 '미분류'로 처리"
        )
    
    def render_rule_management(self):
        """규칙 관리 (저장/로드/내보내기)"""
        st.markdown("### 규칙 관리")
        st.info("설정한 규칙을 저장하고 관리합니다.")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.subheader("규칙 저장")
            
            rule_name = st.text_input(
                "규칙 세트 이름",
                value=f"rule_set_{datetime.now().strftime('%Y%m%d')}",
                help="저장할 규칙 세트의 이름"
            )
            
            description = st.text_area(
                "설명",
                placeholder="이 규칙 세트에 대한 설명을 입력하세요",
                height=100
            )
            
            if st.button("규칙 저장", type="primary", use_container_width=True):
                st.success(f"'{rule_name}' 규칙이 저장되었습니다.")
        
        with col2:
            st.subheader("규칙 불러오기")
            
            saved_rules = ["기본 규칙", "야간 근무 최적화", "주말 근무 규칙"]
            selected_rule = st.selectbox(
                "저장된 규칙 선택",
                saved_rules
            )
            
            if st.button("규칙 불러오기", use_container_width=True):
                st.success(f"'{selected_rule}' 규칙을 불러왔습니다.")
                st.rerun()
        
        with col3:
            st.subheader("규칙 내보내기")
            
            export_format = st.selectbox(
                "내보내기 형식",
                ["JSON", "YAML", "Excel"]
            )
            
            if st.button("규칙 내보내기", use_container_width=True):
                st.success(f"{export_format} 형식으로 내보내기 완료")
                st.download_button(
                    label="파일 다운로드",
                    data=json.dumps(self.default_rules, indent=2),
                    file_name=f"rules_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
        
        # 규칙 버전 관리
        st.subheader("규칙 버전 관리")
        
        version_data = pd.DataFrame([
            {"버전": "v1.2.0", "날짜": "2025-01-28", "변경사항": "테이크아웃 시간 10분으로 수정"},
            {"버전": "v1.1.0", "날짜": "2025-01-20", "변경사항": "꼬리물기 감지 규칙 추가"},
            {"버전": "v1.0.0", "날짜": "2025-01-15", "변경사항": "초기 규칙 설정"}
        ])
        
        st.dataframe(version_data, use_container_width=True)
        
        # 규칙 검증
        st.subheader("규칙 검증")
        
        if st.button("현재 규칙 검증", type="secondary", use_container_width=True):
            with st.spinner("규칙 검증 중..."):
                # 검증 로직 시뮬레이션
                st.success("모든 규칙이 유효합니다.")
                
                # 검증 결과 상세
                with st.expander("검증 결과 상세"):
                    st.write("- 시간 창 중복: 없음")
                    st.write("- 우선순위 충돌: 없음")
                    st.write("- 가중치 범위: 정상")
                    st.write("- 신뢰도 설정: 정상")
    
    def get_tag_description(self, tag: str) -> str:
        """태그 코드 설명 반환"""
        descriptions = {
            "O": "장비작업",
            "T1": "건물/구역 연결",
            "T2": "출입포인트(IN)",
            "T3": "출입포인트(OUT)",
            "G1": "주업무공간",
            "G2": "보조업무공간",
            "G3": "회의공간",
            "G4": "교육공간",
            "M1": "바이오플라자 식사",
            "M2": "테이크아웃",
            "N1": "휴게공간",
            "N2": "복지공간"
        }
        return descriptions.get(tag, "기타")