import json
import subprocess
import sys


def test_command_line_round_trip(tmp_path):
    def run(*args):
        result = subprocess.run(
            [sys.executable, "-m", "adaptivesolve", *map(str, args)],
            capture_output=True,
            text=True,
            timeout=90,
        )
        assert result.returncode == 0, result.stdout + "\n" + result.stderr

    run("demo", "--count", "10", "--output", tmp_path / "report.json")
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["count"] == 10 and report["accuracy"] == 1
    run(
        "solve",
        "--question",
        "Sum the supplied numbers.",
        "--symbols",
        '{"numbers":[3,7,11]}',
        "--output",
        tmp_path / "answer.json",
    )
    assert json.loads((tmp_path / "answer.json").read_text())["answer"] == 21
