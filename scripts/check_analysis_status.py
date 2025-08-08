#!/usr/bin/env python3
"""
배치 분석 진행 상태 확인 스크립트
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
from tabulate import tabulate

# DB 경로
project_root = Path(__file__).parent.parent
analytics_db = project_root / 'data' / 'sambio_analytics.db'
source_db = project_root / 'data' / 'sambio.db'

def check_status():
    """분석 상태 확인"""
    
    if not analytics_db.exists():
        print("❌ 분석 DB가 존재하지 않습니다. 배치 분석을 먼저 실행하세요.")
        return
    
    conn = sqlite3.connect(analytics_db)
    
    # 1. 전체 통계
    print("\n" + "="*60)
    print("📊 전체 분석 통계")
    print("="*60)
    
    total_records = pd.read_sql_query("""
        SELECT 
            COUNT(*) as total_records,
            COUNT(DISTINCT employee_id) as unique_employees,
            COUNT(DISTINCT analysis_date) as unique_dates,
            MIN(analysis_date) as first_date,
            MAX(analysis_date) as last_date,
            AVG(processing_time_ms) as avg_processing_ms
        FROM daily_analysis
    """, conn)
    
    if not total_records.empty:
        row = total_records.iloc[0]
        print(f"📌 총 분석 레코드: {row['total_records']:,}개")
        print(f"👥 분석된 직원 수: {row['unique_employees']:,}명")
        print(f"📅 분석된 날짜 수: {row['unique_dates']}일")
        print(f"📆 기간: {row['first_date']} ~ {row['last_date']}")
        print(f"⏱️  평균 처리 시간: {row['avg_processing_ms']:.0f}ms")
    
    # 2. 날짜별 진행률
    print("\n" + "="*60)
    print("📅 날짜별 분석 현황")
    print("="*60)
    
    daily_status = pd.read_sql_query("""
        SELECT 
            analysis_date,
            COUNT(DISTINCT employee_id) as analyzed_employees,
            AVG(efficiency_ratio) as avg_efficiency,
            AVG(work_hours) as avg_work_hours,
            SUM(CASE WHEN claim_hours > 0 THEN 1 ELSE 0 END) as with_claim
        FROM daily_analysis
        GROUP BY analysis_date
        ORDER BY analysis_date DESC
        LIMIT 10
    """, conn)
    
    if not daily_status.empty:
        print(tabulate(daily_status, headers='keys', tablefmt='grid', floatfmt='.1f'))
    
    # 3. 조직별 현황
    print("\n" + "="*60)
    print("🏢 조직별 분석 현황")
    print("="*60)
    
    org_status = pd.read_sql_query("""
        SELECT 
            center_name,
            COUNT(DISTINCT team_id) as teams,
            COUNT(DISTINCT employee_id) as employees,
            COUNT(*) as total_records,
            AVG(efficiency_ratio) as avg_efficiency
        FROM daily_analysis
        WHERE center_name IS NOT NULL
        GROUP BY center_name
        ORDER BY employees DESC
    """, conn)
    
    if not org_status.empty:
        print(tabulate(org_status, headers='keys', tablefmt='grid', floatfmt='.1f'))
    
    # 4. 처리 로그
    print("\n" + "="*60)
    print("📋 최근 처리 로그")
    print("="*60)
    
    process_log = pd.read_sql_query("""
        SELECT 
            batch_id,
            start_time,
            end_time,
            total_items,
            processed_items,
            failed_items,
            status
        FROM processing_log
        ORDER BY start_time DESC
        LIMIT 5
    """, conn)
    
    if not process_log.empty:
        print(tabulate(process_log, headers='keys', tablefmt='grid'))
    
    # 5. 미처리 데이터 확인
    print("\n" + "="*60)
    print("⚠️  미처리 데이터 확인")
    print("="*60)
    
    # 원본 DB에서 예상 데이터 수 확인
    if source_db.exists():
        source_conn = sqlite3.connect(source_db)
        
        expected = pd.read_sql_query("""
            SELECT 
                COUNT(DISTINCT employee_id) as total_employees
            FROM employees
        """, source_conn)
        
        claim_dates = pd.read_sql_query("""
            SELECT 
                COUNT(DISTINCT work_date) as claim_dates,
                MIN(work_date) as first_claim,
                MAX(work_date) as last_claim
            FROM employee_claims
            WHERE total_hours > 0
        """, source_conn)
        
        if not expected.empty and not claim_dates.empty:
            total_emp = expected.iloc[0]['total_employees']
            claim_days = claim_dates.iloc[0]['claim_dates']
            expected_records = total_emp * claim_days
            
            actual_records = row['total_records'] if not total_records.empty else 0
            completion_rate = (actual_records / expected_records * 100) if expected_records > 0 else 0
            
            print(f"🎯 예상 레코드 수: {expected_records:,}개")
            print(f"   (직원 {total_emp:,}명 × Claim 날짜 {claim_days}일)")
            print(f"✅ 실제 처리된 수: {actual_records:,}개")
            print(f"📊 완료율: {completion_rate:.1f}%")
            
            if completion_rate < 100:
                remaining = expected_records - actual_records
                print(f"⏳ 남은 작업: {remaining:,}개")
                
                # 8코어 기준 예상 시간
                estimated_hours = remaining / (8 * 3600)  # 1초/건, 8코어
                print(f"⏱️  예상 소요 시간: {estimated_hours:.1f}시간 (8코어 기준)")
        
        source_conn.close()
    
    # 6. 데이터 품질 체크
    print("\n" + "="*60)
    print("✅ 데이터 품질 체크")
    print("="*60)
    
    quality_check = pd.read_sql_query("""
        SELECT 
            COUNT(CASE WHEN efficiency_ratio < 0 OR efficiency_ratio > 100 THEN 1 END) as invalid_efficiency,
            COUNT(CASE WHEN work_hours < 0 OR work_hours > 24 THEN 1 END) as invalid_hours,
            COUNT(CASE WHEN employee_name IS NULL THEN 1 END) as missing_names,
            COUNT(CASE WHEN center_name IS NULL THEN 1 END) as missing_center
        FROM daily_analysis
    """, conn)
    
    if not quality_check.empty:
        row = quality_check.iloc[0]
        issues = []
        if row['invalid_efficiency'] > 0:
            issues.append(f"❌ 잘못된 효율성 값: {row['invalid_efficiency']}개")
        if row['invalid_hours'] > 0:
            issues.append(f"❌ 잘못된 시간 값: {row['invalid_hours']}개")
        if row['missing_names'] > 0:
            issues.append(f"⚠️  이름 누락: {row['missing_names']}개")
        if row['missing_center'] > 0:
            issues.append(f"⚠️  센터 정보 누락: {row['missing_center']}개")
        
        if issues:
            for issue in issues:
                print(issue)
        else:
            print("✅ 데이터 품질 이상 없음")
    
    conn.close()
    
    print("\n" + "="*60)
    print("분석 상태 확인 완료")
    print("="*60)


if __name__ == "__main__":
    check_status()