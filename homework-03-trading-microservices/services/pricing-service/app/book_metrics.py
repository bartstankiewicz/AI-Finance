"""Rolling alpha / beta of each book against the benchmark index (book level, not per trade)"""
from collections import defaultdict, deque
from datetime import datetime, timezone
from statistics import covariance, fmean, variance
import threading

import structlog


class BookMetrics:
    """One observation per new benchmark tick: (book return, benchmark return) over the same interval.
    Book return = unrealized PnL change of trades valued at both ends / their |fair_value| at the start,
    so trades opened or closed in between are not counted as performance.
    """

    def __init__(self, valuation_engine, benchmark_symbol, window):
        self.log = structlog.get_logger()
        self.valuation_engine = valuation_engine
        self.benchmark_symbol = benchmark_symbol
        self.window = window
        self._lock = threading.Lock()
        self._observations = {}
        self._updated_at = {}
        self._previous_trades = {}
        self._previous_benchmark = None

    def update(self, valuations):
        """Called once per valuation cycle with all active-trade valuations of that cycle"""
        benchmark = self.valuation_engine.get_current_tick(self.benchmark_symbol)
        if not benchmark or not benchmark.get("spot"):
            self.log.warning("missing_benchmark", symbol=self.benchmark_symbol)
            return
        previous_benchmark = self._previous_benchmark
        if previous_benchmark and benchmark["event_id"] == previous_benchmark["event_id"]:
            return
        current = {valuation["trade_id"]: valuation for valuation in valuations}
        if previous_benchmark:
            benchmark_return = benchmark["spot"] / previous_benchmark["spot"] - 1
            now = datetime.now(timezone.utc).isoformat()
            with self._lock:
                for book_id, book_return in self._book_returns(current):
                    self._observations.setdefault(book_id, deque(maxlen=self.window)).append((book_return, benchmark_return))
                    self._updated_at[book_id] = now
        self._previous_trades = current
        self._previous_benchmark = benchmark

    def snapshot(self):
        with self._lock:
            observations = {book_id: list(values) for book_id, values in self._observations.items()}
            updated_at = dict(self._updated_at)
        return {
            "benchmark_symbol": self.benchmark_symbol,
            "book_metrics": [self._metrics(book_id, values, updated_at[book_id]) for book_id, values in observations.items()],
        }

    def _book_returns(self, current):
        pnl_change, exposure = defaultdict(float), defaultdict(float)
        for trade_id, valuation in current.items():
            previous = self._previous_trades.get(trade_id)
            if previous is None:
                continue
            book_id = valuation["book_id"]
            pnl_change[book_id] += valuation["unrealized_pnl"] - previous["unrealized_pnl"]
            exposure[book_id] += abs(previous["fair_value"])
        for book_id, base in exposure.items():
            if base > 0:
                yield book_id, pnl_change[book_id] / base

    def _metrics(self, book_id, observations, updated_at):
        alpha = beta = None
        if len(observations) == self.window:
            book_returns, benchmark_returns = zip(*observations)
            benchmark_variance = variance(benchmark_returns)
            if benchmark_variance > 0:
                beta = covariance(book_returns, benchmark_returns) / benchmark_variance
                alpha = fmean(book_returns) - beta * fmean(benchmark_returns)
        return {
            "book_id": book_id,
            "alpha": alpha,
            "beta": beta,
            "last_book_return": observations[-1][0],
            "last_benchmark_return": observations[-1][1],
            "updated_at": updated_at,
        }
