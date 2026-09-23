from __future__ import annotations

import os

import pytest

from src.profile_store import ProfileStore


def _update(store: ProfileStore, request_id: str, tag: str) -> None:
    store.update(
        subject_id="person_a",
        request_id=request_id,
        behavior_description=f"行为 {tag}",
        tags=[tag],
        mechanisms=[f"{tag}_mechanism"],
        confidence=0.5,
        universality_rating="中",
    )


def test_permissions_delete_and_forget(tmp_path) -> None:
    path = tmp_path / "private" / "profiles.json"
    store = ProfileStore(path)
    _update(store, "r1", "a")
    _update(store, "r2", "a")
    assert path.exists()
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600
        assert path.parent.stat().st_mode & 0o777 == 0o700
    assert store.forget_entry("person_a", "r1") is True
    profile = store.get("person_a")
    assert profile is not None
    assert len(profile["behavior_history"]) == 1
    assert store.delete("person_a") is True
    assert store.get("person_a") is None


def test_summary_is_recomputed_after_new_behavior(tmp_path) -> None:
    store = ProfileStore(tmp_path / "profiles.json")
    for index in range(3):
        _update(store, f"old-{index}", "old")
    old_profile = store.get("person_a")
    assert old_profile is not None and "old" in old_profile["pattern_summary"]
    for index in range(5):
        _update(store, f"new-{index}", "new")
    new_profile = store.get("person_a")
    assert new_profile is not None
    assert "new" in new_profile["pattern_summary"]
    assert "old" not in new_profile["pattern_summary"]


def test_invalid_history_limit_is_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="max_history"):
        ProfileStore(tmp_path / "profiles.json", max_history=0)


def test_malformed_legacy_history_entries_are_ignored(tmp_path) -> None:
    path = tmp_path / "profiles.json"
    path.write_text(
        '{"profiles":{"person_a":{"behavior_history":["bad",{"request_id":"ok"}]}}}',
        encoding="utf-8",
    )
    profile = ProfileStore(path).get("person_a")
    assert profile is not None
    assert profile["behavior_history"] == [{"request_id": "ok"}]
