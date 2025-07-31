# SambioHR2 Project Documentation

## 📌 Executive Summary

SambioHR2 is a workforce analytics system designed specifically for 24-hour 2-shift work environments. It analyzes employee activity patterns using tag data and Hidden Markov Models (HMM) to calculate actual working time and classify activities into 17 distinct states.

### Key Capabilities
- **2-Shift Work System Support**: Handles day/night shifts with midnight boundary transitions
- **Meal Time Tracking**: Automatically identifies 4 meal periods (breakfast, lunch, dinner, midnight)
- **Activity Classification**: Uses HMM to classify activities into 17 states
- **Real-time Analytics**: Provides individual and organizational dashboards
- **Data Quality Monitoring**: Tracks data reliability and confidence scores

## 🏗️ System Architecture

### Overview
The system follows a modular architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit UI Layer                        │
├─────────────────────────────────────────────────────────────┤
│                    Analysis Engine                           │
│  ┌─────────────────┐        ┌──────────────────────┐       │
│  │ Individual      │        │ Organization         │       │
│  │ Analyzer        │        │ Analyzer             │       │
│  └─────────────────┘        └──────────────────────┘       │
├─────────────────────────────────────────────────────────────┤
│                    HMM Model Layer                           │
│  ┌─────────────────┐  ┌──────────────┐  ┌────────────┐    │
│  │ HMM Model       │  │ Baum-Welch   │  │ Viterbi    │    │
│  │ (17 states)     │  │ Algorithm    │  │ Algorithm  │    │
│  └─────────────────┘  └──────────────┘  └────────────┘    │
├─────────────────────────────────────────────────────────────┤
│                 Data Processing Pipeline                      │
│  ┌─────────────────┐  ┌──────────────┐  ┌────────────┐    │
│  │ Excel Loader    │  │ Data         │  │ Pickle     │    │
│  │ (100MB+)        │  │ Transformer  │  │ Manager    │    │
│  └─────────────────┘  └──────────────┘  └────────────┘    │
├─────────────────────────────────────────────────────────────┤
│              SQLite Database (15 tables)                     │
└─────────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. Data Processing Layer (`src/data_processing/`)
- **excel_loader.py**: Handles large Excel files (100MB+) efficiently
- **data_transformer.py**: Transforms raw data for 2-shift system
- **pickle_manager.py**: Caches processed data for performance

#### 2. Database Layer (`src/database/`)
- **schema.py**: Defines 15 table structures
- **db_manager.py**: Database connection and query management
- **models.py**: Business logic models
- **tag_schema.py**: Tag system specific tables

#### 3. HMM Model Layer (`src/hmm/`)
- **hmm_model.py**: Core HMM implementation with 17 states
- **baum_welch.py**: Training algorithm for parameter optimization
- **viterbi.py**: Prediction algorithm for activity classification
- **rule_editor.py**: UI for modifying transition/emission rules

#### 4. Analysis Layer (`src/analysis/`)
- **individual_analyzer.py**: Per-employee metrics and patterns
- **organization_analyzer.py**: Department and company-wide analytics
- **network_analyzer.py**: Inter-employee collaboration patterns

