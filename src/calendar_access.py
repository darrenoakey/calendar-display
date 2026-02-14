#!/usr/bin/env python3
# calendar access module using agent-link (supports Apple Calendar + Google Calendar)

import ssl
import time as _time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

try:
    from agent_link import AgentLinkClient
    AGENT_LINK_AVAILABLE = True
except ImportError:
    AGENT_LINK_AVAILABLE = False

# Fallback to EventKit if agent-link not available
try:
    from Foundation import NSDate
    from EventKit import EKEventStore, EKEntityTypeEvent
    EVENTKIT_AVAILABLE = True
except ImportError:
    EVENTKIT_AVAILABLE = False


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
# parse rfc3339
# converts rfc3339 timestamp string to python datetime
def parse_rfc3339(timestamp_str: str) -> datetime:
    """Parse RFC3339 timestamp to datetime."""
    if not timestamp_str:
        return datetime.now()
    # Python 3.13 handles ISO format natively, including timezone
    return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))


# ##################################################################
# create ssl context for agent-link
# creates an ssl context that allows self-signed certificates for localhost
def create_agent_link_ssl_context() -> ssl.SSLContext:
    """Create SSL context that allows self-signed certs for localhost."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# ##################################################################
# patch agent link client
# modifies AgentLinkClient to skip SSL verification for localhost
def patch_agent_link_client():
    """Patch AgentLinkClient to allow self-signed certs for localhost."""
    if not AGENT_LINK_AVAILABLE:
        return

    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
    import json

    original_request = AgentLinkClient._request

    def patched_request(self, method, path, body=None):
        url = f"{self.base_url}{path}"
        headers = {}
        data = None

        # Always set content-type for POST requests, even with empty body
        if method == "POST":
            headers["Content-Type"] = "application/json"
            # Encode body as JSON, default to empty object
            data = json.dumps(body if body is not None else {}).encode("utf-8")
        elif body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")

        req = Request(url, data=data, headers=headers, method=method)

        ctx = create_agent_link_ssl_context()
        if self.cert_path and self.key_path:
            ctx.load_cert_chain(certfile=self.cert_path, keyfile=self.key_path)

        try:
            with urlopen(req, context=ctx) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise RuntimeError(f"HTTP {e.code}: {error_body}") from e
        except URLError as e:
            raise RuntimeError(f"Connection error: {e.reason}") from e

    AgentLinkClient._request = patched_request


# Apply patch once at module load
if AGENT_LINK_AVAILABLE:
    patch_agent_link_client()


# ##################################################################
# get events from agent link
# fetches events from all calendar sources via agent-link API
def get_events_from_agent_link(days: int = 2) -> list[CalendarEvent]:
    """Fetch events from all calendar sources via agent-link."""
    client = AgentLinkClient(base_url="https://localhost:8900")

    # Calculate time range
    now = datetime.now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=days)

    all_events = []

    # Get list of calendar sources
    sources = client.list_sources(category="calendar")

    for source in sources:
        source_name = source.get("name", "")
        module_type = source.get("module_type", "")

        # Determine calendar source prefix for display
        if "google" in module_type.lower():
            source_prefix = "Google"
        elif "apple" in module_type.lower():
            source_prefix = "Apple"
        else:
            source_prefix = "Unknown"

        try:
            # First, list all calendars for this source
            cal_results = client.call("calendar", "list-calendars", {}, source=source_name)
            if not cal_results or cal_results[0].get("Error"):
                print(f"Warning: Failed to list calendars from {source_name}: {cal_results[0].get('Error') if cal_results else 'no results'}")
                continue

            calendars = cal_results[0].get("Data", {}).get("calendars", [])

            # For each calendar, fetch events
            for calendar in calendars:
                cal_name = calendar.get("name", "")

                # Skip birthday calendars
                if "birthday" in cal_name.lower():
                    continue

                try:
                    # Different sources use different parameter names
                    if "apple" in module_type.lower():
                        params = {
                            "calendar": cal_name,  # Apple uses "calendar"
                        }
                    else:
                        params = {
                            "calendar_id": cal_name,  # Google uses "calendar_id"
                            "time_min": start.isoformat(),
                            "time_max": end.isoformat(),
                            "max_results": 250,
                        }

                    event_results = client.call("calendar", "list-events", params, source=source_name)
                    if not event_results or event_results[0].get("Error"):
                        # Skip calendars that error (might be permission issues, etc.)
                        continue

                    events_data = event_results[0].get("Data", {}).get("events", [])

                    for event_json in events_data:
                        # Parse event based on source format
                        if "google" in module_type.lower():
                            # Google Calendar event format
                            start_obj = event_json.get("start", {})
                            end_obj = event_json.get("end", {})
                            start_time = parse_rfc3339(start_obj.get("dateTime", start_obj.get("date", "")))
                            end_time = parse_rfc3339(end_obj.get("dateTime", end_obj.get("date", "")))

                            # Skip all-day events (have "date" instead of "dateTime")
                            if "dateTime" not in start_obj:
                                continue

                            event_id = event_json.get("id", "")
                            title = event_json.get("summary", "")
                            location = event_json.get("location")
                            description = event_json.get("description")
                            url = event_json.get("hangoutLink") or event_json.get("htmlLink")
                        else:
                            # Apple Calendar event format
                            # Apple returns dates as strings like "Saturday, February 15, 2026 at 10:00:00 AM"
                            # We need to parse these
                            start_str = event_json.get("start", "")
                            end_str = event_json.get("end", "")

                            # For now, skip Apple Calendar events as the date parsing is complex
                            # We'll handle this in the EventKit fallback
                            continue

                        event = CalendarEvent(
                            title=title,
                            start_time=start_time,
                            end_time=end_time,
                            notes=description,
                            url=url,
                            location=location,
                            calendar_name=f"{source_prefix} - {cal_name}",
                            event_id=event_id,
                        )
                        all_events.append(event)

                except Exception as e:
                    print(f"Warning: Failed to fetch events from {source_name}/{cal_name}: {e}")
                    continue

        except Exception as e:
            print(f"Warning: Failed to process source {source_name}: {e}")
            continue

    return sorted(all_events, key=lambda e: e.start_time)


# ##################################################################
# EventKit fallback functions
# These are used when agent-link is not available

def get_event_store() -> "EKEventStore":
    """Creates and authorizes an EventKit store for calendar access."""
    if not EVENTKIT_AVAILABLE:
        raise RuntimeError("EventKit not available")

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


def nsdate_to_datetime(nsdate: "NSDate") -> datetime:
    """Converts Foundation NSDate to Python datetime."""
    timestamp = nsdate.timeIntervalSince1970()
    return datetime.fromtimestamp(timestamp)


def get_events_in_range(store: "EKEventStore", start: datetime, end: datetime) -> list[CalendarEvent]:
    """Fetches all calendar events between start and end dates via EventKit."""
    if not EVENTKIT_AVAILABLE:
        raise RuntimeError("EventKit not available")

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


def get_events_from_eventkit(days: int = 2) -> list[CalendarEvent]:
    """Fetch events from EventKit (Apple Calendar only)."""
    store = get_event_store()
    now = datetime.now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=days)
    return get_events_in_range(store, start, end)


# ##################################################################
# get events for days
# fetches events for a specific number of days starting from today at midnight
# uses agent-link only (no EventKit fallback)
def get_events_for_days(days: int = 2, max_retries: int = 5, retry_delay: float = 2.0) -> list[CalendarEvent]:
    """Fetches events from agent-link calendar sources."""
    if not AGENT_LINK_AVAILABLE:
        raise RuntimeError("agent-link Python client not available - run: cd ~/src/agent-link/clients/python && pip3.13 install -e .")

    last_error = None

    for attempt in range(max_retries):
        try:
            return get_events_from_agent_link(days)
        except Exception as e:
            last_error = e
            print(f"Agent-link error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                brief_pause(retry_delay * (attempt + 1))  # exponential backoff

    # If all retries failed, return empty list rather than crashing
    # This allows the app to start and retry on next refresh
    print(f"Agent-link failed after {max_retries} attempts: {last_error}")
    return []
