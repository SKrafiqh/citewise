"""Evaluate a model-written arithmetic expression without executing code (AS-3).

The second model proposes ONE expression (numbers, + - * / ** %, a few math functions). It is parsed
with `ast` and walked node by node: anything not explicitly allowed (names, attributes, strings,
subscripts, lambdas, keyword arguments, ...) is rejected, so there is nothing to escape from.
"""
import ast
import math
import operator

MAX_EXPRESSION_CHARS = 300
MAX_EXPONENT = 1000
MAX_FACTORIAL = 400
MAX_BITS = 10_000
MAX_COMB_ARG = 2000

_BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
           ast.Pow: operator.pow, ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv}
_UNARY = {ast.USub: operator.neg, ast.UAdd: operator.pos}
_FUNCTIONS = {"sqrt": math.sqrt, "exp": math.exp, "log": math.log, "ln": math.log, "log10": math.log10,
              "factorial": math.factorial, "comb": math.comb, "perm": math.perm, "abs": abs,
              "min": min, "max": max, "round": round}
_CONSTANTS = {"pi": math.pi, "e": math.e}


class UnsafeExpression(ValueError):
    pass


def _checked(value):
    if isinstance(value, int) and value.bit_length() > MAX_BITS:
        raise UnsafeExpression("number too large")
    return value


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.Name) and node.id in _CONSTANTS:
        return _CONSTANTS[node.id]
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and (abs(right) > MAX_EXPONENT or (isinstance(left, int) and left.bit_length() * abs(right) > MAX_BITS)):
            raise UnsafeExpression("power too large")
        return _checked(_BINARY[type(node.op)](left, right))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS and not node.keywords:
        args = [_eval(a) for a in node.args]
        if node.func.id == "factorial" and (not args or args[0] > MAX_FACTORIAL):
            raise UnsafeExpression("factorial argument too large")
        if node.func.id in {"factorial", "comb", "perm"}:
            if any(abs(a) > MAX_COMB_ARG for a in args):
                raise UnsafeExpression("argument too large")
            args = [int(a) for a in args]
        return _checked(_FUNCTIONS[node.func.id](*args))
    raise UnsafeExpression(f"{type(node).__name__} is not allowed")


def evaluate(expression: str) -> float:
    """Return the value of the expression; raise UnsafeExpression for anything else."""
    text = expression.strip()
    if not text or len(text) > MAX_EXPRESSION_CHARS:
        raise UnsafeExpression("expression is empty or too long")
    try:
        tree = ast.parse(text, mode="eval")
        return float(_eval(tree.body))
    except UnsafeExpression:
        raise
    except (SyntaxError, ArithmeticError, TypeError, ValueError, OverflowError) as exc:
        raise UnsafeExpression(f"could not evaluate: {type(exc).__name__}") from exc
