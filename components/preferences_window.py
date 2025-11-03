from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QFormLayout, QCheckBox, QDoubleSpinBox, QSpinBox
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QPushButton, QMessageBox

SET_AUTO_OPEN_NEW_WORKSPACE = 'auto_open_new_workspace'
SET_ASK_BEFORE_CLOSING = 'ask_before_closing'
SET_CONFIRM_ON_SAVE = 'confirm_on_save'
SET_ENABLE_SCROLLWHEEL = 'enable_scrollwheel'
SET_SELECT_ALL_ON_FOCUS = 'select_all_on_focus'
SET_RENAME_ON_TYPE_CHANGE = 'rename_on_type_change'
SET_WARN_BEFORE_DELETE = 'warn_before_delete'
SET_USE_RELATIVE_PATHS = 'use_relative_paths'
SET_DEFAULT_ELEMENT_OFFSET_MM = 'default_element_offset_mm'
SET_DEFAULT_LENS_FOCUS_MM = 'default_lens_focus_mm' 
SET_OPEN_TAB_ON_STARTUP = 'open_tab_on_startup'
SET_RETAIN_WORKING_FILES = 'retain_working_files'
SET_AUTO_GENERATE_GIF = 'auto_generate_gif'
SET_COMMA_AS_DECIMAL = 'comma_as_decimal' # TODO: Make this work
SET_ERR_MESS_DUR = 'error_message_duration_ms'

