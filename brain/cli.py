from .brain import handle_turn
from .state import BOOKED, CANCELLED, Session


def main() -> None:
    session = Session()
    print("Hello! I can help book a clinic appointment.")
    while session.current_state not in {BOOKED, CANCELLED}:
        try:
            text = input("> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        session, reply, _ = handle_turn(session, text)
        print(reply)


if __name__ == "__main__":
    main()
