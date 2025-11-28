import itertools
import multiprocessing as mp
from collections.abc import Callable
from pathlib import Path

from unittest.mock import Mock
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import sys


import pytest

from exegesis.application.ports.ai_registry import GenerationError
from exegesis.infrastructure.api.app.research.ai.ledger import CacheRecord, SharedLedger
from exegesis.infrastructure.api.app.research.ai.registry import LLMModel, LLMRegistry
from exegesis.infrastructure.api.app.research.ai.router import (
    LLMRouterService,
    RoutedGeneration,
    reset_router_state,
)
from exegesis.infrastructure.api.app.research.ai import router as router_module


@pytest.fixture(autouse=True)
def _reset_router_state(monkeypatch):
    # Set shorter timeout for tests to avoid hanging
    monkeypatch.setenv("EXEGESIS_ROUTER_INFLIGHT_TIMEOUT", "10.0")
    reset_router_state()
    yield
    reset_router_state()


def _run_generation(router: LLMRouterService, workflow: str = "chat"):
    for candidate in router.iter_candidates(workflow):
        try:
            return router.execute_generation(
                workflow=workflow,
                model=candidate,
                prompt="hello",
            )
        except GenerationError:
            continue
    raise AssertionError("router failed to produce a generation")


@pytest.fixture
def sleep_stub() -> Callable[[float], bool]:
    """Return a ``threading.Event.wait`` stub for injectable sleep."""

    waiter = threading.Event()
    waiter.set()
    return waiter.wait


def _wait_until(
    predicate: Callable[[], bool], *, timeout: float = 1.0, interval: float = 0.001,
    sleep_fn: Callable[[float], bool | None] | None = None,
) -> None:
    """Spin until ``predicate`` evaluates truthy or raise after ``timeout``."""

    sleeper = time.sleep if sleep_fn is None else sleep_fn
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if predicate():
            return
        sleeper(interval)
    raise AssertionError("timed out waiting for condition")


def _wait_for_inflight_status(
    ledger: SharedLedger,
    cache_key: str,
    status: str,
    *,
    timeout: float = 1.0,
    sleep_fn: Callable[[float], bool | None] | None = None,
) -> None:
    """Block until an inflight row reaches the requested ``status``."""

    def _predicate() -> bool:
        with ledger.transaction() as txn:
            row = txn.get_inflight(cache_key)
        return row is not None and row.status == status

    _wait_until(_predicate, timeout=timeout, sleep_fn=sleep_fn)


def _wait_for_inflight_absence(
    ledger: SharedLedger,
    cache_key: str,
    *,
    timeout: float = 1.0,
    sleep_fn: Callable[[float], bool | None] | None = None,
) -> None:
    """Block until no inflight row exists for ``cache_key``."""

    def _predicate() -> bool:
        with ledger.transaction() as txn:
            return txn.get_inflight(cache_key) is None

    _wait_until(_predicate, timeout=timeout, sleep_fn=sleep_fn)


def _wait_for_wal_cleanup(
    path: Path | str,
    *,
    timeout: float = 1.0,
    sleep_fn: Callable[[float], bool | None] | None = None,
) -> None:
    """Wait until SQLite WAL/shm sidecar files disappear."""

    base = Path(path)
    candidates = [base.with_name(base.name + suffix) for suffix in ("-wal", "-shm")]

    def _missing_all() -> bool:
        return all(not candidate.exists() for candidate in candidates)

    _wait_until(_missing_all, timeout=timeout, sleep_fn=sleep_fn)


def _process_budget_run(ledger_path: str, result_queue: mp.Queue) -> None:
    registry = LLMRegistry()
    registry.add_model(
        LLMModel(
            name="primary",
            provider="echo",
            model="echo",
            config={"suffix": "[primary]"},
            pricing={"per_call": 0.6},
            routing={"spend_ceiling": 1.0, "weight": 10.0},
        ),
        make_default=True,
    )
    registry.add_model(
        LLMModel(
            name="backup",
            provider="echo",
            model="echo",
            config={"suffix": "[backup]"},
            pricing={"per_call": 0.4},
            routing={"weight": 1.0},
        )
    )
    router = LLMRouterService(registry, ledger=SharedLedger(ledger_path))
    result = _run_generation(router)
    result_queue.put(
        {
            "model": result.model.name,
            "primary_spend": router.get_spend("primary"),
            "backup_spend": router.get_spend("backup"),
        }
    )


def _process_latency_run(
    ledger_path: str,
    result_queue: mp.Queue,
    *,
    delay: float,
    sleep_fn: Callable[[float], bool | None] | None = None,
) -> None:
    registry = LLMRegistry()
    registry.add_model(
        LLMModel(
            name="slow",
            provider="echo",
            model="echo",
            config={"suffix": "[slow]"},
            routing={"latency_threshold_ms": 30.0, "weight": 5.0},
        ),
        make_default=True,
    )
    registry.add_model(
        LLMModel(
            name="fast",
            provider="echo",
            model="echo",
            config={"suffix": "[fast]"},
            routing={"weight": 1.0},
        )
    )

    slow_calls = 0

    sleeper = time.sleep if sleep_fn is None else sleep_fn

    class _SlowClient:
        def generate(self, **_: object) -> str:
            nonlocal slow_calls
            slow_calls += 1
            sleeper(delay)
            return "slow-response"

    class _FastClient:
        def generate(self, **_: object) -> str:
            return "fast-response"

    registry.models["slow"].build_client = lambda: _SlowClient()
    registry.models["fast"].build_client = lambda: _FastClient()

    router = LLMRouterService(registry, ledger=SharedLedger(ledger_path))
    result = _run_generation(router)
    result_queue.put(
        {
            "model": result.model.name,
            "slow_calls": slow_calls,
            "slow_latency": router.get_latency("slow"),
        }
    )


