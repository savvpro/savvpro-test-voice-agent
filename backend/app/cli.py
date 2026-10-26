"""Chat with the receptionist in the terminal: ``python -m app.cli``.

Uses the same conversation service as the API, against the local database
(seeded automatically if empty). Press Enter on an empty line to simulate
silence; Ctrl-D or Ctrl-C hangs up.
"""

import argparse
import logging
from collections.abc import Callable

from app.db.session import SessionLocal
from app.nlu.classifier import get_classifier
from app.schemas import TurnResponse
from app.services.conversation import ConversationService, prepare_database
from app.services.session_store import SessionStore
from app.speech.tts import NullTTS


def _brain(turn: TurnResponse) -> str:
    nlu = turn.nlu
    head = f"{nlu.intent} {nlu.confidence:.2f} via {nlu.source}" if nlu else "start"
    entities = nlu.entities.model_dump(exclude_none=True) if nlu else {}
    action = f" | action {turn.decision.action}" if turn.decision.action else ""
    found = f" | {entities}" if entities else ""
    return f"  [{head} | state {turn.decision.state.value}{action}{found}]"


def chat(
    conversation: ConversationService,
    read: Callable[[str], str] = input,
    write: Callable[[str], None] = print,
    debug: bool = False,
) -> TurnResponse:
    """Run one call until the agent ends it or the caller hangs up; returns the last turn."""
    turn = conversation.start()
    write(f"agent: {turn.reply_text}")
    while not turn.decision.end_call:
        try:
            text = read("you:   ")
        except EOFError, KeyboardInterrupt:
            write("")
            break
        turn = conversation.turn(turn.session_id, text=text)
        if debug:
            write(_brain(turn))
        write(f"agent: {turn.reply_text}")
    return turn


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--debug", action="store_true", help="show intent, entities and state")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING)

    prepare_database(SessionLocal)
    conversation = ConversationService(
        session_factory=SessionLocal,
        store=SessionStore(),
        classifier=get_classifier(),
        stt=None,
        tts=NullTTS(),
    )
    chat(conversation, debug=args.debug)


if __name__ == "__main__":
    main()
