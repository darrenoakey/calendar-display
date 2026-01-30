# Calendar Display

## Running the App

Start the app using auto:
```
/auto start calendar-display
```

Do NOT launch directly with `python -m src.horizontal_calendar`.

## Python Version

This project requires Python 3.13 specifically because PySide6 is installed there. The `run` script uses `#!/usr/bin/env python3.13` - do not change this to generic `python3` as that resolves to 3.14 which lacks PySide6.

## Architecture Notes

### Flash Animation
The flash animation for urgent events uses a **single shared QTimer** in MainWindow that iterates through all EventCards. Do NOT create individual timers per card - this causes memory issues from timer accumulation during refresh cycles.

### Memory Considerations
- PySide6/Qt on macOS shows very high virtual memory (VSZ ~400GB) which is normal - Metal backend reserves large address spaces
- Actual physical memory (RSS/footprint) is what matters - should be <100MB
- Use `footprint <pid>` to check real memory usage, not `ps` VSZ column
