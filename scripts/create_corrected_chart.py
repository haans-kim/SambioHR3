"""
수정된 클러스터링 차트 생성
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'analysis'))

from lib.llm_analyzer import LLMPatternAnalyzer
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

def create_corrected_chart():
    """수정된 차트 생성"""
    
    # 분석기 초기화
    analyzer = LLMPatternAnalyzer(db_path='data/sambio_human.db')
    
    # 데이터 준비
    df = analyzer.prepare_data_for_llm(min_employees=5)
    
    # 각 팀별 클러스터 할당
    clusters = []
    for _, row in df.iterrows():
        cluster_type = analyzer._determine_cluster_type(row)
        clusters.append({
            'team': row['team'],
            'cluster': cluster_type,
            'employee_count': row['employee_count'],
            'o_per_person': row['o_per_person'],
            't1_per_person': row['t1_per_person'],
            'knox_per_person': row['knox_per_person'],
            'g3_per_person': row['g3_per_person']
        })
    
    cluster_df = pd.DataFrame(clusters)
    
    # 클러스터별 통계 출력
    print("\n=== 클러스터별 분포 확인 ===")
    cluster_stats = cluster_df.groupby('cluster').agg({
        'team': 'count',
        'employee_count': 'sum',
        'o_per_person': 'mean',
        't1_per_person': 'mean'
    }).round(1)
    cluster_stats.columns = ['팀수', '총직원수', '평균장비사용', '평균이동활동']
    print(cluster_stats)
    
    # Plotly로 정확한 차트 생성
    fig = px.scatter(
        cluster_df,
        x='o_per_person',
        y='t1_per_person',
        color='cluster',
        size='employee_count',
        hover_data=['team', 'employee_count', 'knox_per_person', 'g3_per_person'],
        title='장비사용 vs 이동성 지수 패턴 분포 (수정된 클러스터링)',
        labels={
            'o_per_person': '장비 사용 (건/인)',
            't1_per_person': '이동성 지수',
            'cluster': '패턴 유형',
            'employee_count': '직원수'
        },
        color_discrete_map={
            '장비운영집중형': '#1f77b4',  # 파란색
            '현장이동활발형': '#ff7f0e',  # 주황색
            '디지털협업중심형': '#2ca02c',  # 녹색
            '균형업무형': '#d62728',  # 빨간색
            '회의협업중심형': '#9467bd',  # 보라색
            '저활동형': '#8c564b'  # 갈색
        }
    )
    
    # 레이아웃 조정
    fig.update_layout(
        width=1000,
        height=700,
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02
        )
    )
    
    # 차트 저장 및 표시
    fig.write_html('scripts/analysis/output/corrected_clustering_chart.html')
    fig.show()
    
    # 클러스터별 상세 정보
    print("\n=== 클러스터별 대표 팀 ===")
    for cluster in cluster_df['cluster'].unique():
        cluster_data = cluster_df[cluster_df['cluster'] == cluster]
        top_teams = cluster_data.nlargest(3, 'employee_count')['team'].tolist()
        print(f"{cluster}: {', '.join(top_teams)}")
    
    return cluster_df

if __name__ == "__main__":
    result = create_corrected_chart()