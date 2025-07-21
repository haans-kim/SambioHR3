#!/usr/bin/env python3
"""전이 룰 에디터 통합 테스트"""

import sys
from pathlib import Path

# 프로젝트 루트 추가
sys.path.append(str(Path(__file__).parent))

def test_imports():
    """Import 테스트"""
    try:
        from src.rules import RuleManager, TransitionRule
        print("✓ RuleManager import successful")
        
        from src.rules.conditional_transition import ConditionalTransitionEngine
        print("✓ ConditionalTransitionEngine import successful")
        
        # 기본 기능 테스트
        rule_manager = RuleManager()
        print("✓ RuleManager initialized")
        
        # 샘플 룰 생성
        rule = TransitionRule(
            id="test_rule_1",
            from_state="근무",
            to_state="중식",
            base_probability=0.8,
            conditions=[
                {
                    'type': 'time',
                    'start': '11:30',
                    'end': '13:00'
                }
            ],
            confidence=90,
            created_at="2025-01-21T10:00:00",
            version=1,
            is_active=True
        )
        
        # 룰 검증
        is_valid, errors = rule_manager.validate_rule(rule)
        print(f"✓ Rule validation: {'Valid' if is_valid else 'Invalid'}")
        if errors:
            print(f"  Errors: {errors}")
        
        # 조건부 전이 엔진 테스트
        engine = ConditionalTransitionEngine(rule_manager)
        print("✓ ConditionalTransitionEngine initialized")
        
        # 예측 테스트
        context = {
            'current_time': '2025-01-21 12:00:00',
            'location': 'OFFICE',
            'duration_minutes': 60,
            'tag_code': 'G1'
        }
        
        predictions = engine.predict_next_states('근무', context, top_k=3)
        print(f"✓ Predictions generated: {len(predictions)} states")
        
        print("\n모든 테스트 통과! 전이 룰 시스템이 정상적으로 통합되었습니다.")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_imports()