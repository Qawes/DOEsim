# filepath: widgets/helpers.py
import os
import re
import time
from typing import Iterable, Optional

from PyQt6.QtWidgets import QWidget, QApplication, QToolTip, QLineEdit, QDoubleSpinBox, QCheckBox, QComboBox, QSpinBox
from PyQt6.QtCore import QRect
from PyQt6.QtGui import QCursor
from pathlib import Path

# Used:
def ensure_white_image(size: Optional[int] = 256) -> str:
    """Ensure a default white image exists and return its absolute path."""
    if size is None or size <= 0:
        size = 256
    try:
        ap_dir = os.path.join(os.getcwd(), "aperatures")
        os.makedirs(ap_dir, exist_ok=True)
        white_path = os.path.join(ap_dir, "white.png")
        if not os.path.exists(white_path):
            try:
                from PIL import Image as _PILImage
                img = _PILImage.new("L", (size, size), 255)
                img.save(white_path)
                print("Created default white image at:", white_path)
            except Exception:
                print("Warning: cannot create default white image.")
                pass
        return white_path
    except Exception:
        print("Warning: cannot ensure default white image.")
        return ""
    
def check_image_path(path: str) -> str:
    """Check if image path exists; if not, return default white image path."""
    abs_path = os.path.abspath(path) if path else None
    if abs_path and os.path.exists(abs_path):
        return abs_path
    print(f"Warning: No image found in'{path}'. Using default white image.")
    return ensure_white_image()

def set_working_dir(workspace_name: str, retain: bool = True) -> Path:
    """
    Determines and prepares the output directory for simulation results based on workspace name and retention preference.
    If retain is True, creates a timestamped subfolder. If False, uses the workspace folder and deletes previous Screen_*.png/gif files.
    Returns the Path to the output directory (guaranteed to exist).
    """
    import time
    # Ensure "simulation_results" folder exists
    sim_results_dir = Path("simulation_results")
    sim_results_dir.mkdir(parents=True, exist_ok=True)
    base_dir = sim_results_dir / workspace_name
    if retain:
        ts = int(time.time())
        output_dir = base_dir / str(ts)
    else:
        output_dir = base_dir
        # Delete previous Screen_*.png and Screen_*.gif files
        try:
            if output_dir.exists():
                for p in list(output_dir.glob("*.png")) + list(output_dir.glob("*.gif")):
                    try:
                        p.unlink()
                    except Exception:
                        pass
        except Exception:
            pass
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

def check_writeable_folder(path: str | os.PathLike) -> str | None:
    """
    Check if the given folder path exists and is writeable.
    Returns the absolute path if writeable, else None.
    """
    if not path:
        return None
    abs_path = os.path.abspath(os.fspath(path))
    try:
        if not os.path.isdir(abs_path):
            return None
        test_file = os.path.join(abs_path, ".write_test_tmp")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        return abs_path
    except Exception:
        return None

# --- Naming helpers ---
DEFAULT_ALLOWED_NAME_PATTERN = r'^[a-zA-Z0-9_ -]+$'

#TODO: please use these in place of duplicated code elsewhere
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
    return re.match(r'^(Aperture|Lens|Screen|Aperture\s+Result|Target\s+Intensity)\s+(\d+)$', str(name or "")) is not None


def extract_default_suffix(name: str) -> Optional[int]:
    m = re.match(r'^(Aperture|Lens|Screen|Aperture\s+Result|Target\s+Intensity)\s+(\d+)$', str(name or ""))
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
# TODO: please use this instead of implementing 600 different versions
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
#TODO: unused?
def abs_path(path: Optional[str]) -> Optional[str]:
    if not path:
        return path
    try:
        return path if os.path.isabs(path) else os.path.abspath(path)
    except Exception:
        return path

# TODO: unused?
def to_pref_path(path: str, use_relative: bool) -> str:
    if not path:
        return path
    if use_relative:
        try:
            return os.path.relpath(path, os.getcwd())
        except Exception:
            return path
    return path

# TODO: unused?
def normalize_path_for_display(stored_path: Optional[str], use_relative: bool) -> str:
    ap = abs_path(stored_path)
    if not ap:
        return ""
    return to_pref_path(ap, use_relative)


# --- Formatting ---

# TODO: whats this
def fmt_fixed(v: float, decimals: int = 2) -> str:
    try:
        return f"{float(v):.{int(decimals)}f}"
    except Exception:
        return str(v)

TYPE_APERTURE = "Aperture"
TYPE_LENS = "Lens"
TYPE_SCREEN = "Screen"
TYPE_APERTURE_RESULT = "ApertureResult"
TYPE_TARGET_INTENSITY = "TargetIntensity"

