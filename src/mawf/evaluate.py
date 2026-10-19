"""python -m mawf.evaluate : run the task suite with and without injected faults."""

from __future__ import annotations

import json

from .agents import Researcher
from .orchestrator import run

TASKS = [
    ("Total for 4 widgets?", 50.0),
    ("Total for 3 gadgets?", 120.0),
    ("Total for 4 widgets including shipping?", 55.0),
    ("Total for 4 widgets including shipping and tax?", 64.9),
    ("Total for 10 widgets with bulk discount?", 112.5),
    ("Total for 10 gadgets with bulk discount and shipping?", 365.0),
    ("Total for 20 widgets with bulk discount, shipping and tax?", 271.4),
    ("Total for 2 gadgets with tax?", 94.4),
]


def evaluate(flaky: bool) -> dict:
    ok = retries = 0
    wrong = 0
    for q, expected in TASKS:
        o = run(q, researcher=Researcher(flaky=flaky))
        ok += o.ok
        retries += o.attempts - 1
        wrong += o.ok and abs(o.answer - expected) > 0.01
    n = len(TASKS)
    return {"flaky_researcher": flaky, "tasks": n, "success": round(ok / n, 3),
            "wrong_answers_accepted": wrong, "total_retries": retries}


if __name__ == "__main__":
    for f in (False, True):
        print(json.dumps(evaluate(f)))
