# AdaptiveSolve

Adaptive direct/program reasoning with a bounded arithmetic interpreter and repair traces.

AdaptiveSolve implements a direct-answer versus program-execution controller. Low-confidence direct answers trigger a program request, invalid decisions or execution failures trigger bounded repair attempts, and every result records calls and errors.

## Status and provenance

Version 0.1.0 is an original, AI-assisted implementation developed for **Divyansh Gupta**. This repository was written independently: no upstream source files or Git history were imported. Its scientific inspiration is [PIPS](https://arxiv.org/abs/2510.22849); the research ideas remain credited to that paper's authors. The implementation choices and limitations below describe this repository's scope. It is an experimental prototype, not a claimed reproduction of published results.

## Setup

Python 3.10 or newer:

```bash
python -m venv .venv
# Linux/macOS; on Windows use .venv\Scripts\activate
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

## Run

```bash
adaptivesolve demo --count 20 --seed 13 --output runs/demo.json
adaptivesolve solve --question "Sum the supplied numbers." --symbols '{"numbers":[3,7,11]}' --output runs/sum.json
# Replay model decisions stored as a JSON array:
adaptivesolve solve --question "Compute the mean." --symbols '{"numbers":[2,4,6]}' --responses examples/mean-decisions.json --output runs/replay.json
```

Use fresh output paths for new experiments. Training artifacts and generated data are ignored by Git. For independent evaluation, use a different generation seed or a separate dataset; evaluating on the training data is not an unbiased test.

## Implementation

A backend implements `respond(request: dict) -> str` and returns one JSON decision:

```json
{"mode":"direct","confidence":0.95,"answer":5}
```

or

```json
{"mode":"program","confidence":0.9,"expression":"sum(numbers)"}
```

Requests include the question, numeric symbols, a `require_program` flag, attempt index, and previous errors. The default threshold is 0.8 and the total call budget is three. The included `ReplayBackend` accepts saved decisions; `DemoBackend` is a deterministic fixture for arithmetic workflow testing. Integrate a live model by implementing the backend protocol; no hosted model or credentials are bundled.

Programs are interpreted from an AST without `eval` or `exec`. Supported operations are bounded scalar arithmetic, one comparison, conditional expressions, numeric lists, integer indexing, and one-argument `sum`, `min`, `max`, `len`, `sorted`, `abs`, and `round`. There are no attributes, imports, comprehensions, arbitrary calls, loops, file access, or network access in this language. Limits include 4096 expression characters, 256 AST nodes, 128 list items, 256-bit integers, depth limits, and bounded exponents. This is a deliberately small expression language, not a general-purpose Python sandbox.

## Data and artifacts

Reports contain the answer, selected mode, call count, repair count, and error trace. Demo output additionally includes every fixture and expected answer. Output files are created exclusively to avoid overwriting experiments. The package uses only the Python standard library at runtime. A custom backend remains responsible for its own request timeouts, token budgets, and external API handling.

## Validation

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m build
```

The test suite covers: Correct arithmetic and list operations; rejection of unsupported or oversized expressions; direct/program routes and confidence fallback; execution repair; strict decision schemas; call budgets; seeded fixture reproducibility; CLI report generation.

CI runs the suite on Python 3.10 and 3.12. Small synthetic runs validate software behavior; they do not establish a research result. See [VALIDATION.md](VALIDATION.md) for the release checks actually performed.

## Limitations

This controller is not the PIPS model or a reproduction of its benchmark results. It has no trained router, live LLM adapter, general Python executor, or calibrated confidence estimator. The scripted demo's accuracy only confirms workflow behavior. Confidence comes from the backend and may be wrong; numerical execution does not prove that a generated program matches the question. Evaluate actual model decisions on independently labeled tasks before claiming reasoning improvements.

## Configuring routing and retries

`Solver` accepts a finite numeric confidence threshold in `[0, 1]` and an integer `max_attempts` in `[1, 10]`. Booleans are not accepted for either setting. Fractional attempt counts and string thresholds raise `ValueError` during construction, before any backend call.

```python
from adaptivesolve.solver import DemoBackend, Solver

solver = Solver(DemoBackend(), threshold=0.85, max_attempts=3)
result = solver.solve("What is 2 + 3?")
assert result.answer == 5
```

The attempt budget counts all backend responses, including confidence-triggered program requests and repair attempts. A backend adapter should impose its own timeout; the attempt count is not a wall-clock limit. After the budget is exhausted, the solver raises `ValueError` with the collected error trace.

## License

The original code in this repository is MIT licensed, copyright 2026 Divyansh Gupta. See [LICENSE](LICENSE). The cited paper is a separate work; this code's license does not relicense the paper or external datasets.
