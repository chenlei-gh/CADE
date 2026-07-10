"""
CADE Learning System
=====================
Lightweight feedback loop — records patterns, not embeddings.

Design principle:
  No embeddings, no vector DB. Just structured pattern recording.
  When the same fix is applied 3+ times, suggest upgrading to a Playbook.

Three channels:
  1. failure → knowledge/failure_patterns/   (compile/runtime errors)
  2. success → playbooks/                     (when pattern repeats 3+ times)
  3. discovery → knowledge/                   (CAADoc → CADE knowledge)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


# ─── Event ────────────────────────────────────────────────────────


@dataclass
class LearningEvent:
    """A single learning event"""
    type: str  # "compile_failure" | "fix_success" | "api_discovery" | "pattern_detected"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    source: str = ""      # e.g., "repair.py", "CAADoc/CATAssemblyInterfaces"
    description: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "timestamp": self.timestamp,
            "source": self.source,
            "description": self.description,
            "data": self.data,
        }


# ─── PatternRecord ────────────────────────────────────────────────


@dataclass
class PatternRecord:
    """A detected pattern that may become a Playbook"""
    id: str
    description: str
    occurrence_count: int = 1
    events: List[LearningEvent] = field(default_factory=list)
    suggested_playbook_id: str = ""

    def should_promote(self, threshold: int = 3) -> bool:
        return self.occurrence_count >= threshold


# ─── LearningRecorder ─────────────────────────────────────────────


class LearningRecorder:
    """
    Records learning events and detects patterns.

    Usage:
      recorder = LearningRecorder(skill_root)
      recorder.record(LearningEvent(type="compile_failure", ...))
    """

    def __init__(self, skill_root: Path = None):
        self.skill_root = Path(skill_root) if skill_root else Path(__file__).parent.parent
        self.failure_patterns_dir = self.skill_root / "knowledge" / "failure_patterns"
        self._events: List[LearningEvent] = []

    def record(self, event: LearningEvent) -> None:
        """Record a learning event"""
        self._events.append(event)

        if event.type == "compile_failure":
            self._record_failure(event)
        elif event.type == "fix_success":
            self._record_fix(event)
        elif event.type == "api_discovery":
            self._record_discovery(event)

    def record_event(self, event_type: str, description: str, **data) -> None:
        """Convenience: record an event by type and description"""
        event = LearningEvent(
            type=event_type,
            description=description,
            data=data,
        )
        self.record(event)

    def get_recent_events(self, limit: int = 10) -> List[Dict]:
        """Get most recent learning events"""
        return [e.to_dict() for e in self._events[-limit:]]

    # ─── Internal ──────────────────────────────────────────────

    def _record_failure(self, event: LearningEvent) -> None:
        """Record a compile/runtime failure for pattern detection"""
        # Check if this failure pattern already exists
        if "error_signature" in event.data:
            sig = event.data["error_signature"]
            fp_file = self.failure_patterns_dir / f"fp_{sig}.md"
            if not fp_file.exists():
                # Create a stub failure pattern
                self.failure_patterns_dir.mkdir(parents=True, exist_ok=True)
                fp_file.write_text(
                    f"# Failure Pattern: {sig}\n\n"
                    f"**First detected**: {event.timestamp}\n"
                    f"**Source**: {event.source}\n\n"
                    f"## Description\n\n{event.description}\n\n"
                    f"## Occurrences\n\n1. {event.timestamp}\n",
                    encoding="utf-8",
                )

    def _record_fix(self, event: LearningEvent) -> None:
        """Record a successful fix for pattern promotion detection"""
        pass  # Future: detect when same fix applied 3+ times → suggest Playbook

    def _record_discovery(self, event: LearningEvent) -> None:
        """Record new API knowledge discovered from CAADoc"""
        pass  # Future: suggest creating knowledge/ file


# ─── PatternDetector ──────────────────────────────────────────────


class PatternDetector:
    """
    Detects repeated patterns in learning events.

    When the same fix is applied 3+ times, it suggests
    creating a Playbook for that pattern.
    """

    PROMOTION_THRESHOLD = 3

    def __init__(self, recorder: LearningRecorder = None):
        self.recorder = recorder or LearningRecorder()
        self._patterns: Dict[str, PatternRecord] = {}

    def detect(self, events: List[LearningEvent] = None) -> List[PatternRecord]:
        """
        Analyze events and detect repeated patterns.

        Returns patterns that have occurred 3+ times.
        """
        if events is None:
            events = self.recorder._events

        for event in events:
            key = self._event_key(event)
            if key not in self._patterns:
                self._patterns[key] = PatternRecord(
                    id=key,
                    description=event.description,
                    occurrence_count=1,
                    events=[event],
                )
            else:
                self._patterns[key].occurrence_count += 1
                self._patterns[key].events.append(event)

        # Return patterns that should be promoted
        return [p for p in self._patterns.values() if p.should_promote(self.PROMOTION_THRESHOLD)]

    def _event_key(self, event: LearningEvent) -> str:
        """Generate a stable key for pattern grouping"""
        parts = [event.type]
        if "error_signature" in event.data:
            parts.append(event.data["error_signature"])
        elif event.description:
            parts.append(event.description[:50])
        return "_".join(parts).replace(" ", "_").lower()
