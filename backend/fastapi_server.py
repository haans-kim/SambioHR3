#!/usr/bin/env python3
"""
FastAPI 백엔드 서버
Mock 또는 실제 분석 DB와 연동하여 React UI에 데이터 제공
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any
import sqlite3
import pandas as pd
import json
from pathlib import Path
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 앱 초기화
app = FastAPI(
    title="Sambio Analytics API",
    description="조직 분석 대시보드 API",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # React 개발 서버
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB 경로 설정
project_root = Path(__file__).parent.parent
# Mock DB를 기본으로 사용 (실제 분석 완료 후 변경)
DB_PATH = project_root / 'data' / 'sambio_analytics_mock.db'
# DB_PATH = project_root / 'data' / 'sambio_analytics.db'  # 실제 분석 DB


def get_db_connection():
    """DB 연결 생성"""
    if not DB_PATH.exists():
        raise HTTPException(status_code=500, detail=f"Database not found: {DB_PATH}")
    return sqlite3.connect(str(DB_PATH))


@app.get("/")
async def root():
    """API 상태 확인"""
    return {
        "status": "running",
        "api": "Sambio Analytics API",
        "version": "1.0.0",
        "database": DB_PATH.name,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/centers")
async def get_centers(
    analysis_date: date = Query(..., description="분석 날짜 (YYYY-MM-DD)")
):
    """센터 목록 및 요약 정보"""
    try:
        conn = get_db_connection()
        query = """
            SELECT 
                center_id,
                center_name,
                total_employees,
                analyzed_employees,
                total_teams,
                avg_efficiency_ratio,
                avg_work_hours,
                avg_focus_ratio,
                team_performance,
                grade_distribution
            FROM center_daily_summary
            WHERE analysis_date = ?
            ORDER BY center_name
        """
        
        df = pd.read_sql_query(query, conn, params=(analysis_date.isoformat(),))
        conn.close()
        
        # JSON 필드 파싱
        records = df.to_dict('records')
        for record in records:
            if record.get('team_performance'):
                try:
                    record['team_performance'] = json.loads(record['team_performance'])
                except:
                    record['team_performance'] = {}
            if record.get('grade_distribution'):
                try:
                    record['grade_distribution'] = json.loads(record['grade_distribution'])
                except:
                    record['grade_distribution'] = {}
        
        return {
            "date": analysis_date.isoformat(),
            "total_centers": len(records),
            "centers": records
        }
        
    except Exception as e:
        logger.error(f"Error fetching centers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/teams/{center_id}")
async def get_teams_by_center(
    center_id: str,
    analysis_date: date = Query(..., description="분석 날짜")
):
    """특정 센터의 팀 목록"""
    try:
        conn = get_db_connection()
        query = """
            SELECT 
                team_id,
                team_name,
                center_id,
                center_name,
                total_employees,
                analyzed_employees,
                avg_efficiency_ratio,
                avg_work_hours,
                avg_focus_ratio,
                avg_productivity_score,
                grade_distribution,
                efficiency_by_grade
            FROM team_daily_summary
            WHERE center_id = ? AND analysis_date = ?
            ORDER BY team_name
        """
        
        df = pd.read_sql_query(query, conn, params=(center_id, analysis_date.isoformat()))
        conn.close()
        
        # JSON 필드 파싱
        records = df.to_dict('records')
        for record in records:
            for field in ['grade_distribution', 'efficiency_by_grade']:
                if record.get(field):
                    try:
                        record[field] = json.loads(record[field])
                    except:
                        record[field] = {}
        
        return {
            "center_id": center_id,
            "date": analysis_date.isoformat(),
            "total_teams": len(records),
            "teams": records
        }
        
    except Exception as e:
        logger.error(f"Error fetching teams: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/groups/{team_id}")
async def get_groups_by_team(
    team_id: str,
    analysis_date: date = Query(..., description="분석 날짜")
):
    """특정 팀의 그룹별 집계"""
    try:
        conn = get_db_connection()
        query = """
            SELECT 
                group_id,
                group_name,
                COUNT(DISTINCT employee_id) as total_employees,
                AVG(efficiency_ratio) as avg_efficiency_ratio,
                AVG(work_hours) as avg_work_hours,
                AVG(focus_ratio) as avg_focus_ratio,
                AVG(productivity_score) as avg_productivity_score
            FROM daily_analysis
            WHERE team_id = ? AND analysis_date = ?
                AND group_id IS NOT NULL
            GROUP BY group_id, group_name
            ORDER BY group_name
        """
        
        df = pd.read_sql_query(query, conn, params=(team_id, analysis_date.isoformat()))
        conn.close()
        
        records = df.to_dict('records')
        
        return {
            "team_id": team_id,
            "date": analysis_date.isoformat(),
            "total_groups": len(records),
            "groups": records
        }
        
    except Exception as e:
        logger.error(f"Error fetching groups: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/employees/{team_id}")
async def get_employees_by_team(
    team_id: str,
    analysis_date: date = Query(..., description="분석 날짜"),
    group_id: Optional[str] = Query(None, description="그룹 ID (선택)")
):
    """특정 팀/그룹의 직원 상세"""
    try:
        conn = get_db_connection()
        
        # 기본 쿼리
        query = """
            SELECT 
                employee_id,
                employee_name,
                job_grade,
                group_id,
                group_name,
                total_hours,
                work_hours,
                focused_work_hours,
                meeting_hours,
                break_hours,
                meal_hours,
                efficiency_ratio,
                focus_ratio,
                productivity_score,
                breakfast_taken,
                lunch_taken,
                dinner_taken,
                midnight_meal_taken,
                peak_hours,
                activity_distribution,
                claim_hours,
                claim_vs_actual_diff
            FROM daily_analysis
            WHERE team_id = ? AND analysis_date = ?
        """
        
        params = [team_id, analysis_date.isoformat()]
        
        # 그룹 필터 추가
        if group_id:
            query += " AND group_id = ?"
            params.append(group_id)
        
        query += " ORDER BY efficiency_ratio DESC"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        # JSON 필드 파싱
        records = df.to_dict('records')
        for record in records:
            for field in ['peak_hours', 'activity_distribution']:
                if record.get(field):
                    try:
                        record[field] = json.loads(record[field])
                    except:
                        record[field] = []
        
        return {
            "team_id": team_id,
            "group_id": group_id,
            "date": analysis_date.isoformat(),
            "total_employees": len(records),
            "employees": records
        }
        
    except Exception as e:
        logger.error(f"Error fetching employees: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/employee/{employee_id}")
async def get_employee_detail(
    employee_id: str,
    analysis_date: date = Query(..., description="분석 날짜")
):
    """특정 직원 상세 정보"""
    try:
        conn = get_db_connection()
        query = """
            SELECT *
            FROM daily_analysis
            WHERE employee_id = ? AND analysis_date = ?
        """
        
        df = pd.read_sql_query(query, conn, params=(employee_id, analysis_date.isoformat()))
        conn.close()
        
        if df.empty:
            raise HTTPException(status_code=404, detail="Employee data not found")
        
        record = df.to_dict('records')[0]
        
        # JSON 필드 파싱
        for field in ['peak_hours', 'activity_distribution', 'location_patterns', 'hourly_efficiency']:
            if record.get(field):
                try:
                    record[field] = json.loads(record[field])
                except:
                    record[field] = {}
        
        return record
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching employee detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/employee/{employee_id}/trend")
async def get_employee_trend(
    employee_id: str,
    days: int = Query(default=30, description="조회 기간 (일)")
):
    """직원 추세 데이터"""
    try:
        conn = get_db_connection()
        query = """
            SELECT 
                analysis_date,
                efficiency_ratio,
                work_hours,
                focus_ratio,
                productivity_score,
                claim_hours,
                claim_vs_actual_diff
            FROM daily_analysis
            WHERE employee_id = ?
            ORDER BY analysis_date DESC
            LIMIT ?
        """
        
        df = pd.read_sql_query(query, conn, params=(employee_id, days))
        conn.close()
        
        # 날짜순 정렬 (오래된 것부터)
        df = df.sort_values('analysis_date')
        records = df.to_dict('records')
        
        return {
            "employee_id": employee_id,
            "days": days,
            "trend_data": records
        }
        
    except Exception as e:
        logger.error(f"Error fetching employee trend: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics/summary")
async def get_analytics_summary(
    analysis_date: date = Query(..., description="분석 날짜")
):
    """전체 요약 통계"""
    try:
        conn = get_db_connection()
        
        # 전체 통계
        total_query = """
            SELECT 
                COUNT(DISTINCT employee_id) as total_employees,
                COUNT(DISTINCT center_id) as total_centers,
                COUNT(DISTINCT team_id) as total_teams,
                AVG(efficiency_ratio) as avg_efficiency,
                AVG(work_hours) as avg_work_hours,
                AVG(focus_ratio) as avg_focus_ratio,
                AVG(productivity_score) as avg_productivity
            FROM daily_analysis
            WHERE analysis_date = ?
        """
        
        total_df = pd.read_sql_query(total_query, conn, params=(analysis_date.isoformat(),))
        
        # 직급별 분포
        grade_query = """
            SELECT 
                job_grade,
                COUNT(*) as count,
                AVG(efficiency_ratio) as avg_efficiency,
                AVG(work_hours) as avg_work_hours
            FROM daily_analysis
            WHERE analysis_date = ?
                AND job_grade IS NOT NULL
            GROUP BY job_grade
            ORDER BY job_grade
        """
        
        grade_df = pd.read_sql_query(grade_query, conn, params=(analysis_date.isoformat(),))
        
        # 상위/하위 팀
        team_ranking_query = """
            SELECT 
                team_name,
                avg_efficiency_ratio,
                analyzed_employees
            FROM team_daily_summary
            WHERE analysis_date = ?
            ORDER BY avg_efficiency_ratio DESC
        """
        
        team_df = pd.read_sql_query(team_ranking_query, conn, params=(analysis_date.isoformat(),))
        
        conn.close()
        
        return {
            "date": analysis_date.isoformat(),
            "summary": total_df.to_dict('records')[0] if not total_df.empty else {},
            "grade_distribution": grade_df.to_dict('records'),
            "top_teams": team_df.head(5).to_dict('records'),
            "bottom_teams": team_df.tail(5).to_dict('records')
        }
        
    except Exception as e:
        logger.error(f"Error fetching summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dates/available")
async def get_available_dates():
    """분석 가능한 날짜 목록"""
    try:
        conn = get_db_connection()
        query = """
            SELECT DISTINCT analysis_date
            FROM daily_analysis
            ORDER BY analysis_date DESC
            LIMIT 30
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        dates = df['analysis_date'].tolist()
        
        return {
            "available_dates": dates,
            "latest_date": dates[0] if dates else None,
            "oldest_date": dates[-1] if dates else None,
            "total_dates": len(dates)
        }
        
    except Exception as e:
        logger.error(f"Error fetching available dates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status")
async def get_system_status():
    """시스템 상태 확인"""
    try:
        conn = get_db_connection()
        
        # DB 통계
        stats_query = """
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT employee_id) as total_employees,
                COUNT(DISTINCT analysis_date) as total_dates,
                MIN(analysis_date) as first_date,
                MAX(analysis_date) as last_date
            FROM daily_analysis
        """
        
        stats_df = pd.read_sql_query(stats_query, conn)
        conn.close()
        
        stats = stats_df.to_dict('records')[0] if not stats_df.empty else {}
        
        return {
            "status": "healthy",
            "database": {
                "path": str(DB_PATH),
                "size_mb": DB_PATH.stat().st_size / (1024 * 1024) if DB_PATH.exists() else 0,
                "is_mock": "mock" in DB_PATH.name
            },
            "statistics": stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error checking status: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


if __name__ == "__main__":
    import uvicorn
    
    # 서버 실행
    print(f"🚀 Starting FastAPI server...")
    print(f"📁 Using database: {DB_PATH}")
    print(f"📍 API docs: http://localhost:8000/docs")
    print(f"🌐 API URL: http://localhost:8000")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,  # 개발 중 자동 리로드
        log_level="info"
    )