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
        
        # 데이터 로딩 로깅 최적화
        self._cache_hit_count = 0
        self._cache_miss_count = 0
        
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
            employee_id: 직원 ID (문자열 또는 정수)
            start_date: 분석 시작일
            end_date: 분석 종료일
            
        Returns:
            Dict: 분석 결과
        """
        # employee_id를 문자열로 변환 (정수로 들어올 수 있음)
        employee_id = str(employee_id)
        # Individual analysis started - removed debug logging
        
        try:
            # 기본 데이터 수집
            tag_data = self._get_data('tag_logs', employee_id, start_date, end_date)
            claim_data = self._get_data('claim_data', employee_id, start_date, end_date)
            abc_data = self._get_data('abc_activity_data', employee_id, start_date, end_date)
            meal_data = self._get_data('meal_data', employee_id, start_date, end_date)  # 식사 데이터 추가
            
            # 태그 기반 분석 (정교한 분류기 사용) - 식사 데이터 포함
            tag_analysis_results = self._apply_tag_based_analysis(tag_data, meal_data)
            
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
                'meal_time_analysis': self._analyze_meal_times(tag_analysis_results, meal_data),
                'activity_analysis': self._analyze_activities(tag_analysis_results, abc_data),
                'efficiency_analysis': self._analyze_efficiency(tag_analysis_results, claim_data),
                'timeline_analysis': self._analyze_daily_timelines(tag_analysis_results, tag_data),
                'data_quality': self._assess_data_quality(tag_data, claim_data, abc_data),
                'generated_at': datetime.now().isoformat()
            }
            
            # 분석 결과 저장 - 현재 테이블 스키마 문제로 비활성화
            # self._save_analysis_result(employee_id, analysis_result)
            
            # 분석 완료 시 캐시 통계 로깅 (100회마다)
            total_requests = self._cache_hit_count + self._cache_miss_count
            if total_requests % 100 == 0 and total_requests > 0:
                hit_rate = (self._cache_hit_count / total_requests) * 100
                self.logger.info(f"캐시 통계 - 히트율: {hit_rate:.1f}% (총 {total_requests}회 요청)")
            
            # Individual analysis completed - removed debug logging
            return analysis_result
            
        except Exception as e:
            self.logger.error(f"개인별 분석 실패: {employee_id}, 오류: {e}")
            raise

    def _get_data(self, table_name: str, employee_id: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """데이터 조회 (pickle 파일에서 로드)"""
        try:
            # employee_id를 정수로 변환 (pickle 데이터가 정수형으로 저장됨)
            try:
                emp_id_int = int(employee_id)
            except ValueError:
                emp_id_int = employee_id
                
            # pickle 파일에서 전체 데이터 로드 후 필터링
            if table_name == 'claim_data':
                try:
                    claim_df = self.pickle_manager.load_dataframe('claim_data')
                    if claim_df is not None and not claim_df.empty:
                        # 직원 ID와 날짜로 필터링
                        if '사번' in claim_df.columns:
                            # 정수형 비교 우선, 실패시 문자열 비교
                            claim_df = claim_df[claim_df['사번'] == emp_id_int]
                        if '근무일' in claim_df.columns:
                            claim_df['근무일'] = pd.to_datetime(claim_df['근무일'], errors='coerce')
                            claim_df = claim_df[(claim_df['근무일'] >= start_date) & (claim_df['근무일'] <= end_date)]
                        return claim_df
                    return pd.DataFrame()
                except FileNotFoundError:
                    # Pickle file not found - removed debug logging
                    return pd.DataFrame()
                except Exception as e:
                    self.logger.warning(f"Error loading {table_name}: {e}")
                    return pd.DataFrame()
        
            elif table_name == 'tag_logs' or table_name == 'tag_data':
                try:
                    tag_df = self.pickle_manager.load_dataframe('tag_data')
                    if tag_df is not None and not tag_df.empty:
                        # 직원 ID와 날짜로 필터링 - '사번' 컬럼 사용
                        if '사번' in tag_df.columns:
                            # 정수형 비교 (pickle 데이터가 정수형)
                            tag_df = tag_df[tag_df['사번'] == emp_id_int]
                        if 'ENTE_DT' in tag_df.columns:
                            # YYYYMMDD 형식을 datetime으로 변환
                            tag_df['date'] = pd.to_datetime(tag_df['ENTE_DT'].astype(str), format='%Y%m%d', errors='coerce')
                            tag_df = tag_df[(tag_df['date'] >= start_date) & (tag_df['date'] <= end_date)]
                        return tag_df
                    return pd.DataFrame()
                except FileNotFoundError:
                    # Pickle file not found - removed debug logging
                    return pd.DataFrame()
                except Exception as e:
                    self.logger.warning(f"Error loading {table_name}: {e}")
                    return pd.DataFrame()
        
            elif table_name == 'abc_activity_data' or table_name == 'abc_data':
                try:
                    abc_df = self.pickle_manager.load_dataframe('abc_data')
                    if abc_df is not None and not abc_df.empty:
                        # 직원 ID와 날짜로 필터링 (ABC 데이터의 컬럼명에 맞게 수정 필요)
                        return abc_df
                    return pd.DataFrame()
                except FileNotFoundError:
                    # Pickle file not found - removed debug logging
                    return pd.DataFrame()
                except Exception as e:
                    self.logger.warning(f"Error loading {table_name}: {e}")
                    return pd.DataFrame()
            
            elif table_name == 'meal_data':
                try:
                    meal_df = self.pickle_manager.load_dataframe('meal_data')
                    if meal_df is not None and not meal_df.empty:
                        # 직원 ID와 날짜로 필터링
                        if '사번' in meal_df.columns:
                            # 문자열로 비교 (meal_data의 사번은 문자열)
                            meal_df = meal_df[meal_df['사번'] == str(employee_id)]
                        if '정산일' in meal_df.columns:
                            # 날짜 형식 맞추기 (YYYY-MM-DD 형식)
                            date_str = start_date.strftime('%Y-%m-%d')
                            meal_df = meal_df[meal_df['정산일'] == date_str]
                        return meal_df
                    return pd.DataFrame()
                except FileNotFoundError:
                    # Pickle file not found - removed debug logging
                    return pd.DataFrame()
                except Exception as e:
                    self.logger.warning(f"Error loading {table_name}: {e}")
                    return pd.DataFrame()
            
            # 기타 테이블은 빈 DataFrame 반환
            return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Unexpected error in _get_data: {e}")
            return pd.DataFrame()

    
    def _apply_tag_based_analysis(self, tag_data: pd.DataFrame, meal_data: pd.DataFrame = None) -> Dict[str, Any]:
        """
        정교한 분류기를 사용한 태그 기반 분석.
        태그 사이의 시간을 적절한 활동으로 채우고 식사 데이터 통합.
        """
        if tag_data.empty:
            return {'timeline': [], 'summary': {}}

        # 1. 데이터 전처리: classifier가 기대하는 형식으로 변환
        tag_sequence = []
        for _, row in tag_data.iterrows():
            # timestamp 생성 (ENTE_DT + 출입시각)
            try:
                date_str = str(row['ENTE_DT'])
                time_str = str(row['출입시각']).zfill(6)  # 6자리로 패딩
                timestamp = pd.to_datetime(f"{date_str} {time_str}", format='%Y%m%d %H%M%S')
            except:
                timestamp = None
            
            # tag_code 추출 (DR_NM에서 태그 코드 추출)
            dr_nm = row.get('DR_NM', '')
            tag_code = self._extract_tag_code(dr_nm)
            
            # O 태그 여부 확인 (사무실 태그)
            has_o_tag = 'O' in dr_nm or '사무실' in dr_nm or 'Office' in dr_nm or 'OFFICE' in dr_nm
            
            tag_sequence.append({
                'timestamp': timestamp,
                'tag_code': tag_code,
                'has_o_tag': has_o_tag,
                'dr_nm': dr_nm,
                'inout_gb': row.get('INOUT_GB', ''),
                'employee_id': row.get('사번', '')
            })
        
        # 시간순 정렬
        tag_sequence = sorted(tag_sequence, key=lambda x: x['timestamp'] if x['timestamp'] else pd.Timestamp.min)
        
        # 2. TagStateClassifier를 사용하여 분류 수행
        classified_sequence = self.state_classifier.classify_sequence(tag_sequence)
        
        # 3. 태그 사이의 시간 채우기 및 보정
        filled_sequence = self._fill_tag_gaps(classified_sequence)
        
        # 4. 식사 데이터 통합
        if meal_data is not None and not meal_data.empty:
            filled_sequence = self._integrate_meal_data(filled_sequence, meal_data)
        
        # 5. 꼬리물기 패턴 후처리
        self._handle_tailgating(filled_sequence)

        # 요약 생성
        summary = {}
        for entry in filled_sequence:
            state = entry['state']
            if state not in summary:
                summary[state] = 0
            
            # duration_minutes 합산
            duration = entry.get('duration_minutes', 0) or 0
            summary[state] += duration

        return {'timeline': filled_sequence, 'summary': summary}

    def _extract_tag_code(self, dr_nm: str) -> str:
        """DR_NM에서 태그 코드 추출"""
        # 태그 매핑 규칙
        if '사무실' in dr_nm or 'Office' in dr_nm or 'OFFICE' in dr_nm:
            return 'O'  # 사무실
        elif '식당' in dr_nm or 'CAFETERIA' in dr_nm:
            return 'M1'  # 식당
        elif '게이트' in dr_nm or 'GATE' in dr_nm or 'S/G' in dr_nm:
            if '입문' in dr_nm:
                return 'T2'  # 입문
            elif '출문' in dr_nm:
                return 'T3'  # 출문
            else:
                return 'T1'  # 경유
        elif '회의' in dr_nm or 'MEETING' in dr_nm:
            return 'G3'  # 회의실
        elif '교육' in dr_nm or 'TRAINING' in dr_nm:
            return 'G4'  # 교육장
        elif '휴게' in dr_nm or 'REST' in dr_nm:
            return 'N1'  # 휴게실
        elif '브릿지' in dr_nm or 'BRIDGE' in dr_nm:
            return 'T1'  # 경유
        elif '생산' in dr_nm or 'PRODUCTION' in dr_nm or 'P3' in dr_nm or 'P4' in dr_nm:
            return 'G1'  # 생산 구역
        elif '창고' in dr_nm or 'WAREHOUSE' in dr_nm:
            return 'G2'  # 창고
        else:
            return 'T1'  # 기본값: 경유
    
    def _fill_tag_gaps(self, sequence: List[Dict]) -> List[Dict]:
        """
        태그 사이의 시간 간격을 적절한 활동으로 채움.
        O 태그(사무실)가 있으면 전후 시간을 업무로 분류.
        """
        if not sequence:
            return sequence
        
        filled_sequence = []
        
        for i in range(len(sequence)):
            current = sequence[i]
            
            # 현재 항목의 지속 시간 재계산 (다음 태그까지의 시간)
            if i < len(sequence) - 1:
                next_timestamp = sequence[i + 1]['timestamp']
                if current['timestamp'] and next_timestamp:
                    duration = (next_timestamp - current['timestamp']).total_seconds() / 60
                    current['duration_minutes'] = duration
            
            # O 태그 전후 처리
            if current.get('has_o_tag') or current['tag_code'] == 'O':
                # O 태그는 확실한 업무
                current['state'] = '업무(확실)'
                current['confidence'] = 0.98
            elif i > 0 and (sequence[i-1].get('has_o_tag') or sequence[i-1]['tag_code'] == 'O'):
                # O 태그 다음은 업무로 처리 (출문 제외)
                if current['tag_code'] not in ['T3', 'T2']:
                    current['state'] = '업무'
                    current['confidence'] = 0.85
            elif i < len(sequence) - 1 and (sequence[i+1].get('has_o_tag') or sequence[i+1]['tag_code'] == 'O'):
                # O 태그 이전도 업무로 처리 (입문 후)
                if current['tag_code'] not in ['T3', 'T2']:
                    current['state'] = '업무'
                    current['confidence'] = 0.85
            
            # 생산 구역(G1) 태그는 업무로 처리
            if current['tag_code'] == 'G1':
                current['state'] = '업무'
                current['confidence'] = 0.90
            
            # 회의실(G3) 태그는 회의로 처리
            elif current['tag_code'] == 'G3':
                current['state'] = '회의'
                current['confidence'] = 0.90
            
            # 교육장(G4) 태그는 교육으로 처리
            elif current['tag_code'] == 'G4':
                current['state'] = '교육'
                current['confidence'] = 0.90
            
            # 식당(M1) 태그는 식사로 처리
            elif current['tag_code'] == 'M1':
                current['state'] = '식사'
                current['confidence'] = 1.0
                # 식사 시간대에 따라 세분화
                if current['timestamp']:
                    hour = current['timestamp'].hour
                    if 6 <= hour < 9:
                        current['meal_type'] = '아침'
                    elif 11 <= hour < 14:
                        current['meal_type'] = '점심'
                    elif 17 <= hour < 20:
                        current['meal_type'] = '저녁'
                    else:
                        current['meal_type'] = '야식'
            
            # 휴게실(N1, N2) 태그는 휴게로 처리
            elif current['tag_code'] in ['N1', 'N2']:
                current['state'] = '휴게'
                current['confidence'] = 0.85
            
            filled_sequence.append(current)
        
        return filled_sequence
    
    def _integrate_meal_data(self, sequence: List[Dict], meal_data: pd.DataFrame) -> List[Dict]:
        """
        실제 식사 데이터를 timeline에 통합.
        식당에서의 식사는 30분, 테이크아웃은 10분으로 계산.
        """
        if meal_data.empty:
            return sequence
        
        # 식사 데이터를 시간순으로 정렬
        meal_data = meal_data.sort_values('취식일시')
        
        for _, meal in meal_data.iterrows():
            try:
                # 식사 시간 파싱
                meal_time = pd.to_datetime(meal['취식일시'])
                
                # 식사 종류 판단
                meal_type = meal.get('식사구분명', '')
                if '조식' in meal_type:
                    meal_state = '식사'
                    meal_category = '아침'
                elif '중식' in meal_type:
                    meal_state = '식사'
                    meal_category = '점심'
                elif '석식' in meal_type:
                    meal_state = '식사'
                    meal_category = '저녁'
                elif '야식' in meal_type:
                    meal_state = '식사'
                    meal_category = '야식'
                else:
                    meal_state = '식사'
                    meal_category = '기타'
                
                # 테이크아웃 여부 판단
                배식구 = meal.get('배식구', '')
                is_takeout = '테이크아웃' in str(배식구).lower() or 'takeout' in str(배식구).lower()
                meal_duration = 10 if is_takeout else 30
                
                # timeline에서 해당 시간대 찾기
                meal_inserted = False
                for i, entry in enumerate(sequence):
                    if entry['timestamp'] and meal_time:
                        # 식사 시간이 현재 엔트리의 시간 범위 내에 있으면
                        entry_end_time = entry['timestamp']
                        if i < len(sequence) - 1:
                            entry_end_time = sequence[i + 1]['timestamp']
                        
                        if entry['timestamp'] <= meal_time < entry_end_time:
                            # 기존 엔트리를 식사로 변경
                            entry['state'] = meal_state
                            entry['meal_type'] = meal_category
                            entry['is_takeout'] = is_takeout
                            entry['duration_minutes'] = meal_duration
                            entry['confidence'] = 1.0
                            entry['meal_data'] = True
                            meal_inserted = True
                            break
                
                # 적절한 위치를 찾지 못했으면 새로운 엔트리 추가
                if not meal_inserted:
                    new_entry = {
                        'timestamp': meal_time,
                        'state': meal_state,
                        'meal_type': meal_category,
                        'is_takeout': is_takeout,
                        'duration_minutes': meal_duration,
                        'confidence': 1.0,
                        'tag_code': 'M1',
                        'meal_data': True
                    }
                    
                    # 시간 순서에 맞는 위치에 삽입
                    inserted = False
                    for i, entry in enumerate(sequence):
                        if entry['timestamp'] and meal_time < entry['timestamp']:
                            sequence.insert(i, new_entry)
                            inserted = True
                            break
                    
                    if not inserted:
                        sequence.append(new_entry)
                
            except Exception as e:
                self.logger.warning(f"식사 데이터 통합 중 오류: {e}")
        
        # 시간순 재정렬
        sequence = sorted(sequence, key=lambda x: x['timestamp'] if x['timestamp'] else pd.Timestamp.min)
        
        return sequence
    
    def _handle_tailgating(self, sequence: List[Dict]):
        """
        T1(경유)이 장시간 지속되는 '꼬리물기' 패턴을 감지하고 '업무'로 상태를 보정.
        """
        for i, entry in enumerate(sequence):
            # 경유 태그가 30분 이상 지속되면 업무로 변경
            if (entry.get('state') == '경유' and 
                entry.get('duration_minutes', 0) > 30):
                # Tail pattern detected - removed debug logging
                
                # 상태를 '업무'로 변경
                entry['state'] = '업무'
                entry['confidence'] = 0.75
                entry['original_state'] = '경유'
                entry['anomaly'] = 'tailgating'
    
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
        if not claim_data.empty and '근무시간' in claim_data.columns:
            # 시간 문자열을 시간(float)으로 변환
            def parse_work_time(time_str):
                try:
                    if pd.isna(time_str) or time_str == '':
                        return 0.0
                    # "HH:MM" 형태를 시간으로 변환
                    if ':' in str(time_str):
                        hours, minutes = str(time_str).split(':')
                        return float(hours) + float(minutes) / 60
                    else:
                        return float(time_str)
                except:
                    return 0.0
                    
            claim_data['근무시간_hours'] = claim_data['근무시간'].apply(parse_work_time)
            claim_total = claim_data['근무시간_hours'].sum()
        else:
            claim_total = 0
        
        return {
            'actual_work_hours': round(actual_work_hours, 2),
            'claimed_work_hours': round(claim_total, 2),
            'difference_hours': round(actual_work_hours - claim_total, 2),
            'accuracy_ratio': round((actual_work_hours / claim_total * 100) if claim_total > 0 else 0, 2),
            'work_efficiency': round((actual_work_hours / 8.0 * 100) if actual_work_hours > 0 else 0, 2)  # 8시간 기준
        }
    
    def _analyze_shift_patterns(self, analysis_results: Dict[str, Any], 
                              tag_data: pd.DataFrame) -> Dict[str, Any]:
        """교대 근무 패턴 분석"""
        return {
            'primary_shift': '주간',
            'shift_compliance': 95.0,
            'overtime_hours': 0,
            'night_shift_days': 0
        }
    
    def _analyze_meal_times(self, analysis_results: Dict[str, Any], 
                          meal_data: pd.DataFrame) -> Dict[str, Any]:
        """식사 시간 분석"""
        timeline = analysis_results.get('timeline', [])
        
        # 식사별 카운트와 시간 계산
        meal_summary = {
            '아침': {'count': 0, 'minutes': 0},
            '점심': {'count': 0, 'minutes': 0},
            '저녁': {'count': 0, 'minutes': 0},
            '야식': {'count': 0, 'minutes': 0}
        }
        
        for entry in timeline:
            if entry.get('state') == '식사':
                meal_type = entry.get('meal_type', '')
                duration = entry.get('duration_minutes', 0) or 0
                if meal_type in meal_summary:
                    meal_summary[meal_type]['count'] += 1
                    meal_summary[meal_type]['minutes'] += duration
        
        # 실제 식사 데이터가 있으면 더 정확한 카운트 사용
        if meal_data is not None and not meal_data.empty:
            for _, meal in meal_data.iterrows():
                meal_type = meal.get('식사구분명', '')
                if '조식' in meal_type:
                    meal_summary['아침']['count'] = max(meal_summary['아침']['count'], 1)
                elif '중식' in meal_type:
                    meal_summary['점심']['count'] = max(meal_summary['점심']['count'], 1)
                elif '석식' in meal_type:
                    meal_summary['저녁']['count'] = max(meal_summary['저녁']['count'], 1)
                elif '야식' in meal_type:
                    meal_summary['야식']['count'] = max(meal_summary['야식']['count'], 1)
        
        total_meal_minutes = sum(m['minutes'] for m in meal_summary.values())
        meal_count = sum(m['count'] for m in meal_summary.values())
        
        return {
            'breakfast_count': meal_summary['아침']['count'],
            'lunch_count': meal_summary['점심']['count'],
            'dinner_count': meal_summary['저녁']['count'],
            'midnight_meal_count': meal_summary['야식']['count'],
            'total_meal_minutes': total_meal_minutes,
            'avg_meal_duration': total_meal_minutes / meal_count if meal_count > 0 else 0
        }
    
    def _analyze_activities(self, analysis_results: Dict[str, Any], 
                          abc_data: pd.DataFrame) -> Dict[str, Any]:
        """활동 분석"""
        timeline = analysis_results.get('timeline', [])
        
        activity_summary = {}
        for entry in timeline:
            state = entry.get('state', 'UNKNOWN')
            duration = entry.get('duration_minutes', 0) or 0
            if state not in activity_summary:
                activity_summary[state] = 0
            activity_summary[state] += duration
        
        return {
            'activity_distribution': activity_summary,
            'primary_activity': max(activity_summary.items(), key=lambda x: x[1])[0] if activity_summary else 'UNKNOWN',
            'activity_diversity': len(activity_summary)
        }
    
    def _analyze_efficiency(self, analysis_results: Dict[str, Any], 
                          claim_data: pd.DataFrame) -> Dict[str, Any]:
        """효율성 분석"""
        timeline = analysis_results.get('timeline', [])
        
        # 실제 근무 시간과 생산적 시간 계산
        productive_states = [ActivityState.WORK.value, ActivityState.WORK_CONFIRMED.value]
        productive_minutes = sum(
            entry.get('duration_minutes', 0) or 0 
            for entry in timeline 
            if entry.get('state') in productive_states
        )
        
        total_minutes = sum(entry.get('duration_minutes', 0) or 0 for entry in timeline)
        
        return {
            'productivity_ratio': round((productive_minutes / total_minutes * 100) if total_minutes > 0 else 0, 2),
            'idle_time_ratio': 0,
            'focus_time_ratio': 0,
            'efficiency_score': round((productive_minutes / 480 * 100) if productive_minutes > 0 else 0, 2)  # 8시간 기준
        }
    
    def _analyze_daily_timelines(self, analysis_results: Dict[str, Any], 
                               tag_data: pd.DataFrame) -> Dict[str, Any]:
        """일별 타임라인 분석"""
        timeline = analysis_results.get('timeline', [])
        
        return {
            'timeline': timeline,  # timeline 데이터 포함
            'timeline_entries': len(timeline),
            'avg_activity_duration': round(sum(entry.get('duration_minutes', 0) or 0 for entry in timeline) / len(timeline), 2) if timeline else 0,
            'state_transitions': len(timeline) - 1 if len(timeline) > 1 else 0
        }
    
    def _assess_data_quality(self, tag_data: pd.DataFrame, claim_data: pd.DataFrame, 
                           abc_data: pd.DataFrame) -> Dict[str, Any]:
        """데이터 품질 평가"""
        return {
            'tag_data_completeness': 100 if not tag_data.empty else 0,
            'claim_data_completeness': 100 if not claim_data.empty else 0,
            'abc_data_completeness': 100 if not abc_data.empty else 0,
            'total_tags': len(tag_data) if not tag_data.empty else 0,
            'overall_quality_score': 80.0,
            'data_completeness': 80.0  # 대안 필드명
        }
    
    def _save_analysis_result(self, employee_id: str, analysis_result: Dict[str, Any]):
        """분석 결과 저장 - 현재 비활성화"""
        # 테이블 스키마 문제로 인해 비활성화
        pass
