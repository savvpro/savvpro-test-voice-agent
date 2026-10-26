"""Guard test: fail if any LLM or AI SDK appears in requirements.txt.

The brain must be our own code.  This test enforces that rule at the
dependency level so an accidental ``pip install openai`` cannot slip
through unnoticed.
"""

from __future__ import annotations

import pathlib

import pytest

# Substrings that indicate an LLM / AI SDK dependency.
_BANNED = (
    "openai",
    "anthropic",
    "google-generativeai",
    "langchain",
    "llama",
    "cohere",
    "tiktoken",
    "transformers",
    "huggingface",
    "replicate",
    "mistral",
    "groq",
    "ai21",
    "boto3-bedrock",
    "vertexai",
)

_REQUIREMENTS = pathlib.Path(__file__).resolve().parents[1] / "requirements.txt"


@pytest.mark.parametrize("banned", _BANNED)
def test_requirements_has_no_llm_sdk(banned: str) -> None:
    """requirements.txt must not contain *{banned}*."""
    assert _REQUIREMENTS.exists(), f"requirements.txt not found at {_REQUIREMENTS}"
    contents = _REQUIREMENTS.read_text(encoding="utf-8").lower()
    assert banned not in contents, (
        f"Banned AI/LLM dependency '{banned}' found in requirements.txt. "
        "The brain must be our own code — no LLM SDKs allowed."
    )
