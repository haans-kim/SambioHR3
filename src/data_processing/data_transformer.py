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
        
        # 5. 입문/출문 매칭 및 체류시간 계산 (대용량 데이터에서는 선택적)
        if len(processed_df) < 100000:  # 10만 건 미만일 때만 체류시간 계산
            processed_df = self._calculate_stay_duration(processed_df)
        else:
            self.logger.info(f"대용량 데이터({len(processed_df):,}행)로 체류시간 계산 생략")
            processed_df['stay_duration'] = None
        
        # 6. 근무구역/비근무구역 분류
        processed_df = self._classify_work_areas(processed_df)
        
        self.logger.info(f"태깅 데이터 전처리 완료: {len(processed_df):,}행")
        
        return processed_df
    
    def _sort_chronologically(self, df: pd.DataFrame) -> pd.DataFrame:
        """시계열 정렬"""
        self.logger.info("시계열 정렬 수행")
        
        # 원본 데이터 샘플 로깅
        self.logger.info(f"날짜 샘플: {df['ENTE_DT'].head()}")
        self.logger.info(f"시간 샘플: {df['출입시각'].head()}")
        
        # 날짜와 시간 결합 - 다양한 시간 형식 시도
        # 시간이 HHMM 형식이 아닐 수 있으므로 여러 형식 시도
        df['datetime'] = pd.to_datetime(df['ENTE_DT'].astype(str) + ' ' + df['출입시각'].astype(str).str.zfill(6), 
                                       format='%Y%m%d %H%M%S', errors='coerce')
        
        # 첫 번째 시도가 실패하면 다른 형식 시도
        if df['datetime'].isnull().all():
            df['datetime'] = pd.to_datetime(df['ENTE_DT'].astype(str) + ' ' + df['출입시각'].astype(str).str.zfill(4), 
                                           format='%Y%m%d %H%M', errors='coerce')
        
        # 시간 변환에 실패한 행 처리
        invalid_time_mask = df['datetime'].isnull()
        if invalid_time_mask.any():
            self.logger.warning(f"잘못된 시간 형식 {invalid_time_mask.sum()}건 발견")
            # 실패한 샘플 데이터 로깅
            failed_samples = df[invalid_time_mask].head()
            self.logger.warning(f"실패 샘플:\n{failed_samples[['ENTE_DT', '출입시각']]}")
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
        """입문/출문 매칭 및 체류시간 계산 (최적화된 버전)"""
        self.logger.info("체류시간 계산 시작")
        
        # 체류시간 컬럼 초기화
        df['stay_duration'] = None
        
        # 전체 사번 수 확인
        unique_employees = df['사번'].unique()
        total_employees = len(unique_employees)
        self.logger.info(f"처리할 사번 수: {total_employees:,}명")
        
        # 진행상황 표시를 위한 카운터
        processed_employees = 0
        
        # 배치 처리로 성능 개선
        batch_size = 100  # 한 번에 처리할 사번 수
        
        for i in range(0, total_employees, batch_size):
            batch_employees = unique_employees[i:i+batch_size]
            
            for emp_id in batch_employees:
                emp_mask = df['사번'] == emp_id
                emp_data = df[emp_mask]
                
                # 입문과 출문 분리
                entry_indices = emp_data[emp_data['INOUT_GB'] == '입문'].index
                
                for idx in entry_indices:
                    entry_time = df.loc[idx, 'datetime']
                    
                    # 같은 사번의 다음 출문 찾기
                    next_exit_mask = (
                        (df['사번'] == emp_id) & 
                        (df['INOUT_GB'] == '출문') & 
                        (df['datetime'] > entry_time)
                    )
                    
                    next_exits = df[next_exit_mask]
                    
                    if not next_exits.empty:
                        next_exit = next_exits.iloc[0]
                        duration = (next_exit['datetime'] - entry_time).total_seconds() / 3600
                        df.loc[idx, 'stay_duration'] = duration
            
            processed_employees += len(batch_employees)
            if processed_employees % 1000 == 0:
                self.logger.info(f"체류시간 계산 진행: {processed_employees:,}/{total_employees:,} 사번 ({processed_employees/total_employees*100:.1f}%)")
        
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
    
    def process_organization_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """조직현황 데이터 처리"""
        self.logger.info("조직현황 데이터 처리 시작")
        
        processed_df = df.copy()
        
        # 컬럼명 정리 (공백 제거)
        processed_df.columns = processed_df.columns.str.strip()
        
        # 필수 컬럼 확인
        required_columns = ['사번', '성명', '부서명', '센터', 'BU', '팀', '그룹', '파트']
        existing_columns = [col for col in required_columns if col in processed_df.columns]
        
        if not existing_columns:
            self.logger.warning("조직현황 데이터에 필수 컬럼이 없습니다.")
            return processed_df
        
        # 재직상태가 '재직'인 직원만 필터링 (재직상태 컬럼이 있는 경우)
        if '재직상태' in processed_df.columns:
            processed_df = processed_df[processed_df['재직상태'] == '재직'].copy()
        
        # 날짜 형식 변환
        date_columns = ['그룹입사일', '당사입사일']
        for col in date_columns:
            if col in processed_df.columns:
                processed_df[col] = pd.to_datetime(processed_df[col], format='%Y%m%d', errors='coerce')
        
        # 입사년도 숫자로 변환
        if '입사년도' in processed_df.columns:
            processed_df['입사년도'] = processed_df['입사년도'].str.extract(r'(\d{4})').astype(float)
        
        # 조직 계층 구조 생성 (센터 > BU > 팀 > 그룹 > 파트)
        org_hierarchy_cols = ['센터', 'BU', '팀', '그룹', '파트']
        existing_hierarchy = [col for col in org_hierarchy_cols if col in processed_df.columns]
        
        if existing_hierarchy:
            # 조직 전체 경로 생성
            processed_df['조직경로'] = processed_df[existing_hierarchy].apply(
                lambda x: ' > '.join([str(val) for val in x if pd.notna(val) and str(val) != '-']), 
                axis=1
            )
        
        # 직급 정보 정리
        if '직급명' in processed_df.columns:
            processed_df['직급명'] = processed_df['직급명'].str.strip()
        
        # 데이터베이스 컬럼명으로 매핑
        column_mapping = {
            '사번': 'employee_no',
            '성명': 'name',
            '성별': 'gender',
            '입사년도': 'hire_year',
            '국적': 'nationality',
            '직급명': 'position_name',
            '직급2*': 'position_level',
            '입사경위1': 'hire_type',
            '그룹입사일': 'group_hire_date',
            '당사입사일': 'company_hire_date',
            '부서코드': 'dept_code',
            '부서명': 'dept_name',
            '센터': 'center',
            'BU': 'bu',
            '팀': 'team',
            '그룹': 'group_name',
            '파트': 'part',
            '재직상태': 'employment_status',
            '인력유형': 'employment_type',
            '직책명': 'job_title',
            '직무': 'job_role',
            '녹스메일': 'email',
            '조직경로': 'org_path'
        }
        
        # 매핑 적용
        processed_df = processed_df.rename(columns=column_mapping)
        
        # 필요한 컬럼만 선택 (매핑된 컬럼 중에서)
        available_columns = [col for col in column_mapping.values() if col in processed_df.columns]
        processed_df = processed_df[available_columns]
        
        self.logger.info(f"조직현황 데이터 처리 완료: {len(processed_df):,}행")
        
        return processed_df
    
    def process_meal_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        식사 데이터 전처리
        
        Args:
            df: 원본 식사 데이터
            
        Returns:
            DataFrame: 전처리된 식사 데이터
        """
        self.logger.info("식사 데이터 전처리 시작")
        
        # 데이터 복사
        processed_df = df.copy()
        
        # 1. 컬럼명 정리 및 표준화
        column_mapping = {
            '사번': 'employee_id',
            'Knox ID': 'knox_id',
            '성명': 'employee_name',
            '취식일시': 'meal_datetime',
            '식당명': 'restaurant_name',
            '식사가격': 'meal_price',
            '식사대분류': 'meal_category',
            '식사구분명': 'meal_type_detail',
            '부서': 'department',
            '부서코드': 'department_code',
            '테이크아웃': 'is_takeout',
            '배식구': 'serving_counter',
            '식단': 'menu_detail',
            '결제날짜': 'payment_date',
            '카드번호': 'card_number',
            '기기번호': 'device_number'
        }
        
        # 존재하는 컬럼만 매핑
        existing_columns = {k: v for k, v in column_mapping.items() if k in processed_df.columns}
        processed_df = processed_df.rename(columns=existing_columns)
        
        # 2. 날짜/시간 형식 변환
        if 'meal_datetime' in processed_df.columns:
            processed_df['meal_datetime'] = pd.to_datetime(processed_df['meal_datetime'])
            processed_df['meal_date'] = processed_df['meal_datetime'].dt.date
            processed_df['meal_time'] = processed_df['meal_datetime'].dt.time
            processed_df['meal_hour'] = processed_df['meal_datetime'].dt.hour
        
        # 3. 건물/위치 정보 추출 (식당명에서)
        if 'restaurant_name' in processed_df.columns:
            # 식당명에서 건물 정보 추출
            processed_df['building'] = processed_df['restaurant_name'].apply(self._extract_building_from_restaurant)
            processed_df['cafeteria_location'] = 'CAFETERIA'  # 모든 식사 데이터는 CAFETERIA 태그
        
        # 4. 식사 시간대 검증 및 분류
        if 'meal_category' in processed_df.columns and 'meal_hour' in processed_df.columns:
            processed_df['is_valid_meal_time'] = processed_df.apply(self._validate_meal_time, axis=1)
        
        # 5. 교대 근무 정보 추가
        if 'meal_hour' in processed_df.columns:
            processed_df['shift_type'] = processed_df['meal_hour'].apply(
                lambda h: 'NIGHT' if (h >= 20 or h < 8) else 'DAY'
            )
        
        # 6. 테이크아웃 플래그 변환
        if 'is_takeout' in processed_df.columns:
            processed_df['is_takeout'] = processed_df['is_takeout'].map({'Y': True, 'N': False})
        
        # 7. 중복 제거 (동일 시간대 중복 식사 기록)
        if 'employee_id' in processed_df.columns and 'meal_datetime' in processed_df.columns:
            processed_df = processed_df.drop_duplicates(subset=['employee_id', 'meal_datetime'])
        
        self.logger.info(f"식사 데이터 전처리 완료: {len(processed_df):,}행")
        
        return processed_df
    
    def _extract_building_from_restaurant(self, restaurant_name: str) -> str:
        """식당명에서 건물 정보 추출"""
        if pd.isna(restaurant_name):
            return None
            
        restaurant_mapping = {
            'SBL 2단지 임시 식당': 'P5',  # 임시식당을 P5로 매핑
            'SBL 바이오프라자2 식당': 'BP',
            'SBL 바이오프라자2 푸드코트': 'BP',
            '삼성바이오로직스 커뮤니티동 투썸플레이스': 'COMMUNITY'
        }
        
        return restaurant_mapping.get(restaurant_name, 'UNKNOWN')
    
    def _validate_meal_time(self, row) -> bool:
        """식사 시간대 유효성 검증"""
        meal_hour = row.get('meal_hour', -1)
        meal_category = row.get('meal_category', '')
        
        valid_times = {
            '조식': (6, 9),
            '중식': (11, 14),
            '석식': (17, 20),
            '야식': (23, 25),  # 자정 넘어가는 경우 고려
            '간식': (7, 8)
        }
        
        if meal_category in valid_times:
            start, end = valid_times[meal_category]
            if end > 24:  # 자정 넘어가는 경우
                return meal_hour >= start or meal_hour < (end - 24)
            else:
                return start <= meal_hour < end
        
        return True
    
    def merge_meal_with_tag_data(self, tag_df: pd.DataFrame, meal_df: pd.DataFrame) -> pd.DataFrame:
        """
        식사 데이터를 태그 데이터와 병합
        
        Args:
            tag_df: 태그 데이터
            meal_df: 식사 데이터
            
        Returns:
            DataFrame: 병합된 데이터
        """
        self.logger.info("식사 데이터와 태그 데이터 병합 시작")
        
        # 태그 데이터에 meal_type 컬럼이 없으면 추가
        if 'meal_type' not in tag_df.columns:
            tag_df['meal_type'] = None
        
        # 태그 데이터에 is_meal 플래그 추가
        if 'is_meal' not in tag_df.columns:
            tag_df['is_meal'] = False
        
        # 식사 데이터를 태그 형식으로 변환
        meal_as_tags = pd.DataFrame()
        
        if not meal_df.empty and 'employee_id' in meal_df.columns and 'meal_datetime' in meal_df.columns:
            # 필요한 컬럼 매핑
            meal_as_tags['사번'] = meal_df['employee_id']
            meal_as_tags['datetime'] = meal_df['meal_datetime']
            meal_as_tags['DR_NO'] = meal_df.get('building', 'CAFETERIA')
            meal_as_tags['DR_NM'] = meal_df.get('restaurant_name', 'CAFETERIA')
            meal_as_tags['INOUT_GB'] = 'I'  # 식당 입장으로 처리
            meal_as_tags['meal_type'] = meal_df.get('meal_category', None)
            meal_as_tags['is_meal'] = True
            meal_as_tags['work_area'] = 'N'  # 식당은 비근무구역
            
            # 태그 데이터에 없는 추가 정보
            meal_as_tags['meal_price'] = meal_df.get('meal_price', None)
            meal_as_tags['is_takeout'] = meal_df.get('is_takeout', False)
            meal_as_tags['menu_detail'] = meal_df.get('menu_detail', None)
            
            # 날짜와 시간 분리 (태그 데이터 형식에 맞춤)
            meal_as_tags['ENTE_DT'] = meal_as_tags['datetime'].dt.strftime('%Y%m%d')
            meal_as_tags['출입시각'] = meal_as_tags['datetime'].dt.strftime('%H%M%S')
            
            # 태그 데이터와 동일한 컬럼 구조로 맞춤
            for col in tag_df.columns:
                if col not in meal_as_tags.columns:
                    meal_as_tags[col] = None
            
            # 두 데이터프레임 병합
            merged_df = pd.concat([tag_df, meal_as_tags], ignore_index=True)
            
            # 시간순 정렬
            if 'datetime' in merged_df.columns:
                merged_df = merged_df.sort_values(['사번', 'datetime'])
            
            self.logger.info(f"병합 완료: 태그 {len(tag_df):,}행 + 식사 {len(meal_as_tags):,}행 = 총 {len(merged_df):,}행")
        else:
            merged_df = tag_df
            self.logger.warning("식사 데이터가 비어있거나 필수 컬럼이 없어 병합하지 않음")
        
        return merged_df
    
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