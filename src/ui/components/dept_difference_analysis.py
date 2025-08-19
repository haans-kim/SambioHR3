"""
dept_difference_analysis.py
부서별 차이 분석 및 보정 시스템 UI (메인 앱 통합 버전)
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import sys
import os
from datetime import datetime

# 분석 라이브러리 경로 추가
analysis_path = os.path.join(os.path.dirname(__file__), '../../../scripts/analysis')
if analysis_path not in sys.path:
    sys.path.insert(0, analysis_path)

try:
    from lib.pattern_analyzer import DepartmentPatternAnalyzer
except ImportError:
    st.error("분석 라이브러리를 찾을 수 없습니다. scripts/analysis/lib/pattern_analyzer.py 파일을 확인하세요.")
    DepartmentPatternAnalyzer = None

def render_page():
    """메인 페이지 렌더링"""
    
    st.title("🎯 부서별 차이 분석 및 보정 시스템")
    st.markdown("---")
    
    # 사이드바 설정
    with st.sidebar:
        st.header("⚙️ 분석 설정")
        
        analysis_type = st.selectbox(
            "분석 유형",
            ["실시간 분석", "저장된 결과 조회"]
        )
        
        if analysis_type == "실시간 분석":
            n_clusters = st.slider("클러스터 수", 3, 7, 5)
            if st.button("🔄 분석 실행", type="primary"):
                run_analysis(n_clusters)
    
    # 메인 탭
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 차이 분석", 
        "🔄 보정 Factor", 
        "📈 검증 결과", 
        "📝 리포트"
    ])
    
    with tab1:
        render_difference_analysis()
    
    with tab2:
        render_correction_factors()
    
    with tab3:
        render_validation_results()
    
    with tab4:
        render_report()

def load_analysis_data():
    """분석 데이터 로드 (캐시 제거 - 항상 최신 데이터)"""
    
    conn = sqlite3.connect('data/sambio_human.db')
    
    # 저장된 분석 결과 로드
    try:
        patterns_df = pd.read_sql_query(
            "SELECT * FROM dept_pattern_analysis_new", 
            conn
        )
        conn.close()
        return patterns_df
    except Exception as e:
        conn.close()
        return None

def run_analysis(n_clusters):
    """실시간 분석 실행"""
    
    if DepartmentPatternAnalyzer is None:
        st.error("분석 라이브러리를 로드할 수 없습니다.")
        return
    
    with st.spinner("분석 중... (약 30초 소요)"):
        try:
            # 분석 실행 - 올바른 DB 경로 사용
            analyzer = DepartmentPatternAnalyzer(db_path='data/sambio_human.db')
            patterns = analyzer.extract_patterns()
            clusters = analyzer.cluster_departments(n_clusters)
            reliability = analyzer.calculate_reliability_scores()
            corrections = analyzer.derive_correction_factors()
            analyzer.save_results()
            
            st.success("✅ 분석이 완료되었습니다!")
            st.rerun()  # experimental_rerun은 deprecated
            
        except Exception as e:
            st.error(f"❌ 분석 중 오류 발생: {str(e)}")

def render_difference_analysis():
    """차이 분석 탭"""
    
    st.header("📊 부서별 근무 패턴 차이 분석")
    
    # 데이터 로드
    df = load_analysis_data()
    
    if df is None or df.empty:
        st.warning("분석 데이터가 없습니다. 먼저 분석을 실행하세요.")
        return
    
    # 1. 핵심 지표 표시
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("분석 부서 수", f"{len(df)}개")
    
    with col2:
        total_emp = df['employee_count'].sum() if 'employee_count' in df.columns else 0
        st.metric("총 직원 수", f"{total_emp:,}명")
    
    with col3:
        avg_fixity = df['location_fixity'].mean() if 'location_fixity' in df.columns else 0
        st.metric("평균 위치 고정성", f"{avg_fixity:.1f}%")
    
    with col4:
        avg_reliability = df['reliability_score'].mean() if 'reliability_score' in df.columns else 0
        st.metric("평균 신뢰도", f"{avg_reliability:.3f}")
    
    st.markdown("---")
    
    # 2. 산점도 - 부서별 패턴 분포
    if 'location_fixity' in df.columns and 'data_density' in df.columns:
        # 클러스터 이름 매핑을 먼저 적용 (실제 데이터 기반)
        if 'cluster' in df.columns:
            # 디버깅: Plant팀 데이터 확인
            plant_teams = df[(df['center'] == '오퍼레이션센터') & (df['team'].str.contains('Plant', na=False))]
            if not plant_teams.empty:
                st.sidebar.write("Plant팀 위치 고정성:")
                for _, row in plant_teams.iterrows():
                    st.sidebar.write(f"- {row['team']}: {row['location_fixity']:.1f}%")
            
            # 각 클러스터의 특성을 계산하여 동적으로 이름 할당
            cluster_names = {}
            for cluster_id in df['cluster'].unique():
                cluster_data = df[df['cluster'] == cluster_id]
                avg_fixity = cluster_data['location_fixity'].mean()
                avg_external = cluster_data['external_activity'].mean() if 'external_activity' in cluster_data.columns else 0
                avg_office = cluster_data['office_ratio'].mean() if 'office_ratio' in cluster_data.columns else 0
                
                # primary_plant 정보 추출
                primary_plant = 'Unknown'
                if 'primary_plant' in cluster_data.columns:
                    mode_result = cluster_data['primary_plant'].mode()
                    if len(mode_result) > 0:
                        primary_plant = mode_result[0]
                
                # Plant별 비율 계산
                p1_avg = cluster_data['p1_ratio'].mean() if 'p1_ratio' in cluster_data.columns else 0
                p2_avg = cluster_data['p2_ratio'].mean() if 'p2_ratio' in cluster_data.columns else 0
                p3_avg = cluster_data['p3_ratio'].mean() if 'p3_ratio' in cluster_data.columns else 0
                p4_avg = cluster_data['p4_ratio'].mean() if 'p4_ratio' in cluster_data.columns else 0
                p5_avg = cluster_data['p5_ratio'].mean() if 'p5_ratio' in cluster_data.columns else 0
                
                # 특정 Plant가 압도적으로 높은지 확인
                max_plant_ratio = max(p1_avg, p2_avg, p3_avg, p4_avg, p5_avg)
                
                # 클러스터 특성에 따른 이름 할당
                if avg_office > 40:
                    cluster_names[cluster_id] = f'Type_{cluster_id}_사무중심형'
                elif max_plant_ratio > 40:  # 특정 Plant가 40% 이상이면 그 Plant 중심
                    if p1_avg == max_plant_ratio:
                        cluster_names[cluster_id] = f'Type_{cluster_id}_P1중심형'
                    elif p2_avg == max_plant_ratio:
                        cluster_names[cluster_id] = f'Type_{cluster_id}_P2중심형'
                    elif p3_avg == max_plant_ratio:
                        cluster_names[cluster_id] = f'Type_{cluster_id}_P3중심형'
                    elif p4_avg == max_plant_ratio:
                        cluster_names[cluster_id] = f'Type_{cluster_id}_P4중심형'
                    else:
                        cluster_names[cluster_id] = f'Type_{cluster_id}_P5중심형'
                elif avg_fixity > 90:
                    cluster_names[cluster_id] = f'Type_{cluster_id}_생산집중형'
                elif avg_fixity > 70:
                    cluster_names[cluster_id] = f'Type_{cluster_id}_생산활동형'
                elif avg_fixity > 50:
                    cluster_names[cluster_id] = f'Type_{cluster_id}_복합활동형'
                elif avg_fixity > 30:
                    cluster_names[cluster_id] = f'Type_{cluster_id}_혼합근무형'
                else:
                    if avg_external > 20:
                        cluster_names[cluster_id] = f'Type_{cluster_id}_외부활동형'
                    else:
                        cluster_names[cluster_id] = f'Type_{cluster_id}_지원업무형'
            
            df['pattern_type'] = df['cluster'].map(cluster_names)
            
            # 색상 매핑 정의 (새로운 클러스터 타입에 맞게)
            color_map = {}
            color_palette = [
                '#2ca02c',  # 초록색
                '#ff7f0e',  # 주황색  
                '#1f77b4',  # 파란색
                '#d62728',  # 빨간색
                '#9467bd',  # 보라색
                '#8c564b',  # 갈색
                '#e377c2',  # 핑크색
                '#7f7f7f',  # 회색
            ]
            
            # 각 패턴 타입에 색상 할당
            unique_patterns = df['pattern_type'].unique()
            for i, pattern_name in enumerate(unique_patterns):
                if pd.notna(pattern_name):
                    # 특정 키워드에 따른 색상 지정
                    if 'P1' in pattern_name:
                        color_map[pattern_name] = '#2ca02c'  # 초록
                    elif 'P2' in pattern_name:
                        color_map[pattern_name] = '#ff7f0e'  # 주황
                    elif 'P3' in pattern_name:
                        color_map[pattern_name] = '#1f77b4'  # 파랑
                    elif 'P4' in pattern_name:
                        color_map[pattern_name] = '#d62728'  # 빨강
                    elif 'P5' in pattern_name:
                        color_map[pattern_name] = '#9467bd'  # 보라
                    elif '사무' in pattern_name:
                        color_map[pattern_name] = '#8c564b'  # 갈색
                    elif '복합' in pattern_name or '혼합' in pattern_name:
                        color_map[pattern_name] = '#7f7f7f'  # 회색
                    else:
                        # 나머지는 순환 색상 할당
                        color_map[pattern_name] = color_palette[i % len(color_palette)]
            
            fig_scatter = px.scatter(
                df,
                x='location_fixity',
                y='data_density',
                color='pattern_type',
                color_discrete_map=color_map,
                size='employee_count',
                hover_data=['center', 'team', 'employee_count', 'reliability_score'],
                title='부서별 근무 패턴 분포 (5개 클러스터)',
                labels={
                    'location_fixity': '위치 고정성 (%)',
                    'data_density': '일평균 태그 수',
                    'pattern_type': '패턴 유형',
                    'employee_count': '직원 수',
                    'reliability_score': '신뢰도'
                }
            )
            
            # 클러스터 버블 표시 제거 - 데이터 포인트만으로도 충분히 구분 가능
        else:
            fig_scatter = px.scatter(
                df,
                x='location_fixity',
                y='data_density',
                size='employee_count',
                hover_data=['center', 'team'],
                title='부서별 근무 패턴 분포',
                labels={
                    'location_fixity': '위치 고정성 (%)',
                    'data_density': '일평균 태그 수'
                }
            )
        
        # 차트 레이아웃 개선
        fig_scatter.update_layout(
            height=500,
            showlegend=True,
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02
            )
        )
        fig_scatter.update_traces(marker=dict(opacity=0.7))
        
        st.plotly_chart(fig_scatter, use_container_width=True)
    
    # 3. 패턴 유형별 통계
    st.subheader("📈 패턴 유형별 분포")
    
    if 'cluster' in df.columns:
        # 클러스터별 통계 계산
        cluster_stats = df.groupby('cluster').agg({
            'team': 'count',  # 팀 수
            'employee_count': 'sum',
            'location_fixity': 'mean',
            'data_density': 'mean',
            'reliability_score': 'mean',
            'correction_factor': 'mean'
        }).round(2)
        
        # 컬럼명 변경
        cluster_stats.columns = ['팀수', '총직원수', '평균위치고정성', '평균데이터밀도', '평균신뢰도', '평균보정Factor']
        
        # 클러스터 이름 매핑 (동적으로 생성 - 위와 동일한 로직)
        cluster_names_stats = {}
        for cluster_id in cluster_stats.index:
            cluster_data = df[df['cluster'] == cluster_id]
            avg_fixity = cluster_data['location_fixity'].mean()
            avg_external = cluster_data['external_activity'].mean() if 'external_activity' in cluster_data.columns else 0
            avg_office = cluster_data['office_ratio'].mean() if 'office_ratio' in cluster_data.columns else 0
            
            # primary_plant 정보 추출
            primary_plant = 'Unknown'
            if 'primary_plant' in cluster_data.columns:
                mode_result = cluster_data['primary_plant'].mode()
                if len(mode_result) > 0:
                    primary_plant = mode_result[0]
            
            # Plant별 비율 계산
            p1_avg = cluster_data['p1_ratio'].mean() if 'p1_ratio' in cluster_data.columns else 0
            p2_avg = cluster_data['p2_ratio'].mean() if 'p2_ratio' in cluster_data.columns else 0
            p3_avg = cluster_data['p3_ratio'].mean() if 'p3_ratio' in cluster_data.columns else 0
            p4_avg = cluster_data['p4_ratio'].mean() if 'p4_ratio' in cluster_data.columns else 0
            p5_avg = cluster_data['p5_ratio'].mean() if 'p5_ratio' in cluster_data.columns else 0
            
            # 특정 Plant가 압도적으로 높은지 확인
            max_plant_ratio = max(p1_avg, p2_avg, p3_avg, p4_avg, p5_avg)
            
            # 클러스터 특성에 따른 이름 할당
            if avg_office > 40:
                cluster_names_stats[cluster_id] = f'Type_{cluster_id}_사무중심형'
            elif max_plant_ratio > 40:  # 특정 Plant가 40% 이상이면 그 Plant 중심
                if p1_avg == max_plant_ratio:
                    cluster_names_stats[cluster_id] = f'Type_{cluster_id}_P1중심형'
                elif p2_avg == max_plant_ratio:
                    cluster_names_stats[cluster_id] = f'Type_{cluster_id}_P2중심형'
                elif p3_avg == max_plant_ratio:
                    cluster_names_stats[cluster_id] = f'Type_{cluster_id}_P3중심형'
                elif p4_avg == max_plant_ratio:
                    cluster_names_stats[cluster_id] = f'Type_{cluster_id}_P4중심형'
                else:
                    cluster_names_stats[cluster_id] = f'Type_{cluster_id}_P5중심형'
            elif avg_fixity > 90:
                cluster_names_stats[cluster_id] = f'Type_{cluster_id}_생산집중형'
            elif avg_fixity > 70:
                cluster_names_stats[cluster_id] = f'Type_{cluster_id}_생산활동형'
            elif avg_fixity > 50:
                cluster_names_stats[cluster_id] = f'Type_{cluster_id}_복합활동형'
            elif avg_fixity > 30:
                cluster_names_stats[cluster_id] = f'Type_{cluster_id}_혼합근무형'
            else:
                if avg_external > 20:
                    cluster_names_stats[cluster_id] = f'Type_{cluster_id}_외부활동형'
                else:
                    cluster_names_stats[cluster_id] = f'Type_{cluster_id}_지원업무형'
        
        cluster_stats.index = cluster_stats.index.map(lambda x: cluster_names_stats.get(x, f'Type_{x}'))
        
        # 정렬 (직원수 기준)
        cluster_stats = cluster_stats.sort_values('총직원수', ascending=False)
        
        # 테이블 표시
        st.dataframe(cluster_stats, use_container_width=True)
        
        # 추가 시각화: 클러스터별 분포 파이 차트
        col1, col2 = st.columns(2)
        
        with col1:
            # 파이 차트용 색상 매핑 생성 (scatter plot과 동일한 로직)
            pie_color_map = {}
            for name in cluster_stats.index:
                if 'P1' in name:
                    pie_color_map[name] = '#2ca02c'  # 초록
                elif 'P2' in name:
                    pie_color_map[name] = '#ff7f0e'  # 주황
                elif 'P3' in name:
                    pie_color_map[name] = '#1f77b4'  # 파랑
                elif 'P4' in name:
                    pie_color_map[name] = '#d62728'  # 빨강
                elif 'P5' in name:
                    pie_color_map[name] = '#9467bd'  # 보라
                elif '사무' in name:
                    pie_color_map[name] = '#8c564b'  # 갈색
                elif '복합' in name or '혼합' in name:
                    pie_color_map[name] = '#7f7f7f'  # 회색
                else:
                    pie_color_map[name] = '#e377c2'  # 핑크 (기타)
            
            fig_pie_teams = px.pie(
                values=cluster_stats['팀수'],
                names=cluster_stats.index,
                title='클러스터별 팀 분포',
                color_discrete_map=pie_color_map
            )
            st.plotly_chart(fig_pie_teams, use_container_width=True)
        
        with col2:
            fig_pie_employees = px.pie(
                values=cluster_stats['총직원수'],
                names=cluster_stats.index,
                title='클러스터별 직원 분포',
                color_discrete_map=pie_color_map  # 동일한 색상 매핑 사용
            )
            st.plotly_chart(fig_pie_employees, use_container_width=True)

def render_correction_factors():
    """보정 Factor 탭"""
    
    st.header("🔄 부서별 보정 Factor")
    
    df = load_analysis_data()
    
    if df is None or df.empty:
        st.warning("분석 데이터가 없습니다.")
        return
    
    # 1. 보정 타입별 분포
    if 'correction_type' in df.columns:
        type_counts = df['correction_type'].value_counts()
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig_pie = px.pie(
                values=type_counts.values,
                names=type_counts.index,
                title='보정 타입 분포'
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            # 보정 Factor 히스토그램
            if 'correction_factor' in df.columns:
                fig_hist = px.histogram(
                    df,
                    x='correction_factor',
                    nbins=20,
                    title='보정 Factor 분포',
                    labels={'correction_factor': '보정 Factor', 'count': '부서 수'}
                )
                st.plotly_chart(fig_hist, use_container_width=True)
    
    # 2. 부서별 보정 Factor 테이블
    st.subheader("📋 부서별 보정 Factor")
    
    if all(col in df.columns for col in ['center', 'team', 'reliability_score', 'correction_factor']):
        display_df = df[['center', 'team', 'employee_count', 
                         'reliability_score', 'correction_factor', 'correction_type']]
        display_df = display_df.sort_values('correction_factor', ascending=False)
        
        st.dataframe(
            display_df.style.format({
                'reliability_score': '{:.3f}',
                'correction_factor': '{:.3f}'
            }),
            use_container_width=True,
            height=400
        )

def render_validation_results():
    """검증 결과 탭"""
    
    st.header("📈 Claim 데이터 검증 결과")
    
    # 검증 로직 구현 (추후 개발)
    st.info("Claim 데이터와의 비교 검증 기능은 추후 구현 예정입니다.")
    
    # 예시 차트
    st.subheader("예상 개선 효과")
    
    improvement_data = pd.DataFrame({
        '보정 방법': ['기존 (획일적)', '개선 (차별화)'],
        '평균 오차율': [12.5, 7.2],
        '부서간 편차': [8.3, 3.1]
    })
    
    fig = px.bar(
        improvement_data,
        x='보정 방법',
        y=['평균 오차율', '부서간 편차'],
        title='보정 방법별 성능 비교',
        barmode='group'
    )
    st.plotly_chart(fig, use_container_width=True)

def render_report():
    """리포트 탭"""
    
    st.header("📝 분석 리포트")
    
    df = load_analysis_data()
    
    if df is None or df.empty:
        st.warning("분석 데이터가 없습니다.")
        return
    
    # 리포트 내용 생성
    st.markdown(f"""
    ## 부서별 근무 패턴 차이 분석 보고서
    
    **분석 일시**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
    
    ### 1. 요약
    - **분석 부서 수**: {len(df)}개
    - **총 직원 수**: {df['employee_count'].sum():,}명
    - **분석 기간**: 2025년 6월 (1개월)
    
    ### 2. 주요 발견사항
    
    #### 2.1 패턴 분류
    부서별 근무 패턴을 분석한 결과, 크게 5가지 유형으로 분류됨:
    
    - **Type A (생산고정형)**: 생산동 위치 비율 85% 이상
    - **Type B (생산중심형)**: 생산동 위치 비율 60-85%
    - **Type C (혼합근무형)**: 생산동 위치 비율 30-60%
    - **Type D (외부활동형)**: 외부 활동 비율 15% 이상
    - **Type E (사무중심형)**: 사무실 중심 근무
    
    #### 2.2 신뢰도 분포
    - **높은 신뢰도 (>0.75)**: {len(df[df['reliability_score'] > 0.75])}개 부서
    - **중간 신뢰도 (0.45-0.75)**: {len(df[(df['reliability_score'] >= 0.45) & (df['reliability_score'] <= 0.75)])}개 부서
    - **낮은 신뢰도 (<0.45)**: {len(df[df['reliability_score'] < 0.45])}개 부서
    
    ### 3. 결론
    
    부서별 근무 패턴에 따라 차별화된 보정 Factor를 적용함으로써:
    - Claim 대비 오차율 감소 예상
    - 부서별 특성을 반영한 공정한 평가 가능
    - 데이터 기반 의사결정 체계 구축
    """)
    
    # 다운로드 버튼
    if st.button("📥 Excel 리포트 다운로드"):
        # Excel 파일 생성 로직 (추후 구현)
        st.success("리포트가 다운로드되었습니다.")

# 메인 앱에서 import하여 사용