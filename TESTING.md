# Testing Guide

## Test Structure

```
backend/tests/
├── benchmark/
│   ├── __init__.py
│   ├── test_tools.py                    # 21 tests - Tool dispatcher
│   ├── test_engine_scoring.py           # 14 tests - Slot scoring
│   ├── test_engine_recurrence.py        # 12 tests - Recurrence patterns
│   ├── test_engine_conflicts.py         # 14 tests - Conflict detection
│   ├── test_edge_cases.py              # 12 tests - Timezone, overflow, off-days
│   └── test_api_endpoints.py           # 21 tests - API contract validation
├── test_integration.py                  # 20+ tests - Full API integration
└── conftest.py                          # Test fixtures
```

## Running Tests

### All Benchmark Tests (106 scenarios)

```bash
cd backend
python -m pytest tests/benchmark/ -v
```

### Specific Test File

```bash
python -m pytest tests/benchmark/test_tools.py -v
python -m pytest tests/benchmark/test_engine_scoring.py -v
```

### With Coverage

```bash
python -m pytest tests/benchmark/ --cov=app --cov-report=term-missing
```

### Stop on First Failure

```bash
python -m pytest tests/benchmark/ -x
```

## Test Categories

### Tool Dispatcher Tests (`test_tools.py`)
- Verifies all 13 tools are registered and callable
- Tests input validation for each tool
- Tests error handling for missing/invalid arguments
- Tests auth checks (user not found)

### Engine Scoring Tests (`test_engine_scoring.py`)
- Base score validation
- Morning preference bonus
- Lunch avoidance penalty
- Buffer time bonus
- Urgency bonus (within 2 days)
- Score range [5, 100] enforcement

### Recurrence Tests (`test_engine_recurrence.py`)
- Daily/weekly/monthly expansion
- Custom intervals
- Month-end overflow (Jan 31 → Feb 28)
- Range boundaries

### Conflict Detection Tests (`test_engine_conflicts.py`)
- Adjacent appointments (no overlap)
- Partial overlap detection
- Full containment detection
- Timezone-aware conflict detection

### Edge Case Tests (`test_edge_cases.py`)
- Full-day busy → no slots
- UTC timezone handling
- Extreme timezone offsets (UTC+14)
- Off-day working hours

### API Contract Tests (`test_api_endpoints.py`)
- Auth: register, login, refresh, logout
- Calendar: CRUD operations
- Agent: search, create, chat
- Correct status codes and response shapes

## Frontend E2E Tests

Located in `frontend/tests/e2e/`:

```bash
cd frontend
npx playwright install
npx playwright test
```

## CI/CD Integration

Add to your CI pipeline:

```yaml
- name: Run backend tests
  run: |
    cd backend
    pip install -r requirements.txt
    python -m pytest tests/benchmark/ -v --tb=short

- name: Build frontend
  run: |
    cd frontend
    npm ci
    npm run build
```
