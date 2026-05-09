import pytest

from adaptivesolve.language import ExpressionError, Interpreter
from adaptivesolve.solver import DemoBackend, ReplayBackend, Solver, benchmark, decision


@pytest.mark.parametrize(
    "expression",
    [
        '__import__("os").system("id")',
        "(1).__class__",
        "[x for x in [1,2]]",
        "2 ** 100000000",
        "[1] * 100000000",
        "sum([1, 2], start=0)",
        "1e309",
        "1 / 0",
        "open(1)",
        "numbers[999]",
    ],
)
def test_unsupported_and_explosive_expressions_rejected(expression):
    with pytest.raises(ExpressionError):
        Interpreter().run(expression, {"numbers": [1, 2]})


def test_arithmetic_and_limits():
    language = Interpreter()
    assert language.run("sum(numbers) / len(numbers)", {"numbers": [2, 4, 6]}) == 4
    assert language.run("max(numbers) if len(numbers) > 0 else 0", {"numbers": [-3, 7]}) == 7
    assert language.run("sorted(numbers)[0]", {"numbers": [5, 2, 3]}) == 2
    with pytest.raises(ExpressionError):
        language.run("1", {"numbers": list(range(129))})
    with pytest.raises(ExpressionError):
        language.run("1", {"value": 2**300})


def test_routes_and_uncertainty_fallback():
    assert Solver(DemoBackend()).solve("What is 2 + 3?").mode == "direct"
    backend = ReplayBackend(
        [
            dict(mode="direct", confidence=0.2, answer=9),
            dict(mode="program", confidence=0.8, expression="sum(numbers)"),
        ]
    )
    result = Solver(backend).solve("sum", {"numbers": [2, 3]})
    assert (result.answer, result.mode, result.calls) == (5, "program", 2)


def test_execution_failure_is_repaired():
    backend = ReplayBackend(
        [
            dict(mode="program", confidence=0.9, expression="1/0"),
            dict(mode="program", confidence=0.9, expression="sum(numbers)"),
        ]
    )
    result = Solver(backend).solve("sum", {"numbers": [1, 2]})
    assert result.answer == 3 and result.repairs == 1 and len(result.errors) == 1


@pytest.mark.parametrize(
    "raw",
    [
        "[]",
        '{"mode":"direct","confidence":NaN,"answer":1}',
        '{"mode":"direct","confidence":true,"answer":1}',
        '{"mode":"direct","confidence":0.9}',
    ],
)
def test_invalid_decision_schema(raw):
    with pytest.raises(ValueError):
        decision(raw)


def test_attempt_budget_and_reproducibility():
    backend = ReplayBackend(["broken"] * 10)
    with pytest.raises(ValueError, match="after 2 attempts"):
        Solver(backend, max_attempts=2).solve("test")
    assert benchmark(12, 42) == benchmark(12, 42)
    report = benchmark(12, 42)
    assert report["accuracy"] == 1 and {r["mode"] for r in report["rows"]} == {"direct", "program"}


def test_oversized_confidence_is_rejected_without_overflow():
    import json

    with pytest.raises(ValueError):
        decision(json.dumps(dict(mode="direct", confidence=10**1000, answer=1)))


@pytest.mark.parametrize(
    "options",
    [
        {"max_attempts": 2.5},
        {"max_attempts": True},
        {"max_attempts": 0},
        {"threshold": True},
        {"threshold": "0.8"},
        {"threshold": 10**1000},
    ],
)
def test_solver_rejects_invalid_options_before_calling_backend(options):
    with pytest.raises(ValueError, match="threshold"):
        Solver(ReplayBackend([]), **options)


def test_forced_program_rejection_reports_the_actual_cause():
    backend = ReplayBackend(
        [
            dict(mode="direct", confidence=0.1, answer=2),
            dict(mode="direct", confidence=0.99, answer=2),
            dict(mode="program", confidence=0.9, expression="1+1"),
        ]
    )
    result = Solver(backend).solve("Compute two")
    assert result.answer == 2 and result.calls == 3
    assert "confidence below" in result.errors[0]
    assert "program was required" in result.errors[1]


def test_duplicate_decision_keys_are_not_silently_overwritten():
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        decision('{"mode":"direct","confidence":0.1,"confidence":1.0,"answer":2}')
