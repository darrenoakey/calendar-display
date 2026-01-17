#!/usr/bin/env python3
# tests for calendar_access module

from datetime import datetime, timedelta

from calendar_access import CalendarEvent, get_event_store, get_events_in_range, get_events_for_days


# ##################################################################
# test event dataclass
# verifies that calendar event can be constructed with all fields
def test_event_dataclass() -> None:
    event = CalendarEvent(
        title="Team Meeting",
        start_time=datetime(2024, 1, 15, 10, 0),
        end_time=datetime(2024, 1, 15, 11, 0),
        notes="Discuss quarterly goals",
        url="https://zoom.us/j/123456",
        location="Conference Room A",
        calendar_name="Work",
        event_id="abc123",
    )
    assert event.title == "Team Meeting"
    assert event.start_time.hour == 10
    assert event.end_time.hour == 11
    assert event.notes == "Discuss quarterly goals"
    assert event.calendar_name == "Work"


# ##################################################################
# test event dataclass optional fields
# verifies that optional fields can be none
def test_event_dataclass_optional_fields() -> None:
    event = CalendarEvent(
        title="Quick Sync",
        start_time=datetime(2024, 1, 15, 14, 0),
        end_time=datetime(2024, 1, 15, 14, 30),
        notes=None,
        url=None,
        location=None,
        calendar_name="Personal",
        event_id="def456",
    )
    assert event.notes is None
    assert event.url is None
    assert event.location is None


# ##################################################################
# test get event store
# verifies that event store can be obtained with permission
def test_get_event_store() -> None:
    store = get_event_store()
    assert store is not None


# ##################################################################
# test get events in range
# verifies that events can be fetched for a date range
def test_get_events_in_range() -> None:
    store = get_event_store()
    now = datetime.now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    events = get_events_in_range(store, start, end)
    assert isinstance(events, list)
    for event in events:
        assert isinstance(event, CalendarEvent)
        assert event.start_time >= start
        assert event.start_time <= end


# ##################################################################
# test get events for days
# verifies the convenience function for fetching multiple days
def test_get_events_for_days() -> None:
    events = get_events_for_days(days=2)
    assert isinstance(events, list)
    for event in events:
        assert isinstance(event, CalendarEvent)


# ##################################################################
# test events sorted by start time
# verifies that returned events are sorted chronologically
def test_events_sorted_by_start_time() -> None:
    events = get_events_for_days(days=7)
    if len(events) >= 2:
        for i in range(len(events) - 1):
            assert events[i].start_time <= events[i + 1].start_time
