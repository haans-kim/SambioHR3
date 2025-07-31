# SambioHR2 API Documentation

## 📋 Overview

This document provides detailed API documentation for the core modules in the SambioHR2 system. Each module is documented with its purpose, main classes/functions, parameters, and usage examples.

## 📦 Module Index

1. [Data Processing](#data-processing)
   - [ExcelLoader](#excelloader)
   - [DataTransformer](#datatransformer)
   - [PickleManager](#picklemanager)
2. [Database](#database)
   - [DatabaseManager](#databasemanager)
   - [Models](#models)
3. [HMM System](#hmm-system)
   - [HMMModel](#hmmmodel)
   - [BaumWelch](#baumwelch)
   - [Viterbi](#viterbi)
4. [Analysis](#analysis)
   - [IndividualAnalyzer](#individualanalyzer)
   - [OrganizationAnalyzer](#organizationanalyzer)
5. [Tag System](#tag-system)
   - [TagMapper](#tagmapper)
   - [RuleEngine](#ruleengine)
   - [ConfidenceCalculator](#confidencecalculator)

---

## 📊 Data Processing

### ExcelLoader
`src.data_processing.excel_loader`

Handles loading and processing of large Excel files efficiently.

#### Class: `ExcelLoader`

```python
class ExcelLoader:
    def __init__(self, chunk_size: int = 10000)
```

**Parameters:**
- `chunk_size` (int): Number of rows to process at once. Default: 10000

#### Methods:

##### `load_file(filepath: str, sheet_name: str = None) -> pd.DataFrame`
Loads an Excel file into a pandas DataFrame.

**Parameters:**
- `filepath` (str): Path to the Excel file
- `sheet_name` (str, optional): Name of the sheet to load

**Returns:**
- `pd.DataFrame`: Loaded data

**Example:**
```python
loader = ExcelLoader(chunk_size=5000)
df = loader.load_file('data/tag_data_24.6.xlsx', sheet_name='Sheet1')
```

##### `load_multiple_files(file_list: List[str]) -> Dict[str, pd.DataFrame]`
Loads multiple Excel files concurrently.

**Parameters:**
- `file_list` (List[str]): List of file paths

**Returns:**
- `Dict[str, pd.DataFrame]`: Dictionary mapping filenames to DataFrames

---

### DataTransformer
`src.data_processing.data_transformer`

Transforms raw data to handle 2-shift work system requirements.

#### Class: `DataTransformer`

```python
class DataTransformer:
    def __init__(self, shift_config: Dict = None)
```

#### Methods:

##### `process_shift_data(df: pd.DataFrame) -> pd.DataFrame`
Processes shift work data handling midnight crossovers.

**Parameters:**
- `df` (pd.DataFrame): Raw shift data

**Returns:**
- `pd.DataFrame`: Processed data with shift indicators

##### `identify_meal_times(df: pd.DataFrame, location_col: str, time_col: str) -> pd.DataFrame`
Identifies meal times based on location and time windows.

**Meal Windows:**
- Breakfast: 06:30-09:00
- Lunch: 11:20-13:20
- Dinner: 17:00-20:00
- Midnight: 23:30-01:00

**Example:**
```python
transformer = DataTransformer()
df_with_meals = transformer.identify_meal_times(
    df, 
    location_col='DR_NM', 
    time_col='timestamp'
)
```

---

### PickleManager
`src.data_processing.pickle_manager`

Manages pickle file caching for improved performance.

#### Class: `PickleManager`

```python
class PickleManager:
    def __init__(self, cache_dir: str = 'data/pickles')
```

#### Methods:

##### `save_data(data: Any, filename: str, compress: bool = True) -> str`
Saves data to pickle file with optional compression.

##### `load_data(filename: str) -> Any`
Loads data from pickle file.

##### `get_cache_info() -> Dict[str, Any]`
Returns information about cached files.

---

## 🗄️ Database

### DatabaseManager
`src.database.db_manager`

Manages database connections and operations.

#### Class: `DatabaseManager`

```python
class DatabaseManager:
    def __init__(self, db_path: str = 'data/sambio_hr.db')
```

#### Methods:

##### `execute_query(query: str, params: tuple = None) -> List[Dict]`
Executes a SELECT query and returns results.

##### `execute_batch(query: str, data: List[tuple]) -> int`
Executes batch insert/update operations.

##### `create_tables() -> None`
Creates all database tables from schema.

**Example:**
```python
db = DatabaseManager()
results = db.execute_query(
    "SELECT * FROM daily_work_data WHERE date = ?", 
    ('2025-06-01',)
)
```

---

### Models
`src.database.models`

SQLAlchemy models for database tables.

#### Key Models:

##### `Employee`
```python
class Employee(Base):
    __tablename__ = 'employees'
    
    employee_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    department = Column(String)
    team = Column(String)
    shift_type = Column(String)  # 'DAY' or 'NIGHT'
```

##### `DailyWorkData`
```python
class DailyWorkData(Base):
    __tablename__ = 'daily_work_data'
    
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    employee_code = Column(String, nullable=False)
    clock_in_time = Column(DateTime)
    clock_out_time = Column(DateTime)
    cross_day_flag = Column(Boolean, default=False)
    actual_work_time = Column(Float)
    meal_times = Column(JSON)  # {breakfast, lunch, dinner, midnight}
```

---

## 🤖 HMM System

### HMMModel
`src.hmm.hmm_model`

Core Hidden Markov Model implementation.

#### Class: `HMMModel`

```python
class HMMModel:
    def __init__(self, n_states: int = 17, n_features: int = 10)
```

**Parameters:**
- `n_states` (int): Number of hidden states (default: 17)
- `n_features` (int): Number of observation features (default: 10)

#### Properties:
- `states`: List of state names
- `transition_matrix`: State transition probabilities
- `emission_matrix`: Observation emission probabilities
- `initial_probabilities`: Initial state distribution

#### Methods:

##### `fit(observations: np.ndarray, n_iter: int = 100) -> None`
Trains the model using Baum-Welch algorithm.

##### `predict(observations: np.ndarray) -> List[str]`
Predicts most likely state sequence using Viterbi algorithm.

##### `score(observations: np.ndarray) -> float`
Computes log-likelihood of observations.

**Example:**
```python
model = HMMModel()
model.fit(training_data, n_iter=50)
states = model.predict(test_observations)
confidence = model.score(test_observations)
```

---

### BaumWelch
`src.hmm.baum_welch`

Implementation of Baum-Welch algorithm for HMM training.

#### Function: `baum_welch_train`

```python
def baum_welch_train(
    observations: np.ndarray,
    n_states: int,
    n_iter: int = 100,
    tol: float = 0.001
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]
```

**Returns:**
- Transition matrix
- Emission matrix
- Initial probabilities

---

### Viterbi
`src.hmm.viterbi`

Implementation of Viterbi algorithm for state prediction.

#### Function: `viterbi_decode`

```python
def viterbi_decode(
    observations: np.ndarray,
    transition_matrix: np.ndarray,
    emission_matrix: np.ndarray,
    initial_probs: np.ndarray
) -> Tuple[List[int], float]
```

**Returns:**
- Most likely state sequence
- Log probability of sequence

---

## 📊 Analysis

### IndividualAnalyzer
`src.analysis.individual_analyzer`

Analyzes individual employee work patterns.

#### Class: `IndividualAnalyzer`

```python
class IndividualAnalyzer:
    def __init__(self, db_manager: DatabaseManager, hmm_model: HMMModel)
```

#### Methods:

##### `analyze_employee(employee_id: str, date_range: Tuple[str, str]) -> Dict`
Performs comprehensive analysis for an employee.

**Returns Dictionary Contains:**
- `total_work_hours`: Total hours worked
- `claimed_vs_actual`: Comparison with self-reported hours
- `activity_distribution`: Time spent in each activity state
- `meal_patterns`: Meal timing analysis
- `productivity_score`: Overall productivity metric
- `shift_efficiency`: Day vs night shift performance

**Example:**
```python
analyzer = IndividualAnalyzer(db, model)
results = analyzer.analyze_employee(
    'EMP001', 
    ('2025-06-01', '2025-06-30')
)
```

##### `get_activity_timeline(employee_id: str, date: str) -> pd.DataFrame`
Returns minute-by-minute activity timeline.

---

### OrganizationAnalyzer
`src.analysis.organization_analyzer`

Analyzes department and organization-wide patterns.

#### Class: `OrganizationAnalyzer`

```python
class OrganizationAnalyzer:
    def __init__(self, db_manager: DatabaseManager)
```

#### Methods:

##### `analyze_department(dept_name: str, date_range: Tuple[str, str]) -> Dict`
Analyzes department-level metrics.

##### `compare_shifts() -> pd.DataFrame`
Compares day vs night shift performance.

##### `get_efficiency_trends(period: str = 'monthly') -> pd.DataFrame`
Returns efficiency trends over time.

---

## 🏷️ Tag System

### TagMapper
`src.tag_system.tag_mapper`

Maps physical locations to logical tags.

#### Class: `TagMapper`

```python
class TagMapper:
    def __init__(self, mapping_file: str = None)
```

#### Methods:

##### `get_tag_for_location(location: str) -> str`
Returns primary tag code for a location.

##### `get_all_tags_for_location(location: str) -> List[str]`
Returns all applicable tags for a location.

##### `is_work_area(location: str) -> bool`
Determines if location is a work area.

---

### RuleEngine
`src.tag_system.rule_engine`

Applies business rules for activity classification.

#### Class: `RuleEngine`

```python
class RuleEngine:
    def __init__(self, rules_file: str = 'config/rules/transition_rules.json')
```

#### Methods:

##### `apply_rules(state_sequence: List[str], context: Dict) -> List[str]`
Applies rule-based corrections to state sequence.

##### `add_rule(rule: Dict) -> None`
Adds a new rule to the engine.

##### `validate_rules() -> List[str]`
Validates all rules for consistency.

**Rule Format:**
```json
{
    "name": "meal_time_override",
    "condition": {
        "location": "CAFETERIA",
        "time_range": ["11:20", "13:20"]
    },
    "action": {
        "set_state": "LUNCH"
    },
    "priority": 100
}
```

---

### ConfidenceCalculator
`src.tag_system.confidence_calculator`

Calculates confidence scores for predictions.

#### Class: `ConfidenceCalculator`

```python
class ConfidenceCalculator:
    def __init__(self, threshold: float = 0.7)
```

#### Methods:

##### `calculate_confidence(predictions: List[str], probabilities: np.ndarray) -> List[float]`
Calculates confidence score for each prediction.

##### `get_reliability_score(data_quality: Dict) -> float`
Computes overall data reliability score.

---

## 🔧 Utility Functions

### Time Normalization
`src.utils.time_normalizer`

```python
def normalize_shift_time(timestamp: datetime, shift_type: str) -> datetime:
    """Normalizes time for shift workers crossing midnight."""
    
def get_meal_period(timestamp: datetime) -> str:
    """Returns meal period name for given time."""
    
def calculate_work_duration(clock_in: datetime, clock_out: datetime) -> float:
    """Calculates work duration handling day boundaries."""
```

### Performance Settings
`src.config.performance_settings`

```python
# Default configurations
BATCH_SIZE = 10000
CACHE_ENABLED = True
PARALLEL_WORKERS = 4
MEMORY_LIMIT_MB = 1024
```

---

## 📝 Usage Examples

### Complete Workflow Example

```python
from src.data_processing import ExcelLoader, DataTransformer, PickleManager
from src.database import DatabaseManager
from src.hmm import HMMModel
from src.analysis import IndividualAnalyzer, OrganizationAnalyzer

# 1. Load and transform data
loader = ExcelLoader()
transformer = DataTransformer()
pickle_mgr = PickleManager()

# Load tag data
tag_data = loader.load_file('data/tag_data_24.6.xlsx')
tag_data = transformer.process_shift_data(tag_data)
tag_data = transformer.identify_meal_times(tag_data, 'DR_NM', 'timestamp')

# Cache processed data
pickle_mgr.save_data(tag_data, 'tag_data_processed')

# 2. Initialize database
db = DatabaseManager()
db.create_tables()
db.execute_batch('INSERT INTO tag_logs ...', tag_data.values.tolist())

# 3. Train HMM model
model = HMMModel()
training_data = prepare_training_data(tag_data)  # Custom preprocessing
model.fit(training_data)

# 4. Analyze individual
analyzer = IndividualAnalyzer(db, model)
results = analyzer.analyze_employee('EMP001', ('2025-06-01', '2025-06-30'))

# 5. Analyze organization
org_analyzer = OrganizationAnalyzer(db)
dept_results = org_analyzer.analyze_department('Production', ('2025-06-01', '2025-06-30'))
```

---

## ⚠️ Error Handling

All modules implement comprehensive error handling:

```python
try:
    result = analyzer.analyze_employee(emp_id, date_range)
except DataNotFoundError as e:
    logger.error(f"No data found for employee {emp_id}: {e}")
except InvalidDateRangeError as e:
    logger.error(f"Invalid date range: {e}")
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise
```

---

## 🔍 Debugging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Module-specific loggers
logger = logging.getLogger('src.hmm.hmm_model')
logger.setLevel(logging.DEBUG)
```

---

## 📈 Performance Considerations

1. **Batch Processing**: Use batch operations for large datasets
2. **Caching**: Enable pickle caching for frequently accessed data
3. **Indexing**: Ensure database indexes are properly created
4. **Memory Management**: Monitor memory usage with large files
5. **Parallel Processing**: Use multiple workers for independent operations

---

**Last Updated**: 2025-01-31  
**API Version**: 1.0.0