# Calendar Display

## Running the App

Start the app using auto:
```
/auto start calendar-display
```

Do NOT launch directly with `python -m src.horizontal_calendar`.

### Calendar Sources

**Agent-Link Integration REQUIRED**: Fetches events from all connected calendar sources
- Apple Calendar (native)
- Google Calendar (requires OAuth configuration in agent-link)
- **Start agent-link first**: `/auto start agent-link`
- Calendar-display will show empty calendar if agent-link is not available

**No EventKit fallback** - agent-link is the only calendar backend.

## Python Version

This project requires Python 3.13 specifically because PySide6 is installed there. The `run` script uses `#!/usr/bin/env python3.13` - do not change this to generic `python3` as that resolves to 3.14 which lacks PySide6.

## Architecture Notes

### Event Card Colors
Colors are assigned **per event** using MD5 hash of `event_id` mod palette size — not per calendar. This ensures multiple events from the same calendar get visually distinct colors. There is NO `calendar_color_map`; do not re-introduce one. Pattern: `int(hashlib.md5(event_id.encode()).hexdigest(), 16) % len(COLORS["card_colors"])`.

### Compact Card Mode
When a day has more than `COMPACT_THRESHOLD` (4) timed events, `DayColumn.set_events()` renders `CompactEventCard` (56px, single-line: time + elided title) instead of full `EventCard` (160px). Spacing also tightens (6px vs 14px). Both card types support flash animation and right-click meeting links. Do NOT remove this adaptive behavior or hardcode one mode — busy days need compact cards to remain readable.

### Flash Animation
The flash animation for urgent events uses a **single shared QTimer** in MainWindow that iterates through all EventCards. Do NOT create individual timers per card - this causes memory issues from timer accumulation during refresh cycles.

### Memory Considerations
- PySide6/Qt on macOS shows very high virtual memory (VSZ ~400GB) which is normal - Metal backend reserves large address spaces
- Actual physical memory (RSS/footprint) is what matters - should be <100MB
- Use `footprint <pid>` to check real memory usage, not `ps` VSZ column

### Agent-Link SSE Integration

Calendar events are fetched via SSE subscription to `GET /api/v1/events/subscribe`:
- `?type=calendar.event.*&snapshot=true&time_min=...&time_max=...`
- Snapshot events arrive first with type `"calendar.event.snapshot"`, then live events
- All sources normalized to `CalendarEventPayload` format: `event_id`, `calendar_id`, `start`/`end` (RFC3339 strings), `summary`, `description`, `location`
- **NOT** the raw Google/Apple format (no nested `{dateTime}` objects, no `id`/`calendar` fields)
- `EventSSEWorker` auto-reconnects with 5s backoff; emits `reconnecting` signal so MainWindow clears stale events before new snapshot
- **Midnight reconnect** (three independent mechanisms — do NOT reduce to one):
  1. `_display_date` check in `update_countdown()` (1-second timer): compares `datetime.now().date()` against stored date, forces SSE reconnect on change. This is the primary mechanism — runs on Qt main thread, independent of SSE events.
  2. `midnight_timer` (one-shot QTimer): fires precisely at 00:00:01, forces SSE reconnect, reschedules for next midnight. Belt-and-suspenders with mechanism 1.
  3. SSE worker `connection_date` check: runs inside `iter_lines()` loop, only fires when an SSE line arrives (unreliable at midnight when no events are published — this alone is NOT sufficient).
- **Cancelled events**: `on_event_update` skips events with `status == "cancelled"` and removes them from `all_events` if previously stored.

**Agent-link structured logs** go to `~/.agent-link/agent-link.log` (JSON NDJSON), NOT to the auto process manager stdout log. Always check this file for calendar watcher activity.

**Timezone handling**: `parse_rfc3339()` returns tz-aware datetimes. `parse_event_from_sse()` converts to naive local time via `.astimezone().replace(tzinfo=None)` so events compare cleanly with `datetime.now()`.

### Meeting Notifications (integrated from calendar-notifications)
- `meeting_link.py`: Extracts Zoom and Google Meet links from calendar events (url > location > notes field priority, Zoom before Meet)
- `meeting_launcher.py`: Launches meetings via `zoommtg://` for Zoom or `open` for Meet (fire-and-forget subprocess)
- Right-click context menu on EventCard shows "Join Zoom Meeting" or "Join Google Meet" when a link is detected
- `MeetingNotificationDialog` shows a popup with live mm:ss countdown 5 minutes before meetings with meeting links
- Notification state tracked via QSettings key `notified_event_keys` (set of `event_id@timestamp` strings, capped at 200)
- Notification check runs in the existing 1-second `update_countdown()` timer — no additional timers needed
- The dialog has its own QTimer for the countdown label, acceptable since at most 0-1 dialogs exist at a time

### All-Day Events
- Detected in `parse_event_from_sse()` by `"T" not in start_str` (date-only strings like `"2026-02-21"` vs timed `"2026-02-21T08:30:00+11:00"`)
- Stored in `CalendarEvent.is_all_day = True`
- Displayed as `AllDayStrip` widgets (42px tall, light color-tinted bg, 4px left color bar, event name 16pt) — rendered above timed event cards in each `DayColumn`
- Excluded from Next Event countdown (`get_next_event` filters `not e.is_all_day`)
- Do NOT filter them out in `_do_update_display` — they still have `start_time`/`end_time` at midnight boundaries which `has_ended()` handles correctly

### Post-Reboot SSE Race Condition
After a reboot, agent-link needs time to complete its initial poll. With EventKit (replacing osascript Feb 2026), the initial poll completes in ~10s. The 45s startup check in `check_startup_events` is usually sufficient now. If the display is still empty, `auto restart calendar-display` once agent-link logs show events published (`~/.agent-link/agent-link.log`).

### Agent-Link Binary Deployment
`auto show agent-link` reveals the binary path auto uses (e.g. `src/agent-link`). After `./run build` in agent-link, the binary goes to `output/bin/agent-link`. You must **copy both `agent-link` and `eventkit-helper`** to the path auto expects, then `auto restart agent-link`.
