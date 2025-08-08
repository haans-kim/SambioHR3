# React UI 아키텍처 설계

## 1. 프로젝트 구조

```
sambio-analytics-ui/
├── public/
│   └── index.html
├── src/
│   ├── api/
│   │   ├── analyticsAPI.ts         # 분석 데이터 API
│   │   ├── apiClient.ts            # Axios 인스턴스
│   │   └── types.ts                # API 타입 정의
│   ├── components/
│   │   ├── common/
│   │   │   ├── Card.tsx            # 재사용 카드 컴포넌트
│   │   │   ├── MetricCard.tsx      # 메트릭 표시 카드
│   │   │   ├── ProgressBar.tsx     # 진행률 표시
│   │   │   └── LoadingSpinner.tsx
│   │   ├── organization/
│   │   │   ├── CenterGrid.tsx      # 센터 카드 그리드
│   │   │   ├── TeamGrid.tsx        # 팀 카드 그리드
│   │   │   ├── GroupGrid.tsx       # 그룹 카드 그리드
│   │   │   └── EmployeeDetail.tsx  # 직원 상세
│   │   ├── charts/
│   │   │   ├── EfficiencyChart.tsx # 효율성 차트
│   │   │   ├── HeatmapChart.tsx    # 시간대별 히트맵
│   │   │   └── TrendChart.tsx      # 추세 차트
│   │   └── layout/
│   │       ├── Header.tsx
│   │       ├── Sidebar.tsx
│   │       └── Layout.tsx
│   ├── hooks/
│   │   ├── useAnalytics.ts         # 분석 데이터 훅
│   │   ├── useOrganization.ts      # 조직 데이터 훅
│   │   └── useWebSocket.ts         # 실시간 업데이트
│   ├── pages/
│   │   ├── Dashboard.tsx           # 메인 대시보드
│   │   ├── OrganizationView.tsx    # 조직 분석 뷰
│   │   ├── TeamView.tsx            # 팀 상세 뷰
│   │   └── EmployeeView.tsx        # 개인 분석 뷰
│   ├── store/
│   │   ├── index.ts                # Redux store
│   │   ├── slices/
│   │   │   ├── analyticsSlice.ts
│   │   │   └── organizationSlice.ts
│   │   └── selectors/
│   ├── styles/
│   │   ├── globals.css
│   │   ├── variables.css
│   │   └── components/
│   ├── utils/
│   │   ├── formatters.ts           # 데이터 포맷팅
│   │   ├── calculations.ts         # 계산 유틸
│   │   └── constants.ts
│   ├── App.tsx
│   └── index.tsx
├── package.json
├── tsconfig.json
└── README.md
```

## 2. 핵심 컴포넌트 설계

### 2.1 MetricCard 컴포넌트
```tsx
// components/common/MetricCard.tsx
interface MetricCardProps {
  title: string;
  value: number | string;
  unit?: string;
  trend?: number;
  color?: 'green' | 'blue' | 'red' | 'yellow';
  onClick?: () => void;
  isClickable?: boolean;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  unit,
  trend,
  color = 'blue',
  onClick,
  isClickable = false
}) => {
  const colorMap = {
    green: '#4CAF50',
    blue: '#2196F3',
    red: '#F44336',
    yellow: '#FFC107'
  };

  return (
    <div 
      className={`metric-card ${isClickable ? 'clickable' : ''}`}
      style={{ borderColor: colorMap[color] }}
      onClick={onClick}
    >
      <h4>{title}</h4>
      <div className="value">
        <span className="number">{value}</span>
        {unit && <span className="unit">{unit}</span>}
      </div>
      {trend !== undefined && (
        <div className="trend">
          <span className={trend > 0 ? 'up' : 'down'}>
            {trend > 0 ? '↑' : '↓'} {Math.abs(trend)}%
          </span>
        </div>
      )}
    </div>
  );
};
```

