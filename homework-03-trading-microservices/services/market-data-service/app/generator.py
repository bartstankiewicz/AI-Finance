import random
import threading
import datetime
import structlog
from config import SERVICE_NAME

# Rates curve (bonds, IRS) - tenors in years; yearly points up to 5Y cover annual IRS payments
RATE_TENORS = {"1Y": 1, "2Y": 2, "3Y": 3, "4Y": 4, "5Y": 5, "7Y": 7, "10Y": 10, "20Y": 20, "30Y": 30}
USD_BASE_RATES = [0.038, 0.040, 0.041, 0.0415, 0.042, 0.0425, 0.043, 0.044, 0.045]

# FX forward curve - tenors in months
FX_TENORS = {"1M": 1 / 12, "3M": 0.25, "6M": 0.5, "9M": 0.75, "1Y": 1.0}

class Generator:
    def __init__(self, event_id):
        self.log = structlog.get_logger().bind(service=SERVICE_NAME)
        self.last_equity_price = 100.0
        self.last_fixed_income_price = 100.0
        self.last_forex_spot = 1.2
        self.last_commodity_price = 2000.0
        self.last_futures_price = 100.0
        self.event_id = event_id
        self.lock = threading.Lock()

    def next_event_id(self):
        """Generate the next event ID in a thread-safe manner"""
        with self.lock:
            self.event_id += 1
            return self.event_id

    def generate_tick(self, last_price, asset_class):
        """Generate a new tick based on the last price"""
        decimal_places = 4 if asset_class in ["FOREX"] else 2

        ticks = round(random.uniform(-0.01, 0.01), 4)
        actual_price = round(last_price * (1 + ticks), decimal_places)
        half_spread = round(actual_price * random.uniform(0.0002, 0.001) / 2, decimal_places)
        bid = round(actual_price - half_spread, decimal_places)
        ask = round(actual_price + half_spread, decimal_places)
        mid = round((bid + ask) / 2, decimal_places)

        return actual_price, bid, ask, mid

    def generate_equity_data(self):
        """Generate equity market data"""
        actual_price, bid, ask, mid = self.generate_tick(self.last_equity_price, "EQUITY")
        last_event_time = datetime.datetime.now().isoformat()

        data = {
            "event_id": self.next_event_id(),
            "timestamp": last_event_time,
            "asset_class": "EQUITY",
            "symbol": "ACME",
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "spot": actual_price,
            "last": self.last_equity_price,
            "currency": "USD",
            "snapshot_type": "EQUITY_DATA_SNAPSHOT",
            "snapshot_time": last_event_time
        }
        self.last_equity_price = actual_price
        self.log.info("generated_equity_data", data=data)
        return data

    def generate_fixed_income_data(self):
        """Generate fixed income market data"""
        yield_rate = round(random.uniform(0.03, 0.06), 3)
        actual_price, bid, ask, mid = self.generate_tick(self.last_fixed_income_price, "FIXED_INCOME")
        last_event_time = datetime.datetime.now().isoformat()

        data = {
            "event_id": self.next_event_id(),
            "timestamp": last_event_time,
            "asset_class": "FIXED_INCOME",
            "symbol": "GOVT",
            "yield": yield_rate,
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "spot": actual_price,
            "last": self.last_fixed_income_price,
            "currency": "USD",
            "snapshot_type": "FIXED_INCOME_DATA_SNAPSHOT",
            "snapshot_time": last_event_time
        }
        self.last_fixed_income_price = actual_price
        self.log.info("generated_fixed_income_data", data=data)
        return data

    def generate_forex_data(self):
        """Generate forex market data"""
        domestic_rate = round(random.uniform(0.01, 0.05), 4)
        foreign_rate = round(random.uniform(0.01, 0.05), 4)
        actual_price, bid, ask, mid = self.generate_tick(self.last_forex_spot, "FOREX")
        last_event_time = datetime.datetime.now().isoformat()

        data = {
            "event_id": self.next_event_id(),
            "timestamp": last_event_time,
            "asset_class": "FOREX",
            "symbol": "EUR/USD",
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "spot": actual_price,
            "last": self.last_forex_spot,
            "domestic_rate": domestic_rate,
            "foreign_rate": foreign_rate,
            "currency": "USD",
            "snapshot_type": "FOREX_DATA_SNAPSHOT",
            "snapshot_time": last_event_time
        }
        self.last_forex_spot = actual_price
        self.log.info("generated_forex_data", data=data)
        return data

    def generate_commodity_data(self):
        """Generate commodity market data"""
        actual_price, bid, ask, mid = self.generate_tick(self.last_commodity_price, "COMMODITY")
        last_event_time = datetime.datetime.now().isoformat()

        data = {
            "event_id": self.next_event_id(),
            "timestamp": last_event_time,
            "asset_class": "COMMODITY",
            "symbol": "XAU/USD",
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "spot": actual_price,
            "last": self.last_commodity_price,
            "currency": "USD",
            "snapshot_type": "COMMODITY_DATA_SNAPSHOT",
            "snapshot_time": last_event_time
        }
        self.last_commodity_price = actual_price
        self.log.info("generated_commodity_data", data=data)
        return data

    def generate_futures_data(self):
        """Generate futures market data"""
        actual_price, bid, ask, mid = self.generate_tick(self.last_futures_price, "FUTURES")
        last_event_time = datetime.datetime.now().isoformat()

        data = {
            "event_id": self.next_event_id(),
            "timestamp": last_event_time,
            "asset_class": "FUTURES",
            "symbol": "OIL",
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "spot": actual_price,
            "last": self.last_futures_price,
            "currency": "USD",
            "snapshot_type": "FUTURES_DATA_SNAPSHOT",
            "snapshot_time": last_event_time
        }
        self.last_futures_price = actual_price
        self.log.info("generated_futures_data", data=data)
        return data

    def build_curve(self, curve_name, curve_type, currency, tenors: dict, rates, event_time, **extra):
        return {
            "event_type": "CURVE",
            "event_id": self.next_event_id(),
            "timestamp": event_time,
            "curve_name": curve_name,
            "curve_type": curve_type,
            "currency": currency,
            "tenors": list(tenors.keys()),
            "year_fractions": [round(t, 6) for t in tenors.values()],
            "rates": rates,
            **extra,
        }

    def generate_curves(self):
        """Generate USD yield/discount curves and EUR/USD forward curve (on startup / on demand)"""
        event_time = datetime.datetime.now().isoformat()

        shift = random.uniform(-0.005, 0.005)
        yields = [round(r + shift, 5) for r in USD_BASE_RATES]

        discount_factors = [round(1 / (1 + r) ** t, 6) for r, t in zip(yields, RATE_TENORS.values())]

        spot = self.last_forex_spot
        domestic_rate = round(random.uniform(0.01, 0.05), 4)
        foreign_rate = round(random.uniform(0.01, 0.05), 4)

        forwards = [
            round(spot * (1 + domestic_rate * t) / (1 + foreign_rate * t), 5)
            for t in FX_TENORS.values()
        ]

        curves = [
            self.build_curve(
                "USD_YIELD", "YIELD_CURVE", "USD", RATE_TENORS, yields, event_time,
                compounding="ANNUAL",
            ),
            self.build_curve(
                "USD_DISCOUNT", "DISCOUNT_CURVE", "USD", RATE_TENORS, discount_factors, event_time,
                compounding="ANNUAL", source_curve="USD_YIELD",
            ),
            self.build_curve(
                "EUR/USD_FWD", "FX_FORWARD_CURVE", "USD", FX_TENORS, forwards, event_time,
                pair="EUR/USD", spot=spot, domestic_rate=domestic_rate, foreign_rate=foreign_rate,
                forward_points=[round((f - spot) * 10000, 1) for f in forwards],
            ),
        ]

        self.log.info("generated_curves", curves=[c["curve_name"] for c in curves])
        return curves
