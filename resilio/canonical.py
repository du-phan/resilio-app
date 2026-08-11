"""Dependency-neutral canonical hashing for persisted authority contracts."""

import hashlib
import json
from typing import Any

from pydantic import BaseModel


def canonical_data_sha256(value: BaseModel | dict[str, Any] | list[Any]) -> str:
    """Hash typed data with stable JSON ordering and representation."""
    payload = (
        value.model_dump(mode="json", by_alias=True)
        if isinstance(value, BaseModel)
        else value
    )
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()
