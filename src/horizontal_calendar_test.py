#!/usr/bin/env python3
# tests for horizontal_calendar module

from datetime import datetime, timedelta

from horizontal_calendar import (
    DisplayConfig, DayColumn, EventCard, NextEventColumn, COLORS,
    format_duration, format_countdown, wrap_text, is_urgent, has_ended
)
from calendar_access import CalendarEvent


# ##################################################################
# test display config defaults
# verifies default configuration values
def test_display_config_defaults() -> None:
    config = DisplayConfig()
    assert config.days == 2
    assert config.refresh_interval_ms == 60000
    assert config.countdown_interval_ms == 1000
    assert config.card_height == 160


# ##################################################################
# test display config custom
# verifies custom configuration values
def test_display_config_custom() -> None:
    config = DisplayConfig(days=5, card_height=180)
    assert config.days == 5
    assert config.card_height == 180


# ##################################################################
# test colors defined
# verifies all required colors are defined
def test_colors_defined() -> None:
    required = ["background", "column_bg", "column_shadow", "header_text",
                "subheader_text", "countdown_text", "countdown_accent",
                "card_colors", "card_text", "card_text_muted"]
    for key in required:
        assert key in COLORS
    assert len(COLORS["card_colors"]) >= 3


# ##################################################################
# test format duration minutes
# verifies duration formatting for minutes only
def test_format_duration_minutes() -> None:
    assert format_duration(30) == "30m"
    assert format_duration(45) == "45m"
    assert format_duration(15) == "15m"


# ##################################################################
# test format duration hours
# verifies duration formatting for whole hours
def test_format_duration_hours() -> None:
    assert format_duration(60) == "1h"
    assert format_duration(120) == "2h"
    assert format_duration(180) == "3h"


# ##################################################################
# test format duration mixed
# verifies duration formatting for hours and minutes
def test_format_duration_mixed() -> None:
    assert format_duration(90) == "1h 30m"
    assert format_duration(75) == "1h 15m"
    assert format_duration(150) == "2h 30m"


# ##################################################################
# test format countdown seconds
# verifies countdown formatting for seconds
def test_format_countdown_seconds() -> None:
    number, label = format_countdown(45)
    assert number == "45"
    assert label == "seconds"


# ##################################################################
# test format countdown minutes
# verifies countdown formatting for minutes
def test_format_countdown_minutes() -> None:
    number, label = format_countdown(300)
    assert number == "5"
    assert label == "minutes"


# ##################################################################
# test format countdown hours
# verifies countdown formatting for hours only
def test_format_countdown_hours() -> None:
    number, label = format_countdown(7200)
    assert number == "2"
    assert label == "hours"
    number2, label2 = format_countdown(5400)
    assert number2 == "1"
    assert label2 == "hour"


# ##################################################################
# test format countdown days
# verifies countdown formatting for days only
def test_format_countdown_days() -> None:
    number, label = format_countdown(172800)
    assert number == "2"
    assert label == "days"
    number2, label2 = format_countdown(90000)
    assert number2 == "1"
    assert label2 == "day"


# ##################################################################
# test format countdown now
# verifies countdown shows now for zero or negative
def test_format_countdown_now() -> None:
    number, label = format_countdown(0)
    assert number == "Now"
    assert label == ""


# ##################################################################
# test wrap text single line
# verifies text that fits on one line is not wrapped
def test_wrap_text_single_line() -> None:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFont
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    font = QFont("Helvetica Neue", 13)
    lines = wrap_text("Short text", font, 300, 2)
    assert len(lines) == 1
    assert lines[0] == "Short text"


# ##################################################################
# test wrap text multiple lines
# verifies long text is wrapped to multiple lines
def test_wrap_text_multiple_lines() -> None:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFont
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    font = QFont("Helvetica Neue", 13)
    long_text = "This is a very long event title that should wrap to multiple lines"
    lines = wrap_text(long_text, font, 150, 2)
    assert len(lines) == 2


# ##################################################################
# test day column creation
# verifies day column can be created with title and subtitle
def test_day_column_creation() -> None:
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    column = DayColumn("Today", "Wednesday, January 15")
    assert column.title == "Today"


# ##################################################################
# test next event column creation
# verifies next event column can be created
def test_next_event_column_creation() -> None:
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    column = NextEventColumn()
    assert column.next_event is None


