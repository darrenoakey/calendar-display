#!/usr/bin/env python3
# vertical card-based calendar display with material design

import hashlib
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QRectF, QSettings, QThread, Signal
from PySide6.QtGui import QPainter, QColor, QFont, QBrush, QLinearGradient, QFontMetrics, QIcon, QAction
from PySide6.QtWidgets import (
    QWidget, QMainWindow, QApplication, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QGraphicsDropShadowEffect, QMenu, QDialog, QPushButton
)

from calendar_access import CalendarEvent
from meeting_link import MeetingLink, extract_meeting_link, notification_key
from meeting_launcher import launch_meeting

SETTINGS_ORG = "CalendarDisplay"
SETTINGS_APP = "CalendarDisplay"
ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "calendar-display-icon.png"


# ##################################################################
# event subscription worker
# background thread for subscribing to calendar event updates via SSE
# reconnects automatically if the connection drops (e.g. agent-link restart)
class EventSSEWorker(QThread):
    event_update = Signal(str, dict)  # emits (event_type, event_data) for each event
    snapshot_complete = Signal()  # emits when initial snapshot is received
    reconnecting = Signal()  # emits before reconnecting so UI can clear stale state

    def __init__(self, days: int = 2):
        super().__init__()
        self.days = days
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        import requests
        import json
        import time
        from datetime import datetime, timedelta

        import sys
        sys.stdout.reconfigure(line_buffering=True)
        retry_delay = 5  # seconds between reconnect attempts

        while not self._stop:
            # Recalculate time range each attempt (day may have changed)
            now = datetime.now()
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=self.days)

            url = "https://localhost:8900/api/v1/events/subscribe"
            params = {
                "type": "calendar.event.*",
                "snapshot": "true",
                "time_min": start.isoformat() + "Z",
                "time_max": end.isoformat() + "Z",
            }

            try:
                response = requests.get(url, params=params, stream=True, verify=False, timeout=None)
                response.raise_for_status()

                snapshot_done = False
                for line in response.iter_lines(decode_unicode=True):
                    if self._stop:
                        return

                    if not line or line.startswith(":"):
                        continue

                    if line.startswith("data: "):
                        data_json = line[6:]  # Remove "data: " prefix
                        try:
                            event_data = json.loads(data_json)
                            event_type = event_data.get("type", "")
                            payload = event_data.get("payload", {})

                            self.event_update.emit(event_type, payload)

                            # Emit snapshot_complete on first non-snapshot event
                            if not snapshot_done and event_type != "calendar.event.snapshot":
                                snapshot_done = True
                                self.snapshot_complete.emit()
                        except json.JSONDecodeError as e:
                            print(f"Failed to parse SSE data: {e}")
                            continue

            except Exception as e:
                if self._stop:
                    return
                print(f"SSE connection error: {e}, reconnecting in {retry_delay}s...")

            if self._stop:
                return

            # Signal reconnection so UI can clear stale events before new snapshot arrives
            self.reconnecting.emit()

            # Wait before retrying, checking _stop every 100ms
            for _ in range(retry_delay * 10):
                if self._stop:
                    return
                time.sleep(0.1)


@dataclass
class DisplayConfig:
    # configuration for the calendar display
    days: int = 2
    refresh_interval_ms: int = 60000
    countdown_interval_ms: int = 1000
    card_height: int = 160
    card_margin: int = 12
    column_padding: int = 20


# color palette - material design 3 inspired with elevated surfaces
COLORS = {
    "background": QColor(243, 243, 247),
    "column_bg": QColor(255, 255, 255),
    "column_shadow": QColor(0, 0, 0, 25),
    "header_text": QColor(30, 30, 40),
    "subheader_text": QColor(100, 100, 110),
    "countdown_text": QColor(50, 50, 60),
    "countdown_accent": QColor(66, 133, 244),
    "card_colors": [
        QColor(66, 133, 244),    # google blue
        QColor(52, 168, 83),     # google green
        QColor(142, 86, 232),    # vibrant purple
        QColor(234, 134, 64),    # warm orange
        QColor(0, 150, 170),     # teal
        QColor(219, 68, 85),     # coral red
    ],
    "card_text": QColor(255, 255, 255),
    "card_text_muted": QColor(255, 255, 255, 200),
}


