#!/usr/bin/env python3
# tests for meeting_link module

from datetime import datetime, timedelta

from calendar_access import CalendarEvent, get_events_for_days
from meeting_link import (
    MeetingLink,
    find_zoom_url_in_text,
    find_meet_url_in_text,
    parse_zoom_url,
    parse_meet_url,
    build_zoommtg_url,
    extract_meeting_link,
    notification_key,
)


# helper to create a test event with specific fields
def make_event(
    url=None, location=None, notes=None, title="Test", event_id="evt1",
    start_time=None, end_time=None,
):
    now = datetime.now()
    return CalendarEvent(
        title=title,
        start_time=start_time or now,
        end_time=end_time or now + timedelta(hours=1),
        notes=notes,
        url=url,
        location=location,
        calendar_name="Work",
        event_id=event_id,
    )


# ##################################################################
# test find zoom url standard link
# proves we can find a standard zoom.us/j/ url in text
def test_find_zoom_url_standard() -> None:
    text = "Join the meeting at https://zoom.us/j/1234567890"
    url = find_zoom_url_in_text(text)
    assert url == "https://zoom.us/j/1234567890"


# ##################################################################
# test find zoom url with password
# proves we can find a zoom url with password parameter
def test_find_zoom_url_with_password() -> None:
    text = "Link: https://zoom.us/j/1234567890?pwd=abc123xyz"
    url = find_zoom_url_in_text(text)
    assert url == "https://zoom.us/j/1234567890?pwd=abc123xyz"


# ##################################################################
# test find zoom url company subdomain
# proves we can find zoom urls with company subdomains
def test_find_zoom_url_company_subdomain() -> None:
    text = "Meeting: https://company.zoom.us/j/9876543210"
    url = find_zoom_url_in_text(text)
    assert url == "https://company.zoom.us/j/9876543210"


# ##################################################################
# test find zoom url personal room
# proves we can find personal meeting room links
def test_find_zoom_url_personal_room() -> None:
    text = "My room: https://zoom.us/my/john.smith"
    url = find_zoom_url_in_text(text)
    assert url == "https://zoom.us/my/john.smith"


# ##################################################################
# test find zoom url none for empty text
# proves None text returns None
def test_find_zoom_url_none_text() -> None:
    assert find_zoom_url_in_text(None) is None
    assert find_zoom_url_in_text("") is None


# ##################################################################
# test find zoom url no match
# proves non-zoom text returns None
def test_find_zoom_url_no_match() -> None:
    assert find_zoom_url_in_text("No meeting link here") is None
    assert find_zoom_url_in_text("https://google.com/meeting") is None


# ##################################################################
# test find meet url standard
# proves we can find google meet urls
def test_find_meet_url_standard() -> None:
    text = "Join at https://meet.google.com/abc-defg-hij"
    url = find_meet_url_in_text(text)
    assert url == "https://meet.google.com/abc-defg-hij"


# ##################################################################
# test find meet url none for empty text
# proves None text returns None for meet
def test_find_meet_url_none_text() -> None:
    assert find_meet_url_in_text(None) is None
    assert find_meet_url_in_text("") is None


# ##################################################################
# test find meet url no match
# proves non-meet text returns None
def test_find_meet_url_no_match() -> None:
    assert find_meet_url_in_text("https://zoom.us/j/123") is None
    assert find_meet_url_in_text("No link here") is None


# ##################################################################
# test parse zoom url standard
# proves parsing extracts meeting id correctly
def test_parse_zoom_url_standard() -> None:
    link = parse_zoom_url("https://zoom.us/j/1234567890")
    assert link is not None
    assert link.link_type == "zoom"
    assert link.meeting_id == "1234567890"
    assert link.password is None
    assert link.launch_url.startswith("zoommtg://")


# ##################################################################
# test parse zoom url with password
# proves parsing extracts password correctly
def test_parse_zoom_url_with_password() -> None:
    link = parse_zoom_url("https://zoom.us/j/1234567890?pwd=abc123")
    assert link is not None
    assert link.meeting_id == "1234567890"
    assert link.password == "abc123"
    assert "pwd=abc123" in link.launch_url


# ##################################################################
# test parse zoom url personal room
# proves personal room links are parsed
def test_parse_zoom_url_personal_room() -> None:
    link = parse_zoom_url("https://zoom.us/my/john.smith")
    assert link is not None
    assert link.meeting_id == "john.smith"
    assert link.link_type == "zoom"


# ##################################################################
# test parse zoom url empty
# proves empty/None input returns None
def test_parse_zoom_url_empty() -> None:
    assert parse_zoom_url("") is None
    assert parse_zoom_url(None) is None


# ##################################################################
# test parse meet url standard
# proves google meet urls are parsed correctly
def test_parse_meet_url_standard() -> None:
    link = parse_meet_url("https://meet.google.com/abc-defg-hij")
    assert link is not None
    assert link.link_type == "meet"
    assert link.meeting_id == "abc-defg-hij"
    assert link.password is None
    assert link.launch_url == "https://meet.google.com/abc-defg-hij"


