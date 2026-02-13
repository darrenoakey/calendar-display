#!/usr/bin/env python3
# meeting launcher for opening zoom and google meet meetings

import subprocess
from typing import Optional

from meeting_link import MeetingLink


# ##################################################################
# launch meeting
# dispatches to the appropriate launcher based on link type
def launch_meeting(link: MeetingLink) -> bool:
    if link.link_type == "zoom":
        return open_zoommtg_url(link.launch_url)
    if link.link_type == "meet":
        return open_url(link.launch_url)
    return False


# ##################################################################
# open zoommtg url
# opens a zoommtg:// url using macos open command (fire-and-forget)
def open_zoommtg_url(zoommtg_url: str) -> bool:
    if not zoommtg_url.startswith("zoommtg://"):
        return False
    try:
        subprocess.Popen(
            ["open", zoommtg_url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except Exception:
        return False


# ##################################################################
# open url
# opens a url in the default browser (fire-and-forget)
def open_url(url: str) -> bool:
    if not url.startswith("http://") and not url.startswith("https://"):
        return False
    try:
        subprocess.Popen(
            ["open", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except Exception:
        return False


# ##################################################################
# check zoom installed
# verifies that zoom is installed on the system using spotlight
def check_zoom_installed() -> bool:
    try:
        result = subprocess.run(
            ["mdfind", "kMDItemCFBundleIdentifier == 'us.zoom.xos'"],
            capture_output=True, text=True, timeout=10,
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


# ##################################################################
# get zoom app path
# returns the path to the zoom application if installed
def get_zoom_app_path() -> Optional[str]:
    try:
        result = subprocess.run(
            ["mdfind", "kMDItemCFBundleIdentifier == 'us.zoom.xos'"],
            capture_output=True, text=True, timeout=10,
        )
        paths = result.stdout.strip().split("\n")
        return paths[0] if paths and paths[0] else None
    except Exception:
        return None