### 2.2 조직 계층 네비게이션
```tsx
// components/organization/OrganizationNavigator.tsx
interface NavigationState {
  level: 'center' | 'team' | 'group';
  centerId?: string;
  teamId?: string;
  groupId?: string;
}

export const OrganizationNavigator: React.FC = () => {
  const [navState, setNavState] = useState<NavigationState>({
    level: 'center'
  });

  const handleDrillDown = (type: string, id: string) => {
    switch (type) {
      case 'center':
        setNavState({ level: 'team', centerId: id });
        break;
      case 'team':
        setNavState({ ...navState, level: 'group', teamId: id });
        break;
    }
  };

  const handleBreadcrumbClick = (level: NavigationState['level']) => {
    setNavState({ ...navState, level });
  };

  return (
    <div className="org-navigator">
      <Breadcrumb onNavigate={handleBreadcrumbClick} state={navState} />
      
      {navState.level === 'center' && (
        <CenterGrid onCenterClick={(id) => handleDrillDown('center', id)} />
      )}
      
      {navState.level === 'team' && navState.centerId && (
        <TeamGrid 
          centerId={navState.centerId}
          onTeamClick={(id) => handleDrillDown('team', id)} 
        />
      )}
      
      {navState.level === 'group' && navState.teamId && (
        <GroupGrid teamId={navState.teamId} />
      )}
    </div>
  );
};
```

## 3. API 설계

### 3.1 FastAPI 백엔드
```python
# backend/main.py
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import date
import sqlite3
import pandas as pd

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/centers")
async def get_centers(analysis_date: date = Query(...)):
    """센터 목록 및 요약 정보"""
    conn = sqlite3.connect("sambio_analytics.db")
    query = """
        SELECT 
            center_id,
            center_name,
            total_employees,
            analyzed_employees,
            avg_efficiency_ratio,
            avg_work_hours,
            avg_focus_ratio
        FROM center_daily_summary
        WHERE analysis_date = ?
        ORDER BY center_name
    """
    df = pd.read_sql_query(query, conn, params=(analysis_date,))
    conn.close()
    return df.to_dict('records')

@app.get("/api/teams/{center_id}")
async def get_teams_by_center(
    center_id: str,
    analysis_date: date = Query(...)
):
    """특정 센터의 팀 목록"""
    conn = sqlite3.connect("sambio_analytics.db")
    query = """
        SELECT 
            team_id,
            team_name,
            total_employees,
            analyzed_employees,
            avg_efficiency_ratio,
            avg_work_hours,
            avg_focus_ratio,
            avg_productivity_score
        FROM team_daily_summary
        WHERE center_id = ? AND analysis_date = ?
        ORDER BY team_name
    """
    df = pd.read_sql_query(query, conn, params=(center_id, analysis_date))
    conn.close()
    return df.to_dict('records')

@app.get("/api/employees/{team_id}")
async def get_employees_by_team(
    team_id: str,
    analysis_date: date = Query(...)
):
    """특정 팀의 직원 상세"""
    conn = sqlite3.connect("sambio_analytics.db")
    query = """
        SELECT 
            employee_id,
            employee_name,
            job_grade,
            total_hours,
            work_hours,
            focused_work_hours,
            efficiency_ratio,
            focus_ratio,
            productivity_score,
            peak_hours,
            activity_distribution
        FROM daily_analysis
        WHERE team_id = ? AND analysis_date = ?
        ORDER BY efficiency_ratio DESC
    """
    df = pd.read_sql_query(query, conn, params=(team_id, analysis_date))
    conn.close()
    return df.to_dict('records')

@app.get("/api/employee/{employee_id}/trend")
async def get_employee_trend(
    employee_id: str,
    days: int = Query(default=30)
):
    """직원 추세 데이터"""
    conn = sqlite3.connect("sambio_analytics.db")
    query = """
        SELECT 
            analysis_date,
            efficiency_ratio,
            work_hours,
            focus_ratio,
            productivity_score
        FROM daily_analysis
        WHERE employee_id = ?
        ORDER BY analysis_date DESC
        LIMIT ?
    """
    df = pd.read_sql_query(query, conn, params=(employee_id, days))
    conn.close()
    return df.to_dict('records')

@app.get("/api/analytics/summary")
async def get_analytics_summary(analysis_date: date = Query(...)):
    """전체 요약 통계"""
    conn = sqlite3.connect("sambio_analytics.db")
    
    summary = {}
    
    # 전체 통계
    total = pd.read_sql_query("""
        SELECT 
            COUNT(DISTINCT employee_id) as total_employees,
            AVG(efficiency_ratio) as avg_efficiency,
            AVG(work_hours) as avg_work_hours
        FROM daily_analysis
        WHERE analysis_date = ?
    """, conn, params=(analysis_date,))
    
    summary['total'] = total.to_dict('records')[0]
    
    # 직급별 분포
    grade_dist = pd.read_sql_query("""
        SELECT 
            job_grade,
            COUNT(*) as count,
            AVG(efficiency_ratio) as avg_efficiency
        FROM daily_analysis
        WHERE analysis_date = ?
        GROUP BY job_grade
    """, conn, params=(analysis_date,))
    
    summary['grade_distribution'] = grade_dist.to_dict('records')
    
    conn.close()
    return summary
```

