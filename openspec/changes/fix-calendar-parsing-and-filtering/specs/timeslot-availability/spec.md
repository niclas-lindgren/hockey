# Time Slot Availability

## MODIFIED Requirements

### REQ-TA-001: Start Time Window vs Duration Window

The time slot checker must allow tournaments to start within the allowed window (11:00-14:00) even if the tournament duration extends beyond the latest start time.

**Priority:** Critical
**Status:** Modified

**Changes:**
- Modified gap checking logic to calculate valid start time range based on gap boundaries and required duration
- Updated "after last event" logic to check only if tournament can start by latest_start (14:00)
- Removed incorrect constraint that entire tournament duration must fit within start window
- Updated user-facing message to clarify "starting between" rather than "between"

**Rationale:** The original logic incorrectly rejected valid slots like 13:30-16:00, even though starting at 13:30 is within the 11:00-14:00 window. Tournaments can extend past 14:00 as long as they start before 14:00.

#### Scenario: Tournament starting at 13:00 extends past latest_start
**Given** the time slot window is 11:00-14:00 for starting
**And** tournaments need 2.5 hours duration
**And** a calendar event ends at 13:00
**When** checking for available time slots
**Then** a slot from 13:00-15:30 should be available
**And** the date should not be marked as a conflict

#### Scenario: Tournament starting at 14:00 is still valid
**Given** the time slot window is 11:00-14:00 for starting
**And** tournaments need 2.5 hours duration
**And** a calendar event ends at 14:00
**When** checking for available time slots
**Then** a slot from 14:00-16:30 should be available
**And** the date should not be marked as a conflict

#### Scenario: Tournament starting after 14:00 is invalid
**Given** the time slot window is 11:00-14:00 for starting
**And** tournaments need 2.5 hours duration
**And** a calendar event ends at 14:30
**When** checking for available time slots
**Then** no slot should be available
**And** the date should be marked as a conflict

#### Scenario: Gap between events with valid start time
**Given** the time slot window is 11:00-14:00 for starting
**And** tournaments need 2.5 hours duration
**And** event 1 ends at 11:00 and event 2 starts at 15:00
**When** checking for available time slots in the gap
**Then** the earliest possible start is 11:00
**And** the latest possible start is min(15:00 - 2.5h = 12:30, 14:00) = 12:30
**And** a slot from 11:00-13:30 should be available

### REQ-TA-002: User-Facing Messages

The time slot checker must clearly communicate that the start time must be within the window, not the entire duration.

**Priority:** Medium
**Status:** Modified

**Changes:**
- Changed message from "need 2.5h between 11:00-14:00" to "need 2.5h, starting between 11:00-14:00"

**Rationale:** The original message was misleading and suggested the entire tournament must fit within 11:00-14:00.

#### Scenario: Display correct availability message
**Given** the time slot checker with 2.5h duration and 11:00-14:00 start window
**When** the checker prints its status message
**Then** it should display "Checking time slot availability (need 2.5h, starting between 11:00-14:00)..."
**And** it should not display "need 2.5h between 11:00-14:00"
