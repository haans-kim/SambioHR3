"""
전이 룰 관리 시스템
룰의 저장, 로드, 검증, 버전 관리를 담당
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import logging
import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict

@dataclass
class TransitionRule:
    """전이 룰 데이터 클래스"""
    id: str
    from_state: str
    to_state: str
    base_probability: float
    conditions: List[Dict[str, Any]]
    confidence: int
    created_at: str
    modified_at: Optional[str] = None
    version: int = 1
    is_active: bool = True
    description: Optional[str] = None  # 설명 필드 추가
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TransitionRule':
        """딕셔너리에서 생성"""
        return cls(**data)

class RuleManager:
    """전이 룰 관리자"""
    
    def __init__(self, rules_dir: str = "config/rules"):
        self.rules_dir = Path(rules_dir)
        self.rules_dir.mkdir(parents=True, exist_ok=True)
        
        self.rules_file = self.rules_dir / "transition_rules.json"
        self.backup_dir = self.rules_dir / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        
        self.logger = logging.getLogger(__name__)
        self.rules_cache = {}
        
    def save_rule(self, rule: TransitionRule) -> bool:
        """룰 저장"""
        try:
            # 기존 룰 로드
            rules = self.load_all_rules()
            
            # 중복 확인
            existing_idx = None
            for i, r in enumerate(rules):
                if r.id == rule.id:
                    existing_idx = i
                    break
            
            # 업데이트 또는 추가
            if existing_idx is not None:
                # 버전 증가
                rule.version = rules[existing_idx].version + 1
                rule.modified_at = datetime.now().isoformat()
                rules[existing_idx] = rule
                self.logger.info(f"룰 업데이트: {rule.id} (v{rule.version})")
            else:
                rules.append(rule)
                self.logger.info(f"새 룰 추가: {rule.id}")
            
            # 파일 저장
            self._save_to_file(rules)
            
            # 캐시 업데이트
            self.rules_cache[rule.id] = rule
            
            return True
            
        except Exception as e:
            self.logger.error(f"룰 저장 실패: {e}")
            return False
    
    def load_all_rules(self) -> List[TransitionRule]:
        """모든 룰 로드"""
        # 캐시 클리어 (매번 새로 로드)
        self.rules_cache.clear()
        
        if not self.rules_file.exists():
            return []
        
        try:
            with open(self.rules_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            rules = []
            for rule_data in data:
                try:
                    rule = TransitionRule.from_dict(rule_data)
                    rules.append(rule)
                    self.rules_cache[rule.id] = rule
                except Exception as e:
                    self.logger.warning(f"룰 로드 실패: {rule_data.get('id', 'unknown')} - {e}")
            
            return rules
            
        except Exception as e:
            self.logger.error(f"룰 파일 로드 실패: {e}")
            return []
    
    def get_rule(self, rule_id: str) -> Optional[TransitionRule]:
        """특정 룰 가져오기"""
        # 캐시 확인
        if rule_id in self.rules_cache:
            return self.rules_cache[rule_id]
        
        # 파일에서 로드
        rules = self.load_all_rules()
        for rule in rules:
            if rule.id == rule_id:
                return rule
        
        return None
    
    def delete_rule(self, rule_id: str) -> bool:
        """룰 삭제 (소프트 삭제)"""
        try:
            rule = self.get_rule(rule_id)
            if not rule:
                return False
            
            # 비활성화
            rule.is_active = False
            rule.modified_at = datetime.now().isoformat()
            
            # 저장
            return self.save_rule(rule)
            
        except Exception as e:
            self.logger.error(f"룰 삭제 실패: {e}")
            return False
    
    def validate_rule(self, rule: TransitionRule) -> Tuple[bool, List[str]]:
        """룰 검증"""
        errors = []
        
        # 기본 검증
        if not rule.from_state or not rule.to_state:
            errors.append("시작/도착 상태가 필요합니다.")
        
        if not 0 <= rule.base_probability <= 1:
            errors.append("확률은 0과 1 사이여야 합니다.")
        
        if not 0 <= rule.confidence <= 100:
            errors.append("신뢰도는 0과 100 사이여야 합니다.")
        
        # 조건 검증
        for i, condition in enumerate(rule.conditions):
            if 'type' not in condition:
                errors.append(f"조건 {i+1}: 타입이 없습니다.")
                continue
            
            cond_type = condition['type']
            
            if cond_type == 'time':
                if 'start' not in condition or 'end' not in condition:
                    errors.append(f"조건 {i+1}: 시작/종료 시간이 필요합니다.")
                else:
                    try:
                        # 시간 형식 검증
                        pd.to_datetime(condition['start'], format='%H:%M')
                        pd.to_datetime(condition['end'], format='%H:%M')
                    except:
                        errors.append(f"조건 {i+1}: 시간 형식이 잘못되었습니다.")
            
            elif cond_type == 'location':
                if 'pattern' not in condition:
                    errors.append(f"조건 {i+1}: 위치 패턴이 필요합니다.")
            
            elif cond_type == 'duration':
                if 'min_duration' not in condition:
                    errors.append(f"조건 {i+1}: 최소 체류시간이 필요합니다.")
                elif condition['min_duration'] < 0:
                    errors.append(f"조건 {i+1}: 체류시간은 0 이상이어야 합니다.")
        
        return len(errors) == 0, errors
    
    def get_applicable_rules(self, from_state: str, 
                            context: Dict[str, Any]) -> List[TransitionRule]:
        """
        주어진 상황에서 적용 가능한 룰 찾기
        
        Args:
            from_state: 현재 상태
            context: 상황 정보 (시간, 위치, 체류시간 등)
            
        Returns:
            적용 가능한 룰 목록 (우선순위 순)
        """
        applicable_rules = []
        
        all_rules = self.load_all_rules()
        
        for rule in all_rules:
            if not rule.is_active:
                continue
            
            if rule.from_state != from_state:
                continue
            
            # 조건 검사
            if self._check_conditions(rule.conditions, context):
                applicable_rules.append(rule)
        
        # 신뢰도 순으로 정렬
        applicable_rules.sort(key=lambda r: r.confidence, reverse=True)
        
        return applicable_rules
    
    def _check_conditions(self, conditions: List[Dict[str, Any]], 
                         context: Dict[str, Any]) -> bool:
        """조건 충족 여부 확인"""
        if not conditions:
            return True
        
        for condition in conditions:
            cond_type = condition.get('type')
            
            if cond_type == 'time':
                if 'current_time' not in context:
                    return False
                
                current_time = pd.to_datetime(context['current_time'])
                start_time = pd.to_datetime(condition['start'], format='%H:%M').time()
                end_time = pd.to_datetime(condition['end'], format='%H:%M').time()
                
                current_time_only = current_time.time()
                
                # 자정을 넘는 경우 처리
                if start_time > end_time:
                    if not (current_time_only >= start_time or current_time_only <= end_time):
                        return False
                else:
                    if not (start_time <= current_time_only <= end_time):
                        return False
            
            elif cond_type == 'location':
                if 'location' not in context:
                    return False
                
                pattern = condition['pattern'].upper()
                location = context['location'].upper()
                
                if pattern not in location:
                    return False
            
            elif cond_type == 'duration':
                if 'duration_minutes' not in context:
                    return False
                
                if context['duration_minutes'] < condition['min_duration']:
                    return False
            
            elif cond_type == 'tag_code':
                if 'tag_code' not in context:
                    return False
                
                if context['tag_code'] != condition['code']:
                    return False
        
        return True
    
    def export_rules(self, output_path: Optional[str] = None) -> str:
        """룰 내보내기"""
        rules = self.load_all_rules()
        
        if output_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = self.backup_dir / f"rules_export_{timestamp}.json"
        
        rules_data = [rule.to_dict() for rule in rules]
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(rules_data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"룰 내보내기 완료: {output_path}")
        return str(output_path)
    
    def import_rules(self, import_path: str, merge: bool = False) -> Tuple[int, int]:
        """
        룰 가져오기
        
        Args:
            import_path: 가져올 파일 경로
            merge: True면 기존 룰과 병합, False면 덮어쓰기
            
        Returns:
            (성공 개수, 실패 개수)
        """
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                rules_data = json.load(f)
            
            if not merge:
                # 백업 생성
                self.create_backup()
                # 기존 룰 삭제
                self.rules_cache.clear()
            
            success_count = 0
            fail_count = 0
            
            for rule_data in rules_data:
                try:
                    rule = TransitionRule.from_dict(rule_data)
                    
                    # 검증
                    is_valid, errors = self.validate_rule(rule)
                    if not is_valid:
                        self.logger.warning(f"룰 검증 실패 {rule.id}: {errors}")
                        fail_count += 1
                        continue
                    
                    # 저장
                    if self.save_rule(rule):
                        success_count += 1
                    else:
                        fail_count += 1
                        
                except Exception as e:
                    self.logger.error(f"룰 가져오기 실패: {e}")
                    fail_count += 1
            
            self.logger.info(f"룰 가져오기 완료: 성공 {success_count}, 실패 {fail_count}")
            return success_count, fail_count
            
        except Exception as e:
            self.logger.error(f"파일 읽기 실패: {e}")
            return 0, len(rules_data) if 'rules_data' in locals() else 0
    
    def create_backup(self) -> str:
        """현재 룰 백업"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self.backup_dir / f"rules_backup_{timestamp}.json"
        
        rules = self.load_all_rules()
        rules_data = [rule.to_dict() for rule in rules]
        
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(rules_data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"백업 생성: {backup_path}")
        return str(backup_path)
    
    def get_rule_statistics(self) -> Dict[str, Any]:
        """룰 통계 정보"""
        rules = self.load_all_rules()
        active_rules = [r for r in rules if r.is_active]
        
        # 상태별 룰 개수
        from_state_counts = {}
        to_state_counts = {}
        
        for rule in active_rules:
            from_state_counts[rule.from_state] = from_state_counts.get(rule.from_state, 0) + 1
            to_state_counts[rule.to_state] = to_state_counts.get(rule.to_state, 0) + 1
        
        # 조건 타입별 개수
        condition_type_counts = {}
        for rule in active_rules:
            for condition in rule.conditions:
                cond_type = condition.get('type', 'unknown')
                condition_type_counts[cond_type] = condition_type_counts.get(cond_type, 0) + 1
        
        return {
            'total_rules': len(rules),
            'active_rules': len(active_rules),
            'inactive_rules': len(rules) - len(active_rules),
            'from_state_distribution': from_state_counts,
            'to_state_distribution': to_state_counts,
            'condition_type_distribution': condition_type_counts,
            'avg_conditions_per_rule': np.mean([len(r.conditions) for r in active_rules]) if active_rules else 0,
            'avg_confidence': np.mean([r.confidence for r in active_rules]) if active_rules else 0
        }
    
    def _save_to_file(self, rules: List[TransitionRule]):
        """룰을 파일에 저장"""
        rules_data = [rule.to_dict() for rule in rules]
        
        with open(self.rules_file, 'w', encoding='utf-8') as f:
            json.dump(rules_data, f, ensure_ascii=False, indent=2)
    
    def generate_rule_id(self, from_state: str, to_state: str) -> str:
        """룰 ID 생성"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"{from_state}_{to_state}_{timestamp}"