#### 5. UI Layer (`src/ui/`)
- **streamlit_app.py**: Main application entry point
- **components/**: Modular UI components
  - individual_dashboard.py
  - organization_dashboard.py
  - data_upload.py
  - model_config.py

## 📊 Data Model

### HMM States (17 total)
```python
STATES = [
    # Work States
    'WORK',              # General work activity
    'FOCUSED_WORK',      # Concentrated work periods
    'EQUIPMENT_OPERATION', # Operating machinery/equipment
    'MEETING',           # Meeting attendance
    'WORK_PREPARATION',  # Preparing for work
    'WORKING',          # Active work execution
    
    # Meal States
    'BREAKFAST',        # 06:30-09:00 + CAFETERIA
    'LUNCH',           # 11:20-13:20 + CAFETERIA
    'DINNER',          # 17:00-20:00 + CAFETERIA
    'MIDNIGHT_MEAL',   # 23:30-01:00 + CAFETERIA
    
    # Movement States
    'MOVEMENT',        # General movement
    'COMMUTE_IN',      # Coming to work
    'COMMUTE_OUT',     # Leaving work
    
    # Rest States
    'BREAK',           # Rest periods
    'FITNESS',         # Exercise/fitness activities
    
    # Non-work States
    'LEAVE',           # Annual leave
    'FAMILY_LEAVE'     # Family-related leave
]
```

### Observation Features (10 dimensions)
1. **Tag Location**: Physical location from tag readers
2. **Time Interval**: Duration between tag reads
3. **Day of Week**: Monday-Sunday
4. **Time Zone**: Hour of day (0-23)
5. **Work Area Flag**: Inside/outside work areas
6. **ABC Activity**: Activity classification from ABC system
7. **Attendance Status**: Official attendance records
8. **Excluded Time**: Non-work time flags
9. **Cafeteria Location**: Meal location detection
10. **Shift Type**: Day/Night shift indicator

## 🔄 Data Processing Pipeline

### 1. Data Input Sources
- **Tag Data**: Entry/exit timestamps and locations
- **ABC Activity Data**: Actual work performed
- **Claim Data**: Self-reported work hours
- **Attendance Data**: Official attendance records
- **Non-work Time Data**: Breaks, meals, training
- **Organization Data**: Employee hierarchy
- **Location Master**: Tag location definitions

### 2. Processing Steps
```
Raw Excel Files → Excel Loader → Data Transformer → Pickle Cache → Database
                                        ↓
                                  HMM Processing
                                        ↓
                                 Activity Classification
                                        ↓
                                  Analysis Results
```

### 3. 2-Shift Work Handling
- **Day Shift**: 08:00-20:00
- **Night Shift**: 20:00-08:00
- **Cross-day Logic**: Handles clock-out on different calendar day
- **Time Continuity**: Maintains sequence across midnight

## 🎯 Key Features

### 1. Meal Time Detection
Automatically identifies meal periods using:
- Time window matching
- CAFETERIA location confirmation
- Duration validation
- Shift-specific meal patterns

### 2. Activity Classification
- **Machine Learning**: HMM with Baum-Welch training
- **Rule-based Override**: Manual rules for specific scenarios
- **Confidence Scoring**: Reliability metrics for predictions
- **Real-time Updates**: Continuous model improvement

### 3. Performance Metrics
- **Individual Level**:
  - Actual vs claimed work time
  - Activity distribution
  - Productivity score
  - Meal time patterns
  
- **Organization Level**:
  - Department averages
  - Shift comparisons
  - Efficiency trends
  - Resource utilization

### 4. Data Quality Management
- **Completeness Tracking**: Missing data identification
- **Consistency Checks**: Cross-validation between sources
- **Confidence Scoring**: Prediction reliability metrics
- **Anomaly Detection**: Unusual pattern identification

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- 8GB RAM minimum (for large datasets)
- Modern web browser

### Installation
```bash
# Clone repository
git clone <repository-url>
cd SambioHR2

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Application
```bash
# Start Streamlit server
streamlit run src/ui/streamlit_app.py

# Alternative entry points
streamlit run timeline_app.py    # Timeline visualization
streamlit run simple_app.py      # Simplified interface
```

### Initial Data Setup
1. Prepare Excel files in required format
2. Upload through web interface
3. System automatically processes and caches data
4. View results in dashboards

## 📈 Performance Characteristics

### Processing Capabilities
- **Excel Files**: Handles 100MB+ files
- **Tag Records**: Processes 1M+ records efficiently
- **Response Time**: <3 seconds for dashboard loads
- **Concurrent Users**: Supports 10+ simultaneous users

### Optimization Strategies
- **Pickle Caching**: Reduces reload time by 90%
- **Database Indexing**: Optimized queries on key fields
- **Lazy Loading**: Loads data on-demand
- **Batch Processing**: Handles large datasets in chunks

## 🔧 Configuration

### Environment Variables
```bash
# Database
DATABASE_URL=sqlite:///data/sambio_hr.db

# Processing
BATCH_SIZE=10000
CACHE_ENABLED=true

# UI
STREAMLIT_THEME=light
MAX_UPLOAD_SIZE=200
```

### HMM Model Parameters
- **States**: 17 predefined activity states
- **Training Iterations**: 100 (configurable)
- **Convergence Threshold**: 0.001
- **Smoothing Factor**: 0.01

## 🛡️ Security & Privacy

### Data Protection
- Local SQLite database (no external connections)
- Pickle files encrypted at rest
- No PII in logs or error messages
- Session-based access control

### Compliance
- Follows data minimization principles
- Audit trail for all modifications
- Configurable data retention policies
- Role-based access control ready

## 📚 Advanced Topics

### Extending the System
1. **Adding New States**: Modify `hmm_model.py`
2. **Custom Analyzers**: Create new modules in `analysis/`
3. **UI Components**: Add to `ui/components/`
4. **Data Sources**: Extend `data_processing/`

### API Integration Points
- RESTful API ready (not implemented)
- Export capabilities (CSV, Excel, JSON)
- Webhook support planned
- Real-time data streaming possible

### Performance Tuning
- Adjust batch sizes for memory constraints
- Enable/disable caching based on usage
- Configure parallel processing workers
- Optimize database vacuum schedule

## 🤝 Contributing

### Development Process
1. Fork repository
2. Create feature branch
3. Implement with tests
4. Submit pull request

### Code Standards
- PEP 8 compliance
- Type hints required
- Docstrings for public methods
- Unit test coverage >80%

### Documentation
- Update relevant .md files
- Include examples
- Document breaking changes
- Update API references

## 📞 Support

### Resources
- **Documentation**: `/doc/` directory
- **Examples**: `/examples/` directory
- **Issue Tracker**: GitHub Issues
- **Development Logs**: `/doc/dev_logs/`

### Common Issues
1. **Memory Errors**: Reduce batch size
2. **Slow Processing**: Enable caching
3. **Missing Data**: Check Excel format
4. **Wrong Classifications**: Adjust HMM rules

## 🎉 Version History

### v1.0.0 (2025-01-18)
- Initial release
- Full 2-shift support
- HMM implementation
- Streamlit UI
- 15 database tables
- Pickle caching

### Roadmap
- v1.1.0: Real-time processing
- v1.2.0: Multi-language support
- v2.0.0: Web API
- v3.0.0: Cloud deployment

---

**Last Updated**: 2025-01-31  
**Maintained By**: Sambio Human Analytics Team