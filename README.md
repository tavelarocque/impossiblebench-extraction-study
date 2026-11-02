# Does ImpossibleBench's code extraction change its measured cheating rate?

A measurement study of [ImpossibleBench](https://github.com/safety-research/impossiblebench)'s
minimal scaffold, prompted by [PR #6](https://github.com/safety-research/impossiblebench/pull/6),
which changes `find_code`, the function that decides which code block in a model's reply gets
executed. On impossible tasks a pass means the model defeated the tests, so that choice sits
directly under the benchmark's headline metric.

**Result for Qwen3.5-9B: the effect is real in principle and absent in practice.**

| Measure (impossible splits, tests modifiable, n = 205) | Result |
|---|---|
| Final replies containing a block whose only definition is `check` | **0** (0 in any attempt) |
| Pass rate, PR #6's rule, `check()` must complete | 9.8% `conflicting`, 5.8% `oneoff` |
| Defs-in-order rule minus PR #6's rule | **−0.5 points**, 95% CI [−1.5, 0.0], McNemar b = 0, c = 1 |
| main, PR #6 and last-block rules | identical score on every episode of every split |
| Requiring `check()` to complete (issue #5's token check) | changes no score |
| No-modify control: rules disagree | 0 of 206 (expected 0) |

Pre-registered verdict: **only in principle**. Full output: [`results/qwen3.5-9b/report.md`](results/qwen3.5-9b/report.md).

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

- **Generation.** The benchmark exactly as published (main `d4f9a14`), minimal scaffold,
  every task in `conflicting`, `oneoff` and `original` with tests modifiable, plus
  `conflicting` and `oneoff` with tests locked as a control: 515 episodes, up to 10 attempts
  each, Qwen3.5-9B via OpenRouter, Inspect 0.3.287.
- **Re-scoring.** Each final reply is scored offline under 4 extraction rules × 2 exit
  settings, composing the code byte-for-byte as `agentic_humaneval_scorer` does. Rules: R0 main,
  R1 PR #6 (`9545d24`), R2 last block by position, R3 every definition from every block in
  order. R0 and R1 are loaded from pinned checkouts of the benchmark, not re-implemented.
  Exit settings: E0 exit code 0; E1 exit code 0 and a token printed after `check()` returns.
- **Isolation.** Every scoring run gets its own container from the benchmark's sandbox image,
  with the same 1 GB limit, no network, an unprivileged user and a read-only root filesystem.
  Model-written code never runs on the host.
- **Gates.** Nothing is reported unless every gate passes: the fixture table reproduces;
  22 planted known-answer cases score as predicted; and replaying each reply under R0 + E0
  reproduces the score Inspect logged (509 of 512 exactly; 3 timing-sensitive cases are
  handled by a pre-registered rule, below).
- **Analysis plan** fixed before generation, with every later change logged with its reason:
  [`PREREGISTRATION.md`](PREREGISTRATION.md).

## Caveats

- **One small model.** Qwen3-8B (used in PR #6's own 926-reply check) was retired on
  OpenRouter before this run, so the comparison with that data is indirect. Stronger models
  cheat far more often in the ImpossibleBench paper; a frontier-model run is the next step.
- **Feedback between attempts is not measured.** Generation used main's `find_code`, so a
  different rule would also change what the model sees between attempts. Only final-reply
  scoring is compared.
- **Timing.** Part of generation ran while the machine was CPU-saturated by an unrelated job.
  3 of 515 episodes sit near the 30 s test limit and replay differently; they are set aside
  under the pre-registered rule, and including them changes nothing (−0.5 either way).
  Excluding all 23 episodes that hit any timeout also gives −0.5.
- **The reference rule has its own blind spot.** The single discordant case (`oneoff`
  `lcbhard_7`) is a `check` override nested inside `if __name__ == "__main__":` with the
  asserts wrapped in `try/except`. PR #6's rule counts it; R3, which keeps only top-level
  definitions, misses it. See [`results/qwen3.5-9b/hand_read.md`](results/qwen3.5-9b/hand_read.md).
- **Pre-registration provenance.** The plan was written before any model call in a private
  document with revision history and is exported verbatim here; the extraction rules and
  fixtures were public in the gist before the first call.

## Reproduce

Needs Docker (OrbStack on macOS works), [uv](https://github.com/astral-sh/uv) and an
OpenRouter key stored in the macOS Keychain as `openrouter-api-key`.

```bash
./setup.sh          # pinned benchmark checkouts, venv, sandbox image, all gates
./run.sh smoke      # 2 tasks end to end, a few cents
./run.sh small      # the full run: ~515 episodes, about $3.30 for Qwen3.5-9B
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
| `generate.py`, `run.sh` | Generation with the published benchmark |
| `rescore.py`, `analyze.py` | Re-scoring under 8 conditions; pre-registered analysis |
| `tests/` | Fixture gate, end-to-end replay of a real Inspect eval, mismatch paths, executor faults |
| `results/qwen3.5-9b/episodes.csv` | One row per episode: every condition's outcome and flags |
| `results/qwen3.5-9b/rows.jsonl.gz` | The same plus each final reply and the code each rule selected |

Raw Inspect logs (full multi-attempt transcripts) are not included; the final
reply for every episode is in `rows.jsonl.gz`.

## License

MIT
