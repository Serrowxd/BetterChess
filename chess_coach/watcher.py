"""Lichess game watcher: streams events and game state, keeps board in sync."""

from __future__ import annotations

import logging
import threading
from typing import Callable

import berserk
import chess

from .evaluator import Evaluator

logger = logging.getLogger(__name__)


def _board_from_uci_moves(moves_str: str | list) -> chess.Board:
    """Build a chess.Board from space-separated UCI moves (or list of UCI strings)."""
    if isinstance(moves_str, list):
        moves_str = " ".join(str(x) for x in moves_str)
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
    on_move with synced board, FEN, evaluation, and player color.
    """

    def __init__(
        self,
        client: berserk.Client,
        evaluator: Evaluator,
        on_move: Callable[[chess.Board, str, str, str], None],
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
        try:
            my_username = (self._client.account.get() or {}).get("username") or ""
        except Exception as e:
            logger.warning("Could not get Lichess username for player color: %s", e)
            my_username = ""
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
                    self._stream_game(game_id, my_username)
            except Exception:
                if self._stop.is_set():
                    return
                logger.exception("Error in incoming events stream")
                continue

    def _stream_game(self, game_id: str, my_username: str) -> None:
        """Stream one game's state and call on_move for each position."""
        # Player color is set from gameFull; gameState events do not include it, so we reuse the last value.
        player_color = "white"
        try:
            for event in self._client.board.stream_game_state(game_id):
                if self._stop.is_set():
                    return
                if event.get("type") == "gameFull":
                    player_color = self._player_color_from_event(event, my_username)
                moves_str = self._moves_from_event(event)
                if moves_str is None:
                    continue
                board = _board_from_uci_moves(moves_str)
                fen = board.fen()
                evaluation = self._evaluator.evaluate(board)
                self._on_move(board, fen, evaluation, player_color)
                if board.is_game_over():
                    break
        except Exception:
            logger.exception("Error streaming game %s", game_id)

    def _player_color_from_event(self, event: dict, my_username: str) -> str:
        """Return 'white' or 'black' depending on which side the user plays."""
        if not my_username:
            return "white"
        # Lichess board/game stream sends player info as event.players.white/black
        # or as top-level event.white / event.black (id is the username).
        players = event.get("players") or {}
        if not players:
            players = {
                "white": event.get("white") or {},
                "black": event.get("black") or {},
            }
        for color in ("white", "black"):
            p = players.get(color) or {}
            uid = p.get("id") or (p.get("user") or {}).get("id") or p.get("name") or ""
            if uid and uid.lower() == my_username.lower():
                return color
        return "white"

    def _moves_from_event(self, event: dict) -> str | None:
        """Extract space-separated UCI moves from gameFull or gameState event."""
        event_type = event.get("type")
        moves = None
        if event_type == "gameFull":
            state = event.get("state") or {}
            moves = state.get("moves", "")
        elif event_type == "gameState":
            moves = event.get("moves", "")
        if moves is None:
            return None
        if isinstance(moves, list):
            return " ".join(str(m) for m in moves)
        return moves if moves else ""
