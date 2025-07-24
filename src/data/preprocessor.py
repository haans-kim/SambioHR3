import pandas as pd
import numpy as np
from datetime import timedelta
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class TagDataPreprocessor:
    """태그 데이터 전처리 클래스"""
    
    def __init__(self, 
                 gap_threshold_minutes: int = 5,
                 min_duration_minutes: int = 1):
        """
        Args:
            gap_threshold_minutes: 꼬리물기 현상으로 간주할 최대 시간 간격 (분)
            min_duration_minutes: 최소 체류 시간 (분)
        """
        self.gap_threshold = timedelta(minutes=gap_threshold_minutes)
        self.min_duration = timedelta(minutes=min_duration_minutes)
    
    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        태그 데이터 전처리 파이프라인
        
        Args:
            df: 원본 태그 데이터
            
        Returns:
            pd.DataFrame: 전처리된 데이터
        """
        df = df.copy()
        
        # 타임스탬프 처리
        df = self._process_timestamps(df)
        
        # 결측값 처리
        df = self._handle_missing_values(df)
        
        # 꼬리물기 현상 보정
        df = self._correct_tailgating(df)
        
        # 체류 시간 계산
        df = self._calculate_duration(df)
        
        # 이상치 제거
        df = self._remove_outliers(df)
        
        return df
    
    def _process_timestamps(self, df: pd.DataFrame) -> pd.DataFrame:
        """타임스탬프 처리 및 정규화"""
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values(['employee_id', 'timestamp'])
            
            # 시간대 정보 추가
            df['hour'] = df['timestamp'].dt.hour
            df['day_of_week'] = df['timestamp'].dt.dayofweek
            df['date'] = df['timestamp'].dt.date
            
        return df
    
    def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """결측값 처리"""
        # 위치 정보가 없는 경우
        if 'location' in df.columns:
            df['location'] = df['location'].fillna('UNKNOWN')
        
        # 직원 ID가 없는 경우 제거
        if 'employee_id' in df.columns:
            df = df.dropna(subset=['employee_id'])
        
        return df
    
    def _correct_tailgating(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        꼬리물기 현상 보정
        한 사람이 문을 열면 다른 사람이 따라 들어가는 현상을 보정
        """
        if not all(col in df.columns for col in ['employee_id', 'timestamp', 'location']):
            logger.warning("Required columns for tailgating correction not found")
            return df
        
        corrected_records = []
        
        for (location, date), group in df.groupby(['location', 'date']):
            group = group.sort_values('timestamp')
            
            prev_time = None
            for idx, row in group.iterrows():
                if prev_time is not None:
                    time_diff = row['timestamp'] - prev_time
                    
                    # 꼬리물기로 의심되는 경우
                    if time_diff < self.gap_threshold:
                        # 보간된 시간 할당
                        interpolated_time = prev_time + time_diff / 2
                        row = row.copy()
                        row['timestamp'] = interpolated_time
                        row['is_interpolated'] = True
                    else:
                        row['is_interpolated'] = False
                else:
                    row['is_interpolated'] = False
                
                corrected_records.append(row)
                prev_time = row['timestamp']
        
        return pd.DataFrame(corrected_records)
    
    def _calculate_duration(self, df: pd.DataFrame) -> pd.DataFrame:
        """각 위치에서의 체류 시간 계산"""
        if not all(col in df.columns for col in ['employee_id', 'timestamp', 'location']):
            return df
        
        df = df.sort_values(['employee_id', 'timestamp'])
        
        # 다음 레코드까지의 시간 계산
        df['next_timestamp'] = df.groupby('employee_id')['timestamp'].shift(-1)
        
        # 체류 시간 계산
        df['duration'] = df['next_timestamp'] - df['timestamp']
        
        # 마지막 레코드 또는 날짜가 바뀌는 경우 처리
        mask = df['next_timestamp'].isna() | (df['timestamp'].dt.date != df['next_timestamp'].dt.date)
        df.loc[mask, 'duration'] = timedelta(minutes=5)  # 기본값 5분
        
        # 체류 시간을 분 단위로 변환
        df['duration_minutes'] = df['duration'].dt.total_seconds() / 60
        
        return df
    
    def _remove_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """이상치 제거"""
        # 너무 짧은 체류 시간 제거
        if 'duration' in df.columns:
            df = df[df['duration'] >= self.min_duration]
        
        # 비정상적으로 긴 체류 시간 처리 (예: 8시간 이상)
        max_duration = timedelta(hours=8)
        if 'duration' in df.columns:
            df.loc[df['duration'] > max_duration, 'duration'] = max_duration
            df.loc[df['duration'] > max_duration, 'duration_minutes'] = 480
        
        return df
    
    def extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        시계열 특성 추출
        
        Args:
            df: 전처리된 데이터
            
        Returns:
            pd.DataFrame: 특성이 추가된 데이터
        """
        df = df.copy()
        
        # 시간대별 특성
        df['time_of_day'] = pd.cut(df['hour'], 
                                   bins=[0, 6, 12, 18, 24],
                                   labels=['night', 'morning', 'afternoon', 'evening'])
        
        # 이전/다음 위치
        df['prev_location'] = df.groupby('employee_id')['location'].shift(1)
        df['next_location'] = df.groupby('employee_id')['location'].shift(-1)
        
        # 위치 변화 여부
        df['location_changed'] = df['location'] != df['prev_location']
        
        # 누적 체류 시간
        df['cumulative_duration'] = df.groupby(['employee_id', 'date', 'location'])['duration_minutes'].cumsum()
        
        return df


# 사용 예시
if __name__ == "__main__":
    # 테스트 데이터 생성
    test_data = pd.DataFrame({
        'employee_id': ['E001'] * 5,
        'timestamp': pd.date_range('2024-01-01 09:00', periods=5, freq='30min'),
        'location': ['OFFICE', 'OFFICE', 'CAFETERIA', 'OFFICE', 'MEETING_ROOM']
    })
    
    preprocessor = TagDataPreprocessor()
    processed_data = preprocessor.preprocess(test_data)
    featured_data = preprocessor.extract_features(processed_data)
    
    print("Processed data:")
    print(featured_data)