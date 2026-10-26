import app.main as main
import json
from datetime import date, timedelta

from app.main import Conversation, handle_turn
from fastapi.testclient import TestClient


def test_logs_expense_from_one_utterance_after_confirmation():
    conversation = Conversation()
    prompt, _ = handle_turn(conversation, "I spent $12.50 on lunch yesterday")
    assert "Should I save it" in prompt
    assert conversation.amount == 12.5
    assert conversation.category == "dining"
    assert conversation.date == (date.today() - timedelta(days=1)).isoformat()
    reply, expense = handle_turn(conversation, "Yes, save it")
    assert "Saved USD 12.50" in reply
    assert expense == {"amount": 12.5, "currency": "USD", "category": "dining", "date": (date.today() - timedelta(days=1)).isoformat(), "description": "lunch"}


def test_assistant_prompts_for_missing_amount_and_category():
    conversation = Conversation()
    assert "How much" in handle_turn(conversation, "Hello")[0]
    assert "What category" in handle_turn(conversation, "$18.25")[0]
    confirmation, _ = handle_turn(conversation, "Groceries")
    assert "under groceries" in confirmation
    assert date.today().isoformat() in confirmation


def test_user_can_correct_amount_before_saving():
    conversation = Conversation(amount=18.0, category="groceries", date="Today", status="confirming")
    reply, _ = handle_turn(conversation, "Actually, make that $20")
    assert "Should I save it" in reply
    assert conversation.amount == 20


def test_cancellation_discards_only_current_draft():
    conversation = Conversation(amount=7.5, category="dining", date="Today")
    conversation.expenses.append({"amount": 3.0, "category": "transport", "date": "Yesterday", "description": "bus"})
    reply, expense = handle_turn(conversation, "Cancel that")
    assert "discarded" in reply
    assert expense is None
    assert len(conversation.expenses) == 1
    assert conversation.amount is None


def test_can_log_multiple_expenses_and_reports_running_total():
    conversation = Conversation(amount=5, category="dining", date="Today", status="confirming")
    handle_turn(conversation, "Yes")
    reply, _ = handle_turn(conversation, "I spent $8 on coffee today")
    assert "Should I save it" in reply
    reply, _ = handle_turn(conversation, "Yes")
    assert "logged total is USD 13.00" in reply


def test_small_talk_is_answered_without_replacing_expense_prompt():
    conversation = Conversation()
    first_prompt, _ = handle_turn(conversation, "Hello")
    assert "How much" in first_prompt

    reply, expense = handle_turn(conversation, "How are you? Where do you live?")
    assert "doing well" in reply
    assert "don’t have a physical home" in reply
    assert "I didn’t catch an expense" not in reply
    assert expense is None
    assert conversation.amount is None
    assert conversation.status == "collecting"


def test_why_question_and_unrecognized_input_get_helpful_replies():
    conversation = Conversation()
    why_reply, _ = handle_turn(conversation, "Why would I tell you something?")
    other_reply, _ = handle_turn(conversation, "Tell me about the weather")
    assert "entirely up to you" in why_reply
    assert "I didn’t catch an expense" in other_reply


def test_small_talk_during_confirmation_preserves_draft():
    conversation = Conversation(amount=12.5, category="dining", date="Today", status="confirming")
    reply, expense = handle_turn(conversation, "How are you?")
    assert "doing well" in reply
    assert conversation.amount == 12.5
    assert conversation.category == "dining"
    assert conversation.status == "confirming"
    assert expense is None


def test_confirmed_expense_survives_conversation_reload_in_sqlite(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "expenses.db")
    main.conversations.clear()
    client = TestClient(main.app)
    session_id = "persistent-test-session"

    client.post("/api/turn", json={"session_id": session_id, "transcript": "$9 on coffee"})
    saved_response = client.post("/api/turn", json={"session_id": session_id, "transcript": "yes"})
    assert saved_response.json()["total"] == 9.0

    main.conversations.clear()
    history_response = client.get(f"/api/expenses/{session_id}")
    assert history_response.json()["expenses"] == [{"amount": 9.0, "currency": "USD", "category": "dining", "date": date.today().isoformat(), "description": "coffee"}]

    client.post(f"/api/reset/{session_id}")
    assert client.get(f"/api/expenses/{session_id}").json()["expenses"] == []


