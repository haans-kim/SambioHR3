"""
llm_pattern_analysis.py
LLM 기반 패턴 분석 UI 컴포넌트
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
import os
import json

# 분석 라이브러리 경로 추가
analysis_path = os.path.join(os.path.dirname(__file__), '../../../scripts/analysis')
if analysis_path not in sys.path:
    sys.path.insert(0, analysis_path)

try:
    # 모듈 리로딩 강제
    import importlib
    import lib.llm_analyzer
    importlib.reload(lib.llm_analyzer)
    from lib.llm_analyzer import LLMPatternAnalyzer
except ImportError:
    st.error("LLM 분석 라이브러리를 찾을 수 없습니다.")
    LLMPatternAnalyzer = None

def render_page():
    """LLM 기반 분석 페이지 렌더링"""
    
    st.title("AI 기반 지능형 패턴 분석")
    st.markdown("---")
    
    # 사이드바 설정
    with st.sidebar:
        st.header("분석 설정")
        
        analysis_type = st.selectbox(
            "분석 유형 선택",
            ["clustering", "anomaly", "benchmarking", "prediction"],
            format_func=lambda x: {
                "clustering": "패턴 기반 그룹화",
                "anomaly": "이상치 탐지",
                "benchmarking": "벤치마킹 분석",
                "prediction": "예측 및 추천"
            }[x]
        )
        
        st.markdown("---")
        
        # 최소 직원수 설정
        min_employees = st.slider(
            "최소 직원수 기준",
            min_value=1,
            max_value=20,
            value=5,
            help="분석에 포함할 팀의 최소 직원수를 설정합니다. 직원수가 너무 적은 팀은 통계적 신뢰도가 낮아 제외됩니다."
        )
        
        st.markdown("---")
        
        st.markdown("""
        ### LLM 분석의 장점
        
        - **의미론적 해석**: 단순 수치가 아닌 비즈니스 맥락 이해
        - **자연어 인사이트**: 이해하기 쉬운 설명 제공
        - **복잡한 패턴 인식**: 다차원 데이터의 숨은 관계 발견
        - **맞춤형 추천**: 각 팀별 개선 방향 제시
        """)
    
    # 메인 탭
    tab1, tab2, tab3, tab4 = st.tabs([
        "데이터 개요", 
        "AI 분석", 
        "시각화", 
        "인사이트"
    ])
    
    with tab1:
        render_data_overview(min_employees)
    
    with tab2:
        render_ai_analysis(analysis_type, min_employees)
    
    with tab3:
        render_visualization(min_employees)
    
    with tab4:
        render_insights()

def render_data_overview(min_employees=5):
    """데이터 개요 탭"""
    
    st.header("분석 대상 데이터")
    
    if LLMPatternAnalyzer is None:
        st.error("분석기를 로드할 수 없습니다.")
        return
    
    # 분석기 초기화
    analyzer = LLMPatternAnalyzer(db_path='data/sambio_human.db')
    df = analyzer.prepare_data_for_llm(min_employees=min_employees)
    
    # 주요 통계
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("분석 대상 팀", f"{len(df)}개")
    
    with col2:
        st.metric("총 직원 수", f"{df['employee_count'].sum():,}명")
    
    with col3:
        avg_knox = df['knox_per_person'].mean()
        st.metric("평균 Knox 활동", f"{avg_knox:.1f}건/인")
    
    with col4:
        avg_equipment = df['o_per_person'].mean()
        st.metric("평균 장비 사용", f"{avg_equipment:.1f}건/인")
    
    st.markdown("---")
    
    # 데이터 미리보기
    st.subheader("팀별 주요 지표")
    
    # 표시할 컬럼 선택
    display_cols = [
        'team', 'employee_count',
        'knox_per_person', 'o_per_person', 
        'g3_per_person', 't1_per_person'
    ]
    
    # 컬럼명 한글화
    col_rename = {
        'team': '팀명',
        'employee_count': '직원수',
        'knox_per_person': 'Knox/인',
        'o_per_person': '장비/인',
        'g3_per_person': '회의/인',
        't1_per_person': '이동/인'
    }
    
    display_df = df[display_cols].rename(columns=col_rename)
    
    # 상위 20개 팀 표시
    st.dataframe(
        display_df.head(20).style.format({
            'Knox/인': '{:.1f}',
            '장비/인': '{:.1f}',
            '회의/인': '{:.1f}',
            '이동/인': '{:.1f}'
        }),
        use_container_width=True,
        height=400
    )

def render_ai_analysis(analysis_type, min_employees=5):
    """AI 분석 탭"""
    
    st.header("AI 기반 패턴 분석")
    
    # LLM 선택 옵션 추가
    col1, col2 = st.columns([3, 1])
    with col1:
        llm_option = st.selectbox(
            "분석 엔진 선택",
            ["규칙 기반 (무료)", "OpenAI GPT-4 (유료)"],
            help="GPT-4를 사용하면 더 정교한 분석이 가능합니다"
        )
    
    with col2:
        if llm_option == "OpenAI GPT-4 (유료)":
            st.info("예상 비용: ~$0.03")
    
    # 제외된 팀 정보 표시
    st.info(f"분석 기준: 직원수 {min_employees}명 이상의 실제 팀만 포함 (상위 조직 및 담당 레벨 제외)")
    
    # 분석 실행 버튼
    if st.button("AI 분석 실행", type="primary"):
        if llm_option == "OpenAI GPT-4 (유료)":
            # OpenAI GPT 사용
            try:
                # OpenAI 분석기 import
                from lib.llm_analyzer_openai import LLMPatternAnalyzerWithOpenAI
                
                with st.spinner("GPT-4가 데이터를 분석하고 있습니다..."):
                    # API 키 설정 (실제 운영 시에는 환경변수나 secrets에서 가져와야 함)
                    api_key = os.environ.get('OPENAI_API_KEY', 'YOUR_API_KEY_HERE')
                    
                    if api_key == 'YOUR_API_KEY_HERE':
                        st.error("OpenAI API 키가 설정되지 않았습니다. 환경변수 OPENAI_API_KEY를 설정해주세요.")
                        return
                    
                    # GPT 분석기 초기화
                    gpt_analyzer = LLMPatternAnalyzerWithOpenAI(
                        db_path='data/sambio_human.db',
                        api_key=api_key
                    )
                    
                    # 데이터 준비
                    gpt_analyzer.prepare_data_for_llm(min_employees=min_employees)
                    
                    # GPT 분석 실행
                    result = gpt_analyzer.analyze_with_gpt(analysis_type, min_employees=min_employees)
                    
                    # 세션에 저장
                    st.session_state['llm_analysis_result'] = result
                    
                    # LLM 사용 정보 표시
                    if 'llm_used' in result:
                        st.success(f"✅ 분석 완료! (사용된 엔진: {result['llm_used']})")
                        
                        # 토큰 사용량 표시
                        if 'tokens_used' in result:
                            estimated_cost = result['tokens_used'] * 0.00002
                            st.info(f"📊 토큰 사용: {result['tokens_used']:,}개 | 💰 예상 비용: ${estimated_cost:.4f}")
                    else:
                        st.success("분석이 완료되었습니다!")
                        
            except ImportError:
                st.error("OpenAI 분석기를 로드할 수 없습니다. 규칙 기반으로 전환합니다.")
                # 폴백: 규칙 기반 사용
                use_rule_based = True
            except Exception as e:
                st.error(f"GPT 분석 중 오류 발생: {str(e)}")
                st.info("규칙 기반 분석으로 전환합니다.")
                use_rule_based = True
        else:
            use_rule_based = True
        
        # 규칙 기반 분석
        if llm_option == "규칙 기반 (무료)" or 'use_rule_based' in locals():
            if LLMPatternAnalyzer is None:
                st.error("분석기를 로드할 수 없습니다.")
                return
                
            with st.spinner("AI가 데이터를 분석하고 있습니다... (약 10초)"):
                # 분석기 초기화
                analyzer = LLMPatternAnalyzer(db_path='data/sambio_human.db')
                
                # 최소 직원수 설정 적용
                analyzer.prepare_data_for_llm(min_employees=min_employees)
                
                # 분석 실행
                result = analyzer.analyze_with_llm(analysis_type, min_employees=min_employees)
                
                # 세션에 저장
                st.session_state['llm_analysis_result'] = result
                
                st.success("✅ 분석 완료! (규칙 기반 엔진 사용)")
    
    # 분석 결과 표시
    if 'llm_analysis_result' in st.session_state:
        result = st.session_state['llm_analysis_result']
        
        st.markdown("---")
        
        # LLM 사용 정보를 상단에 표시
        if 'llm_used' in result:
            with st.expander("🔍 분석 엔진 상세 정보", expanded=False):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("사용된 엔진", result.get('llm_used', 'Unknown'))
                with col2:
                    if 'tokens_used' in result:
                        st.metric("토큰 사용량", f"{result.get('tokens_used', 0):,}")
                with col3:
                    if 'tokens_used' in result:
                        cost = result.get('tokens_used', 0) * 0.00002
                        st.metric("실제 비용", f"${cost:.4f}")
                
                # 원시 응답 데이터 표시 (디버깅용)
                if st.checkbox("🔧 디버그 정보 표시"):
                    st.json({
                        "analysis_type": result.get('analysis_type'),
                        "timestamp": result.get('timestamp'),
                        "llm_used": result.get('llm_used'),
                        "tokens_used": result.get('tokens_used', 0),
                        "total_teams": result.get('total_teams'),
                        "total_employees": result.get('total_employees'),
                        "num_clusters": len(result.get('clusters', {}))
                    })
        
        # 클러스터 정보
        st.subheader("발견된 패턴 그룹")
        
        clusters = result.get('clusters', {})
        
        # 클러스터 요약 테이블
        cluster_data = []
        for cluster_name, info in clusters.items():
            # 전체 팀 목록이 있으면 사용, 없으면 teams 사용
            all_teams = info.get('all_teams', info.get('teams', []))
            
            # 대표 팀 3개 선택 (전체가 3개 이하면 전체 표시)
            if len(all_teams) <= 3:
                display_teams = ', '.join(all_teams)
            else:
                display_teams = f"{', '.join(all_teams[:3])} 외 {len(all_teams)-3}개"
            
            cluster_data.append({
                '패턴 유형': cluster_name,
                '팀 수': f"{info['team_count']}개",
                '직원 수': f"{info['total_employees']:,}명",
                '평균 Knox': f"{info['avg_knox']:.1f}",
                '평균 장비': f"{info['avg_equipment']:.1f}",
                '주요 팀': display_teams
            })
        
        if cluster_data:
            cluster_df = pd.DataFrame(cluster_data)
            # 팀 수 기준으로 정렬
            cluster_df = cluster_df.sort_values('팀 수', ascending=False)
            st.dataframe(cluster_df, use_container_width=True)
        
        # 주요 인사이트
        st.markdown("---")
        st.subheader("주요 발견사항")
        
        insights = result.get('insights', [])
        for insight in insights:
            st.info(insight)
        
        # 각 클러스터별 상세 정보
        st.markdown("---")
        st.subheader("패턴별 상세 분석")
        
        for cluster_name, info in clusters.items():
            with st.expander(f"{cluster_name} ({info['team_count']}개 팀)", expanded=True):
                # 4개 메트릭을 한 행에 표시
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("소속 팀 수", f"{info['team_count']}개")
                
                with col2:
                    st.metric("총 직원 수", f"{info['total_employees']:,}명")
                
                with col3:
                    st.metric("평균 Knox 활동", f"{info['avg_knox']:.1f}건/인")
                
                with col4:
                    st.metric("평균 장비 사용", f"{info['avg_equipment']:.1f}건/인")
                
                st.markdown(f"**소속 팀 전체 목록 ({info['team_count']}개):**")
                
                # 센터별로 그룹화된 팀 목록 가져오기
                teams_by_center = info.get('teams_by_center', {})
                
                if teams_by_center:
                    # 팀 수가 많은 센터부터 정렬
                    sorted_centers = sorted(teams_by_center.items(), 
                                          key=lambda x: len(x[1]), 
                                          reverse=True)
                    
                    # 테이블 데이터 준비
                    table_data = []
                    for center, teams in sorted_centers:
                        table_data.append({
                            '센터': center,
                            '팀 수': f"{len(teams)}개",
                            '소속 팀': ", ".join(teams)
                        })
                    
                    # DataFrame으로 변환하여 표시
                    center_df = pd.DataFrame(table_data)
                    
                    # 컴팩트한 테이블로 표시
                    st.dataframe(
                        center_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            '센터': st.column_config.TextColumn('센터', width='small'),
                            '팀 수': st.column_config.TextColumn('팀 수', width='small'),
                            '소속 팀': st.column_config.TextColumn('소속 팀', width='large')
                        }
                    )
                else:
                    # 센터 정보가 없는 경우 기존 방식으로 표시
                    all_teams = info.get('all_teams', info.get('teams', []))
                    teams_text = ", ".join(all_teams)
                    st.info(teams_text)
                
                st.markdown("---")
                
                # 추천사항 생성
                try:
                    if 'llm_analyzer_instance' not in st.session_state:
                        st.session_state['llm_analyzer_instance'] = LLMPatternAnalyzer(db_path='data/sambio_human.db')
                    
                    analyzer = st.session_state['llm_analyzer_instance']
                    recommendations = analyzer.generate_recommendations(cluster_name)
                except Exception as e:
                    # 오류 발생시 기본 추천사항 제공
                    recommendations = ["추가 분석이 필요합니다."]
                
                st.markdown("**개선 추천사항:**")
                for rec in recommendations:
                    st.write(f"• {rec}")

def render_visualization(min_employees=5):
    """시각화 탭"""
    
    st.header("패턴 시각화")
    
    if LLMPatternAnalyzer is None:
        st.error("분석기를 로드할 수 없습니다.")
        return
    
    # 분석기 초기화
    analyzer = LLMPatternAnalyzer(db_path='data/sambio_human.db')
    analyzer.prepare_data_for_llm(min_employees=min_employees)
    viz_df = analyzer.export_for_visualization(min_employees=min_employees)
    
    # 여러 차원의 산점도 옵션 제공
    st.subheader("다차원 패턴 분석")
    
    # 축 선택 옵션
    col1, col2 = st.columns(2)
    with col1:
        x_axis_option = st.selectbox(
            "X축 선택",
            options=[
                ('o_per_person', '장비 사용 (건/인)'),
                ('knox_per_person', 'Knox 협업 (건/인)'),
                ('t1_per_person', '이동 활동 (건/인)'),
                ('g3_per_person', '회의 참여 (건/인)'),
                ('total_activity', '총 활동량 (건/인)'),
                ('digital_ratio', '디지털 활동 비율 (%)')
            ],
            format_func=lambda x: x[1],
            index=0
        )
    
    with col2:
        y_axis_option = st.selectbox(
            "Y축 선택",
            options=[
                ('knox_per_person', 'Knox 협업 (건/인)'),
                ('o_per_person', '장비 사용 (건/인)'),
                ('t1_per_person', '이동 활동 (건/인)'),
                ('g3_per_person', '회의 참여 (건/인)'),
                ('activity_diversity', '활동 다양성 지수'),
                ('mobility_index', '이동성 지수')
            ],
            format_func=lambda x: x[1],
            index=0
        )
    
    # 선택된 축에 대한 데이터 준비
    x_col, x_label = x_axis_option
    y_col, y_label = y_axis_option
    
    # 추가 지표 계산 (필요한 경우)
    if 'total_activity' not in viz_df.columns:
        viz_df['total_activity'] = viz_df['knox_per_person'] + viz_df['o_per_person'] + viz_df['t1_per_person'] + viz_df['g3_per_person']
    
    if 'digital_ratio' not in viz_df.columns:
        viz_df['digital_ratio'] = (viz_df['knox_per_person'] / viz_df['total_activity'].replace(0, 1)) * 100
    
    if 'activity_diversity' not in viz_df.columns:
        # 활동 다양성 = 각 활동 유형의 분산
        viz_df['activity_diversity'] = viz_df[['knox_per_person', 'o_per_person', 't1_per_person', 'g3_per_person']].std(axis=1)
    
    if 'mobility_index' not in viz_df.columns:
        # 이동성 지수 = 이동 활동 / 총 활동
        viz_df['mobility_index'] = (viz_df['t1_per_person'] / viz_df['total_activity'].replace(0, 1)) * 100
    
    # 스케일 정규화 옵션
    use_log_scale = st.checkbox("로그 스케일 사용 (데이터 분포가 치우친 경우)", value=False)
    
    # 색상 맵 정의 (일관된 색상 사용)
    color_map = {
        '장비운영집중형': '#1f77b4',  # 파란색
        '현장이동활발형': '#ff7f0e',  # 주황색
        '디지털협업중심형': '#2ca02c',  # 녹색
        '균형업무형': '#d62728',  # 빨간색
        '회의협업중심형': '#9467bd',  # 보라색
        '저활동형': '#8c564b'  # 갈색
    }
    
    # 산점도 생성
    fig_scatter = px.scatter(
        viz_df,
        x=x_col,
        y=y_col,
        color='cluster',
        size='employee_count',
        hover_data=['team', 'employee_count', 'knox_per_person', 'o_per_person'],
        title=f'{x_label} vs {y_label} 패턴 분포 (수정된 클러스터링)',
        labels={
            x_col: x_label,
            y_col: y_label,
            'cluster': '패턴 유형',
            'employee_count': '직원 수'
        },
        color_discrete_map=color_map
    )
    
    # 로그 스케일 적용 (선택시)
    if use_log_scale:
        fig_scatter.update_xaxes(type='log', title=f'{x_label} (로그 스케일)')
        fig_scatter.update_yaxes(type='log', title=f'{y_label} (로그 스케일)')
    else:
        # 축 범위를 실제 데이터에 맞게 동적 조정 (여유 10% 추가)
        # Y축: 실제 최대값 기준으로 설정
        y_max = viz_df[y_col].max()
        y_range = [0, y_max * 1.1] if y_max > 0 else [0, 100]
        fig_scatter.update_yaxes(range=y_range)
        
        # X축: 실제 최대값 기준으로 설정
        x_max = viz_df[x_col].max()
        x_range = [0, x_max * 1.1] if x_max > 0 else [0, 100]
        fig_scatter.update_xaxes(range=x_range)
    
    # 그리드 라인 추가로 가독성 향상
    fig_scatter.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
    fig_scatter.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
    
    fig_scatter.update_layout(height=600)
    st.plotly_chart(fig_scatter, use_container_width=True)
    
    st.markdown("---")
    
    # PCA를 이용한 차원 축소 시각화
    st.subheader("주성분 분석 (PCA) 기반 클러스터 시각화")
    
    try:
        from sklearn.preprocessing import StandardScaler
        from sklearn.decomposition import PCA
        
        # 분석에 사용할 특징들
        feature_cols = ['knox_per_person', 'o_per_person', 't1_per_person', 'g3_per_person']
        X = viz_df[feature_cols].values
        
        # 데이터 정규화
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # PCA 수행
        pca = PCA(n_components=2)
        X_pca = pca.fit_transform(X_scaled)
        
        # PCA 결과를 데이터프레임에 추가
        viz_df['pca_1'] = X_pca[:, 0]
        viz_df['pca_2'] = X_pca[:, 1]
        
        # PCA 설명력 표시
        explained_var = pca.explained_variance_ratio_
        st.info(f"주성분 1: {explained_var[0]:.1%} 설명력 | 주성분 2: {explained_var[1]:.1%} 설명력 | 총 {sum(explained_var):.1%} 설명력")
        
        # PCA 산점도
        fig_pca = px.scatter(
            viz_df,
            x='pca_1',
            y='pca_2',
            color='cluster',
            size='employee_count',
            hover_data=['team', 'employee_count', 'knox_per_person', 'o_per_person'],
            title='PCA 기반 팀 패턴 클러스터링 (차원 축소 시각화)',
            labels={
                'pca_1': f'주성분 1 ({explained_var[0]:.1%})',
                'pca_2': f'주성분 2 ({explained_var[1]:.1%})',
                'cluster': '패턴 유형',
                'employee_count': '직원 수'
            }
        )
        
        # 클러스터 중심점 표시
        for cluster in viz_df['cluster'].unique():
            cluster_data = viz_df[viz_df['cluster'] == cluster]
            center_x = cluster_data['pca_1'].mean()
            center_y = cluster_data['pca_2'].mean()
            
            # 클러스터 이름 주석 추가
            fig_pca.add_annotation(
                x=center_x,
                y=center_y,
                text=cluster,
                showarrow=False,
                font=dict(size=10, color='black'),
                bgcolor='rgba(255, 255, 255, 0.7)'
            )
        
        fig_pca.update_layout(height=600)
        fig_pca.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray', zeroline=True, zerolinewidth=2)
        fig_pca.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray', zeroline=True, zerolinewidth=2)
        st.plotly_chart(fig_pca, use_container_width=True)
        
    except ImportError:
        st.warning("PCA 분석을 위해서는 scikit-learn 라이브러리가 필요합니다.")
    
    st.markdown("---")
    
    # 2. 박스플롯 - 클러스터별 분포
    st.subheader("패턴별 지표 분포")
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig_box_knox = px.box(
            viz_df,
            x='cluster',
            y='knox_per_person',
            title='패턴별 Knox 활동 분포',
            labels={
                'cluster': '패턴 유형',
                'knox_per_person': 'Knox 활동 (건/인)'
            }
        )
        fig_box_knox.update_layout(height=400)
        st.plotly_chart(fig_box_knox, use_container_width=True)
    
    with col2:
        fig_box_equipment = px.box(
            viz_df,
            x='cluster',
            y='o_per_person',
            title='패턴별 장비 사용 분포',
            labels={
                'cluster': '패턴 유형',
                'o_per_person': '장비 사용 (건/인)'
            }
        )
        fig_box_equipment.update_layout(height=400)
        st.plotly_chart(fig_box_equipment, use_container_width=True)
    
    # 3. 3D 산점도 옵션
    st.subheader("3D 패턴 시각화")
    
    use_3d = st.checkbox("3D 시각화 활성화", value=False)
    
    if use_3d:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            x_3d = st.selectbox(
                "X축 (3D)",
                options=['knox_per_person', 'o_per_person', 't1_per_person', 'g3_per_person'],
                format_func=lambda x: {
                    'knox_per_person': 'Knox 협업',
                    'o_per_person': '장비 사용',
                    't1_per_person': '이동 활동',
                    'g3_per_person': '회의 참여'
                }[x]
            )
        
        with col2:
            y_3d = st.selectbox(
                "Y축 (3D)",
                options=['o_per_person', 'knox_per_person', 't1_per_person', 'g3_per_person'],
                format_func=lambda x: {
                    'knox_per_person': 'Knox 협업',
                    'o_per_person': '장비 사용',
                    't1_per_person': '이동 활동',
                    'g3_per_person': '회의 참여'
                }[x]
            )
        
        with col3:
            z_3d = st.selectbox(
                "Z축 (3D)",
                options=['t1_per_person', 'g3_per_person', 'knox_per_person', 'o_per_person'],
                format_func=lambda x: {
                    'knox_per_person': 'Knox 협업',
                    'o_per_person': '장비 사용',
                    't1_per_person': '이동 활동',
                    'g3_per_person': '회의 참여'
                }[x]
            )
        
        fig_3d = px.scatter_3d(
            viz_df,
            x=x_3d,
            y=y_3d,
            z=z_3d,
            color='cluster',
            size='employee_count',
            hover_data=['team', 'employee_count'],
            title='3D 공간에서의 팀 패턴 분포',
            labels={
                'cluster': '패턴 유형',
                'employee_count': '직원 수'
            }
        )
        
        fig_3d.update_layout(height=700)
        st.plotly_chart(fig_3d, use_container_width=True)
    
    st.markdown("---")
    
    # 4. 히트맵 - 상관관계
    st.subheader("지표간 상관관계")
    
    correlation_cols = ['knox_per_person', 'o_per_person', 't1_per_person', 'g3_per_person']
    corr_matrix = viz_df[correlation_cols].corr()
    
    fig_heatmap = px.imshow(
        corr_matrix,
        labels=dict(x="지표", y="지표", color="상관계수"),
        x=['Knox 협업', '장비 사용', '이동', '회의'],
        y=['Knox 협업', '장비 사용', '이동', '회의'],
        color_continuous_scale='RdBu',
        aspect='auto'
    )
    
    fig_heatmap.update_layout(height=400)
    st.plotly_chart(fig_heatmap, use_container_width=True)

def render_insights():
    """인사이트 탭"""
    
    st.header("AI 인사이트 및 추천")
    
    # 전략적 인사이트
    st.subheader("전략적 인사이트")
    
    st.markdown("""
    ### 조직 전체 분석 결과
    
    **1. 디지털 전환 수준**
    - 전체 평균 Knox 활동이 93.1건/인으로 디지털 협업이 활발함
    - 상위 25% 팀들은 150건/인 이상의 높은 디지털 활용도
    - 하위 25% 팀들은 디지털 전환 교육 필요
    
    **2. 업무 패턴 다양성**
    - 6개의 명확한 업무 패턴 그룹 식별
    - 장비운영집중형(28팀)과 디지털협업중심형(25팀)이 주요 패턴
    - 각 패턴별 맞춤형 개선 전략 필요
    
    **3. 효율성 개선 기회**
    - 현장이동활발형 팀들의 모바일 시스템 도입 시급
    - 저활동형 팀들의 업무 프로세스 재설계 필요
    - 균형업무형 팀들을 벤치마킹 대상으로 활용
    """)
    
    # 액션 플랜
    st.markdown("---")
    st.subheader("실행 계획")
    
    action_plans = {
        "단기 (1-3개월)": [
            "디지털 협업 우수 팀 사례 공유 세션 개최",
            "저활동 팀 대상 집중 컨설팅 실시",
            "모바일 업무 시스템 파일럿 프로젝트 시작"
        ],
        "중기 (3-6개월)": [
            "패턴별 맞춤형 교육 프로그램 개발",
            "장비 운영 효율성 모니터링 시스템 구축",
            "디지털 워크플로우 자동화 확대"
        ],
        "장기 (6-12개월)": [
            "AI 기반 업무 최적화 시스템 도입",
            "전사 디지털 트윈 구축",
            "데이터 기반 의사결정 체계 확립"
        ]
    }
    
    for period, plans in action_plans.items():
        with st.expander(period):
            for plan in plans:
                st.write(f"- {plan}")
    
    # 다운로드 버튼
    st.markdown("---")
    
    if 'llm_analysis_result' in st.session_state:
        result = st.session_state['llm_analysis_result']
        
        # JSON 다운로드
        json_str = json.dumps(result, ensure_ascii=False, indent=2)
        st.download_button(
            label="분석 결과 다운로드 (JSON)",
            data=json_str,
            file_name="ai_pattern_analysis.json",
            mime="application/json"
        )
        
        # 리포트 생성 버튼
        if st.button("상세 리포트 생성"):
            st.info("PDF 리포트 생성 기능은 추후 구현 예정입니다.")

# 메인 앱에서 import하여 사용