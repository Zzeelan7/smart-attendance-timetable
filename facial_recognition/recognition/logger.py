"""
recognition/logger.py
Logs recognition events to a JSON file and provides query utilities.
"""

import json
import os
import logging
from datetime import datetime
from collections import defaultdict

import config

logger = logging.getLogger(__name__)


class RecognitionLogger:
    """Appends face-recognition events to a rolling JSON log."""

    def __init__(self):
        self._path = config.LOG_FILE
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        if not os.path.exists(self._path):
            self._write([])

    # ─── Write ────────────────────────────────────────────────────────────

    def log_event(self, name: str, confidence: float, is_known: bool,
                  camera_source: str = ""):
        """Append a single recognition event."""
        events = self._read()
        events.append({
            "timestamp":    datetime.now().isoformat(),
            "name":         name,
            "confidence":   confidence,
            "is_known":     is_known,
            "camera":       camera_source,
        })
        # Keep last 5000 events
        if len(events) > 5000:
            events = events[-5000:]
        self._write(events)

    # ─── Read ─────────────────────────────────────────────────────────────

    def get_all(self) -> list[dict]:
        return self._read()

    def get_recent(self, n: int = 50) -> list[dict]:
        return self._read()[-n:]

    def get_stats(self) -> dict:
        """Summary statistics for the dashboard."""
        events = self._read()
        today  = datetime.now().date().isoformat()
        today_events = [e for e in events if e["timestamp"][:10] == today]

        counts: dict[str, int] = defaultdict(int)
        for e in events:
            if e["is_known"]:
                counts[e["name"]] += 1

        return {
            "total_events":    len(events),
            "today_events":    len(today_events),
            "known_count":     sum(1 for e in events if e["is_known"]),
            "unknown_count":   sum(1 for e in events if not e["is_known"]),
            "top_detections":  sorted(counts.items(), key=lambda x: -x[1])[:5],
        }

    # ─── Internal ─────────────────────────────────────────────────────────

    def _read(self) -> list[dict]:
        try:
            with open(self._path) as f:
                return json.load(f)
        except Exception:
            return []

    def _write(self, events: list[dict]):
        with open(self._path, "w") as f:
            json.dump(events, f, indent=2)