class Element:
    """
    Universal element data model used across UI and engine.
    - distance: float (mm)
    - element_type: engine token (lowercase) via property; display 'type' via property
    - params: dict for engine/runtime parameters (e.g., image_path, width_mm, height_mm, f, range flags)
    - name: optional display name
    - next: optional link for UI list management

    Also carries optional convenience attributes commonly used by the UI:
      focal_length, aperture_path, is_range, range_end, steps, aperture_width_mm, aperture_height_mm
    """
    def __init__(self,
                 name: str | None = None,
                 elem_type: str | None = None,
                 distance: float | int | None = None,
                 focal_length: float | int | None = None,
                 aperture_path: str | None = None,
                 is_range: bool | None = None,
                 range_end: float | int | None = None,
                 steps: int | None = None,
                 params: dict | None = None,
                 # Back-compat alias: allow engine-style constructor
                 element_type: str | None = None):
        self.name = name
        self._display_type = None
        # Accept either display type (elem_type) or engine type (element_type)
        if elem_type is not None:
            self._display_type = elem_type
        elif element_type is not None:
            # Use element_type setter mapping
            self.element_type = element_type
        self.distance = float(distance) if distance is not None else 0.0
        self.params = dict(params) if params is not None else {}
        # Optional fields used by the UI
        self.focal_length = focal_length
        self.aperture_path = aperture_path
        self.is_range = is_range
        self.range_end = float(range_end) if range_end is not None else None
        self.steps = int(steps) if steps is not None else None
        self.aperture_width_mm: float | None = None
        self.aperture_height_mm: float | None = None
        # Linked list support for UI ordering
        self.next: Element | None = None

    # UI property (Display type, e.g., 'Aperture')
    @property
    def type(self) -> str | None:
        return self._display_type

    @type.setter
    def type(self, v: str | None):
        self._display_type = v

    # Engine property (lowercase token, e.g., 'aperture')
    @property
    def element_type(self) -> str | None:
        if self._display_type is None:
            return None
        key = str(self._display_type).replace(' ', '').lower()
        mapping = {
            'aperture': 'aperture',
            'lens': 'lens',
            'screen': 'screen',
            'apertureresult': 'apertureresult',
            'targetintensity': 'targetintensity',
        }
        return mapping.get(key, key)

    @element_type.setter
    def element_type(self, v: str | None):
        if v is None:
            self._display_type = None
            return
        key = str(v).replace(' ', '').lower()
        reverse = {
            'aperture': 'Aperture',
            'lens': 'Lens',
            'screen': 'Screen',
            'apertureresult': 'Aperture Result',
            'targetintensity': 'Target Intensity',
        }
        self._display_type = reverse.get(key, v)


# --- GUI testing helpers (shared across tests) ---

def wait_until(predicate, timeout_ms: int = 5000, step_ms: int = 25) -> bool:
    start = time.time()
    while (time.time() - start) * 1000 < timeout_ms:
        QApplication.processEvents()
        try:
            if predicate():
                return True
        except Exception:
            pass
        time.sleep(step_ms / 1000.0)
    return False


def find_row_by_name(table, name: str) -> int:
    for r in range(getattr(table, 'rowCount')()):
        w = table.cellWidget(r, 0)
        if isinstance(w, QLineEdit) and w.text() == name:
            return r
    return -1


def set_name(table, row: int, new_name: str):
    editor = table.cellWidget(row, 0)
    if not isinstance(editor, QLineEdit):
        return
    editor.setText(new_name)
    try:
        editor.editingFinished.emit()
    except Exception:
        pass

# TODO: instead of lots of independent set_X, use a set_properties 
def set_distance(table, row: int, new_dist: float):
    w = table.cellWidget(row, 2)
    # If it's a single QDoubleSpinBox
    if isinstance(w, QDoubleSpinBox):
        w.setValue(new_dist)
        try:
            w.editingFinished.emit()
        except Exception:
            pass
        return
    # If it's a composite widget (range enabled): the "From" editor is the first QDoubleSpinBox
    if isinstance(w, QWidget):
        spins = w.findChildren(QDoubleSpinBox)
        if spins:
            # Sort by x-position to ensure [From, To]
            spins = sorted(spins, key=lambda s: s.geometry().x())
            spins[0].setValue(new_dist)
            try:
                spins[0].editingFinished.emit()
            except Exception:
                pass


def set_aperture_image_path(table, row: int, path: str):
    type_w = table.cellWidget(row, 1)
    if not isinstance(type_w, QComboBox):
        return
    if "aperture" not in type_w.currentText().strip().lower():
        return
    cell = table.cellWidget(row, 3)
    if cell is None:
        return
    line = cell.findChild(QLineEdit)
    if line is None:
        return
    line.setText(path)
    try:
        line.editingFinished.emit()
    except Exception:
        pass


