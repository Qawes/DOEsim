from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QFormLayout, QCheckBox, QDoubleSpinBox
from PyQt6.QtCore import Qt, QSettings

SET_AUTO_OPEN_NEW_WORKSPACE = 'auto_open_new_workspace'
SET_ASK_BEFORE_CLOSING = 'ask_before_closing'
SET_CONFIRM_ON_SAVE = 'confirm_on_save'
SET_ENABLE_SCROLLWHEEL = 'enable_scrollwheel'
SET_SELECT_ALL_ON_FOCUS = 'select_all_on_focus'
SET_RENAME_ON_TYPE_CHANGE = 'rename_on_type_change'
SET_WARN_BEFORE_DELETE = 'warn_before_delete'
SET_USE_RELATIVE_PATHS = 'use_relative_paths'
SET_DEFAULT_ELEMENT_OFFSET_MM = 'default_element_offset_mm'

# Module-level defaults to mirror main_window preferences
_DEFAULT_PREFS = {
    SET_AUTO_OPEN_NEW_WORKSPACE: True,
    SET_ASK_BEFORE_CLOSING: True,
    SET_CONFIRM_ON_SAVE: True,
    SET_ENABLE_SCROLLWHEEL: True,
    SET_SELECT_ALL_ON_FOCUS: True,
    SET_RENAME_ON_TYPE_CHANGE: False,
    SET_WARN_BEFORE_DELETE: True,
    SET_USE_RELATIVE_PATHS: True,
    SET_DEFAULT_ELEMENT_OFFSET_MM: 10.0,
}

def _coerce_type(val, typ):
    if typ is bool:
        if isinstance(val, bool):
            return val
        s = str(val).strip().lower()
        return s in ("1", "true", "yes", "on")
    try:
        return typ(val)
    except Exception:
        return val

def getpref(key: str, default=None):
    """Read an application preference from QSettings with sensible defaults.

    Args:
        key: Preference key name.
        default: Optional default; if None, uses module defaults when available.
    Returns:
        The stored preference value (type-coerced to the default's type when possible).
    """
    s = QSettings("diffractsim", "app")
    if default is None and key in _DEFAULT_PREFS:
        default = _DEFAULT_PREFS[key]
    if default is None:
        return s.value(key, None)
    typ = type(default)
    try:
        return s.value(key, default, type=typ)
    except Exception:
        v = s.value(key, default)
        return _coerce_type(v, typ)

def setpref(key: str, value):
    """Save an application preference to QSettings."""
    s = QSettings("diffractsim", "app")
    s.setValue(key, value)