@pytest.mark.timeout(1.0)
def test_router_deduplicates_inflight_requests(tmp_path, sleep_stub):
    ledger_path = tmp_path / "shared-state.db"
    # Reset in a context to ensure cleanup
    ledger = SharedLedger(str(ledger_path))
    ledger.reset()
    del ledger  # Ensure connections are closed
    _wait_for_wal_cleanup(ledger_path, sleep_fn=sleep_stub)
    results: mp.Queue = mp.Queue()

    # First process: should incur spend and record high latency
    first = mp.Process(
        target=_process_budget_run,
        args=(str(ledger_path), results),
    )
    first.start()
    first.join(timeout=75.0)
    if first.is_alive():
        first.terminate()
        first.join(timeout=2.0)
        pytest.fail("First process timed out and was terminated")
    assert first.exitcode == 0
    first_result = results.get(timeout=5)

    assert first_result["model"] == "primary"
    assert first_result["primary_spend"] == pytest.approx(0.6, rel=1e-2)
    assert first_result["backup_spend"] == pytest.approx(0.0, rel=1e-2)

    # Second process: should see existing spend and latency
    # Spend: 0.6 existing. 0.6 + 0.6 = 1.2 > 1.0. Should NOT increment primary spend (or check will fail in is_available?)
    # Wait, get_spend returns the DB value.
    # Latency: sees > 30ms. Should pick 'fast'.

    second = mp.Process(
        target=_process_budget_run,
        args=(str(ledger_path), results),
    )
    second.start()
    second.join(timeout=75.0)
    if second.is_alive():
        second.terminate()
        second.join(timeout=2.0)
        pytest.fail("Second process timed out and was terminated")
    assert second.exitcode == 0
    second_result = results.get(timeout=5)

    # Verify Spend Sharing
    # Process 2 saw 0.6. It checks availability.
    # If 'primary' were run, 0.6 + 0.6 = 1.2 > 1.0.
    # The router sees projected spend > ceiling.
    # It updates the spend to the ceiling (1.0) and then raises GenerationError (or returns false availability).
    # In our test helper, we catch the error and proceed.
    # So primary spend should be updated to 1.0.
    assert second_result["model"] == "backup"
    assert second_result["primary_spend"] == pytest.approx(1.0, rel=1e-2)
    assert second_result["backup_spend"] > 0.0


@pytest.mark.timeout(5.0)
def test_router_deduplicates_inflight_requests_handles_restart_error(tmp_path, sleep_stub):
    ledger_path = tmp_path / "shared-state.db"
    # Reset in a context to ensure cleanup
    ledger = SharedLedger(str(ledger_path))
    ledger.reset()
    del ledger  # Ensure connections are closed
    _wait_for_wal_cleanup(ledger_path, sleep_fn=sleep_stub)
    results: mp.Queue = mp.Queue()

    # First process: should incur spend and record high latency
    first = mp.Process(
        target=_process_latency_run,
        args=(str(ledger_path), results),
        kwargs={"delay": 0.2},
    )
    first.start()
    first.join(timeout=75.0)
    if first.is_alive():
        first.terminate()
        first.join(timeout=2.0)
        pytest.fail("First process timed out and was terminated")
    assert first.exitcode == 0
    first_result = results.get(timeout=5)

    assert first_result["model"] == "slow"
    assert first_result["slow_calls"] == 1
    assert first_result["slow_latency"] is not None
    assert first_result["slow_latency"] > 0.0

    # Second process: should see existing spend and latency
    # Spend: 0.6 existing. 0.6 + 0.6 = 1.2 > 1.0. Should NOT increment primary spend (or check will fail in is_available?)
    # Wait, get_spend returns the DB value.
    # Latency: sees > 30ms. Should pick 'fast'.

    second = mp.Process(
        target=_process_latency_run,
        args=(str(ledger_path), results),
        kwargs={"delay": 0.2},
    )
    second.start()
    second.join(timeout=75.0)
    if second.is_alive():
        second.terminate()
        second.join(timeout=2.0)
        pytest.fail("Second process timed out and was terminated")
    assert second.exitcode == 0
    second_result = results.get(timeout=5)

    # Verify Latency Sharing
    # If latency was shared, slow model should be skipped (fast selected)
    # and slow_calls should be 0.
    assert second_result["model"] == "fast"
    assert second_result["slow_calls"] == 0
    assert second_result["slow_latency"] == pytest.approx(
        first_result["slow_latency"], rel=1e-2
    )


def test_router_logs_warning_when_latency_projection_near_threshold(monkeypatch):
    registry = LLMRegistry()
    registry.add_model(
        LLMModel(
            name="primary",
            provider="echo",
            model="echo",
            config={"suffix": "[primary]"},
            pricing={"per_call": 0.1},
            routing={"latency_threshold_ms": 100.0, "weight": 5.0},
        ),
        make_default=True,
    )
    mock_logger = Mock()
    monkeypatch.setattr(router_module, "LOGGER", mock_logger)
    router = LLMRouterService(registry)

    with router._ledger.transaction() as txn:
        txn.set_latency("primary", 90.0)

    times = itertools.chain([0.0, 0.0], itertools.repeat(0.0))
    monkeypatch.setattr(router_module.time, "perf_counter", lambda: next(times))

    result = router.execute_generation(workflow="chat", model=registry.models["primary"], prompt="hello")

    assert result.model.name == "primary"
    assert any("recent latency" in call.args[0] for call in mock_logger.warning.call_args_list)


def test_router_logs_warning_when_budget_exceeded(monkeypatch):
    registry = LLMRegistry()
    registry.add_model(
        LLMModel(
            name="primary",
            provider="echo",
            model="echo",
            config={"suffix": "[primary]"},
            pricing={"per_call": 0.1, "completion_tokens": 1.0},
            routing={"spend_ceiling": 1.0, "weight": 5.0},
        ),
        make_default=True,
    )
    mock_logger = Mock()
    monkeypatch.setattr(router_module, "LOGGER", mock_logger)
    router = LLMRouterService(registry)

    class _ExpensiveClient:
        def generate(self, **_: object) -> str:
            return "x" * 4000

    monkeypatch.setattr(registry.models["primary"], "build_client", lambda: _ExpensiveClient())

    with pytest.raises(GenerationError):
        router.execute_generation(workflow="chat", model=registry.models["primary"], prompt="hello")

    assert any("exceeded ceiling" in call.args[0] for call in mock_logger.warning.call_args_list)


def test_router_logs_warning_when_latency_exceeded(monkeypatch):
    registry = LLMRegistry()
    registry.add_model(
        LLMModel(
            name="primary",
            provider="echo",
            model="echo",
            config={"suffix": "[primary]"},
            routing={"latency_threshold_ms": 50.0, "weight": 5.0},
        ),
        make_default=True,
    )
    mock_logger = Mock()
    monkeypatch.setattr(router_module, "LOGGER", mock_logger)
    router = LLMRouterService(registry)

    times = itertools.chain([0.0, 0.2], itertools.repeat(0.2))
    monkeypatch.setattr(router_module.time, "perf_counter", lambda: next(times))

    with pytest.raises(GenerationError):
        router.execute_generation(workflow="chat", model=registry.models["primary"], prompt="hello")

    assert any("latency" in call.args[0] and "exceeded" in call.args[0] for call in mock_logger.warning.call_args_list)


