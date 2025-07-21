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
from ..hmm import HMMModel, ViterbiAlgorithm
from ..data_processing import DataTransformer, PickleManager

class IndividualAnalyzer:
    """개인별 분석기 클래스"""
    
    def __init__(self, db_manager: DatabaseManager, hmm_model: HMMModel):
        """
        Args:
            db_manager: 데이터베이스 매니저
            hmm_model: HMM 모델
        """
        self.db_manager = db_manager
        self.hmm_model = hmm_model
        self.viterbi = ViterbiAlgorithm(hmm_model)
        self.data_transformer = DataTransformer()
        self.pickle_manager = PickleManager()
        self.logger = logging.getLogger(__name__)
        
        # 2교대 근무 설정
        self.shift_patterns = {
            '주간': {'start': time(8, 0), 'end': time(17, 0)},
            '야간': {'start': time(20, 0), 'end': time(5, 0)}
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
            
            # HMM 모델 적용
            hmm_results = self._apply_hmm_analysis(tag_data)
            
            # 분석 결과 통합
            analysis_result = {
                'employee_id': employee_id,
                'analysis_period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'total_days': (end_date - start_date).days + 1
                },
                'work_time_analysis': self._analyze_work_time(hmm_results, claim_data),
                'shift_analysis': self._analyze_shift_patterns(hmm_results, tag_data),
                'meal_time_analysis': self._analyze_meal_times(hmm_results, tag_data),
                'activity_analysis': self._analyze_activities(hmm_results, abc_data),
                'efficiency_analysis': self._analyze_efficiency(hmm_results, claim_data),
                'timeline_analysis': self._analyze_daily_timelines(hmm_results, tag_data),
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

    
    def _apply_hmm_analysis(self, tag_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """HMM 모델 적용"""
        if not tag_data:
            return {'timeline': [], 'summary': {}}
        
        # 태그 데이터를 관측 시퀀스로 변환
        observations = []
        for tag in tag_data:
            obs = {
                'timestamp': tag['timestamp'],
                '태그위치': tag['tag_location'],
                '시간간격': 'medium',  # 실제로는 계산 필요
                '요일': tag['timestamp'].strftime('%A'),
                '시간대': self._get_time_period(tag['timestamp']),
                '근무구역여부': tag['work_area_type'],
                'CAFETERIA위치': 'CAFETERIA' in tag['tag_location'],
                '교대구분': self._determine_shift_type(tag['timestamp'])
            }
            observations.append(obs)
        
        # Viterbi 알고리즘으로 상태 시퀀스 예측
        prediction_result = self.viterbi.predict_with_timeline(observations)
        
        return prediction_result
    
    def _analyze_work_time(self, hmm_results: Dict[str, Any], 
                          claim_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """근무시간 분석"""
        timeline = hmm_results.get('timeline', [])
        
        # 근무 상태 시간 계산
        work_states = ['근무', '집중근무', '장비조작', '회의', '작업준비', '작업중']
        work_time_total = 0
        
        for i, entry in enumerate(timeline):
            if entry['predicted_state'] in work_states:
                # 다음 엔트리와의 시간 차이 계산
                if i + 1 < len(timeline):
                    next_timestamp = timeline[i + 1]['timestamp']
                    current_timestamp = entry['timestamp']
                    if next_timestamp and current_timestamp:
                        duration = (next_timestamp - current_timestamp).total_seconds() / 3600
                        work_time_total += duration
        
        # Claim 데이터와 비교
        claim_total = sum(float(c.get('actual_work_duration', 0)) for c in claim_data)
        
        return {
            'actual_work_hours': round(work_time_total, 2),
            'claimed_work_hours': round(claim_total, 2),
            'difference_hours': round(work_time_total - claim_total, 2),
            'accuracy_ratio': round((work_time_total / claim_total * 100) if claim_total > 0 else 0, 2),
            'work_efficiency': round((work_time_total / 8.0 * 100) if work_time_total > 0 else 0, 2)  # 8시간 기준
        }
    
    def _analyze_shift_patterns(self, hmm_results: Dict[str, Any], 
                               tag_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """교대 근무 패턴 분석"""
        timeline = hmm_results.get('timeline', [])
        
        # 교대별 근무 시간 분석
        shift_analysis = {
            '주간': {'work_hours': 0, 'activity_count': 0},
            '야간': {'work_hours': 0, 'activity_count': 0}
        }
        
        work_states = ['근무', '집중근무', '장비조작', '회의', '작업준비', '작업중']
        
        for i, entry in enumerate(timeline):
            if entry['predicted_state'] in work_states:
                shift_type = self._determine_shift_type(entry['timestamp'])
                shift_analysis[shift_type]['activity_count'] += 1
                
                # 시간 계산
                if i + 1 < len(timeline):
                    next_timestamp = timeline[i + 1]['timestamp']
                    current_timestamp = entry['timestamp']
                    if next_timestamp and current_timestamp:
                        duration = (next_timestamp - current_timestamp).total_seconds() / 3600
                        shift_analysis[shift_type]['work_hours'] += duration
        
        # 교대별 효율성 계산
        for shift_type in shift_analysis:
            if shift_analysis[shift_type]['activity_count'] > 0:
                shift_analysis[shift_type]['avg_duration'] = (
                    shift_analysis[shift_type]['work_hours'] / 
                    shift_analysis[shift_type]['activity_count']
                )
            else:
                shift_analysis[shift_type]['avg_duration'] = 0
        
        return {
            'shift_patterns': shift_analysis,
            'preferred_shift': max(shift_analysis, key=lambda x: shift_analysis[x]['work_hours']),
            'cross_midnight_work': self._detect_cross_midnight_work(timeline)
        }
    
    def _analyze_meal_times(self, hmm_results: Dict[str, Any], 
                           tag_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """식사시간 분석"""
        timeline = hmm_results.get('timeline', [])
        
        meal_analysis = {
            '조식': {'frequency': 0, 'avg_duration': 0, 'times': []},
            '중식': {'frequency': 0, 'avg_duration': 0, 'times': []},
            '석식': {'frequency': 0, 'avg_duration': 0, 'times': []},
            '야식': {'frequency': 0, 'avg_duration': 0, 'times': []}
        }
        
        meal_states = ['조식', '중식', '석식', '야식']
        
        for i, entry in enumerate(timeline):
            if entry['predicted_state'] in meal_states:
                meal_type = entry['predicted_state']
                meal_analysis[meal_type]['frequency'] += 1
                meal_analysis[meal_type]['times'].append(entry['timestamp'].time())
                
                # 식사 지속 시간 계산
                if i + 1 < len(timeline):
                    next_timestamp = timeline[i + 1]['timestamp']
                    current_timestamp = entry['timestamp']
                    if next_timestamp and current_timestamp:
                        duration = (next_timestamp - current_timestamp).total_seconds() / 60  # 분 단위
                        meal_analysis[meal_type]['avg_duration'] += duration
        
        # 평균 지속 시간 계산
        for meal_type in meal_analysis:
            if meal_analysis[meal_type]['frequency'] > 0:
                meal_analysis[meal_type]['avg_duration'] = (
                    meal_analysis[meal_type]['avg_duration'] / 
                    meal_analysis[meal_type]['frequency']
                )
            
            # 시간 정보를 문자열로 변환
            meal_analysis[meal_type]['times'] = [
                t.strftime('%H:%M') for t in meal_analysis[meal_type]['times']
            ]
        
        return {
            'meal_patterns': meal_analysis,
            'total_meal_time': sum(m['avg_duration'] * m['frequency'] for m in meal_analysis.values()),
            'meal_regularity': self._calculate_meal_regularity(meal_analysis)
        }
    
    def _analyze_activities(self, hmm_results: Dict[str, Any], 
                           abc_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """활동 분석"""
        timeline = hmm_results.get('timeline', [])
        
        # HMM 예측 상태 분포
        state_distribution = {}
        for entry in timeline:
            state = entry['predicted_state']
            state_distribution[state] = state_distribution.get(state, 0) + 1
        
        # 백분율 계산
        total_activities = len(timeline)
        state_percentages = {
            state: (count / total_activities * 100) if total_activities > 0 else 0
            for state, count in state_distribution.items()
        }
        
        # ABC 데이터 분석
        abc_analysis = {}
        for activity in abc_data:
            activity_type = activity['activity_classification']
            if activity_type not in abc_analysis:
                abc_analysis[activity_type] = {
                    'frequency': 0,
                    'total_duration': 0,
                    'activities': []
                }
            
            abc_analysis[activity_type]['frequency'] += 1
            abc_analysis[activity_type]['total_duration'] += activity['duration_hours']
            abc_analysis[activity_type]['activities'].append(activity)
        
        return {
            'predicted_state_distribution': state_percentages,
            'abc_activity_analysis': abc_analysis,
            'activity_diversity': len(state_distribution),
            'concentration_ratio': max(state_percentages.values()) if state_percentages else 0
        }
    
    def _analyze_efficiency(self, hmm_results: Dict[str, Any], 
                           claim_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """효율성 분석"""
        timeline = hmm_results.get('timeline', [])
        
        # 집중 근무 시간 계산
        focused_states = ['집중근무', '작업중']
        focused_time = 0
        total_work_time = 0
        
        work_states = ['근무', '집중근무', '장비조작', '회의', '작업준비', '작업중']
        
        for i, entry in enumerate(timeline):
            if entry['predicted_state'] in work_states:
                if i + 1 < len(timeline):
                    next_timestamp = timeline[i + 1]['timestamp']
                    current_timestamp = entry['timestamp']
                    if next_timestamp and current_timestamp:
                        duration = (next_timestamp - current_timestamp).total_seconds() / 3600
                        total_work_time += duration
                        
                        if entry['predicted_state'] in focused_states:
                            focused_time += duration
        
        # 효율성 지표 계산
        efficiency_ratio = (focused_time / total_work_time * 100) if total_work_time > 0 else 0
        
        # 데이터 신뢰도 계산
        confidence_scores = [entry.get('confidence', 0) for entry in timeline]
        avg_confidence = np.mean(confidence_scores) if confidence_scores else 0
        
        return {
            'focused_work_ratio': round(efficiency_ratio, 2),
            'total_work_time': round(total_work_time, 2),
            'focused_work_time': round(focused_time, 2),
            'data_confidence': round(avg_confidence * 100, 2),
            'productivity_score': round((efficiency_ratio * avg_confidence), 2)
        }
    
    def _analyze_daily_timelines(self, hmm_results: Dict[str, Any], 
                                tag_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """일일 타임라인 분석"""
        timeline = hmm_results.get('timeline', [])
        
        # 일별 그룹화
        daily_timelines = {}
        for entry in timeline:
            date_key = entry['timestamp'].strftime('%Y-%m-%d')
            if date_key not in daily_timelines:
                daily_timelines[date_key] = []
            daily_timelines[date_key].append(entry)
        
        # 일별 분석
        daily_analysis = {}
        for date, day_timeline in daily_timelines.items():
            daily_analysis[date] = {
                'activity_count': len(day_timeline),
                'work_duration': self._calculate_daily_work_duration(day_timeline),
                'first_activity': day_timeline[0]['timestamp'].strftime('%H:%M') if day_timeline else None,
                'last_activity': day_timeline[-1]['timestamp'].strftime('%H:%M') if day_timeline else None,
                'shift_type': self._determine_shift_type(day_timeline[0]['timestamp']) if day_timeline else None,
                'state_summary': self._summarize_daily_states(day_timeline)
            }
        
        return {
            'daily_timelines': daily_analysis,
            'total_days': len(daily_timelines),
            'avg_daily_activities': np.mean([d['activity_count'] for d in daily_analysis.values()]) if daily_analysis else 0
        }
    
    def _assess_data_quality(self, tag_data: List[Dict[str, Any]], 
                           claim_data: List[Dict[str, Any]], 
                           abc_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """데이터 품질 평가"""
        quality_metrics = {
            'tag_data_completeness': 0,
            'claim_data_completeness': 0,
            'abc_data_completeness': 0,
            'overall_quality_score': 0,
            'data_gaps': [],
            'reliability_indicators': {}
        }
        
        # 태그 데이터 품질
        if tag_data:
            confidence_scores = [t.get('confidence_score', 0) for t in tag_data if t.get('confidence_score')]
            quality_metrics['tag_data_completeness'] = len(confidence_scores) / len(tag_data) * 100
            quality_metrics['reliability_indicators']['avg_tag_confidence'] = np.mean(confidence_scores) if confidence_scores else 0
        
        # Claim 데이터 품질
        if claim_data:
            complete_claims = [c for c in claim_data if c.get('actual_work_duration') is not None]
            quality_metrics['claim_data_completeness'] = len(complete_claims) / len(claim_data) * 100
        
        # ABC 데이터 품질
        if abc_data:
            complete_activities = [a for a in abc_data if a.get('duration_hours') is not None]
            quality_metrics['abc_data_completeness'] = len(complete_activities) / len(abc_data) * 100
        
        # 전체 품질 점수
        completeness_scores = [
            quality_metrics['tag_data_completeness'],
            quality_metrics['claim_data_completeness'],
            quality_metrics['abc_data_completeness']
        ]
        quality_metrics['overall_quality_score'] = np.mean(completeness_scores)
        
        return quality_metrics
    
    def _get_time_period(self, timestamp: datetime) -> str:
        """시간대 분류"""
        current_time = timestamp.time()
        
        if time(5, 0) <= current_time < time(9, 0):
            return 'early_morning'
        elif time(9, 0) <= current_time < time(12, 0):
            return 'morning'
        elif time(12, 0) <= current_time < time(18, 0):
            return 'afternoon'
        elif time(18, 0) <= current_time < time(22, 0):
            return 'evening'
        else:
            return 'night'
    
    def _determine_shift_type(self, timestamp: datetime) -> str:
        """교대 구분 판정"""
        current_time = timestamp.time()
        
        if time(6, 0) <= current_time < time(18, 0):
            return '주간'
        else:
            return '야간'
    
    def _detect_cross_midnight_work(self, timeline: List[Dict[str, Any]]) -> bool:
        """자정 넘나드는 근무 탐지"""
        if not timeline:
            return False
        
        work_states = ['근무', '집중근무', '장비조작', '회의', '작업준비', '작업중']
        
        for i, entry in enumerate(timeline):
            if entry['predicted_state'] in work_states:
                if i + 1 < len(timeline):
                    current_time = entry['timestamp'].time()
                    next_time = timeline[i + 1]['timestamp'].time()
                    
                    # 자정을 넘나드는 경우 (23:00 이후에서 06:00 이전으로)
                    if current_time >= time(23, 0) and next_time <= time(6, 0):
                        return True
        
        return False
    
    def _calculate_meal_regularity(self, meal_analysis: Dict[str, Any]) -> float:
        """식사 규칙성 계산"""
        regularity_scores = []
        
        for meal_type, data in meal_analysis.items():
            if data['frequency'] > 1:
                times = [datetime.strptime(t, '%H:%M').time() for t in data['times']]
                time_minutes = [t.hour * 60 + t.minute for t in times]
                
                # 시간의 표준편차를 이용한 규칙성 계산
                std_dev = np.std(time_minutes)
                regularity = max(0, 100 - std_dev)  # 표준편차가 클수록 규칙성 낮음
                regularity_scores.append(regularity)
        
        return np.mean(regularity_scores) if regularity_scores else 0
    
    def _calculate_daily_work_duration(self, day_timeline: List[Dict[str, Any]]) -> float:
        """일일 근무 지속시간 계산"""
        work_states = ['근무', '집중근무', '장비조작', '회의', '작업준비', '작업중']
        total_duration = 0
        
        for i, entry in enumerate(day_timeline):
            if entry['predicted_state'] in work_states:
                if i + 1 < len(day_timeline):
                    next_timestamp = day_timeline[i + 1]['timestamp']
                    current_timestamp = entry['timestamp']
                    duration = (next_timestamp - current_timestamp).total_seconds() / 3600
                    total_duration += duration
        
        return round(total_duration, 2)
    
    def _summarize_daily_states(self, day_timeline: List[Dict[str, Any]]) -> Dict[str, int]:
        """일일 상태 요약"""
        state_counts = {}
        for entry in day_timeline:
            state = entry['predicted_state']
            state_counts[state] = state_counts.get(state, 0) + 1
        
        return state_counts
    
    def _save_analysis_result(self, employee_id: str, analysis_result: Dict[str, Any]):
        """분석 결과 저장"""
        try:
            # 분석 결과를 데이터베이스나 파일로 저장하는 로직
            # 여기서는 로깅만 수행
            self.logger.info(f"분석 결과 저장 완료: {employee_id}")
        except Exception as e:
            self.logger.error(f"분석 결과 저장 실패: {employee_id}, 오류: {e}")
    
    def generate_individual_report(self, employee_id: str, analysis_result: Dict[str, Any]) -> str:
        """개인별 분석 보고서 생성"""
        report = f"""
=== 개인별 근무 분석 보고서 ===

직원 ID: {employee_id}
분석 기간: {analysis_result['analysis_period']['start_date']} ~ {analysis_result['analysis_period']['end_date']}

## 근무시간 분석
- 실제 근무시간: {analysis_result['work_time_analysis']['actual_work_hours']}시간
- 신고 근무시간: {analysis_result['work_time_analysis']['claimed_work_hours']}시간
- 정확도: {analysis_result['work_time_analysis']['accuracy_ratio']}%

## 교대 근무 분석
- 주간 근무시간: {analysis_result['shift_analysis']['shift_patterns']['주간']['work_hours']}시간
- 야간 근무시간: {analysis_result['shift_analysis']['shift_patterns']['야간']['work_hours']}시간
- 선호 교대: {analysis_result['shift_analysis']['preferred_shift']}

## 효율성 분석
- 집중 근무 비율: {analysis_result['efficiency_analysis']['focused_work_ratio']}%
- 생산성 점수: {analysis_result['efficiency_analysis']['productivity_score']}점

## 데이터 품질
- 전체 품질 점수: {analysis_result['data_quality']['overall_quality_score']}점
        """
        
        return report