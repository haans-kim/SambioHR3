#!/usr/bin/env python3
"""
잘못 계산된 데이터 정리
효율성이 200% 이상이거나 근무시간이 15시간 이상인 데이터 삭제
"""

import sqlite3
from pathlib import Path

def cleanup_bad_data():
    """잘못된 분석 데이터 정리"""
    
    db_path = Path(__file__).parent / 'data' / 'sambio_human.db'
    
    if not db_path.exists():
        print(f"❌ DB 파일을 찾을 수 없습니다: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 잘못된 데이터 확인
        check_query = """
        SELECT COUNT(*) as bad_count
        FROM daily_analysis_results
        WHERE efficiency_ratio > 200 
           OR total_hours > 15
           OR actual_work_hours > 15
        """
        
        result = cursor.execute(check_query).fetchone()
        bad_count = result[0] if result else 0
        
        print(f"잘못된 데이터: {bad_count}건")
        
        if bad_count > 0:
            # 잘못된 데이터 삭제
            delete_query = """
            DELETE FROM daily_analysis_results
            WHERE efficiency_ratio > 200 
               OR total_hours > 15
               OR actual_work_hours > 15
            """
            
            cursor.execute(delete_query)
            conn.commit()
            
            print(f"✅ {bad_count}건의 잘못된 데이터를 삭제했습니다.")
        else:
            print("✅ 잘못된 데이터가 없습니다.")
        
        # 정상 데이터 확인
        stats_query = """
        SELECT 
            COUNT(*) as total_count,
            AVG(efficiency_ratio) as avg_efficiency,
            AVG(total_hours) as avg_hours,
            MIN(efficiency_ratio) as min_efficiency,
            MAX(efficiency_ratio) as max_efficiency,
            MIN(total_hours) as min_hours,
            MAX(total_hours) as max_hours
        FROM daily_analysis_results
        """
        
        stats = cursor.execute(stats_query).fetchone()
        
        if stats and stats[0] > 0:
            print("\n현재 데이터 통계:")
            print(f"  - 총 레코드: {stats[0]}건")
            print(f"  - 평균 효율성: {stats[1]:.1f}%")
            print(f"  - 평균 근무시간: {stats[2]:.1f}시간")
            print(f"  - 효율성 범위: {stats[3]:.1f}% ~ {stats[4]:.1f}%")
            print(f"  - 근무시간 범위: {stats[5]:.1f}시간 ~ {stats[6]:.1f}시간")
    
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        conn.rollback()
    
    finally:
        conn.close()
    
    print("\n✅ 데이터 정리 완료")


if __name__ == "__main__":
    cleanup_bad_data()