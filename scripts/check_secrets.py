"""Small offline preflight for accidental credentials in deliverable source files."""

import re
import subprocess
from pathlib import Path

PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "OpenAI-style key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}"),
    "GitHub token": re.compile(
        r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"
    ),
    "AWS access ID": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "assigned credential": re.compile(
        r"""(?im)\b(?:api_key|secret_key|password|access_token)\s*[:=]\s*["'](?!example|placeholder|test|fake)[A-Za-z0-9_+/=-]{16,}["']"""
    ),
}


def scan():
    names = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
        )
        .decode()
        .split("\0")
    )
    failures = []
    checked = 0
    for name in sorted(set(filter(None, names))):
        path = Path(name)
        if not path.is_file():
            continue
        data = path.read_bytes()
        if b"\0" in data:
            continue
        content = data.decode("utf-8", errors="replace")
        checked += 1
        if path.name == ".env":
            failures.append((name, "environment file must be ignored"))
        for label, pattern in PATTERNS.items():
            if pattern.search(content):
                failures.append((name, label))
    for name, label in failures:
        print(f"FAIL {name}: {label}")
    print(
        f"Checked {checked} source/evidence files; {len(failures)} suspected credentials. Values are never printed."
    )
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(scan())