class PreferencesTab(QWidget):
    """Settings tab for application preferences."""
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._mw = main_window
        root = QVBoxLayout(self)

        # Workspace behavior
        grp_workspace = QGroupBox("Workspace behavior", self)
        flw = QFormLayout(grp_workspace)
        self.chk_auto_open = QCheckBox("Auto open new workspace when last is closed", grp_workspace)
        self.chk_ask_before_close = QCheckBox("Ask before closing workspaces", grp_workspace)
        flw.addRow(self.chk_auto_open)
        flw.addRow(self.chk_ask_before_close)
        grp_workspace.setLayout(flw)
        root.addWidget(grp_workspace)

        # UI interactions
        grp_ui = QGroupBox("UI interactions", self)
        flu = QFormLayout(grp_ui)
        self.chk_confirm_save = QCheckBox("Display confirmation on saving workspaces", grp_ui)
        self.chk_enable_scrollwheel = QCheckBox("Enable scrollwheel in elements table to modify dropdowns and spinboxes", grp_ui)
        self.chk_select_all_on_focus = QCheckBox("Select all text when clicking into input fields", grp_ui)
        self.chk_rename_on_type = QCheckBox("Change element name when changing its type (only if default-generated)", grp_ui)
        self.chk_warn_before_delete = QCheckBox("Warn before deleting elements", grp_ui)
        flu.addRow(self.chk_confirm_save)
        flu.addRow(self.chk_enable_scrollwheel)
        flu.addRow(self.chk_select_all_on_focus)
        flu.addRow(self.chk_rename_on_type)
        flu.addRow(self.chk_warn_before_delete)
        grp_ui.setLayout(flu)
        root.addWidget(grp_ui)

        # Paths and defaults
        grp_paths = QGroupBox("Paths and defaults", self)
        flp = QFormLayout(grp_paths)
        self.chk_use_relative = QCheckBox("Use relative paths", grp_paths)
        self.spin_default_offset = QDoubleSpinBox()
        self.spin_default_offset.setRange(0.0, 100000.0)
        self.spin_default_offset.setDecimals(2)
        self.spin_default_offset.setSuffix(" mm")
        flp.addRow(self.chk_use_relative)
        flp.addRow("Default distance between elements when adding to the table", self.spin_default_offset)
        grp_paths.setLayout(flp)
        root.addWidget(grp_paths)

        root.addStretch()

        # Initialize values from preferences
        self._load_current()
        # Wire up changes to module-level setpref
        self.chk_auto_open.toggled.connect(lambda v: setpref('auto_open_new_workspace', bool(v)))
        self.chk_ask_before_close.toggled.connect(lambda v: setpref('ask_before_closing', bool(v)))
        self.chk_confirm_save.toggled.connect(lambda v: setpref('confirm_on_save', bool(v)))
        self.chk_enable_scrollwheel.toggled.connect(lambda v: setpref('enable_scrollwheel', bool(v)))
        self.chk_select_all_on_focus.toggled.connect(lambda v: setpref('select_all_on_focus', bool(v)))
        self.chk_rename_on_type.toggled.connect(lambda v: setpref('rename_on_type_change', bool(v)))
        self.chk_warn_before_delete.toggled.connect(lambda v: setpref('warn_before_delete', bool(v)))
        self.chk_use_relative.toggled.connect(self._notify_use_relative_paths_changed)
        # Apply default distance immediately as well
        self.spin_default_offset.valueChanged.connect(lambda v: (setpref('default_element_offset_mm', float(v)), self._mw._apply_default_distance(float(v))))

    def _notify_use_relative_paths_changed(self, v: bool):
        """Save preference and ask all open PhysicalSetupVisualizer widgets to refresh path displays."""
        try:
            setpref('use_relative_paths', bool(v))
        except Exception:
            pass
        # Notify all open visualizers
        try:
            tabs = getattr(self._mw, 'tabs', None)
            if tabs is not None:
                for i in range(tabs.count()):
                    w = tabs.widget(i)
                    vis = getattr(w, 'visualizer', None)
                    if vis is not None and hasattr(vis, 'refresh_aperture_path_display'):
                        try:
                            vis.refresh_aperture_path_display()
                        except Exception:
                            continue
        except Exception:
            pass

    def _load_current(self):
        self.chk_auto_open.setChecked(bool(getpref('auto_open_new_workspace')))
        self.chk_ask_before_close.setChecked(bool(getpref('ask_before_closing')))
        self.chk_confirm_save.setChecked(bool(getpref('confirm_on_save')))
        self.chk_enable_scrollwheel.setChecked(bool(getpref('enable_scrollwheel')))
        self.chk_select_all_on_focus.setChecked(bool(getpref('select_all_on_focus')))
        self.chk_rename_on_type.setChecked(bool(getpref('rename_on_type_change')))
        self.chk_warn_before_delete.setChecked(bool(getpref('warn_before_delete')))
        self.chk_use_relative.setChecked(bool(getpref('use_relative_paths')))
        self.spin_default_offset.setValue(float(getpref('default_element_offset_mm')))

class PreferencesWindow(QWidget):
    """Standalone window that hosts the PreferencesTab."""
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        layout = QVBoxLayout(self)
        self._tab = PreferencesTab(main_window, self)
        layout.addWidget(self._tab)
        self.setLayout(layout)
        # Make it a reasonable default size
        self.resize(520, 480)
