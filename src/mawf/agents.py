"""Planner, Researcher and Critic. The planner is pluggable; the others are deterministic."""

from __future__ import annotations

import json
import re
from typing import Callable

from . import tools
from .contracts import ContractError, Plan, Result, Verdict
from .trace import Trace


def rule_planner(question: str) -> list[dict]:
    """Offline baseline planner for the demo question family."""
    q = question.lower()
    item = "gadget" if "gadget" in q else "widget"
    m = re.search(r"(\d+)", q)
    if not m:
        raise ContractError("no quantity found")
    qty = m.group(1)
    steps = [
        {"tool": "lookup", "arg": f"price_{item}", "store_as": "price"},
        {"tool": "calc", "arg": f"price * {qty}", "store_as": "subtotal"},
    ]
    cur = "subtotal"  # each stage writes a new name: the contract is single-assignment
    if "bulk" in q or int(qty) >= 10:
        steps += [
            {"tool": "lookup", "arg": "discount_bulk", "store_as": "disc"},
            {"tool": "calc", "arg": f"{cur} * (1 - disc)", "store_as": "discounted"},
        ]
        cur = "discounted"
    if "shipping" in q:
        steps += [
            {"tool": "lookup", "arg": "shipping_flat", "store_as": "ship"},
            {"tool": "calc", "arg": f"{cur} + ship", "store_as": "shipped"},
        ]
        cur = "shipped"
    if "tax" in q:
        steps += [
            {"tool": "lookup", "arg": "tax_rate", "store_as": "rate"},
            {"tool": "calc", "arg": f"{cur} * (1 + rate)", "store_as": "total"},
        ]
    else:
        steps += [{"tool": "calc", "arg": cur, "store_as": "total"}]
    return steps


def llm_planner(complete: Callable[[str], str]) -> Callable[[str], list[dict]]:
    def plan(question: str) -> list[dict]:
        prompt = (
            "Plan steps as a JSON array of {tool, arg, store_as}. Tools: lookup(fact key) and "
            "calc(arithmetic over stored names). The last step must store_as 'total'. "
            f"Facts: {sorted(tools.FACTS)}. Question: {question}"
        )
        m = re.search(r"\[.*\]", complete(prompt), re.DOTALL)
        if not m:
            raise ContractError("no JSON array in planner output")
        return json.loads(m.group(0))

    return plan


class Researcher:
    def __init__(self, flaky: bool = False):
        self.flaky = flaky  # fault injection: corrupt the answer on the first attempt

    def run(self, plan: Plan, trace: Trace, attempt: int) -> Result:
        env: dict[str, float] = {}
        try:
            for s in plan.steps:
                val = tools.lookup(s.arg) if s.tool == "lookup" else tools.calc(s.arg, env)
                env[s.store_as] = val
                trace.log("researcher", "tool_call", step=s.id, tool=s.tool, arg=s.arg, value=val)
        except tools.ToolError as e:
            trace.log("researcher", "tool_error", error=str(e))
            return Result(None, env, str(e))
        if "total" not in env:
            return Result(None, env, "plan never produced 'total'")
        answer = env["total"]
        if self.flaky and attempt == 0:
            answer = round(answer * 1.1, 2)
            trace.log("researcher", "fault_injected", reported=answer)
        return Result(round(answer, 2), env)


class Critic:
    """Independent check: the reported answer must equal the last computed total in the trace."""

    def review(self, result: Result, trace: Trace) -> Verdict:
        if result.error:
            return Verdict(False, f"researcher error: {result.error}")
        computed = [e["value"] for e in trace.events if e["kind"] == "tool_call"]
        if not computed:
            return Verdict(False, "no tool calls in trace")
        if abs(round(computed[-1], 2) - (result.answer or 0.0)) > 0.005:
            return Verdict(False, f"answer {result.answer} != last computed {computed[-1]:.2f}")
        return Verdict(True)
