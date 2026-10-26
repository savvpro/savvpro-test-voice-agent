"""Tracking ID and phone-last-4 extractors.

Both extractors operate on ``digit_text`` from :class:`NormalizeResult`
(number words already converted to digits).
"""

from __future__ import annotations

import re

from app.brain.constants import RD_PHONETIC_PREFIXES

# ── Tracking ID extraction ────────────────────────────────────────────
#
# A valid tracking ID is one of the RD_PHONETIC_PREFIXES followed by
# exactly 8 digits.  Digits may be space-separated because the normalizer
# converts each number word to a separate digit token (e.g. "1 2 3 4 5 6 7 8").

def _build_tracking_pattern() -> re.Pattern[str]:
    """Compile a single regex that matches any RD prefix variant + 8 digits.

    The pattern captures:
      group 1: the prefix (for span tracking)
      group 2: the 8-digit portion (possibly with spaces)
    """
    # Sort prefixes longest-first so longer variants are tried before
    # shorter ones (e.g. "are dee" before "r d").
    sorted_prefixes = sorted(RD_PHONETIC_PREFIXES, key=len, reverse=True)
    escaped = [re.escape(p) for p in sorted_prefixes]
    prefix_alt = "|".join(escaped)

    # 8 digits, each optionally followed by whitespace before the next.
    # We use a non-greedy approach: digit followed by optional space, 7 times,
    # then one final digit.
    eight_digits = r"(\d(?:\s*\d){7})"

    pattern = rf"\b(?:{prefix_alt})\s*{eight_digits}"
    return re.compile(pattern, re.IGNORECASE)


_TRACKING_RE = _build_tracking_pattern()


def extract_tracking_ids(digit_text: str) -> list[str]:
    """Extract tracking IDs from normalised digit text.

    Args:
        digit_text: The ``digit_text`` output from the normalizer.

    Returns:
        A list of canonical tracking IDs (``RD########``, uppercase) in
        order of appearance.  Empty list if none found.
    """
    results: list[str] = []
    for match in _TRACKING_RE.finditer(digit_text):
        raw_digits = match.group(1)
        # Strip all whitespace from the captured digit group.
        digits = re.sub(r"\s+", "", raw_digits)
        if len(digits) == 8 and digits.isdigit():
            canonical = f"RD{digits}"
            results.append(canonical)
    return results


# ── Phone last-4 extraction ──────────────────────────────────────────

# Accept both typed digits (1234) and individually spoken digits normalized
# with spaces (1 2 3 4). Do not match a four-digit substring of a longer run.
_FOUR_DIGITS_RE = re.compile(r"(?<!\d)(\d(?:\s*\d){3})(?!\d)")


def extract_phone_last4(
    digit_text: str,
    exclude_digits: str | None = None,
) -> str | None:
    """Extract the caller's last 4 phone digits from normalised digit text.

    Args:
        digit_text: The ``digit_text`` output from the normalizer.
        exclude_digits: The 8 trailing digits of a tracking ID found in the
            same turn.  Any 4-digit substring that overlaps with these
            digits (i.e. is a contiguous substring of them) is ignored.

    Returns:
        A 4-digit string, or ``None`` if zero or multiple candidates remain
        after filtering (ambiguous).
    """
    # First, find all spans occupied by tracking IDs so we can exclude
    # 4-digit groups that overlap with them.
    tracking_spans: list[tuple[int, int]] = []
    for m in _TRACKING_RE.finditer(digit_text):
        tracking_spans.append((m.start(), m.end()))

    # Build the set of 4-digit substrings of the exclude_digits string.
    excluded_substrings: set[str] = set()
    if exclude_digits:
        clean = re.sub(r"\s+", "", exclude_digits)
        for i in range(len(clean) - 3):
            excluded_substrings.add(clean[i : i + 4])

    candidates: list[str] = []
    for m in _FOUR_DIGITS_RE.finditer(digit_text):
        # Skip if this match overlaps with any tracking ID span.
        start, end = m.start(), m.end()
        overlaps = any(
            ts <= start < te or ts < end <= te
            for ts, te in tracking_spans
        )
        if overlaps:
            continue

        digits = re.sub(r"\s+", "", m.group(1))
        # Skip if the digits are a substring of the excluded tracking ID digits.
        if digits in excluded_substrings:
            continue

        candidates.append(digits)

    if len(candidates) == 1:
        return candidates[0]
    # 0 or 2+ candidates → ambiguous or not found.
    return None