# ##################################################################
# format duration
# converts minutes to a human readable duration string
def format_duration(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    if mins == 0:
        return f"{hours}h"
    return f"{hours}h {mins}m"


# ##################################################################
# format countdown
# converts seconds to a countdown display showing only the largest unit
def format_countdown(seconds: int) -> tuple[str, str]:
    if seconds <= 0:
        return "Now", ""
    if seconds >= 86400:
        days = seconds // 86400
        return str(days), "day" if days == 1 else "days"
    if seconds >= 3600:
        hours = seconds // 3600
        return str(hours), "hour" if hours == 1 else "hours"
    if seconds >= 60:
        mins = seconds // 60
        return str(mins), "minute" if mins == 1 else "minutes"
    return str(seconds), "seconds"


# ##################################################################
# wrap text
# wraps text to fit within a given width returning up to max_lines
def wrap_text(text: str, font: QFont, max_width: int, max_lines: int = 2) -> list[str]:
    metrics = QFontMetrics(font)
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = f"{current_line} {word}".strip() if current_line else word
        if metrics.horizontalAdvance(test_line) <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
                if len(lines) >= max_lines:
                    break
                current_line = word
            else:
                lines.append(word)
                if len(lines) >= max_lines:
                    break
    if current_line and len(lines) < max_lines:
        lines.append(current_line)
    if len(lines) == max_lines and current_line:
        last = lines[-1]
        if metrics.horizontalAdvance(last) > max_width or len(words) > sum(len(line.split()) for line in lines):
            while metrics.horizontalAdvance(last + "...") > max_width and len(last) > 3:
                last = last[:-1]
            lines[-1] = last.rstrip() + "..."
    return lines


# ##################################################################
# is urgent
# returns true if event starts within 5 minutes or is currently happening
def is_urgent(event: CalendarEvent, now: Optional[datetime] = None) -> bool:
    if now is None:
        now = datetime.now()
    five_min_from_now = now + timedelta(minutes=5)
    starts_soon = event.start_time <= five_min_from_now and event.start_time > now
    is_active = event.start_time <= now <= event.end_time
    return starts_soon or is_active


# ##################################################################
# has ended
# returns true if the event's end time is in the past
def has_ended(event: CalendarEvent, now: Optional[datetime] = None) -> bool:
    if now is None:
        now = datetime.now()
    return now > event.end_time


# flash animation timing
FLASH_INTERVAL_MS = 50  # update every 50ms for smooth animation
FLASH_CYCLE_MS = 2000   # complete flash cycle every 2 seconds

# meeting notification timing
NOTIFY_MINUTES_BEFORE = 5
MAX_NOTIFIED_KEYS = 200


# ##################################################################
# event card widget
# displays a single event as a material design card with elevation
class EventCard(QFrame):

    def __init__(self, calendar_event: CalendarEvent, color: QColor, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.calendar_event = calendar_event
        self.color = color
        self.meeting_link = extract_meeting_link(calendar_event)
        self.flash_phase = 0.0  # 0.0 to 1.0 representing position in flash cycle
        self.setFixedHeight(160)
        self.setMinimumWidth(200)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 50))
        self.setGraphicsEffect(shadow)

    # ##################################################################
    # update flash
    # advances the flash animation phase - called by parent window's shared timer
    def update_flash(self) -> None:
        if is_urgent(self.calendar_event):
            self.flash_phase += FLASH_INTERVAL_MS / FLASH_CYCLE_MS
            if self.flash_phase >= 1.0:
                self.flash_phase = 0.0
            self.update()
        elif self.flash_phase != 0.0:
            self.flash_phase = 0.0
            self.update()

    # ##################################################################
    # context menu event
    # shows right-click menu with join meeting option if meeting link exists
    def contextMenuEvent(self, context_event) -> None:
        if not self.meeting_link:
            return
        menu = QMenu(self)
        label = "Join Zoom Meeting" if self.meeting_link.link_type == "zoom" else "Join Google Meet"
        action = QAction(label, self)
        action.triggered.connect(lambda: launch_meeting(self.meeting_link))
        menu.addAction(action)
        menu.exec(context_event.globalPos())

    # ##################################################################
    # paint event
    # custom painting for the card content with material design aesthetics
    def paintEvent(self, paint_event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        rect = self.rect()
        self.draw_card_background(painter, rect)
        self.draw_time(painter, rect)
        self.draw_title(painter, rect)
        self.draw_duration(painter, rect)
        self.draw_meeting_badge(painter, rect)
        painter.end()

    # ##################################################################
    # draw card background
    # renders the card with a subtle gradient and rounded corners
    # applies flash effect when event is urgent using hue shift
    def draw_card_background(self, painter: QPainter, rect: QRectF) -> None:
        # calculate flash hue shift: cycle through entire spectrum
        if self.flash_phase > 0:
            # phase goes 0 to 1, shift hue through full 360 degrees
            hue_shift = int(self.flash_phase * 360)
            h, s, lightness, a = self.color.getHsl()
            new_hue = (h + hue_shift) % 360
            base_color = QColor.fromHsl(new_hue, s, lightness, a)
        else:
            base_color = self.color
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0, base_color.lighter(105))
        gradient.setColorAt(0.5, base_color)
        gradient.setColorAt(1, base_color.darker(105))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 12, 12)

    # ##################################################################
    # draw time
    # renders the start time prominently at the top left with 1.5x size
    def draw_time(self, painter: QPainter, rect: QRectF) -> None:
        font = QFont("Helvetica Neue", 30)
        font.setWeight(QFont.Weight.Bold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, -0.5)
        painter.setFont(font)
        painter.setPen(COLORS["card_text"])
        time_str = self.calendar_event.start_time.strftime("%-I:%M %p").lower()
        painter.drawText(
            QRectF(rect.left() + 20, rect.top() + 16, rect.width() - 40, 38),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            time_str
        )

    # ##################################################################
    # draw title
    # renders the event title with word wrap up to two lines at 1.5x size
    def draw_title(self, painter: QPainter, rect: QRectF) -> None:
        font = QFont("Helvetica Neue", 18)
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)
        painter.setPen(COLORS["card_text"])
        max_width = int(rect.width() - 40)
        lines = wrap_text(self.calendar_event.title, font, max_width, 2)
        y_offset = rect.top() + 62
        line_height = 24
        for line in lines:
            painter.drawText(
                QRectF(rect.left() + 20, y_offset, max_width, line_height),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                line
            )
            y_offset += line_height

    # ##################################################################
    # draw duration
    # renders the duration in the bottom right with muted text at 1.5x size
    def draw_duration(self, painter: QPainter, rect: QRectF) -> None:
        font = QFont("Helvetica Neue", 16)
        font.setWeight(QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(COLORS["card_text_muted"])
        duration_mins = int((self.calendar_event.end_time - self.calendar_event.start_time).total_seconds() / 60)
        duration_str = format_duration(duration_mins)
        painter.drawText(
            QRectF(rect.left() + 20, rect.bottom() - 38, rect.width() - 40, 26),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
            duration_str
        )

    # ##################################################################
    # draw meeting badge
    # renders a small meeting type indicator in the bottom left
    def draw_meeting_badge(self, painter: QPainter, rect: QRectF) -> None:
        if not self.meeting_link:
            return
        badge = "Z" if self.meeting_link.link_type == "zoom" else "M"
        font = QFont("Helvetica Neue", 11)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(COLORS["card_text_muted"])
        painter.drawText(
            QRectF(rect.left() + 20, rect.bottom() - 38, 20, 26),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
            badge
        )


# ##################################################################
# next event column widget
# displays countdown to the next upcoming event
class NextEventColumn(QFrame):

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.next_event: Optional[CalendarEvent] = None
        self.setObjectName("NextEventColumn")
        self.setFixedWidth(280)
        self.setStyleSheet("""
            #NextEventColumn {
                background-color: white;
                border-radius: 16px;
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(COLORS["column_shadow"])
        self.setGraphicsEffect(shadow)

    # ##################################################################
    # set next event
    # updates the displayed next event
    def set_next_event(self, event: Optional[CalendarEvent]) -> None:
        self.next_event = event
        self.update()

    # ##################################################################
    # paint event
    # custom painting for the countdown display
    def paintEvent(self, paint_event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        rect = self.rect()
        painter.fillRect(rect, COLORS["column_bg"])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(COLORS["column_bg"])
        painter.drawRoundedRect(rect, 16, 16)
        self.draw_header(painter, rect)
        if self.next_event:
            self.draw_countdown(painter, rect)
            self.draw_event_preview(painter, rect)
        else:
            self.draw_no_events(painter, rect)
        painter.end()

    # ##################################################################
    # draw header
    # renders the "Next Event" header
    def draw_header(self, painter: QPainter, rect: QRectF) -> None:
        font = QFont("Helvetica Neue", 24)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(COLORS["header_text"])
        painter.drawText(
            QRectF(rect.left() + 20, rect.top() + 20, rect.width() - 40, 32),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            "Next Event"
        )

    # ##################################################################
    # draw countdown
    # renders the big countdown timer
    def draw_countdown(self, painter: QPainter, rect: QRectF) -> None:
        now = datetime.now()
        seconds_until = int((self.next_event.start_time - now).total_seconds())
        number, label = format_countdown(seconds_until)
        font_number = QFont("Helvetica Neue", 72)
        font_number.setWeight(QFont.Weight.Bold)
        painter.setFont(font_number)
        painter.setPen(COLORS["countdown_accent"])
        painter.drawText(
            QRectF(rect.left() + 20, rect.top() + 70, rect.width() - 40, 80),
            Qt.AlignmentFlag.AlignCenter,
            number
        )
        if label:
            font_label = QFont("Helvetica Neue", 18)
            font_label.setWeight(QFont.Weight.Medium)
            painter.setFont(font_label)
            painter.setPen(COLORS["subheader_text"])
            painter.drawText(
                QRectF(rect.left() + 20, rect.top() + 150, rect.width() - 40, 28),
                Qt.AlignmentFlag.AlignCenter,
                label
            )

    # ##################################################################
    # draw event preview
    # renders a preview of the next event below the countdown
    def draw_event_preview(self, painter: QPainter, rect: QRectF) -> None:
        idx = int(hashlib.md5(self.next_event.event_id.encode()).hexdigest(), 16) % len(COLORS["card_colors"])
        color = COLORS["card_colors"][idx]
        preview_rect = QRectF(rect.left() + 20, rect.top() + 200, rect.width() - 40, 120)
        gradient = QLinearGradient(preview_rect.topLeft(), preview_rect.bottomRight())
        gradient.setColorAt(0, color.lighter(105))
        gradient.setColorAt(1, color.darker(105))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(preview_rect, 12, 12)
        font_time = QFont("Helvetica Neue", 20)
        font_time.setWeight(QFont.Weight.Bold)
        painter.setFont(font_time)
        painter.setPen(COLORS["card_text"])
        time_str = self.next_event.start_time.strftime("%-I:%M %p").lower()
        painter.drawText(
            QRectF(preview_rect.left() + 16, preview_rect.top() + 12, preview_rect.width() - 32, 28),
            Qt.AlignmentFlag.AlignLeft,
            time_str
        )
        font_title = QFont("Helvetica Neue", 14)
        font_title.setWeight(QFont.Weight.Medium)
        painter.setFont(font_title)
        max_width = int(preview_rect.width() - 32)
        lines = wrap_text(self.next_event.title, font_title, max_width, 2)
        y_offset = preview_rect.top() + 48
        for line in lines:
            painter.drawText(
                QRectF(preview_rect.left() + 16, y_offset, max_width, 20),
                Qt.AlignmentFlag.AlignLeft,
                line
            )
            y_offset += 22
        font_duration = QFont("Helvetica Neue", 12)
        painter.setFont(font_duration)
        painter.setPen(COLORS["card_text_muted"])
        duration_mins = int((self.next_event.end_time - self.next_event.start_time).total_seconds() / 60)
        painter.drawText(
            QRectF(preview_rect.left() + 16, preview_rect.bottom() - 28, preview_rect.width() - 32, 20),
            Qt.AlignmentFlag.AlignRight,
            format_duration(duration_mins)
        )

    # ##################################################################
    # draw no events
    # renders a message when there are no upcoming events
    def draw_no_events(self, painter: QPainter, rect: QRectF) -> None:
        font = QFont("Helvetica Neue", 16)
        painter.setFont(font)
        painter.setPen(COLORS["subheader_text"])
        painter.drawText(
            QRectF(rect.left() + 20, rect.top() + 100, rect.width() - 40, 60),
            Qt.AlignmentFlag.AlignCenter,
            "No upcoming events"
        )


# ##################################################################
# day column widget
# displays a column of events for a single day with material elevation
class DayColumn(QFrame):

    def __init__(self, title: str, subtitle: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.title = title
        self.setObjectName("DayColumn")
        self.setStyleSheet("""
            #DayColumn {
                background-color: white;
                border-radius: 16px;
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(COLORS["column_shadow"])
        self.setGraphicsEffect(shadow)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(6)
        header = QLabel(title)
        header.setStyleSheet(f"""
            QLabel {{
                color: {COLORS["header_text"].name()};
                font-size: 24px;
                font-weight: 700;
                font-family: 'Helvetica Neue';
                letter-spacing: -0.5px;
            }}
        """)
        layout.addWidget(header)
        if subtitle:
            subheader = QLabel(subtitle)
            subheader.setStyleSheet(f"""
                QLabel {{
                    color: {COLORS["subheader_text"].name()};
                    font-size: 13px;
                    font-weight: 500;
                    font-family: 'Helvetica Neue';
                    padding-bottom: 8px;
                }}
            """)
            layout.addWidget(subheader)
        else:
            spacer = QWidget()
            spacer.setFixedHeight(8)
            layout.addWidget(spacer)
        self.cards_layout = QVBoxLayout()
        self.cards_layout.setSpacing(14)
        layout.addLayout(self.cards_layout)
        layout.addStretch()

    # ##################################################################
    # set events
    # populates the column with event cards, each with a unique color per event_id
    def set_events(self, events: list[CalendarEvent]) -> None:
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for cal_event in events:
            idx = int(hashlib.md5(cal_event.event_id.encode()).hexdigest(), 16) % len(COLORS["card_colors"])
            color = COLORS["card_colors"][idx]
            card = EventCard(cal_event, color, self)
            self.cards_layout.addWidget(card)


# ##################################################################
# meeting notification dialog
# shows a popup with event info, live countdown, and join button
class MeetingNotificationDialog(QDialog):

    def __init__(self, calendar_event: CalendarEvent, link: MeetingLink, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.calendar_event = calendar_event
        self.link = link
        self.setWindowTitle("Meeting Starting Soon")
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint
        )
        self.setFixedSize(360, 200)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        self.title_label = QLabel(calendar_event.title)
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold; font-family: 'Helvetica Neue';")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        time_str = calendar_event.start_time.strftime("%-I:%M %p").lower()
        self.time_label = QLabel(f"Starts at {time_str}")
        self.time_label.setStyleSheet("font-size: 14px; color: #666; font-family: 'Helvetica Neue';")
        layout.addWidget(self.time_label)
        self.countdown_label = QLabel()
        self.countdown_label.setStyleSheet(
            "font-size: 24px; font-weight: bold; color: #4285f4; font-family: 'Helvetica Neue';"
        )
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.countdown_label)
        button_layout = QHBoxLayout()
        join_label = "Join Zoom" if link.link_type == "zoom" else "Join Meet"
        self.join_button = QPushButton(join_label)
        self.join_button.setStyleSheet(
            "QPushButton { background-color: #4285f4; color: white; border: none; border-radius: 6px;"
            " padding: 8px 20px; font-size: 14px; font-weight: bold; }"
            " QPushButton:hover { background-color: #3367d6; }"
        )
        self.join_button.clicked.connect(self.join_meeting)
        button_layout.addWidget(self.join_button)
        self.dismiss_button = QPushButton("Dismiss")
        self.dismiss_button.setStyleSheet(
            "QPushButton { background-color: #e0e0e0; color: #333; border: none; border-radius: 6px;"
            " padding: 8px 20px; font-size: 14px; }"
            " QPushButton:hover { background-color: #bdbdbd; }"
        )
        self.dismiss_button.clicked.connect(self.close)
        button_layout.addWidget(self.dismiss_button)
        layout.addLayout(button_layout)
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown_label)
        self.countdown_timer.start(1000)
        self.update_countdown_label()

    # ##################################################################
    # update countdown label
    # refreshes the mm:ss countdown display
    def update_countdown_label(self) -> None:
        now = datetime.now()
        seconds_until = int((self.calendar_event.start_time - now).total_seconds())
        if seconds_until <= 0:
            self.countdown_label.setText("Starting now!")
        else:
            mins = seconds_until // 60
            secs = seconds_until % 60
            self.countdown_label.setText(f"{mins}:{secs:02d}")

    # ##################################################################
    # join meeting
    # launches the meeting and closes the dialog
    def join_meeting(self) -> None:
        launch_meeting(self.link)
        self.close()


