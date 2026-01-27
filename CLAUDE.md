# Calendar Display

## Running the App

Start the app using auto:
```
/auto start calendar-display
```

Do NOT launch directly with `python -m src.horizontal_calendar`.

## Python Version

This project requires Python 3.13 specifically because PySide6 is installed there. The `run` script uses `#!/usr/bin/env python3.13` - do not change this to generic `python3` as that resolves to 3.14 which lacks PySide6.
