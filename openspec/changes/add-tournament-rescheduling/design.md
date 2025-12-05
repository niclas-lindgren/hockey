# Design: Tournament Rescheduling with SOLID/DRY Architecture

## Architecture Overview

### Current Issues
The existing `tournament_scheduler.py` monolithic design has several problems:
1. **Large functions**: `find_available_weekends()` is 180+ lines doing multiple responsibilities
2. **Repeated logic**: Date parsing duplicated 6+ times
3. **Tight coupling**: Calendar scraping, parsing, and filtering are intertwined
4. **Hard to test**: Business logic mixed with data access
5. **Hard to extend**: Adding new conflict types requires modifying core logic

### Proposed Architecture

```
┌─────────────────────────────────────────────────┐
│           TournamentScheduler                    │
│         (Orchestration Layer)                    │
└──────────────┬──────────────────────────────────┘
               │
       ┌───────┴────────┬────────────────┐
       │                │                │
┌──────▼──────┐  ┌─────▼─────┐  ┌──────▼──────┐
│  Calendar   │  │ Conflict  │  │   Excel     │
│DataSources  │  │ Checkers  │  │   Reader    │
└─────────────┘  └───────────┘  └─────────────┘
       │                │                │
       │         ┌──────┴────────┐      │
       │         │               │      │
   ┌───▼────┐  ┌▼────────┐  ┌───▼──────▼────┐
   │  Ice   │  │  Ball   │  │  Team         │
   │  Hall  │  │  Hall   │  │  Extractor    │
   └────────┘  └─────────┘  └───────────────┘
                │
         ┌──────┴──────────────┐
         │                     │
   ┌─────▼──────┐      ┌──────▼────────┐
   │  Holiday   │      │  Tournament   │
   │  Checker   │      │   Checker     │
   └────────────┘      └───────────────┘
```

## Core Components

### 1. Utilities Layer

#### DateParser
**Responsibility**: Single source of truth for date parsing
```python
class DateParser:
    SUPPORTED_FORMATS = ['%d.%m.%Y', '%d/%m/%Y', '%Y-%m-%d']

    @staticmethod
    def parse(date_str: str) -> Optional[datetime]

    @staticmethod
    def parse_datetime_cell(cell: Any) -> Optional[datetime]
```

**Rationale**: Eliminates 6+ instances of duplicate date parsing logic

---

### 2. Data Source Layer

#### CalendarDataSource (Abstract Base)
**Responsibility**: Define interface for calendar data retrieval
```python
class CalendarDataSource(ABC):
    @abstractmethod
    def fetch_events(self, start: datetime, end: datetime) -> List[CalendarEvent]

    @abstractmethod
    def get_source_name(self) -> str
```

#### IceHallCalendar
**Responsibility**: Scrape and parse ice hall events
```python
class IceHallCalendar(CalendarDataSource):
    def __init__(self, url: str, scraper: CalendarScraper)
    def fetch_events(...) -> List[CalendarEvent]
    def is_tournament_event(self, event_name: str) -> bool
```

#### BallHallCalendar
**Responsibility**: Scrape and parse ball hall events
```python
class BallHallCalendar(CalendarDataSource):
    def __init__(self, url: str, scraper: CalendarScraper, min_duration: float = 2.0)
    def fetch_events(...) -> List[CalendarEvent]
    def filters_long_events(self) -> List[CalendarEvent]
```

**Rationale**:
- Open/Closed: New calendar sources can be added without modifying existing code
- Single Responsibility: Each calendar type handles its own scraping logic
- Dependency Inversion: Scheduler depends on CalendarDataSource interface

---

### 3. Excel Layer

#### ExcelTournamentReader
**Responsibility**: Read tournament and team data from Excel files
```python
class ExcelTournamentReader:
    def __init__(self, file_path: str, date_parser: DateParser)

    def get_all_tournament_dates(self) -> Set[date]
    def get_tournament_info(self, tournament_date: date) -> TournamentInfo
    def extract_teams_for_date(self, tournament_date: date) -> List[str]
```

#### TournamentInfo
**Responsibility**: Value object for tournament data
```python
@dataclass
class TournamentInfo:
    date: date
    name: str
    teams: List[str]
    location: Optional[str]
```

