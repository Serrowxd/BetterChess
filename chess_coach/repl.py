"""Terminal REPL for asking the coach questions during a game."""

from __future__ import annotations

import re
import sys
import colorama

from chess_coach.coach import Coach

# SAN move pattern: castling, piece moves, pawn moves, bare squares (e.g. d7, c6); optional move number prefix.
# Lookahead (?=\W|$) so moves followed by markdown (*), punctuation, or end of string are highlighted.
_SAN_PATTERN = re.compile(
    r"(?<!\w)("
    r"O-O(?:-O)?"
    r"|[KQRBN][a-h]?[1-8]?x?[a-h][1-8](=[QRBN])?[+#]?"
    r"|[a-h]x?[a-h][1-8](=[QRBN])?[+#]?"
    r"|[a-h][1-8]"
    r"|\d+\.\s*(?:O-O(?:-O)?|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](=[QRBN])?[+#]?)"
    r")(?=\W|$)",
    re.IGNORECASE,
)

PLAYER_COLOR = colorama.Fore.CYAN
COACH_COLOR = colorama.Fore.YELLOW
MOVE_COLOR = colorama.Fore.GREEN
RESET = colorama.Style.RESET_ALL


def highlight_moves(text: str) -> str:
    """Wrap SAN move notation in coach text with green color."""
    def repl(m: re.Match) -> str:
        return f"{MOVE_COLOR}{m.group(0)}{RESET}"
    return _SAN_PATTERN.sub(repl, text)


def run(coach: Coach) -> None:
    """Run the REPL: read questions, print coach responses. Exits on Ctrl+C or EOF."""
    colorama.init()
    print("Chess Coach REPL. Type your question and press Enter. Ctrl+C or Ctrl+D to exit.\n")
    while True:
        try:
            sys.stdout.write(f"{PLAYER_COLOR}Player> {RESET}")
            sys.stdout.flush()
            line = input().strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break
        if not line:
            continue
        try:
            reply = coach.ask(line)
            print(f"{COACH_COLOR}Coach:{RESET} {highlight_moves(reply)}")
        except Exception as e:
            print(f"{COACH_COLOR}Coach:{RESET} Error: {e}")
        print()
