from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import main


def test_zero_minute_resolution_is_included_in_estimate_and_stats(monkeypatch):
    history = [
        {
            "id": "INC-1",
            "title": "Zero-minute incident",
            "category": "Credential Attack",
            "severity": "High",
            "status": "resolved",
            "resolution_minutes": 0,
            "created_at": "2026-01-01T00:00:00+00:00",
            "resolved_at": "2026-01-01T00:00:00+00:00",
            "memories_recalled": 0,
            "analysis_ms": 1,
        }
    ]
    monkeypatch.setattr(main.store, "resolved_of_category", lambda _: history)
    monkeypatch.setattr(main.store, "new_incident_id", lambda: "INC-2")
    monkeypatch.setattr(main.store, "list_incidents", lambda: history)
    monkeypatch.setattr(main.store, "upsert", lambda _: None)
    monkeypatch.setattr(
        main,
        "get_incident_agent",
        lambda: SimpleNamespace(
            analyze=lambda *_args, **_kwargs: SimpleNamespace(
                response="Response",
                memories_used=[],
                memory_details=[],
                hindsight_available=True,
            )
        ),
    )

    result = main.analyze_incident(
        main.IncidentRequest(
            title="Credential stuffing",
            description="A confirmed successful login followed by immediate containment.",
        )
    )
    stats = main.stats()

    assert result.estimated_minutes == 0
    assert stats["avg_resolution_minutes"] == 0
    assert stats["avg_resolution_by_category"]["Credential Attack"] == 0


def test_lifespan_ensures_hindsight_bank(monkeypatch):
    calls = []
    monkeypatch.setattr(
        main,
        "get_hindsight_service",
        lambda: SimpleNamespace(ensure_bank=lambda: calls.append("ensured")),
    )

    with TestClient(main.app):
        assert calls == ["ensured"]
