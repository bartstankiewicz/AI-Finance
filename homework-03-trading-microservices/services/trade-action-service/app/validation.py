from shared.trading_shared.repositories import AuditLogsRepository
from shared.trading_shared.audit import build_audit_log, AuditEventType, AuditSeverity
from config import SERVICE_NAME


class TradeActionValidation:
    def __init__(self):
        self.audit_repo = AuditLogsRepository()

    def reject_trade(self, log_data, message):
        """Audit-log a validation failure and raise to stop processing"""
        entity_id = log_data.get("trade_id") or log_data.get("client_request_id", "N/A")
        log_data = build_audit_log(
            event_type=AuditEventType.TRADE_REJECTED,
            severity=AuditSeverity.ERROR,
            service_name=SERVICE_NAME,
            entity_id=str(entity_id),
            entity_type="TradeAction",
            message=message,
            payload=log_data
        )
        self.audit_repo.push_audit_logs(log_data)
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

    def validate_option_fields(self, action):
        """Validate option-specific fields of an OPEN_TRADE action"""
        for field in ["underlying_symbol", "option_type", "strike", "maturity_years"]:
            if not action.get(field):
                self.reject_trade(action, f"Missing required option field: {field}")

        if action["option_type"] not in ("CALL", "PUT"):
            self.reject_trade(action, f"Invalid option_type: {action['option_type']}. Must be 'CALL' or 'PUT'")

        if action["strike"] <= 0 or action["maturity_years"] <= 0:
            self.reject_trade(action, "strike and maturity_years must be positive")

    def validate_close_trade(self, action):
        """Validate the action data for closing a trade"""
        for field in ["action_type", "trade_id", "close_reason"]:
            if not action.get(field):
                self.reject_trade(action, f"Missing required field: {field}")

        if action.get("action_type") != "CLOSE_TRADE":
            self.reject_trade(action, f"Invalid action_type for closing trade: {action.get('action_type')}. Must be 'CLOSE_TRADE'")
