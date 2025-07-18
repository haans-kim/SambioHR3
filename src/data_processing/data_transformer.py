"""
데이터 변환 및 전처리 모듈
태깅 데이터의 시계열 정렬, 꼬리물기 현상 처리, 2교대 근무 처리 등을 담당합니다.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime, timedelta
import warnings

class DataTransformer:
    """데이터 변환 및 전처리를 위한 클래스"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 식사시간 정의 (24시간 2교대 근무 반영)
        self.meal_times = {
            'breakfast': {'start': '06:30', 'end': '09:00'},
            'lunch': {'start': '11:20', 'end': '13:20'},
            'dinner': {'start': '17:00', 'end': '20:00'},
            'midnight_meal': {'start': '23:30', 'end': '01:00'}  # 자정 넘어가는 시간
        }
    
    def process_tagging_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        태깅 데이터 전처리
        
        Args:
            df: 원본 태깅 데이터
            
        Returns:
            DataFrame: 전처리된 태깅 데이터
        """
        self.logger.info("태깅 데이터 전처리 시작")
        
        # 필수 컬럼 확인
        required_columns = ['ENTE_DT', '출입시각', '사번', 'DR_NO', 'DR_NM', 'INOUT_GB']
        missing_columns = set(required_columns) - set(df.columns)
        if missing_columns:
            raise ValueError(f"필수 컬럼 누락: {missing_columns}")
        
        # 데이터 복사
        processed_df = df.copy()
        
        # 1. 시계열 정렬 (ENTE_DT + 출입시각)
        processed_df = self._sort_chronologically(processed_df)
        
        # 2. 교대근무 처리 (자정 이후 시간 연속성)
        processed_df = self._handle_shift_work(processed_df)
        
        # 3. 식사시간 탐지
        processed_df = self._detect_meal_times(processed_df)
        
        # 4. 꼬리물기 현상 처리
        processed_df = self._handle_tailgating(processed_df)
        
        # 5. 입문/출문 매칭 및 체류시간 계산
        processed_df = self._calculate_stay_duration(processed_df)
        
        # 6. 근무구역/비근무구역 분류
        processed_df = self._classify_work_areas(processed_df)
        
        self.logger.info(f"태깅 데이터 전처리 완료: {len(processed_df):,}행")
        
        return processed_df
    
    def _sort_chronologically(self, df: pd.DataFrame) -> pd.DataFrame:
        """시계열 정렬"""
        self.logger.info("시계열 정렬 수행")
        
        # 날짜와 시간 결합
        df['datetime'] = pd.to_datetime(df['ENTE_DT'].astype(str) + ' ' + df['출입시각'].astype(str).str.zfill(4), 
                                       format='%Y%m%d %H%M', errors='coerce')
        
        # 시간 변환에 실패한 행 처리
        invalid_time_mask = df['datetime'].isnull()
        if invalid_time_mask.any():
            self.logger.warning(f"잘못된 시간 형식 {invalid_time_mask.sum()}건 발견")
            df = df[~invalid_time_mask].copy()
        
        # 사번별, 시간순 정렬
        df = df.sort_values(['사번', 'datetime']).reset_index(drop=True)
        
        return df
    
    def _handle_shift_work(self, df: pd.DataFrame) -> pd.DataFrame:
        """교대근무 처리 (자정 이후 시간 연속성)"""
        self.logger.info("교대근무 시간 연속성 처리")
        
        # 자정을 넘나드는 근무 식별
        df['hour'] = df['datetime'].dt.hour
        df['date'] = df['datetime'].dt.date
        
        # 교대 구분 (임시 로직 - 실제로는 더 정교한 로직 필요)
        df['shift_type'] = np.where(
            (df['hour'] >= 6) & (df['hour'] < 18), 
            '주간', 
            '야간'
        )
        
        # 자정 이후 시간 처리 (23:30-01:00 야식시간 고려)
        df['cross_midnight'] = False
        
        # 사번별로 그룹화하여 자정 넘어가는 패턴 찾기
        for emp_id in df['사번'].unique():
            emp_mask = df['사번'] == emp_id
            emp_data = df[emp_mask].copy()
            
            # 시간 순서가 거꾸로 된 경우 (자정 넘어간 경우) 식별
            time_diff = emp_data['datetime'].diff()
            midnight_cross_mask = time_diff < timedelta(hours=-12)  # 시간이 거꾸로 간 경우
            
            if midnight_cross_mask.any():
                df.loc[emp_mask & midnight_cross_mask, 'cross_midnight'] = True
        
        return df
    
    def _detect_meal_times(self, df: pd.DataFrame) -> pd.DataFrame:
        """식사시간 탐지 (CAFETERIA 위치 + 시간대 매칭)"""
        self.logger.info("식사시간 탐지 시작")
        
        # CAFETERIA 위치 식별
        cafeteria_mask = df['DR_NM'].str.contains('CAFETERIA', case=False, na=False)
        
        # 식사시간 분류
        df['meal_type'] = None
        
        for meal, times in self.meal_times.items():
            start_time = datetime.strptime(times['start'], '%H:%M').time()
            end_time = datetime.strptime(times['end'], '%H:%M').time()
            
            if meal == 'midnight_meal':
                # 야식의 경우 자정을 넘나드는 시간 처리
                late_night_mask = (df['datetime'].dt.time >= start_time) | \
                                 (df['datetime'].dt.time <= end_time)
            else:
                late_night_mask = (df['datetime'].dt.time >= start_time) & \
                                 (df['datetime'].dt.time <= end_time)
            
            meal_mask = cafeteria_mask & late_night_mask
            df.loc[meal_mask, 'meal_type'] = meal
        
        meal_count = df['meal_type'].notna().sum()
        self.logger.info(f"식사시간 탐지 완료: {meal_count:,}건")
        
        return df
    
    def _handle_tailgating(self, df: pd.DataFrame) -> pd.DataFrame:
        """꼬리물기 현상 처리"""
        self.logger.info("꼬리물기 현상 처리 시작")
        
        # 같은 게이트에서 짧은 시간 간격으로 연속된 태깅 탐지
        tailgating_threshold = timedelta(seconds=30)  # 30초 이내 연속 태깅
        
        df['is_tailgating'] = False
        
        # 게이트별로 그룹화
        for gate in df['DR_NO'].unique():
            gate_mask = df['DR_NO'] == gate
            gate_data = df[gate_mask].copy()
            
            # 시간 간격 계산
            gate_data['time_diff'] = gate_data['datetime'].diff()
            
            # 꼬리물기 의심 케이스 식별
            tailgating_mask = (gate_data['time_diff'] <= tailgating_threshold) & \
                             (gate_data['time_diff'] > timedelta(seconds=0))
            
            if tailgating_mask.any():
                df.loc[gate_mask & tailgating_mask, 'is_tailgating'] = True
        
        tailgating_count = df['is_tailgating'].sum()
        self.logger.info(f"꼬리물기 현상 탐지: {tailgating_count:,}건")
        
        return df
    
    def _calculate_stay_duration(self, df: pd.DataFrame) -> pd.DataFrame:
        """입문/출문 매칭 및 체류시간 계산"""
        self.logger.info("체류시간 계산 시작")
        
        # 입문/출문 매칭
        df['stay_duration'] = None
        
        # 사번별로 그룹화하여 입문-출문 쌍 찾기
        for emp_id in df['사번'].unique():
            emp_mask = df['사번'] == emp_id
            emp_data = df[emp_mask].copy()
            
            # 입문과 출문 분리
            entry_data = emp_data[emp_data['INOUT_GB'] == '입문'].copy()
            exit_data = emp_data[emp_data['INOUT_GB'] == '출문'].copy()
            
            # 입문 후 가장 가까운 출문 찾기
            for idx, entry in entry_data.iterrows():
                # 같은 날짜 또는 다음 날 출문 찾기
                next_exits = exit_data[exit_data['datetime'] > entry['datetime']]
                
                if not next_exits.empty:
                    next_exit = next_exits.iloc[0]
                    duration = (next_exit['datetime'] - entry['datetime']).total_seconds() / 3600  # 시간 단위
                    df.loc[idx, 'stay_duration'] = duration
        
        duration_count = df['stay_duration'].notna().sum()
        self.logger.info(f"체류시간 계산 완료: {duration_count:,}건")
        
        return df
    
    def _classify_work_areas(self, df: pd.DataFrame) -> pd.DataFrame:
        """근무구역/비근무구역 분류"""
        self.logger.info("근무구역 분류 시작")
        
        # 기본적으로 모든 구역을 근무구역으로 분류 (추후 마스터 파일 연동 필요)
        df['work_area_type'] = 'work'
        
        # CAFETERIA는 비근무구역으로 분류
        cafeteria_mask = df['DR_NM'].str.contains('CAFETERIA', case=False, na=False)
        df.loc[cafeteria_mask, 'work_area_type'] = 'non_work'
        
        # 기타 비근무구역 (화장실, 휴게실 등) 
        non_work_keywords = ['화장실', '휴게실', '라운지', '피트니스', '주차장']
        for keyword in non_work_keywords:
            keyword_mask = df['DR_NM'].str.contains(keyword, case=False, na=False)
            df.loc[keyword_mask, 'work_area_type'] = 'non_work'
        
        work_area_count = (df['work_area_type'] == 'work').sum()
        non_work_area_count = (df['work_area_type'] == 'non_work').sum()
        
        self.logger.info(f"근무구역 분류 완료 - 근무구역: {work_area_count:,}건, 비근무구역: {non_work_area_count:,}건")
        
        return df
    
    def process_abc_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """ABC 작업 데이터 처리"""
        self.logger.info("ABC 작업 데이터 처리 시작")
        
        processed_df = df.copy()
        
        # 시간 단위 변환 (분 → 시간)
        processed_df['소요시간_시간'] = processed_df['소요시간'] / 60
        
        # Activity 분류 계층구조 정리
        processed_df['activity_hierarchy'] = (
            processed_df['Activity 대분류'].astype(str) + ' > ' +
            processed_df['Activity 중분류'].astype(str) + ' > ' +
            processed_df['Activity 소분류'].astype(str)
        )
        
        # 날짜 형식 통일
        processed_df['수행일자'] = pd.to_datetime(processed_df['수행일자'], format='%Y%m%d')
        
        self.logger.info(f"ABC 작업 데이터 처리 완료: {len(processed_df):,}행")
        
        return processed_df
    
    def process_claim_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """근무시간 Claim 데이터 처리 (24시간 근무 반영)"""
        self.logger.info("근무시간 Claim 데이터 처리 시작")
        
        processed_df = df.copy()
        
        # 날짜 형식 통일
        processed_df['근무일'] = pd.to_datetime(processed_df['근무일'], format='%Y%m%d')
        
        # 시간 형식 처리
        if '시작' in processed_df.columns and '종료' in processed_df.columns:
            processed_df['시작시간'] = pd.to_datetime(processed_df['시작'], errors='coerce')
            processed_df['종료시간'] = pd.to_datetime(processed_df['종료'], errors='coerce')
            
            # 교대근무 처리: 출근일 ≠ 퇴근일 경우
            processed_df['cross_day_work'] = processed_df['종료시간'] < processed_df['시작시간']
            
            # 실제 근무시간 계산
            processed_df['실제근무시간'] = np.where(
                processed_df['cross_day_work'],
                (processed_df['종료시간'] + timedelta(days=1) - processed_df['시작시간']).dt.total_seconds() / 3600,
                (processed_df['종료시간'] - processed_df['시작시간']).dt.total_seconds() / 3600
            )
        
        self.logger.info(f"근무시간 Claim 데이터 처리 완료: {len(processed_df):,}행")
        
        return processed_df
    
    def get_processing_summary(self, original_df: pd.DataFrame, processed_df: pd.DataFrame) -> Dict:
        """처리 결과 요약 정보"""
        summary = {
            'original_rows': len(original_df),
            'processed_rows': len(processed_df),
            'data_quality': {
                'null_ratio': processed_df.isnull().sum().sum() / (len(processed_df) * len(processed_df.columns)),
                'duplicate_ratio': processed_df.duplicated().sum() / len(processed_df)
            },
            'processing_stats': {}
        }
        
        # 태깅 데이터 특화 통계
        if 'meal_type' in processed_df.columns:
            summary['processing_stats']['meal_detections'] = processed_df['meal_type'].value_counts().to_dict()
        
        if 'is_tailgating' in processed_df.columns:
            summary['processing_stats']['tailgating_count'] = processed_df['is_tailgating'].sum()
        
        if 'stay_duration' in processed_df.columns:
            summary['processing_stats']['avg_stay_duration'] = processed_df['stay_duration'].mean()
        
        return summary