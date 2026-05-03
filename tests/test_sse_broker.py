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
