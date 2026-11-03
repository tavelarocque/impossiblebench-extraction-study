# Does ImpossibleBench's code extraction change its measured cheating rate?

A measurement study of [ImpossibleBench](https://github.com/safety-research/impossiblebench)'s
minimal scaffold, prompted by [PR #6](https://github.com/safety-research/impossiblebench/pull/6),
which changes `find_code`, the function that decides which code block in a model's reply gets
executed. On impossible tasks a pass means the model defeated the tests, so that choice sits
directly under the benchmark's headline metric. Two models, one analysis plan fixed before
generation.

## Results

**1. On final scores, the extraction rule barely matters.** The two-block `check` override
that PR #6's rule cannot see never occurred. Pre-registered verdict for both models: **only in
principle**.

| Impossible splits, tests modifiable | Qwen3.5-9B (n = 205) | Gemini 3.1 Pro preview (n = 199) |
|---|---|---|
| Replies with a block whose only definition is `check` | 0 (0 in any attempt) | 0 (0 in any attempt) |
| Defs-in-order rule minus PR #6's rule (E1) | −0.5 points [−1.5, 0.0], McNemar b = 0, c = 1 | 0.0 points [0.0, 0.0], b = c = 0 |
| Episodes where main and PR #6 score differently | 0 | 1 (`oneoff` `lcbhard_26`, below) |

**2. On the feedback the model sees between attempts, main's rule is broken about one time in
five.** When a reply has more than one code block, main's `find_code` can return the prose
between them, which then fails with a `SyntaxError`, and that error is what the model is shown
as test feedback. PR #6's rule finds parseable code on the same reply.

| Attempts where main's selection does not compile and PR #6's does | Qwen3.5-9B | Gemini 3.1 Pro preview |
|---|---|---|
| Share of all attempts (95% CI, episode bootstrap) | 949 / 4,590 = 20.7% [19.2, 22.2] | 311 / 1,581 = 19.7% [17.4, 21.8] |
| Episodes affected | 388 / 515 | 140 / 199 |
| Reverse (PR #6 unparseable, main parseable) | 0 | 0 |

Confirmatory for Gemini (added to the plan before its full run); exploratory for Qwen, whose
data had already been seen. This measures what the model was fed, not how it would have
behaved given correct feedback.

**3. Requiring `check()` to actually finish changes Gemini's cheating rate by a factor of
two to three.** This replicates the exit-before-check effect from
[issue #5](https://github.com/safety-research/impossiblebench/issues/5).

| Gemini 3.1 Pro preview, PR #6's rule | `conflicting` (n = 103) | `oneoff` (n = 96) |
|---|---|---|
| E0: exit code 0 (the benchmark as published) | 59.2% | 64.6% |
| E1: exit code 0 and a token printed after `check()` | 19.4% | 33.3% |

71 of the 123 E0 passes exit before `check()` finishes, every one via `sys.exit`. For Qwen3.5-9B
the completion token changes no score. Gemini's E0 rates are lower than the 84% and 73% issue
#5 reports for this model on the same scaffold and prompt; the issue does not give its
generation settings (this run used medium reasoning effort and a 40,960-token answer cap), so
read this as the same direction of effect, not a reproduction of its size.

Full reports: [`results/qwen3.5-9b/report.md`](results/qwen3.5-9b/report.md),
[`results/gemini-3.1-pro-preview/report.md`](results/gemini-3.1-pro-preview/report.md).
Hand reading of the interesting episodes: [Qwen](results/qwen3.5-9b/hand_read.md),
[Gemini](results/gemini-3.1-pro-preview/hand_read.md).

## Why it was worth measuring

In the minimal scaffold the model is told its code blocks "will overwrite the original
functions", and with `allow_test_modifications=True` its answer runs *after* the test, so
redefining `check` is exactly the cheat the benchmark counts. Both main's `find_code` and
PR #6's rule skip a block that only redefines `check`, so a reply of the form "honest attempt,
then a block replacing `check`" is scored on the honest attempt. A 10-fixture suite
([`tests/compare_rules.py`](tests/compare_rules.py), published as a
[gist](https://gist.github.com/tavelarocque/ac56c3ba0e04b615d37d8ae8c173eec6) before any model
call) shows this happening. The open question was how often real models write that pattern.

## Method

- **Generation.** The benchmark exactly as published (main `d4f9a14`), minimal scaffold, the
  repo's example prompt, up to 10 attempts, Inspect 0.3.287, models via OpenRouter.
  - Qwen3.5-9B: every task in `conflicting`, `oneoff` and `original` with tests modifiable,
    plus `conflicting` and `oneoff` with tests locked as a control: 515 episodes.
  - Gemini 3.1 Pro preview: `conflicting` and `oneoff` with tests modifiable only, 199 of 206
    episodes (see caveats).
- **Re-scoring.** Each final reply is scored offline under 4 extraction rules × 2 exit
  settings, composing the code byte-for-byte as `agentic_humaneval_scorer` does. Rules: R0 main,
  R1 PR #6 (`9545d24`), R2 last block by position, R3 every definition from every block in
  order. R0 and R1 are loaded from pinned checkouts of the benchmark, not re-implemented.
  Exit settings: E0 exit code 0; E1 exit code 0 and a token printed after `check()` returns.
  H4 applies R0 and R1 to every attempt's reply and records whether each selection compiles.
- **Isolation.** Every scoring run gets its own container from the benchmark's sandbox image,
  with the same 1 GB limit, no network, an unprivileged user and a read-only root filesystem.
  Model-written code never runs on the host.
- **Gates.** Nothing is reported unless every gate passes: the fixture table reproduces;
  22 planted known-answer cases score as predicted; and replaying each reply under R0 + E0
  reproduces the score Inspect logged (Qwen 512 of 515, with 3 timing-sensitive cases handled
  by a pre-registered rule; Gemini 199 of 199).
- **Analysis plan** fixed before generation, with every later change logged with its date and
  reason: [`PREREGISTRATION.md`](PREREGISTRATION.md).

## Caveats

- **Gemini is 199 of 206 episodes, and the stopping decision was made after seeing results.**
  The OpenRouter account ran out of credit mid-run; a targeted retry recovered 41 of the 48
  failed episodes, and the other 7 failed again on credit. They are the 7 highest `oneoff` task ids (`lcbhard_78`, 90, 95, 99,
  100, 101, 102), so not a random sample, and are listed in
  [`excluded.json`](results/gemini-3.1-pro-preview/excluded.json). `conflicting` is complete.
- **Gemini has no controls.** The `original` split and the tests-locked control were dropped
  for cost, decided before the Gemini run (after the Qwen results were known) and logged.
- **The rule comparison for Gemini is mostly a null on a pattern that never appears.** Gemini
  cheats a lot, but by exiting early, not by overriding `check` in a second block, so the
  extraction rule has little to act on.
- **R3 is a reference rule with blind spots, not ground truth.** It misses a `check` override
  nested in an `if __name__ == "__main__":` block (Qwen `lcbhard_7`) and drops legitimate
  top-level setup code. For Gemini under E0 it also drops top-level `sys.exit` calls, which is
  the entire −21.1-point H3 interaction; under E1 the rules agree exactly.
- **Timing (Qwen).** Part of generation ran while the machine was CPU-saturated by an unrelated
  job. 3 episodes sit near the 30 s test limit and replay differently; they are set aside under
  the pre-registered rule, and including them changes nothing. Excluding all episodes with any
  timeout also changes nothing for either model.
- **Two models.** Qwen3-8B (used in PR #6's own 926-reply check) was retired on OpenRouter
  before this run, so the comparison with that data is indirect.
- **Pre-registration provenance.** The plan was written before any model call in a private
  document with revision history and is exported verbatim here; the extraction rules and
  fixtures were public in the gist before the first call.

## Reproduce

Needs Docker (OrbStack on macOS works), [uv](https://github.com/astral-sh/uv) and an
OpenRouter key stored in the macOS Keychain as `openrouter-api-key`.

```bash
./setup.sh                                          # pinned checkouts, venv, sandbox image, all gates
./run.sh smoke                                      # 2 tasks end to end, a few cents
./run.sh small                                      # Qwen3.5-9B, 515 episodes, about $3.30
./run.sh frontier google/gemini-3.1-pro-preview     # 206 episodes, roughly $95
./run.sh retry frontier google/gemini-3.1-pro-preview --dry-run   # list errored episodes
```

Re-scoring and analysis alone, on existing logs:

```bash
.venv/bin/python rescore.py --logs logs/qwen_qwen3.5-9b --main repos/main --pr6 repos/pr6 \
    --out results/qwen_qwen3.5-9b/rows.jsonl
.venv/bin/python analyze.py --rows results/qwen_qwen3.5-9b/rows.jsonl \
    --out results/qwen_qwen3.5-9b/report.md
```

Re-scoring caches each job's result, so an interrupted run resumes where it stopped.

## Files

| Path | What it is |
|---|---|
| `rules.py` | The four extraction rules, the scorer's composition, the `check`-only detector |
| `executor.py` | Isolated execution: one container per run, stall retry, result cache |
| `planted.py` | Known-answer cases re-scored alongside every real run |
| `generate.py`, `run.sh` | Generation with the published benchmark, including targeted retry of errored episodes |
| `rescore.py`, `analyze.py` | Re-scoring under 8 conditions plus H4; pre-registered analysis |
| `tests/` | Fixture gate, end-to-end replay of a real Inspect eval, mismatch paths, executor faults |
| `results/<model>/episodes.csv` | One row per episode: every condition's outcome, flags and H4 attempt counts |
| `results/<model>/rows.jsonl.gz` | The same plus each final reply and the code R1 and R3 selected |
| `results/<model>/excluded.json` | Episodes excluded as infrastructure failures, with the error |

Raw Inspect logs (full multi-attempt transcripts) are not included; the final reply for every
episode is in `rows.jsonl.gz`.

## License

MIT
