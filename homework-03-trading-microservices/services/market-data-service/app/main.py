import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from shared.trading_shared.bottle_server import run_server
from shared.trading_shared.logging_config import configure_logging
from shared.trading_shared.audit import log_audit_error, AuditEventType

from api import MarketDataApi, LatestValues
from config import HOST, PORT, TICK_INTERVAL, DB_PUSH_INTERVAL, RATES_REFRESH_TICKS, SERVICE_NAME
from generator import (
    EventIdSequence,
    EquityMarketDataGenerator,
    FixedIncomeMarketDataGenerator,
    ForexMarketDataGenerator,
    CommodityMarketDataGenerator,
    FuturesMarketDataGenerator,
    EUOptionMarketDataGenerator,
    MarketIndexGenerator,
    InterestRates,
    CurveGenerator,
)
from publisher import Publisher
from persistence import Persistence

from concurrent.futures import ThreadPoolExecutor

import threading
import structlog

log = structlog.get_logger()

# Docker kills the container 10 s after SIGTERM; joins must finish well before that
JOIN_TIMEOUT = 3


def market_data_service(generators, publisher, persistence, latest_data: LatestValues, stop: threading.Event, refresh_rates):
    rounds = 0
    with ThreadPoolExecutor(max_workers=len(generators)) as executor:
        while not stop.is_set():
            tasks = [executor.submit(g.generate) for g in generators]

            for task in tasks:
                try:
                    data = task.result()
                    publisher.publish_data(data)
                    latest_data.put(data["symbol"], data)
                    persistence.add_ticks(data)
                    persistence.add_snapshot(data)
                except Exception:
                    log.exception("error_generating_market_data")

            rounds += 1
            if RATES_REFRESH_TICKS and rounds % RATES_REFRESH_TICKS == 0:
                try:
                    refresh_rates()
                except Exception:
                    log.exception("error_refreshing_rates")
            stop.wait(TICK_INTERVAL)


def push_all(persistence):
    try:
        persistence.push_ticks()
        persistence.push_snapshots()
        persistence.push_curves()
    except Exception:
        log_audit_error(log, AuditEventType.DB_PUSH_ERROR, "Error pushing market data to DB", exc_info=True)


def push_data_to_db(persistence, stop: threading.Event):
    while not stop.wait(DB_PUSH_INTERVAL):
        push_all(persistence)
    push_all(persistence)  # final flush on shutdown


def refresh_curves(curve_generator, persistence, publisher, latest_curves: LatestValues, shift_rates=False, push_now=True):
    """push_now=False leaves the DB write to the db-push thread (used from the tick loop)"""
    curves = curve_generator.generate(shift_rates=shift_rates)
    for curve in curves:
        persistence.add_curve(curve)
        latest_curves.put(curve["curve_name"], curve)
        publisher.publish_data(curve)
    if push_now:
        persistence.push_curves()
    return curves


if __name__ == '__main__':
    configure_logging(SERVICE_NAME)
    stop = threading.Event()
    latest_data = LatestValues()
    latest_curves = LatestValues()

    publisher = Publisher()
    persistence = Persistence()
    ids = EventIdSequence.from_db(persistence)
    rates = InterestRates.from_db(persistence)
    fx_generator = ForexMarketDataGenerator(ids, persistence, rates)
    bond_generator = FixedIncomeMarketDataGenerator(ids, persistence)
    generators = [
        EquityMarketDataGenerator(ids, persistence),
        bond_generator,
        fx_generator,
        CommodityMarketDataGenerator(ids, persistence),
        FuturesMarketDataGenerator(ids, persistence),
        EUOptionMarketDataGenerator(ids, persistence),
        MarketIndexGenerator(ids, persistence),
    ]
    curve_generator = CurveGenerator(ids, rates, bond_generator)

    refresh_curves(curve_generator, persistence, publisher, latest_curves)
    app = MarketDataApi(
        publisher, latest_data, latest_curves,
        refresh_curves=lambda: refresh_curves(curve_generator, persistence, publisher, latest_curves, shift_rates=True),
        get_history=persistence.get_history,
    )

    threads = [
        threading.Thread(
            target=market_data_service,
            args=(generators, publisher, persistence, latest_data, stop,
                  lambda: refresh_curves(curve_generator, persistence, publisher, latest_curves, shift_rates=True, push_now=False)),
            name="market-ticks", daemon=True,
        ),
        threading.Thread(target=push_data_to_db, args=(persistence, stop), name="db-push", daemon=True),
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
        log.info("service_stopped")
