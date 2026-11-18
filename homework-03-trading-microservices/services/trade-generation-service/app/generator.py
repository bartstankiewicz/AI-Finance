import random
import uuid
import datetime
import structlog


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _client_request_id() -> str:
    return f"req-{uuid.uuid4()}"


# Closed without close_price; pricing-service settles them at the model value
MODEL_PRICED_ASSET_CLASSES = ("IRS", "EUROPEAN_OPTION")


class TradeGenerator:
    """Base OPEN_TRADE payload generator for a single instrument; subclasses override class attributes / hooks"""
    asset_class: str
    symbol: str
    price_field = "mid"
    sides = ("BUY",)
    currency = "USD"
    max_quantity = 1000

    def __init__(self, market_data_client, book_client):
        self.market_data_client = market_data_client
        self.book_client = book_client
        self.log = structlog.get_logger().bind(asset_class=self.asset_class)

    @property
    def market_data_key(self) -> tuple:
        return self.asset_class, self.symbol

    def generate(self) -> dict | None:
        price = self._trade_price()
        if price is None:
            return None

        book = self.book_client.get_book_for_asset_class(self.asset_class)
        if not book:
            return None

        trade = self._build_trade(price, book["book_id"])
        self.log.info("generated_trade", data=trade)
        return trade

    def _trade_price(self) -> float | None:
        tick = self.market_data_client.get_price(self.market_data_key)
        return tick.get(self.price_field) if tick else None

    def _build_trade(self, price: float, book_id) -> dict:
        return {
            "asset_class": self.asset_class,
            **self._instrument_fields(price),
            "side": random.choice(self.sides),
            "quantity": random.randint(1, self.max_quantity),
            "trade_price": price,
            "trade_currency": self.currency,
            "book_id": book_id,
            "trade_date": _utc_now(),
        }

    def _instrument_fields(self, price: float) -> dict:
        return {"symbol": self.symbol, "instrument_id": self.symbol}


class EquityTradeGenerator(TradeGenerator):
    asset_class = "EQUITY"
    symbol = "ACME"
    sides = ("BUY", "SELL")


class FixedIncomeTradeGenerator(TradeGenerator):
    asset_class = "BOND"
    symbol = "GOVT"
    price_field = "face_value"


class ForexTradeGenerator(TradeGenerator):
    asset_class = "FX"
    symbol = "EUR/USD"


class CommodityTradeGenerator(TradeGenerator):
    asset_class = "COMMODITY"
    symbol = "XAU/USD"


class FuturesTradeGenerator(TradeGenerator):
    asset_class = "FUTURES"
    symbol = "OIL"
    price_field = "futures_price"


class EUOptionTradeGenerator(TradeGenerator):
    """Long European option on the equity underlying; premium (trade_price) = premium_rate * spot at inception.
    CALL strike 5-10% above spot, PUT strike 5-10% below (both OTM: bet on a rise / fall); always BUY.
    Fair value (Black-Scholes) is computed only in pricing-service.
    """
    asset_class = "EUROPEAN_OPTION"
    underlying_symbol = EquityTradeGenerator.symbol
    symbol = f"{underlying_symbol}_EU_OPTION"
    sides = ("BUY",)
    premium_rate = 0.04
    strike_direction = {"CALL": 1, "PUT": -1}
    strike_distance = (0.05, 0.10)
    maturities_years = (0.25, 0.5, 1.0)

    def generate(self) -> dict | None:
        underlying = self.market_data_client.get_price((EquityTradeGenerator.asset_class, self.underlying_symbol))
        option_tick = self.market_data_client.get_price((self.asset_class, self.symbol))
        if not (underlying and option_tick):
            self.log.warning("missing_market_data", underlying=bool(underlying), option_tick=bool(option_tick))
            return None

        book = self.book_client.get_book_for_asset_class(self.asset_class)
        if not book:
            return None

        spot = underlying["mid"]
        option_type = random.choice(tuple(self.strike_direction))
        distance = random.uniform(*self.strike_distance)
        strike = round(spot * (1 + self.strike_direction[option_type] * distance), 1)
        maturity_years = random.choice(self.maturities_years)
        trade = {
            "asset_class": self.asset_class,
            "symbol": self.symbol,
            "instrument_id": f"{self.underlying_symbol}_{option_type}_{strike}_{maturity_years}Y",
            "underlying_symbol": self.underlying_symbol,
            "option_type": option_type,
            "strike": strike,
            "maturity_years": maturity_years,
            "volatility": option_tick["volatility"],
            "side": random.choice(self.sides),
            "quantity": random.randint(1, self.max_quantity),
            "trade_price": round(spot * self.premium_rate, 4),
            "trade_currency": self.currency,
            "book_id": book["book_id"],
            "trade_date": _utc_now(),
        }
        self.log.info("generated_trade", data=trade, spot=spot)
        return trade