def test_multiple_expenses_in_one_sentence_are_confirmed_and_saved():
    conversation = Conversation()
    reply, expense = handle_turn(conversation, "Spent 450 on lunch and 200 on an Uber")
    assert expense is None
    assert "2 expenses" in reply
    assert conversation.pending_expenses == [
        {"amount": 450.0, "currency": "USD", "category": "dining", "date": date.today().isoformat(), "description": "lunch"},
        {"amount": 200.0, "currency": "USD", "category": "transport", "date": date.today().isoformat(), "description": "an Uber"},
    ]
    reply, first = handle_turn(conversation, "yes")
    assert first == conversation.expenses[0]
    assert "Saved 2 expenses" in reply
    assert len(conversation.expenses) == 2


def test_relative_dates_resolve_against_current_date():
    conversation = Conversation()
    reply, _ = handle_turn(conversation, "$5 two days ago on coffee")
    assert (date.today() - timedelta(days=2)).isoformat() in reply


def test_spoken_money_forms_and_currency_are_supported():
    conversation = Conversation()
    reply, _ = handle_turn(conversation, "four fifty bucks on lunch")
    assert "USD 4.50" in reply
    conversation = Conversation()
    reply, _ = handle_turn(conversation, "twelve hundred dollars for rent")
    assert "USD 1200.00" in reply
    conversation = Conversation()
    reply, _ = handle_turn(conversation, "5k EUR for travel")
    assert "EUR 5000.00" in reply


def test_missing_amount_does_not_guess():
    conversation = Conversation()
    reply, _ = handle_turn(conversation, "I bought coffee")
    assert "How much" in reply
    assert conversation.amount is None


def test_vague_store_category_requires_clarification():
    conversation = Conversation()
    reply, _ = handle_turn(conversation, "I spent $20 on stuff from the store")
    assert "groceries or general shopping" in reply
    assert conversation.amount == 20
    assert conversation.category is None


def test_income_and_non_expense_input_are_not_logged():
    conversation = Conversation()
    income_reply, _ = handle_turn(conversation, "I got paid 5000")
    weather_reply, _ = handle_turn(conversation, "what's the weather?")
    assert "not income" in income_reply
    assert "didn’t catch an expense" in weather_reply
    assert conversation.expenses == []


def test_total_spending_question_returns_saved_total():
    conversation = Conversation(expenses=[
        {"amount": 450.0, "currency": "USD", "category": "dining", "date": date.today().isoformat(), "description": "lunch"},
        {"amount": 200.0, "currency": "USD", "category": "transport", "date": date.today().isoformat(), "description": "Uber"},
    ])
    reply, expense = handle_turn(conversation, "What is my total spending?")
    assert reply == "Your total spending is USD 650.00 across 2 logged expense(s)."
    assert expense is None
    assert conversation.amount is None


def test_total_expense_phrase_returns_saved_total():
    conversation = Conversation(expenses=[
        {"amount": 40.0, "currency": "USD", "category": "shopping", "date": date.today().isoformat(), "description": "clothes"},
        {"amount": 3.76, "currency": "USD", "category": "dining", "date": date.today().isoformat(), "description": "food"},
    ])
    reply, expense = handle_turn(conversation, "My total expense")
    assert "Your total spending is USD 43.76" in reply
    assert expense is None


