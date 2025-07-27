"""
확정적 규칙 엔진 사용 예제
"""

from datetime import datetime, timedelta
import sys
from pathlib import Path

# 프로젝트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.tag_system.rule_integration import get_rule_integration, apply_rules_to_tags
from src.tag_system.confidence_state import ActivityState
from src.utils.time_normalizer import ShiftType


def example_day_shift():
    """주간 근무자 예제"""
    print("\n=== 주간 근무자 하루 일과 ===")
    
    # 태그 시퀀스 (주간 근무자)
    base_date = datetime(2025, 7, 27, 0, 0)
    tags = [
        {'tag': 'T2', 'timestamp': base_date.replace(hour=7, minute=50)},      # 출근
        {'tag': 'G2', 'timestamp': base_date.replace(hour=7, minute=55)},      # 준비
        {'tag': 'G1', 'timestamp': base_date.replace(hour=8, minute=5)},       # 업무 공간
        {'tag': 'O', 'timestamp': base_date.replace(hour=8, minute=10)},       # 실제 업무
        {'tag': 'G1', 'timestamp': base_date.replace(hour=10, minute=30)},     # 업무 지속
        {'tag': 'M1', 'timestamp': base_date.replace(hour=12, minute=0)},      # 점심 식사
        {'tag': 'G1', 'timestamp': base_date.replace(hour=12, minute=45)},     # 업무 복귀
        {'tag': 'O', 'timestamp': base_date.replace(hour=13, minute=0)},       # 업무
        {'tag': 'N1', 'timestamp': base_date.replace(hour=15, minute=0)},      # 휴게
        {'tag': 'G1', 'timestamp': base_date.replace(hour=15, minute=15)},     # 업무 복귀
        {'tag': 'G3', 'timestamp': base_date.replace(hour=16, minute=0)},      # 회의
        {'tag': 'G1', 'timestamp': base_date.replace(hour=17, minute=0)},      # 업무
        {'tag': 'M1', 'timestamp': base_date.replace(hour=18, minute=0)},      # 저녁 식사
        {'tag': 'G1', 'timestamp': base_date.replace(hour=18, minute=40)},     # 업무
        {'tag': 'G3', 'timestamp': base_date.replace(hour=20, minute=0)},      # 인수인계
        {'tag': 'G2', 'timestamp': base_date.replace(hour=20, minute=20)},     # 정리
        {'tag': 'T3', 'timestamp': base_date.replace(hour=20, minute=25)},     # 퇴근
    ]
    
    # 직원 정보
    employee_info = {
        'employee_id': 'EMP001',
        'name': '홍길동',
        'shift_type': 'day'
    }
    
    # 규칙 적용
    states = apply_rules_to_tags(tags, employee_info)
    
    # 결과 출력
    for i, (tag_info, state) in enumerate(zip(tags, states)):
        time_str = tag_info['timestamp'].strftime('%H:%M')
        tag = tag_info['tag']
        
        if state:
            state_str = state.state.value
            confidence = state.confidence
            evidence = state.evidence[0].description if state.evidence else ""
            
            print(f"{time_str} | {tag:^4} → {state_str:^12} (신뢰도: {confidence:.2f}) | {evidence}")
        else:
            print(f"{time_str} | {tag:^4} → {'미확정':^12} | 확정적 규칙 없음")
    
    # 통계
    print("\n=== 분류 통계 ===")
    total = len(states)
    confirmed = sum(1 for s in states if s and s.confidence >= 0.95)
    uncertain = sum(1 for s in states if s is None)
    
    print(f"전체 태그: {total}개")
    print(f"확정 상태: {confirmed}개 ({confirmed/total*100:.1f}%)")
    print(f"미확정: {uncertain}개 ({uncertain/total*100:.1f}%)")


