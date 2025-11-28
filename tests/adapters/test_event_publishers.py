from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from exegesis.adapters.events import build_event_publisher
from exegesis.adapters.events.kafka import KafkaEventPublisher
from exegesis.adapters.events.redis import RedisStreamEventPublisher
from exegesis.application.facades.settings import KafkaEventSink, RedisStreamEventSink
from exegesis.application.ports.events import DomainEvent


def test_kafka_event_publisher_uses_factory() -> None:
    sink = KafkaEventSink(
        topic="exegesis.events",
        bootstrap_servers="kafka:9092",
        producer_config={"acks": "all"},
    )

    created: dict[str, object] = {}

    class _Producer:
        def __init__(self, config: dict[str, object]) -> None:
            self.config = config
            self.calls: list[dict[str, object]] = []
            self.polls: list[int | float] = []
            self.flushes: list[int | float] = []

        def produce(self, *, topic: str, value: bytes, key=None, headers=None) -> None:
            self.calls.append(
                {
                    "topic": topic,
                    "value": value,
                    "key": key,
                    "headers": headers,
                }
            )

        def poll(self, timeout: float) -> None:
            self.polls.append(timeout)

        def flush(self, timeout: float) -> int:
            self.flushes.append(timeout)
            return 0

    def _factory(config: dict[str, object]) -> _Producer:
        created["config"] = config
        producer = _Producer(config)
        created["producer"] = producer
        return producer

    publisher = KafkaEventPublisher(sink, producer_factory=_factory)
    event = DomainEvent(type="exegesis.example", payload={"id": "123"}, key="123")

    publisher.publish(event)

    producer = created["producer"]
    assert created["config"] == {
        "bootstrap.servers": "kafka:9092",
        "acks": "all",
    }
    assert len(producer.calls) == 1
    call = producer.calls[0]
    assert call["topic"] == "exegesis.events"
    assert call["key"] == "123"
    payload = json.loads(call["value"].decode("utf-8"))
    assert payload["type"] == "exegesis.example"
    assert payload["payload"] == {"id": "123"}
    assert producer.polls == [0]
    assert producer.flushes == [sink.flush_timeout_seconds]


def test_redis_stream_event_publisher_appends_messages() -> None:
    sink = RedisStreamEventSink(stream="events", redis_url="redis://redis:6379/0", maxlen=100)

    class _Client:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, str], dict[str, object]]] = []

        def xadd(self, stream: str, fields: dict[str, str], **kwargs: object) -> str:
            self.calls.append((stream, fields, kwargs))
            return "0-0"

    client = _Client()
    publisher = RedisStreamEventPublisher(sink, redis_client=client)
    event = DomainEvent(type="exegesis.example", payload={"id": "abc"})

    publisher.publish(event)

    assert len(client.calls) == 1
    stream, fields, kwargs = client.calls[0]
    assert stream == "events"
    assert json.loads(fields["body"]) == event.to_message()
    assert kwargs == {"maxlen": 100, "approximate": True}


def test_build_event_publisher_resolves_sink_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    sink = RedisStreamEventSink(stream="events", redis_url=None)
    settings = SimpleNamespace(redis_url="redis://redis:6379/1")
    constructed: dict[str, RedisStreamEventSink] = {}

    class _StubPublisher:
        def __init__(self, config: RedisStreamEventSink) -> None:
            constructed["config"] = config

        def publish(self, event: DomainEvent) -> None:  # pragma: no cover - stub
            pass

    monkeypatch.setattr("exegesis.adapters.events.RedisStreamEventPublisher", _StubPublisher)

    publisher = build_event_publisher(sink, settings=settings)  # type: ignore[arg-type]

    assert isinstance(publisher, _StubPublisher)
    assert constructed["config"].redis_url == settings.redis_url


def test_kafka_event_publisher_propagates_producer_errors() -> None:
    sink = KafkaEventSink(topic="failures", bootstrap_servers="kafka:9092", producer_config={})

    class _Producer:
        def __init__(self) -> None:
            self.polls: list[float] = []
            self.flushes: list[float] = []

        def produce(self, **kwargs: object) -> None:  # noqa: ANN001 - mimic confluent producer signature
            raise RuntimeError("produce failed")

        def poll(self, timeout: float) -> None:
            self.polls.append(timeout)

        def flush(self, timeout: float) -> int:
            self.flushes.append(timeout)
            return 0

    created: dict[str, _Producer] = {}

    def factory(options: dict[str, object]) -> _Producer:
        producer = _Producer()
        created["producer"] = producer
        return producer

    publisher = KafkaEventPublisher(sink, producer_factory=factory)
    event = DomainEvent(type="failure", payload={})

    with pytest.raises(RuntimeError):
        publisher.publish(event)

    producer = created["producer"]
    assert producer.polls == []
    assert producer.flushes == []