# ##################################################################
# test parse meet url empty
# proves empty/None input returns None
def test_parse_meet_url_empty() -> None:
    assert parse_meet_url("") is None
    assert parse_meet_url(None) is None


# ##################################################################
# test build zoommtg url without password
# proves zoommtg url is built correctly without password
def test_build_zoommtg_url_no_password() -> None:
    url = build_zoommtg_url("1234567890")
    assert url == "zoommtg://zoom.us/join?action=join&confno=1234567890"


# ##################################################################
# test build zoommtg url with password
# proves zoommtg url is built correctly with password
def test_build_zoommtg_url_with_password() -> None:
    url = build_zoommtg_url("1234567890", "abc123")
    assert url == "zoommtg://zoom.us/join?action=join&confno=1234567890&pwd=abc123"


# ##################################################################
# test extract meeting link from url field
# proves zoom link in url field is found first
def test_extract_meeting_link_url_field() -> None:
    event = make_event(url="https://zoom.us/j/111222333")
    link = extract_meeting_link(event)
    assert link is not None
    assert link.link_type == "zoom"
    assert link.meeting_id == "111222333"


# ##################################################################
# test extract meeting link from location field
# proves zoom link in location field is found when url has none
def test_extract_meeting_link_location_field() -> None:
    event = make_event(location="https://zoom.us/j/444555666")
    link = extract_meeting_link(event)
    assert link is not None
    assert link.meeting_id == "444555666"


# ##################################################################
# test extract meeting link from notes field
# proves zoom link in notes field is found when url and location have none
def test_extract_meeting_link_notes_field() -> None:
    event = make_event(notes="Join here: https://zoom.us/j/777888999")
    link = extract_meeting_link(event)
    assert link is not None
    assert link.meeting_id == "777888999"


# ##################################################################
# test extract meeting link google meet
# proves google meet links are detected
def test_extract_meeting_link_google_meet() -> None:
    event = make_event(url="https://meet.google.com/abc-defg-hij")
    link = extract_meeting_link(event)
    assert link is not None
    assert link.link_type == "meet"
    assert link.meeting_id == "abc-defg-hij"


# ##################################################################
# test extract meeting link zoom priority over meet
# proves zoom is preferred when both present across fields
def test_extract_meeting_link_zoom_priority() -> None:
    event = make_event(
        url="https://zoom.us/j/111222333",
        notes="https://meet.google.com/abc-defg-hij",
    )
    link = extract_meeting_link(event)
    assert link is not None
    assert link.link_type == "zoom"


# ##################################################################
# test extract meeting link no link
# proves None is returned when no meeting link found
def test_extract_meeting_link_no_link() -> None:
    event = make_event(url="https://google.com", notes="Just a regular meeting")
    assert extract_meeting_link(event) is None


# ##################################################################
# test extract meeting link all fields none
# proves None is returned when all fields are None
def test_extract_meeting_link_all_none() -> None:
    event = make_event()
    assert extract_meeting_link(event) is None


# ##################################################################
# test notification key format
# proves notification key includes event_id and timestamp
def test_notification_key_format() -> None:
    event = make_event(event_id="abc123", start_time=datetime(2024, 6, 15, 10, 0, 0))
    key = notification_key(event)
    assert key.startswith("abc123@")
    assert "@" in key


# ##################################################################
# test notification key consistency
# proves same event produces the same key
def test_notification_key_consistency() -> None:
    start = datetime(2024, 6, 15, 10, 0, 0)
    event1 = make_event(event_id="evt1", start_time=start)
    event2 = make_event(event_id="evt1", start_time=start)
    assert notification_key(event1) == notification_key(event2)


# ##################################################################
# test notification key different for recurring events
# proves different start times produce different keys
def test_notification_key_recurring() -> None:
    event1 = make_event(event_id="evt1", start_time=datetime(2024, 6, 15, 10, 0))
    event2 = make_event(event_id="evt1", start_time=datetime(2024, 6, 22, 10, 0))
    assert notification_key(event1) != notification_key(event2)


# ##################################################################
# test extract meeting link from real calendar events
# proves we can find meeting links in actual calendar data
def test_extract_meeting_link_real_calendar() -> None:
    events = get_events_for_days(7)
    links_found = []
    for event in events:
        link = extract_meeting_link(event)
        if link:
            links_found.append((event, link))

    print(f"\nFound {len(links_found)} meeting links in calendar:")
    for event, link in links_found:
        print(f"  - {event.start_time.strftime('%Y-%m-%d %H:%M')} | {event.title}")
        print(f"    Type: {link.link_type}, ID: {link.meeting_id}")
        print(f"    Launch URL: {link.launch_url}")

    # verify structure of any found links
    for event, link in links_found:
        assert isinstance(link, MeetingLink)
        assert link.link_type in ("zoom", "meet")
        assert link.meeting_id
        assert link.launch_url