def test_router_respects_budget_and_falls_back():
    registry = LLMRegistry()
    registry.add_model(
        LLMModel(
            name="primary",
            provider="echo",
            model="echo",
            config={"suffix": "[primary]"},
            pricing={"per_call": 0.6},
            routing={"spend_ceiling": 1.0, "weight": 10.0},
        ),
        make_default=True,
    )
    registry.add_model(
        LLMModel(
            name="backup",
            provider="echo",
            model="echo",
            config={"suffix": "[backup]"},
            pricing={"per_call": 0.4},
            routing={"weight": 1.0},
        )
    )
    router = LLMRouterService(registry)

    first = _run_generation(router)
    assert first.model.name == "primary"
    assert router.get_spend("primary") == pytest.approx(0.6)

    second = _run_generation(router)
    assert second.model.name == "backup"
    assert router.get_spend("primary") == pytest.approx(1.0)
    assert router.get_spend("backup") > 0.0


def test_router_latency_threshold_triggers_fallback(monkeypatch):
    registry = LLMRegistry()
    registry.add_model(
        LLMModel(
            name="slow",
            provider="echo",
            model="echo",
            config={"suffix": "[slow]"},
            routing={"latency_threshold_ms": 1.0, "weight": 5.0},
        ),
        make_default=True,
    )
    registry.add_model(
        LLMModel(
            name="fast",
            provider="echo",
            model="echo",
            config={"suffix": "[fast]"},
            routing={"weight": 1.0},
        )
    )
    router = LLMRouterService(registry)

    times = itertools.cycle([0.0, 0.005, 0.02, 0.021])
    monkeypatch.setattr(router_module.time, "perf_counter", lambda: next(times))

    result = _run_generation(router)
    assert result.model.name == "fast"
    slow_latency = router.get_latency("slow")
    assert slow_latency is not None
    assert slow_latency > 1.0


def test_router_generation_error_when_ledger_prepopulated():
    registry = LLMRegistry()
    registry.add_model(
        LLMModel(
            name="primary",
            provider="echo",
            model="echo",
            config={"suffix": "[primary]"},
            pricing={"per_call": 0.2},
            routing={
                "spend_ceiling": 1.0,
                "latency_threshold_ms": 10.0,
                "weight": 2.0,
            },

        ),
        make_default=True,
    )
    registry.add_model(
        LLMModel(
            name="secondary",
            provider="echo",
            model="echo",
            config={"suffix": "[secondary]"},
            pricing={"per_call": 0.2},
            routing={
                "spend_ceiling": 1.0,
                "latency_threshold_ms": 10.0,
                "weight": 1.0,
            },
        )
    )
    router = LLMRouterService(registry)

    with router._ledger.transaction() as txn:
        for model in registry.models.values():
            txn.set_spend(model.name, 1.5)
            txn.set_latency(model.name, 50.0)

    model = registry.models["primary"]
    with pytest.raises(GenerationError):
        router.execute_generation(workflow="chat", model=model, prompt="hello")

    assert router.get_spend("primary") == pytest.approx(1.0)


def test_router_prefers_model_hint_and_falls_back(monkeypatch):
    registry = LLMRegistry()
    registry.add_model(
        LLMModel(
            name="heavy",
            provider="echo",
            model="echo",
            config={"suffix": "[heavy]"},
            routing={"weight": 5.0},
        ),
        make_default=True,
    )
    registry.add_model(
        LLMModel(
            name="hinted",
            provider="echo",
            model="echo",
            config={"suffix": "[hinted]"},
            routing={"weight": 1.0},
        )
    )

    router = LLMRouterService(registry)

    candidates = router.iter_candidates("chat", model_hint="hinted")
    first = next(candidates)
    assert first.name == "hinted"

    class _FailingClient:
        def generate(self, **_: object) -> str:
            raise GenerationError("boom")

    # Force the hinted model to fail generation to confirm fallback order.
    monkeypatch.setattr(registry.models["hinted"], "build_client", lambda: _FailingClient())
    with pytest.raises(GenerationError):
        router.execute_generation(workflow="chat", model=first, prompt="hello")

    fallback = next(candidates)
    assert fallback.name == "heavy"


def test_router_reuses_cache_entry(monkeypatch):
    registry = LLMRegistry()
    registry.add_model(
        LLMModel(
            name="cached",
            provider="echo",
            model="echo",
            config={},
            pricing={"per_call": 0.5},
            routing={
                "cache_enabled": True,
                "cache_ttl_seconds": 120,
                "cache_max_entries": 8,
                "weight": 1.0,
            },
        ),
        make_default=True,
    )

    router = LLMRouterService(registry)

    call_count = 0

    class _CountingClient:
        def generate(self, **_: object) -> str:
            nonlocal call_count
            call_count += 1
            return "cached-output"

    monkeypatch.setattr(registry.models["cached"], "build_client", lambda: _CountingClient())

    model = registry.get()
    first = router.execute_generation(workflow="chat", model=model, prompt="hello")
    second = router.execute_generation(workflow="chat", model=model, prompt="hello")

    assert call_count == 1
    assert second.output == first.output
    assert router.get_spend("cached") == pytest.approx(first.cost)


