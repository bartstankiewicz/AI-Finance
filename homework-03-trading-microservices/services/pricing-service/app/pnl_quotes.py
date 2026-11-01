"""PnL valuation models - one PnLService subclass per trade asset class.

PnLService holds the flow shared by every asset class (reading trades and ticks, PnL,
building the valuation event, one-time realized PnL of closed trades).
A subclass sets asset_class and implements quote(): the pricing model of its asset class.
"""
from abc import ABC, abstractmethod
from functools import partialmethod
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
    def quote(self, tick, trade):
        """Price one trade from the current tick of its symbol; returns Quote"""
        pass

    def calculate_active(self):
        """Unrealized PnL of all active trades; returns a list so the work runs in the (executor) thread calling it"""
        return list(self.iter_active())

    def calculate_closed(self):
        """One-time realized PnL of closed, unsettled trades; each valuation is stored and settled right away"""
        results = []
        for data in self.iter_closed():
            try:
                self.valuation_engine.settle_trade(data)
            except SQLAlchemyError:
                self.log.exception("settle_trade_failed", trade_id=data["trade_id"])
                continue
            results.append(data)
        return results

    def iter_active(self):
        for trade, tick in self._trades_with_ticks():
            quote = self.quote(tick, trade)
            unrealized_pnl = self.calculate_pnl(trade, quote.reference_price)
            yield self._valuation(trade, quote.fair_value, unrealized_pnl=unrealized_pnl)

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

    def _trades_with_ticks(self):
        """Active trades paired with their tick; each symbol is read once per cycle, trades without a tick are skipped"""
        ticks = {}
        for trade in self.valuation_engine.get_active_trades(self.asset_class):
            symbol = trade["symbol"]
            if symbol not in ticks:
                ticks[symbol] = self.valuation_engine.get_current_tick(symbol)
                if ticks[symbol] is None:
                    self.log.warning("missing_tick", asset_class=self.asset_class, symbol=symbol)
            if ticks[symbol] is not None:
                yield trade, ticks[symbol]

    def _valuation(self, trade, fair_value, unrealized_pnl=0.0, realized_pnl=0.0):
        """Valuation event - contract with blotter-service and frontend, keep field names"""
        return {
            "trade_id": trade["trade_id"],
            "book_id": trade["book_id"],
            "asset_class": self.asset_class,
            "symbol": trade["symbol"],
            "fair_value": round(fair_value, 2),
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": realized_pnl,
            "total_pnl": unrealized_pnl + realized_pnl,
            "currency": trade["trade_currency"],
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
        fair_value = self.calculate_pv(face_value, self.coupon_rate, tick.get("yield"), self.maturity_years)
        market_value = fair_value * trade["quantity"]
        return Quote(fair_value, market_value)

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
        return Quote(forward, spot)

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
    asset_class = "EUROPEAN_OPTION"

    def quote(self, tick, trade):
        raise NotImplementedError(f"{self.asset_class} pricing model is not implemented")


class InterestRateSwapPnLService(PnLService):
    asset_class = "IRS"
    maturity_years = 5
    payments_per_year = 1

    def quote(self, tick, trade):
        raise NotImplementedError(f"{self.asset_class} pricing model is not implemented")


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
    """All registered PnLService subclasses behind the interface of pnl.PnLService,
    so main.py can switch with: from pnl_quotes import PnLServices as PnLService
    """

    def __init__(self, valuation_engine):
        self.services = {asset_class: cls(valuation_engine) for asset_class, cls in PNL_SERVICES.items()}

    def calculate_active(self, asset_class):
        return self.services[asset_class].calculate_active()

    def calculate_closed_positions(self, asset_class):
        return self.services[asset_class].calculate_closed()

    calculate_equity = partialmethod(calculate_active, "EQUITY")
    calculate_fixed_income = partialmethod(calculate_active, "BOND")
    calculate_forex = partialmethod(calculate_active, "FX")
    calculate_commodity = partialmethod(calculate_active, "COMMODITY")
    calculate_futures = partialmethod(calculate_active, "FUTURES")
    calculate_eu_option = partialmethod(calculate_active, "EUROPEAN_OPTION")
    calculate_irs = partialmethod(calculate_active, "IRS")