# ##################################################################
# test event card creation
# verifies event card can be created with an event
def test_event_card_creation() -> None:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QColor
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    event = CalendarEvent(
        title="Test Meeting",
        start_time=datetime.now(),
        end_time=datetime.now() + timedelta(hours=1),
        notes=None,
        url=None,
        location=None,
        calendar_name="Work",
        event_id="test1",
    )
    card = EventCard(event, QColor(66, 133, 244))
    assert card.calendar_event.title == "Test Meeting"


# ##################################################################
# test day column set events
# verifies events can be set on a day column
def test_day_column_set_events() -> None:
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    column = DayColumn("Today", "Wednesday, January 15")
    events = [
        CalendarEvent(
            title="Morning Meeting",
            start_time=datetime.now().replace(hour=9, minute=0),
            end_time=datetime.now().replace(hour=10, minute=0),
            notes=None, url=None, location=None,
            calendar_name="Work",
            event_id="m1",
        ),
        CalendarEvent(
            title="Lunch",
            start_time=datetime.now().replace(hour=12, minute=0),
            end_time=datetime.now().replace(hour=13, minute=0),
            notes=None, url=None, location=None,
            calendar_name="Personal",
            event_id="l1",
        ),
    ]
    column.set_events(events)
    assert column.cards_layout.count() == 2


# ##################################################################
# test color map assignment
# verifies calendars get assigned consistent colors
def test_color_map_assignment() -> None:
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    column = DayColumn("Today")
    events = [
        CalendarEvent(
            title="Work Event",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            notes=None, url=None, location=None,
            calendar_name="Work",
            event_id="w1",
        ),
        CalendarEvent(
            title="Personal Event",
            start_time=datetime.now() + timedelta(hours=2),
            end_time=datetime.now() + timedelta(hours=3),
            notes=None, url=None, location=None,
            calendar_name="Personal",
            event_id="p1",
        ),
    ]
    column.set_events(events)
    assert "Work" in column.calendar_color_map
    assert "Personal" in column.calendar_color_map


# ##################################################################
# test is urgent for event starting soon
# verifies event within 5 minutes is marked urgent
def test_is_urgent_starting_soon() -> None:
    now = datetime(2024, 1, 15, 10, 0, 0)
    event = CalendarEvent(
        title="Soon Event",
        start_time=datetime(2024, 1, 15, 10, 3, 0),  # 3 minutes from now
        end_time=datetime(2024, 1, 15, 11, 0, 0),
        notes=None, url=None, location=None,
        calendar_name="Work",
        event_id="s1",
    )
    assert is_urgent(event, now) is True


# ##################################################################
# test is urgent for active event
# verifies event currently happening is marked urgent
def test_is_urgent_active_event() -> None:
    now = datetime(2024, 1, 15, 10, 30, 0)
    event = CalendarEvent(
        title="Active Event",
        start_time=datetime(2024, 1, 15, 10, 0, 0),  # started 30 min ago
        end_time=datetime(2024, 1, 15, 11, 0, 0),
        notes=None, url=None, location=None,
        calendar_name="Work",
        event_id="a1",
    )
    assert is_urgent(event, now) is True


# ##################################################################
# test is urgent for future event
# verifies event more than 5 minutes away is not urgent
def test_is_urgent_future_event() -> None:
    now = datetime(2024, 1, 15, 10, 0, 0)
    event = CalendarEvent(
        title="Future Event",
        start_time=datetime(2024, 1, 15, 10, 10, 0),  # 10 minutes from now
        end_time=datetime(2024, 1, 15, 11, 0, 0),
        notes=None, url=None, location=None,
        calendar_name="Work",
        event_id="f1",
    )
    assert is_urgent(event, now) is False


# ##################################################################
# test is urgent for past event
# verifies event that has ended is not urgent
def test_is_urgent_past_event() -> None:
    now = datetime(2024, 1, 15, 12, 0, 0)
    event = CalendarEvent(
        title="Past Event",
        start_time=datetime(2024, 1, 15, 10, 0, 0),
        end_time=datetime(2024, 1, 15, 11, 0, 0),  # ended an hour ago
        notes=None, url=None, location=None,
        calendar_name="Work",
        event_id="pa1",
    )
    assert is_urgent(event, now) is False


