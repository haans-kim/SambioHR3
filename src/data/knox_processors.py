"""
Knox 시스템 데이터 처리 함수들
"""

import pandas as pd
import logging
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)

def process_knox_approval_data(df):
    """Knox 결재 시스템 데이터 처리 - O태그로 작업 활동 분류"""
    logger.info(f"Knox Approval 데이터 처리 시작: {len(df)}개 레코드")
    
    # 필수 컬럼 확인 및 매핑
    required_columns = ['상신일시', '사번', '결재상태', '문서종류']
    
    # 컬럼명 정리 (실제 컬럼명에 맞게 조정 필요)
    column_mapping = {
        '상신일시': 'timestamp',
        'Timestamp': 'timestamp',
        '사번': 'employee_id',
        'UserNo': 'employee_id',
        '결재상태': 'approval_status',
        'Task': 'approval_status',
        '문서종류': 'document_type',
        '제목': 'title',
        '승인일시': 'approval_time',
        'APID': 'apid',
        '비고': 'remark'
    }
    
    # 존재하는 컬럼만 매핑
    rename_dict = {k: v for k, v in column_mapping.items() if k in df.columns}
    df = df.rename(columns=rename_dict)
    
    # 타임스탬프 변환
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    elif 'approval_time' in df.columns:
        df['timestamp'] = pd.to_datetime(df['approval_time'])
    
    # 사번 문자열로 변환
    if 'employee_id' in df.columns:
        df['employee_id'] = df['employee_id'].astype(str)
    
    # 시스템 타입 추가
    df['system_type'] = 'Knox_Approval'
    df['equipment_type'] = '결재시스템'
    df['action_type'] = 'APPROVAL_WORK'
    
    # O 태그 관련 정보 추가 - 결재 작업은 업무 활동
    df['is_work_log'] = True
    df['work_confidence'] = 1.0
    df['tag_code'] = 'O'  # 결재 작업
    
    # 결재 상태별 작업 분류
    if 'approval_status' in df.columns:
        df['work_detail'] = df['approval_status'].map({
            '상신': '결재 상신',
            '승인': '결재 승인',
            '반려': '결재 반려',
            '검토': '결재 검토',
            '완료': '결재 완료'
        }).fillna('결재 처리')
    else:
        df['work_detail'] = '결재 업무'
    
    # 날짜 및 시간 정보 추가
    if 'timestamp' in df.columns:
        df['date'] = df['timestamp'].dt.date
        df['hour'] = df['timestamp'].dt.hour
        df['weekday'] = df['timestamp'].dt.day_name()
    
    logger.info(f"Knox Approval 데이터 처리 완료: {len(df)}개 레코드")
    return df

def process_knox_pims_data(df):
    """Knox PIMS 회의 시스템 데이터 처리 - G3 코드로 회의 활동 분류"""
    logger.info(f"Knox PIMS 데이터 처리 시작: {len(df)}개 레코드")
    
    # 컬럼명 정리 (실제 컬럼명에 맞게 조정 필요)
    column_mapping = {
        '회의ID': 'meeting_id',
        '일정ID': 'meeting_id',
        '회의일시': 'timestamp',
        '참석자사번': 'employee_id',
        '사번': 'employee_id',
        '참석자': 'attendee_name',
        '회의제목': 'meeting_title',
        '회의실': 'meeting_room',
        '시작시간': 'start_time',
        '시작일시_GMT+9': 'start_time',
        '종료시간': 'end_time',
        '종료일시_GMT+9': 'end_time',
        '일정_구분': 'meeting_type'
    }
    
    # 존재하는 컬럼만 매핑
    rename_dict = {k: v for k, v in column_mapping.items() if k in df.columns}
    df = df.rename(columns=rename_dict)
    
    # 타임스탬프 변환
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    elif 'start_time' in df.columns:
        df['timestamp'] = pd.to_datetime(df['start_time'])
    
    # 사번 문자열로 변환
    if 'employee_id' in df.columns:
        df['employee_id'] = df['employee_id'].astype(str)
    
    # 시스템 타입 추가
    df['system_type'] = 'Knox_PIMS'
    df['equipment_type'] = '회의시스템'
    df['action_type'] = 'MEETING'
    
    # G3 태그 관련 정보 추가 - 회의는 G3 활동
    df['is_work_log'] = True
    df['work_confidence'] = 1.0
    df['tag_code'] = 'G3'  # 회의
    
    # 회의 시간 계산
    if 'start_time' in df.columns and 'end_time' in df.columns:
        df['start_time'] = pd.to_datetime(df['start_time'])
        df['end_time'] = pd.to_datetime(df['end_time'])
        df['duration_minutes'] = (df['end_time'] - df['start_time']).dt.total_seconds() / 60
        df['work_detail'] = df.apply(lambda x: f"회의 ({x.get('duration_minutes', 0):.0f}분)", axis=1)
    else:
        df['work_detail'] = '회의 참석'
    
    # 날짜 및 시간 정보 추가
    if 'timestamp' in df.columns:
        df['date'] = df['timestamp'].dt.date
        df['hour'] = df['timestamp'].dt.hour
        df['weekday'] = df['timestamp'].dt.day_name()
    
    # 회의 ID별 참석자 수 계산
    if 'meeting_id' in df.columns:
        meeting_attendees = df.groupby('meeting_id')['employee_id'].nunique()
        df['attendee_count'] = df['meeting_id'].map(meeting_attendees)
    
    logger.info(f"Knox PIMS 데이터 처리 완료: {len(df)}개 레코드")
    return df

