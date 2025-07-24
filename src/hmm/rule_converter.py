"""
HMM 전이 확률을 편집 가능한 JSON 규칙으로 변환하는 모듈
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
import logging

from .hmm_model import ActivityState, HMMModel

class HMMRuleConverter:
    """HMM 규칙 변환기"""
    
    def __init__(self, hmm_model: HMMModel):
        self.hmm_model = hmm_model
        self.logger = logging.getLogger(__name__)
        
    def extract_transition_rules(self) -> List[Dict[str, Any]]:
        """HMM 모델의 전이 확률을 JSON 규칙으로 변환"""
        rules = []
        
        # 도메인 지식 기반 전이 규칙 추출
        for from_state in ActivityState:
            for to_state in ActivityState:
                prob = self.hmm_model._get_transition_probability(
                    from_state.value, to_state.value
                )
                
                # 의미있는 확률만 규칙으로 생성 (0.01 초과)
                if prob > 0.01:
                    rule = self._create_transition_rule(
                        from_state.value, to_state.value, prob
                    )
                    rules.append(rule)
        
        return rules
    
    def _create_transition_rule(self, from_state: str, to_state: str, 
                               probability: float) -> Dict[str, Any]:
        """단일 전이 규칙 생성"""
        # 규칙 ID 생성
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        rule_id = f"{from_state}_{to_state}_{timestamp}"
        
        # 조건 생성 (특수 케이스)
        conditions = self._generate_conditions(from_state, to_state)
        
        # 신뢰도 계산 (도메인 지식 기반은 높은 신뢰도)
        confidence = self._calculate_confidence(from_state, to_state, probability)
        
        return {
            "id": rule_id,
            "from_state": from_state,
            "to_state": to_state,
            "base_probability": round(probability, 4),
            "conditions": conditions,
            "confidence": confidence,
            "created_at": datetime.now().isoformat(),
            "modified_at": None,
            "version": 1,
            "is_active": True,
            "description": self._generate_description(from_state, to_state)
        }
    
    def _generate_conditions(self, from_state: str, to_state: str) -> List[Dict[str, Any]]:
        """상태 전이에 대한 조건 생성"""
        conditions = []
        
        # 식사 관련 조건
        meal_states = ["조식", "중식", "석식", "야식"]
        if to_state in meal_states:
            meal_time_map = {
                "조식": {"start": "06:30", "end": "09:00"},
                "중식": {"start": "11:20", "end": "13:20"},
                "석식": {"start": "17:00", "end": "20:00"},
                "야식": {"start": "23:30", "end": "01:00"}
            }
            
            if to_state in meal_time_map:
                conditions.append({
                    "type": "time_window",
                    "parameters": meal_time_map[to_state],
                    "operator": "within",
                    "weight": 0.8
                })
                
                conditions.append({
                    "type": "location",
                    "parameters": {"location": "CAFETERIA"},
                    "operator": "equals",
                    "weight": 0.9
                })
        
        # 야간 교대 조건
        if to_state == "야식":
            conditions.append({
                "type": "shift_type",
                "parameters": {"shift": "야간"},
                "operator": "equals",
                "weight": 0.7
            })
        
        # 퇴근 후 재입문 조건
        if from_state == "퇴근" and to_state == "출근":
            conditions.append({
                "type": "time_since_last_event",
                "parameters": {"minutes": 30},
                "operator": "greater_than",
                "weight": 0.6
            })
        
        return conditions
    
    def _calculate_confidence(self, from_state: str, to_state: str, 
                            probability: float) -> int:
        """규칙의 신뢰도 계산 (0-100)"""
        # 기본 신뢰도
        base_confidence = 70
        
        # 높은 확률은 높은 신뢰도
        if probability > 0.5:
            base_confidence += 20
        elif probability > 0.3:
            base_confidence += 10
        
        # 주요 전이 패턴은 높은 신뢰도
        high_confidence_patterns = [
            ("출근", "근무"),
            ("조식", "근무"),
            ("중식", "근무"),
            ("석식", "근무"),
            ("근무", "퇴근")
        ]
        
        if (from_state, to_state) in high_confidence_patterns:
            base_confidence = min(base_confidence + 15, 100)
        
        return base_confidence
    
    def _generate_description(self, from_state: str, to_state: str) -> str:
        """규칙에 대한 설명 생성"""
        descriptions = {
            ("출근", "근무"): "출근 후 업무 시작",
            ("출근", "조식"): "출근 후 조식 이용",
            ("출근", "이동"): "출근 후 사무실로 이동",
            ("근무", "집중근무"): "일반 근무에서 집중 업무로 전환",
            ("근무", "회의"): "업무 중 회의 참석",
            ("근무", "휴식"): "업무 중 휴식",
            ("근무", "퇴근"): "업무 종료 후 퇴근",
            ("조식", "근무"): "조식 후 업무 복귀",
            ("중식", "근무"): "중식 후 업무 복귀",
            ("석식", "근무"): "석식 후 업무 복귀",
            ("야식", "근무"): "야식 후 업무 복귀",
            ("이동", "근무"): "이동 후 업무 시작",
            ("퇴근", "출근"): "점심시간 외출 후 재입문"
        }
        
        return descriptions.get((from_state, to_state), 
                              f"{from_state}에서 {to_state}로 전이")
    
    def save_rules_to_file(self, filepath: Optional[str] = None):
        """규칙을 JSON 파일로 저장"""
        if filepath is None:
            filepath = "config/rules/hmm_transition_rules.json"
        
        # 디렉토리 생성
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        # 규칙 추출
        rules = self.extract_transition_rules()
        
        # 파일 저장
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"전이 규칙 {len(rules)}개를 {filepath}에 저장했습니다")
        
        return filepath
    
    def merge_with_existing_rules(self, existing_filepath: str, 
                                 output_filepath: Optional[str] = None):
        """기존 규칙과 병합"""
        # 기존 규칙 로드
        existing_rules = []
        if Path(existing_filepath).exists():
            with open(existing_filepath, 'r', encoding='utf-8') as f:
                existing_rules = json.load(f)
        
        # 새 규칙 추출
        new_rules = self.extract_transition_rules()
        
        # 기존 규칙의 ID 집합
        existing_ids = {(r['from_state'], r['to_state']) 
                       for r in existing_rules}
        
        # 병합 (중복 제거)
        merged_rules = existing_rules.copy()
        
        for rule in new_rules:
            key = (rule['from_state'], rule['to_state'])
            if key not in existing_ids:
                merged_rules.append(rule)
        
        # 저장
        if output_filepath is None:
            output_filepath = existing_filepath
        
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(merged_rules, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"병합된 규칙 {len(merged_rules)}개를 저장했습니다")
        
        return output_filepath