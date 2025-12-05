# Calendar Debug Tool

This tool helps you inspect what bookings are actually in the calendars.

## Usage

### Check a specific date
```bash
./debug-calendar.sh skien_ice --date 2026-03-07
./debug-calendar.sh kongsberg_ice --date 2026-01-15
./debug-calendar.sh kongsberg_ball --date 2026-02-20
```

### Check a date range
```bash
./debug-calendar.sh skien_ice --start 2026-03-01 --end 2026-03-31
./debug-calendar.sh kongsberg_ice --start 2026-01-01 --end 2026-02-28
```

## Calendar Types

- **skien_ice** - Skien Ice Hall (Google Calendar via iCal)
- **kongsberg_ice** - Kongsberg Ice Hall (Outlook calendar)
- **kongsberg_ball** - Kongsberg Ball Hall (Outlook calendar)

## Output

For a specific date, the tool shows:

1. **All bookings on that date** with times and durations
2. **Busy periods** - when the ice is booked
3. **Available gaps** - time slots suitable for a tournament (2.5+ hours, starting between 11:00-14:00)

### Example Output

```
Events on 2026-03-08 (Sunday):
--------------------------------------------------------------------------------
  08.03.2026 11:00-12:30 (1.5h): Hockeyskole
  08.03.2026 12:30-14:00 (1.5h): Trening Bredde yngre

================================================================================
TIME ANALYSIS FOR THIS DATE
================================================================================

Busy periods:
  11:00-12:30: Hockeyskole
  12:30-14:00: Trening Bredde yngre

Available gaps (for 2.5h tournament, starting 11:00-14:00):
  14:00-16:30 (after last booking)
```

## Troubleshooting

### "No events found"

If you see no events for a date you expect to have bookings:

1. **Verify the date format** - Use YYYY-MM-DD (e.g., 2026-03-07)
2. **Check you're looking at the right calendar** - Skien bookings are in `skien_ice`, not `kongsberg_ice`
3. **Calendar sync delay** - Google Calendar public feeds can take time to update
4. **Check the website** - The calendar website might show events that aren't in the public feed

### Comparing with website

The Skien calendar is fetched from their public iCal feed:
```
https://calendar.google.com/calendar/ical/istiderskienhockey@gmail.com/public/basic.ics
```

If bookings show on the website but not in the debug tool, the calendar owner may need to:
- Make sure the calendar is set to "public"
- Wait for Google's cache to refresh (can take hours)
- Check that events are actually saved in the calendar

## Integration

The scheduler uses this same calendar data to:
- Check team availability (Skien teams playing away)
- Check time slot availability
- Detect booking conflicts

If the debug tool shows no bookings, the scheduler will consider that time available.
