"""Tiny JSON-file store for incident history/analytics.

Hindsight remains the source of truth for *memory*; this store only powers the
history, timeline and stats views (Hindsight recall returns facts, not a list of incidents).
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "data" / "incidents.json"
_LOCK = threading.Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_incident_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S%f")[:-3]
    return f"INC-{timestamp}-{uuid.uuid4().hex[:8]}"


def _load() -> list[dict]:
    if not _PATH.exists():
        return []
    try:
        items = json.loads(_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Incident history contains invalid JSON: {_PATH}") from exc
    if not isinstance(items, list):
        raise ValueError(f"Incident history must contain a JSON array: {_PATH}")
    return items


def _save(items: list[dict]) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(items, indent=2), encoding="utf-8")


def list_incidents() -> list[dict]:
    with _LOCK:
        return sorted(_load(), key=lambda i: i.get("created_at", ""), reverse=True)


def get_incident(incident_id: str) -> dict | None:
    with _LOCK:
        return next((i for i in _load() if i["id"] == incident_id), None)


def upsert(incident: dict) -> None:
    with _LOCK:
        items = _load()
        for idx, existing in enumerate(items):
            if existing["id"] == incident["id"]:
                items[idx] = {**existing, **incident}
                break
        else:
            items.append(incident)
        _save(items)


def mark_memory_revoked(incident_id: str) -> None:
    """Mark the incident's Hindsight memory as revoked in local analytics."""
    with _LOCK:
        items = _load()
        for item in items:
            if item.get("id") == incident_id:
                item["memory_revoked"] = True
                break
        _save(items)


def resolved_of_category(category: str) -> list[dict]:
    return [i for i in list_incidents() if i.get("status") == "resolved" and i.get("category") == category]
