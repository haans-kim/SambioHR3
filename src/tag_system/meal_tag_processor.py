"""
식사 데이터를 기반으로 M1, M2 태그 생성
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd
from sqlalchemy import text

logger = logging.getLogger(__name__)

class MealTagProcessor:
    """식사 데이터에서 M1, M2 태그 추출"""
    
    def __init__(self, engine=None):
        self.engine = engine
        
        # 테이크아웃 키워드
        self.takeout_keywords = ['테이크아웃', 'take out', 'takeout', 'to go']
        
    def extract_meal_tags(self, employee_id: str, date: datetime) -> List[Dict]:
        """식사 데이터에서 M1, M2 태그 추출"""
        if not self.engine:
            logger.error("데이터베이스 엔진이 없습니다.")
            return []
        
        try:
            # 식사 데이터 조회
            query = text("""
                SELECT 
                    사번,
                    취식일시,
                    배식구,
                    식당명,
                    테이크아웃,
                    식사구분명
                FROM meal_data
                WHERE 사번 = :employee_id
                AND DATE(취식일시) = DATE(:date)
                ORDER BY 취식일시
            """)
            
            with self.engine.connect() as conn:
                result = conn.execute(query, {
                    'employee_id': employee_id,
                    'date': date
                })
                
                meal_tags = []
                for row in result:
                    # 테이크아웃 여부 판단
                    is_takeout = self._is_takeout(
                        row.배식구, 
                        row.테이크아웃,
                        row.식당명
                    )
                    
                    # 태그 생성
                    tag = {
                        'employee_id': row.사번,
                        'timestamp': pd.to_datetime(row.취식일시),
                        'tag_code': 'M2' if is_takeout else 'M1',
                        'source': 'meal_data',
                        'meal_info': {
                            '배식구': row.배식구,
                            '식당명': row.식당명,
                            '식사구분': row.식사구분명,
                            'is_takeout': is_takeout
                        },
                        'duration_minutes': 10 if is_takeout else 30,  # 테이크아웃은 짧은 시간
                        'confidence': 1.0
                    }
                    
                    meal_tags.append(tag)
                
                logger.info(f"{employee_id}의 {date.date()}에 대해 {len(meal_tags)}개 식사 태그 추출 "
                          f"(M1: {sum(1 for t in meal_tags if t['tag_code'] == 'M1')}개, "
                          f"M2: {sum(1 for t in meal_tags if t['tag_code'] == 'M2')}개)")
                
                return meal_tags
                
        except Exception as e:
            logger.error(f"식사 데이터에서 태그 추출 중 오류: {e}")
            return []
    
    def _is_takeout(self, 배식구: str, 테이크아웃: str, 식당명: str) -> bool:
        """테이크아웃 여부 판단"""
        # 1. 테이크아웃 필드 확인
        if 테이크아웃 and str(테이크아웃).lower() in ['y', 'yes', '1', 'true']:
            return True
        
        # 2. 배식구에 테이크아웃 키워드 확인
        if 배식구:
            for keyword in self.takeout_keywords:
                if keyword in 배식구.lower():
                    return True
        
        # 3. 식당명에 테이크아웃 키워드 확인
        if 식당명:
            for keyword in self.takeout_keywords:
                if keyword in 식당명.lower():
                    return True
        
        return False
    
    def get_meal_statistics(self, employee_id: str, start_date: datetime, 
                          end_date: datetime) -> Dict:
        """식사 통계 조회"""
        if not self.engine:
            return {}
        
        try:
            query = text("""
                SELECT 
                    배식구,
                    COUNT(*) as count,
                    AVG(CASE WHEN 테이크아웃 = 'Y' THEN 1 ELSE 0 END) as takeout_ratio
                FROM meal_data
                WHERE 사번 = :employee_id
                AND DATE(취식일시) BETWEEN DATE(:start_date) AND DATE(:end_date)
                GROUP BY 배식구
                ORDER BY count DESC
            """)
            
            with self.engine.connect() as conn:
                result = conn.execute(query, {
                    'employee_id': employee_id,
                    'start_date': start_date,
                    'end_date': end_date
                })
                
                stats = {
                    'total_meals': 0,
                    'takeout_meals': 0,
                    'dine_in_meals': 0,
                    'favorite_places': []
                }
                
                for row in result:
                    stats['total_meals'] += row.count
                    if row.takeout_ratio > 0.5:
                        stats['takeout_meals'] += row.count
                    else:
                        stats['dine_in_meals'] += row.count
                    
                    stats['favorite_places'].append({
                        'place': row.배식구,
                        'count': row.count,
                        'takeout_ratio': float(row.takeout_ratio)
                    })
                
                return stats
                
        except Exception as e:
            logger.error(f"식사 통계 조회 중 오류: {e}")
            return {}
    
    def merge_meal_tags_with_sequence(self, tag_sequence: List[Dict], 
                                    meal_tags: List[Dict]) -> List[Dict]:
        """식사 태그를 태그 시퀀스에 병합"""
        if not meal_tags:
            return tag_sequence
        
        # 모든 태그 합치고 시간순 정렬
        all_tags = tag_sequence + meal_tags
        all_tags.sort(key=lambda x: x['timestamp'])
        
        # 중복 제거 및 병합
        merged = []
        prev_time = None
        
        for tag in all_tags:
            # 같은 시간에 여러 태그가 있는 경우 우선순위
            # M1, M2 > O > 기타 태그
            if prev_time and abs((tag['timestamp'] - prev_time).total_seconds()) < 60:
                # 1분 이내 태그는 우선순위에 따라 선택
                if tag['tag_code'] in ['M1', 'M2']:
                    # 식사 태그 우선
                    if merged[-1]['tag_code'] not in ['M1', 'M2', 'O']:
                        merged[-1] = tag
                elif tag['tag_code'] == 'O':
                    # O 태그는 식사 태그보다 낮은 우선순위
                    if merged[-1]['tag_code'] not in ['M1', 'M2']:
                        merged[-1] = tag
            else:
                merged.append(tag)
                prev_time = tag['timestamp']
        
        return merged