# ##################################################################
# main window
# the main application window with next event and two day columns
class MainWindow(QMainWindow):

    def __init__(self, config: DisplayConfig):
        super().__init__()
        self.config = config
        self.settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        self.all_events: dict[str, CalendarEvent] = {}  # keyed by event_id
        self.notified_event_keys: set[str] = self.load_notified_keys()
        self.active_notification: Optional[MeetingNotificationDialog] = None
        self.fetch_worker: Optional[EventSSEWorker] = None
        self.setWindowTitle("Calendar")
        self.setMinimumSize(600, 500)
        self.restore_geometry()
        self.setWindowOpacity(0.9)
        # make window stay on top of other windows
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet(f"background-color: {COLORS['background'].name()};")
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(24)
        self.next_event_column = NextEventColumn()
        main_layout.addWidget(self.next_event_column)
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        self.today_column = DayColumn("Today", today.strftime("%A, %B %-d"))
        self.tomorrow_column = DayColumn("Tomorrow", tomorrow.strftime("%A, %B %-d"))
        main_layout.addWidget(self.today_column, 1)
        main_layout.addWidget(self.tomorrow_column, 1)
        # Background polling timer
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_events)
        self.refresh_timer.start(config.refresh_interval_ms)
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.start(config.countdown_interval_ms)
        # single shared flash timer for all event cards
        self.flash_timer = QTimer(self)
        self.flash_timer.timeout.connect(self.update_flash_animations)
        self.flash_timer.start(FLASH_INTERVAL_MS)
        # one-shot timer: if display is still empty 45s after startup, force reconnect
        # guards against connecting to agent-link before its initial poll completes
        self.startup_check_timer = QTimer(self)
        self.startup_check_timer.setSingleShot(True)
        self.startup_check_timer.timeout.connect(self.check_startup_events)
        self.startup_check_timer.start(45000)

        # Initial fetch
        self.refresh_events()

    # ##################################################################
    # restore geometry
    # restores window size and position from saved settings
    def restore_geometry(self) -> None:
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(1100, 700)

    # ##################################################################
    # save geometry
    # persists window size and position to settings
    def save_geometry_settings(self) -> None:
        self.settings.setValue("geometry", self.saveGeometry())

    # ##################################################################
    # close event
    # saves window geometry when closing
    def closeEvent(self, close_event) -> None:
        self.save_geometry_settings()
        close_event.accept()

    # ##################################################################
    # move event
    # saves window geometry when moved
    def moveEvent(self, move_event) -> None:
        super().moveEvent(move_event)
        self.save_geometry_settings()

    # ##################################################################
    # resize event
    # saves window geometry when resized
    def resizeEvent(self, resize_event) -> None:
        super().resizeEvent(resize_event)
        self.save_geometry_settings()

    # ##################################################################
    # get next event
    # finds the next upcoming event from now
    def get_next_event(self) -> Optional[CalendarEvent]:
        now = datetime.now()
        all_events_list = list(self.all_events.values())
        future_events = [e for e in all_events_list if e.start_time > now]
        return future_events[0] if future_events else None

    # ##################################################################
    # load notified keys
    # restores previously notified event keys from QSettings
    def load_notified_keys(self) -> set[str]:
        keys = self.settings.value("notified_event_keys", [])
        if isinstance(keys, list):
            return set(str(k) for k in keys if k)
        return set()

    # ##################################################################
    # save notified keys
    # persists notified event keys to QSettings with size limit
    def save_notified_keys(self) -> None:
        keys = sorted(self.notified_event_keys)
        if len(keys) > MAX_NOTIFIED_KEYS:
            keys = keys[-MAX_NOTIFIED_KEYS:]
            self.notified_event_keys = set(keys)
        self.settings.setValue("notified_event_keys", keys)

    # ##################################################################
    # check meeting notifications
    # checks for upcoming meetings that need notification popups
    def check_meeting_notifications(self) -> None:
        now = datetime.now()
        for event in self.all_events.values():
            link = extract_meeting_link(event)
            if not link:
                continue
            minutes_until = (event.start_time - now).total_seconds() / 60
            if not (0 <= minutes_until <= NOTIFY_MINUTES_BEFORE):
                continue
            key = notification_key(event)
            if key in self.notified_event_keys:
                continue
            self.notified_event_keys.add(key)
            self.save_notified_keys()
            self.show_meeting_notification(event, link)

    # ##################################################################
    # show meeting notification
    # displays a meeting notification dialog with live countdown
    def show_meeting_notification(self, event: CalendarEvent, link: MeetingLink) -> None:
        if self.active_notification:
            self.active_notification.close()
        dialog = MeetingNotificationDialog(event, link)
        self.active_notification = dialog
        dialog.show()

    # ##################################################################
    # update countdown
    # refreshes the countdown display every second and checks for meeting notifications
    def update_countdown(self) -> None:
        next_event = self.get_next_event()
        self.next_event_column.set_next_event(next_event)
        self.check_meeting_notifications()

    # ##################################################################
    # update flash animations
    # updates flash state for all event cards using a single shared timer
    def update_flash_animations(self) -> None:
        for column in (self.today_column, self.tomorrow_column):
            for i in range(column.cards_layout.count()):
                item = column.cards_layout.itemAt(i)
                if item and item.widget():
                    card = item.widget()
                    if isinstance(card, EventCard):
                        card.update_flash()

    # ##################################################################
    # refresh events
    # subscribes to SSE stream for calendar events
    def refresh_events(self) -> None:
        # Skip if already subscribed
        if self.fetch_worker is not None and self.fetch_worker.isRunning():
            return

        # Start SSE subscription
        self.fetch_worker = EventSSEWorker(self.config.days)
        self.fetch_worker.event_update.connect(self.on_event_update)
        self.fetch_worker.snapshot_complete.connect(self.on_snapshot_complete)
        self.fetch_worker.reconnecting.connect(self.on_reconnecting)
        self.fetch_worker.start()

    # check startup events
    # fires 45s after startup - if all_events is empty, the SSE connected before
    # agent-link's initial poll completed; force a reconnect to get a fresh snapshot
    def check_startup_events(self) -> None:
        if not self.all_events:
            print("Startup check: no events received, forcing SSE reconnect", flush=True)
            if self.fetch_worker is not None:
                self.fetch_worker.stop()
                self.fetch_worker.wait(2000)
            self.fetch_worker = None
            self.refresh_events()

    # on event update
    # called when an event is received from SSE stream
    def on_event_update(self, event_type: str, event_data: dict) -> None:
        from calendar_access import parse_event_from_sse

        if event_type == "calendar.event.deleted":
            event_id = event_data.get("event_id", "")
            self.all_events.pop(event_id, None)
            self.update_display()
            return

        # Parse and store the event (handles snapshot + created + updated)
        event = parse_event_from_sse(event_data)
        if event is None:
            return

        self.all_events[event.event_id] = event
        self.update_display()

    # on snapshot complete
    # called when initial snapshot has been received
    def on_snapshot_complete(self) -> None:
        print(f"Snapshot complete: {len(self.all_events)} events loaded", flush=True)
        self.update_display()

    # on reconnecting
    # called when SSE connection dropped and worker is about to reconnect
    def on_reconnecting(self) -> None:
        self.all_events.clear()
        self.update_display()

    # update display
    # updates the UI with current events
    def update_display(self) -> None:
        now = datetime.now()
        today = now.date()
        tomorrow = today + timedelta(days=1)
        # filter out events that have already ended
        all_events_list = list(self.all_events.values())
        active_events = [e for e in all_events_list if not has_ended(e, now)]
        today_events = [e for e in active_events if e.start_time.date() == today]
        tomorrow_events = [e for e in active_events if e.start_time.date() == tomorrow]
        self.today_column.set_events(today_events)
        self.tomorrow_column.set_events(tomorrow_events)
        self.update_countdown()


# ##################################################################
# run application
# creates and runs the qt application with the calendar display
def run_application(days: int = 2) -> int:
    import sys
    import setproctitle
    setproctitle.setproctitle("calendar-display")
    # set macos dock/menu name via pyobjc
    try:
        from Foundation import NSBundle
        bundle = NSBundle.mainBundle()
        info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
        info["CFBundleName"] = "Calendar Display"
    except ImportError:
        pass  # pyobjc not available
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Calendar Display")
    app.setApplicationDisplayName("Calendar Display")
    app.setStyle("Fusion")
    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))
    config = DisplayConfig(days=days)
    window = MainWindow(config)
    if ICON_PATH.exists():
        window.setWindowIcon(QIcon(str(ICON_PATH)))
    window.show()
    return app.exec()
