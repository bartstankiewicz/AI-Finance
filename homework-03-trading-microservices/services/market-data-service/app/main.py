import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from shared.trading_shared.bottle_server import run_server

from api import MarketDataApi
from config import HOST, PORT, TICK_INTERVAL, SERVICE_NAME
from generator import (
    EventIdSequence,
    EquityMarketDataGenerator,
    FixedIncomeMarketDataGenerator,
    ForexMarketDataGenerator,
    CommodityMarketDataGenerator,
    FuturesMarketDataGenerator,
    EUOptionMarketDataGenerator,
    CurveGenerator,
)
from publisher import Publisher
from persistence import Persistence

from concurrent.futures import ThreadPoolExecutor

import time
import threading
import structlog

log = structlog.get_logger().bind(service=SERVICE_NAME)


def market_data_service(generators, executor, publisher, persistence, latest_data: dict):
    while True:
        tasks = [executor.submit(g.generate) for g in generators]

        for task in tasks:
            try:
                data = task.result()
                publisher.publish_data(data)
                latest_data[data["symbol"]] = data
                persistence.add_ticks(data)
                persistence.add_snapshot(data)
            except Exception:
                log.exception("error_generating_market_data")

        time.sleep(TICK_INTERVAL)

def push_data_to_db(persistence):
    while True:
        try:
            persistence.push_ticks()
            persistence.push_snapshots()
            persistence.push_curves()
        except Exception:
            log.exception("error_pushing_data_to_db")
        time.sleep(10)


def refresh_curves(curve_generator, persistence, publisher, latest_curves: dict):
    curves = curve_generator.generate()
    for curve in curves:
        persistence.add_curve(curve)
        latest_curves[curve["curve_name"]] = curve
        publisher.publish_data(curve)
    persistence.push_curves()
    return curves


if __name__ == '__main__':
    latest_data = {}
    latest_curves = {}

    publisher = Publisher()
    persistence = Persistence()
    ids = EventIdSequence(persistence.get_last_event_id())
    fx_generator = ForexMarketDataGenerator(ids)
    generators = [
        EquityMarketDataGenerator(ids),
        FixedIncomeMarketDataGenerator(ids),
        fx_generator,
        CommodityMarketDataGenerator(ids),
        FuturesMarketDataGenerator(ids),
        EUOptionMarketDataGenerator(ids),
    ]
    curve_generator = CurveGenerator(ids, fx_generator)
    executor = ThreadPoolExecutor(max_workers=len(generators))

    refresh_curves(curve_generator, persistence, publisher, latest_curves)
    app = MarketDataApi(
        publisher, latest_data, latest_curves,
        refresh_curves=lambda: refresh_curves(curve_generator, persistence, publisher, latest_curves),
        get_history=persistence.get_history,
    )

    thread_market_ticks = threading.Thread(target=market_data_service, args=(generators, executor, publisher, persistence, latest_data), daemon=True)
    thread_market_ticks.start()

    thread_snapshot = threading.Thread(target=push_data_to_db, args=(persistence,), daemon=True)
    thread_snapshot.start()

    log.info("service_started", host=HOST, port=PORT)
    run_server(app, host=HOST, port=PORT)
