import json
import queue
import threading
from collections import deque
import structlog

RECENT_ACTIONS = 50


class ActionPublisher:
    def __init__(self):
        self.log = structlog.get_logger()
        self.subscribers = []
        self.recent = deque(maxlen=RECENT_ACTIONS)
        self.lock = threading.Lock()

    def publish(self, action):
        with self.lock:
            self.recent.append(action)
            subscribers = list(self.subscribers)
        for subscriber in subscribers:
            subscriber.put(action)

    def stream_events(self):
        """SSE event generator - replay recent actions, then live ones; unsubscribe on disconnect"""
        client_queue = queue.Queue()
        with self.lock:
            self.subscribers.append(client_queue)
            initial_events = list(self.recent)
        self.log.info("client_subscribed", active_clients=len(self.subscribers))
        try:
            yield b": connected\n\n"
            for event in initial_events:
                yield f"data: {json.dumps(event)}\n\n".encode('utf-8')
            while True:
                try:
                    event = client_queue.get(timeout=30)
                    yield f"data: {json.dumps(event)}\n\n".encode('utf-8')
                except queue.Empty:
                    yield b": heartbeat\n\n"
        finally:
            with self.lock:
                self.subscribers.remove(client_queue)
            self.log.info("client_disconnected", active_clients=len(self.subscribers))