def test_router_deduplicates_inflight_requests(monkeypatch, sleep_stub):
    registry = LLMRegistry()
    registry.add_model(
        LLMModel(
            name="primary",
            provider="echo",
            model="echo",
            config={},
            pricing={"per_call": 0.3},
            routing={"weight": 1.0},
        ),
        make_default=True,
    )

    router = LLMRouterService(registry)
    model = registry.get()

    call_count = 0
    call_lock = threading.Lock()
    first_started = threading.Event()
    allow_first_to_finish = threading.Event()
    error_observed = threading.Event()

    original_read_inflight = router._ledger._read_inflight

    def _instrumented_read(cache_key_arg: str, *, _orig=original_read_inflight):
        row = _orig(cache_key_arg)
        if row is not None and row.status == "error":
            error_observed.set()
        return row

    monkeypatch.setattr(router._ledger, "_read_inflight", _instrumented_read)

    class _SlowClient:
        def __init__(self, sleeper: Callable[[float], bool | None]):
            self._sleep = sleeper

        def generate(self, **_: object) -> str:
            nonlocal call_count
            with call_lock:
                call_count += 1
                current = call_count
            if current == 1:
                first_started.set()
                if not allow_first_to_finish.wait(timeout=5.0):  # pragma: no cover - safeguard
                    raise TimeoutError("test did not release first generation")
                self._sleep(0.001)
                return "shared-output"
            pytest.fail("Unexpected follower generation invocation")

    monkeypatch.setattr(model, "build_client", lambda: _SlowClient(sleep_stub))

    start_barrier = threading.Barrier(3)

    def _invoke() -> RoutedGeneration:
        start_barrier.wait()
        return router.execute_generation(workflow="chat", model=model, prompt="simultaneous")

    initial_updated_at: float | None = None

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(_invoke) for _ in range(3)]
        assert first_started.wait(timeout=2.0)

        cache_key = router._ledger.encode_cache_key(
            (model.name, "chat", "simultaneous", 0.2, 800)
        )
        with router._ledger.transaction() as txn:
            inflight_snapshot = txn.get_inflight(cache_key)
            if inflight_snapshot is not None:
                initial_updated_at = inflight_snapshot.updated_at
            txn.mark_inflight_error(cache_key, "transient failure")

        ledger_wait_future = executor.submit(
            lambda: router._ledger.wait_for_inflight(
                cache_key, poll_interval=0.01, timeout=2.0, sleep_fn=sleep_stub
            )
        )
        assert error_observed.wait(timeout=5.0)
        allow_first_to_finish.set()
        results = [future.result() for future in futures]
        ledger_wait_record = ledger_wait_future.result()

    assert call_count == 1
    outputs = {result.output for result in results}
    outputs.add(ledger_wait_record.output)
    assert outputs == {"shared-output"}
    with router._ledger.transaction() as txn:
        txn.clear_single_inflight(cache_key)
    late_record = router._ledger.wait_for_inflight(
        cache_key, poll_interval=0.01, timeout=1.0, sleep_fn=sleep_stub
    )
    assert late_record.output == "shared-output"
    assert router.get_spend("primary") == pytest.approx(results[0].cost)

    with router._ledger.transaction() as txn:
        txn.create_inflight(cache_key, model_name=model.name, workflow="chat")

    assert initial_updated_at is not None
    replayed_record = router._ledger.wait_for_inflight(
        cache_key,
        poll_interval=0.01,
        timeout=1.0,
        observed_updated_at=initial_updated_at,
        sleep_fn=sleep_stub,
    )
    assert replayed_record.output == "shared-output"


def test_router_deduplicates_inflight_requests_handles_restart_error(
    monkeypatch, sleep_stub
):
    registry = LLMRegistry()
    registry.add_model(
        LLMModel(
            name="primary",
            provider="echo",
            model="echo",
            config={},
            pricing={"per_call": 0.3},
            routing={"weight": 1.0},
        ),
        make_default=True,
    )

    router = LLMRouterService(registry)
    model = registry.get()

    call_count = 0
    call_lock = threading.Lock()
    first_call_done = threading.Event()
    first_call_release = threading.Event()
    retry_attempted = threading.Event()

    class _FlakyClient:
        def __init__(self, sleeper: Callable[[float], bool | None]):
            self._sleep = sleeper

        def generate(self, **_: object) -> str:
            nonlocal call_count
            with call_lock:
                call_count += 1
                current = call_count
            if current == 1:
                first_call_done.set()
                if not first_call_release.wait(timeout=5.0):  # pragma: no cover - safeguard
                    raise TimeoutError("test did not release initial generation")
                self._sleep(0.001)
                return "shared-output"
            retry_attempted.set()
            raise GenerationError("boom")

    monkeypatch.setattr(model, "build_client", lambda: _FlakyClient(sleep_stub))

    original_wait = router._ledger.wait_for_inflight

    def _slow_wait(
        cache_key: str,
        *,
        poll_interval: float = 0.05,
        timeout: float | None = None,
        observed_updated_at: float | None = None,
    ) -> CacheRecord:
        return original_wait(
            cache_key,
            poll_interval=0.2,
            timeout=timeout,
            observed_updated_at=observed_updated_at,
        )

    monkeypatch.setattr(router._ledger, "wait_for_inflight", _slow_wait)

    barrier = threading.Barrier(3)
    cache_key = router._ledger.encode_cache_key(
        (model.name, "chat", "simultaneous", 0.2, 800)
    )
    initial_updated_at: float | None = None

    def _invoke() -> RoutedGeneration:
        barrier.wait()
        return router.execute_generation(
            workflow="chat", model=model, prompt="simultaneous"
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(_invoke) for _ in range(3)]
        assert first_call_done.wait(timeout=2.0)
        deadline = time.time() + 2.0
        while initial_updated_at is None and time.time() < deadline:
            with router._ledger.transaction() as txn:
                snapshot = txn.get_inflight(cache_key)
            if snapshot is not None:
                initial_updated_at = snapshot.updated_at
            else:
                sleep_stub(0.01)
        first_call_release.set()
        _wait_for_inflight_status(
            router._ledger,
            cache_key,
            "success",
            timeout=2.0,
            sleep_fn=sleep_stub,
        )
        sleep_stub(0.01)

        def _expect_error() -> None:
            router.execute_generation(workflow="chat", model=model, prompt="simultaneous")

        error_future = executor.submit(_expect_error)
        _wait_until(retry_attempted.is_set, timeout=5.0, sleep_fn=sleep_stub)
        with pytest.raises(GenerationError):
            error_future.result()

        results = [future.result() for future in futures]

    assert call_count == 2
    assert {result.output for result in results} == {"shared-output"}
    cache_key = router._ledger.encode_cache_key(
        (model.name, "chat", "simultaneous", 0.2, 800)
    )
    with router._ledger.transaction() as txn:
        txn.clear_single_inflight(cache_key)
    preserved_record = router._ledger.wait_for_inflight(
        cache_key, poll_interval=0.01, timeout=1.0, sleep_fn=sleep_stub
    )
    assert preserved_record.output == "shared-output"

    with router._ledger.transaction() as txn:
        txn.create_inflight(cache_key, model_name=model.name, workflow="chat")

    assert initial_updated_at is not None
    replayed_record = router._ledger.wait_for_inflight(
        cache_key,
        poll_interval=0.01,
        timeout=1.0,
        observed_updated_at=initial_updated_at,
        sleep_fn=sleep_stub,
    )
    assert replayed_record.output == "shared-output"


