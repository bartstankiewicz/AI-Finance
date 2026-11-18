import math

import structlog

from shared.trading_shared.audit import log_audit_error, AuditEventType
from config import SERVICE_NAME

IRS_SIDE_BY_DIRECTION = {"PAY_FIXED": "BUY", "RECEIVE_FIXED": "SELL"}
IRS_PAYMENTS_PER_YEAR = (1, 2, 4, 12)
IRS_MAX_MATURITY_YEARS = 10
IRS_FIXED_RATE_RANGE = (-0.05, 0.20)


class TradeActionValidation:
    def __init__(self):
        self.log = structlog.get_logger()

    def reject_trade(self, action, message):
        """Audit-log a validation failure (TRADE_REJECTED) and raise to stop processing"""
        entity_id = action.get("trade_id") or action.get("client_request_id", "N/A")
        log_audit_error(
            self.log,
            AuditEventType.TRADE_REJECTED,
            message,
            entity_type="TradeAction",
            entity_id=entity_id,
            action=action,
        )
        raise ValueError(message)

    def validate_open_trade(self, action):
        """Validate the action data for opening a trade"""
        for field in ["action_type", "client_request_id", "side"]:
            if not action.get(field):
                self.reject_trade(action, f"Missing required field: {field}")

        if action.get("action_type") != "OPEN_TRADE":
            self.reject_trade(action, f"Invalid action_type for opening trade: {action.get('action_type')}. Must be 'OPEN_TRADE'")

        if action.get("asset_class") == "EUROPEAN_OPTION":
            self.validate_option_fields(action)
        elif action.get("asset_class") == "IRS":
            self.validate_irs_fields(action)

    def validate_irs_fields(self, action):
        """Validate IRS-specific fields of an OPEN_TRADE action"""
        numeric_fields = ("notional", "fixed_rate", "maturity_years", "payments_per_year")
        for field in (*numeric_fields, "direction"):
            if action.get(field) is None:
                self.reject_trade(action, f"Missing required IRS field: {field}")

        for field in numeric_fields:
            value = action[field]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                self.reject_trade(action, f"IRS field {field} must be a finite number, got: {value!r}")

        direction = action["direction"]
        if direction not in IRS_SIDE_BY_DIRECTION:
            self.reject_trade(action, f"Invalid direction: {direction}. Must be one of {list(IRS_SIDE_BY_DIRECTION)}")
        if action["side"] != IRS_SIDE_BY_DIRECTION[direction]:
            self.reject_trade(action, f"side {action['side']} does not match direction {direction}")

        if action["notional"] <= 0:
            self.reject_trade(action, "notional must be positive")

        low, high = IRS_FIXED_RATE_RANGE
        if not low <= action["fixed_rate"] <= high:
            self.reject_trade(action, f"fixed_rate must be within [{low}, {high}] (decimal, e.g. 0.0425)")

        payments_per_year = action["payments_per_year"]
        if payments_per_year not in IRS_PAYMENTS_PER_YEAR:
            self.reject_trade(action, f"payments_per_year must be one of {IRS_PAYMENTS_PER_YEAR}")

        maturity_years = action["maturity_years"]
        if not 0 < maturity_years <= IRS_MAX_MATURITY_YEARS:
            self.reject_trade(action, f"maturity_years must be within (0, {IRS_MAX_MATURITY_YEARS}]")
        if not math.isclose(maturity_years * payments_per_year, round(maturity_years * payments_per_year)):
            self.reject_trade(action, "maturity_years * payments_per_year must be a whole number of periods")

    def validate_option_fields(self, action):
        """Validate option-specific fields of an OPEN_TRADE action"""
        for field in ["underlying_symbol", "option_type", "strike", "maturity_years"]:
            if not action.get(field):
                self.reject_trade(action, f"Missing required option field: {field}")

        if action["option_type"] not in ("CALL", "PUT"):
            self.reject_trade(action, f"Invalid option_type: {action['option_type']}. Must be 'CALL' or 'PUT'")

        if action["strike"] <= 0 or action["maturity_years"] <= 0:
            self.reject_trade(action, "strike and maturity_years must be positive")

        if not action.get("symbol"):
            self.reject_trade(action, "Missing required option field: symbol (option market data symbol)")

    def validate_close_trade(self, action):
        """Validate the action data for closing a trade"""
        for field in ["action_type", "trade_id", "close_reason"]:
            if not action.get(field):
                self.reject_trade(action, f"Missing required field: {field}")

        if action.get("action_type") != "CLOSE_TRADE":
            self.reject_trade(action, f"Invalid action_type for closing trade: {action.get('action_type')}. Must be 'CLOSE_TRADE'")
