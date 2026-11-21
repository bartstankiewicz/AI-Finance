"""PnL valuation models - one PnLService subclass per trade asset class.

PnLService holds the flow shared by every asset class (reading trades and ticks, PnL,
building the valuation event, one-time realized PnL of closed trades).
A subclass sets asset_class and implements quote(): the pricing model of its asset class.
Hooks market_data_key / get_market_data / unrealized_pnl let a model price from data other than a tick (IRS: curve).
"""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
import math
from typing import NamedTuple

import structlog
from sqlalchemy.exc import SQLAlchemyError


class Quote(NamedTuple):
    """Pricing model result: fair value of the position and the price its unrealized PnL is measured against"""
    fair_value: float
    reference_price: float


class PnLService(ABC):
    asset_class = None
    multiplier = 1.0

    def __init__(self, valuation_engine):
        self.log = structlog.get_logger()
        self.valuation_engine = valuation_engine

    @abstractmethod
    def quote(self, market_data, trade):
        """Price one trade from its current market data (tick by default); returns Quote"""
        pass

    def market_data_key(self, trade):
        return trade["symbol"]

    def get_market_data(self, key):
        return self.valuation_engine.get_current_tick(key)

    def unrealized_pnl(self, trade, quote):
        return self.calculate_pnl(trade, quote.reference_price)

    def calculate_active(self):
        """Unrealized PnL of all active trades; returns a list so the work runs in the (executor) thread calling it"""
        return list(self.iter_active())

    def calculate_closed(self):
        """One-time realized PnL of closed, unsettled trades; each valuation is stored and settled right away"""
        results = []
        for data in self.iter_closed():
            data["valuation_status"] = "SETTLED"
            try:
                self.valuation_engine.settle_trade(data)
            except SQLAlchemyError:
                self.log.exception("settle_trade_failed", trade_id=data["trade_id"])
                continue
            results.append(data)
        return results

    def iter_active(self):
        trades = self.valuation_engine.get_active_trades(self.asset_class)
        for trade, market_data in self._with_market_data(trades):
            quote = self._quote_or_skip(market_data, trade)
            if quote is not None:
                yield self._valuation(trade, quote.fair_value, unrealized_pnl=self.unrealized_pnl(trade, quote))

    def iter_closed(self):
        for trade in self.valuation_engine.get_closed_trades(self.asset_class):
            close_price = trade["close_price"]
            if close_price is None:
                continue
            realized_pnl = self.calculate_pnl(trade, close_price)
            yield self._valuation(trade, close_price * trade["quantity"], realized_pnl=realized_pnl)

    def calculate_pnl(self, trade, reference_price):
        """PnL between a reference price and the trade price (unrealized: market price, realized: close_price)"""
        if trade["side"] == "BUY":
            pnl = (reference_price - trade["trade_price"]) * trade["quantity"] * self.multiplier
        else:
            pnl = (trade["trade_price"] - reference_price) * trade["quantity"] * self.multiplier
        return round(pnl, 2)

    @staticmethod
    def interpolate_rate(curve_points, target_tenor):
        """Linear interpolation over points sorted by tenor_years; None outside the curve range"""
        previous_point = None
        for point in curve_points:
            if point["tenor_years"] == target_tenor:
                return point["rate"]
            if point["tenor_years"] > target_tenor:
                if previous_point is None:
                    return None
                x1, y1 = previous_point["tenor_years"], previous_point["rate"]
                x2, y2 = point["tenor_years"], point["rate"]
                weight = (target_tenor - x1) / (x2 - x1)
                return y1 + weight * (y2 - y1)
            previous_point = point
        return None

    @staticmethod
    def curve_points(curve):
        """Curve event (year_fractions, rates) -> points for interpolate_rate"""
        return [{"tenor_years": tenor, "rate": rate} for tenor, rate in zip(curve["year_fractions"], curve["rates"])]

    @classmethod
    def discount_factor(cls, curve, t):
        """DF linearly interpolated on a discount curve with D(0) = 1; no extrapolation"""
        curve_points = [{"tenor_years": 0.0, "rate": 1.0}] + cls.curve_points(curve)
        df = cls.interpolate_rate(curve_points, t)
        if df is None:
            raise ValueError(f"t={t} outside curve {curve['curve_name']} range [0, {curve_points[-1]['tenor_years']}]")
        return df

    def _with_market_data(self, trades):
        """Trades paired with their market data; each key is read once per cycle, trades without data are skipped"""
        market_data = {}
        for trade in trades:
            key = self.market_data_key(trade)
            if key not in market_data:
                market_data[key] = self.get_market_data(key)
                if market_data[key] is None:
                    self.log.warning("missing_market_data", asset_class=self.asset_class, key=key)
            if market_data[key] is not None:
                yield trade, market_data[key]

    def _quote_or_skip(self, market_data, trade):
        try:
            return self.quote(market_data, trade)
        except (ValueError, KeyError, TypeError):
            self.log.warning("valuation_skipped", asset_class=self.asset_class, trade_id=trade["trade_id"], exc_info=True)
            return None

    def _valuation(self, trade, fair_value, unrealized_pnl=0.0, realized_pnl=0.0):
        """Valuation event - contract with blotter-service and frontend, keep field names"""
        return {
            "event_type": "valuation_update",
            "trade_id": trade["trade_id"],
            "book_id": trade["book_id"],
            "asset_class": self.asset_class,
            "symbol": trade["symbol"],
            "fair_value": round(fair_value, 2),
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": realized_pnl,
            "total_pnl": unrealized_pnl + realized_pnl,
            "currency": trade["trade_currency"],
            "valuation_status": "LIVE",
            "created_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        }


class EquityPnLService(PnLService):
    asset_class = "EQUITY"

    def quote(self, tick, trade):
        price = tick.get("mid") or tick.get("last")
        fair_value = price * trade["quantity"]
        return Quote(fair_value, price)


class FixedIncomePnLService(PnLService):
    asset_class = "BOND"
    coupon_rate = 0.05
    maturity_years = 5

    def quote(self, tick, trade):
        face_value = tick.get("face_value")
        pv = self.calculate_pv(face_value, self.coupon_rate, tick.get("yield"), self.maturity_years)
        return Quote(pv * trade["quantity"], pv)

    @staticmethod
    def calculate_pv(face_value, coupon_rate, yield_rate, maturity_years):
        """Present value of the bond cash flows: annual coupons plus face value repaid at maturity"""
        annual_coupon = face_value * coupon_rate
        pv = 0.0
        for year in range(1, maturity_years + 1):
            cash_flow = annual_coupon
            if year == maturity_years:
                cash_flow += face_value
            pv += cash_flow / (1 + yield_rate) ** year
        return pv


class ForexPnLService(PnLService):
    asset_class = "FX"
    time_years = 0.5

    def quote(self, tick, trade):
        spot = tick.get("spot")
        forward = self.calculate_fx_forward(spot, tick.get("domestic_rate"), tick.get("foreign_rate"), self.time_years)
        return Quote(forward * trade["quantity"], spot)

    @staticmethod
    def calculate_fx_forward(spot, domestic_rate, foreign_rate, time_years):
        """Forward rate of a currency pair"""
        return spot * (1 + domestic_rate * time_years) / (1 + foreign_rate * time_years)


class CommodityPnLService(PnLService):
    asset_class = "COMMODITY"

    def quote(self, tick, trade):
        spot = tick.get("spot")
        fair_value = spot * trade["quantity"]
        return Quote(fair_value, spot)


class FuturesPnLService(PnLService):
    asset_class = "FUTURES"

    def quote(self, tick, trade):
        futures_price = tick.get("futures_price")
        fair_value = futures_price * self.multiplier * trade["quantity"]
        return Quote(fair_value, futures_price)


class OptionsPnLService(PnLService):
    """European option, Black-Scholes with continuous dividend yield.
    Market data per option symbol (e.g. ACME_EU_OPTION): option tick (volatility, dividend_yield),
    underlying tick (spot = mid), USD_YIELD curve (r = zero yield at T).
    Time to expiry = maturity_years - years elapsed since trade_date; at/after expiry value = intrinsic.
    trade_price is the premium paid per unit, so unrealized PnL = (model price - premium) * qty.
    """
    asset_class = "EUROPEAN_OPTION"
    curve_name = "USD_YIELD"
    seconds_per_year = 365.0 * 24 * 3600

    def get_market_data(self, symbol):
        option_tick = self.valuation_engine.get_current_tick(symbol)
        if not option_tick:
            return None
        underlying = self.valuation_engine.get_current_tick(option_tick["underlying_symbol"])
        curve = self.valuation_engine.get_curve(self.curve_name)
        if not (underlying and curve):
            return None
        return {"option": option_tick, "underlying": underlying, "curve": curve}

    def iter_closed(self):
        """Realized PnL at the model price on settlement (one cycle after close); close_price is not used.
        Trades without market data stay unsettled and are retried next cycle.
        """
        trades = self.valuation_engine.get_closed_trades(self.asset_class)
        for trade, market_data in self._with_market_data(trades):
            quote = self._quote_or_skip(market_data, trade)
            if quote is not None:
                realized_pnl = self.calculate_pnl(trade, quote.reference_price)
                yield self._valuation(trade, quote.fair_value, realized_pnl=realized_pnl)

    def quote(self, market_data, trade):
        option_tick = market_data["option"]
        time_years = self.time_to_expiry(trade)
        rate = self.risk_free_rate(market_data["curve"], time_years)
        price = self.black_scholes_price(
            trade["option_type"], market_data["underlying"]["mid"], trade["strike"], time_years, rate,
            option_tick["volatility"], option_tick.get("dividend_yield", 0.0),
        )
        return Quote(price * trade["quantity"], price)

    def risk_free_rate(self, curve, t):
        """Zero yield at t from USD_YIELD, flat before the first tenor (1Y)"""
        curve_points = self.curve_points(curve)
        if t <= curve_points[0]["tenor_years"]:
            zero_yield = curve_points[0]["rate"]
        else:
            zero_yield = self.interpolate_rate(curve_points, t)
        if zero_yield is None:
            raise ValueError(f"t={t} outside curve {curve['curve_name']} range")
        return math.log(1 + zero_yield)

    def time_to_expiry(self, trade):
        elapsed = (datetime.now(timezone.utc) - trade["trade_date"]).total_seconds() / self.seconds_per_year
        return max(trade["maturity_years"] - elapsed, 0.0)

    @staticmethod
    def normal_cdf(x):
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    @classmethod
    def black_scholes_price(cls, option_type, spot, strike, time_years, rate, volatility, dividend_yield=0.0):
        """Price per unit (the only Black-Scholes implementation in the system)"""
        if time_years <= 0:
            intrinsic = spot - strike if option_type == "CALL" else strike - spot
            return max(intrinsic, 0.0)
        sqrt_t = math.sqrt(time_years)
        d1 = (math.log(spot / strike) + (rate - dividend_yield + 0.5 * volatility ** 2) * time_years) / (volatility * sqrt_t)
        d2 = d1 - volatility * sqrt_t
        discounted_spot = spot * math.exp(-dividend_yield * time_years)
        discounted_strike = strike * math.exp(-rate * time_years)
        if option_type == "CALL":
            return discounted_spot * cls.normal_cdf(d1) - discounted_strike * cls.normal_cdf(d2)
        if option_type == "PUT":
            return discounted_strike * cls.normal_cdf(-d2) - discounted_spot * cls.normal_cdf(-d1)
        raise ValueError(f"Unsupported option_type: {option_type}")


class InterestRateSwapPnLService(PnLService):
    """Simplified IRS: NPV = receive leg PV - pay leg PV (PAY_FIXED: floating - fixed, RECEIVE_FIXED: fixed - floating).
    Discount factors come from the <trade_currency>_DISCOUNT curve (rates = DFs per year_fraction).
    No upfront premium is assumed, so unrealized PnL = NPV.
    """
    asset_class = "IRS"

    def market_data_key(self, trade):
        return f"{trade['trade_currency']}_DISCOUNT"

    def get_market_data(self, curve_name):
        return self.valuation_engine.get_curve(curve_name)

    def unrealized_pnl(self, trade, quote):
        return round(quote.fair_value, 2)

    def iter_closed(self):
        """Realized PnL = NPV on the curve at settlement (one cycle after close); close_price is not used.
        Trades without curve or outside its range stay unsettled and are retried next cycle.
        """
        trades = self.valuation_engine.get_closed_trades(self.asset_class)
        for trade, curve in self._with_market_data(trades):
            quote = self._quote_or_skip(curve, trade)
            if quote is not None:
                yield self._valuation(trade, quote.fair_value, realized_pnl=round(quote.fair_value, 2))

    def quote(self, curve, trade):
        npv = self.calculate_npv(
            curve, trade["notional"], trade["fixed_rate"], trade["maturity_years"],
            trade["payments_per_year"], trade["direction"],
        )
        return Quote(npv, npv)

    @classmethod
    def calculate_npv(cls, curve, notional, fixed_rate, maturity_years, payments_per_year, direction):
        schedule = cls.build_schedule(curve, maturity_years, payments_per_year)
        fixed = cls.pv_fixed_leg(schedule, notional, fixed_rate)
        floating = cls.pv_floating_leg(schedule, notional)
        if direction == "PAY_FIXED":
            return floating - fixed
        if direction == "RECEIVE_FIXED":
            return fixed - floating
        raise ValueError(f"Unsupported IRS direction: {direction}")

    @classmethod
    def build_schedule(cls, curve, maturity_years, payments_per_year):
        period_count = maturity_years * payments_per_year
        accrual = 1.0
        schedule = []
        previous_df = 1.0
        for period_number in range(1, round(period_count) + 1):
            payment_time = period_number / payments_per_year
            discount_factor = cls.discount_factor(curve, payment_time)
            forward_rate = (previous_df / discount_factor - 1) / accrual
            schedule.append({
                "payment_time": payment_time,
                "accrual": accrual,
                "discount_factor": discount_factor,
                "forward_rate": forward_rate,
            })
            previous_df = discount_factor
        return schedule

    @staticmethod
    def pv_fixed_leg(schedule, notional, fixed_rate):
        return sum(notional * fixed_rate * period["accrual"] * period["discount_factor"]
                   for period in schedule)

    @staticmethod
    def pv_floating_leg(schedule, notional):
        return sum(notional * period["forward_rate"] * period["accrual"] * period["discount_factor"]
                   for period in schedule)

    @staticmethod
    def calculate_annuity(schedule, notional):
        return sum(notional * period["accrual"] * period["discount_factor"] for period in schedule)

    @classmethod
    def calculate_par_rate(cls, schedule, notional):
        return cls.pv_floating_leg(schedule, notional) / cls.calculate_annuity(schedule, notional)


PNL_SERVICES = {cls.asset_class: cls for cls in (
    EquityPnLService,
    FixedIncomePnLService,
    ForexPnLService,
    CommodityPnLService,
    FuturesPnLService,
    OptionsPnLService,
    InterestRateSwapPnLService,
)}


class PnLServices:
    """All registered PnLService subclasses behind one facade used by main.py"""

    def __init__(self, valuation_engine):
        self.services = {asset_class: cls(valuation_engine) for asset_class, cls in PNL_SERVICES.items()}

    def calculate_active(self, asset_class):
        return self.services[asset_class].calculate_active()

    def calculate_closed_positions(self, asset_class):
        return self.services[asset_class].calculate_closed()
