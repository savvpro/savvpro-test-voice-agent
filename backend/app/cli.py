"""Talk to the brain in the terminal (no microphone needed):  python -m app.cli"""
from datetime import datetime

from app.brain.assistant import Assistant
from app.services.booking import ClinicCalendar
from app.services.seed import seed_calendar


def main() -> None:
    calendar = seed_calendar(ClinicCalendar(), datetime.now())
    bot = Assistant(calendar)
    print("Assistant:", bot.start().reply)
    while not bot.session.state.value == "done":
        try:
            text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        result = bot.hear(text)
        print("Assistant:", result.reply)
        print("   [" + " | ".join(result.trace) + "]")


if __name__ == "__main__":
    main()
