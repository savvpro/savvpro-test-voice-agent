import ast
import socket
from pathlib import Path

from app.booking import BookingStore
from app.conversation.engine import ConversationEngine


def test_conversation_package_has_no_llm_imports() -> None:
    denied = {"openai", "anthropic", "google.generativeai", "cohere", "langchain"}
    root = Path(__file__).parents[1] / "app" / "conversation"
    imports = set()
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
    assert not any(name.split(".")[0] in denied for name in imports)


def test_conversation_engine_cannot_open_network(monkeypatch) -> None:
    def denied(*_args, **_kwargs):
        raise AssertionError("conversation brain opened a socket")

    monkeypatch.setattr(socket, "socket", denied)
    engine = ConversationEngine(BookingStore())
    session = engine.create_session("offline")
    assert engine.turn(session, "t1", 0, "Sara")["action"] == "ask_field"
