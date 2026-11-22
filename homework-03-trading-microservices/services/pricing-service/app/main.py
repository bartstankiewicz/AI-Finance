import sys
import threading
import structlog
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from shared.trading_shared.bottle_server import run_server
from shared.trading_shared.logging_config import configure_logging
from shared.trading_shared.audit import log_audit_error, AuditEventType

from api import PricingServiceApi
from valuation_publisher import ValuationPublisher
from market_data_client import MarketDataClient
from persistence import Persistence
from valuation_engine import ValuationEngine
from pnl_quotes import PnLServices, PNL_SERVICES
from book_metrics import BookMetrics
from config import (
    HOST, PORT, VALUATION_INTERVAL, SERVICE_NAME,
    BENCHMARK_SYMBOL, ALPHA_BETA_WINDOW,
)

log = structlog.get_logger()


ASSET_CLASSES = list(PNL_SERVICES)

DB_PUSH_INTERVAL = 10

# Docker kills the container 10 s after SIGTERM; joins must finish well before that
JOIN_TIMEOUT = 3
TICK_WAIT_TIMEOUT = 1.0


def attach_alpha_beta(book_metrics, valuations):
    """Set the latest alpha / beta of each valuation's book (None until the rolling window is full)"""
    alpha_beta = book_metrics.alpha_beta_by_book()
    for valuation in valuations:
        valuation["alpha"], valuation["beta"] = alpha_beta.get(valuation["book_id"], (None, None))
    return valuations


def publish_valuations(publisher, valuations):
    for valuation in valuations:
        publisher.publish_data(valuation)


def pricing_service_active_trades(pnl_services, persistence, publisher, book_metrics, market_data_client, executor, stop):
    while not stop.is_set():
        if not market_data_client.wait_for_tick(TICK_WAIT_TIMEOUT):
            continue
        tasks = {asset_class: executor.submit(pnl_services.calculate_active, asset_class) for asset_class in ASSET_CLASSES}
        cycle_valuations = []
        for asset_class, task in tasks.items():
            try:
                cycle_valuations.extend(task.result())
            except Exception:
                log.exception("Error processing active trades", asset_class=asset_class)
        try:
            book_metrics.update(cycle_valuations)
        except Exception:
            log.exception("Error updating book metrics")
        for valuation in attach_alpha_beta(book_metrics, cycle_valuations):
            persistence.add_valuation(valuation)
        publish_valuations(publisher, cycle_valuations)


def pricing_service_close_trades(pnl_services, publisher, book_metrics, executor, stop):
    while not stop.is_set():
        alpha_beta = book_metrics.alpha_beta_by_book()
        tasks = {asset_class: executor.submit(pnl_services.calculate_closed_positions, asset_class, alpha_beta) for asset_class in ASSET_CLASSES}
        for asset_class, task in tasks.items():
            try:
                publish_valuations(publisher, task.result())
            except Exception:
                log.exception("Error processing closed trades", asset_class=asset_class)
        stop.wait(VALUATION_INTERVAL)


def push_valuations(persistence):
    try:
        persistence.push_valuations()
    except Exception:
        log_audit_error(log, AuditEventType.DB_PUSH_ERROR, "Error pushing valuations to DB", exc_info=True)


def push_to_db(persistence, stop):
    while not stop.wait(DB_PUSH_INTERVAL):
        push_valuations(persistence)
    push_valuations(persistence)  # final flush on shutdown


if __name__ == '__main__':
    configure_logging(SERVICE_NAME)
    stop = threading.Event()
    publisher = ValuationPublisher()
    persistence = Persistence()
    market_data_client = MarketDataClient()
    valuation_engine = ValuationEngine(persistence, market_data_client)
    pnl_services = PnLServices(valuation_engine)
    book_metrics = BookMetrics(valuation_engine, BENCHMARK_SYMBOL, ALPHA_BETA_WINDOW)
    app = PricingServiceApi(publisher, valuation_engine, book_metrics)

    market_data_client.start()

    executor = ThreadPoolExecutor(max_workers=len(ASSET_CLASSES))
    threads = [
        threading.Thread(target=pricing_service_active_trades, args=(pnl_services, persistence, publisher, book_metrics, market_data_client, executor, stop), name="valuation-active", daemon=True),
        threading.Thread(target=pricing_service_close_trades, args=(pnl_services, publisher, book_metrics, executor, stop), name="valuation-closed", daemon=True),
        threading.Thread(target=push_to_db, args=(persistence, stop), name="db-push", daemon=True),
    ]
    for thread in threads:
        thread.start()

    log.info("service_started", host=HOST, port=PORT)
    try:
        run_server(app, host=HOST, port=PORT)
    finally:
        log.info("service_stopping")
        stop.set()
        for thread in threads:
            thread.join(timeout=JOIN_TIMEOUT)
        executor.shutdown(wait=False, cancel_futures=True)
        log.info("service_stopped")