class IRSTradeGenerator(TradeGenerator):
    """USD swap with a contractual fixed rate set once at the schedule's inception par rate."""
    asset_class = "IRS"
    currency = "USD"
    curve_name = "USD_DISCOUNT"
    side_by_direction = {"PAY_FIXED": "BUY", "RECEIVE_FIXED": "SELL"}
    notionals = (1_000_000, 5_000_000, 10_000_000)
    maturities_years = (1, 2, 3, 5, 7, 10)
    payments_per_year_choices = (1, 2, 4)

    def generate(self) -> dict | None:
        curve = self.market_data_client.get_curve(self.curve_name)
        if not curve:
            self.log.warning("missing_curve", curve_name=self.curve_name)
            return None

        book = self.book_client.get_book_for_asset_class(self.asset_class)
        if not book:
            return None

        maturity_years = random.choice(self.maturities_years)
        payments_per_year = random.choice(self.payments_per_year_choices)
        direction = random.choice(tuple(self.side_by_direction))
        fixed_rate = self._par_rate(curve, maturity_years, payments_per_year)
        symbol = f"{self.currency}_IRS_{maturity_years}Y"
        trade = {
            "asset_class": self.asset_class,
            "symbol": symbol,
            "instrument_id": f"{symbol}_{payments_per_year}PA",
            "side": self.side_by_direction[direction],
            "quantity": 1,
            "trade_price": fixed_rate,
            "trade_currency": self.currency,
            "book_id": book["book_id"],
            "trade_date": _utc_now(),
            "notional": random.choice(self.notionals),
            "fixed_rate": fixed_rate,
            "maturity_years": maturity_years,
            "payments_per_year": payments_per_year,
            "direction": direction,
        }
        self.log.info("generated_trade", data=trade)
        return trade

    @classmethod
    def _par_rate(cls, curve: dict, maturity_years: int, payments_per_year: int) -> float:
        accrual = 1.0
        previous_df = 1.0
        floating_pv = 0.0
        annuity = 0.0
        for period_number in range(1, maturity_years * payments_per_year + 1):
            discount_factor = cls._discount_factor(curve, period_number / payments_per_year)
            forward_rate = (previous_df / discount_factor - 1) / accrual
            floating_pv += forward_rate * accrual * discount_factor
            annuity += accrual * discount_factor
            previous_df = discount_factor
        return floating_pv / annuity

    @staticmethod
    def _discount_factor(curve: dict, payment_time: float) -> float:
        points = [(0.0, 1.0), *zip(curve["year_fractions"], curve["rates"])]
        for (start_time, start_df), (end_time, end_df) in zip(points, points[1:]):
            if start_time <= payment_time <= end_time:
                weight = (payment_time - start_time) / (end_time - start_time)
                return start_df + weight * (end_df - start_df)
        raise ValueError(f"Payment time {payment_time} outside discount curve range")


class TradeActionGenerator:
    """Randomly produces OPEN_TRADE (via instrument generators) or CLOSE_TRADE actions"""

    def __init__(self, trade_generators: list[TradeGenerator], market_data_client, blotter_client):
        self.trade_generators = trade_generators
        self.market_data_client = market_data_client
        self.blotter_client = blotter_client
        self.log = structlog.get_logger()

    def generate_trade_action(self, close_probability: float = 0.3, max_active_trades: int | None = None) -> dict | None:
        if max_active_trades is not None and self._active_limit_reached(max_active_trades):
            return self.trade_out()

        if random.random() < close_probability:
            closing_trade = self.trade_out()
            if closing_trade:
                return closing_trade

        return self.trade_in()

    def _active_limit_reached(self, max_active_trades: int) -> bool:
        active_trades = self.blotter_client.get_active_trades(limit=max_active_trades)
        if len(active_trades) >= max_active_trades:
            self.log.info("max_active_trades_reached", max_active_trades=max_active_trades)
            return True
        return False

    def trade_in(self) -> dict | None:
        trade = random.choice(self.trade_generators).generate()
        if not trade:
            return None

        return {**trade, "action_type": "OPEN_TRADE", "client_request_id": _client_request_id()}

    def trade_out(self) -> dict | None:
        active_trade = self.blotter_client.get_random_active_trade()
        if not active_trade:
            self.log.warning("no_active_trades_to_close")
            return None

        close_price = None
        if active_trade["asset_class"] not in MODEL_PRICED_ASSET_CLASSES:
            tick = self.market_data_client.get_price((active_trade["asset_class"], active_trade["symbol"]))
            if not tick:
                return None
            close_price = tick.get("futures_price") or tick.get("mid") or tick.get("face_value")

        return {
            "action_type": "CLOSE_TRADE",
            "client_request_id": _client_request_id(),
            "trade_id": active_trade["trade_id"],
            "close_price": close_price,
            "closed_at": _utc_now(),
            "close_reason": "RANDOM_TRADE_OUT",
        }
