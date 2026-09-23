from __future__ import annotations

import json

import pytest

from src.cli import _build_parser, main
from src.profile_store import ProfileStore


def _seed_profile(path) -> None:
    store = ProfileStore(path / "user_profiles.json")
    store.update(
        subject_id="person_a",
        request_id="request_a",
        behavior_description="一段已同意保存的观察",
        tags=["conversation_interruption"],
        mechanisms=["role_or_norm_expectation"],
        confidence=0.4,
        universality_rating="中",
    )


def test_parser_requires_subcommand() -> None:
    parser = _build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args([])
    assert exc.value.code == 2


def test_profile_export_forget_and_delete(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("BEHAVIOR_PSYCHOLOGY_DATA_DIR", str(tmp_path))
    _seed_profile(tmp_path)

    main(["export-profile", "--subject", "person_a"])
    exported = json.loads(capsys.readouterr().out)
    assert exported["subject_id"] == "person_a"

    main(
        [
            "forget-entry",
            "--subject",
            "person_a",
            "--request-id",
            "request_a",
            "--yes",
        ]
    )
    assert "已删除指定记录" in capsys.readouterr().out

    main(["delete-profile", "--subject", "person_a", "--yes"])
    assert "已删除画像" in capsys.readouterr().out


def test_delete_requires_confirmation(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("BEHAVIOR_PSYCHOLOGY_DATA_DIR", str(tmp_path))
    with pytest.raises(SystemExit) as exc:
        main(["delete-profile", "--subject", "person_a"])
    assert exc.value.code == 1
    assert "需要显式传入 --yes" in capsys.readouterr().err
