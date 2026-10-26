"""Executable conversation checks: python -m tests.check_phase2_conversations.

These transcripts use a fixed date and fail immediately if a response, state,
or collected field differs from the expected behavior.
"""

from datetime import datetime

from app.brain.engine import ConversationEngine


REFERENCE = datetime(2025, 1, 15, 10)
EMPTY = {"date": None, "time": None, "party_size": None}
DETAILS = {"date": "2025-01-16", "time": "19:00", "party_size": 4}
BOOKING = "tomorrow at 7pm for 4"


def check(label, setup, turns):
    """Execute a conversation and assert every supplied turn's result."""
    engine = ConversationEngine(reference_date=REFERENCE)
    sid = engine.create_session()
    engine.start_conversation(sid)
    for text in setup:
        engine.process_input(sid, text)

    print(f"\n{label}")
    for text, expected_state, expected_data, expected_prompt in turns:
        response = engine.process_input(sid, text)
        assert response.state == expected_state, (label, text, response)
        assert response.collected_data == expected_data, (label, text, response)
        assert expected_prompt.lower() in response.message.lower(), (label, text, response)
        # Escape any template emoji so Windows console encodings cannot fail.
        message = response.message.encode("ascii", "backslashreplace").decode("ascii")
        print(f"  User: {text}")
        print(f"  Brain [{response.state}]: {message}")
        print(f"  Data: {response.collected_data}")
    print("  PASS")


def main():
    cases = 0

    def run(label, setup, turns):
        nonlocal cases
        check(label, setup, turns)
        cases += 1

    for rejection in ("no", "not correct", "that's wrong", "incorrect"):
        run("Confirmation rejection", [BOOKING], [
            (rejection, "confirm", DETAILS, "What would you like to change"),
            ("actually 6 people", "confirm", {**DETAILS, "party_size": 6}, "Shall I"),
            ("yes", "completed", {**DETAILS, "party_size": 6}, "confirmed"),
        ])

    for value in ("7:99pm", "25:00", "13:75"):
        run("Invalid time", ["tomorrow for 4"], [
            (value, "ask_time", {**DETAILS, "time": None}, "valid time"),
            ("8pm", "confirm", {**DETAILS, "time": "20:00"}, "Shall I"),
        ])

    for value in ("February 30", "April 31", "2025-01-10", "yesterday"):
        prompt = "past" if value in ("2025-01-10", "yesterday") else "valid calendar date"
        run("Invalid or past date", [], [
            (value, "ask_date", EMPTY, prompt),
            ("tomorrow", "ask_time", {**EMPTY, "date": DETAILS["date"]}, "What time"),
        ])

    for value in ("-2 people", "0 guests"):
        run("Invalid guest count", ["tomorrow at 7pm"], [
            (value, "ask_party_size", {**DETAILS, "party_size": None}, "at least 1"),
            ("4 people", "confirm", DETAILS, "Shall I"),
        ])

    run("Ambiguous time", ["tomorrow for 4"], [
        ("7pm or 8pm", "ask_time", {**DETAILS, "time": None}, "choose one time"),
        ("8pm", "confirm", {**DETAILS, "time": "20:00"}, "Shall I"),
    ])

    for value, field, state, prompt, replacement, resolved in (
        ("actually 50 people", "party_size", "ask_party_size", "20 guests", "6", 6),
        ("actually February 30", "date", "ask_date", "valid calendar date", "Friday", "2025-01-17"),
        ("change the time to 3am", "time", "ask_time", "hours", "8pm", "20:00"),
        ("actually 7:99pm", "time", "ask_time", "valid time", "8pm", "20:00"),
    ):
        cleared = {**DETAILS, field: None}
        corrected = {**DETAILS, field: resolved}
        run("Invalid correction", [BOOKING], [
            (value, state, cleared, prompt),
            ("hello", state, cleared, "Could you say it again"),
            ("yes", state, cleared, "Could you say it again"),
            (replacement, "confirm", corrected, "Shall I"),
            ("book it", "completed", corrected, "confirmed"),
        ])

    run("Completed session", [BOOKING, "yes"], [
        ("change the time to 8pm", "completed", DETAILS, "already confirmed"),
        ("actually 6 people", "completed", DETAILS, "contact the restaurant"),
        ("cancel", "completed", DETAILS, "already confirmed"),
        ("start over", "ask_date", EMPTY, "start fresh"),
    ])

    run("Cancellation and restart", [BOOKING], [
        ("cancel", "cancelled", DETAILS, "cancelled"),
        ("change the time to 8pm", "cancelled", DETAILS, "start over"),
        ("restart", "ask_date", EMPTY, "start fresh"),
    ])

    run("Normal conversation", [], [
        ("hello", "ask_date", EMPTY, "date"),
        ("tomorrow", "ask_time", {**EMPTY, "date": DETAILS["date"]}, "What time"),
        ("7pm", "ask_party_size", {**DETAILS, "party_size": None}, "How many"),
        ("4", "confirm", DETAILS, "Shall I"),
        ("yes", "completed", DETAILS, "confirmed"),
    ])

    print(f"\nPASS: {cases} conversation scenarios; all state, data, and prompt assertions passed.")


if __name__ == "__main__":
    main()
