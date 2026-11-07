"""Test to guarantee NO LLM or LLM SDK is imported anywhere in ai-tool/src."""

from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_MODULES = {
    "openai",
    "anthropic",
    "google.generativeai",
    "gemini",
    "mistralai",
    "langchain",
    "llama_index",
    "transformers",
    "torch",
    "onnx",
}


def test_no_forbidden_llm_imports() -> None:
    src_dir = Path(__file__).resolve().parent.parent.parent / "src"
    assert src_dir.exists(), f"Source dir not found: {src_dir}"

    for py_file in src_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in FORBIDDEN_MODULES:
                        assert not alias.name.startswith(forbidden), (
                            f"Forbidden LLM import '{alias.name}' in {py_file}"
                        )
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for forbidden in FORBIDDEN_MODULES:
                    assert not mod.startswith(forbidden), (
                        f"Forbidden LLM import from '{mod}' in {py_file}"
                    )
