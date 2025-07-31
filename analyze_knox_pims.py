import pandas as pd
import os

# 파일 경로
file_path = '/Users/hanskim/Projects/SambioHR2/data/Knox_PIMS_2025.06.xlsx'

# 파일 존재 확인
if not os.path.exists(file_path):
    print(f"파일을 찾을 수 없습니다: {file_path}")
    exit(1)

print(f"파일 크기: {os.path.getsize(file_path) / 1024 / 1024:.2f} MB")

# Excel 파일 읽기
print("\nExcel 파일을 읽는 중...")
df = pd.read_excel(file_path)

print(f"\n=== 데이터 크기 ===")
print(f"행 수: {len(df):,}")
print(f"컬럼 수: {len(df.columns)}")

print("\n=== 전체 컬럼명 ===")
for i, col in enumerate(df.columns):
    print(f"{i:2d}: {col}")

# 시간 관련 컬럼 찾기
print("\n=== 시간 관련 컬럼 (추정) ===")
time_keywords = ['시간', '일시', 'time', 'date', 'GMT', '시작', '종료', 'start', 'end', '일자']
time_columns = []

for col in df.columns:
    col_lower = col.lower()
    if any(keyword.lower() in col_lower for keyword in time_keywords):
        time_columns.append(col)
        print(f"- {col}")

# 시간 관련 컬럼의 데이터 타입과 샘플 확인
print("\n=== 시간 관련 컬럼 데이터 샘플 ===")
for col in time_columns:
    print(f"\n[{col}]")
    print(f"데이터 타입: {df[col].dtype}")
    print(f"null 값 개수: {df[col].isnull().sum()}")
    print("샘플 데이터 (상위 5개):")
    for idx, val in enumerate(df[col].head(5)):
        print(f"  {idx}: {val}")
    
# GMT+9 관련 컬럼 특별 확인
print("\n=== GMT+9 관련 컬럼 확인 ===")
gmt_columns = [col for col in df.columns if 'GMT' in col.upper()]
if gmt_columns:
    for col in gmt_columns:
        print(f"\n[{col}]")
        print("샘플 데이터 (상위 10개):")
        for idx, val in enumerate(df[col].head(10)):
            print(f"  {idx}: {val}")
else:
    print("GMT가 포함된 컬럼명을 찾을 수 없습니다.")

# 데이터 타입별 컬럼 분류
print("\n=== 데이터 타입별 컬럼 분류 ===")
dtype_groups = df.dtypes.groupby(df.dtypes).groups
for dtype, columns in dtype_groups.items():
    print(f"\n{dtype} 타입: {len(columns)}개")
    if 'datetime' in str(dtype) or 'date' in str(dtype):
        print("컬럼 목록:")
        for col in columns:
            print(f"  - {col}")