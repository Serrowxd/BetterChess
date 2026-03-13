"""Chess Coach: Gemini LLM with message history and hidden board updates."""

from __future__ import annotations

import os
import threading

# CAREFUL WHEN CHANGING THIS PROMPT !!!
SYSTEM_PROMPT = """You are a chess coach assisting a player during their live Lichess game.
You will receive periodic board updates (FEN and position evaluation) as hidden context.
Use that context to answer questions about the position, suggest ideas, or explain plans.
Do not repeat the raw board update to the user. Answer concisely and focus on practical advice."""

MAX_BOARD_UPDATES = int(os.environ.get("MAX_BOARD_UPDATES", "20"))
MAX_CONVERSATION_TURNS = int(os.environ.get("MAX_CONVERSATION_TURNS", "10"))
BOARD_UPDATE_PREFIX = "[Board update - do not repeat to user] "


def _gemini_chat(messages: list[dict[str, str]]) -> str:
    # Google GenAI SDK (google-genai). If upgrading, check client API at https://ai.google.dev/gemini-api/docs
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

    def _prune_history(self) -> None:
        """Keep system + last N board updates + last M conversation turns. Call under lock. Order preserved."""
        if len(self._history) <= 1:
            return
        rest = self._history[1:]
        # Tag each message: (msg, "board") or (msg, "turn", pair_id)
        tagged: list[tuple[dict[str, str], str, int]] = []
        pair_id = -1
        i = 0
        while i < len(rest):
            m = rest[i]
            content = (m.get("content") or "").strip()
            if content.startswith(BOARD_UPDATE_PREFIX):
                tagged.append((m, "board", -1))
                i += 1
            else:
                pair_id += 1
                while i < len(rest) and not (rest[i].get("content") or "").strip().startswith(BOARD_UPDATE_PREFIX):
                    tagged.append((rest[i], "turn", pair_id))
                    i += 1
        board_indices = [i for i, (_, t, _) in enumerate(tagged) if t == "board"]
        turn_pair_ids = list(dict.fromkeys(tagged[j][2] for j in range(len(tagged)) if tagged[j][1] == "turn"))
        keep_n_boards = set(board_indices[-MAX_BOARD_UPDATES:])
        keep_m_pairs = set(turn_pair_ids[-MAX_CONVERSATION_TURNS:])
        # Keep indices for last N board updates or last M turn pairs.
        kept_idx = {
            i for i, (_, t, pid) in enumerate(tagged)
            if (t == "board" and i in keep_n_boards) or (t == "turn" and pid in keep_m_pairs)
        }
        new_rest = [tagged[j][0] for j in range(len(tagged)) if j in kept_idx]
        self._history = [self._history[0]] + new_rest

    def inject_board_update(
        self,
        fen: str,
        evaluation: str,
        player_color: str | None = None,
    ) -> None:
        """Append a hidden board-update message so the LLM stays live with the game."""
        prefix = ""
        if player_color and player_color.lower() == "black":
            prefix = "You are playing as Black. "
        elif player_color and player_color.lower() == "white":
            prefix = "You are playing as White. "
        content = (
            f"{BOARD_UPDATE_PREFIX}{prefix}"
            f"Current FEN: {fen}. Position evaluation: {evaluation}."
        )
        with self._lock:
            self._prune_history()
            self._history.append({"role": "user", "content": content})

    def ask(self, question: str) -> str:
        """Append user message, call Gemini, append assistant reply, return reply."""
        with self._lock:
            self._prune_history()
            self._history.append({"role": "user", "content": question})
            messages = list(self._history)
        reply = _gemini_chat(messages)
        with self._lock:
            self._history.append({"role": "assistant", "content": reply})
        return reply
