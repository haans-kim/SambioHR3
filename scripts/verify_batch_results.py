#!/usr/bin/env python3
"""
배치 분석 결과 검증 스크립트
데이터 품질, 일관성, 완전성 검증
"""

import sqlite3
from pathlib import Path
import pandas as pd
from datetime import datetime
import sys

# DB 경로
project_root = Path(__file__).parent.parent
analytics_db = project_root / 'data' / 'sambio_analytics.db'
source_db = project_root / 'data' / 'sambio.db'

class BatchResultVerifier:
    """배치 결과 검증 클래스"""
    
    def __init__(self):
        self.analytics_conn = sqlite3.connect(analytics_db)
        self.source_conn = sqlite3.connect(source_db) if source_db.exists() else None
        self.errors = []
        self.warnings = []
        
    def verify_all(self):
        """전체 검증 실행"""
        print("\n" + "="*60)
        print("🔍 배치 분석 결과 검증 시작")
        print("="*60)
        
        # 1. 데이터 완전성 검증
        self.verify_completeness()
        
        # 2. 데이터 품질 검증
        self.verify_quality()
        
        # 3. 집계 일관성 검증
        self.verify_aggregations()
        
        # 4. Claim 데이터 비교
        self.verify_claim_comparison()
        
        # 5. 조직 정보 일관성
        self.verify_organization_consistency()
        
        # 결과 출력
        self.print_results()
        
    def verify_completeness(self):
        """데이터 완전성 검증"""
        print("\n📊 데이터 완전성 검증...")
        
        # 분석된 데이터 수
        analyzed = pd.read_sql_query("""
            SELECT 
                COUNT(*) as total,
                COUNT(DISTINCT employee_id) as employees,
                COUNT(DISTINCT analysis_date) as dates
            FROM daily_analysis
        """, self.analytics_conn)
        
        if self.source_conn:
            # 예상 데이터 수
            expected_emp = pd.read_sql_query("""
                SELECT COUNT(DISTINCT employee_id) as total
                FROM employees
            """, self.source_conn)
            
            expected_claims = pd.read_sql_query("""
                SELECT 
                    COUNT(DISTINCT employee_id || '|' || work_date) as total
                FROM employee_claims
                WHERE total_hours > 0
            """, self.source_conn)
            
            if analyzed['total'].iloc[0] < expected_claims['total'].iloc[0]:
                missing = expected_claims['total'].iloc[0] - analyzed['total'].iloc[0]
                self.warnings.append(f"미처리 레코드: {missing:,}개")
                
                # 미처리 날짜 찾기
                missing_dates = pd.read_sql_query("""
                    SELECT DISTINCT ec.work_date
                    FROM employee_claims ec
                    WHERE ec.total_hours > 0
                        AND NOT EXISTS (
                            SELECT 1 FROM daily_analysis da
                            WHERE da.employee_id = ec.employee_id
                                AND da.analysis_date = ec.work_date
                        )
                    ORDER BY ec.work_date
                    LIMIT 10
                """, self.source_conn)
                
                if not missing_dates.empty:
                    self.warnings.append(f"미처리 날짜 예시: {missing_dates['work_date'].tolist()}")
        
        print(f"  ✅ 총 {analyzed['total'].iloc[0]:,}개 레코드 분석 완료")
        print(f"  ✅ {analyzed['employees'].iloc[0]:,}명 직원")
        print(f"  ✅ {analyzed['dates'].iloc[0]}일간 데이터")
        
    def verify_quality(self):
        """데이터 품질 검증"""
        print("\n🔍 데이터 품질 검증...")
        
        # 범위 검증
        invalid = pd.read_sql_query("""
            SELECT 
                COUNT(CASE WHEN efficiency_ratio < 0 OR efficiency_ratio > 100 THEN 1 END) as bad_efficiency,
                COUNT(CASE WHEN work_hours < 0 OR work_hours > 24 THEN 1 END) as bad_hours,
                COUNT(CASE WHEN total_hours < work_hours THEN 1 END) as bad_total,
                COUNT(CASE WHEN focus_ratio < 0 OR focus_ratio > 100 THEN 1 END) as bad_focus
            FROM daily_analysis
        """, self.analytics_conn)
        
        row = invalid.iloc[0]
        if row['bad_efficiency'] > 0:
            self.errors.append(f"잘못된 효율성 값: {row['bad_efficiency']}개")
        if row['bad_hours'] > 0:
            self.errors.append(f"잘못된 근무시간: {row['bad_hours']}개")
        if row['bad_total'] > 0:
            self.errors.append(f"총 시간 < 근무시간: {row['bad_total']}개")
        if row['bad_focus'] > 0:
            self.errors.append(f"잘못된 집중도: {row['bad_focus']}개")
        
        # NULL 값 검증
        nulls = pd.read_sql_query("""
            SELECT 
                COUNT(CASE WHEN employee_id IS NULL THEN 1 END) as null_emp_id,
                COUNT(CASE WHEN analysis_date IS NULL THEN 1 END) as null_date,
                COUNT(CASE WHEN total_hours IS NULL THEN 1 END) as null_hours
            FROM daily_analysis
        """, self.analytics_conn)
        
        row = nulls.iloc[0]
        if row['null_emp_id'] > 0:
            self.errors.append(f"직원 ID 누락: {row['null_emp_id']}개")
        if row['null_date'] > 0:
            self.errors.append(f"날짜 누락: {row['null_date']}개")
        
        if not self.errors:
            print("  ✅ 데이터 품질 이상 없음")
        
    def verify_aggregations(self):
        """집계 데이터 일관성 검증"""
        print("\n📈 집계 일관성 검증...")
        
        # 팀 집계 vs 개인 데이터 비교
        team_check = pd.read_sql_query("""
            SELECT 
                t.team_id,
                t.analysis_date,
                t.avg_efficiency_ratio as team_avg,
                d.calc_avg,
                ABS(t.avg_efficiency_ratio - d.calc_avg) as diff
            FROM team_daily_summary t
            JOIN (
                SELECT 
                    team_id,
                    analysis_date,
                    AVG(efficiency_ratio) as calc_avg
                FROM daily_analysis
                WHERE team_id IS NOT NULL
                GROUP BY team_id, analysis_date
            ) d ON t.team_id = d.team_id AND t.analysis_date = d.analysis_date
            WHERE ABS(t.avg_efficiency_ratio - d.calc_avg) > 0.1
            LIMIT 10
        """, self.analytics_conn)
        
        if not team_check.empty:
            self.warnings.append(f"팀 집계 불일치: {len(team_check)}건")
        else:
            print("  ✅ 팀 집계 일관성 확인")
        
        # 센터 집계 vs 개인 데이터 비교
        center_check = pd.read_sql_query("""
            SELECT 
                c.center_id,
                c.analysis_date,
                c.total_employees as center_total,
                d.calc_total,
                ABS(c.total_employees - d.calc_total) as diff
            FROM center_daily_summary c
            JOIN (
                SELECT 
                    center_id,
                    analysis_date,
                    COUNT(DISTINCT employee_id) as calc_total
                FROM daily_analysis
                WHERE center_id IS NOT NULL
                GROUP BY center_id, analysis_date
            ) d ON c.center_id = d.center_id AND c.analysis_date = d.analysis_date
            WHERE c.total_employees != d.calc_total
            LIMIT 10
        """, self.analytics_conn)
        
        if not center_check.empty:
            self.warnings.append(f"센터 집계 불일치: {len(center_check)}건")
        else:
            print("  ✅ 센터 집계 일관성 확인")
        
    def verify_claim_comparison(self):
        """Claim 데이터 비교 검증"""
        print("\n📋 Claim 데이터 비교...")
        
        if self.source_conn:
            # Claim vs 실제 분석 비교
            claim_diff = pd.read_sql_query("""
                SELECT 
                    AVG(ABS(claim_vs_actual_diff)) as avg_diff,
                    MAX(ABS(claim_vs_actual_diff)) as max_diff,
                    COUNT(CASE WHEN ABS(claim_vs_actual_diff) > 4 THEN 1 END) as large_diff
                FROM daily_analysis
                WHERE claim_hours > 0
            """, self.analytics_conn)
            
            if not claim_diff.empty:
                row = claim_diff.iloc[0]
                print(f"  📊 평균 차이: {row['avg_diff']:.2f}시간")
                print(f"  📊 최대 차이: {row['max_diff']:.2f}시간")
                
                if row['large_diff'] > 0:
                    self.warnings.append(f"Claim과 4시간 이상 차이: {row['large_diff']}건")
        
    def verify_organization_consistency(self):
        """조직 정보 일관성 검증"""
        print("\n🏢 조직 정보 일관성 검증...")
        
        # 조직 정보 누락 확인
        org_missing = pd.read_sql_query("""
            SELECT 
                COUNT(CASE WHEN center_name IS NULL THEN 1 END) as no_center,
                COUNT(CASE WHEN team_name IS NULL THEN 1 END) as no_team,
                COUNT(CASE WHEN job_grade IS NULL THEN 1 END) as no_grade
            FROM daily_analysis
        """, self.analytics_conn)
        
        row = org_missing.iloc[0]
        if row['no_center'] > 0:
            self.warnings.append(f"센터 정보 누락: {row['no_center']}개")
        if row['no_team'] > 0:
            self.warnings.append(f"팀 정보 누락: {row['no_team']}개")
        if row['no_grade'] > 0:
            self.warnings.append(f"직급 정보 누락: {row['no_grade']}개")
        
        if row['no_center'] == 0 and row['no_team'] == 0:
            print("  ✅ 조직 정보 완전성 확인")
        
    def print_results(self):
        """검증 결과 출력"""
        print("\n" + "="*60)
        print("📊 검증 결과 요약")
        print("="*60)
        
        if self.errors:
            print("\n❌ 오류 ({} 건):".format(len(self.errors)))
            for error in self.errors:
                print(f"  • {error}")
        else:
            print("\n✅ 심각한 오류 없음")
        
        if self.warnings:
            print("\n⚠️  경고 ({} 건):".format(len(self.warnings)))
            for warning in self.warnings:
                print(f"  • {warning}")
        else:
            print("\n✅ 경고 사항 없음")
        
        # 최종 판정
        print("\n" + "="*60)
        if not self.errors and len(self.warnings) < 5:
            print("✅ 배치 분석 결과 검증 통과!")
            print("   데이터를 사용할 준비가 완료되었습니다.")
        elif self.errors:
            print("❌ 검증 실패 - 오류를 수정해야 합니다.")
            sys.exit(1)
        else:
            print("⚠️  검증 완료 - 경고 사항을 검토하세요.")
        print("="*60)
        
    def __del__(self):
        """연결 종료"""
        if hasattr(self, 'analytics_conn'):
            self.analytics_conn.close()
        if hasattr(self, 'source_conn') and self.source_conn:
            self.source_conn.close()


def main():
    """메인 실행"""
    if not analytics_db.exists():
        print("❌ 분석 DB가 존재하지 않습니다. 배치 분석을 먼저 실행하세요.")
        sys.exit(1)
    
    verifier = BatchResultVerifier()
    verifier.verify_all()


if __name__ == "__main__":
    main()