"""
태그 시스템을 활용한 개인별 업무 분석
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import pickle
import gzip
from datetime import datetime, timedelta
import logging
from sqlalchemy import create_engine
from src.tag_system.tag_system_adapter import TagSystemAdapter
from src.tag_system.meal_tag_processor import MealTagProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_url():
    """데이터베이스 URL 반환"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'sambio_human.db')
    return f'sqlite:///{db_path}'

def load_o_tags():
    """O 태그 데이터 로드"""
    o_tag_file = 'data/pickles/o_tags_equipment_v20250726_120702.pkl.gz'
    logger.info(f"O 태그 데이터 로드 중: {o_tag_file}")
    
    with gzip.open(o_tag_file, 'rb') as f:
        o_tags_df = pickle.load(f)
    
    logger.info(f"O 태그 {len(o_tags_df):,}개 로드 완료")
    return o_tags_df

def get_available_employees(o_tags_df):
    """분석 가능한 직원 목록"""
    # O 태그가 많은 순으로 상위 20명
    employee_counts = o_tags_df['employee_id'].value_counts().head(20)
    
    print("\n=== 분석 가능한 직원 목록 (O 태그 많은 순) ===")
    for i, (emp_id, count) in enumerate(employee_counts.items(), 1):
        print(f"{i:2}. 사번: {emp_id} (O 태그: {count}개)")
    
    return employee_counts.index.tolist()

def analyze_employee_day(employee_id, date, o_tags_df):
    """특정 직원의 하루 분석"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'sambio_human.db')
    engine = create_engine(f'sqlite:///{db_path}')
    
    # 태그 시스템 어댑터 생성
    adapter = TagSystemAdapter(db_path)
    meal_processor = MealTagProcessor(engine)
    
    print(f"\n=== {employee_id} 직원의 {date} 업무 분석 ===")
    
    # 1. 태그 데이터 처리
    result = adapter.process_tag_data(employee_id, date)
    
    # 2. O 태그 추가
    employee_o_tags = o_tags_df[
        (o_tags_df['employee_id'] == employee_id) & 
        (pd.to_datetime(o_tags_df['timestamp']).dt.date == date.date())
    ]
    
    if len(employee_o_tags) > 0:
        print(f"\n장비 사용 O 태그: {len(employee_o_tags)}개")
        for _, o_tag in employee_o_tags.iterrows():
            print(f"  - {o_tag['timestamp'].strftime('%H:%M')} : {', '.join(o_tag['equipment_types'])} "
                  f"({o_tag['duration_minutes']:.0f}분, {o_tag['action_count']}회)")
    
    # 3. 식사 태그 처리
    meal_tags = meal_processor.extract_meal_tags(employee_id, date)
    if meal_tags:
        print(f"\n식사 태그: {len(meal_tags)}개")
        for tag in meal_tags:
            meal_type = "테이크아웃" if tag['tag_code'] == 'M2' else "식사"
            print(f"  - {tag['timestamp'].strftime('%H:%M')} : {meal_type} @ {tag['meal_info']['배식구']}")
    
    # 4. 상태 시퀀스 출력
    if result['states']:
        print(f"\n시간대별 활동 상태:")
        print("시간  | 태그 | 상태         | 신뢰도 | 비고")
        print("-" * 50)
        
        for i, state in enumerate(result['states'][:30]):  # 처음 30개만
            time_str = state['timestamp'].strftime('%H:%M') if 'timestamp' in state else '--:--'
            tag = state.get('tag_code', '--')
            status = state.get('state', '알수없음')
            confidence = state.get('confidence', 0)
            anomaly = state.get('anomaly', '')
            
            # O 태그 여부 표시
            if state.get('has_o_tag') or tag == 'O':
                anomaly = '★ 업무확정'
            
            print(f"{time_str} | {tag:4} | {status:12} | {confidence:.2f} | {anomaly}")
    
    # 5. 업무 시간 통계
    print(f"\n=== 업무 시간 통계 ===")
    print(f"총 근무시간: {result.get('total_work_minutes', 0):.0f}분 "
          f"({result.get('total_work_minutes', 0)/60:.1f}시간)")
    print(f"확정 업무시간: {result.get('work_time_minutes', 0):.0f}분 "
          f"({result.get('work_time_minutes', 0)/60:.1f}시간)")
    print(f"업무 신뢰도: {result.get('work_confidence', 0):.1%}")
    
    # 6. 상태별 시간 분포
    if 'state_statistics' in result and 'durations' in result['state_statistics']:
        print(f"\n상태별 시간 분포:")
        durations = result['state_statistics']['durations']
        total_duration = sum(durations.values())
        
        for state, duration in sorted(durations.items(), key=lambda x: x[1], reverse=True):
            if duration > 0:
                percentage = (duration / total_duration * 100) if total_duration > 0 else 0
                print(f"  {state:12} : {duration:6.0f}분 ({percentage:5.1f}%)")
    
    # 7. 이상 패턴
    if result.get('anomalies'):
        print(f"\n이상 패턴 감지: {len(result['anomalies'])}건")
        for anomaly in result['anomalies']:
            print(f"  - {anomaly['timestamp'].strftime('%H:%M')} : "
                  f"{anomaly['type']} (신뢰도: {anomaly['confidence']:.1%})")

def main():
    # O 태그 데이터 로드
    o_tags_df = load_o_tags()
    
    # 분석 가능한 직원 목록
    available_employees = get_available_employees(o_tags_df)
    
    # 사용자 입력
    print("\n분석할 직원의 사번을 입력하세요 (또는 위 목록의 번호):")
    user_input = input("> ").strip()
    
    if user_input.isdigit() and 1 <= int(user_input) <= len(available_employees):
        employee_id = available_employees[int(user_input) - 1]
    else:
        employee_id = user_input
    
    # 날짜 입력
    print("\n분석할 날짜를 입력하세요 (YYYY-MM-DD, 기본값: 2025-06-10):")
    date_input = input("> ").strip()
    
    if date_input:
        try:
            analysis_date = datetime.strptime(date_input, '%Y-%m-%d')
        except:
            print("잘못된 날짜 형식입니다. 기본값을 사용합니다.")
            analysis_date = datetime(2025, 6, 10)
    else:
        analysis_date = datetime(2025, 6, 10)
    
    # 분석 실행
    analyze_employee_day(employee_id, analysis_date, o_tags_df)
    
    # 추가 분석 여부
    print("\n다른 직원을 분석하시겠습니까? (y/n)")
    if input("> ").strip().lower() == 'y':
        main()

if __name__ == "__main__":
    main()