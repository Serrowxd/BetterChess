"""Chess Coach: terminal-based coach for live Lichess games."""

from .coach import Coach
from .evaluator import ChessAPIEvaluator, Evaluator, StockfishEvaluator
from .repl import run as run_repl
from .watcher import LichessWatcher

__all__ = [
    "Coach",
    "ChessAPIEvaluator",
    "Evaluator",
    "LichessWatcher",
    "StockfishEvaluator",
    "run_repl",
]
