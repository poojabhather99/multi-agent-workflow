from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .agents import Critic, Researcher, rule_planner
from .contracts import ContractError, parse_plan
from .trace import Trace


@dataclass
class Outcome:
    answer: float | None
    attempts: int
    ok: bool
    failures: list[str]
    trace: Trace


def run(question: str, planner: Callable[[str], list[dict]] = rule_planner,
        researcher: Researcher | None = None, max_attempts: int = 3) -> Outcome:
    researcher = researcher or Researcher()
    critic = Critic()
    trace = Trace()
    failures: list[str] = []
    for attempt in range(max_attempts):
        trace.log("orchestrator", "attempt", n=attempt)
        try:
            plan = parse_plan(question, planner(question))
        except (ContractError, ValueError) as e:
            failures.append(f"planner: {e}")
            trace.log("planner", "rejected", error=str(e))
            continue
        trace.log("planner", "plan", steps=[(s.tool, s.arg, s.store_as) for s in plan.steps])
        result = researcher.run(plan, trace, attempt)
        verdict = critic.review(result, trace)
        trace.log("critic", "verdict", ok=verdict.ok, reason=verdict.reason)
        if verdict.ok:
            return Outcome(result.answer, attempt + 1, True, failures, trace)
        failures.append(f"critic: {verdict.reason}")
    return Outcome(None, max_attempts, False, failures, trace)
