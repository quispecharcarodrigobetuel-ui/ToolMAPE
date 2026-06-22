from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CollectorResult:
    source_id: str
    items: list[dict[str, Any]] = field(default_factory=list)
    method: str = "requests"
    errors: list[str] = field(default_factory=list)


class CollectorError(RuntimeError):
    pass
