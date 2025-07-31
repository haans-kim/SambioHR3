# SambioHR2 Database Schema Documentation

## 📊 Overview

SambioHR2 uses SQLite as its database engine with SQLAlchemy ORM. The database consists of 15 core tables organized into 5 logical groups:

1. **Employee & Organization** (3 tables)
2. **Work & Activity Data** (4 tables)
3. **Tag System** (4 tables)
4. **HMM Model** (2 tables)
5. **System & Logs** (2 tables)

## 🗄️ Database Structure

### Entity Relationship Diagram

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│    employees    │────<│  daily_work_data │>────│  tag_logs       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                       │                         │
         │                       │                         │
         v                       v                         v
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ organization    │     │   activities     │     │ tag_master      │
│   _mapping      │     └──────────────────┘     └─────────────────┘
└─────────────────┘              │                         │
                                 │                         │
                                 v                         v
                        ┌──────────────────┐     ┌─────────────────┐
                        │  hmm_states      │     │ location_tag    │
                        └──────────────────┘     │   _mapping      │
                                                 └─────────────────┘
```

## 📋 Table Specifications

### 1. Employee & Organization Tables

#### `employees`
Core employee information table.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| employee_id | VARCHAR(20) | PRIMARY KEY | Employee ID (사번) |
| name | VARCHAR(100) | NOT NULL | Employee name |
| department | VARCHAR(100) | | Department name |
| team | VARCHAR(100) | | Team name |
| position | VARCHAR(50) | | Job position |
| shift_type | VARCHAR(10) | CHECK IN ('DAY','NIGHT') | Shift assignment |
| hire_date | DATE | | Employment start date |
| status | VARCHAR(20) | DEFAULT 'ACTIVE' | Employment status |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation |
| updated_at | TIMESTAMP | | Last update time |

**Indexes:**
- `idx_emp_dept`: (department)
- `idx_emp_shift`: (shift_type)
- `idx_emp_status`: (status)

#### `organization_mapping`
Organizational hierarchy mapping.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Record ID |
| employee_id | VARCHAR(20) | FOREIGN KEY → employees | Employee reference |
| center | VARCHAR(100) | | Center name |
| bu | VARCHAR(100) | | Business unit |
| team | VARCHAR(100) | | Team name |
| group_name | VARCHAR(100) | | Group name |
| part | VARCHAR(100) | | Part name |
| valid_from | DATE | NOT NULL | Effective start date |
| valid_to | DATE | | Effective end date |

**Indexes:**
- `idx_org_emp_date`: (employee_id, valid_from)
- `idx_org_hierarchy`: (center, bu, team)

#### `organization_summary`
Aggregated organizational metrics.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Record ID |
| date | DATE | NOT NULL | Summary date |
| dept_name | VARCHAR(100) | NOT NULL | Department name |
| metric_type | VARCHAR(50) | NOT NULL | Metric type |
| value | FLOAT | | Metric value |
| count | INTEGER | | Employee count |
| shift | VARCHAR(10) | | Shift type (optional) |

**Indexes:**
- `idx_org_sum_date_dept`: (date, dept_name)

### 2. Work & Activity Data Tables

#### `daily_work_data`
Daily work records with 2-shift support.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Record ID |
| date | DATE | NOT NULL | Work date |
| employee_code | VARCHAR(20) | FOREIGN KEY → employees | Employee reference |
| name | VARCHAR(100) | | Employee name (denormalized) |
| shift | VARCHAR(10) | | Shift type (DAY/NIGHT) |
| clock_in_time | TIMESTAMP | | Clock-in timestamp |
| clock_out_time | TIMESTAMP | | Clock-out timestamp |
| cross_day_flag | BOOLEAN | DEFAULT FALSE | Midnight crossing indicator |
| gross_work_time | FLOAT | | Total time (hours) |
| actual_work_time | FLOAT | | Actual work time (hours) |
| rest_time | FLOAT | | Rest time (hours) |
| meal_times | JSON | | Meal durations {"breakfast": 0.5, ...} |
| overtime | FLOAT | | Overtime hours |
| data_quality | FLOAT | CHECK BETWEEN 0 AND 1 | Data reliability score |

**Indexes:**
- `idx_daily_work_date_emp`: (date, employee_code)
- `idx_daily_work_shift`: (shift, date)

#### `shift_work_data`
Detailed shift work breakdown.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Record ID |
| date | DATE | NOT NULL | Work date |
| employee_code | VARCHAR(20) | FOREIGN KEY → employees | Employee reference |
| day_shift_hours | FLOAT | DEFAULT 0 | Day shift hours |
| night_shift_hours | FLOAT | DEFAULT 0 | Night shift hours |
| transition_time | TIMESTAMP | | Shift transition time |
| total_work_time | FLOAT | | Total hours worked |

#### `activities`
HMM-classified activity records.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Record ID |
| employee_id | VARCHAR(20) | FOREIGN KEY → employees | Employee reference |
| timestamp | TIMESTAMP | NOT NULL | Activity timestamp |
| state | VARCHAR(50) | NOT NULL | HMM state |
| duration | INTEGER | | Duration (minutes) |
| confidence | FLOAT | CHECK BETWEEN 0 AND 1 | Prediction confidence |
| location | VARCHAR(100) | | Physical location |
| raw_data | JSON | | Original observation data |

**Indexes:**
- `idx_activities_emp_time`: (employee_id, timestamp)
- `idx_activities_state`: (state)

#### `work_sessions`
Continuous work session tracking.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Session ID |
| employee_id | VARCHAR(20) | FOREIGN KEY → employees | Employee reference |
| session_date | DATE | NOT NULL | Session date |
| start_time | TIMESTAMP | NOT NULL | Session start |
| end_time | TIMESTAMP | | Session end |
| session_type | VARCHAR(50) | | Type of work session |
| total_duration | FLOAT | | Duration (hours) |
| activity_breakdown | JSON | | Activity distribution |

### 3. Tag System Tables

#### `tag_master`
Master tag definitions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| tag_code | VARCHAR(10) | PRIMARY KEY | Unique tag code |
| tag_category | CHAR(1) | CHECK IN ('G','N','T','M','O') | Category |
| tag_name | VARCHAR(100) | NOT NULL | Tag name |
| description | TEXT | | Detailed description |
| priority | INTEGER | DEFAULT 0 | Processing priority |
| is_active | BOOLEAN | DEFAULT TRUE | Active flag |

**Categories:**
- G: Gate (entry/exit points)
- N: Non-work areas
- T: Work areas
- M: Meeting/conference
- O: Other/special

#### `tag_logs`
Raw tag reading logs.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Log ID |
| employee_code | VARCHAR(20) | NOT NULL | Employee ID |
| timestamp | TIMESTAMP | NOT NULL | Tag read time |
| location | VARCHAR(100) | NOT NULL | Physical location |
| location_code | VARCHAR(20) | | Location code |
| tag_type | VARCHAR(10) | | Entry/Exit type |
| processed_flag | BOOLEAN | DEFAULT FALSE | Processing status |
| session_id | VARCHAR(50) | | Related session |

**Indexes:**
- `idx_tag_logs_emp_time`: (employee_code, timestamp)
- `idx_tag_logs_processed`: (processed_flag)

#### `location_tag_mapping`
Maps physical locations to logical tags.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Mapping ID |
| location | VARCHAR(100) | NOT NULL UNIQUE | Physical location |
| tag_code | VARCHAR(10) | FOREIGN KEY → tag_master | Associated tag |
| is_primary | BOOLEAN | DEFAULT TRUE | Primary tag flag |
| mapping_confidence | FLOAT | DEFAULT 1.0 | Mapping reliability |

**Indexes:**
- `idx_location_tag`: (location, tag_code)

#### `state_transition_rules`
HMM state transition rules.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Rule ID |
| from_state | VARCHAR(50) | NOT NULL | Source state |
| to_state | VARCHAR(50) | NOT NULL | Target state |
| base_probability | FLOAT | CHECK BETWEEN 0 AND 1 | Base transition prob |
| conditions | JSON | | Rule conditions |
| priority | INTEGER | DEFAULT 0 | Rule priority |
| is_active | BOOLEAN | DEFAULT TRUE | Active flag |

**Indexes:**
- `idx_transition_states`: (from_state, to_state)

### 4. HMM Model Tables

#### `hmm_states`
HMM state definitions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| state_id | INTEGER | PRIMARY KEY AUTOINCREMENT | State ID |
| state_name | VARCHAR(50) | NOT NULL UNIQUE | State name |
| state_category | VARCHAR(50) | | Category (WORK/MEAL/REST/etc) |
| description | TEXT | | State description |
| color_code | VARCHAR(7) | | UI color (#RRGGBB) |
| icon | VARCHAR(50) | | UI icon name |

#### `hmm_model_config`
Model configuration and parameters.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Config ID |
| model_version | VARCHAR(20) | NOT NULL | Model version |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation time |
| transition_matrix | JSON | | Full transition matrix |
| emission_matrix | JSON | | Full emission matrix |
| initial_probs | JSON | | Initial state probabilities |
| training_metrics | JSON | | Training performance metrics |
| is_active | BOOLEAN | DEFAULT FALSE | Active model flag |

### 5. System & Log Tables

#### `processing_log`
System processing history.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Log ID |
| process_type | VARCHAR(50) | NOT NULL | Process type |
| start_time | TIMESTAMP | NOT NULL | Process start |
| end_time | TIMESTAMP | | Process end |
| status | VARCHAR(20) | | SUCCESS/FAILED/RUNNING |
| records_processed | INTEGER | | Record count |
| error_message | TEXT | | Error details |
| metadata | JSON | | Additional info |

#### `meal_logs`
Meal time tracking.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Log ID |
| employee_id | VARCHAR(20) | FOREIGN KEY → employees | Employee reference |
| date | DATE | NOT NULL | Meal date |
| meal_type | VARCHAR(20) | CHECK IN ('BREAKFAST','LUNCH','DINNER','MIDNIGHT') | Meal type |
| start_time | TIMESTAMP | | Meal start |
| end_time | TIMESTAMP | | Meal end |
| location | VARCHAR(100) | | Cafeteria location |
| duration | INTEGER | | Duration (minutes) |

**Indexes:**
- `idx_meal_emp_date`: (employee_id, date)

## 🔗 Relationships

### Primary Relationships

1. **employees → daily_work_data** (1:N)
   - One employee has multiple daily work records
   - Linked by: employee_code/employee_id

2. **employees → tag_logs** (1:N)
   - One employee generates multiple tag logs
   - Linked by: employee_code

3. **employees → activities** (1:N)
   - One employee has multiple activity records
   - Linked by: employee_id

4. **tag_master → location_tag_mapping** (1:N)
   - One tag can map to multiple locations
   - Linked by: tag_code

5. **employees → organization_mapping** (1:N)
   - One employee can have multiple org assignments over time
   - Linked by: employee_id

### Junction Tables

- **location_tag_mapping**: Links physical locations to logical tags
- **state_transition_rules**: Defines valid state transitions
- **organization_mapping**: Tracks organizational changes over time

## 🔐 Constraints & Business Rules

### Data Integrity Constraints

1. **Shift Constraints**
   - Day shift: 08:00-20:00
   - Night shift: 20:00-08:00
   - Cross-day flag required for night shifts

2. **Meal Time Windows**
   ```sql
   CHECK (
     (meal_type = 'BREAKFAST' AND TIME(start_time) BETWEEN '06:30' AND '09:00') OR
     (meal_type = 'LUNCH' AND TIME(start_time) BETWEEN '11:20' AND '13:20') OR
     (meal_type = 'DINNER' AND TIME(start_time) BETWEEN '17:00' AND '20:00') OR
     (meal_type = 'MIDNIGHT' AND (TIME(start_time) >= '23:30' OR TIME(start_time) <= '01:00'))
   )
   ```

3. **Work Time Validation**
   ```sql
   CHECK (actual_work_time <= gross_work_time)
   CHECK (rest_time >= 0)
   CHECK (overtime >= 0)
   ```

4. **Probability Constraints**
   ```sql
   CHECK (confidence BETWEEN 0 AND 1)
   CHECK (base_probability BETWEEN 0 AND 1)
   CHECK (data_quality BETWEEN 0 AND 1)
   ```

### Referential Integrity

All foreign keys have CASCADE options:
- **ON DELETE**: RESTRICT (prevent orphaned records)
- **ON UPDATE**: CASCADE (propagate changes)

## 📈 Performance Optimization

### Index Strategy

1. **Primary Indexes**: All primary keys
2. **Foreign Key Indexes**: All foreign key columns
3. **Query Optimization Indexes**:
   - Date-based queries: (date, employee_code)
   - Time-range queries: (timestamp)
   - Status queries: (processed_flag, status)

### Partitioning Strategy

For large deployments, consider partitioning:
- **tag_logs**: By month
- **activities**: By month
- **daily_work_data**: By quarter

## 🔧 Maintenance

### Regular Maintenance Tasks

1. **Daily**
   - Update organization_summary
   - Process pending tag_logs
   - Clean processing_log > 30 days

2. **Weekly**
   - Rebuild statistics
   - Vacuum database
   - Archive completed work_sessions

3. **Monthly**
   - Backup full database
   - Analyze query performance
   - Review and optimize indexes

### Data Retention

- **tag_logs**: 6 months (then archive)
- **activities**: 1 year
- **daily_work_data**: 2 years
- **processing_log**: 30 days
- **All others**: Indefinite

## 📊 Sample Queries

### 1. Get employee's daily activity summary
```sql
SELECT 
    e.name,
    a.state,
    SUM(a.duration) as total_minutes,
    AVG(a.confidence) as avg_confidence
FROM activities a
JOIN employees e ON a.employee_id = e.employee_id
WHERE a.employee_id = 'EMP001' 
    AND DATE(a.timestamp) = '2025-06-15'
GROUP BY e.name, a.state
ORDER BY total_minutes DESC;
```

### 2. Compare shift efficiency
```sql
SELECT 
    d.shift,
    AVG(d.actual_work_time / d.gross_work_time) as efficiency,
    COUNT(DISTINCT d.employee_code) as employee_count
FROM daily_work_data d
WHERE d.date BETWEEN '2025-06-01' AND '2025-06-30'
GROUP BY d.shift;
```

### 3. Meal pattern analysis
```sql
SELECT 
    m.meal_type,
    AVG(m.duration) as avg_duration,
    COUNT(*) as meal_count
FROM meal_logs m
JOIN employees e ON m.employee_id = e.employee_id
WHERE e.shift_type = 'NIGHT'
    AND m.date BETWEEN '2025-06-01' AND '2025-06-30'
GROUP BY m.meal_type;
```

---

**Version**: 1.0.0  
**Last Updated**: 2025-01-31  
**Database Engine**: SQLite 3.x with SQLAlchemy ORM