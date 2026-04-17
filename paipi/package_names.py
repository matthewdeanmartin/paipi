from __future__ import annotations

import re

_LIST_MARKER_RE = re.compile(r"^(?:[*\-–—]\s+|\d+[.)]\s+)")
_VALID_PACKAGE_NAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,213})$")
_PEP503_NORMALIZE_RE = re.compile(r"[-_.]+")
_MAX_UNSEPARATED_NAME_LENGTH = 64


def canonicalize_package_name(name: str) -> str:
    """Normalize a package name with PEP 503 rules."""
    return _PEP503_NORMALIZE_RE.sub("-", name.strip()).lower()


def is_pep503_normalized(name: str) -> bool:
    """Return True when the name is already PEP 503-normalized."""
    stripped = name.strip()
    return bool(stripped) and stripped == canonicalize_package_name(stripped)


def is_valid_package_name(name: str) -> bool:
    """Return True when the name is plausibly a Python package name."""
    stripped = name.strip()
    if not stripped or not _VALID_PACKAGE_NAME_RE.fullmatch(stripped):
        return False

    if (
        len(stripped) > _MAX_UNSEPARATED_NAME_LENGTH
        and "-" not in stripped
        and "_" not in stripped
        and "." not in stripped
    ):
        return False

    return True


def extract_candidate_package_name(line: str) -> str | None:
    """Extract a plausible package name from a single LLM response line."""
    candidate = _LIST_MARKER_RE.sub("", line.strip())
    candidate = candidate.strip().strip("`\"'")
    if candidate.endswith(","):
        candidate = candidate[:-1].rstrip()

    if (
        not candidate
        or any(ch.isspace() for ch in candidate)
        or ":" in candidate
        or "/" in candidate
        or "\\" in candidate
        or candidate.startswith(("{", "[", "(", "<"))
        or candidate.endswith((":", "{", "[", "("))
    ):
        return None

    if not is_valid_package_name(candidate):
        return None

    return candidate
