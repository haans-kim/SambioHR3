#!/usr/bin/env python3
"""
태깅지점 마스터 데이터 업로드 스크립트
Excel 파일에서 태그 위치 마스터 데이터를 읽어 데이터베이스에 저장
"""

import pandas as pd
import os
import sys
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 프로젝트 루트 경로 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from src.database.schema import Base, TagLocationMaster
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
    
    # 기존 데이터 삭제
    with db_manager.get_session() as session:
        session.query(TagLocationMaster).delete()
        session.commit()
        print("기존 태깅지점 마스터 데이터 삭제 완료")
    
    # 새 데이터 입력
    with db_manager.get_session() as session:
        for idx, row in df.iterrows():
            # Excel의 컬럼과 DB 스키마 매핑
            tag_location = TagLocationMaster(
                정렬No=row.get('정렬No.'),
                출처파일=None,  # Excel에 없음
                위치=f"{row.get('구역', '')}/{row.get('동', '')}/{row.get('층', '')}".strip('/'),
                기기번호=str(row.get('기기번호', '')),
                게이트명=row.get('게이트명'),
                표기명=row.get('표기명'),
                입출구분=row.get('입출구분'),
                근무구역여부=row.get('공간구분_code'),  # 공간구분_code 사용
                근무=row.get('공간구분_NM'),  # 공간구분_NM 사용
                라벨링=row.get('라벨링_활동')
            )
            session.add(tag_location)
            
            if (idx + 1) % 100 == 0:
                session.commit()
                print(f"{idx + 1}개 데이터 저장 완료...")
        
        session.commit()
        print(f"총 {len(df)}개의 태깅지점 마스터 데이터 저장 완료")
    
    # 데이터 확인
    with db_manager.get_session() as session:
        count = session.query(TagLocationMaster).count()
        print(f"\n데이터베이스 확인: 총 {count}개의 태깅지점 마스터 데이터 존재")
        
        # 샘플 데이터 출력
        samples = session.query(TagLocationMaster).limit(5).all()
        print("\n샘플 데이터:")
        for sample in samples:
            print(f"- {sample.위치} / {sample.게이트명} / {sample.표기명} / {sample.근무구역여부}")

if __name__ == "__main__":
    # Excel 파일 경로
    excel_path = os.path.join(project_root, "data", "태깅지점(IG정리)_20250724_1100.xlsx")
    
    if not os.path.exists(excel_path):
        print(f"Error: 파일을 찾을 수 없습니다 - {excel_path}")
        sys.exit(1)
    
    upload_tag_location_master(excel_path)
    print("\n태깅지점 마스터 데이터 업로드 완료!")