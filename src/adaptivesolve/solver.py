"""Adaptive direct/program routing with repair and explicit backend boundaries."""

import json
import math
import random
import re
from dataclasses import asdict, dataclass
from typing import Protocol

from .language import ExpressionError, Interpreter


class Backend(Protocol):
    def respond(self, request: dict) -> str:
        """Return a JSON decision: mode, confidence, and answer or expression."""
        ...


@dataclass
class Result:
    answer: object
    mode: str
    calls: int
    repairs: int
    errors: list


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def decision(raw):
    if not isinstance(raw, str) or len(raw) > 16384:
        raise ValueError("Backend response must be a JSON string up to 16384 characters")
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_unique_object,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Non-finite JSON")),
        )
    except (json.JSONDecodeError, RecursionError) as error:
        raise ValueError("Backend returned invalid JSON") from error
    if not isinstance(value, dict) or value.get("mode") not in ("direct", "program"):
        raise ValueError("Decision requires mode direct or program")
    confidence = value.get("confidence")
    if (
        type(confidence) not in (int, float)
        or not 0 <= confidence <= 1
        or not math.isfinite(confidence)
    ):
        raise ValueError("Decision requires finite confidence in [0, 1]")
    field = "answer" if value["mode"] == "direct" else "expression"
    if field not in value:
        raise ValueError(f"Decision is missing {field}")
    if field == "expression" and (
        not isinstance(value[field], str) or not value[field].strip() or len(value[field]) > 4096
    ):
        raise ValueError("Program decisions require an expression of 1..4096 characters")
    return value


class Solver:
    def __init__(self, backend: Backend, threshold=0.8, max_attempts=3):
        if (
            type(threshold) not in (int, float)
            or not 0 <= threshold <= 1
            or not math.isfinite(threshold)
            or type(max_attempts) is not int
            or not 1 <= max_attempts <= 10
        ):
            raise ValueError("threshold must be in [0,1]; max_attempts must be in [1,10]")
        self.backend = backend
        self.threshold = threshold
        self.max_attempts = max_attempts
        self.interpreter = Interpreter()

    def solve(self, question, symbols=None):
        if not isinstance(question, str) or not question.strip() or len(question) > 8192:
            raise ValueError("A question of 1..8192 characters is required")
        symbols = {} if symbols is None else symbols
        # Validate symbols even if the backend selects the direct route.
        self.interpreter.run("0", symbols)
        errors = []
        forced_program = False
        repairs = 0
        for attempt in range(self.max_attempts):
            request = dict(
                question=question,
                symbols=symbols,
                require_program=forced_program,
                previous_errors=list(errors),
                attempt=attempt,
            )
            try:
                parsed = decision(self.backend.respond(request))
                if parsed["mode"] == "direct":
                    if forced_program or parsed["confidence"] < self.threshold:
                        errors.append(
                            "A program was required; the backend returned another direct answer"
                            if forced_program
                            else "Direct answer confidence below threshold; generate an expression"
                        )
                        forced_program = True
                        continue
                    answer = self.interpreter.check(parsed["answer"])
                    return Result(answer, "direct", attempt + 1, repairs, errors)
                answer = self.interpreter.run(parsed["expression"], symbols)
                return Result(answer, "program", attempt + 1, repairs, errors)
            except (ValueError, ExpressionError) as error:
                errors.append(str(error))
                repairs += 1
                forced_program = True
        raise ValueError(
            f"No valid answer after {self.max_attempts} attempts: " + "; ".join(errors)
        )


class ReplayBackend:
    """Consume pre-recorded model decisions, useful for reproducible evaluation."""

    def __init__(self, responses):
        self.responses = iter(responses)

    def respond(self, request):
        try:
            response = next(self.responses)
        except StopIteration as error:
            raise ValueError("Replay decisions exhausted") from error
        return response if isinstance(response, str) else json.dumps(response, allow_nan=False)


class DemoBackend:
    """A scripted fixture, not a learned language model."""

    def respond(self, request):
        if "numbers" in request["symbols"]:
            return json.dumps(dict(mode="program", confidence=1.0, expression="sum(numbers)"))
        match = re.fullmatch(r"What is (-?\d+) \+ (-?\d+)\?", request["question"])
        if match:
            left, right = map(int, match.groups())
            if request["require_program"]:
                return json.dumps(
                    dict(mode="program", confidence=1.0, expression=f"{left} + {right}")
                )
            return json.dumps(dict(mode="direct", confidence=1.0, answer=left + right))
        raise ValueError("Demo backend only supports its documented arithmetic fixtures")


def benchmark(count=20, seed=0):
    if not 1 <= count <= 10000:
        raise ValueError("Benchmark count must be in [1,10000]")
    rng = random.Random(seed)
    solver = Solver(DemoBackend())
    rows = []
    for index in range(count):
        if index % 2:
            numbers = [rng.randint(-100, 100) for _ in range(8)]
            question = "Sum the supplied numbers."
            symbols = {"numbers": numbers}
            expected = sum(numbers)
        else:
            left, right = rng.randint(-100, 100), rng.randint(-100, 100)
            question = f"What is {left} + {right}?"
            symbols = {}
            expected = left + right
        result = solver.solve(question, symbols)
        rows.append(
            dict(
                question=question,
                symbols=symbols,
                expected=expected,
                correct=result.answer == expected,
                **asdict(result),
            )
        )
    return dict(
        note="Scripted workflow test; accuracy is not an LLM benchmark result.",
        seed=seed,
        count=count,
        accuracy=sum(row["correct"] for row in rows) / count,
        model_calls=sum(row["calls"] for row in rows),
        rows=rows,
    )
