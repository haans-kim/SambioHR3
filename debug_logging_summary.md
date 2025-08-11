# Debug Logging Summary

## Overview
Found DEBUG logging statements across 21 files in the project. These can be categorized by their purpose and location.

## Files with DEBUG Logging

### 1. Database Components
- `/src/database/singleton_manager.py` - 8 debug statements
  - Singleton instance creation/initialization
  - Cache hits/misses/overflow
  - Pickle data loading status

- `/src/database/db_manager.py` - 4 debug statements
  - Query execution tracking
  - Data type debugging for attendance data
  - Time object conversion logging

### 2. Data Processing
- `/src/data_processing/pickle_manager.py` - 13 debug statements
  - File loading/saving operations
  - File path searches
  - Metadata operations
  - Pattern matching results

### 3. Analysis Components
- `/src/analysis/individual_analyzer.py` - 6 debug statements
  - Analysis start/completion tracking
  - Pickle file not found messages
  - 꼬리물기 pattern detection

### 4. UI Components
- `/src/ui/components/individual_dashboard.py` - 4 debug statements
  - Knox PIMS time checking
  - Data loading failures (LAMS, MES, EAM)

- `/src/ui/components/organization_dashboard.py` - Multiple debug statements
  - Metric calculation tracking
  - Time parsing errors

### 5. Utility Components
- `/src/utils/performance_cache.py` - 6 debug statements
  - Cache hit notifications for various data types
  - Data filtering completion logs

### 6. Tag System
- `/src/tag_system/tag_mapper.py` - 2 debug statements
  - Location to tag mapping logs

- `/src/tag_system/rule_integration.py` - 1 debug statement
  - Rule matching failures

- `/src/tag_system/rule_engine.py` - 1 debug statement
  - Rule application tracking

- `/src/tag_system/confidence_calculator_v2.py` - 2 debug statements
  - Transition probability file loading
  - Tag activity tracking

### 7. HMM Components
- `/src/hmm/viterbi.py` - 1 debug statement
  - Cached prediction results

- `/src/hmm/viterbi_with_rules.py` - 1 debug statement
  - Cached prediction results

### 8. Config
- `/src/config/logging_config.py` - Contains the debug_log function itself

## Recommendations for Cleanup

### High Priority (Remove these)
1. **Repetitive cache hit logs** - These generate too much noise:
   - All "캐시 히트" messages in performance_cache.py
   - Cache-related messages in singleton_manager.py
   - Cached prediction messages in viterbi files

2. **File operation logs** - Normal operations shouldn't be logged:
   - File save/load messages in pickle_manager.py
   - Pattern matching results

3. **Initialization logs** - One-time events:
   - Singleton initialization messages

### Medium Priority (Consider removing)
1. **Analysis tracking** - Start/completion logs that don't add value
2. **Data type debugging** - Should be removed after fixing issues
3. **Rule matching logs** - Unless actively debugging rules

### Low Priority (May keep if needed)
1. **Error-related debug logs** - FileNotFound, parsing failures
2. **Pattern detection** - 꼬리물기 pattern logs might be useful
3. **Time validation** - Knox PIMS time checking

## Quick Cleanup Commands

To remove all debug logging:
```bash
# Remove all logger.debug statements
find src -name "*.py" -type f -exec sed -i.bak '/logger\.debug/d' {} \;
find src -name "*.py" -type f -exec sed -i.bak '/self\.logger\.debug/d' {} \;

# Clean up backup files
find src -name "*.py.bak" -type f -delete
```

To selectively remove by pattern:
```bash
# Remove cache-related debug logs
find src -name "*.py" -type f -exec sed -i.bak '/캐시.*히트/d' {} \;

# Remove initialization logs
find src -name "*.py" -type f -exec sed -i.bak '/초기화 완료/d' {} \;
```