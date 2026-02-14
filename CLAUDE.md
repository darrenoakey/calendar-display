# Calendar Display

## Running the App

Start the app using auto:
```
/auto start calendar-display
```

Do NOT launch directly with `python -m src.horizontal_calendar`.

### Calendar Sources

The app supports multiple calendar sources through two mechanisms:

1. **Agent-Link Integration** (preferred): Fetches events from all connected calendar sources
   - Apple Calendar (native)
   - Google Calendar (requires OAuth configuration in agent-link)
   - Start agent-link first: `/auto start agent-link`
   - Calendar-display will auto-retry if agent-link is not available

2. **EventKit Fallback**: Direct Apple Calendar access via PyObjC EventKit
   - Automatically used if agent-link is unavailable
   - Requires Calendar permission in System Settings > Privacy & Security > Calendars
   - Only shows Apple Calendar events (no Google Calendar)

The app will automatically fall back to EventKit if agent-link is not running or fails to connect.

## Python Version

This project requires Python 3.13 specifically because PySide6 is installed there. The `run` script uses `#!/usr/bin/env python3.13` - do not change this to generic `python3` as that resolves to 3.14 which lacks PySide6.

## Architecture Notes

### Flash Animation
The flash animation for urgent events uses a **single shared QTimer** in MainWindow that iterates through all EventCards. Do NOT create individual timers per card - this causes memory issues from timer accumulation during refresh cycles.

### Memory Considerations
- PySide6/Qt on macOS shows very high virtual memory (VSZ ~400GB) which is normal - Metal backend reserves large address spaces
- Actual physical memory (RSS/footprint) is what matters - should be <100MB
- Use `footprint <pid>` to check real memory usage, not `ps` VSZ column

### Meeting Notifications (integrated from calendar-notifications)
- `meeting_link.py`: Extracts Zoom and Google Meet links from calendar events (url > location > notes field priority, Zoom before Meet)
- `meeting_launcher.py`: Launches meetings via `zoommtg://` for Zoom or `open` for Meet (fire-and-forget subprocess)
- Right-click context menu on EventCard shows "Join Zoom Meeting" or "Join Google Meet" when a link is detected
- `MeetingNotificationDialog` shows a popup with live mm:ss countdown 5 minutes before meetings with meeting links
- Notification state tracked via QSettings key `notified_event_keys` (set of `event_id@timestamp` strings, capped at 200)
- Notification check runs in the existing 1-second `update_countdown()` timer — no additional timers needed
- The dialog has its own QTimer for the countdown label, acceptable since at most 0-1 dialogs exist at a time