def test_wait_for_inflight_handles_transient_absence(tmp_path, sleep_stub):
    ledger_path = tmp_path / "transient-inflight.db"
    ledger = SharedLedger(str(ledger_path))
    ledger.reset()
    cache_key = "cache-key"

    waiter_count = 2
    barrier = threading.Barrier(waiter_count + 1)
    outputs: list[str] = []
    errors: list[Exception] = []
    entered = threading.Event()
    entered_count = 0
    entered_lock = threading.Lock()

    def _waiter() -> None:
        barrier.wait()
        nonlocal entered_count
        with entered_lock:
            entered_count += 1
            if entered_count == waiter_count:
                entered.set()
        try:
            record = ledger.wait_for_inflight(
                cache_key, poll_interval=0.01, timeout=2.0, sleep_fn=sleep_stub
            )
            outputs.append(record.output)
        except Exception as exc:  # pragma: no cover - unexpected
            errors.append(exc)

    threads = [threading.Thread(target=_waiter) for _ in range(waiter_count)]
    for thread in threads:
        thread.start()

    barrier.wait()
    assert entered.wait(timeout=1.0)

    with ledger.transaction() as txn:
        txn.create_inflight(cache_key, model_name="model", workflow="workflow")

    _wait_for_inflight_status(ledger, cache_key, "waiting", sleep_fn=sleep_stub)

    with ledger.transaction() as txn:
        txn.mark_inflight_success(
            cache_key,
            model_name="model",
            workflow="workflow",
            output="shared-output",
            latency_ms=10.0,
            cost=0.1,
        )

    for i, thread in enumerate(threads):
        thread.join(timeout=5)
        if thread.is_alive():
            pytest.fail(f"Thread {i} timed out waiting for inflight completion")

    assert not errors, f"Errors occurred in waiter threads: {errors}"
    assert outputs == ["shared-output"] * waiter_count


def test_wait_for_inflight_recovers_from_transient_error(tmp_path, sleep_stub):
    ledger_path = tmp_path / "transient-error.db"
    ledger = SharedLedger(str(ledger_path))
    ledger.reset()
    cache_key = "cache-key"

    with ledger.transaction() as txn:
        txn.create_inflight(cache_key, model_name="model", workflow="workflow")

    ready = threading.Event()
    entered_wait = threading.Event()
    outputs: list[str] = []
    errors: list[Exception] = []

    def _waiter() -> None:
        ready.set()
        entered_wait.set()
        try:
            record = ledger.wait_for_inflight(
                cache_key, poll_interval=0.01, timeout=2.0, sleep_fn=sleep_stub
            )
            outputs.append(record.output)
        except Exception as exc:  # pragma: no cover - unexpected
            errors.append(exc)

    thread = threading.Thread(target=_waiter)
    thread.start()

    assert ready.wait(timeout=1.0)
    assert entered_wait.wait(timeout=1.0)

    with ledger.transaction() as txn:
        txn.mark_inflight_error(cache_key, "transient failure")

    _wait_for_inflight_status(ledger, cache_key, "error", sleep_fn=sleep_stub)

    with ledger.transaction() as txn:
        txn.mark_inflight_success(
            cache_key,
            model_name="model",
            workflow="workflow",
            output="recovered",
            latency_ms=12.0,
            cost=0.2,
        )

    thread.join(timeout=5)
    if thread.is_alive():
        pytest.fail("Waiter thread timed out waiting for recovery from transient error")
    assert not errors, f"Errors occurred in waiter thread: {errors}"
    assert outputs == ["recovered"]


def test_wait_for_inflight_preserves_completed_output_after_restart_failure(
    tmp_path, monkeypatch, sleep_stub
):
    ledger_path = tmp_path / "restart-failure.db"
    ledger = SharedLedger(str(ledger_path))
    ledger.reset()
    cache_key = "cache-key"

    with ledger.transaction() as txn:
        txn.create_inflight(cache_key, model_name="model", workflow="workflow")

    first_waiting_seen = threading.Event()
    restart_waiting_seen = threading.Event()
    release_initial = threading.Event()
    release_restart = threading.Event()

    original_read = ledger._read_inflight

    def _instrumented_read(cache_key_arg: str, *, _orig=original_read):
        row = _orig(cache_key_arg)
        if row is not None and row.status == "waiting":
            if row.output is None and not first_waiting_seen.is_set():
                first_waiting_seen.set()
                release_initial.wait(timeout=2.0)
            elif row.output is not None and not restart_waiting_seen.is_set():
                restart_waiting_seen.set()
                release_restart.wait(timeout=2.0)
        return row

    monkeypatch.setattr(ledger, "_read_inflight", _instrumented_read)

    outputs: list[str] = []
    errors: list[Exception] = []

    def _waiter() -> None:
        try:
            record = ledger.wait_for_inflight(
                cache_key, poll_interval=0.01, timeout=2.0, sleep_fn=sleep_stub
            )
            outputs.append(record.output)
        except Exception as exc:  # pragma: no cover - unexpected
            errors.append(exc)

    thread = threading.Thread(target=_waiter)
    thread.start()

    assert first_waiting_seen.wait(timeout=1.0)
    with ledger.transaction() as txn:
        txn.mark_inflight_success(
            cache_key,
            model_name="model",
            workflow="workflow",
            output="shared-output",
            latency_ms=11.0,
            cost=0.3,
        )
    with ledger.transaction() as txn:
        txn.create_inflight(cache_key, model_name="model", workflow="workflow")
    release_initial.set()

    assert restart_waiting_seen.wait(timeout=1.0)
    with ledger.transaction() as txn:
        txn.mark_inflight_error(cache_key, "new owner failed")
    release_restart.set()

    thread.join(timeout=5)
    if thread.is_alive():
        pytest.fail("Waiter thread timed out waiting for preserved completion")

    assert not errors, f"Errors occurred in waiter thread: {errors}"
    assert outputs == ["shared-output"]


