"""
APEX HIGH-SIGNAL COMPANIES — Utils Tests
Tests for shared utilities: errors, retry, metrics, persistence, hebbian.
"""

import json
import time
import threading
from pathlib import Path

import pytest

from utils import (
    APEXError, ValidationError, TelemetryError, MeshError,
    retry, MetricsCounter, MetricsRegistry, metrics,
    JSONLStore, HebbianWeight, CircuitBreaker,
)


# ─── Error Types ─────────────────────────────────────────────────────────────

class TestErrorTypes:
    """Tests for structured error types."""

    def test_base_error(self):
        err = APEXError("test error", module="test", code="E001", details={"key": "val"})
        assert str(err) == "test error"
        assert err.module == "test"
        assert err.code == "E001"
        assert err.details == {"key": "val"}
        d = err.to_dict()
        assert d["error"] == "APEXError"
        assert d["module"] == "test"

    def test_validation_error(self):
        err = ValidationError("invalid input", module="config")
        assert isinstance(err, APEXError)
        assert err.module == "config"

    def test_telemetry_error(self):
        err = TelemetryError("packet decode failed", module="nasa")
        assert isinstance(err, APEXError)

    def test_mesh_error(self):
        err = MeshError("handover failed", module="constellation")
        assert isinstance(err, APEXError)

    def test_error_inheritance(self):
        errors = [ValidationError, TelemetryError, MeshError]
        for err_cls in errors:
            assert issubclass(err_cls, APEXError)


# ─── Retry Pattern ───────────────────────────────────────────────────────────

class TestRetry:
    """Tests for retry decorator."""

    def test_retry_succeeds_first_try(self):
        call_count = 0

        @retry(max_attempts=3, backoff=0.01)
        def succeed_first():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = succeed_first()
        assert result == "ok"
        assert call_count == 1

    def test_retry_succeeds_after_failures(self):
        call_count = 0

        @retry(max_attempts=3, backoff=0.01)
        def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("not yet")
            return "ok"

        result = fail_twice()
        assert result == "ok"
        assert call_count == 3

    def test_retry_exhausted(self):
        @retry(max_attempts=2, backoff=0.01)
        def always_fail():
            raise ValueError("always")

        with pytest.raises(ValueError):
            always_fail()

    def test_retry_specific_exceptions(self):
        call_count = 0

        @retry(max_attempts=3, backoff=0.01, exceptions=(ValueError,))
        def fail_type():
            nonlocal call_count
            call_count += 1
            raise TypeError("wrong type")

        with pytest.raises(TypeError):
            fail_type()
        assert call_count == 1  # Not retried


# ─── Metrics Counters ────────────────────────────────────────────────────────

class TestMetrics:
    """Tests for metrics counters."""

    def test_counter_inc(self):
        c = MetricsCounter("test")
        c.inc("requests")
        c.inc("requests")
        assert c.get("requests") == 2

    def test_counter_dec(self):
        c = MetricsCounter("test")
        c.inc("active", 5)
        c.dec("active", 2)
        assert c.get("active") == 3

    def test_counter_set(self):
        c = MetricsCounter("test")
        c.set("gauge", 42)
        assert c.get("gauge") == 42

    def test_counter_snapshot(self):
        c = MetricsCounter("test")
        c.inc("requests")
        snap = c.snapshot()
        assert snap["name"] == "test"
        assert snap["counts"]["requests"] == 1

    def test_counter_reset(self):
        c = MetricsCounter("test")
        c.inc("requests")
        c.reset()
        assert c.get("requests") == 0

    def test_counter_thread_safe(self):
        c = MetricsCounter("test")
        def inc_many():
            for _ in range(100):
                c.inc("counter")

        threads = [threading.Thread(target=inc_many) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert c.get("counter") == 1000

    def test_registry(self):
        reg = MetricsRegistry()
        c1 = reg.counter("requests")
        c2 = reg.counter("requests")
        assert c1 is c2
        c1.inc("ok")
        snap = reg.snapshot()
        assert "requests" in snap


# ─── JSONL Persistence ───────────────────────────────────────────────────────

class TestJSONLStore:
    """Tests for JSONL persistence."""

    def test_append_and_read(self, tmp_path):
        store = JSONLStore(tmp_path / "test.jsonl")
        store.append({"ts": 1, "event": "start"})
        store.append({"ts": 2, "event": "end"})
        records = store.read_all()
        assert len(records) == 2
        assert records[0]["event"] == "start"

    def test_read_last(self, tmp_path):
        store = JSONLStore(tmp_path / "test.jsonl")
        for i in range(10):
            store.append({"i": i})
        last = store.read_last(3)
        assert len(last) == 3
        assert last[0]["i"] == 7

    def test_count(self, tmp_path):
        store = JSONLStore(tmp_path / "test.jsonl")
        assert store.count() == 0
        store.append({"a": 1})
        store.append({"a": 2})
        assert store.count() == 2

    def test_clear(self, tmp_path):
        store = JSONLStore(tmp_path / "test.jsonl")
        store.append({"a": 1})
        store.clear()
        assert store.count() == 0

    def test_empty_store(self, tmp_path):
        store = JSONLStore(tmp_path / "empty.jsonl")
        assert store.read_all() == []
        assert store.read_last(5) == []

    def test_thread_safe(self, tmp_path):
        store = JSONLStore(tmp_path / "test.jsonl")
        def append_many():
            for _ in range(100):
                store.append({"thread": threading.current_thread().name})

        threads = [threading.Thread(target=append_many) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert store.count() == 500


# ─── Hebbian Weight ──────────────────────────────────────────────────────────

class TestHebbianWeight:
    """Tests for Hebbian weight."""

    def test_initial_value(self):
        hw = HebbianWeight(initial=0.5)
        assert hw.value == 0.5

    def test_reward_bounded(self):
        hw = HebbianWeight(initial=0.9, eta=0.2, max_bound=1.0)
        hw.reward()
        assert hw.value <= 1.0

    def test_penalty_bounded(self):
        hw = HebbianWeight(initial=0.1, eta=0.2, min_bound=0.0)
        hw.penalty()
        assert hw.value >= 0.0

    def test_reward_increases(self):
        hw = HebbianWeight(initial=0.5, gamma=1.0, eta=0.1)
        hw.reward()
        assert hw.value > 0.5

    def test_penalty_decreases(self):
        hw = HebbianWeight(initial=0.5, eta=0.1)
        hw.penalty()
        assert hw.value < 0.5

    def test_to_dict(self):
        hw = HebbianWeight(initial=0.7)
        d = hw.to_dict()
        assert d["weight"] == 0.7
        assert d["gamma"] == 0.95


# ─── Circuit Breaker ─────────────────────────────────────────────────────────

class TestCircuitBreaker:
    """Tests for circuit breaker."""

    def test_closed_by_default(self):
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.allow_request("link-1")
        assert cb.get_state("link-1") == "closed"

    def test_opens_after_failures(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure("link-1")
        assert not cb.allow_request("link-1")
        assert cb.get_state("link-1") == "open"

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.01)
        for _ in range(3):
            cb.record_failure("link-1")
        time.sleep(0.02)
        assert cb.allow_request("link-1")
        assert cb.get_state("link-1") == "half_open"

    def test_resets_on_success(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure("link-1")
        cb.record_success("link-1")
        assert cb.allow_request("link-1")
        assert cb.get_state("link-1") == "closed"

    def test_reset_method(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure("link-1")
        cb.reset("link-1")
        assert cb.allow_request("link-1")

    def test_independent_keys(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure("link-1")
        assert not cb.allow_request("link-1")
        assert cb.allow_request("link-2")
