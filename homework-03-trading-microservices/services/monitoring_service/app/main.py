import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from concurrent.futures import ThreadPoolExecutor
from shared.trading_shared.bottle_server import run_server
from config import HOST, PORT, SERVICE_URLS, MONITORING_INTERVAL, SERVICE_NAME
from monitor import Monitor
from publisher import MonitorPublisher
from api import MonitoringServiceApi
import threading
import time
import structlog

log = structlog.get_logger().bind(service=SERVICE_NAME)


def monitoring_service(monitor, executor, publisher):
    service_names = list(SERVICE_URLS.keys())
    service_urls = list(SERVICE_URLS.values())

    while True:
        try:
            results = list(executor.map(monitor.check_service, service_names, service_urls))
            publisher.publish_data(dict(zip(service_names, results)))
        except Exception:
            log.exception("error_monitoring_services")

        time.sleep(MONITORING_INTERVAL)

if __name__ == '__main__':
    monitor = Monitor()
    publisher = MonitorPublisher()
    app = MonitoringServiceApi(monitor, publisher)
    executor = ThreadPoolExecutor(max_workers=len(SERVICE_URLS))

    thread = threading.Thread(target=monitoring_service, args=(monitor, executor, publisher), daemon=True)
    thread.start()

    log.info("service_started", host=HOST, port=PORT)
    run_server(app, host=HOST, port=PORT)