**Rationale**:
- Single Responsibility: Excel parsing separated from business logic
- DRY: Centralized Excel reading logic
- Testable: Can be tested with mock Excel data

---

### 4. Conflict Checking Layer

#### ConflictChecker (Abstract Base)
**Responsibility**: Define interface for conflict detection
```python
class ConflictChecker(ABC):
    @abstractmethod
    def check_conflicts(
        self,
        dates: List[date],
        context: ConflictContext
    ) -> ConflictResult

    @abstractmethod
    def get_checker_name(self) -> str
```

#### ConflictContext
**Responsibility**: Encapsulate all data needed for conflict checking
```python
@dataclass
class ConflictContext:
    start_date: datetime
    end_date: datetime
    team_names: List[str]
    calendar_events: List[CalendarEvent]
    excel_dates: Set[date]
    tournament_to_reschedule: Optional[date]
```

#### ConflictResult
**Responsibility**: Value object for conflict check results
```python
@dataclass
class ConflictResult:
    excluded_dates: Set[date]
    reasons: Dict[date, str]
    checker_name: str
```

#### Implementations:

**HolidayConflictChecker**
```python
class HolidayConflictChecker(ConflictChecker):
    def __init__(self, country: str = 'NO')
    def check_conflicts(...) -> ConflictResult
```

**TournamentConflictChecker**
```python
class TournamentConflictChecker(ConflictChecker):
    def __init__(self, calendar_source: CalendarDataSource)
    def check_conflicts(...) -> ConflictResult
```

**BallHallConflictChecker**
```python
class BallHallConflictChecker(ConflictChecker):
    def __init__(self, calendar_source: BallHallCalendar)
    def check_conflicts(...) -> ConflictResult
```

**TeamAvailabilityChecker**
```python
class TeamAvailabilityChecker(ConflictChecker):
    def __init__(self, calendar_source: CalendarDataSource)
    def check_conflicts(...) -> ConflictResult
    def check_team_availability(self, team: str, dates: List[date]) -> Set[date]
```

**ExcelConflictChecker**
```python
class ExcelConflictChecker(ConflictChecker):
    def __init__(self, excel_dates: Set[date])
    def check_conflicts(...) -> ConflictResult
```

**Rationale**:
- Open/Closed: New conflict types added by implementing interface
- Single Responsibility: Each checker handles one type of conflict
- Composable: Checkers can be combined and reused

---

### 5. Orchestration Layer

#### TournamentScheduler
**Responsibility**: Coordinate all components to find available dates
```python
class TournamentScheduler:
    def __init__(
        self,
        calendar_sources: List[CalendarDataSource],
        conflict_checkers: List[ConflictChecker],
        date_parser: DateParser
    )

    def find_available_dates(
        self,
        start_date: datetime,
        end_date: datetime,
        team_names: List[str] = None,
        excel_file: str = None
    ) -> SchedulingResult

    def reschedule_tournament(
        self,
        tournament_date: date,
        excel_file: str,
        start_date: datetime,
        end_date: datetime
    ) -> SchedulingResult
```

#### SchedulingResult
**Responsibility**: Value object for scheduling results
```python
@dataclass
class SchedulingResult:
    available_dates: List[date]
    excluded_dates: List[date]
    exclusion_breakdown: Dict[str, int]
    detailed_exclusions: List[Tuple[date, str]]
    total_weekends_checked: int
```

**Rationale**:
- Single Responsibility: Only coordinates, doesn't implement logic
- Dependency Inversion: Depends on abstractions (interfaces)
- Open/Closed: New features added by injecting new checkers

---

## Design Decisions

### 1. Why Abstract Base Classes?
**Decision**: Use ABC for CalendarDataSource and ConflictChecker

**Rationale**:
- Enforces interface contracts
- Enables dependency inversion
- Allows easy mocking for tests
- Makes extension points explicit

**Alternative Considered**: Duck typing
**Rejected**: Less explicit, harder to understand extension points

---

### 2. Why Value Objects (Dataclasses)?
**Decision**: Use dataclasses for TournamentInfo, ConflictResult, SchedulingResult

**Rationale**:
- Immutable data structures
- Type safety
- Clear data contracts
- Easy to test

**Alternative Considered**: Dictionaries
**Rejected**: No type safety, prone to KeyErrors

---

### 3. Why Separate DateParser?
**Decision**: Dedicated utility class for date parsing

