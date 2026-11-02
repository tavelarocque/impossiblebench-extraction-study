"""Run composed scoring scripts in isolation.

Docker mode gives every scoring job its own fresh container from the image the
benchmark's sandbox uses (aisiuk/inspect-tool-support), with the same 1 GB
memory limit as the repo's compose.yaml, no network, an unprivileged user and a
read-only root filesystem. One container per job mirrors the benchmark, where
each episode had its own 1 GB sandbox: a job that exhausts memory fails alone,
exactly as it would there, instead of taking other jobs down with it.

Model-written code never runs on the host. Local mode exists only for the
harness's own tests, which execute fixtures written by us; rescore.py refuses it
for real logs.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

IMAGE = "aisiuk/inspect-tool-support"
TIMEOUT = 30  # VERIFY_TIMEOUT in livecodebench_scorers.py
MEMORY = "1g"  # mem_limit in the repo's compose.yaml
HOST_TIMEOUT = TIMEOUT + 120  # outer guard on the container runtime itself
RETRIES = 3

# Runs inside the container (or locally in tests): one job, 30 s limit, as the scorer does.
RUNNER = r'''
import json, os, subprocess, sys, tempfile
job = json.load(open(sys.argv[1]))
timeout = int(sys.argv[3])
py = sys.executable if os.environ.get("IBSTUDY_LOCAL") else "python"
with tempfile.TemporaryDirectory() as d:
    try:
        r = subprocess.run([py, "-c", job["code"]], cwd=d, capture_output=True, text=True,
                           timeout=timeout, start_new_session=True)
        res = {"id": job["id"], "rc": r.returncode, "stdout": r.stdout[-4000:],
               "stderr": r.stderr[-4000:], "timeout": False}
    except subprocess.TimeoutExpired:
        res = {"id": job["id"], "rc": None, "stdout": "", "stderr": "timeout", "timeout": True}
json.dump(res, open(sys.argv[2], "w"))
'''


class InfraError(RuntimeError):
    """The executor itself failed (not the job): never scored, never cached."""


def _attempt(job: dict, mode: str) -> dict:
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "runner.py").write_text(RUNNER)
        (d / "job.json").write_text(json.dumps(job))
        out = d / "out"
        out.mkdir()
        os.chmod(out, 0o777)
        for f in ("runner.py", "job.json"):
            os.chmod(d / f, 0o644)
        name = "ibstudy-" + uuid.uuid4().hex[:12]
        if mode == "docker":
            cmd = ["docker", "run", "--rm", "--name", name, "--network", "none", "--memory", MEMORY,
                   "--pids-limit", "512", "--user", "65534:65534",
                   "--read-only", "--tmpfs", "/tmp:rw,size=512m", "-e", "HOME=/tmp",
                   "-v", f"{d}/runner.py:/in/runner.py:ro", "-v", f"{d}/job.json:/in/job.json:ro",
                   "-v", f"{out}:/out:rw",
                   IMAGE, "python", "/in/runner.py", "/in/job.json", "/out/result.json", str(TIMEOUT)]
            env = None
        elif mode == "local":
            cmd = [sys.executable, str(d / "runner.py"), str(d / "job.json"),
                   str(out / "result.json"), str(TIMEOUT)]
            env = {**os.environ, "IBSTUDY_LOCAL": "1"}
        else:
            raise ValueError(mode)
        try:
            p = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=HOST_TIMEOUT)
        except subprocess.TimeoutExpired:
            # The job itself is limited to 30 s inside the container, so this is the container
            # runtime stalling (e.g. the machine slept or changed network): an infrastructure fault.
            if mode == "docker":
                subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=60)
            raise InfraError(f"{job['id']}: container did not finish within {HOST_TIMEOUT} s")
        result = out / "result.json"
        if result.exists():
            return json.loads(result.read_text())
        # The container itself died (e.g. the job exhausted its 1 GB): a failed run, as in the
        # benchmark's sandbox. Anything else is an infrastructure fault and must not be scored.
        if mode == "docker" and p.returncode == 137:
            return {"id": job["id"], "rc": 137, "stdout": "", "stderr": "container killed (memory limit)",
                    "timeout": False}
        raise InfraError(f"{job['id']}: rc={p.returncode} {p.stderr[-500:]}")


def _run_one(job: dict, mode: str, cache_dir: Path | None) -> dict:
    cached = cache_dir / (job["id"].replace(":", "_") + ".json") if cache_dir else None
    if cached and cached.exists():
        return json.loads(cached.read_text())
    for attempt in range(1, RETRIES + 1):
        try:
            res = _attempt(job, mode)
            break
        except InfraError as e:
            print(f"  infrastructure fault (attempt {attempt}/{RETRIES}), retrying: {e}", flush=True)
            if attempt == RETRIES:
                raise
            time.sleep(10 * attempt)
    if cached:
        tmp = cached.with_suffix(".tmp")
        tmp.write_text(json.dumps(res))
        tmp.replace(cached)  # atomic: a crash never leaves a half-written result
    return res


def run_jobs(jobs: list[dict], mode: str = "docker", workers: int = 6,
             cache_dir: Path | None = None) -> dict[str, dict]:
    """jobs: [{"id": str, "code": str}] -> {id: {"rc", "stdout", "stderr", "timeout"}}

    With cache_dir, each finished job's result is saved under its id (a hash of its code),
    so an interrupted run resumes without re-running finished jobs.
    """
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        have = sum((cache_dir / (j["id"].replace(":", "_") + ".json")).exists() for j in jobs)
        if have:
            print(f"  resuming: {have}/{len(jobs)} results already cached", flush=True)
    done = 0
    results = {}
    with ThreadPoolExecutor(workers) as ex:
        for r in ex.map(lambda j: _run_one(j, mode, cache_dir), jobs):
            results[r["id"]] = r
            done += 1
            if done % 250 == 0 or done == len(jobs):
                print(f"  scored {done}/{len(jobs)}", flush=True)
    return results
