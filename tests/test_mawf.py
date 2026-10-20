import json

import pytest

from mawf import tools
from mawf.agents import Critic, Researcher, llm_planner, rule_planner
from mawf.contracts import ContractError, Result, parse_plan
from mawf.evaluate import TASKS, evaluate
from mawf.orchestrator import run
from mawf.trace import Trace


@pytest.mark.parametrize(("expr", "want"), [("2 + 3 * 4", 14.0), ("(1 + 2) / 4", 0.75), ("-3 + 5", 2.0)])
def test_calc_ok(expr, want):
    assert tools.calc(expr, {}) == want


def test_calc_uses_env():
    assert tools.calc("a * 2", {"a": 4}) == 8.0


@pytest.mark.parametrize(
    "expr",
    ["__import__('os').system('x')", "a.b", "2 ** 3", "1 / 0", "unknown + 1", "(", "x" * 300, "[1]"],
)
def test_calc_rejects_unsafe(expr):
    with pytest.raises(tools.ToolError):
        tools.calc(expr, {})


def test_lookup():
    assert tools.lookup("tax_rate") == 0.18
    with pytest.raises(tools.ToolError):
        tools.lookup("nope")


@pytest.mark.parametrize(
    "raw",
    [
        [],
        "x",
        [{"tool": "shell", "arg": "ls", "store_as": "a"}],
        [{"tool": "calc", "arg": "", "store_as": "a"}],
        [{"tool": "calc", "arg": "1", "store_as": "1bad"}],
        [{"tool": "calc", "arg": "1", "store_as": "a"}, {"tool": "calc", "arg": "2", "store_as": "a"}],
        ["not a dict"],
        [{"tool": "calc", "arg": "1", "store_as": f"v{i}"} for i in range(9)],
    ],
)
def test_plan_contract_rejects(raw):
    with pytest.raises(ContractError):
        parse_plan("q", raw)


def test_rule_planner_output_is_valid_for_all_tasks():
    for q, _ in TASKS:
        parse_plan(q, rule_planner(q))


def test_all_tasks_correct_without_faults():
    for q, expected in TASKS:
        o = run(q)
        assert o.ok and o.answer == pytest.approx(expected) and o.attempts == 1


def test_critic_catches_injected_fault_and_retry_fixes_it():
    o = run("Total for 4 widgets including shipping?", researcher=Researcher(flaky=True))
    assert o.ok and o.attempts == 2 and o.answer == 55.0
    assert o.trace.count("fault_injected") == 1
    assert any(f.startswith("critic:") for f in o.failures)


def test_critic_rejects_mismatch_and_errors():
    t = Trace()
    t.log("researcher", "tool_call", value=10.0)
    assert not Critic().review(Result(11.0), t).ok
    assert Critic().review(Result(10.0), t).ok
    assert not Critic().review(Result(None, error="boom"), t).ok
    assert not Critic().review(Result(1.0), Trace()).ok


def test_bad_llm_plan_is_rejected_not_executed():
    bad = llm_planner(lambda _p: '[{"tool":"shell","arg":"rm -rf /","store_as":"x"}]')
    o = run("Total for 4 widgets?", planner=bad, max_attempts=2)
    assert not o.ok and o.attempts == 2 and all(f.startswith("planner:") for f in o.failures)
    assert o.trace.count("tool_call") == 0


def test_llm_planner_accepts_fenced_json():
    good = llm_planner(lambda _p: "```json\n" + json.dumps(rule_planner("Total for 4 widgets?")) + "\n```")
    assert run("Total for 4 widgets?", planner=good).ok


def test_planner_that_never_stores_total_fails_cleanly():
    p = lambda _q: [{"tool": "lookup", "arg": "tax_rate", "store_as": "rate"}]  # noqa: E731
    o = run("anything", planner=p, max_attempts=2)
    assert not o.ok


def test_trace_is_jsonl():
    o = run("Total for 4 widgets?")
    lines = o.trace.to_jsonl().splitlines()
    assert all(json.loads(x)["n"] == i for i, x in enumerate(lines))


def test_evaluation_summary():
    clean, flaky = evaluate(False), evaluate(True)
    assert clean["success"] == 1.0 and clean["total_retries"] == 0
    assert flaky["success"] == 1.0 and flaky["total_retries"] == len(TASKS)
    assert clean["wrong_answers_accepted"] == flaky["wrong_answers_accepted"] == 0


def test_trace_index_is_sequential_across_retries():
    o = run("Total for 4 widgets including shipping?", researcher=Researcher(flaky=True))
    assert [e["n"] for e in o.trace.events] == list(range(len(o.trace.events)))
    assert [e["attempt"] for e in o.trace.events if e["kind"] == "attempt"] == [0, 1]
