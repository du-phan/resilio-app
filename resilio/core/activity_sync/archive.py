"""Canonical activity archive repository."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

import yaml

from resilio.schemas.activity import CanonicalActivity


class ActivityArchiveError(RuntimeError):
    pass


class ActivityArchive:
    def __init__(self, root: Path):
        self.root = root

    def load_all(self) -> list[CanonicalActivity]:
        records: list[CanonicalActivity] = []
        seen_local: set[str] = set()
        seen_external: set[str] = set()
        for path in sorted(self.root.rglob("*.yaml")):
            try:
                raw = yaml.safe_load(path.read_text())
                activity = CanonicalActivity.model_validate(raw)
            except Exception as exc:
                raise ActivityArchiveError(
                    f"Active archive contains a non-v2 or invalid record: {path}"
                ) from exc
            if activity.local_activity_id in seen_local:
                raise ActivityArchiveError(
                    f"Duplicate local activity ID: {activity.local_activity_id}"
                )
            seen_local.add(activity.local_activity_id)
            external_id = activity.origin.intervals_icu_activity_id
            if external_id:
                if external_id in seen_external:
                    raise ActivityArchiveError(
                        f"Duplicate external activity reference: {external_id}"
                    )
                seen_external.add(external_id)
            expected = self.path_for(activity)
            if path != expected:
                raise ActivityArchiveError(
                    f"Activity path does not match stable ID/date: {path} != {expected}"
                )
            records.append(activity)
        return records

    def path_for(self, activity: CanonicalActivity) -> Path:
        return (
            self.root
            / activity.date.strftime("%Y-%m")
            / f"{activity.local_activity_id}.yaml"
        )

    def find_path(self, local_activity_id: str) -> Optional[Path]:
        matches = list(self.root.glob(f"*/{local_activity_id}.yaml"))
        if len(matches) > 1:
            raise ActivityArchiveError(
                f"Duplicate files for local activity ID: {local_activity_id}"
            )
        return matches[0] if matches else None

    def write(self, activity: CanonicalActivity) -> Path:
        target = self.path_for(activity)
        old_path = self.find_path(activity.local_activity_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = activity.model_dump(mode="json", by_alias=True)
        content = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
        fd, temporary = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
            os.replace(temporary, target)
        except Exception:
            Path(temporary).unlink(missing_ok=True)
            raise
        if old_path is not None and old_path != target:
            old_path.unlink()
        return target
