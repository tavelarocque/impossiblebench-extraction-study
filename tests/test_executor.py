"""Executor robustness: stalled runs are retried then reported, never scored; results resume from cache."""

from __future__ import annotations

import pytest

import executor


def test_stall_is_retried_then_raised_and_not_cached(tmp_path, monkeypatch):
    # The runner never finishes within the outer guard: stands in for a stalled container runtime.
    monkeypatch.setattr(executor, "HOST_TIMEOUT", 2)
    monkeypatch.setattr(executor, "RETRIES", 2)
    monkeypatch.setattr(executor.time, "sleep", lambda s: None)
    job = {"id": "code:stall", "code": "import time; time.sleep(10)"}
    with pytest.raises(executor.InfraError):
        executor.run_jobs([job], mode="local", cache_dir=tmp_path / "cache")
    assert not list((tmp_path / "cache").glob("*.json")), "an infrastructure fault must never be cached"


def test_cached_results_are_reused_without_rerunning(tmp_path):
    cache = tmp_path / "cache"
    first = executor.run_jobs([{"id": "code:a", "code": "print('first')"}], mode="local", cache_dir=cache)
    assert first["code:a"]["rc"] == 0 and "first" in first["code:a"]["stdout"]
    # Same id, code that would fail if it ran: the cached result must come back unchanged.
    again = executor.run_jobs([{"id": "code:a", "code": "raise SystemExit(9)"}], mode="local", cache_dir=cache)
    assert again["code:a"] == first["code:a"]


def test_job_failures_are_results_not_faults(tmp_path):
    r = executor.run_jobs([{"id": "code:x", "code": "raise SystemExit(3)"}], mode="local", cache_dir=tmp_path / "c")
    assert r["code:x"]["rc"] == 3 and r["code:x"]["timeout"] is False
