"""
전이 룰 에디터 UI 컴포넌트
HMM 상태 전이 규칙을 시각적으로 편집하는 인터페이스
"""

import streamlit as st
import pandas as pd
import json
from datetime import time, datetime
from typing import Dict, List, Any, Optional
import logging
from pathlib import Path

from ...hmm import HMMModel, HMMRuleEditor
from ...hmm.hmm_model import ActivityState
from ...rules import RuleManager, TransitionRule

class TransitionRuleEditor:
    """전이 룰 에디터 UI 클래스"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.hmm_model = HMMModel()
        self.rule_editor = HMMRuleEditor(self.hmm_model)
        
        # 룰 관리자 초기화
        self.rule_manager = RuleManager()
        
        # 활동 상태 목록
        self.states = [state.value for state in ActivityState]
        
        # 조건 타입
        self.condition_types = {
            'time': '시간대',
            'location': '위치',
            'duration': '체류시간',
            'tag_code': '태그코드',
            'day_of_week': '요일'
        }
    
    def render(self):
        """에디터 UI 렌더링"""
        st.markdown("## 🔄 전이 룰 에디터")
        st.markdown("활동 간 전이 규칙을 정의하고 관리합니다.")
        
        # 탭 구성
        tab1, tab2, tab3, tab4 = st.tabs([
            "📝 룰 편집", 
            "📊 시각화", 
            "📁 템플릿", 
            "⚙️ 설정"
        ])
        
        with tab1:
            self.render_rule_editor()
        
        with tab2:
            self.render_visualization()
        
        with tab3:
            self.render_templates()
        
        with tab4:
            self.render_settings()
    
    def render_rule_editor(self):
        """룰 편집 인터페이스"""
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("### 새 룰 추가")
            
            # From 상태 선택
            from_state = st.selectbox(
                "시작 상태",
                self.states,
                key="from_state"
            )
            
            # To 상태 선택
            to_state = st.selectbox(
                "도착 상태",
                self.states,
                key="to_state"
            )
            
            # 기본 확률
            base_probability = st.slider(
                "기본 전이 확률",
                0.0, 1.0, 0.5,
                step=0.01,
                key="base_prob"
            )
            
            # 조건 추가
            st.markdown("#### 조건 설정")
            conditions = self.render_condition_editor()
            
            # 신뢰도
            confidence = st.slider(
                "신뢰도 (%)",
                0, 100, 80,
                key="confidence"
            )
            
            # 룰 추가 버튼
            if st.button("➕ 룰 추가", type="primary"):
                self.add_rule(
                    from_state, to_state, 
                    base_probability, conditions, 
                    confidence
                )
        
        with col2:
            st.markdown("### 현재 룰 목록")
            self.render_rules_list()
    
    def render_condition_editor(self) -> List[Dict[str, Any]]:
        """조건 편집기"""
        conditions = []
        
        # 세션 상태 초기화
        if 'conditions' not in st.session_state:
            st.session_state.conditions = []
        
        # 조건 타입 선택
        condition_type = st.selectbox(
            "조건 타입",
            list(self.condition_types.keys()),
            format_func=lambda x: self.condition_types[x],
            key="condition_type"
        )
        
        # 조건 값 입력
        if condition_type == 'time':
            col1, col2 = st.columns(2)
            with col1:
                start_time = st.time_input("시작 시간", value=time(9, 0))
            with col2:
                end_time = st.time_input("종료 시간", value=time(18, 0))
            
            if st.button("시간 조건 추가"):
                condition = {
                    'type': 'time',
                    'start': start_time.strftime('%H:%M'),
                    'end': end_time.strftime('%H:%M')
                }
                st.session_state.conditions.append(condition)
        
        elif condition_type == 'location':
            location = st.text_input("위치 패턴 (예: CAFETERIA, 회의실)")
            if st.button("위치 조건 추가") and location:
                condition = {
                    'type': 'location',
                    'pattern': location
                }
                st.session_state.conditions.append(condition)
        
        elif condition_type == 'duration':
            duration_min = st.number_input(
                "최소 체류시간 (분)",
                min_value=0,
                value=30,
                step=5
            )
            if st.button("체류시간 조건 추가"):
                condition = {
                    'type': 'duration',
                    'min_duration': duration_min
                }
                st.session_state.conditions.append(condition)
        
        elif condition_type == 'tag_code':
            tag_code = st.text_input("태그 코드 (예: G1, T2)")
            if st.button("태그 조건 추가") and tag_code:
                condition = {
                    'type': 'tag_code',
                    'code': tag_code
                }
                st.session_state.conditions.append(condition)
        
        # 현재 조건 표시
        if st.session_state.conditions:
            st.markdown("##### 설정된 조건:")
            for i, cond in enumerate(st.session_state.conditions):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"{i+1}. {self._format_condition(cond)}")
                with col2:
                    if st.button("❌", key=f"del_cond_{i}"):
                        st.session_state.conditions.pop(i)
                        st.rerun()
        
        return st.session_state.conditions
    
    def _format_condition(self, condition: Dict[str, Any]) -> str:
        """조건을 읽기 쉬운 형태로 포맷팅"""
        cond_type = condition['type']
        
        if cond_type == 'time':
            return f"시간: {condition['start']} ~ {condition['end']}"
        elif cond_type == 'location':
            return f"위치: {condition['pattern']}"
        elif cond_type == 'duration':
            return f"체류시간: {condition['min_duration']}분 이상"
        elif cond_type == 'tag_code':
            return f"태그: {condition['code']}"
        else:
            return str(condition)
    
    def add_rule(self, from_state: str, to_state: str, 
                 probability: float, conditions: List[Dict], 
                 confidence: int):
        """룰 추가"""
        try:
            # 룰 ID 생성
            rule_id = self.rule_manager.generate_rule_id(from_state, to_state)
            
            # TransitionRule 객체 생성
            rule = TransitionRule(
                id=rule_id,
                from_state=from_state,
                to_state=to_state,
                base_probability=probability,
                conditions=conditions,
                confidence=confidence,
                created_at=datetime.now().isoformat(),
                version=1,
                is_active=True
            )
            
            # 룰 검증
            is_valid, errors = self.rule_manager.validate_rule(rule)
            if not is_valid:
                st.error(f"❌ 룰 검증 실패: {', '.join(errors)}")
                return
            
            # 룰 저장
            if self.rule_manager.save_rule(rule):
                # HMM 모델에 적용
                self.rule_editor.edit_transition_probability(
                    from_state, to_state, probability
                )
                
                st.success(f"✅ 룰 추가됨: {from_state} → {to_state}")
                
                # 조건 초기화
                st.session_state.conditions = []
            else:
                st.error("❌ 룰 저장 실패")
            
        except Exception as e:
            st.error(f"❌ 룰 추가 실패: {e}")
            self.logger.error(f"룰 추가 오류: {e}")
    
    
    def render_rules_list(self):
        """현재 룰 목록 표시"""
        rules = self.rule_manager.load_all_rules()
        active_rules = [r for r in rules if r.is_active]
        
        if not active_rules:
            st.info("아직 정의된 룰이 없습니다.")
            return
        
        # DataFrame으로 변환
        df_rules = []
        for rule in active_rules:
            df_rules.append({
                'From': rule.from_state,
                'To': rule.to_state,
                'Probability': f"{rule.base_probability:.2f}",
                'Conditions': len(rule.conditions),
                'Confidence': f"{rule.confidence}%",
                'Version': rule.version,
                'ID': rule.id
            })
        
        df = pd.DataFrame(df_rules)
        
        # 테이블 표시
        st.dataframe(
            df,
            hide_index=True,
            use_container_width=True
        )
        
        # 룰 삭제
        if active_rules:
            rule_to_delete = st.selectbox(
                "삭제할 룰 선택",
                [r.id for r in active_rules],
                format_func=lambda x: f"{x.split('_')[0]} → {x.split('_')[1]}"
            )
            
            if st.button("🗑️ 선택한 룰 삭제"):
                self.delete_rule(rule_to_delete)
    
    def delete_rule(self, rule_id: str):
        """룰 삭제"""
        if self.rule_manager.delete_rule(rule_id):
            st.success(f"✅ 룰 비활성화됨: {rule_id}")
            st.rerun()
        else:
            st.error(f"❌ 룰 삭제 실패: {rule_id}")
    
    def render_visualization(self):
        """전이 다이어그램 시각화"""
        st.markdown("### 상태 전이 다이어그램")
        
        # 룰 통계 표시
        stats = self.rule_manager.get_rule_statistics()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("전체 룰", stats['total_rules'])
        with col2:
            st.metric("활성 룰", stats['active_rules'])
        with col3:
            st.metric("평균 조건 수", f"{stats['avg_conditions_per_rule']:.1f}")
        with col4:
            st.metric("평균 신뢰도", f"{stats['avg_confidence']:.0f}%")
        
        # 간단한 전이 행렬 표시
        if self.hmm_model.transition_matrix is not None:
            st.markdown("#### 전이 확률 행렬")
            
            # DataFrame으로 변환
            df_matrix = pd.DataFrame(
                self.hmm_model.transition_matrix,
                index=self.states,
                columns=self.states
            )
            
            # 히트맵 스타일 적용
            st.dataframe(
                df_matrix,
                use_container_width=True
            )
        
        # 상태별 룰 분포
        st.markdown("#### 상태별 룰 분포")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("##### 시작 상태별 룰 개수")
            if stats['from_state_distribution']:
                df_from = pd.DataFrame(
                    list(stats['from_state_distribution'].items()),
                    columns=['State', 'Count']
                )
                st.bar_chart(df_from.set_index('State'))
        
        with col2:
            st.markdown("##### 도착 상태별 룰 개수")
            if stats['to_state_distribution']:
                df_to = pd.DataFrame(
                    list(stats['to_state_distribution'].items()),
                    columns=['State', 'Count']
                )
                st.bar_chart(df_to.set_index('State'))
    
    def render_templates(self):
        """룰 템플릿"""
        st.markdown("### 룰 템플릿")
        
        template_options = {
            "표준 근무": self.create_standard_work_template,
            "2교대 근무": self.create_shift_work_template,
            "식사 패턴": self.create_meal_pattern_template
        }
        
        selected_template = st.selectbox(
            "템플릿 선택",
            list(template_options.keys())
        )
        
        if st.button("📥 템플릿 적용"):
            template_func = template_options[selected_template]
            rules = template_func()
            
            # 룰 적용
            success_count = 0
            for rule_data in rules:
                # 룰 ID 생성
                rule_id = self.rule_manager.generate_rule_id(
                    rule_data['from_state'], 
                    rule_data['to_state']
                )
                
                # TransitionRule 객체 생성
                rule = TransitionRule(
                    id=rule_id,
                    from_state=rule_data['from_state'],
                    to_state=rule_data['to_state'],
                    base_probability=rule_data['base_probability'],
                    conditions=rule_data['conditions'],
                    confidence=rule_data['confidence'],
                    created_at=datetime.now().isoformat(),
                    version=1,
                    is_active=True
                )
                
                # 룰 저장
                if self.rule_manager.save_rule(rule):
                    self.rule_editor.edit_transition_probability(
                        rule.from_state,
                        rule.to_state,
                        rule.base_probability
                    )
                    success_count += 1
            
            st.success(f"✅ {selected_template} 템플릿 적용 완료 ({success_count}개 룰)")
            st.rerun()
    
    def create_standard_work_template(self) -> List[Dict[str, Any]]:
        """표준 근무 패턴 템플릿"""
        return [
            {
                'from_state': '출근',
                'to_state': '근무',
                'base_probability': 0.8,
                'conditions': [{'type': 'time', 'start': '08:00', 'end': '09:00'}],
                'confidence': 90
            },
            {
                'from_state': '근무',
                'to_state': '중식',
                'base_probability': 0.8,
                'conditions': [
                    {'type': 'time', 'start': '11:30', 'end': '13:00'},
                    {'type': 'location', 'pattern': 'CAFETERIA'}
                ],
                'confidence': 95
            },
            {
                'from_state': '중식',
                'to_state': '근무',
                'base_probability': 0.9,
                'conditions': [],
                'confidence': 90
            },
            {
                'from_state': '근무',
                'to_state': '퇴근',
                'base_probability': 0.7,
                'conditions': [{'type': 'time', 'start': '17:00', 'end': '19:00'}],
                'confidence': 85
            }
        ]
    
    def create_shift_work_template(self) -> List[Dict[str, Any]]:
        """2교대 근무 패턴 템플릿"""
        return [
            # 주간 근무
            {
                'from_state': '출근',
                'to_state': '근무',
                'base_probability': 0.8,
                'conditions': [{'type': 'time', 'start': '07:00', 'end': '08:00'}],
                'confidence': 90
            },
            # 야간 근무
            {
                'from_state': '출근',
                'to_state': '근무',
                'base_probability': 0.8,
                'conditions': [{'type': 'time', 'start': '19:00', 'end': '20:00'}],
                'confidence': 90
            },
            # 야식
            {
                'from_state': '근무',
                'to_state': '야식',
                'base_probability': 0.7,
                'conditions': [
                    {'type': 'time', 'start': '23:30', 'end': '01:00'},
                    {'type': 'location', 'pattern': 'CAFETERIA'}
                ],
                'confidence': 85
            }
        ]
    
    def create_meal_pattern_template(self) -> List[Dict[str, Any]]:
        """식사 패턴 템플릿"""
        return [
            {
                'from_state': '근무',
                'to_state': '조식',
                'base_probability': 0.6,
                'conditions': [
                    {'type': 'time', 'start': '06:30', 'end': '09:00'},
                    {'type': 'location', 'pattern': 'CAFETERIA'}
                ],
                'confidence': 90
            },
            {
                'from_state': '근무',
                'to_state': '중식',
                'base_probability': 0.8,
                'conditions': [
                    {'type': 'time', 'start': '11:20', 'end': '13:20'},
                    {'type': 'location', 'pattern': 'CAFETERIA'}
                ],
                'confidence': 95
            },
            {
                'from_state': '근무',
                'to_state': '석식',
                'base_probability': 0.7,
                'conditions': [
                    {'type': 'time', 'start': '17:00', 'end': '20:00'},
                    {'type': 'location', 'pattern': 'CAFETERIA'}
                ],
                'confidence': 90
            }
        ]
    
    def render_settings(self):
        """설정"""
        st.markdown("### 설정")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 모델 설정")
            
            # 정규화 옵션
            normalize = st.checkbox(
                "전이 확률 자동 정규화",
                value=True,
                help="각 상태의 전이 확률 합이 1이 되도록 자동 조정"
            )
            
            # 최소 확률
            min_prob = st.number_input(
                "최소 전이 확률",
                min_value=0.0,
                max_value=1.0,
                value=0.01,
                step=0.01,
                help="모든 전이에 대한 최소 확률값"
            )
        
        with col2:
            st.markdown("#### 내보내기/가져오기")
            
            # 룰 내보내기
            if st.button("💾 룰 내보내기"):
                export_path = self.rule_manager.export_rules()
                with open(export_path, 'r', encoding='utf-8') as f:
                    rules_data = f.read()
                
                st.download_button(
                    label="📥 JSON 다운로드",
                    data=rules_data,
                    file_name="transition_rules.json",
                    mime="application/json"
                )
            
            # 룰 가져오기
            uploaded_file = st.file_uploader(
                "룰 파일 업로드",
                type=['json']
            )
            
            if uploaded_file is not None:
                try:
                    # 임시 파일로 저장
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
                        json.dump(json.load(uploaded_file), temp_file, ensure_ascii=False, indent=2)
                        temp_path = temp_file.name
                    
                    # 룰 가져오기 (병합 모드)
                    success_count, fail_count = self.rule_manager.import_rules(temp_path, merge=True)
                    
                    # 임시 파일 삭제
                    Path(temp_path).unlink()
                    
                    st.success(f"✅ 룰 가져오기 완료: 성공 {success_count}개, 실패 {fail_count}개")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ 파일 로드 실패: {e}")