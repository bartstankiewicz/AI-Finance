from bottle import Bottle, request, response


class PricingServiceApi(Bottle):
    def __init__(self, publisher, valuation_engine, book_metrics):
        super().__init__()
        self.publisher = publisher
        self.valuation_engine = valuation_engine
        self.book_metrics = book_metrics
        self.route('/health', method='GET', callback=self.health)
        self.route('/valuations', method='GET', callback=self.valuations)
        self.route('/valuations/<trade_id>', method='GET', callback=self.valuations_by_trade)
        self.route('/book-metrics', method='GET', callback=self.book_metrics_snapshot)
        self.route('/valuation-stream', method='GET', callback=self.valuation_stream)

    def health(self):
        """Health check requested"""
        health_status = {
            "service": "pricing-service",
            "status": "UP",
            "market_data_stream": self.valuation_engine.get_market_data_status(),
        }
        return health_status

    def valuations(self):
        """Get the latest valuations (newest first); optional ?limit=N"""
        valuations = self.valuation_engine.get_all_valuations()
        limit = request.query.get("limit")
        if limit is None:
            return {"valuations": valuations}
        if not limit.isdigit():
            response.status = 400
            return {"error": "limit must be a non-negative integer"}
        return {"valuations": valuations[:int(limit)]}

    def valuations_by_trade(self, trade_id):
        """Get valuations for a specific trade_id"""
        return {"valuations": self.valuation_engine.get_valuation_by_trade_id(trade_id)}

    def book_metrics_snapshot(self):
        """Rolling alpha / beta per book against the benchmark"""
        return self.book_metrics.snapshot()

    def valuation_stream(self):
        """Stream requested"""
        response.content_type = "text/event-stream"
        response.set_header("Cache-Control", "no-cache")
        return self.publisher.stream_events()

