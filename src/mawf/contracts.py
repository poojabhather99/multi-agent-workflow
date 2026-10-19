"""Typed contracts between agents. Anything an LLM produces is validated into these."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

TOOLS = {"lookup", "calc"}


class ContractError(ValueError):
    pass


@dataclass(frozen=True)
class Step:
    id: str
    tool: str
    arg: str
    store_as: str


@dataclass(frozen=True)
class Plan:
    question: str
    steps: tuple[Step, ...]


@dataclass
class Result:
    answer: float | None
    evidence: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class Verdict:
    ok: bool
    reason: str = ""


def parse_plan(question: str, raw: Any) -> Plan:
    """Validate an untrusted list of step dicts into a Plan."""
    if not isinstance(raw, list) or not raw or len(raw) > 8:
        raise ContractError("plan must be a list of 1-8 steps")
    steps, names = [], set()
    for i, s in enumerate(raw):
        if not isinstance(s, dict):
            raise ContractError(f"step {i} is not an object")
        tool, arg, name = s.get("tool"), s.get("arg"), s.get("store_as")
        if tool not in TOOLS:
            raise ContractError(f"step {i}: unknown tool {tool!r}")
        if not isinstance(arg, str) or not arg:
            raise ContractError(f"step {i}: arg must be a non-empty string")
        if not isinstance(name, str) or not name.isidentifier() or name in names:
            raise ContractError(f"step {i}: store_as must be a unique identifier")
        names.add(name)
        steps.append(Step(f"s{i}", tool, arg, name))
    return Plan(question, tuple(steps))
