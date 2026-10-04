import random
import uuid
import datetime
import structlog
from config import SERVICE_NAME


class TradeGenerator:
    def __init__(self, market_data_client, book_client, blotter_client):
        self.market_data_client = market_data_client
        self.book_client = book_client
        self.blotter_client = blotter_client
        self.log = structlog.get_logger().bind(service=SERVICE_NAME)

    def trade_in(self):
        """Generate a trade with random parameters"""
        generate_trade = random.choice([
            self.generate_equity_trade,
            self.generate_fixed_income_trade,
            self.generate_forex_trade,
            self.generate_commodity_trade,
            self.generate_futures_trade,
            self.generate_eu_option_trade,
            self.generate_irs_trade
        ])

        generated_trade = generate_trade()
        if not generated_trade:
            return None

        generated_trade["action_type"] = "OPEN_TRADE"
        generated_trade["client_request_id"] = f"req-{uuid.uuid4()}"
        return generated_trade

    def generate_trade_action(self, close_probability=0.3):
        """Randomly decide whether to open a new trade or close an existing one"""
        if random.random() < close_probability:
            closing_trade = self.trade_out()
            if closing_trade:
                return closing_trade

        return self.trade_in()

    def trade_out(self):
        """Generate a trade closure with random parameters"""
        active_trade = self.blotter_client.get_random_active_trade()
        if not active_trade:
            self.log.warning("no_active_trades_to_close")
            return None

        tick = self.market_data_client.get_price((active_trade["asset_class"], active_trade["symbol"]))
        if not tick:
            return None

        close_price = tick.get("mid") or tick.get("face_value")

        data = {
            "action_type": "CLOSE_TRADE",
            "client_request_id": f"req-{uuid.uuid4()}",
            "trade_id": active_trade["trade_id"],
            "close_price": close_price,
            "closed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "close_reason": "RANDOM_TRADE_OUT"
        }
        return data

    def generate_equity_trade(self):
        """Generate a trade for the equity asset class"""
        equity_descrption = ("EQUITY", "ACME")
        quantity = random.randint(1, 1000)
        trade_data = self.market_data_client.get_price(equity_descrption)
        if not trade_data:
            return None
        trade_price = trade_data.get("mid")

        book = self.book_client.get_book_for_asset_class("EQUITY")
        if not book:
            return None

        data = {
            "asset_class": "EQUITY",
            "symbol": "ACME",
            "side": random.choice(["BUY", "SELL"]),
            "quantity": quantity,
            "trade_price": trade_price,
            "trade_currency": "USD",
            "book_id": book["book_id"],
            "instrument_id": "ACME",
            "trade_date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self.log.info("generated_equity_trade", data=data)
        return data

    def generate_fixed_income_trade(self):
        """Generate a trade for the fixed income asset class"""
        fixed_income_description = ("BOND", "GOVT")
        quantity = random.randint(1, 1000)
        trade_data = self.market_data_client.get_price(fixed_income_description)
        if not trade_data:
            return None
        trade_price = trade_data.get("face_value")

        book = self.book_client.get_book_for_asset_class("BOND")
        if not book:
            return None

        data = {
            "asset_class": "BOND",
            "symbol": "GOVT",
            "side": "BUY",
            "quantity": quantity,
            "trade_price": trade_price,
            "trade_currency": "USD",
            "book_id": book["book_id"],
            "instrument_id": "GOVT",
            "trade_date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self.log.info("generated_fixed_income_trade", data=data)
        return data

    def generate_forex_trade(self):
        """Generate a trade for the forex asset class"""
        fx_description = ("FX", "EUR/USD")
        quantity = random.randint(1, 1000)
        trade_data = self.market_data_client.get_price(fx_description)
        if not trade_data:
            return None
        trade_price = trade_data.get("mid")

        book = self.book_client.get_book_for_asset_class("FX")
        if not book:
            return None

        data = {
            "asset_class": "FX",
            "symbol": "EUR/USD",
            "side": "BUY",
            "quantity": quantity,
            "trade_price": trade_price,
            "trade_currency": "USD",
            "book_id": book["book_id"],
            "instrument_id": "EUR/USD",
            "trade_date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self.log.info("generated_forex_trade", data=data)
        return data

    def generate_commodity_trade(self):
        """Generate a trade for the commodity asset class"""
        commodity_description = ("COMMODITY", "XAU/USD")
        quantity = random.randint(1, 1000)
        trade_data = self.market_data_client.get_price(commodity_description)
        if not trade_data:
            return None
        trade_price = trade_data.get("mid")

        book = self.book_client.get_book_for_asset_class("COMMODITY")
        if not book:
            return None

        data = {
            "asset_class": "COMMODITY",
            "symbol": "XAU/USD",
            "side": "BUY",
            "quantity": quantity,
            "trade_price": trade_price,
            "trade_currency": "USD",
            "book_id": book["book_id"],
            "instrument_id": "XAU/USD",
            "trade_date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self.log.info("generated_commodity_trade", data=data)
        return data

    def generate_futures_trade(self):
        """Generate a trade for the futures asset class"""
        futures_description = ("FUTURES", "OIL")
        quantity = random.randint(1, 1000)
        trade_data = self.market_data_client.get_price(futures_description)
        if not trade_data:
            return None
        trade_price = trade_data.get("mid")

        book = self.book_client.get_book_for_asset_class("FUTURES")
        if not book:
            return None

        data = {
            "asset_class": "FUTURES",
            "symbol": "OIL",
            "side": "BUY",
            "quantity": quantity,
            "trade_price": trade_price,
            "trade_currency": "USD",
            "book_id": book["book_id"],
            "instrument_id": "OIL",
            "trade_date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self.log.info("generated_futures_trade", data=data)
        return data

    def generate_eu_option_trade(self):
        """Generate a trade for the European option asset class"""
        eu_option_description = ("EQUITY", "ACME")
        trade_data = self.market_data_client.get_price(eu_option_description)
        if not trade_data:
            return None
        trade_price = round(trade_data.get("mid"), 1)

        book = self.book_client.get_book_for_asset_class("EUROPEAN_OPTION")
        if not book:
            return None

        quantity = random.randint(1, 1000)
        strike = round(trade_price * random.choice([0.9, 1.0, 1.1]), 1)
        volatility = round(random.uniform(0.1, 0.5), 2)
        maturity_years = random.choice([0.25, 0.5, 1.0])

        data = {
            "asset_class": "EUROPEAN_OPTION",
            "underlying_symbol": "ACME",
            "quantity": quantity,
            "side": random.choice(["BUY", "SELL"]),
            "trade_price": trade_price,
            "option_type": random.choice(["CALL", "PUT"]),
            "strike": strike,
            "volatility": volatility,
            "trade_currency": "USD",
            "book_id": book["book_id"],
            "instrument_id": f"ACME_EU_OPTION_{strike}_{maturity_years}",
            "maturity_years": maturity_years,
            "trade_date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self.log.info("generated_eu_option_trade", data=data)
        return data

    def generate_irs_trade(self):
        """Generate a trade for the Interest Rate Swap (IRS) asset class"""

        data = {
            "asset_class": "INTEREST_RATE_SWAP",
        }
        self.log.info("generated_irs_trade", data=data)
        return data