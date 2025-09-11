# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Sambio Human Analytics is a workforce analytics system designed for 24-hour 2-shift work environments. It calculates real working time by analyzing log data and uses Hidden Markov Models (HMM) to classify employee activities.

## Key Commands

### Running the Application
```bash
# Main application
streamlit run src/ui/streamlit_app.py

# Alternative versions
streamlit run timeline_app.py  # Timeline visualization
streamlit run tests/simple_app.py    # Simplified interface
streamlit run tests/stable_app.py    # Stable test version
```

### Development Setup
```bash
# Create virtual environment
python -m venv venv

# Activate environment
source venv/bin/activate  # Unix/macOS
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### Testing & Quality
```bash
# Run tests (from project root)
python -m pytest tests/

# Code quality tools
black --check src/  # Code formatting check
flake8 src/        # Linting
mypy src/          # Type checking

# Data validation scripts
python find_valid_employees.py
python cleanup_bad_data.py
python inspect_pickle_data.py
```

## Architecture Overview

### Core Data Flow
1. **Excel Data Input** → Large Excel files (100MB+) containing employee log data
2. **Data Processing** → Transforms 2-shift work data, handles date crossovers
3. **Pickle Caching** → Speeds up repeated data loading
4. **SQLite Database** → 13 tables storing processed data
5. **HMM Analysis** → Classifies activities into 17 states
6. **Streamlit UI** → Displays individual and organizational dashboards

### Key Architectural Decisions

#### 2-Shift Work System Handling
- Day shift: 08:00-20:00, Night shift: 20:00-08:00
- Clock-in and clock-out dates can differ
- Special logic in `data_transformer.py` handles date transitions

#### 4 Meal Time Windows
Critical for activity classification:
- Breakfast: 06:30-09:00 + CAFETERIA location
- Lunch: 11:20-13:20 + CAFETERIA location  
- Dinner: 17:00-20:00 + CAFETERIA location
- Midnight meal: 23:30-01:00 + CAFETERIA location

#### HMM Model States (17 total)
Key states include: WORK, FOCUSED_WORK, EQUIPMENT_OPERATION, MEETING, BREAKFAST, LUNCH, DINNER, MIDNIGHT_MEAL, BREAK, MOVEMENT, IDLE, etc.

### Database Schema
13 tables including:
- `employees`: Basic employee information
- `daily_logs`: Raw log data with timestamps
- `work_sessions`: Processed work sessions
- `activities`: HMM-classified activities
- `meal_logs`: Meal time tracking
- Multiple analysis and summary tables

### Critical Components

#### Data Processing Pipeline
1. `src/data_processing/excel_loader.py`: Handles large Excel files efficiently
2. `src/data_processing/data_transformer.py`: Transforms raw data for 2-shift system
3. `src/data_processing/pickle_manager.py`: Caches processed data to avoid re-processing
4. `src/data/integrated_data_processor.py`: Unified data processing interface
5. `src/data/knox_processors.py`: Knox/PIMS equipment data processing

#### Analysis Engines
- `src/analysis/individual_analyzer.py`: Per-employee metrics and patterns
- `src/analysis/organization_analyzer.py`: Department and company-wide analytics
- `src/analysis/work_time_estimator.py`: Real working time calculations
- `src/analysis/office_worker_estimator.py`: Office worker specific analysis
- `src/analysis/batch_analysis_monitor.py`: Batch processing monitoring

#### HMM Implementation
- `src/hmm/hmm_model.py`: Core model with 17 states
- `src/hmm/baum_welch.py`: Training algorithm
- `src/hmm/viterbi.py`: Activity prediction
- `src/hmm/rule_editor.py`: Modify classification rules
- `src/hmm/viterbi_with_rules.py`: Rule-enhanced prediction

#### Tag System (New Architecture)
- `src/tag_system/tag_system_adapter.py`: Main tag processing interface
- `src/tag_system/state_classifier.py`: Tag-based state classification
- `src/tag_system/rule_engine.py`: Business rule processing
- `src/tag_system/confidence_calculator_v2.py`: Advanced confidence scoring
- `src/tag_system/meal_tag_processor.py`: Specialized meal time processing

## Important Considerations

### Performance
- Excel files can exceed 100MB
- Pickle caching is essential for responsiveness
- Database indexes on timestamp and employee_id columns

### Data Integrity
- 2-shift workers may have log entries spanning two calendar days
- Meal classification requires both time window AND location matching
- Equipment operation logs may have gaps that need interpolation

### UI State Management
- Streamlit reruns on every interaction
- Use session state for persistence
- Progress bars for long operations

## Current Development Status
- Version 1.0.0 (2025-01-18)
- Basic functionality implemented
- Active development per doc/plan.md (Phases 1-4 complete)
- Hybrid tag/HMM system implementation in progress
- FastAPI backend available at `backend/fastapi_server.py`

## Key Development Patterns

### Module Organization
- **Modular architecture**: Each major function has its own module under `src/`
- **Component-based UI**: UI components are in `src/ui/components/`
- **Layered design**: Data → Analysis → UI clear separation
- **Shared utilities**: Common utilities in `src/utils/` and `src/config/`

### Data Flow Architecture
1. **Raw Data**: Excel files → `src/data_processing/excel_loader.py`
2. **Transformation**: 2-shift handling → `src/data_processing/data_transformer.py`
3. **Caching**: Pickle files → `src/data_processing/pickle_manager.py`
4. **Database**: SQLite storage → `src/database/db_manager.py`
5. **Analysis**: HMM/Tag processing → `src/analysis/` + `src/tag_system/`
6. **UI**: Streamlit components → `src/ui/components/`

### State Management
- **Database singleton**: `src/database/singleton_manager.py`
- **Performance caching**: `src/utils/performance_cache.py`
- **Recent views**: `src/utils/recent_views_manager.py`
- **Session state**: Streamlit session state for UI persistence

## Development History & Documentation

### 개발 일지 위치
- `/doc/dev_logs/`: 일별 개발 로그
- `/doc/changes/`: 주요 변경사항 기록
- `CHANGELOG.md`: 버전별 변경사항

### 문서화 규칙
1. **일일 작업 기록**: `/doc/dev_logs/YYYY-MM-DD.md`
2. **기능별 문서**: `/doc/features/기능명.md`
3. **변경사항 추적**: Git 커밋 메시지 + 상세 문서

### 개발 컨텍스트 유지 방법
1. **작업 시작 시**: 이전 작업 내용 확인 (`/doc/dev_logs/`)
2. **작업 중**: TodoWrite 도구로 진행사항 추적
3. **작업 완료 시**: 일일 로그 업데이트, 변경사항 문서화

### 주요 작업 영역
- **최근 작업**: 전환 규칙 통합 (transition_rule_integration_summary.md)
- **진행 중**: 룰 관리 시스템 개선
- **계획됨**: doc/plan.md Phase 5-6

### 기술 문서 위치
- **데이터베이스 설계**: `/doc/technical/database_design.md`
- **API 설계**: `/doc/technical/api_design.md`
- **시스템 아키텍처**: 컴포넌트 기반 (Streamlit)
- **변경 추적 가이드**: `/doc/technical/change_tracking_guide.md`

### API 변경 추적
Claude Code 작업 시 자동으로 API/DB 변경사항이 추적됩니다:
- **추적 스크립트**: `/scripts/track_changes.py`
- **변경 로그**: `/doc/changes/LATEST.md`
- **수동 실행**: `python scripts/track_changes.py`

## Common Development Tasks

### Adding New Analysis Features
1. Create analysis module in `src/analysis/`
2. Add database tables if needed in `src/database/schema.py`
3. Create UI component in `src/ui/components/`
4. Import and integrate in `src/ui/streamlit_app.py`

### Data Processing Extensions
1. Add new processors in `src/data/` for specific data types
2. Extend `src/data/integrated_data_processor.py` if needed
3. Update pickle management in `src/data_processing/pickle_manager.py`
4. Test with validation scripts in project root

### UI Component Development
1. Follow existing patterns in `src/ui/components/`
2. Use `src/ui/styles/` for consistent styling
3. Implement error handling and progress indicators
4. Test with different data scenarios

### Database Schema Changes
1. Modify `src/database/schema.py` for new tables
2. Update `src/database/models.py` for new business logic
3. Create migration scripts if needed
4. Update analysis modules to use new schema

### Performance Optimization
- Use `src/utils/performance_cache.py` for caching
- Monitor with `src/analysis/parallel_batch_analyzer.py`
- Profile with built-in performance measurement tools
- Consider pickle vs database trade-offs for data access