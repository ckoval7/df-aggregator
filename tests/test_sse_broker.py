import json
import time

from sse_broker import Broker


def test_publish_then_subscribe_replays_last_snapshot():
    broker = Broker(heartbeat_interval_s=3600)  # effectively disable heartbeat
    broker.publish("rx_config", {"receivers": []})
    ch = broker.subscribe()
    try:
        frame = ch.get(timeout=1.0)
        assert frame.event_type == "rx_config"
        assert json.loads(frame.data_json) == {"receivers": []}
    finally:
        broker.unsubscribe(ch)
        broker.shutdown()


def test_subscribe_then_publish_delivers_frame():
    broker = Broker(heartbeat_interval_s=3600)
    ch = broker.subscribe()
    try:
        broker.publish("pipeline", {"db_intersections": 42})
        frame = ch.get(timeout=1.0)
        assert frame.event_type == "pipeline"
        assert json.loads(frame.data_json) == {"db_intersections": 42}
    finally:
        broker.unsubscribe(ch)
        broker.shutdown()


def test_unsubscribe_stops_delivery():
    broker = Broker(heartbeat_interval_s=3600)
    ch = broker.subscribe()
    broker.unsubscribe(ch)
    broker.publish("rx_config", {"receivers": []})
    # ch should now be empty (no snapshot was buffered before subscribe + only
    # post-unsubscribe publish happened).
    import queue as _q
    try:
        ch.get(timeout=0.1)
        raise AssertionError("Expected empty queue")
    except _q.Empty:
        pass
    broker.shutdown()


def test_overflow_drops_oldest_non_heartbeat():
    broker = Broker(heartbeat_interval_s=3600)
    ch = broker.subscribe()
    # Fill the queue past capacity (queue size = 64).
    for i in range(70):
        broker.publish("rx_telemetry", {"i": i})
    # Drain — we expect at most ~64 frames, and the earliest "i" should not be 0
    # (it should have been dropped to make room).
    seen = []
    import queue as _q
    while True:
        try:
            f = ch.get(timeout=0.05)
            seen.append(json.loads(f.data_json)["i"])
        except _q.Empty:
            break
    broker.unsubscribe(ch)
    broker.shutdown()
    assert len(seen) <= 64
    # The latest publish must be present.
    assert seen[-1] == 69
    # An early publish must have been dropped.
    assert 0 not in seen


def test_heartbeat_fires():
    broker = Broker(heartbeat_interval_s=0.05)
    ch = broker.subscribe()
    try:
        # Within 1s, several heartbeats should arrive.
        deadline = time.time() + 1.0
        beats = 0
        while time.time() < deadline and beats < 3:
            f = ch.get(timeout=0.5)
            if f.event_type == "heartbeat":
                beats += 1
        assert beats >= 3
    finally:
        broker.unsubscribe(ch)
        broker.shutdown()