def example_night_shift():
    """야간 근무자 예제"""
    print("\n=== 야간 근무자 식사 시간 ===")
    
    # 야간 근무자 식사 패턴
    base_date = datetime(2025, 7, 27, 0, 0)
    tags = [
        {'tag': 'G1', 'timestamp': base_date.replace(hour=22, minute=30)},
        {'tag': 'M1', 'timestamp': base_date.replace(hour=23, minute=40)},     # 야식
        {'tag': 'G1', 'timestamp': base_date + timedelta(days=1, minutes=20)}, # 다음날 00:20 (40분 식사)
        {'tag': 'O', 'timestamp': base_date.replace(hour=0, minute=30)},
        {'tag': 'G1', 'timestamp': base_date.replace(hour=5, minute=0)},
        {'tag': 'M1', 'timestamp': base_date.replace(hour=6, minute=40)},      # 조식
        {'tag': 'G1', 'timestamp': base_date.replace(hour=8, minute=0)},       # 80분 → 60분으로 제한
    ]
    
    # 규칙 통합 인스턴스
    integration = get_rule_integration()
    
    # 태그별 처리
    print("시간    | 태그 | 상태        | 식사 시간 | 설명")
    print("-" * 60)
    
    for i in range(len(tags)):
        tag_info = tags[i]
        
        # 다음 태그까지 시간
        to_next = None
        if i < len(tags) - 1:
            diff = tags[i+1]['timestamp'] - tag_info['timestamp']
            to_next = diff.total_seconds() / 60
        
        # 식사 시간 계산
        meal_duration = integration.get_meal_duration(tag_info['tag'], to_next)
        
        # 규칙 적용
        tag_data = {
            'tag': tag_info['tag'],
            'timestamp': tag_info['timestamp'],
            'to_next_minutes': to_next,
            'shift_type': ShiftType.NIGHT
        }
        
        state = integration.rule_engine.apply_rules(tag_data)
        
        time_str = tag_info['timestamp'].strftime('%H:%M')
        tag = tag_info['tag']
        
        if state and state.state == ActivityState.MEAL:
            evidence = state.evidence[0]
            actual_duration = evidence.metadata.get('duration_minutes', 0)
            capped = evidence.metadata.get('capped', False)
            
            cap_str = " (제한됨)" if capped else ""
            print(f"{time_str} | {tag:^4} | {state.state.value:^10} | {actual_duration:>4.0f}분{cap_str:^8} | {evidence.description}")
        elif tag in ['M1', 'M2']:
            print(f"{time_str} | {tag:^4} | {'식사':^10} | {meal_duration:>4.0f}분      | 규칙 적용")
        else:
            state_str = state.state.value if state else "미확정"
            print(f"{time_str} | {tag:^4} | {state_str:^10} | -          |")


def example_takeout():
    """테이크아웃 예제"""
    print("\n=== 테이크아웃 패턴 ===")
    
    base_date = datetime(2025, 7, 27, 12, 0)
    tags = [
        {'tag': 'G1', 'timestamp': base_date},
        {'tag': 'T1', 'timestamp': base_date + timedelta(minutes=5)},
        {'tag': 'M2', 'timestamp': base_date + timedelta(minutes=10)},      # 테이크아웃
        {'tag': 'T1', 'timestamp': base_date + timedelta(minutes=12)},      # 2분 후 이동
        {'tag': 'N2', 'timestamp': base_date + timedelta(minutes=15)},      # 휴게실
        {'tag': 'T1', 'timestamp': base_date + timedelta(minutes=45)},      # 30분 후
        {'tag': 'G1', 'timestamp': base_date + timedelta(minutes=48)},
    ]
    
    states = apply_rules_to_tags(tags)
    
    print("시간  | 태그 | 상태     | 설명")
    print("-" * 50)
    
    for tag_info, state in zip(tags, states):
        time_str = tag_info['timestamp'].strftime('%H:%M')
        tag = tag_info['tag']
        
        if state:
            state_str = state.state.value
            desc = state.evidence[0].description if state.evidence else ""
            print(f"{time_str} | {tag:^4} | {state_str:^8} | {desc}")
        else:
            print(f"{time_str} | {tag:^4} | {'?':^8} | 규칙 없음")


def example_config_update():
    """설정 업데이트 예제"""
    print("\n=== 설정 업데이트 예제 ===")
    
    integration = get_rule_integration()
    
    # 현재 설정
    print(f"현재 M1 최대 시간: {integration.rule_engine.config.meal_max_duration_minutes}분")
    print(f"현재 M2 고정 시간: {integration.rule_engine.config.takeout_fixed_duration_minutes}분")
    
    # 설정 변경 (법적 검토 후)
    print("\n설정 변경 중...")
    success = integration.update_config(
        meal_max_duration_minutes=50,
        takeout_fixed_duration_minutes=25
    )
    
    if success:
        print("설정 변경 완료!")
        print(f"새 M1 최대 시간: {integration.rule_engine.config.meal_max_duration_minutes}분")
        print(f"새 M2 고정 시간: {integration.rule_engine.config.takeout_fixed_duration_minutes}분")
    else:
        print("설정 변경 실패!")


if __name__ == "__main__":
    # 예제 실행
    example_day_shift()
    example_night_shift()
    example_takeout()
    example_config_update()
    
    # 검증
    print("\n=== 시퀀스 검증 예제 ===")
    
    # 문제가 있는 시퀀스
    problem_tags = [
        {'tag': 'T2', 'timestamp': datetime(2025, 7, 27, 8, 0)},
        {'tag': 'T3', 'timestamp': datetime(2025, 7, 27, 8, 5)},  # 출근 직후 퇴근?
    ]
    
    integration = get_rule_integration()
    states = apply_rules_to_tags(problem_tags)
    
    validation = integration.validate_sequence(states)
    print(f"검증 결과: {'통과' if validation['valid'] else '실패'}")
    if validation['issues']:
        print("문제점:")
        for issue in validation['issues']:
            print(f"  - {issue}")