from app.cli import chat


def test_book_by_typing(make_conversation):
    lines = iter(
        [
            "book me with a dermatologist on friday at 10 am",
            "Ali Raza",
            "03001234567",
            "yes",
            "no thanks",
        ]
    )
    out: list[str] = []
    last = chat(make_conversation(), read=lambda _: next(lines), write=out.append, debug=True)
    assert last.decision.end_call
    assert any("booking reference is SC-" in line for line in out)
    assert any(line.startswith("  [affirm") and "action booked" in line for line in out)


def test_hang_up_with_ctrl_d(make_conversation):
    def read(_):
        raise EOFError

    out: list[str] = []
    last = chat(make_conversation(), read=read, write=out.append)
    assert not last.decision.end_call
    assert out[0].startswith("agent: ")
