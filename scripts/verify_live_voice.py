"""Verify generated speech through the running app and real Groq STT, without reading keys."""
import json
from pathlib import Path
from uuid import uuid4

import httpx


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    with httpx.Client(base_url="http://127.0.0.1:8088", headers={"Origin": "http://127.0.0.1:8088"}, timeout=60, trust_env=False) as client:
        response = client.post("/api/v1/session")
        response.raise_for_status()
        snapshot = response.json()
        for index in range(1, 4):
            audio = (root / ".artifacts" / f"live-voice-{index}.wav").read_bytes()
            response = client.post("/api/v1/transcriptions", content=audio, headers={"Content-Type": "audio/wav"})
            if response.status_code != 200:
                print(json.dumps({"stage": "transcription", "status": response.status_code, "error": response.json().get("error", {}).get("code")}))
                raise SystemExit(1)
            transcript = response.json()["text"]
            response = client.post("/api/v1/turns", json={"text": transcript, "request_id": str(uuid4()), "expected_version": snapshot["version"]})
            response.raise_for_status()
            snapshot = response.json()
            print(json.dumps({"turn": index, "transcript": transcript, "state": snapshot["state"], "reply": snapshot["reply"]}))
        if snapshot.get("receipt", {}).get("status") != "pending_review":
            raise SystemExit("The live voice flow did not finish with a pending claim.")
        print("LIVE_GROQ_VOICE_FLOW_PASSED")


if __name__ == "__main__":
    main()