## 4. 상태 관리 (Redux Toolkit)

```typescript
// store/slices/organizationSlice.ts
import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { analyticsAPI } from '../../api/analyticsAPI';

interface OrganizationState {
  centers: Center[];
  selectedCenter?: Center;
  teams: Team[];
  selectedTeam?: Team;
  employees: Employee[];
  loading: boolean;
  error: string | null;
}

export const fetchCenters = createAsyncThunk(
  'organization/fetchCenters',
  async (date: string) => {
    const response = await analyticsAPI.getCenters(date);
    return response.data;
  }
);

export const fetchTeams = createAsyncThunk(
  'organization/fetchTeams',
  async ({ centerId, date }: { centerId: string; date: string }) => {
    const response = await analyticsAPI.getTeamsByCenter(centerId, date);
    return response.data;
  }
);

const organizationSlice = createSlice({
  name: 'organization',
  initialState: {
    centers: [],
    teams: [],
    employees: [],
    loading: false,
    error: null
  } as OrganizationState,
  reducers: {
    selectCenter: (state, action) => {
      state.selectedCenter = action.payload;
      state.teams = [];
      state.selectedTeam = undefined;
    },
    selectTeam: (state, action) => {
      state.selectedTeam = action.payload;
      state.employees = [];
    }
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchCenters.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchCenters.fulfilled, (state, action) => {
        state.loading = false;
        state.centers = action.payload;
      })
      .addCase(fetchCenters.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || 'Failed to fetch centers';
      });
  }
});
```

## 5. 실행 계획

### 5.1 프로젝트 초기화
```bash
# React 프로젝트 생성
npx create-react-app sambio-analytics-ui --template typescript
cd sambio-analytics-ui

# 필요한 패키지 설치
npm install axios react-router-dom @reduxjs/toolkit react-redux
npm install recharts react-datepicker classnames
npm install @types/react-datepicker --save-dev

# UI 라이브러리 (선택)
npm install antd  # 또는 mui
```

### 5.2 백엔드 설정
```bash
# FastAPI 백엔드
pip install fastapi uvicorn pandas

# 실행
uvicorn main:app --reload --port 8000
```

### 5.3 개발 우선순위
1. **Phase 1** (Day 1): 기본 구조 및 API 연동
   - 프로젝트 설정
   - API 클라이언트 구현
   - 기본 라우팅

2. **Phase 2** (Day 2): 핵심 컴포넌트
   - MetricCard 컴포넌트
   - 조직 그리드 컴포넌트
   - 데이터 페칭 훅

3. **Phase 3** (Day 3): 상호작용 및 완성
   - 드릴다운 네비게이션
   - 차트 컴포넌트
   - 반응형 디자인

## 6. 성능 최적화

### 6.1 데이터 캐싱
```typescript
// hooks/useAnalytics.ts
import { useQuery } from 'react-query';

export const useAnalytics = (date: string) => {
  return useQuery(
    ['analytics', date],
    () => analyticsAPI.getCenters(date),
    {
      staleTime: 5 * 60 * 1000, // 5분
      cacheTime: 10 * 60 * 1000, // 10분
    }
  );
};
```

### 6.2 가상 스크롤링
```tsx
// 대량 데이터 표시 시
import { FixedSizeList } from 'react-window';

<FixedSizeList
  height={600}
  itemCount={employees.length}
  itemSize={100}
  width={'100%'}
>
  {({ index, style }) => (
    <EmployeeCard 
      employee={employees[index]} 
      style={style} 
    />
  )}
</FixedSizeList>
```

## 7. 배포 전략

### 7.1 Docker 컨테이너화
```dockerfile
# Frontend Dockerfile
FROM node:16-alpine as build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

### 7.2 환경 변수
```typescript
// config/environment.ts
export const config = {
  API_URL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
  WS_URL: process.env.REACT_APP_WS_URL || 'ws://localhost:8000',
};
```