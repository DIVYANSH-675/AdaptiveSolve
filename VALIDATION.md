# Release validation

Executed locally on 2026-11-17 on Linux CPU.

Environment: Python 3.12.3; pytest 9.2.0; Ruff 0.17.5.

- Editable installation succeeded.
- Ruff lint and format checks passed.
- **20 tests passed**, including a command-line workflow test that creates its own data/artifacts.
- Wheel and source-distribution builds succeeded.
- The experiments below ran successfully; raw evaluation output is preserved in [examples/release-report.json](examples/release-report.json).

## Exploratory run

Ran 20 seeded arithmetic fixtures with seed 13. All 20 matched expected answers, with one backend call per fixture and both direct/program routes exercised. This uses a scripted backend, so 100% is a software workflow result, not an LLM reasoning accuracy claim.

Replayed the documented mean example: a confidence-0.4 direct answer was rejected, the next decision executed `sum(numbers) / len(numbers)`, and the result was 4.0 after two calls. The test suite separately exercises syntax/execution repair and malicious/oversized expression rejection.

## Reproduction and scope

Use the README commands, matching the seeds and sizes above. AstroBridge's final evaluation used seed 202. Exact floating-point values can differ across dependency versions and hardware. Generated training checkpoints remain local under ignored `runs/` directories; they are not bundled in the repository or Python distribution.

The CI workflow validates Python 3.10 and 3.12 independently; its current result is visible in [GitHub Actions](https://github.com/DIVYANSH-675/AdaptiveSolve/actions). No GPU benchmark, large external dataset, or paper-result reproduction was run. There is no claim that these development experiments establish general research superiority.

## Input-validation follow-up (2026-11-17)

Validate solver option types before entering the retry loop. Regression tests cover the rejected inputs and valid usage.
The updated full suite passed locally: **26 tests**, including the CLI workflow.
Ruff lint and format checks also passed. The exploratory experiment results above
remain the original measurements; this follow-up did not rerun or replace them.
