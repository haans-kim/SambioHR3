#!/usr/bin/env python3
"""
태깅지점 마스터 데이터 업로드 스크립트 (개선 버전)
Excel 파일에서 태그 위치 마스터 데이터를 읽어 데이터베이스에 저장
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
    
    # 데이터베이스 연결
    db_manager = DatabaseManager()
    engine = db_manager.engine
    
    # 기존 테이블 삭제
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS tag_location_master"))
        conn.commit()
        print("기존 tag_location_master 테이블 삭제 완료")
    
    # 테이블 생성
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
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()
        print("tag_location_master 테이블 생성 완료")
    
    # DataFrame 준비
    df_to_upload = pd.DataFrame({
        '정렬No': df['정렬No.'],
        '출처파일': None,
        '위치': df.apply(lambda row: f"{row.get('구역', '')}/{row.get('동', '')}/{row.get('층', '')}".strip('/'), axis=1),
        '기기번호': df['기기번호'].astype(str),
        '게이트명': df['게이트명'],
        '표기명': df['표기명'],
        '입출구분': df['입출구분'],
        '근무구역여부': df['공간구분_code'],
        '근무': df['공간구분_NM'],
        '라벨링': df['라벨링_활동'],
        'created_at': datetime.now()
    })
    
    # DataFrame을 데이터베이스에 저장
    df_to_upload.to_sql('tag_location_master', engine, if_exists='append', index=False)
    print(f"총 {len(df_to_upload)}개의 태깅지점 마스터 데이터 저장 완료")
    
    # 데이터 확인
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM tag_location_master"))
        count = result.scalar()
        print(f"\n데이터베이스 확인: 총 {count}개의 태깅지점 마스터 데이터 존재")
        
        # 샘플 데이터 출력
        result = conn.execute(text("SELECT * FROM tag_location_master LIMIT 5"))
        print("\n샘플 데이터:")
        for row in result:
            print(f"- {row[3]} / {row[5]} / {row[6]} / {row[8]}")  # 위치 / 게이트명 / 표기명 / 근무구역여부

if __name__ == "__main__":
    # Excel 파일 경로
    excel_path = os.path.join(project_root, "data", "태깅지점(IG정리)_20250724_1100.xlsx")
    
    if not os.path.exists(excel_path):
        print(f"Error: 파일을 찾을 수 없습니다 - {excel_path}")
        sys.exit(1)
    
    upload_tag_location_master(excel_path)
    print("\n태깅지점 마스터 데이터 업로드 완료!")