# Module-level defaults to mirror main_window preferences
_DEFAULT_PREFS = {
    SET_AUTO_OPEN_NEW_WORKSPACE: False,
    SET_OPEN_TAB_ON_STARTUP: False,
    SET_ASK_BEFORE_CLOSING: True,
    SET_CONFIRM_ON_SAVE: True,
    SET_ENABLE_SCROLLWHEEL: False,
    SET_SELECT_ALL_ON_FOCUS: True,
    SET_RENAME_ON_TYPE_CHANGE: True,
    SET_WARN_BEFORE_DELETE: True,
    SET_USE_RELATIVE_PATHS: True,
    SET_DEFAULT_ELEMENT_OFFSET_MM: 10.0,
    SET_DEFAULT_LENS_FOCUS_MM: 1000.0,
    SET_RETAIN_WORKING_FILES: True,
    SET_AUTO_GENERATE_GIF: True,
    SET_ERR_MESS_DUR: 3000,
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
        self.chk_auto_open = QCheckBox("Auto open new workspace when none is present", grp_workspace)
        self.chk_auto_open.setToolTip("If enabled, a new workspace will be created automatically whenever the last workspace is closed.")
        self.chk_open_on_startup = QCheckBox("Open an empty workspace on startup", grp_workspace)
        self.chk_open_on_startup.setToolTip("If enabled, a new workspace will be created automatically when the application starts.")
        self.chk_ask_before_close = QCheckBox("Ask before closing workspaces", grp_workspace)
        self.chk_ask_before_close.setToolTip("Prompt for confirmation before closing a workspace tab. For the last tab, the prompt adapts based on the auto-open preference.")
        flw.addRow(self.chk_auto_open)
        flw.addRow(self.chk_open_on_startup)
        flw.addRow(self.chk_ask_before_close)
        grp_workspace.setLayout(flw)
        root.addWidget(grp_workspace)

        # UI interactions
        grp_ui = QGroupBox("UI interactions", self)
        flu = QFormLayout(grp_ui)
        self.chk_confirm_save = QCheckBox("Display confirmation on saving workspaces", grp_ui)
        self.chk_confirm_save.setToolTip("Show a confirmation message after successfully saving a workspace.")
        self.chk_enable_scrollwheel = QCheckBox("Enable scrollwheel in elements table to modify dropdowns and spinboxes", grp_ui)
        self.chk_enable_scrollwheel.setToolTip("Allow using the mouse wheel to change values in dropdowns and spin boxes in the elements table.")
        self.chk_select_all_on_focus = QCheckBox("Select all text when clicking into input fields", grp_ui)
        self.chk_select_all_on_focus.setToolTip("Automatically select all text when an input field gains focus.")
        self.chk_rename_on_type = QCheckBox("Change element name when changing its type (only if default-generated)", grp_ui)
        self.chk_rename_on_type.setToolTip("If enabled, default-generated element names will update when you change the element type.")
        self.chk_warn_before_delete = QCheckBox("Warn before deleting elements", grp_ui)
        self.chk_warn_before_delete.setToolTip("Ask for confirmation before deleting elements from the setup.")
        # Error message duration spinbox
        self.spin_err_dur = QSpinBox(grp_ui)
        self.spin_err_dur.setRange(500, 20000)
        self.spin_err_dur.setSingleStep(250)
        self.spin_err_dur.setSuffix(" ms")
        self.spin_err_dur.setToolTip("Duration for temporary error messages (e.g., aborted rename).")
        flu.addRow(self.chk_confirm_save)
        flu.addRow(self.chk_enable_scrollwheel)
        flu.addRow(self.chk_select_all_on_focus)
        flu.addRow(self.chk_rename_on_type)
        flu.addRow(self.chk_warn_before_delete)
        flu.addRow("Error message display time", self.spin_err_dur)
        grp_ui.setLayout(flu)
        root.addWidget(grp_ui)

        # Output options
        grp_output = QGroupBox("Output", self)
        flo = QFormLayout(grp_output)
        self.chk_retain_files = QCheckBox("Retain generated screen files", grp_output)
        self.chk_retain_files.setToolTip("Keep generated screen images and metadata in timestamped subfolders instead of cleaning them up.")
        self.chk_auto_gif = QCheckBox("Auto-generate GIF for screen ranges", grp_output)
        self.chk_auto_gif.setToolTip("Automatically create an animated GIF for screen distance ranges after solving.")
        flo.addRow(self.chk_retain_files)
        flo.addRow(self.chk_auto_gif)
        grp_output.setLayout(flo)
        root.addWidget(grp_output)

        # Paths and defaults
        grp_paths = QGroupBox("Paths and defaults", self)
        flp = QFormLayout(grp_paths)
        self.chk_use_relative = QCheckBox("Use relative paths", grp_paths)
        self.chk_use_relative.setToolTip("Store aperture file paths relative to the workspace or project folder when possible.")
        self.spin_default_offset = QDoubleSpinBox()
        self.spin_default_offset.setRange(0.0, 100000.0)
        self.spin_default_offset.setDecimals(2)
        self.spin_default_offset.setSuffix(" mm")
        self.spin_default_offset.setToolTip("Distance (in millimeters) to insert between newly added elements by default.")
        self.spin_default_lens_focus = QDoubleSpinBox()
        self.spin_default_lens_focus.setRange(0.1, 100000.0)
        self.spin_default_lens_focus.setDecimals(2)
        self.spin_default_lens_focus.setSuffix(" mm")
        self.spin_default_lens_focus.setToolTip("Default focal length (in millimeters) for newly added lenses.")
        flp.addRow(self.chk_use_relative)
        flp.addRow("Default distance between elements when adding to the table", self.spin_default_offset)
        flp.addRow("Default lens focal length", self.spin_default_lens_focus)
        grp_paths.setLayout(flp)
        root.addWidget(grp_paths)

        # Maintenance
        grp_maint = QGroupBox("Maintenance", self)
        flm = QFormLayout(grp_maint)
        # Right-align the reset button
        from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        self.btn_reset_settings = QPushButton("Reset all settings to defaults", grp_maint)
        self.btn_reset_settings.setToolTip("Deletes all saved user settings (window geometry, layouts, and preferences)")
        self.btn_reset_settings.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        btn_layout.addWidget(self.btn_reset_settings)
        flm.addRow(btn_layout)
        grp_maint.setLayout(flm)
        root.addWidget(grp_maint)

        root.addStretch()

        # Initialize values from preferences
        self._load_current()
        # Wire up changes to module-level setpref using shared constants
        self.chk_auto_open.toggled.connect(lambda v: setpref(SET_AUTO_OPEN_NEW_WORKSPACE, bool(v)))
        self.chk_ask_before_close.toggled.connect(lambda v: setpref(SET_ASK_BEFORE_CLOSING, bool(v)))
        self.chk_open_on_startup.toggled.connect(lambda v: setpref(SET_OPEN_TAB_ON_STARTUP, bool(v)))
        self.chk_confirm_save.toggled.connect(lambda v: setpref(SET_CONFIRM_ON_SAVE, bool(v)))
        self.chk_enable_scrollwheel.toggled.connect(lambda v: setpref(SET_ENABLE_SCROLLWHEEL, bool(v)))
        self.chk_select_all_on_focus.toggled.connect(lambda v: setpref(SET_SELECT_ALL_ON_FOCUS, bool(v)))
        self.chk_rename_on_type.toggled.connect(lambda v: setpref(SET_RENAME_ON_TYPE_CHANGE, bool(v)))
        self.chk_warn_before_delete.toggled.connect(lambda v: setpref(SET_WARN_BEFORE_DELETE, bool(v)))
        self.chk_retain_files.toggled.connect(lambda v: setpref(SET_RETAIN_WORKING_FILES, bool(v)))
        self.chk_auto_gif.toggled.connect(lambda v: setpref(SET_AUTO_GENERATE_GIF, bool(v)))
        self.chk_use_relative.toggled.connect(self._notify_use_relative_paths_changed)
        # Apply default distance immediately as well
        self.spin_default_offset.valueChanged.connect(lambda v: setpref(SET_DEFAULT_ELEMENT_OFFSET_MM, float(v)))
        # Apply default lens focus immediately as well
        self.spin_default_lens_focus.valueChanged.connect(lambda v: setpref(SET_DEFAULT_LENS_FOCUS_MM, float(v)))
        # Error message duration
        self.spin_err_dur.valueChanged.connect(lambda v: setpref(SET_ERR_MESS_DUR, int(v)))
        # Reset button
        self.btn_reset_settings.clicked.connect(self._reset_all_settings)

    def _notify_use_relative_paths_changed(self, v: bool):
        """Save preference and ask all open PhysicalSetupVisualizer widgets to refresh path displays."""
        try:
            setpref(SET_USE_RELATIVE_PATHS, bool(v))
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
        self.chk_auto_open.setChecked(bool(getpref(SET_AUTO_OPEN_NEW_WORKSPACE)))
        self.chk_ask_before_close.setChecked(bool(getpref(SET_ASK_BEFORE_CLOSING)))
        self.chk_confirm_save.setChecked(bool(getpref(SET_CONFIRM_ON_SAVE)))
        self.chk_enable_scrollwheel.setChecked(bool(getpref(SET_ENABLE_SCROLLWHEEL)))
        self.chk_select_all_on_focus.setChecked(bool(getpref(SET_SELECT_ALL_ON_FOCUS)))
        self.chk_rename_on_type.setChecked(bool(getpref(SET_RENAME_ON_TYPE_CHANGE)))
        self.chk_warn_before_delete.setChecked(bool(getpref(SET_WARN_BEFORE_DELETE)))
        self.chk_use_relative.setChecked(bool(getpref(SET_USE_RELATIVE_PATHS)))
        self.chk_open_on_startup.setChecked(bool(getpref(SET_OPEN_TAB_ON_STARTUP)))
        # New
        if hasattr(self, 'chk_retain_files'):
            self.chk_retain_files.setChecked(bool(getpref(SET_RETAIN_WORKING_FILES)))
        if hasattr(self, 'chk_auto_gif'):
            self.chk_auto_gif.setChecked(bool(getpref(SET_AUTO_GENERATE_GIF)))
        self.spin_default_offset.setValue(float(getpref(SET_DEFAULT_ELEMENT_OFFSET_MM)))
        self.spin_default_lens_focus.setValue(float(getpref(SET_DEFAULT_LENS_FOCUS_MM)))
        if hasattr(self, 'spin_err_dur'):
            self.spin_err_dur.setValue(int(getpref(SET_ERR_MESS_DUR)))

    def _reset_all_settings(self):
        """Delete all user-specific settings and restore defaults immediately."""
        reply = QMessageBox.question(
            self,
            "Reset settings",
            "This will delete all saved settings (window geometry, layouts, and preferences) and restore defaults. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            s = QSettings("diffractsim", "app")
            s.clear()
            s.sync()
        except Exception:
            QMessageBox.critical(self, "Reset settings", "Failed to clear application settings.")
            return
        # Reload UI with defaults
        try:
            self._load_current()
        except Exception:
            pass
        # Reapply runtime defaults immediately (distance/path displays)
        try:
            self._mw._apply_default_distance(getpref(SET_DEFAULT_ELEMENT_OFFSET_MM))
        except Exception:
            pass
        # Restore main window geometry and per-tab layouts to defaults
        try:
            if hasattr(self._mw, "_restore_window_geometry"):
                self._mw._restore_window_geometry()
        except Exception:
            pass
        try:
            tabs = getattr(self._mw, 'tabs', None)
            if tabs is not None:
                for i in range(tabs.count()):
                    tab = tabs.widget(i)
                    # Apply default splitter sizes and table columns
                    try:
                        self._mw._apply_saved_layout_to_tab(tab)
                    except Exception:
                        pass
                    # Refresh visualizer path displays
                    vis = getattr(tab, 'visualizer', None)
                    if vis is not None and hasattr(vis, 'refresh_aperture_path_display'):
                        try:
                            vis.refresh_aperture_path_display()
                        except Exception:
                            pass
        except Exception:
            pass
        QMessageBox.information(self, "Reset settings", "All settings have been reset to defaults.")

class PreferencesWindow(QWidget):
    """Standalone window that hosts the PreferencesTab."""
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setWindowIcon(QIcon("fzp_icon.ico"))
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        layout = QVBoxLayout(self)
        self._tab = PreferencesTab(main_window, self)
        layout.addWidget(self._tab)
        self.setLayout(layout)
        # Make it a reasonable default size
        self.resize(520, 480)
