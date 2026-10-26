"""
Manual smoke-test: send a WAV to /ws/calls and print transcript + reply.

Usage:
    python scripts/ws_smoke_test.py [--wav PATH] [--url URL]

Requirements (already installed in the project venv):
    pip install websockets

Example:
    python scripts/ws_smoke_test.py --wav scripts/sample.wav
    python scripts/ws_smoke_test.py               # text-only mode (no audio)
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import struct
import wave
from pathlib import Path


async def run(server_url: str, wav_path: str | None) -> None:
    import websockets  # type: ignore[import-untyped]

    ws_url = server_url.rstrip("/") + "/ws/calls"
    print(f"Connecting to {ws_url} …")

    async with websockets.connect(ws_url) as ws:
        # ── Turn 0: Server greeting ────────────────────────────────────────
        raw = await ws.recv()
        msg = json.loads(raw)
        assert msg["type"] == "turn", f"Expected turn, got: {msg}"
        print(f"\n[TURN {msg['turn']}] 🤖 {msg['reply_text']}")
        if msg.get("audio"):
            audio_bytes = base64.b64decode(msg["audio"])
            print(f"         (audio: {len(audio_bytes)} bytes, {msg.get('audio_mime', '?')})")
        timings = msg.get("timings", {})
        print(f"         timings: {timings}")

        # ── Optional Turn 1: Send audio frame ─────────────────────────────
        if wav_path:
            wav_file = Path(wav_path)
            if not wav_file.exists():
                print(f"\n[WARNING] WAV file not found: {wav_path}. Skipping audio turn.")
            else:
                audio_data = wav_file.read_bytes()
                print(f"\n[SEND AUDIO] {wav_file.name} ({len(audio_data)} bytes) …")
                await ws.send(audio_data)

                raw = await ws.recv()
                msg = json.loads(raw)
                print(f"\n[TURN {msg.get('turn', '?')}] 👤 transcript: '{msg.get('user_text', '')}'")
                print(f"              🤖 {msg.get('reply_text', '')}")
                print(f"              timings: {msg.get('timings', {})}")
                if msg.get("end_call"):
                    print("\n[CALL ENDED] Server ended the call.")
                    return

        # ── Turn 2+: Text-based booking dialog ────────────────────────────
        demo_turns = [
            "I'd like to book a checkup",
            "Tomorrow",
            "10 AM",
            "Sara Khan",
            "03001234567",
            "yes",
            "yes",
        ]

        for text in demo_turns:
            print(f"\n[SEND TEXT] {text!r}")
            await ws.send(json.dumps({"type": "user_text", "text": text}))

            raw = await ws.recv()
            msg = json.loads(raw)
            print(f"[TURN {msg.get('turn', '?')}] 🤖 {msg.get('reply_text', '')}")
            timings = msg.get("timings", {})
            if timings:
                total = timings.get("total_ms", 0)
                print(f"           ⏱  {total:.0f}ms total "
                      f"(stt={timings.get('stt_ms',0):.0f}ms "
                      f"brain={timings.get('brain_ms',0):.0f}ms "
                      f"tts={timings.get('tts_ms',0):.0f}ms)")

            if msg.get("end_call"):
                print("\n✅ Booking complete! Waiting for call_ended frame …")
                raw = await ws.recv()
                end = json.loads(raw)
                print(f"[CALL ENDED] reason={end.get('reason', '?')}")
                return

        # ── Clean close ────────────────────────────────────────────────────
        await ws.send(json.dumps({"type": "end"}))
        raw = await ws.recv()
        end = json.loads(raw)
        print(f"\n[CALL ENDED] {end}")


def main() -> None:
    parser = argparse.ArgumentParser(description="BrightSmile WS smoke-test")
    parser.add_argument(
        "--wav",
        default=None,
        help="Path to a WAV audio file to send as the first audio turn",
    )
    parser.add_argument(
        "--url",
        default="ws://localhost:8000",
        help="Base WebSocket URL of the backend server",
    )
    args = parser.parse_args()
    asyncio.run(run(args.url, args.wav))


if __name__ == "__main__":
    main()
