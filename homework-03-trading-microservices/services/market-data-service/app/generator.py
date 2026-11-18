import random
import threading
import datetime
import structlog
from config import SERVICE_NAME
from persistence import Persistence

# Curve tenors in years; yearly points cover annual IRS payments
RATE_TENORS = {f"{year}Y": float(year) for year in range(1, 11)}
# Initial interest rate per currency (annual compounding), used when DB has no FX tick yet
INITIAL_RATES = {"USD": 0.042, "EUR": 0.027}
# USD zero-yield spread over the GOVT tick yield per tenor: upward sloping, flattening at the long end
USD_YIELD_SPREADS = {
    "1Y": 0.0020, "2Y": 0.0040, "3Y": 0.0055, "4Y": 0.0067, "5Y": 0.0077,
    "6Y": 0.0085, "7Y": 0.0092, "8Y": 0.0098, "9Y": 0.0103, "10Y": 0.0107,
}


def curve_name(currency: str, kind: str) -> str:
    """e.g. ("USD", "DISCOUNT") -> USD_DISCOUNT"""
    return f"{currency}_{kind}"


class InterestRates:
    """Current interest rates per currency - single source for FX tick rates and USD curves.
    A currency is either flat (single rate, moved by shift()) or curve-driven (zero yields per tenor set by
    set_zero_curve(); its single rate is the shortest zero yield). Both change only on curve refresh.
    """
    compounding = "ANNUAL"
    step_std = 0.0005  # ~5bp per shift
    rate_low, rate_high = 0.0, 0.10

    def __init__(self, initial_rates: dict = INITIAL_RATES):
        self._lock = threading.Lock()
        self._rates = dict(initial_rates)
        self._zero_curves: dict[str, dict[float, float]] = {}

    @classmethod
    def from_db(cls, db: Persistence) -> "InterestRates":
        """Continue from the rates of the last persisted FX tick, so a restart does not move rates"""
        rates = cls()
        symbol = ForexMarketDataGenerator.symbol
        last_fx = db.get_last_quote(symbol) or {}
        foreign, domestic = symbol.split("/")
        for currency, field in ((domestic, "domestic_rate"), (foreign, "foreign_rate")):
            if last_fx.get(field) is not None:
                rates._rates[currency] = last_fx[field]
        return rates

    @property
    def currencies(self) -> list[str]:
        return list(self._rates)

    def shift(self) -> None:
        """One random-walk step per flat currency; curve-driven currencies move only via set_zero_curve"""
        with self._lock:
            for currency, rate in self._rates.items():
                if currency not in self._zero_curves:
                    self._rates[currency] = _bounded_walk(rate, self.step_std, self.rate_low, self.rate_high, decimals=5)

    def set_zero_curve(self, currency: str, zero_yields: dict[float, float]) -> None:
        """zero_yields: year fraction -> annually compounded zero yield"""
        with self._lock:
            self._zero_curves[currency] = dict(sorted(zero_yields.items()))
            self._rates[currency] = self._zero_curves[currency][min(zero_yields)]

    def rate(self, currency: str) -> float:
        with self._lock:
            return self._rates[currency]

    def zero_rate(self, currency: str, t: float) -> float:
        """Linear interpolation of zero yields, flat outside the curve; flat currencies return their single rate"""
        with self._lock:
            curve = self._zero_curves.get(currency)
            if not curve:
                return self._rates[currency]
            times = list(curve)
            if t <= times[0]:
                return curve[times[0]]
            if t >= times[-1]:
                return curve[times[-1]]
            for t0, t1 in zip(times, times[1:]):
                if t0 <= t <= t1:
                    return curve[t0] + (curve[t1] - curve[t0]) * (t - t0) / (t1 - t0)

    def discount_factor(self, currency: str, t: float) -> float:
        return 1 / (1 + self.zero_rate(currency, t)) ** t


def _bounded_walk(value: float, step_std: float, low: float, high: float, decimals: int = 4) -> float:
    return round(min(max(value + random.gauss(0, step_std), low), high), decimals)


class EventIdSequence:
    def __init__(self, start: int):
        self._value = start
        self._lock = threading.Lock()

    @classmethod
    def from_db(cls, db: Persistence) -> "EventIdSequence":
        return cls(db.get_last_event_id())

    def __iter__(self):
        return self

    def __next__(self) -> int:
        with self._lock:
            self._value += 1
            return self._value


