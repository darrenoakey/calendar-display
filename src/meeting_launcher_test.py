#!/usr/bin/env python3
# tests for meeting_launcher module

from meeting_link import MeetingLink
from meeting_launcher import (
    launch_meeting,
    open_zoommtg_url,
    open_url,
    check_zoom_installed,
    get_zoom_app_path,
)


# ##################################################################
# test open zoommtg url rejects non zoommtg urls
# proves validation rejects urls that don't start with zoommtg://
def test_open_zoommtg_url_rejects_invalid() -> None:
    assert not open_zoommtg_url("https://zoom.us/j/123")
    assert not open_zoommtg_url("invalid://url")
    assert not open_zoommtg_url("")


# ##################################################################
# test open url rejects non http urls
# proves validation rejects urls that don't start with http
def test_open_url_rejects_invalid() -> None:
    assert not open_url("zoommtg://zoom.us/join")
    assert not open_url("ftp://files.example.com")
    assert not open_url("")


# ##################################################################
# test launch meeting unknown type returns false
# proves launch_meeting returns False for unknown link types
def test_launch_meeting_unknown_type() -> None:
    link = MeetingLink(
        link_type="unknown",
        meeting_id="123",
        password=None,
        original_url="https://example.com",
        launch_url="https://example.com",
    )
    result = launch_meeting(link)
    assert result is False


# ##################################################################
# test launch meeting zoom type with invalid url returns false
# proves zoom dispatch validates the zoommtg:// prefix
def test_launch_meeting_zoom_rejects_bad_launch_url() -> None:
    link = MeetingLink(
        link_type="zoom",
        meeting_id="1234567890",
        password=None,
        original_url="https://zoom.us/j/1234567890",
        launch_url="https://not-a-zoommtg-url",
    )
    result = launch_meeting(link)
    assert result is False


# ##################################################################
# test launch meeting meet type with invalid url returns false
# proves meet dispatch validates the http:// prefix
def test_launch_meeting_meet_rejects_bad_launch_url() -> None:
    link = MeetingLink(
        link_type="meet",
        meeting_id="abc-defg-hij",
        password=None,
        original_url="https://meet.google.com/abc-defg-hij",
        launch_url="ftp://not-an-http-url",
    )
    result = launch_meeting(link)
    assert result is False


# ##################################################################
# test check zoom installed
# proves we can detect if zoom is installed
def test_check_zoom_installed() -> None:
    is_installed = check_zoom_installed()
    print(f"\nZoom installed: {is_installed}")
    assert is_installed, "Zoom is not installed on this system"


# ##################################################################
# test get zoom app path
# proves we can find the zoom application path
def test_get_zoom_app_path() -> None:
    path = get_zoom_app_path()
    print(f"\nZoom app path: {path}")
    assert path is not None, "Could not find Zoom app path"
    assert "zoom" in path.lower(), "Path does not appear to be Zoom"