**Rationale**:
- DRY: Eliminates 6+ duplicate implementations
- Single place to add new date formats
- Easier to test edge cases
- Consistent behavior across codebase

---

### 4. Why ConflictContext?
**Decision**: Pass all context in single object instead of many parameters

**Rationale**:
- Reduces parameter coupling
- Easy to add new context without changing signatures
- Self-documenting
- Easier to create test fixtures

**Alternative Considered**: Individual parameters
**Rejected**: Functions had 6+ parameters, hard to maintain

---

### 5. Why Dependency Injection?
**Decision**: Inject dependencies via constructor

**Rationale**:
- Testability: Easy to inject mocks
- Flexibility: Can swap implementations
- Explicit dependencies: Clear what each class needs
- SOLID compliance: Dependency Inversion Principle

**Alternative Considered**: Global singletons
**Rejected**: Hard to test, tight coupling

---

## Rescheduling Flow

### User Flow
```
1. User specifies: --reschedule 2026-01-17 --excel-file schedule.xlsx
2. System extracts teams for 2026-01-17 from Excel
3. System checks each date in range for ALL team availability
4. System applies existing conflict checks
5. System returns ranked dates when all teams are free
```

### Implementation Flow
```python
def reschedule_tournament(tournament_date, excel_file, start, end):
    # 1. Extract tournament teams
    reader = ExcelTournamentReader(excel_file, date_parser)
    tournament_info = reader.get_tournament_info(tournament_date)

    # 2. Create context with team names
    context = ConflictContext(
        start_date=start,
        end_date=end,
        team_names=tournament_info.teams,
        # ... other context
    )

    # 3. Check conflicts (includes team availability)
    results = []
    for checker in conflict_checkers:
        result = checker.check_conflicts(weekend_dates, context)
        results.append(result)

    # 4. Combine results
    available = find_dates_passing_all_checks(results)

    return SchedulingResult(available_dates=available, ...)
```

---

## Testing Strategy

### Unit Tests
- DateParser: All date formats, edge cases
- Each ConflictChecker: Various conflict scenarios
- ExcelTournamentReader: Different Excel structures
- TournamentScheduler: Orchestration logic

### Integration Tests
- End-to-end scheduling with real Excel files
- Calendar scraping with cached responses
- Rescheduling complete flow

### Test Fixtures
```python
# fixtures/sample_tournaments.xlsx - Known structure
# fixtures/calendar_responses/ - Cached calendar HTML
# fixtures/conflict_scenarios.py - Test data
```

---

## Migration Strategy

### Phase 1: Extract Utilities (No Breaking Changes)
1. Create DateParser
2. Replace all date parsing with DateParser
3. Run existing tests to ensure no regression

### Phase 2: Create Interfaces (No Breaking Changes)
1. Define CalendarDataSource, ConflictChecker interfaces
2. Keep existing functions as private helpers

### Phase 3: Implement New Classes (No Breaking Changes)
1. Implement calendar sources
2. Implement conflict checkers
3. Keep existing code paths working

### Phase 4: Create Orchestrator
1. Implement TournamentScheduler
2. Wire up all components

### Phase 5: Update CLI (Breaking Changes Acceptable)
1. Update main() to use new architecture
2. Add --reschedule argument
3. Update tests

### Phase 6: Cleanup
1. Remove old functions
2. Update documentation

---

## Performance Considerations

### Caching Strategy
- Cache calendar responses for date range
- Cache parsed Excel data
- Reuse conflict check results when possible

### Parallel Processing
- Fetch multiple calendar sources concurrently
- Run independent conflict checks in parallel

### Memory Management
- Stream Excel rows for large files
- Don't load entire calendar in memory
- Use generators where appropriate

---

## Backward Compatibility

**Guarantees**:
- Existing CLI arguments continue to work
- Output format remains the same
- Excel file format support unchanged

**New Additions**:
- `--reschedule <date>` argument
- Requires `--excel-file` when rescheduling
- New output section showing tournament teams

---

## Code Quality Metrics

**Target**:
- Cyclomatic complexity: <10 per function
- Code duplication: <20%
- Test coverage: >80%
- Max function length: 50 lines
- Max class length: 200 lines

**Enforcement**:
- Pre-commit hooks for complexity
- Coverage reports in CI
- Code review checklist
