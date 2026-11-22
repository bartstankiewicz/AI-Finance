"""Rolling alpha / beta of each book against the benchmark index (book level, not per trade)"""
from collections import defaultdict, deque
from datetime import datetime, timezone
import threading

import structlog

# Relative tolerance below which the benchmark variance is treated as zero (float rounding of running sums)
ZERO_VARIANCE_TOLERANCE = 1e-12


def calculate_return(initial_value, current_value):
    return current_value / initial_value - 1


class RollingAlphaBeta:
    """Last `window` (book_return, benchmark_return) pairs with running sums: O(1) per observation and per read"""

    def __init__(self, window):
        self.window = window
        self.pairs = deque()
        self.sum_book = self.sum_benchmark = self.sum_cross = self.sum_benchmark_sq = 0.0
        self.updated_at = None

    def add(self, book_return, benchmark_return, updated_at):
        if len(self.pairs) == self.window:
            self._accumulate(*self.pairs.popleft(), sign=-1.0)
        self.pairs.append((book_return, benchmark_return))
        self._accumulate(book_return, benchmark_return, sign=1.0)
        self.updated_at = updated_at

    def _accumulate(self, book_return, benchmark_return, sign):
        self.sum_book += sign * book_return
        self.sum_benchmark += sign * benchmark_return
        self.sum_cross += sign * book_return * benchmark_return
        self.sum_benchmark_sq += sign * benchmark_return * benchmark_return

    def alpha_beta(self):
        """beta = cov(book, benchmark) / var(benchmark), alpha = mean(book) - beta * mean(benchmark); None until the window is full"""
        n = len(self.pairs)
        if n < self.window or n < 2:
            return None, None
        mean_book = self.sum_book / n
        mean_benchmark = self.sum_benchmark / n
        benchmark_variance = (self.sum_benchmark_sq - n * mean_benchmark * mean_benchmark) / (n - 1)
        if benchmark_variance <= ZERO_VARIANCE_TOLERANCE * (self.sum_benchmark_sq / n):
            return None, None
        covariance = (self.sum_cross - n * mean_book * mean_benchmark) / (n - 1)
        beta = covariance / benchmark_variance
        return mean_book - beta * mean_benchmark, beta


class BookMetrics:
    """One observation per new benchmark tick: (book return, benchmark return) over the same interval.
    Book return = calculate_return(V_start, V_end) with V_start = sum |fair_value| at the start and
    V_end = V_start + unrealized PnL change, both only over trades valued at both ends,
    so trades opened or closed in between are not counted as performance.
    """

    def __init__(self, valuation_engine, benchmark_symbol, window):
        self.log = structlog.get_logger()
        self.valuation_engine = valuation_engine
        self.benchmark_symbol = benchmark_symbol
        self.window = window
        self._lock = threading.Lock()
        self._books = {}
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
        current = {valuation["trade_id"]: (valuation["book_id"], valuation["unrealized_pnl"], abs(valuation["fair_value"])) for valuation in valuations}
        if previous_benchmark:
            benchmark_return = calculate_return(previous_benchmark["spot"], benchmark["spot"])
            book_returns = self._book_returns(current)
            now = datetime.now(timezone.utc).isoformat()
            with self._lock:
                for book_id, book_return in book_returns.items():
                    book = self._books.get(book_id)
                    if book is None:
                        book = self._books[book_id] = RollingAlphaBeta(self.window)
                    book.add(book_return, benchmark_return, now)
        self._previous_trades = current
        self._previous_benchmark = benchmark

    def alpha_beta_by_book(self):
        with self._lock:
            return {book_id: book.alpha_beta() for book_id, book in self._books.items()}

    def snapshot(self):
        with self._lock:
            metrics = [(book_id, *book.alpha_beta(), len(book.pairs), book.updated_at) for book_id, book in self._books.items()]
        return {
            "benchmark_symbol": self.benchmark_symbol,
            "book_metrics": [
                {"book_id": book_id, "alpha": alpha, "beta": beta, "observations": observations, "updated_at": updated_at}
                for book_id, alpha, beta, observations, updated_at in metrics
            ],
        }

    def _book_returns(self, current):
        """Single pass over the cycle: per book start value and PnL change of trades present in both cycles"""
        start_value, pnl_change = defaultdict(float), defaultdict(float)
        previous_trades = self._previous_trades
        for trade_id, (book_id, unrealized_pnl, _) in current.items():
            previous = previous_trades.get(trade_id)
            if previous is None:
                continue
            _, previous_pnl, previous_value = previous
            start_value[book_id] += previous_value
            pnl_change[book_id] += unrealized_pnl - previous_pnl
        return {
            book_id: calculate_return(value, value + pnl_change[book_id])
            for book_id, value in start_value.items()
            if value > 0
        }
