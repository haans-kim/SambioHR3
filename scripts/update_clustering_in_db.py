"""
DB에 하이브리드 클러스터링 결과 업데이트
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'analysis'))

from lib.llm_analyzer import LLMPatternAnalyzer
import sqlite3
import pandas as pd

def update_clustering():
    """모든 팀의 클러스터링 결과를 DB에 저장"""
    
    # 분석기 초기화
    analyzer = LLMPatternAnalyzer(db_path='data/sambio_human.db')
    
    # DB에서 모든 팀 데이터 직접 가져오기 (필터링 없이)
    conn = sqlite3.connect('data/sambio_human.db')
    query = """
    SELECT 
        center, bu, team, employee_count,
        g1_count, g2_count, g3_count, g4_count,
        n1_count, n2_count, t1_count,
        knox_total_count, knox_approval_count, knox_pims_count, knox_mail_count,
        o_tag_count, eam_count, lams_count, mes_count, equis_count, mdm_count,
        -- 인당 지표 계산
        ROUND(g1_count * 1.0 / NULLIF(employee_count, 0), 1) as g1_per_person,
        ROUND(g3_count * 1.0 / NULLIF(employee_count, 0), 1) as g3_per_person,
        ROUND(g4_count * 1.0 / NULLIF(employee_count, 0), 1) as g4_per_person,
        ROUND(n1_count * 1.0 / NULLIF(employee_count, 0), 1) as n1_per_person,
        ROUND(t1_count * 1.0 / NULLIF(employee_count, 0), 1) as t1_per_person,
        ROUND(knox_total_count * 1.0 / NULLIF(employee_count, 0), 1) as knox_per_person,
        ROUND(o_tag_count * 1.0 / NULLIF(employee_count, 0), 1) as o_per_person
    FROM dept_pattern_analysis_new
    ORDER BY team
    """
    
    all_df = pd.read_sql_query(query, conn)
    conn.close()
    
    # 각 팀에 클러스터 할당
    all_df['cluster_type'] = all_df.apply(analyzer._determine_cluster_type, axis=1)
    
    # 분석 대상 여부 표시 (직원 5명 이상이고 실제 팀인 경우)
    all_df['is_analysis_target'] = all_df.apply(
        lambda row: 1 if row['employee_count'] >= 5 else 0, 
        axis=1
    )
    
    # 제외 사유 분류
    def get_exclusion_reason(row):
        if row['employee_count'] < 5:
            if row['employee_count'] <= 3 and row['team'].endswith('담당'):
                return '담당레벨(3명이하)'
            elif row['team'] in ['바이오연구소', '경영지원센터', '대표이사', '상생협력센터', 
                                '영업센터', '품질운영센터', 'CDO개발센터', 'EPCV센터']:
                return '상위조직'
            else:
                return '소규모팀(5명미만)'
        else:
            return None
    
    all_df['exclusion_reason'] = all_df.apply(get_exclusion_reason, axis=1)
    
    # DB 연결
    conn = sqlite3.connect('data/sambio_human.db')
    cursor = conn.cursor()
    
    # 업데이트 실행
    update_count = 0
    exclude_count = 0
    
    for _, row in all_df.iterrows():
        team = row['team']
        cluster = row['cluster_type']
        is_target = row['is_analysis_target']
        exclusion = row['exclusion_reason']
        
        # dept_pattern_analysis_new 테이블 업데이트
        cursor.execute("""
            UPDATE dept_pattern_analysis_new 
            SET cluster_type = ?,
                is_analysis_target = ?,
                exclusion_reason = ?
            WHERE team = ?
        """, (cluster, is_target, exclusion, team))
        
        if cursor.rowcount > 0:
            if is_target:
                update_count += 1
            else:
                exclude_count += 1
    
    # 커밋
    conn.commit()
    
    # 결과 확인
    print("=== 클러스터링 업데이트 완료 ===")
    print(f"분석 대상 팀 업데이트: {update_count}개")
    print(f"제외된 팀 업데이트: {exclude_count}개")
    
    # 클러스터별 통계
    print("\n=== 클러스터별 분포 (분석 대상만) ===")
    result = cursor.execute("""
        SELECT cluster_type, COUNT(*) as count, SUM(employee_count) as total_employees
        FROM dept_pattern_analysis_new
        WHERE is_analysis_target = 1
        GROUP BY cluster_type
        ORDER BY count DESC
    """).fetchall()
    
    for cluster, count, employees in result:
        print(f"{cluster}: {count}개 팀, {employees}명")
    
    # 제외된 팀 통계
    print("\n=== 제외된 팀 분류 ===")
    excluded = cursor.execute("""
        SELECT exclusion_reason, COUNT(*) as count, 
               GROUP_CONCAT(team, ', ') as teams
        FROM dept_pattern_analysis_new
        WHERE is_analysis_target = 0
        GROUP BY exclusion_reason
    """).fetchall()
    
    for reason, count, teams in excluded:
        team_list = teams.split(', ')[:3]  # 처음 3개만 표시
        print(f"{reason}: {count}개 팀")
        print(f"  예시: {', '.join(team_list)}")
    
    # 제외된 팀들의 클러스터 분포
    print("\n=== 제외된 팀들의 클러스터 유형 (참고용) ===")
    excluded_clusters = cursor.execute("""
        SELECT cluster_type, COUNT(*) as count, exclusion_reason
        FROM dept_pattern_analysis_new
        WHERE is_analysis_target = 0
        GROUP BY cluster_type, exclusion_reason
        ORDER BY cluster_type, exclusion_reason
    """).fetchall()
    
    for cluster, count, reason in excluded_clusters:
        print(f"{cluster} ({reason}): {count}개 팀")
    
    conn.close()
    
    print("\n✅ DB 업데이트 완료!")
    print("다른 프로그램에서 dept_pattern_analysis_new 테이블의 cluster_type 컬럼을 조회하면")
    print("하이브리드 클러스터링 결과를 확인할 수 있습니다.")
    
    return all_df

if __name__ == "__main__":
    # 필요한 컬럼 추가 (이미 있으면 무시)
    conn = sqlite3.connect('data/sambio_human.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE dept_pattern_analysis_new ADD COLUMN cluster_type TEXT")
        print("cluster_type 컬럼 추가됨")
    except:
        print("cluster_type 컬럼이 이미 존재함")
    
    try:
        cursor.execute("ALTER TABLE dept_pattern_analysis_new ADD COLUMN is_analysis_target INTEGER DEFAULT 1")
        print("is_analysis_target 컬럼 추가됨")
    except:
        print("is_analysis_target 컬럼이 이미 존재함")
    
    try:
        cursor.execute("ALTER TABLE dept_pattern_analysis_new ADD COLUMN exclusion_reason TEXT")
        print("exclusion_reason 컬럼 추가됨")
    except:
        print("exclusion_reason 컬럼이 이미 존재함")
    
    conn.commit()
    conn.close()
    
    # 클러스터링 업데이트 실행
    update_clustering()