"""Chess Coach: Gemini LLM with message history and hidden board updates."""

from __future__ import annotations

import os
import threading

# CAREFUL WHEN CHANGING THIS PROMPT !!!
SYSTEM_PROMPT = """You are a chess coach assisting a player during their live Lichess game.
You will receive periodic board updates (FEN and Stockfish evaluation) as hidden context.
Use that context to answer questions about the position, suggest ideas, or explain plans.
Do not repeat the raw board update to the user. Answer concisely and focus on practical advice."""


def _gemini_chat(messages: list[dict[str, str]]) -> str:
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return "Set GEMINI_API_KEY (or GOOGLE_API_KEY) in the environment."
    client = genai.Client(api_key=api_key)
    model_name = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")
    # Build conversation history as Content objects (user / model roles; skip system)
    contents = []
    for m in messages:
        if m["role"] == "system":
            continue
        role = "user" if m["role"] == "user" else "model"
        contents.append(
            types.Content(role=role, parts=[types.Part.from_text(text=m["content"])])
        )
    if not contents:
        return ""
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
        )
        if not response.candidates:
            return "No response from model."
        return (response.text or "").strip()
    except Exception as e:
        return f"Gemini error: {e!r}"


class Coach:
    """Maintains message history and injects board updates for the LLM."""

    def __init__(self) -> None:
        self._history: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        self._lock = threading.Lock()

    def inject_board_update(self, fen: str, evaluation: str) -> None:
        """Append a hidden board-update message so the LLM stays live with the game."""
        content = (
            "[Board update - do not repeat to user] "
            f"Current FEN: {fen}. Stockfish evaluation: {evaluation}."
        )
        with self._lock:
            self._history.append({"role": "user", "content": content})

    def ask(self, question: str) -> str:
        """Append user message, call Gemini, append assistant reply, return reply."""
        with self._lock:
            self._history.append({"role": "user", "content": question})
            reply = _gemini_chat(self._history)
            self._history.append({"role": "assistant", "content": reply})
        return reply
