#!/usr/bin/env python3
"""
Claim 데이터 확인 스크립트
"""

import pandas as pd
import sqlite3
from pathlib import Path

# 경로 설정
project_root = Path(__file__).parent.parent
excel_path = project_root / 'data' / 'data_근무시간(claim)_전사_2506.xlsx'
db_path = project_root / 'data' / 'sambio.db'

# Excel 파일 직접 확인
df = pd.read_excel(excel_path)
print(f'Excel 파일 원본: {len(df):,}행')
print(f'컬럼: {df.columns.tolist()}')
print(f'\n근무시간 컬럼 샘플:')
print(df['근무시간'].head(10))

# DB 확인
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM employee_claims')
db_count = cursor.fetchone()[0]
print(f'\nDB에 저장된 건수: {db_count:,}건')

# 0시간 필터링 확인
zero_hours = (df['근무시간'] == '00:00').sum()
non_zero = len(df) - zero_hours
print(f'\n근무시간이 00:00인 행: {zero_hours:,}개')
print(f'근무시간이 00:00이 아닌 행: {non_zero:,}개')

# 데이터 타입 확인
print(f'\n근무시간 컬럼 데이터 타입: {df["근무시간"].dtype}')
print(f'유니크한 근무시간 값 개수: {df["근무시간"].nunique()}')

# 근무시간 분포
print('\n근무시간 분포 (상위 10개):')
print(df['근무시간'].value_counts().head(10))

conn.close()