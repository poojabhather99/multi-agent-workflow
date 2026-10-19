# multi-agent-workflow

[![CI](https://github.com/poojabhather99/multi-agent-workflow/actions/workflows/ci.yml/badge.svg)](https://github.com/poojabhather99/multi-agent-workflow/actions/workflows/ci.yml)

A small multi-agent pipeline built around the parts that usually break in practice: **typed contracts between agents, an auditable trace, and a critic that can reject work and trigger a retry.**

Three roles:

- **Planner** turns a question into a list of steps (`lookup` a fact, or `calc` an expression). The default planner is rule-based so everything runs offline; `llm_planner` wraps any `complete(prompt) -> str` function.
- **Researcher** executes the plan against two tools: a fact table lookup and an arithmetic evaluator built on `ast` (numbers, names, `+ - * /` only; no calls, attributes or exponentiation).
- **Critic** independently checks the researcher's reported answer against the last value computed in the trace, and rejects mismatches.

The orchestrator loops plan, research, review for up to three attempts and records every event in a JSONL-able trace.

## Why the contracts matter

A plan is untrusted input, whether it comes from a model or a bug. `parse_plan` rejects unknown tools, empty arguments, duplicate or non-identifier names, and plans longer than 8 steps before anything runs. A rejected plan counts as a failed attempt and is logged, so a model that proposes `{"tool": "shell", ...}` never reaches execution (there is a test for exactly that).

## Run

```bash
pip install -e ".[dev]"
python -m mawf.evaluate
pytest -q          # 30 tests
```

## Evaluation

Eight pricing questions with known answers (quantity, bulk discount, shipping, tax combined in different ways). The second run injects a fault: the researcher reports an answer 10% too high on its first attempt.

| Researcher | Success | Wrong answers accepted | Retries |
|---|---|---|---|
| Normal | 8/8 | 0 | 0 |
| Fault injected | 8/8 | 0 | 8 |

The critic caught every injected fault and one retry fixed each. During development the rule planner had a bug (it reused a variable name, which the contract forbids) that made 5 of 8 tasks fail on the first run; the contract rejection is what exposed it, and the fix was in the planner.

## Limitations

- The critic checks that the answer is consistent with the trace, not that the plan was right. A wrong plan that computes consistently would pass. Catching that needs an independent solver or a second model.
- The task family is narrow and the rule planner is hand-written for it, so 8/8 says the plumbing works, not that the agents generalise. The LLM planner path is tested with stubbed replies only; it has not been run against a live model.
- The injected fault is one artificial kind (a scaled final answer).
