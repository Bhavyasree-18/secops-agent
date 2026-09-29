import pytest

from app.services import store
from app.services.store import new_incident_id


def test_incident_ids_are_unique_with_timestamp_prefix():
    first = new_incident_id()
    second = new_incident_id()

    assert first.startswith("INC-")
    assert second.startswith("INC-")
    assert first != second


def test_corrupt_history_is_reported_without_overwriting_it(tmp_path, monkeypatch):
    history_file = tmp_path / "incidents.json"
    original = "{invalid json"
    history_file.write_text(original, encoding="utf-8")
    monkeypatch.setattr(store, "_PATH", history_file)

    with pytest.raises(ValueError, match="invalid JSON"):
        store.upsert({"id": "INC-1"})

    assert history_file.read_text(encoding="utf-8") == original


def test_history_must_be_a_json_array(tmp_path, monkeypatch):
    history_file = tmp_path / "incidents.json"
    history_file.write_text('{"id": "INC-1"}', encoding="utf-8")
    monkeypatch.setattr(store, "_PATH", history_file)

    with pytest.raises(ValueError, match="JSON array"):
        store.list_incidents()