# ##################################################################
# test is urgent at exactly 5 minutes
# verifies event exactly 5 minutes away is urgent
def test_is_urgent_exactly_five_minutes() -> None:
    now = datetime(2024, 1, 15, 10, 0, 0)
    event = CalendarEvent(
        title="Five Min Event",
        start_time=datetime(2024, 1, 15, 10, 5, 0),  # exactly 5 minutes
        end_time=datetime(2024, 1, 15, 11, 0, 0),
        notes=None, url=None, location=None,
        calendar_name="Work",
        event_id="fm1",
    )
    assert is_urgent(event, now) is True


# ##################################################################
# test is urgent at event start
# verifies event at exact start time is urgent
def test_is_urgent_at_start() -> None:
    now = datetime(2024, 1, 15, 10, 0, 0)
    event = CalendarEvent(
        title="Starting Now",
        start_time=datetime(2024, 1, 15, 10, 0, 0),  # exactly now
        end_time=datetime(2024, 1, 15, 11, 0, 0),
        notes=None, url=None, location=None,
        calendar_name="Work",
        event_id="sn1",
    )
    assert is_urgent(event, now) is True


# ##################################################################
# test is urgent at event end
# verifies event at exact end time is still urgent
def test_is_urgent_at_end() -> None:
    now = datetime(2024, 1, 15, 11, 0, 0)
    event = CalendarEvent(
        title="Ending Now",
        start_time=datetime(2024, 1, 15, 10, 0, 0),
        end_time=datetime(2024, 1, 15, 11, 0, 0),  # ending now
        notes=None, url=None, location=None,
        calendar_name="Work",
        event_id="en1",
    )
    assert is_urgent(event, now) is True


# ##################################################################
# test has ended for past event
# verifies event that ended is detected as ended
def test_has_ended_past_event() -> None:
    now = datetime(2024, 1, 15, 12, 0, 0)
    event = CalendarEvent(
        title="Past Event",
        start_time=datetime(2024, 1, 15, 10, 0, 0),
        end_time=datetime(2024, 1, 15, 11, 0, 0),  # ended an hour ago
        notes=None, url=None, location=None,
        calendar_name="Work",
        event_id="pe1",
    )
    assert has_ended(event, now) is True


# ##################################################################
# test has ended for active event
# verifies event currently happening is not ended
def test_has_ended_active_event() -> None:
    now = datetime(2024, 1, 15, 10, 30, 0)
    event = CalendarEvent(
        title="Active Event",
        start_time=datetime(2024, 1, 15, 10, 0, 0),
        end_time=datetime(2024, 1, 15, 11, 0, 0),
        notes=None, url=None, location=None,
        calendar_name="Work",
        event_id="ae1",
    )
    assert has_ended(event, now) is False


# ##################################################################
# test has ended for future event
# verifies future event is not ended
def test_has_ended_future_event() -> None:
    now = datetime(2024, 1, 15, 9, 0, 0)
    event = CalendarEvent(
        title="Future Event",
        start_time=datetime(2024, 1, 15, 10, 0, 0),
        end_time=datetime(2024, 1, 15, 11, 0, 0),
        notes=None, url=None, location=None,
        calendar_name="Work",
        event_id="fe1",
    )
    assert has_ended(event, now) is False


# ##################################################################
# test has ended at exact end time
# verifies event at exact end time is not yet ended (boundary case)
def test_has_ended_at_exact_end_time() -> None:
    now = datetime(2024, 1, 15, 11, 0, 0)
    event = CalendarEvent(
        title="Ending Now",
        start_time=datetime(2024, 1, 15, 10, 0, 0),
        end_time=datetime(2024, 1, 15, 11, 0, 0),  # ending exactly now
        notes=None, url=None, location=None,
        calendar_name="Work",
        event_id="een1",
    )
    # at exact end time, event has NOT ended (now > end_time is false)
    assert has_ended(event, now) is False


# ##################################################################
# test has ended one second after end
# verifies event just after end time is ended
def test_has_ended_one_second_after() -> None:
    now = datetime(2024, 1, 15, 11, 0, 1)
    event = CalendarEvent(
        title="Just Ended",
        start_time=datetime(2024, 1, 15, 10, 0, 0),
        end_time=datetime(2024, 1, 15, 11, 0, 0),
        notes=None, url=None, location=None,
        calendar_name="Work",
        event_id="je1",
    )
    assert has_ended(event, now) is True