def test_wait_for_inflight_replays_preserved_after_restart_for_new_waiter(tmp_path, sleep_stub):
    ledger_path = tmp_path / "restart-new-waiter.db"
    ledger = SharedLedger(str(ledger_path))
    ledger.reset()
    cache_key = "cache-key"

    with ledger.transaction() as txn:
        txn.create_inflight(cache_key, model_name="model", workflow="workflow")
    with ledger.transaction() as txn:
        txn.mark_inflight_success(
            cache_key,
            model_name="model",
            workflow="workflow",
            output="shared-output",
            latency_ms=5.0,
            cost=0.1,
        )
    with ledger.transaction() as txn:
        txn.create_inflight(cache_key, model_name="model", workflow="workflow")

    record = ledger.wait_for_inflight(
        cache_key,
        poll_interval=0.01,
        timeout=0.3,
        sleep_fn=sleep_stub,
    )
    assert record.output == "shared-output"


def test_wait_for_inflight_delivers_preserved_after_error_message(tmp_path, sleep_stub):
    ledger_path = tmp_path / "preserved-after-error.db"
    ledger = SharedLedger(str(ledger_path))
    ledger.reset()
    cache_key = "cache-key"

    with ledger.transaction() as txn:
        txn.create_inflight(cache_key, model_name="model", workflow="workflow")
    with ledger.transaction() as txn:
        txn.mark_inflight_success(
            cache_key,
            model_name="model",
            workflow="workflow",
            output="shared-output",
            latency_ms=7.0,
            cost=0.25,
        )
    with ledger.transaction() as txn:
        txn.create_inflight(cache_key, model_name="model", workflow="workflow")
    with ledger.transaction() as txn:
        txn.mark_inflight_error(
            cache_key, "Deduplicated generation completed without a result"
        )

    start = time.perf_counter()
    record = ledger.wait_for_inflight(
        cache_key,
        poll_interval=0.01,
        timeout=1.0,
        sleep_fn=sleep_stub,
    )
    elapsed = time.perf_counter() - start

    assert record.output == "shared-output"
    assert elapsed < 0.5


def test_wait_for_inflight_returns_empty_output(tmp_path, sleep_stub):
    ledger_path = tmp_path / "empty-output.db"
    ledger = SharedLedger(str(ledger_path))
    ledger.reset()
    cache_key = "cache-key"

    with ledger.transaction() as txn:
        txn.create_inflight(cache_key, model_name="model", workflow="workflow")

    ready = threading.Event()
    entered_wait = threading.Event()
    outputs: list[str] = []
    errors: list[Exception] = []

    def _waiter() -> None:
        ready.set()
        entered_wait.set()
        try:
            record = ledger.wait_for_inflight(
                cache_key, poll_interval=0.01, timeout=2.0, sleep_fn=sleep_stub
            )
            outputs.append(record.output)
        except Exception as exc:  # pragma: no cover - unexpected
            errors.append(exc)

    thread = threading.Thread(target=_waiter)
    thread.start()

    assert ready.wait(timeout=1.0)
    assert entered_wait.wait(timeout=1.0)

    with ledger.transaction() as txn:
        txn.mark_inflight_success(
            cache_key,
            model_name="model",
            workflow="workflow",
            output="",
            latency_ms=6.0,
            cost=0.05,
        )

    thread.join(timeout=5)
    if thread.is_alive():
        pytest.fail("Waiter thread timed out waiting for empty output")
    assert not errors, f"Errors occurred in waiter thread: {errors}"
    assert outputs == [""]


def test_wait_for_inflight_waits_for_late_cache_write(tmp_path, sleep_stub):
    ledger_path = tmp_path / "late-cache.db"
    ledger = SharedLedger(str(ledger_path))
    ledger.reset()
    cache_key = "cache-key"

    with ledger.transaction() as txn:
        txn.create_inflight(cache_key, model_name="model", workflow="workflow")

    ready = threading.Event()
    entered_wait = threading.Event()
    outputs: list[str] = []
    errors: list[Exception] = []

    def _waiter() -> None:
        ready.set()
        entered_wait.set()
        try:
            record = ledger.wait_for_inflight(
                cache_key, poll_interval=0.01, timeout=2.0, sleep_fn=sleep_stub
            )
            outputs.append(record.output)
        except Exception as exc:  # pragma: no cover - unexpected
            errors.append(exc)

    thread = threading.Thread(target=_waiter)
    thread.start()

    assert ready.wait(timeout=1.0)
    assert entered_wait.wait(timeout=1.0)

    with ledger.transaction() as txn:
        txn.clear_single_inflight(cache_key)

    _wait_for_inflight_absence(ledger, cache_key, sleep_fn=sleep_stub)

    with ledger.transaction() as txn:
        txn.store_cache_entry(
            CacheRecord(
                cache_key=cache_key,
                model_name="model",
                workflow="workflow",
                prompt="prompt",
                temperature=0.0,
                max_output_tokens=1,
                output="cached-output",
                latency_ms=10.0,
                cost=0.2,
                created_at=time.monotonic(),
            )
        )

    thread.join(timeout=5)
    if thread.is_alive():
        pytest.fail("Waiter thread timed out waiting for late cache write")
    assert not errors, f"Errors occurred in waiter thread: {errors}"
    assert outputs == ["cached-output"]


def test_wait_for_inflight_handles_restart_requeue(tmp_path, sleep_stub):
    ledger_path = tmp_path / "restart-requeue.db"
    ledger = SharedLedger(str(ledger_path))
    ledger.reset()
    cache_key = "cache-key"

    with ledger.transaction() as txn:
        txn.create_inflight(cache_key, model_name="model", workflow="workflow")

    ready = threading.Event()
    entered_wait = threading.Event()
    outputs: list[str] = []
    errors: list[Exception] = []

    def _waiter() -> None:
        ready.set()
        entered_wait.set()
        try:
            record = ledger.wait_for_inflight(
                cache_key, poll_interval=0.01, timeout=2.0, sleep_fn=sleep_stub
            )
            outputs.append(record.output)
        except Exception as exc:  # pragma: no cover - unexpected
            errors.append(exc)

    thread = threading.Thread(target=_waiter)
    thread.start()

    assert ready.wait(timeout=1.0)
    assert entered_wait.wait(timeout=1.0)

    with ledger.transaction() as txn:
        txn.clear_single_inflight(cache_key)

    with ledger.transaction() as txn:
        txn.create_inflight(cache_key, model_name="model", workflow="workflow")

    _wait_for_inflight_status(ledger, cache_key, "waiting", sleep_fn=sleep_stub)

    with ledger.transaction() as txn:
        txn.mark_inflight_success(
            cache_key,
            model_name="model",
            workflow="workflow",
            output="after-restart",
            latency_ms=8.0,
            cost=0.15,
        )

    thread.join(timeout=5)
    if thread.is_alive():
        pytest.fail("Waiter thread timed out waiting for restart requeue")
    assert not errors, f"Errors occurred in waiter thread: {errors}"
    assert outputs == ["after-restart"]


