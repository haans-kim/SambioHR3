#!/usr/bin/env python3
"""
태깅지점 마스터 데이터 업로드 스크립트 (v3 - 신규 태그 시스템)
Excel 파일에서 태그 위치 마스터 데이터를 읽어 데이터베이스에 저장
새로운 Tag_Code 체계 적용
"""

import pandas as pd
import os
import sys
from datetime import datetime
from sqlalchemy import create_engine, text

# 프로젝트 루트 경로 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from src.database.db_manager import DatabaseManager

def upload_tag_location_master(excel_path: str):
    """
    태깅지점 마스터 데이터 업로드
    
    Args:
        excel_path: 태깅지점 Excel 파일 경로
    """
    print(f"태깅지점 마스터 데이터 업로드 시작: {excel_path}")
    
    # Excel 파일 읽기
    df = pd.read_excel(excel_path)
    print(f"총 {len(df)}개의 태깅지점 데이터 로드 완료")
    
    # 컬럼명 확인
    print("\nExcel 파일 컬럼명:", list(df.columns))
    print("\n데이터 샘플:")
    print(df.head())
    
    # 데이터베이스 연결
    db_manager = DatabaseManager()
    engine = db_manager.engine
    
    # 기존 테이블 삭제
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS tag_location_master"))
        conn.commit()
        print("\n기존 tag_location_master 테이블 삭제 완료")
    
    # 테이블 생성 (새로운 구조)
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tag_location_master (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                "정렬No" INTEGER,
                "출처파일" VARCHAR(100),
                "위치" VARCHAR(100),
                "기기번호" VARCHAR(20),
                "게이트명" VARCHAR(200),
                "표기명" VARCHAR(200),
                "입출구분" VARCHAR(10),
                "근무구역여부" VARCHAR(10),
                "근무" VARCHAR(10),
                "라벨링" VARCHAR(20),
                "Tag_Code" VARCHAR(10),
                "구역" VARCHAR(50),
                "동" VARCHAR(50),
                "층" VARCHAR(50),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()
        print("tag_location_master 테이블 생성 완료")
    
    # Tag_Code 컬럼 확인 및 생성
    if 'Tag_Code' not in df.columns:
        print("\n주의: Tag_Code 컬럼이 없습니다. 공간구분_code로 대체합니다.")
        df['Tag_Code'] = df.get('공간구분_code', 'G1')
    
    # DataFrame 준비
    df_to_upload = pd.DataFrame({
        '정렬No': df.get('정렬No.', df.get('정렬No', None)),
        '출처파일': df.get('출처파일', None),
        '위치': df.apply(lambda row: f"{row.get('구역', '')}/{row.get('동', '')}/{row.get('층', '')}".strip('/'), axis=1),
        '기기번호': df['기기번호'].astype(str) if '기기번호' in df.columns else None,
        '게이트명': df.get('게이트명', None),
        '표기명': df.get('표기명', None),
        '입출구분': df.get('입출구분', None),
        '근무구역여부': df.get('공간구분_code', None),
        '근무': df.get('공간구분_NM', None),
        '라벨링': df.get('라벨링_활동', None),
        'Tag_Code': df['Tag_Code'],
        '구역': df.get('구역', None),
        '동': df.get('동', None),
        '층': df.get('층', None),
        'created_at': datetime.now()
    })
    
    # Null 값 처리
    df_to_upload = df_to_upload.fillna('')
    
    # Tag_Code 통계 출력
    print("\nTag_Code 분포:")
    tag_code_counts = df_to_upload['Tag_Code'].value_counts()
    for code, count in tag_code_counts.items():
        print(f"  {code}: {count}개")
    
    # 출입문 태그 확인
    entrance_tags = df_to_upload[df_to_upload['Tag_Code'].isin(['T2', 'T3'])]
    print(f"\n출입문 태그 수: T2(입문) {len(entrance_tags[entrance_tags['Tag_Code'] == 'T2'])}개, T3(출문) {len(entrance_tags[entrance_tags['Tag_Code'] == 'T3'])}개")
    if len(entrance_tags) > 0:
        print("출입문 샘플:")
        print(entrance_tags[['표기명', 'Tag_Code', '입출구분']].head())
    
    # DataFrame을 데이터베이스에 저장
    df_to_upload.to_sql('tag_location_master', engine, if_exists='append', index=False)
    print(f"\n총 {len(df_to_upload)}개의 태깅지점 마스터 데이터 저장 완료")
    
    # 데이터 확인
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM tag_location_master"))
        count = result.scalar()
        print(f"\n데이터베이스 확인: 총 {count}개의 태깅지점 마스터 데이터 존재")
        
        # Tag_Code별 집계
        result = conn.execute(text("""
            SELECT Tag_Code, COUNT(*) as cnt 
            FROM tag_location_master 
            GROUP BY Tag_Code 
            ORDER BY Tag_Code
        """))
        print("\n데이터베이스 Tag_Code 분포:")
        for row in result:
            print(f"  {row[0]}: {row[1]}개")
        
        # 출입문 샘플 데이터 출력
        result = conn.execute(text("""
            SELECT 표기명, Tag_Code, 입출구분, 게이트명 
            FROM tag_location_master 
            WHERE Tag_Code IN ('T2', 'T3') 
            LIMIT 10
        """))
        print("\n출입문 샘플 데이터:")
        for row in result:
            print(f"  {row[0]} / {row[1]} / {row[2]} / {row[3]}")

if __name__ == "__main__":
    # Excel 파일 찾기
    data_dir = os.path.join(project_root, "data")
    
    # 가능한 파일명들
    possible_files = [
        "태깅지점(IG정리)_20250724_1100.xlsx",
        "태깅지점.xlsx",
        "tag_location_master.xlsx",
        "tag_data_24.6.xlsx"
    ]
    
    excel_path = None
    for filename in possible_files:
        path = os.path.join(data_dir, filename)
        if os.path.exists(path):
            excel_path = path
            break
    
    if not excel_path:
        print("Error: 태깅지점 마스터 파일을 찾을 수 없습니다.")
        print(f"다음 위치에서 찾았습니다: {data_dir}")
        print(f"찾은 파일들: {os.listdir(data_dir)}")
        sys.exit(1)
    
    upload_tag_location_master(excel_path)
    print("\n태깅지점 마스터 데이터 업로드 완료!")