def test_redis_stream_event_publisher_propagates_client_errors() -> None:
    sink = RedisStreamEventSink(stream="events", redis_url="redis://redis:6379/0")

    class _Client:
        def xadd(self, *args, **kwargs):  # noqa: ANN001 - mimic redis client signature
            raise RuntimeError("redis failure")

    publisher = RedisStreamEventPublisher(sink, redis_client=_Client())
    event = DomainEvent(type="redis", payload={})

    with pytest.raises(RuntimeError):
        publisher.publish(event)


def test_redis_stream_event_publisher_uses_client_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    sink = RedisStreamEventSink(stream="events", redis_url="redis://custom:6379/0", maxlen=50)
    captured: dict[str, object] = {}

    class _Client:
        def __init__(self) -> None:
            self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def xadd(self, *args: object, **kwargs: object) -> str:
            self.calls.append((args, kwargs))
            return "0-1"

    def factory(url: str) -> _Client:
        captured["url"] = url
        client = _Client()
        captured["client"] = client
        return client

    publisher = RedisStreamEventPublisher(sink, client_factory=factory)
    event = DomainEvent(type="redis", payload={"id": 1})

    publisher.publish(event)

    assert captured["url"] == "redis://custom:6379/0"
    client: _Client = captured["client"]  # type: ignore[assignment]
    assert len(client.calls) == 1
    args, kwargs = client.calls[0]
    assert args[0] == "events"
    assert kwargs == {"maxlen": 50, "approximate": True}


# === Validation Tests ===


def test_kafka_event_publisher_requires_topic() -> None:
    sink = KafkaEventSink(topic="", bootstrap_servers="kafka:9092")

    with pytest.raises(ValueError, match="Kafka event sink requires a topic"):
        KafkaEventPublisher(sink, producer_factory=lambda _: None)


def test_kafka_event_publisher_requires_bootstrap_servers() -> None:
    sink = KafkaEventSink(topic="events", bootstrap_servers="")

    with pytest.raises(ValueError, match="Kafka event sink requires bootstrap_servers"):
        KafkaEventPublisher(sink, producer_factory=lambda _: None)


def test_redis_stream_event_publisher_requires_stream() -> None:
    sink = RedisStreamEventSink(stream="", redis_url="redis://redis:6379/0")

    with pytest.raises(ValueError, match="Redis stream event sink requires a stream name"):
        RedisStreamEventPublisher(sink, redis_client=object())


def test_redis_stream_event_publisher_requires_redis_url_when_no_client() -> None:
    sink = RedisStreamEventSink(stream="events", redis_url=None)

    with pytest.raises(ValueError, match="Redis stream event sink requires a redis_url"):
        RedisStreamEventPublisher(sink)


# === Kafka Batching Tests ===


def test_kafka_event_publisher_batches_messages_by_size() -> None:
    sink = KafkaEventSink(
        topic="events",
        bootstrap_servers="kafka:9092",
        batch_size=3,
        flush_interval_seconds=100.0,  # High interval to ensure size triggers flush
        flush_timeout_seconds=5.0,
    )

    class _Producer:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []
            self.flushes: list[float] = []

        def produce(self, **kwargs: object) -> None:
            self.calls.append(kwargs)

        def poll(self, timeout: float) -> None:
            pass

        def flush(self, timeout: float) -> int:
            self.flushes.append(timeout)
            return 0

    producer = _Producer()
    publisher = KafkaEventPublisher(sink, producer_factory=lambda _: producer)

    # Publish 2 messages - should not flush yet
    publisher.publish(DomainEvent(type="test", payload={"n": 1}))
    publisher.publish(DomainEvent(type="test", payload={"n": 2}))
    assert len(producer.flushes) == 0

    # 3rd message should trigger batch flush
    publisher.publish(DomainEvent(type="test", payload={"n": 3}))
    assert len(producer.flushes) == 1
    assert producer.flushes[0] == 5.0


