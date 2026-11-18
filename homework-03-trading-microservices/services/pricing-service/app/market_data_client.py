import json
import urllib.request
import threading
import time
import structlog
from config import STREAM_URL, RECONNECTING_INTERVAL, TICK_SETTLE_TIME
from shared.trading_shared.audit import log_audit_error, AuditEventType

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
urllib.request.install_opener(opener)

class MarketDataClient:
    def __init__(self):
        self.log = structlog.get_logger()
        self.lock = threading.Lock()
        self.connection_status = "DISCONNECTED"
        self.cache = {}
        self.curves = {}
        self.tick_received = threading.Event()

    def start(self):
        """Start streaming thread"""
        threading.Thread(target=self.connect_to_market_data_stream, daemon=True).start()

    def log_stream_disconnected(self):
        """STREAM_ERROR goes to AuditLogs (via the log file); entity_id/entity_type are always the same here"""
        log_audit_error(self.log, AuditEventType.STREAM_ERROR, "Market data stream disconnected",
                        entity_type="Stream", entity_id=STREAM_URL)

    def connect_to_market_data_stream(self):
        """Connect to the market data stream and read events"""
        while True:
            try:
                request = urllib.request.Request(STREAM_URL, headers={'Accept': 'text/event-stream'})
                with urllib.request.urlopen(request, timeout=None) as response:
                    with self.lock:
                        previous_status = self.connection_status
                        self.connection_status = "CONNECTED"
                    self.log.info("connection_status_to_market_data_stream", status=self.connection_status)
                    if previous_status != "CONNECTED":
                        self.log.info("market_data_stream_connected", entity_type="Stream", entity_id=STREAM_URL)
                    self.read_events(response)
            except Exception:
                self.log.warning("connection_error_to_market_data_stream")
            finally:
                with self.lock:
                    previous_status = self.connection_status
                    self.connection_status = "DISCONNECTED"
                if previous_status != "DISCONNECTED":
                    self.log_stream_disconnected()
            time.sleep(RECONNECTING_INTERVAL)

    def read_events(self, received_data):
        """Reading events from market data stream and updating cache"""
        for line in received_data:
            line = line.decode('utf-8').strip()
            if not line.startswith('data: '):
                continue
            try:
                data = json.loads(line[6:])
            except json.JSONDecodeError:
                self.log.warning("invalid_market_data_event", line=line[:200])
                continue
            if data.get("event_type") == "CURVE":
                with self.lock:
                    self.curves[data["curve_name"]] = data
                continue
            symbol = data.get("symbol")
            if not symbol:
                continue
            with self.lock:
                self.cache[symbol] = data
            self.tick_received.set()

    def wait_for_tick(self, timeout):
        """True once new ticks arrived since the previous call; waits TICK_SETTLE_TIME so one call covers the whole round"""
        if not self.tick_received.wait(timeout):
            return False
        time.sleep(TICK_SETTLE_TIME)
        self.tick_received.clear()
        return True

    def get_price(self, symbol):
        """Get latest tick of a symbol"""
        with self.lock:
            return self.cache.get(symbol)

    def get_connection_status(self):
        with self.lock:
            return self.connection_status

    def get_curve(self, curve_name):
        """Get latest curve by name, e.g. USD_DISCOUNT"""
        with self.lock:
            return self.curves.get(curve_name)