def _thread_budget_run(ledger_path: str) -> dict:
    """Thread-safe version of _process_budget_run for fast cross-connection testing."""
    registry = LLMRegistry()
    registry.add_model(
        LLMModel(
            name="primary",
            provider="echo",
            model="echo",
            config={"suffix": "[primary]"},
            pricing={"per_call": 0.6},
            routing={"spend_ceiling": 1.0, "weight": 10.0},
        ),
        make_default=True,
    )
    registry.add_model(
        LLMModel(
            name="backup",
            provider="echo",
            model="echo",
            config={"suffix": "[backup]"},
            pricing={"per_call": 0.4},
            routing={"weight": 1.0},
        )
    )
    # Create fresh ledger instance (new connection to same DB)
    router = LLMRouterService(registry, ledger=SharedLedger(ledger_path))
    result = _run_generation(router)
    return {
        "model": result.model.name,
        "primary_spend": router.get_spend("primary"),
        "backup_spend": router.get_spend("backup"),
    }


@pytest.mark.timeout(2.0)
def test_router_shared_spend_across_connections(tmp_path, sleep_stub):
    """Fast test: verifies spend sharing via SQLite WAL across separate connections.

    This tests the same state-sharing behavior as the multiprocessing test but
    uses threads with separate router/ledger instances, avoiding Windows spawn
    overhead (~8-9s per process).
    """
    ledger_path = tmp_path / "shared-ledger.db"
    ledger = SharedLedger(str(ledger_path))
    ledger.reset()
    del ledger
    _wait_for_wal_cleanup(ledger_path, sleep_fn=sleep_stub)

    # Run first "isolated" router instance
    first_result = _thread_budget_run(str(ledger_path))
    assert first_result["model"] == "primary"
    assert first_result["primary_spend"] == pytest.approx(0.6, rel=1e-2)
    assert first_result["backup_spend"] == pytest.approx(0.0, rel=1e-2)

    # Run second "isolated" router instance - should see first's state
    second_result = _thread_budget_run(str(ledger_path))
    assert second_result["model"] == "backup"
    assert second_result["primary_spend"] == pytest.approx(1.0, rel=1e-2)
    assert second_result["backup_spend"] > 0.0


@pytest.mark.slow
@pytest.mark.timeout(120)
@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="multiprocessing spawn is too slow on Windows; use connection-based variant instead",
)
def test_router_shared_spend_across_processes(tmp_path, sleep_stub):
    """Slow test: verifies spend sharing via SQLite WAL across OS processes.

    On Windows, this takes ~18s due to spawn overhead. Use
    test_router_shared_spend_across_connections for CI.
    """
    ledger_path = tmp_path / "shared-ledger.db"
    # Reset in a context to ensure cleanup
    ledger = SharedLedger(str(ledger_path))
    ledger.reset()
    del ledger  # Ensure connections are closed
    _wait_for_wal_cleanup(ledger_path, sleep_fn=sleep_stub)
    results: mp.Queue = mp.Queue()

    first = mp.Process(target=_process_budget_run, args=(str(ledger_path), results))
    first.start()
    first.join(timeout=75.0)
    if first.is_alive():
        first.terminate()
        first.join(timeout=2.0)
        pytest.fail("First process timed out and was terminated")
    assert first.exitcode == 0
    first_result = results.get(timeout=5)

    assert first_result["model"] == "primary"
    assert first_result["primary_spend"] == pytest.approx(0.6, rel=1e-2)
    assert first_result["backup_spend"] == pytest.approx(0.0, rel=1e-2)

    second = mp.Process(target=_process_budget_run, args=(str(ledger_path), results))
    second.start()
    second.join(timeout=75.0)
    if second.is_alive():
        second.terminate()
        second.join(timeout=2.0)
        pytest.fail("Second process timed out and was terminated")
    assert second.exitcode == 0
    second_result = results.get(timeout=5)

    assert second_result["model"] == "backup"
    assert second_result["primary_spend"] == pytest.approx(1.0, rel=1e-2)
    assert second_result["backup_spend"] > 0.0


def _thread_latency_run(ledger_path: str, *, delay: float) -> dict:
    """Thread-safe version of _process_latency_run for fast cross-connection testing."""
    registry = LLMRegistry()
    registry.add_model(
        LLMModel(
            name="slow",
            provider="echo",
            model="echo",
            config={"suffix": "[slow]"},
            routing={"latency_threshold_ms": 30.0, "weight": 5.0},
        ),
        make_default=True,
    )
    registry.add_model(
        LLMModel(
            name="fast",
            provider="echo",
            model="echo",
            config={"suffix": "[fast]"},
            routing={"weight": 1.0},
        )
    )

    slow_calls = 0

    class _SlowClient:
        def generate(self, **_: object) -> str:
            nonlocal slow_calls
            slow_calls += 1
            time.sleep(delay)
            return "slow-response"

    class _FastClient:
        def generate(self, **_: object) -> str:
            return "fast-response"

    registry.models["slow"].build_client = lambda: _SlowClient()
    registry.models["fast"].build_client = lambda: _FastClient()

    # Create fresh ledger instance (new connection to same DB)
    router = LLMRouterService(registry, ledger=SharedLedger(ledger_path))
    result = _run_generation(router)
    return {
        "model": result.model.name,
        "slow_calls": slow_calls,
        "slow_latency": router.get_latency("slow"),
    }


@pytest.mark.allow_sleep
@pytest.mark.timeout(2.0)
def test_router_shared_latency_across_connections(tmp_path, sleep_stub):
    """Fast test: verifies latency sharing via SQLite WAL across separate connections.

    This tests the same state-sharing behavior as the multiprocessing test but
    uses sequential calls with separate router/ledger instances, avoiding Windows
    spawn overhead (~8-9s per process).
    """
    ledger_path = tmp_path / "latency-ledger.db"
    ledger = SharedLedger(str(ledger_path))
    ledger.reset()
    del ledger
    _wait_for_wal_cleanup(ledger_path, sleep_fn=sleep_stub)

    # First "isolated" router - slow model gets called, records high latency
    first_result = _thread_latency_run(str(ledger_path), delay=0.05)
    assert first_result["model"] == "fast"  # Falls back after slow exceeds threshold
    assert first_result["slow_calls"] == 1
    assert first_result["slow_latency"] is not None
    assert first_result["slow_latency"] > 0.0

    # Second "isolated" router - should see latency and skip slow model
    second_result = _thread_latency_run(str(ledger_path), delay=0.05)
    assert second_result["model"] == "fast"
    assert second_result["slow_calls"] == 0  # Skipped due to recorded latency
    assert second_result["slow_latency"] == pytest.approx(
        first_result["slow_latency"], rel=1e-2
    )


