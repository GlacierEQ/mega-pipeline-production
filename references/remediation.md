# Production Readiness Remediation Templates

## Dimension 1: Tests

```python
# tests/test_<module>.py
import pytest
from hypothesis import given, strategies as st

# Unit test pattern
class TestCoreFunction:
    def test_basic_operation(self):
        result = core_function(input)
        assert result is not None
        assert result.status == "expected"

    def test_edge_case_empty(self):
        with pytest.raises(ValueError):
            core_function(empty_input)

# Property-based test pattern (Hypothesis)
@given(st.lists(st.floats(), min_size=1, max_size=100))
def test_sort_is_idempotent(lst):
    assert sort_function(lst) == sort_function(sort_function(lst))
```

## Dimension 2: Config

```python
# config.py or pyproject.toml
from dataclasses import dataclass

@dataclass(frozen=True)
class EngineConfig:
    max_buffer_size: int = 100_000
    sigma_threshold: float = 3.0
    gamma: float = 0.95
    eta: float = 0.10

# Usage
DEFAULT_CONFIG = EngineConfig()

# TOML alternative
# [tool.my_module]
# max_buffer_size = 100000
# sigma_threshold = 3.0
```

## Dimension 3: Telemetry

```python
import logging
import sys

logger = logging.getLogger(__name__)

# Structured logging setup
def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        '{"ts":"%(asctime)s","level":"%(levelname)s","module":"%(name)s","msg":"%(message)s"}'
    ))
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level))

# Usage
logger.info("Processing started", extra={"count": len(items)})
logger.warning("Threshold exceeded", extra={"value": val, "threshold": max_val})
```

## Dimension 4: Persistence

```python
import json
import time
from pathlib import Path

class StateManager:
    def __init__(self, state_dir: str = ".state"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True)

    def save_snapshot(self, data: dict, name: str = "latest") -> Path:
        path = self.state_dir / f"{name}_{int(time.time())}.jsonl"
        with open(path, "w") as f:
            json.dump(data, f, separators=(",", ":"))
        return path

    def load_latest(self, name: str = "latest") -> dict:
        snapshots = sorted(self.state_dir.glob(f"{name}_*.jsonl"))
        if not snapshots:
            return {}
        with open(snapshots[-1]) as f:
            return json.load(f)
```

## Dimension 5: API Surface

```python
class PublicAPI:
    """Public interface for external consumers.

    This class exposes the stable API for programmatic access.
    All methods are documented and versioned.
    """

    def process(self, input_data: str) -> dict:
        """Process input data and return structured result.

        Args:
            input_data: Raw input string to process.

        Returns:
            dict with keys: status, result, metadata.

        Raises:
            ValueError: If input_data is empty or invalid.
        """
        if not input_data:
            raise ValueError("input_data cannot be empty")
        # ... implementation
```

## Dimension 6: Error Recovery

```python
import time
from functools import wraps

def retry(max_attempts: int = 3, backoff: float = 1.0):
    """Decorator with exponential backoff retry logic."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        time.sleep(backoff * (2 ** attempt))
            raise last_exception
        return wrapper
    return decorator

# Usage
@retry(max_attempts=3, backoff=0.5)
def risky_operation():
    # ... may fail
    pass
```

## Dimension 7: Integration

```python
# integration/test_pipeline.py
from module_a import ComponentA
from module_b import ComponentB

def test_a_feeds_b():
    a = ComponentA()
    b = ComponentB()
    output_a = a.process("test")
    result = b.consume(output_a)
    assert result is not None
    assert result.status == "processed"
```