def test_today_report_returns_total_and_itemized_expenses():
    conversation = Conversation(expenses=[
        {"amount": 40.0, "currency": "USD", "category": "shopping", "date": date.today().isoformat(), "description": "clothes"},
        {"amount": 3.76, "currency": "USD", "category": "dining", "date": date.today().isoformat(), "description": "food"},
        {"amount": 20.0, "currency": "USD", "category": "transport", "date": (date.today() - timedelta(days=1)).isoformat(), "description": "bus"},
    ])
    reply, expense = handle_turn(conversation, "How much money did I spend today and on which things?")
    assert "Today you spent USD 43.76" in reply
    assert "USD 40.00 for clothes" in reply
    assert "USD 3.76 for food" in reply
    assert "USD 20.00 for bus" not in reply
    assert expense is None


def test_spending_breakdown_returns_categories_and_amounts():
    conversation = Conversation(expenses=[
        {"amount": 40.0, "currency": "USD", "category": "shopping", "date": date.today().isoformat(), "description": "clothes"},
        {"amount": 3.76, "currency": "USD", "category": "dining", "date": date.today().isoformat(), "description": "food"},
        {"amount": 10.0, "currency": "USD", "category": "shopping", "date": date.today().isoformat(), "description": "books"},
    ])
    reply, expense = handle_turn(conversation, "What are the things I spend money on?")
    assert "shopping: USD 50.00" in reply
    assert "dining: USD 3.76" in reply
    assert expense is None


def test_history_question_explains_multiple_entries_in_one_session():
    conversation = Conversation(expenses=[
        {"amount": 40.0, "currency": "USD", "category": "shopping", "date": date.today().isoformat(), "description": "clothes"},
        {"amount": 3.76, "currency": "USD", "category": "dining", "date": date.today().isoformat(), "description": "food"},
    ])
    reply, expense = handle_turn(conversation, "Why are there two logged expenses? I only created one session")
    assert "USD 40.00 for clothes" in reply
    assert "USD 3.76 for food" in reply
    assert "One session can contain multiple expense entries" in reply
    assert expense is None


def test_current_expense_question_returns_latest_saved_expense():
    conversation = Conversation(expenses=[
        {"amount": 40.0, "currency": "USD", "category": "shopping", "date": date.today().isoformat(), "description": "clothes"},
        {"amount": 3.76, "currency": "USD", "category": "dining", "date": date.today().isoformat(), "description": "food"},
    ])
    reply, expense = handle_turn(conversation, "What is my current expense?")
    assert reply == f"Your most recent saved expense is USD 3.76 for food on {date.today().isoformat()}."
    assert expense is None


def test_recall_question_checks_saved_expenses_instead_of_starting_new_draft():
    conversation = Conversation(expenses=[
        {"amount": 40.0, "currency": "USD", "category": "shopping", "date": date.today().isoformat(), "description": "clothes"},
        {"amount": 3.76, "currency": "USD", "category": "dining", "date": date.today().isoformat(), "description": "food"},
        ], status="saved")
    reply, expense = handle_turn(conversation, "Wasn't it $40 before?")
    assert "saved USD 40.00 expense for clothes" in reply
    assert "full saved total is USD 43.76" in reply
    assert expense is None
    assert conversation.amount is None
    assert conversation.status == "saved"


def test_natural_question_about_two_log_expenses_returns_history():
    conversation = Conversation(expenses=[
        {"amount": 40.0, "currency": "USD", "category": "shopping", "date": date.today().isoformat(), "description": "clothes"},
        {"amount": 3.76, "currency": "USD", "category": "dining", "date": date.today().isoformat(), "description": "food"},
    ])
    reply, expense = handle_turn(conversation, "What are these two log expenses?")
    assert "USD 40.00 for clothes" in reply
    assert "USD 3.76 for food" in reply
    assert expense is None


def test_update_log_request_starts_a_follow_up_flow():
    existing_expense = {"amount": 40.0, "currency": "USD", "category": "shopping", "date": date.today().isoformat(), "description": "clothes"}
    conversation = Conversation(expenses=[existing_expense], status="saved")
    reply, expense = handle_turn(conversation, "Can you help me update this log?")
    assert "add a new expense, edit an existing entry, or remove one" in reply
    assert expense is None
    assert conversation.expenses == [existing_expense]