@pytest.mark.allow_sleep
def test_kafka_event_publisher_batches_messages_by_time() -> None:
    import time

    sink = KafkaEventSink(
        topic="events",
        bootstrap_servers="kafka:9092",
        batch_size=100,  # High batch size so time triggers flush
        flush_interval_seconds=0.2,
        flush_timeout_seconds=3.0,
    )

    class _Producer:
        def __init__(self) -> None:
            self.flushes: list[float] = []

        def produce(self, **kwargs: object) -> None:
            pass

        def poll(self, timeout: float) -> None:
            pass

        def flush(self, timeout: float) -> int:
            self.flushes.append(timeout)
            return 0

    producer = _Producer()
    publisher = KafkaEventPublisher(sink, producer_factory=lambda _: producer)

    # Publish first message - no flush due to high batch size
    publisher.publish(DomainEvent(type="test", payload={"n": 1}))
    assert len(producer.flushes) == 0

    # Wait for flush interval to elapse
    time.sleep(0.25)

    # Next publish should trigger time-based flush because interval elapsed
    publisher.publish(DomainEvent(type="test", payload={"n": 2}))
    assert len(producer.flushes) == 1
    assert producer.flushes[0] == 3.0


def test_kafka_event_publisher_batch_size_1_flushes_immediately() -> None:
    sink = KafkaEventSink(
        topic="events",
        bootstrap_servers="kafka:9092",
        batch_size=1,  # Batching disabled
        flush_timeout_seconds=2.0,
    )

    class _Producer:
        def __init__(self) -> None:
            self.flushes: list[float] = []

        def produce(self, **kwargs: object) -> None:
            pass

        def poll(self, timeout: float) -> None:
            pass

        def flush(self, timeout: float) -> int:
            self.flushes.append(timeout)
            return 0

    producer = _Producer()
    publisher = KafkaEventPublisher(sink, producer_factory=lambda _: producer)

    # Each publish should flush immediately with batch_size=1
    publisher.publish(DomainEvent(type="test", payload={"n": 1}))
    assert len(producer.flushes) == 1

    publisher.publish(DomainEvent(type="test", payload={"n": 2}))
    assert len(producer.flushes) == 2


# === Kafka Event Headers Tests ===


def test_kafka_event_publisher_includes_headers() -> None:
    sink = KafkaEventSink(topic="events", bootstrap_servers="kafka:9092")

    class _Producer:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def produce(self, **kwargs: object) -> None:
            self.calls.append(kwargs)

        def poll(self, timeout: float) -> None:
            pass

        def flush(self, timeout: float) -> int:
            return 0

    producer = _Producer()
    publisher = KafkaEventPublisher(sink, producer_factory=lambda _: producer)

    event = DomainEvent(
        type="test",
        payload={"id": "123"},
        headers={"trace-id": "abc-def", "user-id": "42"}
    )
    publisher.publish(event)

    assert len(producer.calls) == 1
    call = producer.calls[0]
    headers = call["headers"]
    assert headers == [("trace-id", b"abc-def"), ("user-id", b"42")]


# === Kafka Flush and Close Tests ===


def test_kafka_event_publisher_explicit_flush() -> None:
    sink = KafkaEventSink(
        topic="events",
        bootstrap_servers="kafka:9092",
        batch_size=100,  # Large batch size
        flush_timeout_seconds=7.0,
    )

    class _Producer:
        def __init__(self) -> None:
            self.flushes: list[float] = []

        def produce(self, **kwargs: object) -> None:
            pass

        def poll(self, timeout: float) -> None:
            pass

        def flush(self, timeout: float) -> int:
            self.flushes.append(timeout)
            return 0

    producer = _Producer()
    publisher = KafkaEventPublisher(sink, producer_factory=lambda _: producer)

    # Publish without triggering batch flush
    publisher.publish(DomainEvent(type="test", payload={}))
    assert len(producer.flushes) == 0

    # Explicit flush
    publisher.flush()
    assert len(producer.flushes) == 1
    assert producer.flushes[0] == 7.0


def test_kafka_event_publisher_close_flushes_messages() -> None:
    sink = KafkaEventSink(
        topic="events",
        bootstrap_servers="kafka:9092",
        flush_timeout_seconds=3.0,
    )

    class _Producer:
        def __init__(self) -> None:
            self.flushes: list[float] = []

        def produce(self, **kwargs: object) -> None:
            pass

        def poll(self, timeout: float) -> None:
            pass

        def flush(self, timeout: float) -> int:
            self.flushes.append(timeout)
            return 0

    producer = _Producer()
    publisher = KafkaEventPublisher(sink, producer_factory=lambda _: producer)

    publisher.close()

    # close() should use max(30.0, flush_timeout)
    assert len(producer.flushes) == 1
    assert producer.flushes[0] == 30.0


