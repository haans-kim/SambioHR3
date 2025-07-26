"""
장비 사용 데이터 처리 함수들
"""

import pandas as pd
import logging
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)

def process_eam_data(df):
    """EAM(안전설비시스템) 데이터 처리"""
    logger.info(f"EAM 데이터 처리 시작: {len(df)}개 레코드")
    
    # 컬럼명 정리
    df = df.rename(columns={
        'ATTEMPTDATE': 'timestamp',
        'USERNO': 'employee_id',
        'ATTEMPTRESULT': 'action_type',
        'APP': 'application'
    })
    
    # 타임스탬프 변환
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # 사번 문자열로 변환
    df['employee_id'] = df['employee_id'].astype(str)
    
    # 시스템 타입 추가
    df['system_type'] = 'EAM'
    df['equipment_type'] = '안전설비시스템'
    
    # LOGIN과 SUCCESS만 필터링 (실제 사용 로그)
    df = df[df['action_type'].isin(['LOGIN', 'SUCCESS'])].copy()
    
    # O 태그 관련 정보 추가
    df['is_work_log'] = True
    df['work_confidence'] = 1.0
    
    # 날짜 및 시간 정보 추가
    df['date'] = df['timestamp'].dt.date
    df['hour'] = df['timestamp'].dt.hour
    df['weekday'] = df['timestamp'].dt.day_name()
    
    logger.info(f"EAM 데이터 처리 완료: {len(df)}개 레코드")
    return df

def process_lams_data(df):
    """LAMS(품질시스템) 데이터 처리"""
    logger.info(f"LAMS 데이터 처리 시작: {len(df)}개 레코드")
    
    # 컬럼명 정리
    df = df.rename(columns={
        'User_No': 'employee_id',
        'DATE': 'timestamp',
        'Task': 'action_type'
    })
    
    # 타임스탬프 변환
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # 사번 문자열로 변환
    df['employee_id'] = df['employee_id'].astype(str)
    
    # 시스템 타입 추가
    df['system_type'] = 'LAMS'
    df['equipment_type'] = '품질시스템'
    
    # O 태그 관련 정보 추가
    df['is_work_log'] = True
    df['work_confidence'] = 1.0
    
    # create/modify 작업 구분
    df['work_detail'] = df['action_type'].map({
        'create': '스케쥴 작성',
        'modify': '스케쥴 수정'
    })
    
    # 날짜 및 시간 정보 추가
    df['date'] = df['timestamp'].dt.date
    df['hour'] = df['timestamp'].dt.hour
    df['weekday'] = df['timestamp'].dt.day_name()
    
    logger.info(f"LAMS 데이터 처리 완료: {len(df)}개 레코드")
    return df

def process_mes_data(df):
    """MES(생산시스템) 데이터 처리"""
    logger.info(f"MES 데이터 처리 시작: {len(df)}개 레코드")
    
    # 컬럼명 정리
    df = df.rename(columns={
        'login_time': 'timestamp',
        'USERNo': 'employee_id',
        'session': 'application'
    })
    
    # 타임스탬프 변환
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # 사번 문자열로 변환
    df['employee_id'] = df['employee_id'].astype(str)
    
    # 시스템 타입 추가
    df['system_type'] = 'MES'
    df['equipment_type'] = '생산시스템'
    df['action_type'] = 'LOGIN'
    
    # O 태그 관련 정보 추가
    df['is_work_log'] = True
    df['work_confidence'] = 1.0
    
    # 날짜 및 시간 정보 추가
    df['date'] = df['timestamp'].dt.date
    df['hour'] = df['timestamp'].dt.hour
    df['weekday'] = df['timestamp'].dt.day_name()
    
    logger.info(f"MES 데이터 처리 완료: {len(df)}개 레코드")
    return df

def merge_equipment_data(eam_df=None, lams_df=None, mes_df=None):
    """모든 장비 사용 데이터 통합"""
    dfs = []
    
    if eam_df is not None:
        dfs.append(eam_df)
    if lams_df is not None:
        dfs.append(lams_df)
    if mes_df is not None:
        dfs.append(mes_df)
    
    if not dfs:
        logger.warning("통합할 장비 데이터가 없습니다.")
        return pd.DataFrame()
    
    # 데이터 통합
    merged_df = pd.concat(dfs, ignore_index=True)
    
    # 타임스탬프로 정렬
    merged_df = merged_df.sort_values('timestamp')
    
    # 인덱스 재설정
    merged_df = merged_df.reset_index(drop=True)
    
    logger.info(f"장비 데이터 통합 완료: 총 {len(merged_df)}개 레코드")
    
    # 시스템별 통계
    system_stats = merged_df.groupby('system_type').size()
    logger.info("시스템별 로그 수:")
    for system, count in system_stats.items():
        logger.info(f"  {system}: {count:,}개")
    
    return merged_df

def create_o_tags_from_equipment(equipment_df):
    """장비 사용 데이터에서 O 태그 생성"""
    o_tags = []
    
    # 사원별, 날짜별로 그룹화
    grouped = equipment_df.groupby(['employee_id', 'date'])
    
    for (employee_id, date), group in grouped:
        # 시간순 정렬
        group = group.sort_values('timestamp')
        
        # 연속된 작업 세션 감지
        sessions = []
        current_session = None
        
        for _, row in group.iterrows():
            if current_session is None:
                # 새 세션 시작
                current_session = {
                    'employee_id': employee_id,
                    'start_time': row['timestamp'],
                    'end_time': row['timestamp'],
                    'system_types': [row['system_type']],
                    'action_count': 1
                }
            else:
                # 이전 작업과의 시간 차이
                time_diff = (row['timestamp'] - current_session['end_time']).total_seconds() / 60
                
                if time_diff <= 30:  # 30분 이내면 같은 세션
                    current_session['end_time'] = row['timestamp']
                    if row['system_type'] not in current_session['system_types']:
                        current_session['system_types'].append(row['system_type'])
                    current_session['action_count'] += 1
                else:
                    # 세션 종료 및 새 세션 시작
                    sessions.append(current_session)
                    current_session = {
                        'employee_id': employee_id,
                        'start_time': row['timestamp'],
                        'end_time': row['timestamp'],
                        'system_types': [row['system_type']],
                        'action_count': 1
                    }
        
        # 마지막 세션 추가
        if current_session:
            sessions.append(current_session)
        
        # 세션을 O 태그로 변환
        for session in sessions:
            duration = (session['end_time'] - session['start_time']).total_seconds() / 60
            
            # 최소 5분 이상의 세션만 O 태그로 생성
            if duration >= 5 or session['action_count'] >= 3:
                o_tag = {
                    'employee_id': session['employee_id'],
                    'timestamp': session['start_time'],
                    'tag_code': 'O',
                    'source': 'equipment_data',
                    'equipment_types': session['system_types'],
                    'duration_minutes': max(duration, 5),  # 최소 5분
                    'action_count': session['action_count'],
                    'confidence': 1.0
                }
                o_tags.append(o_tag)
    
    logger.info(f"생성된 O 태그 수: {len(o_tags)}개")
    return o_tags