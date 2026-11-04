# Initialise backend package and make the sibling `ai-tool/src` directory importable.
# The `voice_agent` package lives under `dental-voice-assistant/ai-tool/src`.
# Adding this directory to `sys.path` lets `from voice_agent.stt.fake_stt import FakeSTT`
# resolve correctly when the FastAPI app starts.

import sys
from pathlib import Path

# Resolve the repository root (dental-voice-assistant)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_AI_TOOL_SRC = _REPO_ROOT / "ai-tool" / "src"

# Insert at front of import search path if not already present
if str(_AI_TOOL_SRC) not in sys.path:
    sys.path.insert(0, str(_AI_TOOL_SRC))
