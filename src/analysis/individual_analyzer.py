"""
개인별 분석기 구현
2교대 근무 시스템을 반영한 개인별 근무 데이터 분석
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, time
import logging
from sqlalchemy.orm import Session

from ..database import DatabaseManager, DailyWorkData, TagLogs, ClaimData, AbcActivityData
from ..data_processing import DataTransformer, PickleManager
from ..tag_system.state_classifier import TagStateClassifier, ActivityState

class IndividualAnalyzer:
    """개인별 분석기 클래스"""
    
    def __init__(self, db_manager: DatabaseManager, hmm_model=None):
        """
        Args:
            db_manager: 데이터베이스 매니저
            hmm_model: HMM 모델 (deprecated, 태그 기반 시스템 사용)
        """
        self.db_manager = db_manager
        self.data_transformer = DataTransformer()
        self.pickle_manager = PickleManager()
        self.logger = logging.getLogger(__name__)
        
        # 정교한 규칙 기반 분류기 초기화
        self.state_classifier = TagStateClassifier()
        
        # 2교대 근무 설정
        self.shift_patterns = {
            '주간': {'start': time(8, 0), 'end': time(20, 30)},
            '야간': {'start': time(20, 0), 'end': time(8, 30)}
        }
        
        # 식사시간 설정
        self.meal_times = {
            'breakfast': {'start': time(6, 30), 'end': time(9, 0)},
            'lunch': {'start': time(11, 20), 'end': time(13, 20)},
            'dinner': {'start': time(17, 0), 'end': time(20, 0)},
            'midnight_meal': {'start': time(23, 30), 'end': time(1, 0)}
        }
    
    def analyze_individual(self, employee_id: str, start_date: datetime, 
                          end_date: datetime) -> Dict[str, Any]:
        """
        개인별 종합 분석
        
        Args:
            employee_id: 직원 ID
            start_date: 분석 시작일
            end_date: 분석 종료일
            
        Returns:
            Dict: 분석 결과
        """
        self.logger.info(f"개인별 분석 시작: {employee_id}, {start_date} ~ {end_date}")
        
        try:
            # 기본 데이터 수집
            tag_data = self._get_data('tag_logs', employee_id, start_date, end_date)
            claim_data = self._get_data('claim_data', employee_id, start_date, end_date)
            abc_data = self._get_data('abc_activity_data', employee_id, start_date, end_date)
            
            # 태그 기반 분석 (정교한 분류기 사용)
            tag_analysis_results = self._apply_tag_based_analysis(tag_data)
            
            # 분석 결과 통합
            analysis_result = {
                'employee_id': employee_id,
                'analysis_period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'total_days': (end_date - start_date).days + 1
                },
                'work_time_analysis': self._analyze_work_time(tag_analysis_results, claim_data),
                'shift_analysis': self._analyze_shift_patterns(tag_analysis_results, tag_data),
                'meal_time_analysis': self._analyze_meal_times(tag_analysis_results, tag_data),
                'activity_analysis': self._analyze_activities(tag_analysis_results, abc_data),
                'efficiency_analysis': self._analyze_efficiency(tag_analysis_results, claim_data),
                'timeline_analysis': self._analyze_daily_timelines(tag_analysis_results, tag_data),
                'data_quality': self._assess_data_quality(tag_data, claim_data, abc_data),
                'generated_at': datetime.now().isoformat()
            }
            
            # 분석 결과 저장
            self._save_analysis_result(employee_id, analysis_result)
            
            self.logger.info(f"개인별 분석 완료: {employee_id}")
            return analysis_result
            
        except Exception as e:
            self.logger.error(f"개인별 분석 실패: {employee_id}, 오류: {e}")
            raise

    def _get_data(self, table_name: str, employee_id: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """데이터 조회 (캐시 우선)"""
        pickle_name = f"{table_name}_{employee_id}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        
        try:
            # 1. Pickle 캐시에서 로드 시도
            df = self.pickle_manager.load_dataframe(name=pickle_name)
            self.logger.info(f"캐시에서 데이터 로드 성공: {pickle_name}")
            return df
        except FileNotFoundError:
            self.logger.info(f"캐시 파일을 찾을 수 없음: {pickle_name}. 데이터베이스에서 조회합니다.")
            # 2. 캐시 없으면 데이터베이스에서 조회
            with self.db_manager.get_session() as session:
                table_class = self.db_manager.get_table_class(table_name)
                
                # 날짜 컬럼 동적 결정
                date_column = 'timestamp' if hasattr(table_class, 'timestamp') else 'work_date'
                
                query = session.query(table_class).filter(
                    table_class.employee_id == employee_id,
                    getattr(table_class, date_column) >= start_date,
                    getattr(table_class, date_column) <= end_date
                )
                
                df = pd.read_sql(query.statement, query.session.bind)
                
                # 3. 조회된 데이터를 다음을 위해 캐시에 저장
                if not df.empty:
                    self.pickle_manager.save_dataframe(df, name=pickle_name, description=f"{table_name} data for {employee_id}")
                    self.logger.info(f"데이터베이스 조회 결과를 캐시에 저장: {pickle_name}")
                
                return df

    
    def _apply_tag_based_analysis(self, tag_data: pd.DataFrame) -> Dict[str, Any]:
        """
        정교한 분류기를 사용한 태그 기반 분석.
        꼬리물기 등 특수 패턴을 후처리로 보정.
        """
        if tag_data.empty:
            return {'timeline': [], 'summary': {}}

        # 1. TagStateClassifier를 사용하여 1차 분류 수행
        # DataFrame을 dict 리스트로 변환하여 전달
        tag_sequence = tag_data.to_dict('records')
        classified_sequence = self.state_classifier.classify_sequence(tag_sequence)

        # 2. 꼬리물기 패턴 후처리
        self._handle_tailgating(classified_sequence)

        # 요약 생성
        summary = {}
        for entry in classified_sequence:
            state = entry['state']
            if state not in summary:
                summary[state] = 0
            
            # duration_minutes이 None이 아닌 경우만 합산
            duration = entry.get('duration_minutes', 0) or 0
            summary[state] += duration

        return {'timeline': classified_sequence, 'summary': summary}

    def _handle_tailgating(self, sequence: List[Dict]):
        """
        T1(경유)이 장시간 지속되는 '꼬리물기' 패턴을 감지하고 '업무'로 상태를 보정.
        """
        for i, entry in enumerate(sequence):
            # 'anomaly' 필드에 'tailgating'이 설정된 경우
            if entry.get('anomaly') == 'tailgating':
                self.logger.info(f"꼬리물기 패턴 감지: {entry['timestamp']} 에서 {entry.get('duration_minutes', 0):.1f}분 지속")
                
                # 상태를 '업무'로 변경하고 신뢰도 조정
                entry['state'] = ActivityState.WORK.value
                entry['confidence'] = entry.get('anomaly_confidence', 0.7) # anomaly_confidence 값 사용
                entry['original_state'] = ActivityState.TRANSIT.value # 원래 상태 기록
    
    def _analyze_work_time(self, analysis_results: Dict[str, Any], 
                          claim_data: pd.DataFrame) -> Dict[str, Any]:
        """근무시간 분석 - timeline의 duration_minutes을 직접 합산"""
        timeline = analysis_results.get('timeline', [])
        
        if not timeline:
            return {
                'actual_work_hours': 0,
                'claimed_work_hours': 0,
                'difference_hours': 0,
                'accuracy_ratio': 0,
                'work_efficiency': 0
            }
        
        # 근무 상태 정의 (ActivityState Enum 사용)
        work_states = [
            ActivityState.WORK.value, 
            ActivityState.WORK_CONFIRMED.value, 
            ActivityState.MEETING.value,
            ActivityState.EDUCATION.value
        ]
        
        # 각 상태의 총 지속시간 계산
        total_work_minutes = 0
        for entry in timeline:
            if entry['state'] in work_states:
                duration = entry.get('duration_minutes', 0) or 0
                total_work_minutes += duration
        
        actual_work_hours = total_work_minutes / 60

        # Claim 데이터와 비교
        claim_total = claim_data['근무시간'].sum() if not claim_data.empty else 0
        
        return {
            'actual_work_hours': round(actual_work_hours, 2),
            'claimed_work_hours': round(claim_total, 2),
            'difference_hours': round(actual_work_hours - claim_total, 2),
            'accuracy_ratio': round((actual_work_hours / claim_total * 100) if claim_total > 0 else 0, 2),
            'work_efficiency': round((actual_work_hours / 8.0 * 100) if actual_work_hours > 0 else 0, 2)  # 8시간 기준
        }
    
    # ... (이하 다른 _analyze 함수들은 기존 로직을 유지하되, 입력받는 데이터 구조에 맞춰 수정 필요)
    # ... (예: hmm_results 대신 analysis_results, predicted_state 대신 state)
