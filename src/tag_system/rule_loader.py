"""
규칙 설정 로더
JSON 파일에서 규칙을 로드하고 관리
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime

from .rule_engine import RuleConfig

logger = logging.getLogger(__name__)


class RuleLoader:
    """규칙 설정 로더"""
    
    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            # 기본 경로: config/rules/deterministic_rules.json
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / 'config' / 'rules' / 'deterministic_rules.json'
        
        self.config_path = Path(config_path)
        self._config_data = None
        self._rule_config = None
        self._last_loaded = None
    
    def load_config(self, force_reload: bool = False) -> RuleConfig:
        """설정 파일 로드"""
        if not force_reload and self._rule_config is not None:
            return self._rule_config
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config_data = json.load(f)
            
            # RuleConfig 객체 생성
            config_section = self._config_data.get('config', {})
            self._rule_config = RuleConfig(
                meal_max_duration_minutes=config_section.get('meal_max_duration_minutes', 60),
                takeout_fixed_duration_minutes=config_section.get('takeout_fixed_duration_minutes', 30),
                short_duration_threshold_minutes=config_section.get('short_duration_threshold_minutes', 5),
                long_duration_threshold_minutes=config_section.get('long_duration_threshold_minutes', 120),
                critical_confidence=config_section.get('critical_confidence', 0.98),
                high_confidence=config_section.get('high_confidence', 0.95),
                medium_confidence=config_section.get('medium_confidence', 0.90)
            )
            
            self._last_loaded = datetime.now()
            logger.info(f"규칙 설정 로드 완료: {self.config_path}")
            
            return self._rule_config
            
        except FileNotFoundError:
            logger.warning(f"설정 파일 없음: {self.config_path}")
            return RuleConfig()  # 기본값 사용
        
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 오류: {e}")
            return RuleConfig()
        
        except Exception as e:
            logger.error(f"설정 로드 오류: {e}")
            return RuleConfig()
    
    def get_rule_definitions(self) -> Dict[str, Any]:
        """규칙 정의 반환"""
        if self._config_data is None:
            self.load_config()
        
        return self._config_data.get('rule_definitions', {}) if self._config_data else {}
    
    def get_time_windows(self) -> Dict[str, Any]:
        """시간 윈도우 설정 반환"""
        if self._config_data is None:
            self.load_config()
        
        return self._config_data.get('time_windows', {}) if self._config_data else {}
    
    def save_config(self, config: RuleConfig) -> bool:
        """설정 저장"""
        try:
            # 기존 데이터 로드
            if self._config_data is None:
                self.load_config()
            
            # config 섹션 업데이트
            self._config_data['config'] = {
                'meal_max_duration_minutes': config.meal_max_duration_minutes,
                'takeout_fixed_duration_minutes': config.takeout_fixed_duration_minutes,
                'short_duration_threshold_minutes': config.short_duration_threshold_minutes,
                'long_duration_threshold_minutes': config.long_duration_threshold_minutes,
                'critical_confidence': config.critical_confidence,
                'high_confidence': config.high_confidence,
                'medium_confidence': config.medium_confidence
            }
            
            # 업데이트 시간
            self._config_data['last_updated'] = datetime.now().strftime('%Y-%m-%d')
            
            # 파일 저장
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config_data, f, indent=2, ensure_ascii=False)
            
            logger.info("규칙 설정 저장 완료")
            return True
            
        except Exception as e:
            logger.error(f"설정 저장 오류: {e}")
            return False
    
    def update_rule(self, category: str, rule_id: str, updates: Dict[str, Any]) -> bool:
        """특정 규칙 업데이트"""
        try:
            if self._config_data is None:
                self.load_config()
            
            # 규칙 찾기
            rule_definitions = self._config_data.get('rule_definitions', {})
            if category not in rule_definitions:
                logger.warning(f"규칙 카테고리 없음: {category}")
                return False
            
            rules = rule_definitions[category].get('rules', [])
            for rule in rules:
                if rule.get('id') == rule_id:
                    # 규칙 업데이트
                    rule.update(updates)
                    
                    # 파일 저장
                    with open(self.config_path, 'w', encoding='utf-8') as f:
                        json.dump(self._config_data, f, indent=2, ensure_ascii=False)
                    
                    logger.info(f"규칙 업데이트 완료: {category}/{rule_id}")
                    return True
            
            logger.warning(f"규칙 ID 없음: {rule_id}")
            return False
            
        except Exception as e:
            logger.error(f"규칙 업데이트 오류: {e}")
            return False
    
    def get_legal_notice(self) -> Optional[str]:
        """법적 고지사항 반환"""
        if self._config_data is None:
            self.load_config()
        
        return self._config_data.get('legal_notice') if self._config_data else None
    
    def validate_config(self) -> Dict[str, Any]:
        """설정 유효성 검증"""
        issues = []
        warnings = []
        
        try:
            config = self.load_config()
            
            # 식사 시간 검증
            if config.meal_max_duration_minutes > 120:
                warnings.append("식사 최대 시간이 120분을 초과합니다")
            
            if config.takeout_fixed_duration_minutes > 60:
                warnings.append("테이크아웃 시간이 60분을 초과합니다")
            
            # 신뢰도 검증
            if not (0.0 <= config.critical_confidence <= 1.0):
                issues.append("critical_confidence가 0-1 범위를 벗어남")
            
            if not (0.0 <= config.high_confidence <= 1.0):
                issues.append("high_confidence가 0-1 범위를 벗어남")
            
            if not (0.0 <= config.medium_confidence <= 1.0):
                issues.append("medium_confidence가 0-1 범위를 벗어남")
            
            # 신뢰도 순서 검증
            if config.critical_confidence < config.high_confidence:
                warnings.append("critical_confidence가 high_confidence보다 낮음")
            
            if config.high_confidence < config.medium_confidence:
                warnings.append("high_confidence가 medium_confidence보다 낮음")
            
        except Exception as e:
            issues.append(f"설정 검증 중 오류: {e}")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings
        }


# 글로벌 로더 인스턴스
_global_loader = None


def get_rule_loader() -> RuleLoader:
    """글로벌 로더 인스턴스 반환"""
    global _global_loader
    if _global_loader is None:
        _global_loader = RuleLoader()
    return _global_loader


def load_rule_config(config_path: Optional[Path] = None) -> RuleConfig:
    """규칙 설정 로드 헬퍼"""
    if config_path:
        loader = RuleLoader(config_path)
    else:
        loader = get_rule_loader()
    
    return loader.load_config()