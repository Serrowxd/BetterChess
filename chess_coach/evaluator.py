"""Position evaluators: local Stockfish or Chess API (chess-api.com)."""

import chess
import chess.engine

CHESS_API_URL = "https://chess-api.com/v1"


class StockfishEvaluator:
    """Evaluates positions using a Stockfish UCI engine."""

    def __init__(self, path: str) -> None:
        self._engine = chess.engine.SimpleEngine.popen_uci(path)

    def evaluate(
        self,
        board: chess.Board,
        limit: chess.engine.Limit | None = None,
    ) -> str:
        """Analyse the position and return a human-readable evaluation string."""
        if limit is None:
            limit = chess.engine.Limit(depth=15)
        try:
            info = self._engine.analyse(
                board,
                limit,
                info=chess.engine.INFO_SCORE,
            )
        except chess.engine.EngineTerminatedError:
            return "Engine unavailable"
        score = info.get("score")
        if score is None:
            return "No evaluation"
        return self._format_score(score)

    def _format_score(self, score: chess.engine.PovScore) -> str:
        """Format PovScore from white's perspective for LLM consumption."""
        white_score = score.white()
        if white_score.is_mate():
            plies = white_score.mate()
            if plies is None:
                return "Checkmate"
            moves = abs(plies) // 2  # plies to full moves
            if plies > 0:
                return f"Mate in {moves} (White wins)"
            return f"Mate in {moves} (Black wins)"
        cp = white_score.score()
        if cp is None:
            return "Unknown"
        pawns = cp / 100.0
        if abs(pawns) < 0.01:
            return "Equal"
        if pawns > 0:
            return f"+{pawns:.2f} (White ahead)"
        return f"{pawns:.2f} (Black ahead)"

    def quit(self) -> None:
        """Shut down the engine cleanly."""
        self._engine.quit()


class ChessAPIEvaluator:
    """Evaluates positions using the Chess API (https://chess-api.com)."""

    def __init__(
        self,
        url: str = CHESS_API_URL,
        depth: int = 12,
        timeout_seconds: float = 15.0,
    ) -> None:
        self._url = url.rstrip("/")
        self._depth = min(max(1, depth), 18)
        self._timeout = timeout_seconds

    def evaluate(
        self,
        board: chess.Board,
        limit: chess.engine.Limit | None = None,
    ) -> str:
        """Analyse the position via Chess API and return a human-readable evaluation."""
        import urllib.request
        import json

        payload = json.dumps({"fen": board.fen(), "depth": self._depth}).encode("utf-8")
        req = urllib.request.Request(
            self._url,
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return f"Chess API error: {e!r}"

        mate = data.get("mate")
        if mate is not None:
            moves = abs(mate)
            if mate > 0:
                return f"Mate in {moves} (White wins)"
            return f"Mate in {moves} (Black wins)"

        eval_val = data.get("eval")
        if eval_val is None:
            text = data.get("text", "")
            return text if text else "No evaluation"

        # API: negative eval = black winning (same as centipawns from white's view)
        if abs(eval_val) < 0.01:
            return "Equal"
        if eval_val > 0:
            return f"+{eval_val:.2f} (White ahead)"
        return f"{eval_val:.2f} (Black ahead)"

    def quit(self) -> None:
        """No-op; no local resource to release."""
        pass
