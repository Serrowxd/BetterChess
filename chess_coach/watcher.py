"""Lichess game watcher: streams events and game state, keeps board in sync."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Callable

import berserk
import chess

if TYPE_CHECKING:
    from chess_coach.evaluator import StockfishEvaluator


def _board_from_uci_moves(moves_str: str) -> chess.Board:
    """Build a chess.Board from space-separated UCI moves."""
    board = chess.Board()
    if not moves_str or not moves_str.strip():
        return board
    for uci in moves_str.strip().split():
        try:
            move = chess.Move.from_uci(uci)
            if move in board.legal_moves:
                board.push(move)
        except (ValueError, AssertionError):
            continue
    return board


class LichessWatcher(threading.Thread):
    """
    Watches Lichess for game start, then streams game state and invokes
    on_move with synced board, FEN, and Stockfish evaluation.
    """

    def __init__(
        self,
        client: berserk.Client,
        evaluator: StockfishEvaluator,
        on_move: Callable[[chess.Board, str, str], None],
        *,
        daemon: bool = True,
    ) -> None:
        super().__init__(daemon=daemon)
        self._client = client
        self._evaluator = evaluator
        self._on_move = on_move
        self._stop = threading.Event()

    def stop(self) -> None:
        """Request the watcher to stop after the current iteration."""
        self._stop.set()

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                for event in self._client.board.stream_incoming_events():
                    if self._stop.is_set():
                        return
                    if event.get("type") != "gameStart":
                        continue
                    game = event.get("game") or {}
                    game_id = game.get("id") or game.get("gameId")
                    if not game_id:
                        continue
                    self._stream_game(game_id)
            except Exception:
                if self._stop.is_set():
                    return
                continue

    def _stream_game(self, game_id: str) -> None:
        """Stream one game's state and call on_move for each position."""
        try:
            for event in self._client.board.stream_game_state(game_id):
                if self._stop.is_set():
                    return
                moves_str = self._moves_from_event(event)
                if moves_str is None:
                    continue
                board = _board_from_uci_moves(moves_str)
                fen = board.fen()
                evaluation = self._evaluator.evaluate(board)
                self._on_move(board, fen, evaluation)
                if board.is_game_over():
                    break
        except Exception:
            pass

    def _moves_from_event(self, event: dict) -> str | None:
        """Extract space-separated UCI moves from gameFull or gameState event."""
        event_type = event.get("type")
        if event_type == "gameFull":
            state = event.get("state") or {}
            return state.get("moves", "")
        if event_type == "gameState":
            return event.get("moves", "")
        return None
