"""
APEX HIGH-SIGNAL COMPANIES — Shared Utilities
Structured error types, retry patterns, metrics counters, and common helpers.
"""

from __future__ import annotations

import json
import logging
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar, cast


logger = logging.getLogger(__name__)


# ─── Structured Error Types ──────────────────────────────────────────────────

class APEXError(Exception):
    """Base exception for all APEX modules."""

    def __init__(self, message: str, module: str = "", code: str = "", details: Optional[Dict] = None) -> None:
        super().__init__(message)
        self.module = module
        self.code = code
        self.details = details or {}
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": self.__class__.__name__,
            "message": str(self),
            "module": self.module,
            "code": self.code,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class ValidationError(APEXError):
    """Input validation failed."""
    pass


class TelemetryError(APEXError):
    """Telemetry processing failed."""
    pass


class MeshError(APEXError):
    """Constellation mesh operation failed."""
    pass


class PlacementError(APEXError):
    """GPU placement failed."""
    pass


class VerificationError(APEXError):
    """Verification pipeline failed."""
    pass


class SignalError(APEXError):
    """Signal processing failed."""
    pass


class ComplianceError(APEXError):
    """Compliance check failed."""
    pass


class SwarmError(APEXError):
    """Swarm operation failed."""
    pass


# ─── Retry Pattern ───────────────────────────────────────────────────────────

F = TypeVar("F", bound=Callable[..., Any])


def retry(
    max_attempts: int = 3,
    backoff: float = 1.0,
    exceptions: tuple = (Exception,),
    logger_name: str = "retry",
) -> Callable[[F], F]:
    """Decorator with exponential backoff retry logic.

    Args:
        max_attempts: Maximum number of retry attempts.
        backoff: Initial backoff time in seconds (doubles each attempt).
        exceptions: Tuple of exceptions to catch and retry.
        logger_name: Logger name for retry logging.
    """
    log = logging.getLogger(logger_name)

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[Exception] = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        sleep_time = backoff * (2 ** attempt)
                        log.warning(
                            "Retry %d/%d for %s after %.1fs: %s",
                            attempt + 1, max_attempts, func.__name__, sleep_time, e,
                        )
                        time.sleep(sleep_time)
                    else:
                        log.error(
                            "All %d attempts failed for %s: %s",
                            max_attempts, func.__name__, e,
                        )
            raise last_exception  # type: ignore[misc]
        return cast(F, wrapper)
    return decorator


# ─── Metrics Counters ────────────────────────────────────────────────────────

class MetricsCounter:
    """Thread-safe metrics counter for production observability."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._counts: Dict[str, int] = {}
        self._timers: Dict[str, float] = {}
        self._lock = threading.Lock()

    def inc(self, key: str, value: int = 1) -> None:
        """Increment a counter."""
        with self._lock:
            self._counts[key] = self._counts.get(key, 0) + value

    def dec(self, key: str, value: int = 1) -> None:
        """Decrement a counter."""
        with self._lock:
            self._counts[key] = self._counts.get(key, 0) - value

    def set(self, key: str, value: int) -> None:
        """Set a counter to a specific value."""
        with self._lock:
            self._counts[key] = value

    def get(self, key: str, default: int = 0) -> int:
        """Get a counter value."""
        with self._lock:
            return self._counts.get(key, default)

    def timer_start(self, key: str) -> None:
        """Start a timer."""
        with self._lock:
            self._timers[key] = time.monotonic()

    def timer_stop(self, key: str) -> float:
        """Stop a timer and return elapsed seconds."""
        with self._lock:
            start = self._timers.pop(key, time.monotonic())
            return time.monotonic() - start

    def reset(self) -> None:
        """Reset all counters."""
        with self._lock:
            self._counts.clear()
            self._timers.clear()

    def snapshot(self) -> Dict[str, Any]:
        """Get a snapshot of all metrics."""
        with self._lock:
            return {
                "name": self.name,
                "counts": dict(self._counts),
                "active_timers": list(self._timers.keys()),
            }

    def to_json(self) -> str:
        """Serialize metrics to JSON."""
        return json.dumps(self.snapshot(), indent=2)


class MetricsRegistry:
    """Global metrics registry for all modules."""

    def __init__(self) -> None:
        self._counters: Dict[str, MetricsCounter] = {}
        self._lock = threading.Lock()

    def counter(self, name: str) -> MetricsCounter:
        """Get or create a named counter."""
        with self._lock:
            if name not in self._counters:
                self._counters[name] = MetricsCounter(name)
            return self._counters[name]

    def snapshot(self) -> Dict[str, Any]:
        """Get snapshot of all counters."""
        with self._lock:
            return {name: c.snapshot() for name, c in self._counters.items()}

    def reset(self) -> None:
        """Reset all counters."""
        with self._lock:
            for c in self._counters.values():
                c.reset()


# Global metrics instance
metrics = MetricsRegistry()


# ─── JSONL Persistence ───────────────────────────────────────────────────────

class JSONLStore:
    """Append-only JSONL store for state persistence."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, record: Dict[str, Any]) -> None:
        """Append a record to the store."""
        with self._lock:
            with open(self.path, "a") as f:
                f.write(json.dumps(record, separators=(",", ":")) + "\n")

    def read_all(self) -> List[Dict[str, Any]]:
        """Read all records from the store."""
        if not self.path.exists():
            return []
        records = []
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def read_last(self, n: int = 1) -> List[Dict[str, Any]]:
        """Read last n records."""
        all_records = self.read_all()
        return all_records[-n:]

    def clear(self) -> None:
        """Clear the store."""
        with self._lock:
            if self.path.exists():
                self.path.write_text("")

    def count(self) -> int:
        """Count records in the store."""
        if not self.path.exists():
            return 0
        with open(self.path) as f:
            return sum(1 for line in f if line.strip())


