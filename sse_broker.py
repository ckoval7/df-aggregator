"""Server-Sent Events broker.

Owns the set of connected SSE clients. Producers call ``publish(event_type,
payload)``; the broker fans out to per-client bounded queues. Each event type
keeps its most recent payload so a fresh subscriber gets state immediately
instead of waiting for the next change.

Thread model: ``publish`` and ``subscribe``/``unsubscribe`` are safe to call
from any thread. A single daemon thread fans out heartbeat frames every
``heartbeat_interval_s`` seconds.
"""
from __future__ import annotations

import json
import logging
import queue
import threading

# ClientChannel.put_nowait reaches into queue.Queue internals to drop the oldest
# non-heartbeat frame on overflow (queue.Queue has no public "drop oldest" API).
# Assert at import that those private attributes still exist so a future Python
# upgrade fails loud instead of silently corrupting the counter.
_q_check = queue.Queue()
assert all(hasattr(_q_check, a) for a in ("mutex", "queue", "unfinished_tasks", "not_full")), (
    "queue.Queue internals changed — ClientChannel.put_nowait needs updating"
)
del _q_check
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Frame:
    event_type: str
    data_json: str


class ClientChannel:
    """Per-client bounded queue with overflow-drop policy.

    When the queue is full, the oldest non-heartbeat frame is dropped to make
    room. Heartbeats are never dropped — they are the liveness signal.
    """

    def __init__(self, queue_size: int = 64):
        self._q: queue.Queue[Frame] = queue.Queue(maxsize=queue_size)

    def get(self, timeout: Optional[float] = None) -> Frame:
        return self._q.get(timeout=timeout)

    def put_nowait(self, frame: Frame) -> None:
        try:
            self._q.put_nowait(frame)
            return
        except queue.Full:
            pass
        # Drain oldest non-heartbeat frame, then retry.
        try:
            with self._q.mutex:
                for i, existing in enumerate(list(self._q.queue)):
                    if existing.event_type != "heartbeat":
                        del self._q.queue[i]
                        # Manual decrement matches the del above. Not paired with task_done() —
                        # join() must not be called on this queue.
                        self._q.unfinished_tasks -= 1
                        self._q.not_full.notify()
                        break
            self._q.put_nowait(frame)
        except queue.Full:
            log.debug("SSE client queue full (no evictable non-heartbeat slot); dropping new frame")


class Broker:
    def __init__(self, heartbeat_interval_s: float = 10.0):
        self._lock = threading.Lock()
        self._clients: set[ClientChannel] = set()
        self._last: dict[str, Frame] = {}
        self._heartbeat_interval_s = heartbeat_interval_s
        self._stop = threading.Event()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, name="sse-heartbeat", daemon=True
        )
        self._heartbeat_thread.start()

    def publish(self, event_type: str, payload) -> None:
        try:
            data_json = json.dumps(payload, separators=(",", ":"))
        except (TypeError, ValueError):
            log.warning("SSE publish: payload not JSON-serializable for event %r", event_type)
            return
        frame = Frame(event_type=event_type, data_json=data_json)
        with self._lock:
            self._last[event_type] = frame
            clients = list(self._clients)
        for ch in clients:
            ch.put_nowait(frame)

    def subscribe(self) -> ClientChannel:
        ch = ClientChannel()
        with self._lock:
            self._clients.add(ch)
            snapshots = list(self._last.values())
        for frame in snapshots:
            ch.put_nowait(frame)
        return ch

    def unsubscribe(self, ch: ClientChannel) -> None:
        with self._lock:
            self._clients.discard(ch)

    def shutdown(self) -> None:
        self._stop.set()

    def _heartbeat_loop(self) -> None:
        hb = Frame(event_type="heartbeat", data_json="{}")
        while not self._stop.wait(self._heartbeat_interval_s):
            with self._lock:
                clients = list(self._clients)
            for ch in clients:
                ch.put_nowait(hb)
