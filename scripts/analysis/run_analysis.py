#!/usr/bin/env python
"""
run_analysis.py
부서별 차이 분석 메인 실행 스크립트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from lib.pattern_analyzer import DepartmentPatternAnalyzer
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

def main():
    """메인 실행 함수"""
    
    print("=" * 60)
    print("부서별 근무 패턴 차이 분석 시작")
    print("=" * 60)
    
    # 1. 분석기 초기화
    print("\n[1/6] 분석기 초기화...")
    analyzer = DepartmentPatternAnalyzer(db_path='../../data/sambio_human.db')
    
    # 2. 패턴 추출
    print("[2/6] 부서별 패턴 추출 중...")
    patterns = analyzer.extract_patterns()
    print(f"  → {len(patterns)}개 부서 패턴 추출 완료")
    
    # 3. 클러스터링
    print("[3/6] 부서 클러스터링 수행 중...")
    clusters = analyzer.cluster_departments(n_clusters=5)
    for cluster_id, info in clusters.items():
        print(f"  → {info['name']}: {info['size']}개 팀, {info['total_employees']}명")
    
    # 4. 신뢰도 계산
    print("[4/6] 신뢰도 점수 계산 중...")
    reliability = analyzer.calculate_reliability_scores()
    print(f"  → 평균 신뢰도: {reliability['reliability_score'].mean():.3f}")
    
    # 5. 보정 Factor 도출
    print("[5/6] 보정 Factor 도출 중...")
    corrections = analyzer.derive_correction_factors()
    
    # 보정 타입별 통계
    type_stats = corrections['correction_type'].value_counts()
    for correction_type, count in type_stats.items():
        print(f"  → {correction_type}: {count}개 부서")
    
    # 6. 결과 저장
    print("[6/6] 결과 저장 중...")
    analyzer.save_results()
    
    # 7. 간단한 시각화
    create_visualizations(analyzer.patterns_df)
    
    # 8. 리포트 생성
    report = analyzer.generate_report()
    print("\n" + "=" * 60)
    print("분석 완료 - 요약")
    print("=" * 60)
    print(f"총 부서 수: {report['summary']['total_departments']}")
    print(f"총 직원 수: {report['summary']['total_employees']}")
    print(f"\n패턴 분포:")
    for pattern, count in report['pattern_distribution'].items():
        print(f"  - {pattern}: {count}개 부서")
    
    print("\n✅ 분석이 성공적으로 완료되었습니다!")
    print(f"결과 파일: scripts/analysis/output/")

def create_visualizations(df):
    """간단한 시각화 생성"""
    
    # 설정
    import platform
    if platform.system() == 'Darwin':  # macOS
        plt.rcParams['font.family'] = 'AppleGothic'
    elif platform.system() == 'Windows':
        plt.rcParams['font.family'] = 'Malgun Gothic'
    else:
        plt.rcParams['font.family'] = 'DejaVu Sans'
    plt.rcParams['axes.unicode_minus'] = False
    
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    
    # 1. 위치 고정성 분포
    axes[0, 0].hist(df['location_fixity'], bins=20, edgecolor='black')
    axes[0, 0].set_xlabel('위치 고정성 (%)')
    axes[0, 0].set_ylabel('부서 수')
    axes[0, 0].set_title('부서별 위치 고정성 분포')
    
    # 2. 신뢰도 vs 보정 Factor
    axes[0, 1].scatter(df['reliability_score'], df['correction_factor'])
    axes[0, 1].set_xlabel('신뢰도 점수')
    axes[0, 1].set_ylabel('보정 Factor')
    axes[0, 1].set_title('신뢰도와 보정 Factor 관계')
    
    # 3. 클러스터별 부서 수
    cluster_counts = df['cluster'].value_counts()
    axes[1, 0].bar(cluster_counts.index, cluster_counts.values)
    axes[1, 0].set_xlabel('클러스터')
    axes[1, 0].set_ylabel('부서 수')
    axes[1, 0].set_title('클러스터별 부서 분포')
    
    # 4. 보정 타입 분포
    type_counts = df['correction_type'].value_counts()
    axes[1, 1].pie(type_counts.values, labels=type_counts.index, autopct='%1.1f%%')
    axes[1, 1].set_title('보정 타입 분포')
    
    plt.tight_layout()
    
    # 저장
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    plt.savefig(f'output/analysis_summary_{timestamp}.png', dpi=100)
    print(f"  → 시각화 저장: output/analysis_summary_{timestamp}.png")
    
    plt.close()

if __name__ == "__main__":
    main()