class MarketDataGenerator:
    asset_class: str
    symbol: str
    currency = "USD"
    initial_price = 0.0
    decimal_places = 2

    def __init__(self, ids: EventIdSequence, db: Persistence):
        self.event_id = ids
        self.log = structlog.get_logger().bind(asset_class=self.asset_class)
        self._restore_state(db.get_last_quote(self.symbol) or {})

    @property
    def snapshot_type(self) -> str:
        return f"{self.asset_class}_DATA_SNAPSHOT"

    def generate(self) -> dict:
        quote = self._build_quote(self._event_time())
        self._log_validation_errors(quote)
        self.log.info("generated_market_data", data=quote)
        return quote

    def _restore_state(self, last_quote: dict) -> None:
        """Continue the random walk from the last persisted quote instead of the initial value"""
        self.last_price = last_quote.get("spot") or self.initial_price

    def _build_quote(self, event_time: str) -> dict:
        return {
            "event_id": next(self.event_id),
            "timestamp": event_time,
            "asset_class": self.asset_class,
            "symbol": self.symbol,
            "currency": self.currency,
            **self._price_fields(),
            **self._extra_fields(),
            "snapshot_type": self.snapshot_type,
            "snapshot_time": event_time,
        }

    def _price_fields(self) -> dict:
        """Default: random-walk price quoted in currency"""
        price = self._next_price()
        fields = {**self._two_sided_quote(price), "spot": price, "last": self.last_price}
        self.last_price = price
        return fields

    def _next_price(self) -> float:
        return round(self.last_price * (1 + random.uniform(-0.01, 0.01)), self.decimal_places)

    def _two_sided_quote(self, price: float) -> dict:
        dp = self.decimal_places
        half_spread = round(price * random.uniform(0.0002, 0.001) / 2, dp)
        bid = round(price - half_spread, dp)
        ask = round(price + half_spread, dp)
        return {"bid": bid, "ask": ask, "mid": round((bid + ask) / 2, dp)}

    def _extra_fields(self) -> dict:
        return {}

    def _log_validation_errors(self, quote: dict) -> None:
        errors = self._validate_quote(quote)
        if errors:
            self.log.error("invalid_quote", errors=errors)

    @staticmethod
    def _validate_quote(quote) -> list[str]:
        # Not every instrument has a two-sided quote (bond, option)
        if "bid" not in quote or "ask" not in quote:
            return []

        errors = []
        if quote["bid"] <= 0:
            errors.append("Bid must be positive")
        if quote["ask"] <= 0:
            errors.append("Ask must be positive")
        if quote["bid"] > quote["ask"]:
            errors.append("Bid cannot be greater than ask")
        return errors

    @staticmethod
    def _event_time() -> str:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()


class EquityMarketDataGenerator(MarketDataGenerator):
    asset_class = "EQUITY"
    symbol = "ACME"
    initial_price = 100.0


class FixedIncomeMarketDataGenerator(MarketDataGenerator):
    """Bond market inputs: face value + yield; PV (fair value) is computed in pricing-service"""
    asset_class = "FIXED_INCOME"
    symbol = "GOVT"
    currency = "PERCENT_OF_PAR"
    initial_price = 100.0
    initial_yield = 0.043
    # Small per-tick step: the USD curves are rebuilt from this yield only every RATES_REFRESH_TICKS
    yield_step = 0.00002

    def _restore_state(self, last_quote: dict) -> None:
        self.last_price = last_quote.get("face_value") or self.initial_price
        self.yield_rate = last_quote.get("yield") or self.initial_yield

    def _price_fields(self) -> dict:
        self.last_price = self._next_price()
        last_yield = self.yield_rate
        self.yield_rate = _bounded_walk(self.yield_rate, self.yield_step, 0.001, 0.15, decimals=5)
        return {"face_value": self.last_price, "yield": self.yield_rate, "last_yield": last_yield}


class ForexMarketDataGenerator(MarketDataGenerator):
    """Spot random walk; domestic/foreign rates are the current InterestRates of the pair currencies"""
    asset_class = "FOREX"
    symbol = "EUR/USD"
    initial_price = 1.2
    decimal_places = 4

    def __init__(self, ids: EventIdSequence, db: Persistence, rates: InterestRates):
        self.rates = rates
        self.foreign_currency, self.domestic_currency = self.symbol.split("/")
        super().__init__(ids, db)

    def _extra_fields(self) -> dict:
        return {
            "domestic_rate": self.rates.rate(self.domestic_currency),
            "foreign_rate": self.rates.rate(self.foreign_currency),
        }


class FuturesMarketDataGenerator(MarketDataGenerator):
    """Spot random walk + cost-of-carry futures price F = S * (1 + carry_rate * expiry_years); bid/ask quote F"""
    asset_class = "FUTURES"
    symbol = "OIL"
    initial_price = 100.0
    expiry_years = 0.5
    initial_carry_rate = 0.05
    carry_rate_step = 0.0002

    def _restore_state(self, last_quote: dict) -> None:
        super()._restore_state(last_quote)
        self.carry_rate = last_quote.get("carry_rate", self.initial_carry_rate)

    def _price_fields(self) -> dict:
        spot = self._next_price()
        self.carry_rate = _bounded_walk(self.carry_rate, self.carry_rate_step, 0.0, 0.10, decimals=5)
        futures_price = round(spot * (1 + self.carry_rate * self.expiry_years), self.decimal_places)
        fields = {
            **self._two_sided_quote(futures_price),
            "spot": spot,
            "last": self.last_price,
            "futures_price": futures_price,
            "carry_rate": self.carry_rate,
            "expiry_years": self.expiry_years,
        }
        self.last_price = spot
        return fields


class CommodityMarketDataGenerator(MarketDataGenerator):
    asset_class = "COMMODITY"
    symbol = "XAU/USD"
    initial_price = 2000.0


