import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .solver import DemoBackend, ReplayBackend, Solver, benchmark


def main():
    p = argparse.ArgumentParser(
        description="Adaptive arithmetic reasoning with bounded expression execution"
    )
    p.add_argument("command", choices=["demo", "solve"])
    p.add_argument("--question")
    p.add_argument("--symbols", default="{}", help="JSON object of numeric symbols")
    p.add_argument(
        "--responses",
        help="JSON array of recorded model decisions; otherwise use scripted demo backend",
    )
    p.add_argument("--threshold", type=float, default=0.8)
    p.add_argument("--max-attempts", type=int, default=3)
    p.add_argument("--seed", type=int, default=13)
    p.add_argument("--count", type=int, default=20)
    p.add_argument("--output", default="runs/result.json")
    a = p.parse_args()
    try:
        if a.command == "demo":
            report = benchmark(a.count, a.seed)
        else:
            if not a.question:
                p.error("solve requires --question")
            symbols = json.loads(a.symbols)
            if a.responses:
                responses = json.loads(Path(a.responses).read_text())
                if not isinstance(responses, list):
                    p.error("--responses must contain a JSON array")
                backend = ReplayBackend(responses)
            else:
                backend = DemoBackend()
            report = asdict(Solver(backend, a.threshold, a.max_attempts).solve(a.question, symbols))
    except (ValueError, OSError) as error:
        p.error(str(error))
    output = Path(a.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, allow_nan=False))
