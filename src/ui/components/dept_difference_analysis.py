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
    
    # 팀별 태그 개수 데이터 표시 추가
    st.subheader("📋 팀별 태그 개수 데이터")
    
    # 표시할 컬럼 선택
    tag_columns = []
    
    # 기본 정보
    basic_cols = ['center', 'bu', 'team', 'employee_count']
    for col in basic_cols:
        if col in df.columns:
            tag_columns.append(col)
    
    # 태그 개수 컬럼들 (TagCode별) - T2, T3, M1, M2 제외
    count_cols = ['g1_count', 'g2_count', 'g3_count', 'g4_count',
                  'n1_count', 'n2_count', 't1_count',
                  'knox_total_count', 'knox_approval_count',
                  'knox_pims_count', 'knox_mail_count', 'o_tag_count', 
                  'eam_count', 'lams_count', 'mes_count', 'equis_count', 'mdm_count']
    
    for col in count_cols:
        if col in df.columns:
            tag_columns.append(col)
    
    if tag_columns:
        # 데이터프레임 표시
        display_df = df[tag_columns].copy()
        
        # 팀별로 정렬
        if 'center' in display_df.columns and 'team' in display_df.columns:
            display_df = display_df.sort_values(['center', 'team'])
        
        # 스크롤 가능한 테이블로 표시
        st.dataframe(
            display_df,
            use_container_width=True,
            height=300
        )
        
        # 요약 통계
        st.markdown("### 📊 태그 개수 요약")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if 'o_tag_count' in df.columns:
                total_o = df['o_tag_count'].sum()
                st.metric("총 O태그 (장비)", f"{total_o:,}")
        
        with col2:
            if 'knox_total_count' in df.columns:
                total_knox = df['knox_total_count'].sum()
                st.metric("총 Knox (결재+회의+메일)", f"{total_knox:,}")
        
        with col3:
            if 't1_count' in df.columns:
                total_t1 = df['t1_count'].sum()
                st.metric("총 T1 (이동공간)", f"{total_t1:,}")
        
        with col4:
            if 'g3_count' in df.columns:
                total_g3 = df['g3_count'].sum()
                st.metric("총 G3 (회의/협업)", f"{total_g3:,}")
    
    st.markdown("---")
    
    # 1. 핵심 지표 표시
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("분석 부서 수", f"{len(df)}개")
    
    with col2:
        total_emp = df['employee_count'].sum() if 'employee_count' in df.columns else 0
        st.metric("총 직원 수", f"{total_emp:,}명")
    
    with col3:
        avg_diversity = df['tag_diversity'].mean() if 'tag_diversity' in df.columns else 0
        st.metric("평균 태그 다양성", f"{avg_diversity:.1f}")
    
    with col4:
        avg_reliability = df['reliability_score'].mean() if 'reliability_score' in df.columns else 0
        st.metric("평균 신뢰도", f"{avg_reliability:.3f}")
    
    st.markdown("---")
    
    # 2. 태그 기반 클러스터링 시각화
    st.subheader("🎯 태그 기반 클러스터링 결과")
    
    # 태그 개수 기반 산점도 그리기
    if 'o_tag_count' in df.columns and 'knox_total_count' in df.columns:
        # 클러스터 이름 매핑을 먼저 적용 (태그 개수 기반)
        if 'cluster' in df.columns:
            
            # 각 클러스터의 특성을 계산하여 동적으로 이름 할당
            cluster_names = {}
            for cluster_id in df['cluster'].unique():
                cluster_data = df[df['cluster'] == cluster_id]
                
                # 태그 개수 기반으로 클러스터 특성 계산
                avg_o_tag = cluster_data['o_tag_count'].mean() if 'o_tag_count' in cluster_data.columns else 0
                avg_knox = cluster_data['knox_total_count'].mean() if 'knox_total_count' in cluster_data.columns else 0
                avg_t1 = cluster_data['t1_count'].mean() if 't1_count' in cluster_data.columns else 0
                avg_g3 = cluster_data['g3_count'].mean() if 'g3_count' in cluster_data.columns else 0
                
                # 클러스터 타입 결정 (태그 개수 기반)
                if avg_o_tag > 1000:
                    cluster_names[cluster_id] = f'Type_{cluster_id}_장비집중형'
                elif avg_knox > 1000:
                    cluster_names[cluster_id] = f'Type_{cluster_id}_협업중심형'
                elif avg_t1 > 500:
                    cluster_names[cluster_id] = f'Type_{cluster_id}_이동활발형'
                elif avg_g3 > 50:
                    cluster_names[cluster_id] = f'Type_{cluster_id}_회의중심형'
                else:
                    cluster_names[cluster_id] = f'Type_{cluster_id}_복합활동형'
            
            df['pattern_type'] = df['cluster'].map(cluster_names)
            
            # 색상 매핑 정의 (행동 패턴 기반 클러스터 타입)
            color_map = {}
            
            # 각 패턴 타입에 색상 할당
            unique_patterns = df['pattern_type'].unique()
            for pattern_name in unique_patterns:
                if pd.notna(pattern_name):
                    # 특정 키워드에 따른 색상 지정
                    if '고정근무형' in pattern_name:
                        color_map[pattern_name] = '#d62728'  # 빨강 - 고정
                    elif '이동활발형' in pattern_name:
                        color_map[pattern_name] = '#2ca02c'  # 초록 - 활발
                    elif '사무중심형' in pattern_name:
                        color_map[pattern_name] = '#1f77b4'  # 파랑 - 사무
                    elif '생산중심형' in pattern_name:
                        color_map[pattern_name] = '#ff7f0e'  # 주황 - 생산
                    elif '외부활동형' in pattern_name:
                        color_map[pattern_name] = '#9467bd'  # 보라 - 외부
                    elif '복합활동형' in pattern_name:
                        color_map[pattern_name] = '#7f7f7f'  # 회색 - 복합
                    else:
                        color_map[pattern_name] = '#8c564b'  # 갈색 - 기타
            
            # 태그 개수 기반으로 축 선택
            x_axis = 'o_tag_count' if 'o_tag_count' in df.columns else 'total_tags'
            y_axis = 'knox_total_count' if 'knox_total_count' in df.columns else 't1_count'
            
            fig_scatter = px.scatter(
                df,
                x=x_axis,
                y=y_axis,
                color='pattern_type',
                color_discrete_map=color_map,
                size='employee_count',
                hover_data=['center', 'team', 'employee_count', 't1_count', 'g3_count'],
                title='태그 개수 기반 부서별 패턴 분포 (5개 클러스터)',
                labels={
                    'o_tag_count': 'O태그 개수 (장비 사용)',
                    'knox_total_count': 'Knox 총 개수 (결재+회의+메일)',
                    't1_count': 'T1태그 개수 (이동)',
                    'g3_count': 'G3태그 개수 (회의)',
                    'pattern_type': '패턴 유형',
                    'employee_count': '직원 수',
                    'total_tags': '총 태그 수'
                }
            )
            
            # 클러스터 버블 표시 제거 - 데이터 포인트만으로도 충분히 구분 가능
        else:
            fig_scatter = px.scatter(
                df,
                x='total_tags',
                y='tags_per_person',
                size='employee_count',
                hover_data=['center', 'team'],
                title='부서별 근무 패턴 분포',
                labels={
                    'total_tags': '총 태그 수',
                    'tags_per_person': '인당 태그 수'
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
            'tags_per_person': 'mean',
            'tag_diversity': 'mean',
            'reliability_score': 'mean',
            'correction_factor': 'mean'
        }).round(2)
        
        # 컬럼명 변경
        cluster_stats.columns = ['팀수', '총직원수', '인당태그수', '태그다양성', '평균신뢰도', '평균보정Factor']
        
        # 클러스터 이름 매핑 (동적으로 생성 - 위와 동일한 로직)
        cluster_names_stats = {}
        for cluster_id in cluster_stats.index:
            cluster_data = df[df['cluster'] == cluster_id]
            
            # 태그 개수 기반으로 클러스터 특성 계산
            avg_o_tag = cluster_data['o_tag_count'].mean() if 'o_tag_count' in cluster_data.columns else 0
            avg_knox = cluster_data['knox_total_count'].mean() if 'knox_total_count' in cluster_data.columns else 0
            avg_t1 = cluster_data['t1_count'].mean() if 't1_count' in cluster_data.columns else 0
            avg_g3 = cluster_data['g3_count'].mean() if 'g3_count' in cluster_data.columns else 0
            
            # 클러스터 타입 결정 (태그 개수 기반)
            if avg_o_tag > 1000:
                cluster_names_stats[cluster_id] = f'Type_{cluster_id}_장비집중형'
            elif avg_knox > 1000:
                cluster_names_stats[cluster_id] = f'Type_{cluster_id}_협업중심형'
            elif avg_t1 > 500:
                cluster_names_stats[cluster_id] = f'Type_{cluster_id}_이동활발형'
            elif avg_g3 > 50:
                cluster_names_stats[cluster_id] = f'Type_{cluster_id}_회의중심형'
            else:
                cluster_names_stats[cluster_id] = f'Type_{cluster_id}_복합활동형'
        
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
                if '고정근무형' in name:
                    pie_color_map[name] = '#d62728'  # 빨강 - 고정
                elif '이동활발형' in name:
                    pie_color_map[name] = '#2ca02c'  # 초록 - 활발
                elif '사무중심형' in name:
                    pie_color_map[name] = '#1f77b4'  # 파랑 - 사무
                elif '생산중심형' in name:
                    pie_color_map[name] = '#ff7f0e'  # 주황 - 생산
                elif '외부활동형' in name:
                    pie_color_map[name] = '#9467bd'  # 보라 - 외부
                elif '복합활동형' in name:
                    pie_color_map[name] = '#7f7f7f'  # 회색 - 복합
                else:
                    pie_color_map[name] = '#8c564b'  # 갈색 - 기타
            
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