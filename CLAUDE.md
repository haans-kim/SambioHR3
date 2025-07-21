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
streamlit run simple_app.py    # Simplified interface
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
1. `excel_loader.py`: Handles large Excel files efficiently
2. `data_transformer.py`: Transforms raw data for 2-shift system
3. `pickle_manager.py`: Caches processed data to avoid re-processing

#### Analysis Engines
- `individual_analyzer.py`: Per-employee metrics and patterns
- `organization_analyzer.py`: Department and company-wide analytics

#### HMM Implementation
- `hmm_model.py`: Core model with 17 states
- `baum_welch.py`: Training algorithm
- `viterbi.py`: Activity prediction
- `rule_editor.py`: Modify classification rules

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