def test_query_total_follow_ups_inherit_and_override_slots():
    conversation = Conversation(expenses=[
        {"amount": 40.0, "currency": "USD", "category": "shopping", "date": date.today().isoformat(), "description": "clothes"},
        {"amount": 3.76, "currency": "USD", "category": "dining", "date": (date.today() - timedelta(days=1)).isoformat(), "description": "food"},
    ])
    today_reply, _ = handle_turn(conversation, "What is my total spending today?")
    yesterday_reply, _ = handle_turn(conversation, "And yesterday?")
    food_reply, _ = handle_turn(conversation, "What about food?")
    assert "USD 40.00" in today_reply
    assert "USD 3.76" in yesterday_reply
    assert "on dining" in food_reply
    assert "USD 3.76" in food_reply


def test_last_expense_can_be_corrected_by_follow_up():
    expense = {"amount": 40.0, "currency": "USD", "category": "shopping", "date": date.today().isoformat(), "description": "clothes"}
    conversation = Conversation(expenses=[expense], last_logged_expense=expense, status="saved")
    prompt, _ = handle_turn(conversation, "Change it to 35")
    assert "change that expense" in prompt
    reply, _ = handle_turn(conversation, "yes")
    assert "USD 35.00" in reply
    assert conversation.expenses[-1]["amount"] == 35.0


def test_last_expense_can_be_deleted_by_follow_up():
    expense = {"amount": 40.0, "currency": "USD", "category": "shopping", "date": date.today().isoformat(), "description": "clothes"}
    conversation = Conversation(expenses=[expense], last_logged_expense=expense, status="saved")
    prompt, _ = handle_turn(conversation, "Delete that")
    assert "Should I delete" in prompt
    reply, _ = handle_turn(conversation, "yes")
    assert "Deleted" in reply
    assert conversation.expenses == []


def test_specific_dated_category_expense_can_be_deleted():
    expense = {"amount": 5.0, "currency": "USD", "category": "dining", "date": date.today().isoformat(), "description": "October 20"}
    conversation = Conversation(expenses=[expense], last_logged_expense=expense, status="saved")
    prompt, _ = handle_turn(conversation, "Can you help me remove the 20th October dining from my log?")
    assert "Should I delete USD 5.00" in prompt
    assert date(date.today().year, 10, 20).isoformat() in prompt
    reply, _ = handle_turn(conversation, "Yes")
    assert "Deleted" in reply
    assert conversation.expenses == []


def test_specific_expense_amount_can_be_updated():
    expense = {"amount": 3.76, "currency": "USD", "category": "dining", "date": date.today().isoformat(), "description": "food"}
    conversation = Conversation(expenses=[expense], last_logged_expense=expense, status="saved")
    prompt, _ = handle_turn(conversation, "Update the food expense from 3.76 dollars into 5.54 dollars")
    assert "update food from USD 3.76 to USD 5.54" in prompt
    reply, _ = handle_turn(conversation, "Yes")
    assert "USD 5.54" in reply
    assert conversation.expenses[-1]["amount"] == 5.54


def test_compound_delete_and_update_does_not_partially_mutate_log():
    expense = {"amount": 3.0, "currency": "USD", "category": "dining", "date": date.today().isoformat(), "description": "food"}
    conversation = Conversation(expenses=[expense], last_logged_expense=expense, status="saved")
    reply, result = handle_turn(conversation, "Remove the dining from 26th October and update the food dining expense from $3 to $5")
    assert "won’t change anything yet" in reply
    assert result is None
    assert conversation.expenses == [expense]


def test_toy_purchase_is_classified_as_shopping():
    conversation = Conversation()
    reply, expense = handle_turn(conversation, "Oh, I forgot to add, yesterday I spent $2.00 on a toy.")
    assert "under shopping" in reply
    assert conversation.category == "shopping"
    assert conversation.date == (date.today() - timedelta(days=1)).isoformat()
    assert expense is None


