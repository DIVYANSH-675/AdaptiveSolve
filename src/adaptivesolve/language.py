"""An interpreted arithmetic expression language: no Python eval or exec."""

import ast
import math
import operator


class ExpressionError(ValueError):
    pass


class Interpreter:
    """Bounded scalar/list arithmetic. This is intentionally not general Python."""

    def __init__(self, max_nodes=256, max_items=128, max_bits=256):
        for key, value, low, high in (
            ("max_nodes", max_nodes, 1, 4096),
            ("max_items", max_items, 1, 1024),
            ("max_bits", max_bits, 8, 4096),
        ):
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{key} must be an integer in [{low},{high}]")
        self.max_nodes = max_nodes
        self.max_items = max_items
        self.max_bits = max_bits

    def check(self, value, depth=0):
        if depth > 12:
            raise ExpressionError("Value nesting limit exceeded")
        if type(value) is bool:
            return value
        if type(value) is int and value.bit_length() <= self.max_bits:
            return value
        if type(value) is float and math.isfinite(value) and abs(value) <= 1e100:
            return value
        if type(value) in (list, tuple) and len(value) <= self.max_items:
            return [self.check(v, depth + 1) for v in value]
        raise ExpressionError(
            "Only bounded finite numbers, booleans, and numeric lists are supported"
        )

    def run(self, expression, symbols=None):
        if not isinstance(expression, str) or len(expression) > 4096:
            raise ExpressionError("Expression must be a string of at most 4096 characters")
        symbols = {} if symbols is None else symbols
        if not isinstance(symbols, dict) or len(symbols) > self.max_items:
            raise ExpressionError("Symbols must be a bounded dictionary")
        environment = {name: self.check(value) for name, value in symbols.items()}
        if any(
            not isinstance(name, str) or not name.isidentifier() or name.startswith("_")
            for name in environment
        ):
            raise ExpressionError("Invalid symbol name")
        try:
            tree = ast.parse(expression, mode="eval")
        except (SyntaxError, ValueError, RecursionError) as error:
            raise ExpressionError("Invalid expression syntax") from error
        if sum(1 for _ in ast.walk(tree)) > self.max_nodes:
            raise ExpressionError("Expression node limit exceeded")
        budget = [self.max_nodes]

        def visit(node, depth=0):
            budget[0] -= 1
            if budget[0] < 0 or depth > 32:
                raise ExpressionError("Expression evaluation limit exceeded")

            def child(n):
                return visit(n, depth + 1)

            if isinstance(node, ast.Constant):
                result = node.value
            elif isinstance(node, ast.Name):
                if node.id not in environment:
                    raise ExpressionError(f"Unknown symbol: {node.id}")
                result = environment[node.id]
            elif isinstance(node, (ast.List, ast.Tuple)):
                if len(node.elts) > self.max_items:
                    raise ExpressionError("List size limit exceeded")
                result = [child(item) for item in node.elts]
            elif isinstance(node, ast.BinOp):
                left, right = child(node.left), child(node.right)
                # No sequence operations: bound numeric operands before computing.
                if type(left) not in (int, float) or type(right) not in (int, float):
                    raise ExpressionError("Binary operators require numbers")
                operations = {
                    ast.Add: operator.add,
                    ast.Sub: operator.sub,
                    ast.Mult: operator.mul,
                    ast.Div: operator.truediv,
                    ast.FloorDiv: operator.floordiv,
                    ast.Mod: operator.mod,
                }
                if isinstance(node.op, ast.Pow):
                    if abs(right) > 16 or (
                        left < 0 and type(right) is float and not right.is_integer()
                    ):
                        raise ExpressionError("Exponent outside supported range")
                    if (
                        type(left) is int
                        and type(right) is int
                        and right > 0
                        and left.bit_length() * right > self.max_bits
                    ):
                        raise ExpressionError("Integer power exceeds size limit")
                    result = left**right
                elif type(node.op) in operations:
                    result = operations[type(node.op)](left, right)
                else:
                    raise ExpressionError("Unsupported binary operator")
            elif isinstance(node, ast.UnaryOp) and isinstance(
                node.op, (ast.UAdd, ast.USub, ast.Not)
            ):
                value = child(node.operand)
                if type(value) not in (int, float, bool):
                    raise ExpressionError("Unary operators require scalar values")
                result = {ast.UAdd: operator.pos, ast.USub: operator.neg, ast.Not: operator.not_}[
                    type(node.op)
                ](value)
            elif isinstance(node, ast.Compare) and len(node.ops) == 1:
                operations = {
                    ast.Eq: operator.eq,
                    ast.NotEq: operator.ne,
                    ast.Lt: operator.lt,
                    ast.LtE: operator.le,
                    ast.Gt: operator.gt,
                    ast.GtE: operator.ge,
                }
                if type(node.ops[0]) not in operations:
                    raise ExpressionError("Unsupported comparison")
                result = operations[type(node.ops[0])](child(node.left), child(node.comparators[0]))
            elif isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
                result = child(node.values[0])
                for operand in node.values[1:]:
                    if (isinstance(node.op, ast.And) and not result) or (
                        isinstance(node.op, ast.Or) and result
                    ):
                        break
                    result = child(operand)
            elif isinstance(node, ast.IfExp):
                result = child(node.body if child(node.test) else node.orelse)
            elif isinstance(node, ast.Subscript):
                value, index = child(node.value), child(node.slice)
                if not isinstance(value, list) or type(index) is not int:
                    raise ExpressionError("Indexing requires a list and integer")
                result = value[index]
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.keywords or len(node.args) != 1:
                    raise ExpressionError("Functions take exactly one positional argument")
                value = child(node.args[0])
                if node.func.id in ("sum", "min", "max", "len", "sorted"):
                    if not isinstance(value, list) or any(
                        type(v) not in (int, float, bool) for v in value
                    ):
                        raise ExpressionError("Aggregate functions require a flat numeric list")
                    result = {"sum": sum, "min": min, "max": max, "len": len, "sorted": sorted}[
                        node.func.id
                    ](value)
                elif node.func.id in ("abs", "round", "sqrt", "floor", "ceil") and type(value) in (
                    int,
                    float,
                ):
                    result = {
                        "abs": abs,
                        "round": round,
                        "sqrt": math.sqrt,
                        "floor": math.floor,
                        "ceil": math.ceil,
                    }[node.func.id](value)
                else:
                    raise ExpressionError("Unsupported function")
            else:
                raise ExpressionError(f"Unsupported syntax: {type(node).__name__}")
            return self.check(result)

        try:
            return visit(tree.body)
        except ExpressionError:
            raise
        except (ArithmeticError, TypeError, ValueError, IndexError, RecursionError) as error:
            raise ExpressionError(f"Expression failed: {type(error).__name__}") from error
