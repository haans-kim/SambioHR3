"""
Knox와 Equipment 데이터를 daily_logs와 통합하는 프로세서
"""

import pandas as pd
import logging
from datetime import datetime, timedelta
import numpy as np
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class IntegratedDataProcessor:
    """Knox와 Equipment 데이터를 통합 처리하는 클래스"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
    
    def process_and_integrate_knox_data(self, approval_df=None, pims_df=None, mail_df=None):
        """Knox 데이터를 처리하고 데이터베이스에 저장 및 daily_logs와 통합"""
        
        all_logs = []
        
        # 1. Knox Approval 데이터 처리 (O태그)
        if approval_df is not None and not approval_df.empty:
            self.logger.info(f"Knox Approval 데이터 처리 중: {len(approval_df)}개 레코드")
            
            # 데이터베이스에 저장
            self._save_knox_approval_to_db(approval_df)
            
            # daily_logs 형식으로 변환
            for _, row in approval_df.iterrows():
                if pd.notna(row.get('timestamp')) and pd.notna(row.get('employee_id')):
                    log_entry = {
                        'employee_id': str(row['employee_id']),
                        'timestamp': pd.to_datetime(row['timestamp']),
                        'tag_code': 'O',  # 결재 작업
                        'tag_name': '결재 업무',
                        'location': 'Knox Approval System',
                        'direction': 'WORK',
                        'source': 'knox_approval',
                        'confidence': 1.0,
                        'work_detail': row.get('work_detail', '결재 처리'),
                        'system_type': 'Knox_Approval'
                    }
                    all_logs.append(log_entry)
        
        # 2. Knox PIMS 데이터 처리 (G3태그)
        if pims_df is not None and not pims_df.empty:
            self.logger.info(f"Knox PIMS 데이터 처리 중: {len(pims_df)}개 레코드")
            
            # 데이터베이스에 저장
            self._save_knox_pims_to_db(pims_df)
            
            # daily_logs 형식으로 변환
            for _, row in pims_df.iterrows():
                if pd.notna(row.get('timestamp')) and pd.notna(row.get('employee_id')):
                    # 회의 시작 로그
                    start_log = {
                        'employee_id': str(row['employee_id']),
                        'timestamp': pd.to_datetime(row['timestamp']),
                        'tag_code': 'G3',  # 회의
                        'tag_name': '회의',
                        'location': row.get('meeting_room', 'Knox PIMS'),
                        'direction': 'MEETING_START',
                        'source': 'knox_pims',
                        'confidence': 1.0,
                        'meeting_id': row.get('meeting_id', ''),
                        'duration_minutes': row.get('duration_minutes', 0),
                        'attendee_count': row.get('attendee_count', 1),
                        'system_type': 'Knox_PIMS'
                    }
                    all_logs.append(start_log)
                    
                    # 회의 종료 로그 (duration이 있는 경우)
                    if 'end_time' in row and pd.notna(row['end_time']):
                        end_log = start_log.copy()
                        end_log['timestamp'] = pd.to_datetime(row['end_time'])
                        end_log['direction'] = 'MEETING_END'
                        all_logs.append(end_log)
        
        # 3. Knox Mail 데이터 처리 (O태그)
        if mail_df is not None and not mail_df.empty:
            self.logger.info(f"Knox Mail 데이터 처리 중: {len(mail_df)}개 레코드")
            
            # 데이터베이스에 저장
            self._save_knox_mail_to_db(mail_df)
            
            # daily_logs 형식으로 변환
            for _, row in mail_df.iterrows():
                if pd.notna(row.get('timestamp')) and pd.notna(row.get('employee_id')):
                    log_entry = {
                        'employee_id': str(row['employee_id']),
                        'timestamp': pd.to_datetime(row['timestamp']),
                        'tag_code': 'O',  # 메일 작업
                        'tag_name': '메일 업무',
                        'location': 'Knox Mail System',
                        'direction': 'WORK',
                        'source': 'knox_mail',
                        'confidence': row.get('work_confidence', 0.8),
                        'work_detail': row.get('work_detail', '메일 발송'),
                        'system_type': 'Knox_Mail'
                    }
                    all_logs.append(log_entry)
        
        # daily_logs 테이블에 통합
        if all_logs:
            self._integrate_with_daily_logs(all_logs)
            self.logger.info(f"총 {len(all_logs)}개의 Knox 로그를 daily_logs에 통합")
        
        return all_logs
    
    def process_and_integrate_equipment_data(self, eam_df=None, lams_df=None, mes_df=None):
        """Equipment 데이터를 처리하고 데이터베이스에 저장 및 daily_logs와 통합"""
        
        all_logs = []
        
        # 1. EAM 데이터 처리 (O태그)
        if eam_df is not None and not eam_df.empty:
            self.logger.info(f"EAM 데이터 처리 중: {len(eam_df)}개 레코드")
            
            # 데이터베이스에 저장
            self._save_equipment_to_db(eam_df, 'EAM')
            
            # daily_logs 형식으로 변환
            for _, row in eam_df.iterrows():
                if pd.notna(row.get('timestamp')) and pd.notna(row.get('employee_id')):
                    log_entry = {
                        'employee_id': str(row['employee_id']),
                        'timestamp': pd.to_datetime(row['timestamp']),
                        'tag_code': 'O',  # 장비 작업
                        'tag_name': '안전설비 작업',
                        'location': 'EAM System',
                        'direction': 'WORK',
                        'source': 'equipment_eam',
                        'confidence': 1.0,
                        'work_detail': '안전설비시스템 사용',
                        'system_type': 'EAM'
                    }
                    all_logs.append(log_entry)
        
        # 2. LAMS 데이터 처리 (O태그)
        if lams_df is not None and not lams_df.empty:
            self.logger.info(f"LAMS 데이터 처리 중: {len(lams_df)}개 레코드")
            
            # 데이터베이스에 저장
            self._save_equipment_to_db(lams_df, 'LAMS')
            
            # daily_logs 형식으로 변환
            for _, row in lams_df.iterrows():
                if pd.notna(row.get('timestamp')) and pd.notna(row.get('employee_id')):
                    log_entry = {
                        'employee_id': str(row['employee_id']),
                        'timestamp': pd.to_datetime(row['timestamp']),
                        'tag_code': 'O',  # 장비 작업
                        'tag_name': '품질시스템 작업',
                        'location': 'LAMS System',
                        'direction': 'WORK',
                        'source': 'equipment_lams',
                        'confidence': 1.0,
                        'work_detail': row.get('work_detail', '품질시스템 사용'),
                        'system_type': 'LAMS'
                    }
                    all_logs.append(log_entry)
        
        # 3. MES 데이터 처리 (O태그)
        if mes_df is not None and not mes_df.empty:
            self.logger.info(f"MES 데이터 처리 중: {len(mes_df)}개 레코드")
            
            # 데이터베이스에 저장
            self._save_equipment_to_db(mes_df, 'MES')
            
            # daily_logs 형식으로 변환
            for _, row in mes_df.iterrows():
                if pd.notna(row.get('timestamp')) and pd.notna(row.get('employee_id')):
                    log_entry = {
                        'employee_id': str(row['employee_id']),
                        'timestamp': pd.to_datetime(row['timestamp']),
                        'tag_code': 'O',  # 장비 작업
                        'tag_name': '생산시스템 작업',
                        'location': 'MES System',
                        'direction': 'WORK',
                        'source': 'equipment_mes',
                        'confidence': 1.0,
                        'work_detail': '생산시스템 사용',
                        'system_type': 'MES'
                    }
                    all_logs.append(log_entry)
        
        # daily_logs 테이블에 통합
        if all_logs:
            self._integrate_with_daily_logs(all_logs)
            self.logger.info(f"총 {len(all_logs)}개의 Equipment 로그를 daily_logs에 통합")
        
        return all_logs
    
    def _save_knox_approval_to_db(self, df):
        """Knox Approval 데이터를 데이터베이스에 저장"""
        try:
            # 컬럼 매핑
            df_to_save = pd.DataFrame({
                'timestamp': pd.to_datetime(df.get('timestamp', df.get('Timestamp'))),
                'employee_id': df.get('employee_id', df.get('UserNo', df.get('사번'))).astype(str),
                'task': df.get('approval_status', df.get('Task', df.get('결재상태'))),
                'apid': df.get('apid', df.get('APID')),
                'remark': df.get('remark', df.get('비고'))
            })
            
            # 데이터베이스에 저장
            df_to_save.to_sql('knox_approval_data', self.db_manager.engine, 
                            if_exists='append', index=False)
            self.logger.info(f"Knox Approval 데이터 {len(df_to_save)}개 저장 완료")
        except Exception as e:
            self.logger.error(f"Knox Approval 데이터 저장 실패: {e}")
    
    def _save_knox_pims_to_db(self, df):
        """Knox PIMS 데이터를 데이터베이스에 저장"""
        try:
            # 컬럼 매핑
            df_to_save = pd.DataFrame({
                'employee_id': df.get('employee_id', df.get('사번')).astype(str),
                'meeting_id': df.get('meeting_id', df.get('일정ID')),
                'meeting_type': df.get('meeting_type', df.get('일정_구분')),
                'start_time': pd.to_datetime(df.get('start_time', df.get('시작일시_GMT+9'))),
                'end_time': pd.to_datetime(df.get('end_time', df.get('종료일시_GMT+9')))
            })
            
            # 데이터베이스에 저장
            df_to_save.to_sql('knox_pims_data', self.db_manager.engine, 
                            if_exists='append', index=False)
            self.logger.info(f"Knox PIMS 데이터 {len(df_to_save)}개 저장 완료")
        except Exception as e:
            self.logger.error(f"Knox PIMS 데이터 저장 실패: {e}")
    
    def _save_knox_mail_to_db(self, df):
        """Knox Mail 데이터를 데이터베이스에 저장"""
        try:
            # 컬럼 매핑
            df_to_save = pd.DataFrame({
                'mail_key': df.get('mail_key', df.get('메일key')),
                'send_time': pd.to_datetime(df.get('timestamp', df.get('발신일시_GMT9'))),
                'sender_id': df.get('employee_id', df.get('발신인사번_text')).astype(str)
            })
            
            # 데이터베이스에 저장
            df_to_save.to_sql('knox_mail_data', self.db_manager.engine, 
                            if_exists='append', index=False)
            self.logger.info(f"Knox Mail 데이터 {len(df_to_save)}개 저장 완료")
        except Exception as e:
            self.logger.error(f"Knox Mail 데이터 저장 실패: {e}")
    
    def _save_equipment_to_db(self, df, system_type):
        """Equipment 데이터를 데이터베이스에 저장"""
        try:
            # 컬럼 매핑
            df_to_save = pd.DataFrame({
                'system_type': system_type,
                'timestamp': pd.to_datetime(df['timestamp']),
                'employee_id': df['employee_id'].astype(str),
                'action_type': df.get('action_type', ''),
                'application': df.get('application', '')
            })
            
            # 데이터베이스에 저장
            df_to_save.to_sql('equipment_data', self.db_manager.engine, 
                            if_exists='append', index=False)
            self.logger.info(f"{system_type} 데이터 {len(df_to_save)}개 저장 완료")
        except Exception as e:
            self.logger.error(f"{system_type} 데이터 저장 실패: {e}")
    
    def _integrate_with_daily_logs(self, logs):
        """로그를 tag_logs 테이블에 통합"""
        try:
            # DataFrame으로 변환
            logs_df = pd.DataFrame(logs)
            
            # tag_logs 테이블에 맞게 컬럼 조정
            tag_logs_df = pd.DataFrame()
            tag_logs_df['employee_id'] = logs_df['employee_id']
            tag_logs_df['timestamp'] = pd.to_datetime(logs_df['timestamp'])
            tag_logs_df['date'] = tag_logs_df['timestamp'].dt.date
            tag_logs_df['hour'] = tag_logs_df['timestamp'].dt.hour
            tag_logs_df['tag_code'] = logs_df.get('tag_code', 'O')
            tag_logs_df['tag_name'] = logs_df.get('tag_name', '')
            tag_logs_df['location'] = logs_df.get('location', '')
            tag_logs_df['direction'] = logs_df.get('direction', 'IN')
            tag_logs_df['shift_type'] = tag_logs_df['hour'].apply(
                lambda h: 'DAY' if 8 <= h < 20 else 'NIGHT'
            )
            tag_logs_df['confidence'] = logs_df.get('confidence', 1.0)
            
            # tag_logs 테이블에 저장
            tag_logs_df.to_sql('tag_logs', self.db_manager.engine, 
                         if_exists='append', index=False)
            self.logger.info(f"tag_logs에 {len(tag_logs_df)}개 로그 통합 완료")
            
        except Exception as e:
            self.logger.error(f"tag_logs 통합 실패: {e}")
    
    def get_integrated_daily_logs(self, employee_id: str, start_date: datetime, end_date: datetime):
        """통합된 tag_logs 데이터 조회"""
        query = """
        SELECT 
            employee_id,
            timestamp,
            tag_code,
            tag_name,
            location,
            direction,
            confidence,
            date,
            hour,
            shift_type
        FROM tag_logs
        WHERE employee_id = :employee_id
            AND date >= :start_date
            AND date <= :end_date
        ORDER BY timestamp
        """
        
        df = pd.read_sql(query, self.db_manager.engine, params={
            'employee_id': employee_id,
            'start_date': start_date,
            'end_date': end_date
        })
        
        return df