def test_kafka_event_publisher_close_uses_extended_timeout() -> None:
    sink = KafkaEventSink(
        topic="events",
        bootstrap_servers="kafka:9092",
        flush_timeout_seconds=50.0,  # Longer than default 30s
    )

    class _Producer:
        def __init__(self) -> None:
            self.flushes: list[float] = []

        def produce(self, **kwargs: object) -> None:
            pass

        def poll(self, timeout: float) -> None:
            pass

        def flush(self, timeout: float) -> int:
            self.flushes.append(timeout)
            return 0

    producer = _Producer()
    publisher = KafkaEventPublisher(sink, producer_factory=lambda _: producer)

    publisher.close()

    assert len(producer.flushes) == 1
    assert producer.flushes[0] == 50.0


def test_kafka_event_publisher_context_manager() -> None:
    sink = KafkaEventSink(topic="events", bootstrap_servers="kafka:9092")

    class _Producer:
        def __init__(self) -> None:
            self.flushes: list[float] = []

        def produce(self, **kwargs: object) -> None:
            pass

        def poll(self, timeout: float) -> None:
            pass

        def flush(self, timeout: float) -> int:
            self.flushes.append(timeout)
            return 0

    producer = _Producer()

    with KafkaEventPublisher(sink, producer_factory=lambda _: producer) as publisher:
        publisher.publish(DomainEvent(type="test", payload={}))
        assert len(producer.flushes) == 1  # immediate flush with batch_size=1

    # __exit__ should trigger close() and final flush
    assert len(producer.flushes) == 2
    assert producer.flushes[1] == 30.0


def test_kafka_event_publisher_raises_when_closed() -> None:
    sink = KafkaEventSink(topic="events", bootstrap_servers="kafka:9092")

    class _Producer:
        def produce(self, **kwargs: object) -> None:
            pass

        def poll(self, timeout: float) -> None:
            pass

        def flush(self, timeout: float) -> int:
            return 0

    publisher = KafkaEventPublisher(sink, producer_factory=lambda _: _Producer())
    publisher.close()

    with pytest.raises(RuntimeError, match="Publisher is closed"):
        publisher.publish(DomainEvent(type="test", payload={}))


def test_kafka_event_publisher_flush_when_closed_is_noop() -> None:
    sink = KafkaEventSink(topic="events", bootstrap_servers="kafka:9092")

    class _Producer:
        def __init__(self) -> None:
            self.flushes: list[float] = []

        def produce(self, **kwargs: object) -> None:
            pass

        def poll(self, timeout: float) -> None:
            pass

        def flush(self, timeout: float) -> int:
            self.flushes.append(timeout)
            return 0

    producer = _Producer()
    publisher = KafkaEventPublisher(sink, producer_factory=lambda _: producer)
    publisher.close()

    # flush() after close should be a no-op
    publisher.flush()
    assert len(producer.flushes) == 1  # Only the close() flush


def test_kafka_event_publisher_close_is_idempotent() -> None:
    sink = KafkaEventSink(topic="events", bootstrap_servers="kafka:9092")

    class _Producer:
        def __init__(self) -> None:
            self.flushes: list[float] = []

        def produce(self, **kwargs: object) -> None:
            pass

        def poll(self, timeout: float) -> None:
            pass

        def flush(self, timeout: float) -> int:
            self.flushes.append(timeout)
            return 0

    producer = _Producer()
    publisher = KafkaEventPublisher(sink, producer_factory=lambda _: producer)

    publisher.close()
    publisher.close()  # Second close should not flush again

    assert len(producer.flushes) == 1


# === Redis Stream Additional Tests ===


def test_redis_stream_event_publisher_without_maxlen() -> None:
    sink = RedisStreamEventSink(stream="events", redis_url="redis://redis:6379/0", maxlen=None)

    class _Client:
        def __init__(self) -> None:
            self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def xadd(self, *args: object, **kwargs: object) -> str:
            self.calls.append((args, kwargs))
            return "0-1"

    client = _Client()
    publisher = RedisStreamEventPublisher(sink, redis_client=client)
    publisher.publish(DomainEvent(type="test", payload={}))

    assert len(client.calls) == 1
    _, kwargs = client.calls[0]
    assert kwargs == {}  # No maxlen arguments when maxlen is None
