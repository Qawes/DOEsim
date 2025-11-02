# filepath: widgets/helpers.py
import os
import re
from typing import Iterable, Optional

from PyQt6.QtWidgets import QWidget, QApplication, QToolTip
from PyQt6.QtCore import QRect
from PyQt6.QtGui import QCursor

# --- Naming helpers ---
DEFAULT_ALLOWED_NAME_PATTERN = r'^[a-zA-Z0-9_ -]+$'


def is_valid_name(name: str, min_len: int = 3, pattern: str = DEFAULT_ALLOWED_NAME_PATTERN):
    """Validate a display name against length and allowed characters.
    Returns True if valid, or an error message string if invalid.
    """
    if name is None:
        return f"Name is required."
    if len(name) < int(min_len):
        return f"Name must be at least {int(min_len)} characters long."
    if not re.match(pattern, name):
        return "Name can only contain letters, numbers, spaces, underscores, and hyphens."
    return True


def filter_to_accepted_chars(name: str, pattern: str = DEFAULT_ALLOWED_NAME_PATTERN) -> str:
    """Return a version of 'name' where characters not accepted by the pattern are replaced with '_'."""
    return _sanitize_name_for_pattern(name, pattern)


def validate_name_against(name: str,
                          existing: Iterable[str],
                          min_len: int = 3,
                          pattern: str = DEFAULT_ALLOWED_NAME_PATTERN,
                          exclude: Optional[str] = None):
    """Validate 'name' for length, allowed characters, and uniqueness among 'existing'.
    Returns True if valid/unique, else a concise error string.
    Excludes an optional 'exclude' name from duplicate detection (useful when renaming in-place).
    """
    vr = is_valid_name(name, min_len, pattern)
    if vr is not True:
        return vr
    s = set(str(x) for x in existing)
    if exclude is not None:
        try:
            s.discard(str(exclude))
        except Exception:
            pass
    if str(name) in s:
        return f"A name '{name}' already exists."
    return True


def _sanitize_name_for_pattern(name: str, pattern: str = DEFAULT_ALLOWED_NAME_PATTERN) -> str:
    # For the default pattern, replace any disallowed char with underscore
    # Allowed: letters, digits, space, underscore, hyphen
    # If a different pattern is supplied, fall back to conservative replacement
    try:
        return re.sub(r'[^a-zA-Z0-9_ -]', '_', str(name or ''))
    except Exception:
        return str(name or '').replace(',', '_').replace('.', '_')


def suggest_unique_name(base: str, existing: Iterable[str], min_len: int = 3, pattern: str = DEFAULT_ALLOWED_NAME_PATTERN) -> str:
    """Return a name derived from 'base' that is valid and unique among 'existing'.
    Strategy:
      - If base invalid or duplicate, derive a candidate.
      - If base ends with <delim><number>, where delim is in ' ', '-', '_', '.', ',', increment number; else append _2.
      - Sanitize prefix to meet validation pattern to avoid infinite loops on invalid chars.
    """
    existing_set = set([str(x) for x in existing])
    # First try base if valid and unused
    if is_valid_name(base, min_len, pattern) is True and base not in existing_set:
        return base
    # Try to parse numeric suffix with multiple delimiters
    m = re.match(r'^(.*?)([ _\-\.,])(\d+)$', str(base or ""))
    if m:
        raw_prefix = m.group(1)
        raw_delim = m.group(2)
        counter = int(m.group(3)) + 1
    else:
        raw_prefix = base or "Workspace"
        raw_delim = '_'
        counter = 2
    # Sanitize prefix for allowed pattern
    prefix = filter_to_accepted_chars(raw_prefix, pattern).strip()
    if not prefix:
        prefix = "Workspace"
    # Use only allowed delimiters in output
    delim = raw_delim if raw_delim in (' ', '-', '_') else '_'
    # Generate candidates safely
    while True:
        candidate = f"{prefix}{delim}{counter}"
        if is_valid_name(candidate, min_len, pattern) is True and candidate not in existing_set:
            return candidate
        counter += 1


def is_default_generated_element_name(name: str) -> bool:
    return re.match(r'^(Aperture|Lens|Screen)\s+(\d+)$', str(name or "")) is not None


def extract_default_suffix(name: str) -> Optional[int]:
    m = re.match(r'^(Aperture|Lens|Screen)\s+(\d+)$', str(name or ""))
    if not m:
        return None
    try:
        return int(m.group(2))
    except Exception:
        return None


def generate_unique_default_name(base_type: str, existing: Iterable[str]) -> str:
    i = 1
    existing_set = set([str(x) for x in existing])
    while True:
        candidate = f"{base_type} {i}"
        if candidate not in existing_set:
            return candidate
        i += 1


def name_exists(name: str, existing: Iterable[str]) -> bool:
    s = set([str(x) for x in existing])
    return str(name) in s


# --- Slug helpers for filenames ---

def slugify(nm: Optional[str]) -> str:
    s = (nm or "screen").strip()
    if not s:
        s = "screen"
    return "".join(ch if (ch.isalnum() or ch in ("_", "-")) else "_" for ch in s)


# --- Tooltip helper ---

def show_temp_tooltip(widget: QWidget, text: str, duration_ms: int = 3000):
    """Show a temporary tooltip near a widget, with fallbacks if needed."""
    try:
        pos = widget.mapToGlobal(widget.rect().bottomLeft())
        QToolTip.showText(pos, text, widget, widget.rect(), int(duration_ms))
        return
    except Exception:
        pass
    try:
        fw = QApplication.focusWidget()
        if fw is not None:
            pos = fw.mapToGlobal(fw.rect().center())
            QToolTip.showText(pos, text, fw, fw.rect(), int(duration_ms))
        else:
            pos = QCursor.pos()
            QToolTip.showText(pos, text, None, QRect(), int(duration_ms))
    except Exception:
        pass


# --- Path helpers ---

def abs_path(path: Optional[str]) -> Optional[str]:
    if not path:
        return path
    try:
        return path if os.path.isabs(path) else os.path.abspath(path)
    except Exception:
        return path


def to_pref_path(path: str, use_relative: bool) -> str:
    if not path:
        return path
    if use_relative:
        try:
            return os.path.relpath(path, os.getcwd())
        except Exception:
            return path
    return path


def normalize_path_for_display(stored_path: Optional[str], use_relative: bool) -> str:
    ap = abs_path(stored_path)
    if not ap:
        return ""
    return to_pref_path(ap, use_relative)


# --- Formatting ---

def fmt_fixed(v: float, decimals: int = 2) -> str:
    try:
        return f"{float(v):.{int(decimals)}f}"
    except Exception:
        return str(v)
