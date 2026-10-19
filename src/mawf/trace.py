"""Append-only event trace so every run can be inspected or replayed."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Trace:
    events: list[dict[str, Any]] = field(default_factory=list)

    def log(self, agent: str, kind: str, **data: Any) -> None:
        self.events.append({"n": len(self.events), "agent": agent, "kind": kind, **data})

    def count(self, kind: str) -> int:
        return sum(e["kind"] == kind for e in self.events)

    def to_jsonl(self) -> str:
        return "\n".join(json.dumps(e) for e in self.events)
