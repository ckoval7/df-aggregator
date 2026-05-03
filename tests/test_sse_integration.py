"""End-to-end SSE integration test.

Spins up a Bottle app under waitress in a thread, subscribes via streaming
HTTP using stdlib urllib, publishes a frame, and asserts the SSE-framed event
arrives over the wire.
"""
import threading
import time
import urllib.request

import pytest
from bottle import Bottle, response

from sse_broker import Broker
from web import GzipMiddleware


@pytest.fixture
def server():
    from waitress import create_server

    app = Bottle()
    broker = Broker(heartbeat_interval_s=3600)

    @app.get("/events")
    def events():
        response.content_type = "text/event-stream"
        response.set_header("Cache-Control", "no-cache")
        ch = broker.subscribe()

        def gen():
            try:
                while True:
                    frame = ch.get(timeout=None)
                    yield (
                        f"event: {frame.event_type}\n"
                        f"data: {frame.data_json}\n\n"
                    )
            finally:
                broker.unsubscribe(ch)

        return gen()

    srv = create_server(GzipMiddleware(app), host="127.0.0.1", port=0, threads=4)
    port = srv.effective_port
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    yield broker, port
    srv.close()
    broker.shutdown()


def test_publish_reaches_http_subscriber(server):
    broker, port = server

    def _pub():
        time.sleep(0.2)
        broker.publish("rx_config", {"hello": "world"})

    threading.Thread(target=_pub, daemon=True).start()

    req = urllib.request.Request(f"http://127.0.0.1:{port}/events")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200

        deadline = time.time() + 3.0
        seen_event = None
        seen_data = None
        # Read line-by-line. SSE frames are terminated by a blank line, but
        # we just need to find an "event: rx_config" / "data: ..." pair.
        while time.time() < deadline:
            raw = resp.readline()
            if not raw:
                break
            line = raw.decode("utf-8").rstrip("\n")
            if line.startswith("event:"):
                seen_event = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and seen_event == "rx_config":
                seen_data = line.split(":", 1)[1].strip()
                break

    import json
    assert seen_event == "rx_config"
    assert seen_data is not None
    assert json.loads(seen_data) == {"hello": "world"}
