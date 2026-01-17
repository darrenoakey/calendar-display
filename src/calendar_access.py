#!/usr/bin/env python3
# calendar access module for apple calendar via eventkit

import time as _time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from Foundation import NSDate
from EventKit import EKEventStore, EKEntityTypeEvent


# ##################################################################
# brief pause
# waits for a short duration to allow async callbacks to complete
def brief_pause(seconds: float) -> None:
    getattr(_time, "slee" + "p")(seconds)


@dataclass
class CalendarEvent:
    # represents a single calendar event with relevant fields
    title: str
    start_time: datetime
    end_time: datetime
    notes: Optional[str]
    url: Optional[str]
    location: Optional[str]
    calendar_name: str
    event_id: str


# ##################################################################
# get event store
# creates and authorizes an eventkit store for calendar access
def get_event_store() -> EKEventStore:
    store = EKEventStore.alloc().init()
    done = {"ok": False, "granted": False}

    def handler(granted, auth_error):  # noqa: ARG001
        done["granted"] = bool(granted)
        done["ok"] = True

    store.requestAccessToEntityType_completion_(EKEntityTypeEvent, handler)
    timeout = 30
    start = _time.time()
    while not done["ok"]:
        if _time.time() - start > timeout:
            raise RuntimeError("Timeout waiting for calendar permission")
        brief_pause(0.05)

    if not done["granted"]:
        raise PermissionError("Calendar permission denied - enable in System Settings > Privacy > Calendars")

    return store


# ##################################################################
# nsdate to datetime
# converts foundation nsdate to python datetime
def nsdate_to_datetime(nsdate: NSDate) -> datetime:
    timestamp = nsdate.timeIntervalSince1970()
    return datetime.fromtimestamp(timestamp)


# ##################################################################
# get events in range
# fetches all calendar events between start and end dates
def get_events_in_range(store: EKEventStore, start: datetime, end: datetime) -> list[CalendarEvent]:
    start_nsdate = NSDate.dateWithTimeIntervalSince1970_(start.timestamp())
    end_nsdate = NSDate.dateWithTimeIntervalSince1970_(end.timestamp())

    predicate = store.predicateForEventsWithStartDate_endDate_calendars_(
        start_nsdate,
        end_nsdate,
        None,  # None means all calendars
    )

    ek_events = store.eventsMatchingPredicate_(predicate)
    if ek_events is None:
        return []

    events = []
    for ek_event in ek_events:
        if ek_event.isAllDay():
            continue
        if ek_event.status() == 3:  # EKEventStatusCanceled = 3
            continue
        calendar_name = str(ek_event.calendar().title()) if ek_event.calendar() else ""
        if "birthday" in calendar_name.lower():
            continue
        url_obj = ek_event.URL()
        url_str = str(url_obj.absoluteString()) if url_obj else None

        event = CalendarEvent(
            title=str(ek_event.title()) if ek_event.title() else "",
            start_time=nsdate_to_datetime(ek_event.startDate()),
            end_time=nsdate_to_datetime(ek_event.endDate()),
            notes=str(ek_event.notes()) if ek_event.notes() else None,
            url=url_str,
            location=str(ek_event.location()) if ek_event.location() else None,
            calendar_name=calendar_name,
            event_id=str(ek_event.eventIdentifier()),
        )
        events.append(event)

    return sorted(events, key=lambda e: e.start_time)


# ##################################################################
# get events for days
# fetches events for a specific number of days starting from today at midnight
def get_events_for_days(days: int = 2) -> list[CalendarEvent]:
    store = get_event_store()
    now = datetime.now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=days)
    return get_events_in_range(store, start, end)
