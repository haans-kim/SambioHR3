"""
개인별 분석 결과를 데이터베이스에 저장하는 모듈
"""

import logging
from datetime import datetime, date
from typing import Dict, Any, Optional
import pandas as pd
from sqlalchemy import text

from ..database import get_database_manager


class AnalysisResultSaver:
    """개인별 분석 결과를 DB에 저장하는 클래스"""
    
    def __init__(self):
        self.db_manager = get_database_manager()
        self.logger = logging.getLogger(__name__)
    
    def save_individual_analysis(self, analysis_result: Dict[str, Any], employee_info: Optional[Dict[str, Any]] = None) -> bool:
        """
        개인별 분석 결과를 daily_analysis_results 테이블에 저장
        
        Args:
            analysis_result: individual_dashboard에서 생성된 분석 결과
            employee_info: 직원 조직 정보 (center_id, group_id, team_id 등)
            
        Returns:
            bool: 저장 성공 여부
        """
        try:
            # 직원 정보가 없으면 DB에서 조회
            if not employee_info:
                employee_info = self._get_employee_info(analysis_result['employee_id'])
            
            # 저장할 데이터 준비
            data = self._prepare_data_for_save(analysis_result, employee_info)
            
            # DB에 저장 (UPSERT)
            self._upsert_daily_analysis(data)
            
            self.logger.info(f"분석 결과 저장 완료: {data['employee_id']} - {data['analysis_date']}")
            return True
            
        except Exception as e:
            self.logger.error(f"분석 결과 저장 실패: {e}")
            return False
    
    def _get_employee_info(self, employee_id: str) -> Dict[str, Any]:
        """직원의 조직 정보 조회"""
        try:
            # 조직 마스터 데이터에서 직원 정보 조회
            query = """
            SELECT 
                e.employee_id,
                e.employee_name,
                e.center_id,
                e.group_id,
                e.team_id,
                om.center_name,
                om.group_name,
                om.team_name,
                e.job_grade
            FROM employees e
            LEFT JOIN organization_master om ON e.team_id = om.team_id
            WHERE e.employee_id = :employee_id
            """
            
            result = self.db_manager.execute_query(query, {'employee_id': employee_id})
            
            if result and len(result) > 0:
                row = result[0]
                return {
                    'employee_id': row[0],
                    'employee_name': row[1],
                    'center_id': row[2],
                    'group_id': row[3],
                    'team_id': row[4],
                    'center_name': row[5],
                    'group_name': row[6],
                    'team_name': row[7],
                    'job_grade': row[8]
                }
            else:
                # 조직 정보가 없는 경우 기본값 반환
                return {
                    'employee_id': employee_id,
                    'center_id': None,
                    'group_id': None,
                    'team_id': None,
                    'job_grade': None
                }
                
        except Exception as e:
            self.logger.warning(f"직원 정보 조회 실패: {e}")
            return {'employee_id': employee_id}
    
    def _prepare_data_for_save(self, analysis_result: Dict[str, Any], employee_info: Dict[str, Any]) -> Dict[str, Any]:
        """저장할 데이터 준비"""
        
        # 기본 정보
        data = {
            'employee_id': analysis_result['employee_id'],
            'analysis_date': analysis_result['analysis_date'],
            
            # 조직 정보
            'center_id': employee_info.get('center_id'),
            'center_name': employee_info.get('center_name'),
            'group_id': employee_info.get('group_id'),
            'group_name': employee_info.get('group_name'),
            'team_id': employee_info.get('team_id'),
            'team_name': employee_info.get('team_name'),
            'job_grade': employee_info.get('job_grade'),  # 직급 정보 추가
            
            # 시간 지표
            'work_start': analysis_result.get('work_start'),
            'work_end': analysis_result.get('work_end'),
            'total_hours': analysis_result.get('total_hours', 0),
            'actual_work_hours': analysis_result['work_time_analysis'].get('actual_work_hours', 0),
            'claimed_work_hours': analysis_result['work_time_analysis'].get('claimed_work_hours', 0),
            'efficiency_ratio': analysis_result['work_time_analysis'].get('efficiency_ratio', 0),
            
            # 기타 지표
            'confidence_score': analysis_result['work_time_analysis'].get('confidence_score', 0),
            'activity_count': len(analysis_result.get('activity_segments', [])),
            'tag_count': analysis_result.get('total_records', 0),
            
            # 근무 패턴
            'shift_type': self._determine_shift_type(analysis_result),
            'work_type': analysis_result.get('work_type', '정규')
        }
        
        # 활동별 시간 추출
        activity_times = self._extract_activity_times(analysis_result.get('activity_summary', {}))
        data.update(activity_times)
        
        # 구역별 시간 추출
        area_times = self._extract_area_times(analysis_result.get('area_summary', {}))
        data.update(area_times)
        
        # 식사 횟수 계산
        data['meal_count'] = self._count_meals(analysis_result.get('activity_summary', {}))
        
        return data
    
    def _extract_activity_times(self, activity_summary: Dict[str, float]) -> Dict[str, int]:
        """활동별 시간 추출 (분 단위)"""
        
        # 업무 관련 활동 합계
        work_minutes = (
            activity_summary.get('WORK', 0) +
            activity_summary.get('FOCUSED_WORK', 0) +
            activity_summary.get('EQUIPMENT_OPERATION', 0) +
            activity_summary.get('WORKING', 0)
        )
        
        # 회의 시간
        meeting_minutes = (
            activity_summary.get('MEETING', 0) +
            activity_summary.get('G3_MEETING', 0)
        )
        
        # 식사 시간
        breakfast_minutes = activity_summary.get('BREAKFAST', 0)
        lunch_minutes = activity_summary.get('LUNCH', 0)
        dinner_minutes = activity_summary.get('DINNER', 0)
        midnight_meal_minutes = activity_summary.get('MIDNIGHT_MEAL', 0)
        meal_minutes = breakfast_minutes + lunch_minutes + dinner_minutes + midnight_meal_minutes
        
        return {
            'work_minutes': int(work_minutes),
            'focused_work_minutes': int(activity_summary.get('FOCUSED_WORK', 0)),
            'equipment_minutes': int(activity_summary.get('EQUIPMENT_OPERATION', 0)),
            'meeting_minutes': int(meeting_minutes),
            'training_minutes': int(activity_summary.get('TRAINING', 0)),
            'meal_minutes': int(meal_minutes),
            'breakfast_minutes': int(breakfast_minutes),
            'lunch_minutes': int(lunch_minutes),
            'dinner_minutes': int(dinner_minutes),
            'midnight_meal_minutes': int(midnight_meal_minutes),
            'movement_minutes': int(activity_summary.get('MOVEMENT', 0)),
            'rest_minutes': int(activity_summary.get('REST', 0)),
            'fitness_minutes': int(activity_summary.get('FITNESS', 0)),
            'commute_in_minutes': int(activity_summary.get('COMMUTE_IN', 0)),
            'commute_out_minutes': int(activity_summary.get('COMMUTE_OUT', 0)),
            'preparation_minutes': int(activity_summary.get('WORK_PREPARATION', 0))
        }
    
    def _extract_area_times(self, area_summary: Dict[str, float]) -> Dict[str, int]:
        """구역별 시간 추출 (분 단위)"""
        return {
            'work_area_minutes': int(area_summary.get('Y', 0)),
            'non_work_area_minutes': int(area_summary.get('N', 0)),
            'gate_area_minutes': int(area_summary.get('G', 0))
        }
    
    def _count_meals(self, activity_summary: Dict[str, float]) -> int:
        """식사 횟수 계산"""
        meal_count = 0
        meal_types = ['BREAKFAST', 'LUNCH', 'DINNER', 'MIDNIGHT_MEAL']
        
        for meal in meal_types:
            if activity_summary.get(meal, 0) > 0:
                meal_count += 1
        
        return meal_count
    
    def _determine_shift_type(self, analysis_result: Dict[str, Any]) -> str:
        """근무 유형 판단"""
        # 식사 횟수 기반 판단
        meal_count = self._count_meals(analysis_result.get('activity_summary', {}))
        
        if meal_count >= 4:
            return '야간근무'
        elif meal_count >= 2:
            return '주간근무'
        else:
            # 근무 시작 시간 기반 판단
            work_start = analysis_result.get('work_start')
            if work_start:
                if isinstance(work_start, str):
                    hour = int(work_start.split(':')[0])
                else:
                    hour = work_start.hour
                
                if hour >= 18 or hour < 6:
                    return '야간근무'
                else:
                    return '주간근무'
            
            return '특수근무'
    
    def _upsert_daily_analysis(self, data: Dict[str, Any]):
        """데이터 UPSERT (INSERT or UPDATE)"""
        
        # SQLite의 UPSERT 구문 사용
        query = """
        INSERT OR REPLACE INTO daily_analysis_results (
            employee_id, analysis_date,
            center_id, center_name, group_id, group_name, team_id, team_name, job_grade,
            work_start, work_end, total_hours, actual_work_hours, 
            claimed_work_hours, efficiency_ratio,
            work_minutes, focused_work_minutes, equipment_minutes,
            meeting_minutes, training_minutes,
            meal_minutes, breakfast_minutes, lunch_minutes, 
            dinner_minutes, midnight_meal_minutes,
            movement_minutes, rest_minutes, fitness_minutes,
            commute_in_minutes, commute_out_minutes, preparation_minutes,
            work_area_minutes, non_work_area_minutes, gate_area_minutes,
            confidence_score, activity_count, meal_count, tag_count,
            shift_type, work_type,
            updated_at
        ) VALUES (
            :employee_id, :analysis_date,
            :center_id, :center_name, :group_id, :group_name, :team_id, :team_name, :job_grade,
            :work_start, :work_end, :total_hours, :actual_work_hours,
            :claimed_work_hours, :efficiency_ratio,
            :work_minutes, :focused_work_minutes, :equipment_minutes,
            :meeting_minutes, :training_minutes,
            :meal_minutes, :breakfast_minutes, :lunch_minutes,
            :dinner_minutes, :midnight_meal_minutes,
            :movement_minutes, :rest_minutes, :fitness_minutes,
            :commute_in_minutes, :commute_out_minutes, :preparation_minutes,
            :work_area_minutes, :non_work_area_minutes, :gate_area_minutes,
            :confidence_score, :activity_count, :meal_count, :tag_count,
            :shift_type, :work_type,
            CURRENT_TIMESTAMP
        )
        """
        
        # 날짜 형식 변환
        if isinstance(data['analysis_date'], date):
            data['analysis_date'] = data['analysis_date'].strftime('%Y-%m-%d')
        
        # 시간 형식 변환
        if isinstance(data['work_start'], datetime):
            data['work_start'] = data['work_start'].strftime('%Y-%m-%d %H:%M:%S')
        if isinstance(data['work_end'], datetime):
            data['work_end'] = data['work_end'].strftime('%Y-%m-%d %H:%M:%S')
        
        # 쿼리 실행
        self.db_manager.execute_query(query, data)
    
    def save_batch_results(self, results: list) -> int:
        """
        여러 분석 결과를 일괄 저장
        
        Args:
            results: 분석 결과 리스트
            
        Returns:
            int: 저장된 레코드 수
        """
        saved_count = 0
        
        for result in results:
            try:
                if self.save_individual_analysis(result):
                    saved_count += 1
            except Exception as e:
                self.logger.error(f"배치 저장 중 오류: {e}")
        
        self.logger.info(f"배치 저장 완료: {saved_count}/{len(results)} 레코드")
        return saved_count