class MarketIndexGenerator(MarketDataGenerator):
    """Benchmark for book alpha/beta; starts at the SPX close of 2026-11-17"""
    asset_class = "MARKET_DATA_INDEX"
    symbol = "S&P500"
    initial_price = 7340.53


class EUOptionMarketDataGenerator(MarketDataGenerator):
    """Option-only inputs (sigma, q); pricing takes spot from the ACME tick and r from USD_DISCOUNT"""
    asset_class = "EUROPEAN_OPTION"
    underlying_symbol = EquityMarketDataGenerator.symbol
    symbol = f"{underlying_symbol}_EU_OPTION"
    long_run_volatility = 0.25
    initial_dividend_yield = 0.02

    def _restore_state(self, last_quote: dict) -> None:
        super()._restore_state(last_quote)
        self.volatility = last_quote.get("volatility") or self.long_run_volatility
        self.dividend_yield = last_quote.get("dividend_yield", self.initial_dividend_yield)

    def _price_fields(self) -> dict:
        return {}

    def _extra_fields(self) -> dict:
        pull = 0.05 * (self.long_run_volatility - self.volatility)
        self.volatility = _bounded_walk(self.volatility + pull, 0.005, 0.05, 1.0)
        self.dividend_yield = _bounded_walk(self.dividend_yield, 0.0002, 0.0, 0.10)
        return {
            "underlying_symbol": self.underlying_symbol,
            "volatility": self.volatility,
            "dividend_yield": self.dividend_yield,
        }

class CurveGenerator:
    """USD yield/discount/forward curves from the GOVT yield.
    USD zero yields = current GOVT tick yield + USD_YIELD_SPREADS; the 1Y point is also the USD rate in FX ticks.
    """
    yield_currency = "USD"

    def __init__(self, ids: EventIdSequence, rates: InterestRates, bond: FixedIncomeMarketDataGenerator):
        self.event_id = ids
        self.rates = rates
        self.bond = bond
        self.log = structlog.get_logger().bind(service=SERVICE_NAME)
        self._lock = threading.Lock()  # one refresh at a time: shift + build see the same rates

    def generate(self, shift_rates: bool = False) -> list[dict]:
        """Build all curves; shift_rates=True first moves the flat (EUR) rates one random-walk step"""
        with self._lock:
            if shift_rates:
                self.rates.shift()
            base_yield = self.bond.yield_rate
            self.rates.set_zero_curve(self.yield_currency, {
                RATE_TENORS[tenor]: round(base_yield + spread, 5) for tenor, spread in USD_YIELD_SPREADS.items()
            })
            event_time = MarketDataGenerator._event_time()
            curves = [
                self._yield_curve(base_yield, event_time),
                self._discount_curve(self.yield_currency, event_time),
                self._forward_rate_curve(self.yield_currency, event_time),
            ]
        self.log.info("generated_curves", curves=[c["curve_name"] for c in curves], rates_shifted=shift_rates,
                      base_yield=base_yield)
        return curves

    def _yield_curve(self, base_yield: float, event_time: str) -> dict:
        currency = self.yield_currency
        return self._build_curve(
            curve_name(currency, "YIELD"), "YIELD_CURVE", currency, RATE_TENORS,
            [round(self.rates.zero_rate(currency, t), 6) for t in RATE_TENORS.values()], event_time,
            base_symbol=self.bond.symbol, base_yield=base_yield,
            compounding=self.rates.compounding,
        )

    def _discount_curve(self, currency: str, event_time: str) -> dict:
        """DF(t) = (1 + z(t))^-t"""
        return self._build_curve(
            curve_name(currency, "DISCOUNT"), "DISCOUNT_CURVE", currency, RATE_TENORS,
            [round(self.rates.discount_factor(currency, t), 6) for t in RATE_TENORS.values()], event_time,
            rate=self.rates.rate(currency),
            compounding=self.rates.compounding,
        )

    def _forward_rate_curve(self, currency: str, event_time: str) -> dict:
        """Annual forward per [t_prev, t]: F = DF(t_prev) / DF(t) - 1; the first period equals the 1Y zero yield"""
        dfs = [self.rates.discount_factor(currency, t) for t in [0.0, *RATE_TENORS.values()]]
        forwards = [round(df0 / df1 - 1, 6) for df0, df1 in zip(dfs, dfs[1:])]
        return self._build_curve(
            curve_name(currency, "FORWARD"), "FORWARD_CURVE", currency, RATE_TENORS, forwards, event_time,
            discount_curve=curve_name(currency, "DISCOUNT"),
            compounding=self.rates.compounding,
        )

    def _build_curve(self, curve_name, curve_type, currency, tenors: dict, rates, event_time, **extra) -> dict:
        return {
            "event_type": "CURVE",
            "event_id": next(self.event_id),
            "timestamp": event_time,
            "curve_name": curve_name,
            "curve_type": curve_type,
            "currency": currency,
            "tenors": list(tenors.keys()),
            "year_fractions": [round(t, 6) for t in tenors.values()],
            "rates": rates,
            **extra,
        }
