"""Chess Coach: terminal-based coach for live Lichess games."""

from chess_coach.coach import Coach
from chess_coach.evaluator import ChessAPIEvaluator, StockfishEvaluator
from chess_coach.repl import run as run_repl
from chess_coach.watcher import LichessWatcher

__all__ = [
    "Coach",
    "ChessAPIEvaluator",
    "LichessWatcher",
    "StockfishEvaluator",
    "run_repl",
]
