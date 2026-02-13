#!/usr/bin/env python3
# meeting link extraction for zoom and google meet from calendar events

import re
from dataclasses import dataclass
from typing import Optional

from calendar_access import CalendarEvent


@dataclass
class MeetingLink:
    # represents a parsed meeting link with connection details
    link_type: str  # "zoom" or "meet"
    meeting_id: str
    password: Optional[str]
    original_url: str
    launch_url: str


# zoom url patterns to match
ZOOM_PATTERNS = [
    # https://zoom.us/j/MEETING_ID?pwd=PASSWORD
    r"https?://(?:[\w-]+\.)?zoom\.us/j/(\d+)(?:\?pwd=([a-zA-Z0-9]+))?",
    # https://zoom.us/my/PERSONAL_LINK
    r"https?://(?:[\w-]+\.)?zoom\.us/my/([\w.-]+)",
    # zoommtg://zoom.us/join?confno=MEETING_ID
    r"zoommtg://(?:[\w-]+\.)?zoom\.us/join\?(?:.*&)?confno=(\d+)",
]

# google meet pattern
MEET_PATTERN = r"https?://meet\.google\.com/([\w-]+-[\w-]+-[\w-]+)"


# ##################################################################
# find zoom url in text
# searches text for any zoom meeting url pattern
def find_zoom_url_in_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    for pattern in ZOOM_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)
    return None


# ##################################################################
# find meet url in text
# searches text for a google meet url pattern
def find_meet_url_in_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    match = re.search(MEET_PATTERN, text, re.IGNORECASE)
    if match:
        return match.group(0)
    return None


# ##################################################################
# parse zoom url
# extracts meeting id and password from a zoom url
def parse_zoom_url(url: Optional[str]) -> Optional[MeetingLink]:
    if not url:
        return None

    meeting_id = None
    password = None

    # try standard format: zoom.us/j/MEETING_ID
    match = re.search(r"zoom\.us/j/(\d+)", url, re.IGNORECASE)
    if match:
        meeting_id = match.group(1)

    # try personal meeting room: zoom.us/my/PERSONAL_LINK
    if not meeting_id:
        match = re.search(r"zoom\.us/my/([\w.-]+)", url, re.IGNORECASE)
        if match:
            meeting_id = match.group(1)

    # try zoommtg format: confno=MEETING_ID
    if not meeting_id:
        match = re.search(r"confno=(\d+)", url, re.IGNORECASE)
        if match:
            meeting_id = match.group(1)

    if not meeting_id:
        return None

    # extract password if present
    pwd_match = re.search(r"[?&]pwd=([a-zA-Z0-9]+)", url)
    if pwd_match:
        password = pwd_match.group(1)

    launch_url = build_zoommtg_url(meeting_id, password)
    return MeetingLink(
        link_type="zoom",
        meeting_id=meeting_id,
        password=password,
        original_url=url,
        launch_url=launch_url,
    )


# ##################################################################
# parse meet url
# extracts meeting code from a google meet url
def parse_meet_url(url: Optional[str]) -> Optional[MeetingLink]:
    if not url:
        return None
    match = re.search(MEET_PATTERN, url, re.IGNORECASE)
    if not match:
        return None
    meeting_code = match.group(1)
    return MeetingLink(
        link_type="meet",
        meeting_id=meeting_code,
        password=None,
        original_url=url,
        launch_url=url,
    )


# ##################################################################
# build zoommtg url
# constructs a zoommtg:// url for direct zoom launch
def build_zoommtg_url(meeting_id: str, password: Optional[str] = None) -> str:
    base = f"zoommtg://zoom.us/join?action=join&confno={meeting_id}"
    if password:
        base += f"&pwd={password}"
    return base


# ##################################################################
# extract meeting link
# searches all fields of a calendar event for zoom or meet links
# priority: url > location > notes; zoom checked before meet in each field
def extract_meeting_link(event: CalendarEvent) -> Optional[MeetingLink]:
    fields = [event.url, event.location, event.notes]

    # check each field for zoom first, then meet
    for field in fields:
        zoom_url = find_zoom_url_in_text(field)
        if zoom_url:
            return parse_zoom_url(zoom_url)

    for field in fields:
        meet_url = find_meet_url_in_text(field)
        if meet_url:
            return parse_meet_url(meet_url)

    return None


# ##################################################################
# notification key
# generates a unique key for tracking meeting notifications
# uses event_id + start_time timestamp to handle recurring events
def notification_key(event: CalendarEvent) -> str:
    timestamp = int(event.start_time.timestamp())
    return f"{event.event_id}@{timestamp}"
