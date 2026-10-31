"""
Terminal test client for the Voice Agent WebSocket server.

Usage:
    # Start the server first:
    cd backend && uvicorn main:app --reload

    # Then in another terminal:
    cd backend && python scripts/test_client.py

Type your messages and press Enter. The agent reply, FSM state, and
collected slots are printed after each exchange.
Type 'quit' or 'exit' to close.
"""

import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    print("websockets not installed. Run: pip install websockets")
    sys.exit(1)

SERVER_URL = "ws://localhost:8000/ws"

RESET  = "\033[0m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
GREY   = "\033[90m"


def _print_message(role: str, text: str, colour: str) -> None:
    print(f"\n{colour}[{role}]{RESET} {text}")


def _print_state(state: str, slots: dict) -> None:
    slot_str = "  ".join(f"{k}={v!r}" for k, v in slots.items()) or "(none)"
    print(f"{GREY}  state={state}  slots=[ {slot_str} ]{RESET}")


async def run() -> None:
    print(f"\n{YELLOW}Connecting to {SERVER_URL} …{RESET}")
    try:
        async with websockets.connect(SERVER_URL) as ws:
            print(f"{YELLOW}Connected. Type your message, or 'quit' to exit.{RESET}\n")

            # Receive opening greeting
            raw = await ws.recv()
            msg = json.loads(raw)
            _print_message("Agent", msg["reply"], GREEN)
            _print_state(msg["state"], msg.get("slots", {}))

            while True:
                try:
                    user_input = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: input(f"\n{CYAN}[You]{RESET} ")
                    )
                except (EOFError, KeyboardInterrupt):
                    print("\nExiting.")
                    break

                if user_input.strip().lower() in ("quit", "exit", "q"):
                    print("Closing connection.")
                    break

                if not user_input.strip():
                    continue

                await ws.send(json.dumps({"text": user_input}))

                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=10)
                except asyncio.TimeoutError:
                    print(f"{YELLOW}[timeout — no response]{RESET}")
                    continue

                msg = json.loads(raw)
                _print_message("Agent", msg["reply"], GREEN)
                _print_state(msg["state"], msg.get("slots", {}))

                if msg["state"] == "END":
                    print(f"\n{YELLOW}Call ended.{RESET}")
                    break

    except OSError as exc:
        print(f"\n{YELLOW}Could not connect: {exc}{RESET}")
        print("Make sure the server is running: uvicorn main:app --reload")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())

