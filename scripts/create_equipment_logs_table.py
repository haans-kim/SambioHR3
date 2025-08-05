#!/usr/bin/env python3
"""
equipment_logs 테이블 생성 스크립트
"""

import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.database import DatabaseSchema

def create_equipment_logs_table():
    """equipment_logs 테이블 생성"""
    try:
        # 데이터베이스 스키마 인스턴스 생성
        db_schema = DatabaseSchema()
        
        # 테이블 생성
        db_schema.create_tables()
        
        print("equipment_logs 테이블이 성공적으로 생성되었습니다.")
        
        # 테이블 정보 확인
        table_info = db_schema.get_table_info()
        if 'equipment_logs' in table_info:
            print("\nequipment_logs 테이블 정보:")
            print(f"컬럼 수: {table_info['equipment_logs']['column_count']}")
            print("컬럼 목록:")
            for col_name, col_type in table_info['equipment_logs']['columns']:
                print(f"  - {col_name}: {col_type}")
        
    except Exception as e:
        print(f"테이블 생성 실패: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(create_equipment_logs_table())