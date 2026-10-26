from app.brain import Session, State, handle


def test_happy_path_books_a_table():
    s = Session()
    s.state = State.GREETING
    _, s, _ = handle(s, "hi")
    assert s.state == State.COLLECT_DAY

    _, s, _ = handle(s, "Friday")
    assert s.day == "Friday" and s.state == State.COLLECT_TIME

    _, s, _ = handle(s, "7 pm")
    assert s.time == "19:00" and s.state == State.COLLECT_PARTY_SIZE

    _, s, _ = handle(s, "four people")
    assert s.party_size == 4 and s.state == State.COLLECT_NAME

    _, s, _ = handle(s, "my name is John")
    assert s.name == "John" and s.state == State.CONFIRM

    _, s, _ = handle(s, "yes")
    assert s.state == State.BOOKED
    assert s.booking_id is not None


def test_invalid_day_reprompts():
    s = Session(state=State.COLLECT_DAY)
    _, s, _ = handle(s, "banana")
    assert s.state == State.COLLECT_DAY


def test_party_too_large():
    s = Session(state=State.COLLECT_PARTY_SIZE)
    _, s, _ = handle(s, "12 people")
    assert s.state == State.COLLECT_PARTY_SIZE


def test_change_time_at_confirm():
    s = Session(day="Friday", time="19:00", party_size=4, name="John", state=State.CONFIRM)
    _, s, _ = handle(s, "actually make it 8 pm")
    assert s.time == "20:00" and s.state == State.CONFIRM


def test_cancel_anywhere():
    s = Session(state=State.COLLECT_TIME)
    _, s, _ = handle(s, "cancel")
    assert s.state == State.CANCEL


def test_out_of_scope_and_messy_name():
    s = Session(state=State.COLLECT_DAY)
    
    # Test out of scope question (should not break the flow)
    _, s, _ = handle(s, "do you have coffee?")
    assert s.state == State.COLLECT_DAY 
    
    # Test messy name extraction ("put Amna")
    s.state = State.COLLECT_NAME
    _, s, _ = handle(s, "you should put Amna")
    assert s.name == "Amna"