def test_category_correction_replaces_wrong_category_and_keeps_confirmation():
    conversation = Conversation(amount=2.0, category="groceries", date=(date.today() - timedelta(days=1)).isoformat(), description="toy", status="confirming")
    reply, expense = handle_turn(conversation, "No, not in groceries, but add it in shopping")
    assert conversation.category == "shopping"
    assert conversation.status == "confirming"
    assert "under shopping" in reply
    assert "Should I save it" in reply
    assert expense is None


def test_saved_expense_category_can_be_renamed_without_new_amount():
    expense = {"amount": 2.0, "currency": "USD", "category": "shopping", "date": (date.today() - timedelta(days=1)).isoformat(), "description": "toy"}
    conversation = Conversation(expenses=[expense], last_logged_expense=expense, status="saved")
    prompt, _ = handle_turn(conversation, "Update the name from shopping to a toy")
    assert "rename the category from shopping to toy" in prompt
    reply, _ = handle_turn(conversation, "Yes")
    assert "Renamed the expense category to toy" in reply
    assert conversation.expenses[-1]["category"] == "toy"


def test_change_category_follow_up_clears_stale_category():
    conversation = Conversation(amount=2.0, category="shopping", date=date.today().isoformat(), description="toy", status="confirming")
    handle_turn(conversation, "No")
    reply, expense = handle_turn(conversation, "I’d like to change the category")
    assert "What category should I use" in reply
    assert conversation.category is None
    assert expense is None


def test_generic_remove_entry_request_asks_for_target():
    conversation = Conversation(expenses=[
        {"amount": 40.0, "currency": "USD", "category": "shopping", "date": date.today().isoformat(), "description": "clothes"},
        {"amount": 5.0, "currency": "USD", "category": "dining", "date": date.today().isoformat(), "description": "food"},
    ])
    reply, expense = handle_turn(conversation, "Remove one entry from the expense log")
    assert "Which expense should I remove" in reply
    assert expense is None
    assert len(conversation.expenses) == 2


def test_turn_returns_confidence_trace_and_logs_reviewer_correction(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "expenses.db")
    monkeypatch.setattr(main, "TURN_LOG_PATH", tmp_path / "turns.jsonl")
    monkeypatch.setattr(main, "CORRECTIONS_PATH", tmp_path / "corrections.jsonl")
    main.conversations.clear()
    client = TestClient(main.app)
    response = client.post("/api/turn", json={"session_id": "telemetry", "transcript": "what's the weather?"})
    payload = response.json()
    assert payload["turn_id"]
    assert 0 <= payload["confidence"] <= 1
    assert payload["decision_trace"]
    assert "fallback" in json.loads((tmp_path / "turns.jsonl").read_text(encoding="utf-8"))["flags"]

    correction = client.post("/api/corrections", json={"turn_id": payload["turn_id"], "text": "what's the weather?", "intent": "small_talk"})
    assert correction.json() == {"status": "recorded"}
    assert json.loads((tmp_path / "corrections.jsonl").read_text(encoding="utf-8"))["intent"] == "small_talk"


def test_query_follow_up_restores_context_after_conversation_reload(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "expenses.db")
    monkeypatch.setattr(main, "TURN_LOG_PATH", tmp_path / "turns.jsonl")
    main.conversations.clear()
    client = TestClient(main.app)
    session_id = "follow-up-reload"
    main.conversations[session_id] = Conversation(expenses=[
        {"amount": 10.0, "currency": "USD", "category": "dining", "date": date.today().isoformat(), "description": "lunch"},
    ])
    first = client.post("/api/turn", json={"session_id": session_id, "transcript": "What is my total spending today?"}).json()
    assert "USD 10.00" in first["reply"]

    main.conversations.clear()
    follow_up = client.post("/api/turn", json={"session_id": session_id, "transcript": "And yesterday?"}).json()
    assert "no saved expenses" in follow_up["reply"]
    assert any(item.get("note") == "Inherited intent query_total from previous turn" for item in follow_up["decision_trace"])