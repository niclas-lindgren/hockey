# Proposal: Add Tournament Rescheduling

## Summary
Add functionality to reschedule an existing tournament by extracting participating teams from an Excel file and finding alternative dates when all teams are available, while maintaining all existing conflict checks. Refactor codebase to follow SOLID and DRY principles.

## Problem
Currently, the system can only find available dates for new tournaments. When a tournament needs to be rescheduled due to conflicts or other issues, there is no automated way to:
1. Identify which teams were scheduled for the original tournament
2. Find alternative dates when all those specific teams are available
3. Ensure the new date passes all existing validation checks

Manual rescheduling is error-prone and time-consuming, especially when coordinating multiple teams' schedules.

## Proposed Solution
Extend the tournament scheduler with a `--reschedule` mode that:
1. Accepts a tournament date and Excel file as input
2. Parses the Excel file to extract all teams scheduled for that date
3. Checks team availability across the date range
4. Applies all existing conflict checks (ice hall, ball hall, holidays, other teams)
5. Returns ranked alternative dates when all teams are available

The implementation will refactor existing code to follow SOLID principles:
- **Single Responsibility**: Each class handles one concern (parsing, validation, scheduling)
- **Open/Closed**: New conflict checkers can be added without modifying existing code
- **Dependency Inversion**: High-level scheduling logic depends on abstractions, not concrete implementations

DRY principles will be applied by:
- Extracting repeated date parsing logic into utilities
- Creating reusable conflict checker components
- Consolidating duplicate calendar scraping code

## Scope
**In Scope:**
- New `--reschedule` CLI argument to trigger rescheduling mode
- Excel parser enhancement to extract tournament teams for a specific date
- Team availability checker that validates all teams are free
- Refactored architecture with clear separation of concerns
- Unit tests for new components
- Updated documentation

**Out of Scope:**
- Modifying the Excel file automatically
- Web UI or API endpoints
- Email notifications to teams
- Calendar integration (Google Calendar, Outlook)
- Multi-tournament rescheduling in batch

## Success Criteria
1. User can reschedule a tournament by specifying date and Excel file
2. System correctly identifies all teams from the tournament
3. System finds dates when all teams are available
4. All existing conflict checks still pass
5. Code follows SOLID principles with <20% duplication
6. Test coverage >80% for new code
7. Documentation updated with rescheduling examples

## Dependencies
- Existing calendar scraping functionality
- openpyxl library for Excel parsing
- Playwright for calendar access

## Risks & Mitigations
**Risk**: Excel format variations may break team extraction
**Mitigation**: Implement flexible parser with fallback strategies and clear error messages

**Risk**: Large refactor may introduce regressions
**Mitigation**: Maintain existing tests, add integration tests, incremental refactoring

**Risk**: Performance degradation with additional team checks
**Mitigation**: Implement caching for calendar data, parallel conflict checking

## Timeline Estimate
- Design & architecture: 1 day
- Core refactoring: 2-3 days
- Rescheduling feature: 1-2 days
- Testing & documentation: 1 day
**Total**: 5-7 days

## Alternatives Considered
1. **Manual rescheduling tool**: Separate script for rescheduling only
   - Rejected: Would duplicate calendar scraping and conflict checking logic

2. **Excel output only**: Generate Excel with available dates
   - Deferred: Can be added later as enhancement

3. **Minimal refactor**: Add rescheduling without architecture changes
   - Rejected: Would increase technical debt and violate SOLID/DRY requirements
