"""Detailed tests for resilience policy internals (circuit breaking, pruning, etc.)."""

import time
import threading
from unittest.mock import MagicMock, patch

import pytest

from exegesis.infrastructure.api.app.adapters import resilience as resilience_adapter
from exegesis.infrastructure.api.app.adapters.resilience import (
    CircuitBreakerResiliencePolicy,
    _CircuitState,
    _categorise_exception,
)
from exegesis.application.core.resilience import ResilienceSettings, ResilienceError


class TestResilienceInternals:

    @pytest.fixture(autouse=True)
    def clear_circuit_state(self):
        CircuitBreakerResiliencePolicy._circuit_states.clear()
        yield
        CircuitBreakerResiliencePolicy._circuit_states.clear()

    def test_categorise_exception_unknown(self):
        """Verify fallback for unknown exceptions."""
        exc = ValueError("Something unexpected")
        assert _categorise_exception(exc) == "unknown"

    def test_circuit_reset_after_timeout(self):
        """Verify circuit closes (resets) after breaker_reset_seconds passes."""
        settings = ResilienceSettings(
            max_attempts=1,
            breaker_threshold=1,
            breaker_reset_seconds=10
        )
        policy = CircuitBreakerResiliencePolicy(settings)
        key = "test_circuit"

        # 1. Trip the circuit
        with pytest.raises(ResilienceError):
            policy.run(lambda: (_ for _ in ()).throw(ConnectionError("Fail")), key=key, classification="test")

        # Verify it's open
        state = CircuitBreakerResiliencePolicy._circuit_states[key]
        assert state.opened_at is not None

        # 2. Fast forward time to BEFORE reset
        with patch("time.monotonic", return_value=state.opened_at + 5):
            with pytest.raises(ResilienceError) as exc:
                policy.run(lambda: "ok", key=key, classification="test")
            assert exc.value.metadata.category == "circuit_open"

        # 3. Fast forward time to AFTER reset
        future_time = state.opened_at + 15
        with patch("time.monotonic", return_value=future_time):
            # Should succeed now (circuit closes on check)
            result, _ = policy.run(lambda: "success", key=key, classification="test")
            assert result == "success"

            # State should be reset
            state = CircuitBreakerResiliencePolicy._circuit_states[key]
            assert state.opened_at is None
            assert state.failures == 0

    def test_pruning_stale_entries(self):
        """Verify that stale entries (TTL expired) are removed."""
        policy = CircuitBreakerResiliencePolicy()

        # Inject a stale state
        now = time.monotonic()
        stale_key = "stale_key"
        active_key = "active_key"

        # Directly manipulate the shared state for test setup
        # Stale: Last touched > 1 hour ago
        CircuitBreakerResiliencePolicy._circuit_states[stale_key] = _CircuitState(
            last_touched=now - 4000  # > 3600 seconds
        )
        # Active: Last touched just now
        CircuitBreakerResiliencePolicy._circuit_states[active_key] = _CircuitState(
            last_touched=now
        )

        # Trigger pruning
        policy._check_circuit("any_key", now)

        states = CircuitBreakerResiliencePolicy._circuit_states
        assert active_key in states
        assert stale_key not in states

    def test_pruning_lru_behavior(self):
        """Verify that when capacity is reached, oldest untouched healthy entries are removed."""
        policy = CircuitBreakerResiliencePolicy()
        # Reduce capacity for testing
        policy._max_circuit_entries = 3

        now = 1000.0

        # Add 4 entries to force over-capacity before the check
        # "oldest" should be evicted if it's healthy
        states = CircuitBreakerResiliencePolicy._circuit_states
        states["k1"] = _CircuitState(last_touched=now - 100)
        states["k2"] = _CircuitState(last_touched=now - 50)
        states["k3"] = _CircuitState(last_touched=now - 10)
        states["k4"] = _CircuitState(last_touched=now - 5)

        # Now len=4, max=3. Excess=1.
        # Trigger pruning via check_circuit for a new key "k5"
        policy._check_circuit("k5", now)

        # k1 should be gone (oldest)
        assert "k1" not in states
        assert "k2" in states
        assert "k3" in states
        assert "k4" in states
        assert "k5" in states

    def test_pruning_protects_open_circuits(self):
        """Open circuits should NOT be pruned even if they are the 'oldest' candidates."""
        policy = CircuitBreakerResiliencePolicy()
        policy._max_circuit_entries = 2

        now = 1000.0
        states = CircuitBreakerResiliencePolicy._circuit_states

        # k1 is old but OPEN
        states["k1"] = _CircuitState(last_touched=now - 100, opened_at=now - 50, failures=5)
        # k2 is newer and healthy
        states["k2"] = _CircuitState(last_touched=now - 10)
        # k3 is also healthy (to create excess)
        states["k3"] = _CircuitState(last_touched=now - 5)

        # len=3, max=2. Excess=1.
        # Trigger access for k4
        policy._check_circuit("k4", now)

        # Sorted by last_touched: k1 (oldest), k2, k3.
        # k1 is skipped because opened_at is not None.
        # k2 is healthy -> removed.

        assert "k1" in states
        assert "k2" not in states
        assert "k3" in states
        assert "k4" in states

    def test_thread_safety_sanity_check(self):
        """Concurrent access shouldn't corrupt the state dict (basic smoke test)."""
        policy = CircuitBreakerResiliencePolicy()
        errors = []

        def worker(i):
            try:
                policy.run(lambda: "ok", key=f"key_{i}", classification="test")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads: t.start()
        for t in threads: t.join()

        assert len(errors) == 0
        # We expect 50 entries (or max capacity)
        assert len(CircuitBreakerResiliencePolicy._circuit_states) <= 512

