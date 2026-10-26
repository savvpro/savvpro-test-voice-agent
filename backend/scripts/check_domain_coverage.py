"""Enforce domain branch-aware coverage using the existing coverage.py report."""

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--minimum", type=float, default=95)
    parser.add_argument("--report", type=Path, default=Path("coverage.json"))
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    files = [
        data["summary"]
        for name, data in report["files"].items()
        if "/domain/" in name.replace("\\", "/")
    ]
    possible = sum(data["num_statements"] + data["num_branches"] for data in files)
    covered = sum(data["covered_lines"] + data["covered_branches"] for data in files)
    if not possible:
        raise SystemExit("No domain coverage was measured; refusing to pass the gate.")
    percentage = 100 * covered / possible
    print(f"Domain branch-aware coverage: {percentage:.2f}% (required {args.minimum:.0f}%)")
    return 0 if percentage >= args.minimum else 1


if __name__ == "__main__":
    raise SystemExit(main())