def set_screen_range(table, row: int, is_enabled: bool, start_val: float | None = None, end_val: float | None = None, steps: int | None = None):
    # Toggle the checkbox
    val_cell = table.cellWidget(row, 3)
    if (val_cell is None):
        return
    chk = val_cell.findChild(QCheckBox)
    if (chk is None):
        return
    chk.setChecked(is_enabled)
    QApplication.processEvents()

    # Wait for the range UI (two spinboxes) to appear when enabling range
    if is_enabled:
        wait_until(
            lambda: isinstance(table.cellWidget(row, 2), QWidget)
                    and len(table.cellWidget(row, 2).findChildren(QDoubleSpinBox)) >= 2,
            timeout_ms=500
        )

    # Set steps if provided
    if steps is not None:
        sp = val_cell.findChild(QSpinBox)
        if sp is not None:
            sp.setValue(int(steps))
            try:
                sp.editingFinished.emit()
            except Exception:
                pass
            QApplication.processEvents()
            wait_until(
                lambda: isinstance(table.cellWidget(row, 2), QWidget)
                        and len(table.cellWidget(row, 2).findChildren(QDoubleSpinBox)) >= 2,
                timeout_ms=500
            )

    # Set start/end in distance cell if provided
    dist_cell = table.cellWidget(row, 2)
    if isinstance(dist_cell, QWidget):
        spins = dist_cell.findChildren(QDoubleSpinBox)
        # Ensure left-to-right ordering: [From, To]
        if len(spins) >= 2:
            spins = sorted(spins, key=lambda s: s.geometry().x())
        if start_val is not None and spins:
            spins[0].setValue(float(start_val))
            try:
                spins[0].editingFinished.emit()
            except Exception:
                pass
            QApplication.processEvents()
            dist_cell = table.cellWidget(row, 2)
            if isinstance(dist_cell, QWidget):
                spins = dist_cell.findChildren(QDoubleSpinBox)
                if len(spins) >= 2:
                    spins = sorted(spins, key=lambda s: s.geometry().x())
        if end_val is not None and len(spins) > 1:
            spins[1].setValue(float(end_val))
            try:
                spins[1].editingFinished.emit()
            except Exception:
                pass


def ensure_dirs():
    os.makedirs(os.path.join(os.getcwd(), "workspaces"), exist_ok=True)
    os.makedirs(os.path.join(os.getcwd(), "aperatures"), exist_ok=True)


def step_spin_to_value(spin: QDoubleSpinBox, target: float):
    """Drive a QDoubleSpinBox to target using stepUp/stepDown, not setValue.
    Uses a ladder of singleStep sizes for speed, then fine adjustment.
    """
    if not isinstance(spin, QDoubleSpinBox):
        return
    ladder = [10.0, 1.0, 0.1, 0.01]
    # Ensure target within spin range
    target = max(spin.minimum(), min(spin.maximum(), float(target)))
    for step in ladder:
        spin.setSingleStep(step)
        QApplication.processEvents()
        # Move upwards in coarse steps
        while (target - spin.value()) >= (step - 1e-12):
            spin.stepUp()
            QApplication.processEvents()
        # If overshot, step down
        while (spin.value() - target) >= (step - 1e-12):
            spin.stepDown()
            QApplication.processEvents()
    try:
        spin.editingFinished.emit()
    except Exception:
        pass
    QApplication.processEvents()


def step_distance(table, row: int, target: float):
    """Find the distance spinbox cell for a row and step it to target.
    Works for single spin and for composite range widget (uses the From spin).
    """
    w = table.cellWidget(row, 2)
    spin = None
    if isinstance(w, QDoubleSpinBox):
        spin = w
    elif isinstance(w, QWidget):
        spins = w.findChildren(QDoubleSpinBox)
        if spins:
            # Sort left-to-right, use first as 'From'
            spin = sorted(spins, key=lambda s: s.geometry().x())[0]
    if isinstance(spin, QDoubleSpinBox):
        step_spin_to_value(spin, target)

# TODO: use this in tests?
def select_row_and_wait(table, row: int, timeout_ms: int = 1000) -> bool:
    try:
        table.clearSelection()
        QApplication.processEvents()
        table.setFocus()
        table.selectRow(int(row))
        QApplication.processEvents()
        return wait_until(
            lambda: hasattr(table, 'selectionModel') and table.selectionModel() is not None and any(
                idx.row() == row for idx in table.selectionModel().selectedRows()
            ),
            timeout_ms=timeout_ms,
        )
    except Exception:
        return False

# TODO: update  for robust type getting, test3 fails due to this?
def get_row_types(table) -> list[str]:
    types: list[str] = []
    for r in range(1, getattr(table, 'rowCount')()):
        w = table.cellWidget(r, 1)
        if isinstance(w, QComboBox):
            types.append(w.currentText())
    return types


# TODO: update  for robust type getting, test9 fails due to this?
def get_row_names(table):  # type: ignore
    """Return a list of element names (from column 0, QLineEdit, for rows 1+)."""
    names = []
    for r in range(1, getattr(table, 'rowCount')()):
        w = table.cellWidget(r, 0)
        if isinstance(w, QLineEdit):
            names.append(w.text())
    return names
