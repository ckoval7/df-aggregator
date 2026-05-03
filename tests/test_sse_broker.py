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
