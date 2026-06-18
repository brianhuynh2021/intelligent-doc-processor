from __future__ import annotations

import re
import unicodedata
from pathlib import PurePosixPath, PureWindowsPath

_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._-]+")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def strip_control_chars(text: str) -> str:
    """Remove ASCII control characters (keeps \\t, \\n, \\r)."""
    return _CONTROL_CHARS.sub("", text)


def safe_display_filename(name: str | None, max_len: int = 255) -> str:
    """Filename safe for DB storage and display.

    Strips path components and control chars, keeps Unicode (e.g. Vietnamese),
    caps length. Use sanitize_filename() when the name will hit a filesystem.
    """
    if not name:
        return "unnamed"
    base = PurePosixPath(name).name or PureWindowsPath(name).name or name
    base = unicodedata.normalize("NFKC", base)
    base = strip_control_chars(base).strip()
    if not base:
        return "unnamed"
    return base[:max_len]


def sanitize_filename(name: str | None, max_len: int = 200) -> str:
    """Make a filename safe for storage and display.

    Strips path components, control chars, normalizes unicode, collapses
    unsafe runs to '_', and caps total length. Returns 'unnamed' for empty
    input.
    """
    if not name:
        return "unnamed"

    base = PurePosixPath(name).name or PureWindowsPath(name).name or name
    base = unicodedata.normalize("NFKC", base)
    base = strip_control_chars(base).strip()
    base = _FILENAME_SAFE.sub("_", base).strip("._-")

    if not base:
        return "unnamed"

    if len(base) <= max_len:
        return base

    suffix_idx = base.rfind(".")
    if suffix_idx > 0 and len(base) - suffix_idx <= 16:
        ext = base[suffix_idx:]
        return base[: max_len - len(ext)] + ext
    return base[:max_len]