# ─── Hebbian Weight ──────────────────────────────────────────────────────────

class HebbianWeight:
    """Thread-safe Hebbian weight with bounds checking."""

    def __init__(
        self,
        initial: float = 1.0,
        gamma: float = 0.95,
        eta: float = 0.10,
        min_bound: float = 0.0,
        max_bound: float = 2.0,
    ) -> None:
        self._weight = initial
        self.gamma = gamma
        self.eta = eta
        self.min_bound = min_bound
        self.max_bound = max_bound
        self._lock = threading.Lock()

    @property
    def value(self) -> float:
        with self._lock:
            return self._weight

    def reward(self) -> float:
        """Apply Hebbian reward (reinforcement)."""
        with self._lock:
            self._weight = min(self.max_bound, self._weight + self.eta)
            self._weight = max(self.min_bound, self._weight * self.gamma)
            return self._weight

    def penalty(self) -> float:
        """Apply Hebbian penalty (decay)."""
        with self._lock:
            self._weight = max(self.min_bound, self._weight - self.eta)
            return self._weight

    def to_dict(self) -> Dict[str, Any]:
        return {
            "weight": self.value,
            "gamma": self.gamma,
            "eta": self.eta,
            "bounds": [self.min_bound, self.max_bound],
        }


# ─── Circuit Breaker ─────────────────────────────────────────────────────────

class CircuitBreaker:
    """Thread-safe circuit breaker for fault tolerance."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max: int = 1,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max
        self._state: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _get_state(self, key: str) -> Dict[str, Any]:
        if key not in self._state:
            self._state[key] = {
                "failures": 0,
                "state": "closed",
                "last_failure": 0.0,
                "half_open_count": 0,
            }
        return self._state[key]

    def record_failure(self, key: str) -> None:
        with self._lock:
            state = self._get_state(key)
            state["failures"] += 1
            state["last_failure"] = time.time()
            if state["failures"] >= self.failure_threshold:
                state["state"] = "open"

    def record_success(self, key: str) -> None:
        with self._lock:
            state = self._get_state(key)
            state["failures"] = 0
            state["state"] = "closed"

    def allow_request(self, key: str) -> bool:
        with self._lock:
            state = self._get_state(key)
            if state["state"] == "closed":
                return True
            if state["state"] == "open":
                elapsed = time.time() - state["last_failure"]
                if elapsed >= self.recovery_timeout:
                    state["state"] = "half_open"
                    state["half_open_count"] = 0
                    return True
                return False
            # half_open
            if state["half_open_count"] < self.half_open_max:
                state["half_open_count"] += 1
                return True
            return False

    def get_state(self, key: str) -> str:
        with self._lock:
            return self._get_state(key)["state"]

    def reset(self, key: str) -> None:
        with self._lock:
            if key in self._state:
                del self._state[key]