def process_knox_mail_data(df):
    """Knox 메일 시스템 데이터 처리"""
    logger.info(f"Knox Mail 데이터 처리 시작: {len(df)}개 레코드")
    
    # 컬럼명 정리 (실제 컬럼명에 맞게 조정 필요)
    column_mapping = {
        '발송일시': 'timestamp',
        '발신일시_GMT9': 'timestamp',
        '발신자사번': 'employee_id',
        '발신인사번_text': 'employee_id',
        '발신자': 'sender_name',
        '수신자': 'recipients',
        '제목': 'subject',
        '첨부파일': 'has_attachment',
        '메일key': 'mail_key'
    }
    
    # 존재하는 컬럼만 매핑
    rename_dict = {k: v for k, v in column_mapping.items() if k in df.columns}
    df = df.rename(columns=rename_dict)
    
    # 타임스탬프 변환
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # 사번 문자열로 변환
    if 'employee_id' in df.columns:
        df['employee_id'] = df['employee_id'].astype(str)
    
    # 시스템 타입 추가
    df['system_type'] = 'Knox_Mail'
    df['equipment_type'] = '메일시스템'
    df['action_type'] = 'EMAIL_WORK'
    
    # O 태그 관련 정보 추가 - 메일 작업은 일반 업무
    df['is_work_log'] = True
    df['work_confidence'] = 0.8  # 메일은 업무 확실성이 조금 낮음
    df['tag_code'] = 'O'  # 일반 작업
    
    # 메일 작업 분류
    df['work_detail'] = '메일 발송'
    
    # 수신자 수 계산
    if 'recipients' in df.columns:
        df['recipient_count'] = df['recipients'].apply(
            lambda x: len(str(x).split(';')) if pd.notna(x) else 0
        )
        
        # 대량 메일 여부
        df['is_bulk_mail'] = df['recipient_count'] > 10
    
    # 날짜 및 시간 정보 추가
    if 'timestamp' in df.columns:
        df['date'] = df['timestamp'].dt.date
        df['hour'] = df['timestamp'].dt.hour
        df['weekday'] = df['timestamp'].dt.day_name()
        
        # 업무 시간 외 메일 여부
        df['is_after_hours'] = ~df['hour'].between(8, 19)
    
    logger.info(f"Knox Mail 데이터 처리 완료: {len(df)}개 레코드")
    return df

def merge_knox_data(approval_df=None, pims_df=None, mail_df=None):
    """모든 Knox 시스템 데이터 통합"""
    dfs = []
    
    if approval_df is not None:
        dfs.append(approval_df)
    if pims_df is not None:
        dfs.append(pims_df)
    if mail_df is not None:
        dfs.append(mail_df)
    
    if not dfs:
        logger.warning("통합할 Knox 데이터가 없습니다.")
        return pd.DataFrame()
    
    # 데이터 통합
    merged_df = pd.concat(dfs, ignore_index=True)
    
    # 타임스탬프로 정렬
    merged_df = merged_df.sort_values('timestamp')
    
    # 인덱스 재설정
    merged_df = merged_df.reset_index(drop=True)
    
    logger.info(f"Knox 데이터 통합 완료: 총 {len(merged_df)}개 레코드")
    
    # 시스템별 통계
    system_stats = merged_df.groupby('system_type').size()
    logger.info("Knox 시스템별 로그 수:")
    for system, count in system_stats.items():
        logger.info(f"  {system}: {count:,}개")
    
    # 태그별 통계
    if 'tag_code' in merged_df.columns:
        tag_stats = merged_df.groupby('tag_code').size()
        logger.info("태그별 분류:")
        for tag, count in tag_stats.items():
            logger.info(f"  {tag}: {count:,}개")
    
    return merged_df

def create_tags_from_knox_data(knox_df):
    """Knox 데이터에서 태그 생성 (O태그 및 G3태그)"""
    tags = []
    
    # 이미 태그 코드가 할당된 데이터를 그대로 활용
    for _, row in knox_df.iterrows():
        tag = {
            'employee_id': row['employee_id'],
            'timestamp': row['timestamp'],
            'tag_code': row.get('tag_code', 'O'),
            'source': f"knox_{row['system_type'].lower()}",
            'equipment_type': row['equipment_type'],
            'work_detail': row.get('work_detail', ''),
            'confidence': row.get('work_confidence', 1.0)
        }
        
        # 회의 데이터인 경우 추가 정보
        if row.get('tag_code') == 'G3' and 'duration_minutes' in row:
            tag['duration_minutes'] = row['duration_minutes']
            tag['meeting_id'] = row.get('meeting_id', '')
            tag['attendee_count'] = row.get('attendee_count', 1)
        
        tags.append(tag)
    
    logger.info(f"생성된 Knox 태그 수: {len(tags)}개")
    
    # 태그 종류별 통계
    tag_df = pd.DataFrame(tags)
    tag_stats = tag_df.groupby('tag_code').size()
    logger.info("생성된 태그 통계:")
    for tag_code, count in tag_stats.items():
        logger.info(f"  {tag_code}: {count:,}개")
    
    return tags