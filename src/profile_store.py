"""经用户显式选择后使用的本地画像存储。"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
import threading
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional


class ProfileStoreError(RuntimeError):
    pass


def default_data_dir() -> Path:
    override = os.environ.get("BEHAVIOR_PSYCHOLOGY_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return root / "behavior-psychology"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "behavior-psychology"
    root = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    return root / "behavior-psychology"


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def generate_pattern_summary(profile: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    """基于最近五条有效记录生成可撤销、会持续刷新的摘要。"""

    history = profile.get("behavior_history", [])
    if not history:
        return "", [], []
    recent_history = history[-5:]
    tag_counter: Counter[str] = Counter()
    mechanism_counter: Counter[str] = Counter()
    for entry in recent_history:
        tag_counter.update(entry.get("tags", []))
        mechanism_counter.update(entry.get("mechanisms", []))
    recurring_tags = [name for name, count in tag_counter.items() if count >= 2]
    recurring_mechanisms = [name for name, count in mechanism_counter.items() if count >= 2]
    repeated = recurring_tags + recurring_mechanisms
    if len(repeated) < 2:
        return "近期记录尚不足以形成稳定模式；这些条目仅代表用户提供的观察。", [], []
    parts: list[str] = []
    if recurring_tags:
        parts.append(f"近期记录中重复出现的行为标签包括 {'、'.join(recurring_tags)}")
    if recurring_mechanisms:
        parts.append(f"重复出现的假设机制包括 {'、'.join(recurring_mechanisms)}")
    return (
        "；".join(parts) + "。这是对有限、主观记录的汇总，不代表稳定人格或真实动机。",
        recurring_tags,
        recurring_mechanisms,
    )


def _normalise_profile(subject_id: str, profile: dict[str, Any]) -> dict[str, Any]:
    now = _utc_now()
    if "behavior_history" not in profile:
        old_history = profile.get("history", [])
        profile = {
            "subject_id": subject_id,
            "alias": profile.get("alias", ""),
            "created_at": profile.get("created_at", profile.get("first_analyzed", now)),
            "updated_at": profile.get("updated_at", profile.get("last_analyzed", now)),
            "behavior_history": old_history if isinstance(old_history, list) else [],
            "pattern_summary": "",
        }
    profile.setdefault("subject_id", subject_id)
    profile.setdefault("alias", "")
    profile.setdefault("created_at", now)
    profile.setdefault("updated_at", now)
    profile.setdefault("behavior_history", [])
    profile.setdefault("pattern_summary", "")
    profile.setdefault("recurring_tags", [])
    profile.setdefault("recurring_mechanisms", [])
    history = profile.get("behavior_history")
    profile["behavior_history"] = (
        [entry for entry in history if isinstance(entry, dict)] if isinstance(history, list) else []
    )
    return profile


class ProfileStore:
    """单机本地画像库；通过文件锁和原子替换避免并发覆盖。"""

    _thread_lock = threading.RLock()

    def __init__(self, path: Optional[Path] = None, max_history: int = 50) -> None:
        if max_history < 1:
            raise ValueError("max_history 必须大于等于 1。")
        self.path = path or (default_data_dir() / "user_profiles.json")
        self.lock_path = self.path.with_suffix(".lock")
        self.max_history = max_history

    def _ensure_parent(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.path.parent, 0o700)
        except OSError:
            pass

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self._ensure_parent()
        with self._thread_lock:
            with self.lock_path.open("a+", encoding="utf-8") as lock_handle:
                try:
                    os.chmod(self.lock_path, 0o600)
                except OSError:
                    pass
                if os.name == "nt":
                    import msvcrt

                    lock_handle.seek(0, os.SEEK_END)
                    if lock_handle.tell() == 0:
                        lock_handle.write("\0")
                        lock_handle.flush()
                    lock_handle.seek(0)
                    locking = vars(msvcrt)["locking"]
                    locking(lock_handle.fileno(), vars(msvcrt)["LK_LOCK"], 1)
                else:
                    import fcntl

                    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    if os.name == "nt":
                        import msvcrt

                        lock_handle.seek(0)
                        locking = vars(msvcrt)["locking"]
                        locking(lock_handle.fileno(), vars(msvcrt)["LK_UNLCK"], 1)
                    else:
                        import fcntl

                        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    def _load_unlocked(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": "2.1", "profiles": {}}
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise ProfileStoreError("画像文件无法读取或格式损坏。") from exc
        if not isinstance(data, dict) or not isinstance(data.get("profiles", {}), dict):
            raise ProfileStoreError("画像文件结构无效。")
        data.setdefault("version", "2.1")
        data.setdefault("profiles", {})
        return data

    def _save_unlocked(self, data: dict[str, Any]) -> None:
        self._ensure_parent()
        temp_name: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=".user_profiles.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_name = handle.name
                os.chmod(temp_name, 0o600)
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
            os.chmod(self.path, 0o600)
        except OSError as exc:
            if temp_name:
                try:
                    Path(temp_name).unlink(missing_ok=True)
                except OSError:
                    pass
            raise ProfileStoreError("画像文件保存失败。") from exc

    def get(self, subject_id: str) -> Optional[dict[str, Any]]:
        with self._locked():
            data = self._load_unlocked()
            profile = data["profiles"].get(subject_id)
            if not isinstance(profile, dict):
                return None
            return _normalise_profile(subject_id, profile)

    def update(
        self,
        *,
        subject_id: str,
        request_id: str,
        behavior_description: str,
        tags: list[str],
        mechanisms: list[str],
        confidence: float,
        universality_rating: str,
    ) -> tuple[dict[str, Any], bool]:
        with self._locked():
            data = self._load_unlocked()
            profiles = data["profiles"]
            existing = profiles.get(subject_id)
            profile = _normalise_profile(subject_id, existing if isinstance(existing, dict) else {})
            history = profile["behavior_history"]
            if any(entry.get("request_id") == request_id for entry in history):
                return profile, False
            now = _utc_now()
            history.append(
                {
                    "request_id": request_id,
                    "timestamp": now,
                    "behavior_description": behavior_description,
                    "tags": tags,
                    "mechanisms": mechanisms,
                    "confidence": confidence,
                    "universality_rating": universality_rating,
                }
            )
            profile["behavior_history"] = history[-self.max_history :]
            profile["updated_at"] = now
            if not profile.get("created_at"):
                profile["created_at"] = now
            if len(profile["behavior_history"]) >= 3:
                summary, recurring_tags, recurring_mechanisms = generate_pattern_summary(profile)
                profile["pattern_summary"] = summary
                profile["recurring_tags"] = recurring_tags
                profile["recurring_mechanisms"] = recurring_mechanisms
            else:
                profile["pattern_summary"] = ""
                profile["recurring_tags"] = []
                profile["recurring_mechanisms"] = []
            profiles[subject_id] = profile
            self._save_unlocked(data)
            return profile, True

    def delete(self, subject_id: str) -> bool:
        with self._locked():
            data = self._load_unlocked()
            existed = data["profiles"].pop(subject_id, None) is not None
            if existed:
                self._save_unlocked(data)
            return existed

    def forget_entry(self, subject_id: str, request_id: str) -> bool:
        with self._locked():
            data = self._load_unlocked()
            existing = data["profiles"].get(subject_id)
            if not isinstance(existing, dict):
                return False
            profile = _normalise_profile(subject_id, existing)
            old_history = profile["behavior_history"]
            new_history = [entry for entry in old_history if entry.get("request_id") != request_id]
            if len(new_history) == len(old_history):
                return False
            profile["behavior_history"] = new_history
            summary, tags, mechanisms = generate_pattern_summary(profile)
            profile["pattern_summary"] = summary if len(new_history) >= 3 else ""
            profile["recurring_tags"] = tags if len(new_history) >= 3 else []
            profile["recurring_mechanisms"] = mechanisms if len(new_history) >= 3 else []
            profile["updated_at"] = _utc_now()
            data["profiles"][subject_id] = profile
            self._save_unlocked(data)
            return True
