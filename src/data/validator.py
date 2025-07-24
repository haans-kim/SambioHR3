import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class DataValidator:
    """데이터 품질 검증 클래스"""
    
    def __init__(self):
        self.validation_results = {}
        self.required_columns = {
            'tag_data': ['employee_id', 'timestamp', 'location'],
            'employee_data': ['employee_id', 'name', 'department'],
            'attendance_data': ['employee_id', 'date', 'check_in', 'check_out']
        }
    
    def validate(self, df: pd.DataFrame, data_type: str = 'tag_data') -> Tuple[bool, Dict]:
        """
        데이터 검증 실행
        
        Args:
            df: 검증할 데이터프레임
            data_type: 데이터 유형
            
        Returns:
            Tuple[bool, Dict]: (검증 통과 여부, 검증 결과 상세)
        """
        self.validation_results = {
            'data_type': data_type,
            'total_records': len(df),
            'issues': [],
            'warnings': [],
            'statistics': {}
        }
        
        # 필수 컬럼 검증
        is_valid = self._check_required_columns(df, data_type)
        
        # 데이터 타입 검증
        if is_valid:
            self._check_data_types(df, data_type)
        
        # 데이터 품질 검증
        if is_valid:
            self._check_data_quality(df, data_type)
        
        # 통계 정보 수집
        self._collect_statistics(df)
        
        # 최종 검증 결과
        has_critical_issues = len(self.validation_results['issues']) > 0
        
        return not has_critical_issues, self.validation_results
    
    def _check_required_columns(self, df: pd.DataFrame, data_type: str) -> bool:
        """필수 컬럼 존재 여부 확인"""
        if data_type not in self.required_columns:
            logger.warning(f"Unknown data type: {data_type}")
            return True
        
        required = self.required_columns[data_type]
        missing = [col for col in required if col not in df.columns]
        
        if missing:
            self.validation_results['issues'].append({
                'type': 'missing_columns',
                'details': f"Missing required columns: {missing}"
            })
            return False
        
        return True
    
    def _check_data_types(self, df: pd.DataFrame, data_type: str):
        """데이터 타입 검증"""
        if data_type == 'tag_data':
            # timestamp 컬럼 타입 확인
            if 'timestamp' in df.columns:
                try:
                    pd.to_datetime(df['timestamp'])
                except:
                    self.validation_results['issues'].append({
                        'type': 'invalid_data_type',
                        'details': "timestamp column cannot be converted to datetime"
                    })
            
            # employee_id 타입 확인
            if 'employee_id' in df.columns:
                if df['employee_id'].dtype == 'object':
                    # 문자열 타입인지 확인
                    non_string = df['employee_id'].apply(lambda x: not isinstance(x, str) and pd.notna(x))
                    if non_string.any():
                        self.validation_results['warnings'].append({
                            'type': 'mixed_data_type',
                            'details': f"{non_string.sum()} non-string employee_ids found"
                        })
    
    def _check_data_quality(self, df: pd.DataFrame, data_type: str):
        """데이터 품질 검증"""
        # 중복 레코드 확인
        duplicates = df.duplicated().sum()
        if duplicates > 0:
            self.validation_results['warnings'].append({
                'type': 'duplicate_records',
                'details': f"{duplicates} duplicate records found"
            })
        
        # 결측값 확인
        missing_counts = df.isnull().sum()
        if missing_counts.any():
            missing_info = missing_counts[missing_counts > 0].to_dict()
            self.validation_results['warnings'].append({
                'type': 'missing_values',
                'details': missing_info
            })
        
        if data_type == 'tag_data' and all(col in df.columns for col in ['timestamp', 'employee_id']):
            # 시간 순서 확인
            df_sorted = df.sort_values(['employee_id', 'timestamp'])
            time_diffs = df_sorted.groupby('employee_id')['timestamp'].diff()
            
            # 역순 시간 확인
            reverse_time = (time_diffs < pd.Timedelta(0)).sum()
            if reverse_time > 0:
                self.validation_results['issues'].append({
                    'type': 'time_order_issue',
                    'details': f"{reverse_time} records with reverse time order"
                })
            
            # 비정상적인 시간 간격 확인 (예: 24시간 이상)
            large_gaps = (time_diffs > pd.Timedelta(hours=24)).sum()
            if large_gaps > 0:
                self.validation_results['warnings'].append({
                    'type': 'large_time_gaps',
                    'details': f"{large_gaps} records with >24 hour gaps"
                })
    
    def _collect_statistics(self, df: pd.DataFrame):
        """데이터 통계 정보 수집"""
        stats = {
            'total_records': len(df),
            'columns': list(df.columns),
            'memory_usage_mb': df.memory_usage(deep=True).sum() / 1024 / 1024
        }
        
        # 날짜 범위
        if 'timestamp' in df.columns:
            try:
                timestamps = pd.to_datetime(df['timestamp'])
                stats['date_range'] = {
                    'start': str(timestamps.min()),
                    'end': str(timestamps.max()),
                    'days': (timestamps.max() - timestamps.min()).days
                }
            except:
                pass
        
        # 유니크 값 수
        for col in df.columns:
            if df[col].dtype in ['object', 'string']:
                unique_count = df[col].nunique()
                if unique_count < 1000:  # 너무 많으면 생략
                    stats[f'{col}_unique_count'] = unique_count
        
        self.validation_results['statistics'] = stats
    
    def generate_report(self) -> str:
        """검증 결과 리포트 생성"""
        report = []
        report.append(f"Data Validation Report - {self.validation_results['data_type']}")
        report.append("=" * 50)
        
        # 통계 정보
        report.append("\nStatistics:")
        for key, value in self.validation_results['statistics'].items():
            report.append(f"  - {key}: {value}")
        
        # 심각한 이슈
        if self.validation_results['issues']:
            report.append("\n⚠️  Critical Issues:")
            for issue in self.validation_results['issues']:
                report.append(f"  - [{issue['type']}] {issue['details']}")
        
        # 경고
        if self.validation_results['warnings']:
            report.append("\n⚡ Warnings:")
            for warning in self.validation_results['warnings']:
                report.append(f"  - [{warning['type']}] {warning['details']}")
        
        # 검증 결과
        if not self.validation_results['issues']:
            report.append("\n✅ Validation Passed!")
        else:
            report.append("\n❌ Validation Failed!")
        
        return "\n".join(report)


# 사용 예시
if __name__ == "__main__":
    # 테스트 데이터
    test_data = pd.DataFrame({
        'employee_id': ['E001', 'E001', 'E002', 'E002', None],
        'timestamp': pd.date_range('2024-01-01', periods=5, freq='H'),
        'location': ['OFFICE', 'CAFETERIA', 'OFFICE', None, 'MEETING_ROOM']
    })
    
    validator = DataValidator()
    is_valid, results = validator.validate(test_data, 'tag_data')
    
    print(validator.generate_report())