@pytest.mark.slow
@pytest.mark.timeout(120)
@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="multiprocessing spawn is too slow on Windows; use connection-based variant instead",
)
def test_router_shared_latency_across_processes(tmp_path, sleep_stub):
    """Slow test: verifies latency sharing via SQLite WAL across OS processes.

    On Windows, this takes ~18s due to spawn overhead. Use
    test_router_shared_latency_across_connections for CI.
    """
    ledger_path = tmp_path / "latency-ledger.db"
    # Reset in a context to ensure cleanup
    ledger = SharedLedger(str(ledger_path))
    ledger.reset()
    del ledger  # Ensure connections are closed
    _wait_for_wal_cleanup(ledger_path, sleep_fn=sleep_stub)
    results: mp.Queue = mp.Queue()

    first = mp.Process(
        target=_process_latency_run,
        args=(str(ledger_path), results),
        kwargs={"delay": 0.05},
    )
    first.start()
    first.join(timeout=75.0)
    if first.is_alive():
        first.terminate()
        first.join(timeout=2.0)
        pytest.fail("First process timed out and was terminated")
    assert first.exitcode == 0
    first_result = results.get(timeout=5)

    assert first_result["model"] == "fast"
    assert first_result["slow_calls"] == 1
    assert first_result["slow_latency"] is not None
    assert first_result["slow_latency"] > 0.0

    second = mp.Process(
        target=_process_latency_run,
        args=(str(ledger_path), results),
        kwargs={"delay": 0.05},
    )
    second.start()
    second.join(timeout=75.0)
    if second.is_alive():
        second.terminate()
        second.join(timeout=2.0)
        pytest.fail("Second process timed out and was terminated")
    assert second.exitcode == 0
    second_result = results.get(timeout=5)

    assert second_result["model"] == "fast"
    assert second_result["slow_calls"] == 0
    assert second_result["slow_latency"] == pytest.approx(
        first_result["slow_latency"], rel=1e-2
    )


def test_wait_for_inflight_immediately_replays_preserved_on_recreated_waiting(
    tmp_path, sleep_stub
):
    """Regression test: verifies preserved output is surfaced immediately when
    a waiting row is recreated after a router restart.

    This tests the fix for the production concurrency gap where waiters would
    block indefinitely when a restarted router recreated the inflight row as
    'waiting' even though a successful output was already preserved.
    """
    ledger_path = tmp_path / "replay-preserved.db"
    ledger = SharedLedger(str(ledger_path))
    ledger.reset()
    cache_key = "replay-cache-key"

    # 1. Create initial inflight entry and mark success
    with ledger.transaction() as txn:
        txn.create_inflight(cache_key, model_name="model", workflow="workflow")
    with ledger.transaction() as txn:
        txn.mark_inflight_success(
            cache_key,
            model_name="model",
            workflow="workflow",
            output="preserved-output",
            latency_ms=10.0,
            cost=0.5,
        )

    # 2. Simulate router restart by recreating inflight as 'waiting'
    with ledger.transaction() as txn:
        txn.create_inflight(cache_key, model_name="model", workflow="workflow")

    # Verify the row is in waiting state
    row = ledger._read_inflight(cache_key)
    assert row is not None
    assert row.status == "waiting"

    # 3. New waiter should immediately get the preserved output
    start = time.perf_counter()
    record = ledger.wait_for_inflight(
        cache_key,
        poll_interval=0.01,
        timeout=1.0,
        sleep_fn=sleep_stub,
    )
    elapsed = time.perf_counter() - start

    # Should return the preserved output immediately (within first poll cycle)
    assert record.output == "preserved-output"
    assert elapsed < 0.5, f"Took too long ({elapsed:.2f}s) - waiter should return immediately"


def test_wait_for_inflight_concurrent_waiters_all_receive_preserved_after_restart(
    tmp_path, sleep_stub
):
    """Regression test: verifies multiple concurrent waiters all receive the
    preserved output when a waiting row is recreated after a router restart.

    This ensures the fix handles fan-out scenarios where multiple threads
    are waiting for the same generation.
    """
    ledger_path = tmp_path / "concurrent-replay.db"
    ledger = SharedLedger(str(ledger_path))
    ledger.reset()
    cache_key = "concurrent-cache-key"
    waiter_count = 3

    # 1. Create initial inflight entry
    with ledger.transaction() as txn:
        txn.create_inflight(cache_key, model_name="model", workflow="workflow")

    # 2. Start multiple waiters before success is marked
    barrier = threading.Barrier(waiter_count + 1)
    outputs: list[str] = []
    errors: list[Exception] = []
    lock = threading.Lock()

    def _waiter() -> None:
        barrier.wait(timeout=2.0)  # Synchronize start
        try:
            record = ledger.wait_for_inflight(
                cache_key, poll_interval=0.01, timeout=3.0, sleep_fn=sleep_stub
            )
            with lock:
                outputs.append(record.output)
        except Exception as exc:  # pragma: no cover - unexpected
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=_waiter) for _ in range(waiter_count)]
    for t in threads:
        t.start()

    # 3. Wait for all waiters to start, then mark success
    barrier.wait(timeout=2.0)
    time.sleep(0.05)  # Small delay to ensure waiters are polling

    with ledger.transaction() as txn:
        txn.mark_inflight_success(
            cache_key,
            model_name="model",
            workflow="workflow",
            output="shared-concurrent-output",
            latency_ms=15.0,
            cost=0.25,
        )

    # 4. Simulate router restart
    with ledger.transaction() as txn:
        txn.create_inflight(cache_key, model_name="model", workflow="workflow")

    # 5. All waiters should eventually receive the preserved output
    for t in threads:
        t.join(timeout=5)
        if t.is_alive():
            pytest.fail("Waiter thread timed out")

    assert not errors, f"Errors occurred in waiter threads: {errors}"
    assert len(outputs) == waiter_count
    assert all(o == "shared-concurrent-output" for o in outputs)
