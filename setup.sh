#!/usr/bin/env bash
# One-time setup on the run machine. Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")"

command -v docker >/dev/null || { echo "Docker not found. Install OrbStack first."; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker isn't running. Open OrbStack, then re-run."; exit 1; }
command -v uv >/dev/null || { echo "uv not found: brew install uv"; exit 1; }

echo "== pinned benchmark checkouts"
mkdir -p repos
[ -d repos/src/.git ] || git clone --quiet https://github.com/safety-research/impossiblebench repos/src
git -C repos/src fetch --quiet origin main pull/6/head
[ -d repos/main ] || git -C repos/src worktree add --quiet --detach ../main d4f9a14
[ -d repos/pr6 ] || git -C repos/src worktree add --quiet --detach ../pr6 9545d24
echo "main=$(git -C repos/main rev-parse --short=7 HEAD) pr6=$(git -C repos/pr6 rev-parse --short=7 HEAD)"

echo "== python environment"
[ -x .venv/bin/python ] || uv venv --quiet --python 3.12 .venv
uv pip install --quiet --python .venv/bin/python "inspect_ai==0.3.287" openai datasets pytest

echo "== sandbox image (same one the benchmark uses)"
docker pull --quiet aisiuk/inspect-tool-support

echo "== gates: fixture table, end-to-end replay, planted cases"
.venv/bin/python -m pytest -q tests/

echo "== docker executor check (network blocked, per-job memory limit, isolation)"
.venv/bin/python - <<'EOF'
from executor import run_jobs
r = run_jobs([{"id": "ok", "code": "print('sandbox ok')"},
              {"id": "net", "code": "import socket; socket.create_connection(('1.1.1.1', 53), 2)"},
              {"id": "mem", "code": "x = bytearray(3 * 1024**3); print('allocated')"},
              {"id": "ok2", "code": "print('still ok')"}], mode="docker")
assert r["ok"]["rc"] == 0 and "sandbox ok" in r["ok"]["stdout"], r["ok"]
assert r["net"]["rc"] != 0, "network should be blocked inside the scoring sandbox"
assert r["mem"]["rc"] != 0 and "allocated" not in r["mem"]["stdout"], ("3 GB should exceed the 1 GB limit", r["mem"])
assert r["ok2"]["rc"] == 0, "a job exhausting memory must not affect other jobs"
print("docker executor ok: network blocked, 1 GB limit enforced per job, jobs isolated")
EOF

echo
echo "SETUP COMPLETE. Next: ./run.sh smoke"
