"""Tools with strict inputs: a fact table lookup and a safe arithmetic evaluator."""

from __future__ import annotations

import ast
import operator as op

FACTS = {
    "price_widget": 12.5,
    "price_gadget": 40.0,
    "shipping_flat": 5.0,
    "tax_rate": 0.18,
    "discount_bulk": 0.10,
    "bulk_threshold": 10,
}

_OPS = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv}


class ToolError(ValueError):
    pass


def lookup(key: str) -> float:
    if key not in FACTS:
        raise ToolError(f"unknown fact: {key}")
    return FACTS[key]


def calc(expr: str, env: dict[str, float]) -> float:
    """Evaluate + - * / over numbers and previously stored names. No calls, no attributes."""

    def ev(n: ast.AST) -> float:
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, ast.Name):
            if n.id not in env:
                raise ToolError(f"unknown name: {n.id}")
            return float(env[n.id])
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            try:
                return _OPS[type(n.op)](ev(n.left), ev(n.right))
            except ZeroDivisionError as e:
                raise ToolError("division by zero") from e
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            return -ev(n.operand)
        raise ToolError("unsupported expression")

    if len(expr) > 200:
        raise ToolError("expression too long")
    try:
        return ev(ast.parse(expr, mode="eval"))
    except SyntaxError as e:
        raise ToolError("syntax error") from e
