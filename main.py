"""Entry point for the Terminal Chess Coach."""

import os
import sys

import berserk

from chess_coach import Coach, LichessWatcher, ChessAPIEvaluator, run_repl
from chess_coach.evaluator import CHESS_API_URL


def main() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    token = os.environ.get("LICHESS_API_TOKEN")
    if not token:
        print("Set LICHESS_API_TOKEN in the environment or .env", file=sys.stderr)
        sys.exit(1)

    session = berserk.TokenSession(token)
    client = berserk.Client(session=session)
    depth = int(os.environ.get("CHESS_API_DEPTH", "12"))
    evaluator = ChessAPIEvaluator(url=CHESS_API_URL, depth=depth)
    coach = Coach()

    def on_move(_board, fen: str, evaluation: str) -> None:
        coach.inject_board_update(fen, evaluation)

    watcher = LichessWatcher(client, evaluator, on_move, daemon=True)
    watcher.start()

    try:
        run_repl(coach)
    finally:
        watcher.stop()
        evaluator.quit()


if __name__ == "__main__":
    main()
