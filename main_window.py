from PyQt6.QtWidgets import QMainWindow, QTabWidget, QSplitter, QVBoxLayout, QMessageBox, QMenuBar, QMenu, QWidget, QInputDialog, QLineEdit, QFileDialog, QLabel, QStackedWidget
from PyQt6.QtCore import Qt, QSettings, QUrl, QTimer
from PyQt6.QtGui import QIcon, QDesktopServices
from components.system_parameters import SystemParametersWidget
from components.element_table import PhysicalSetupVisualizer
from components.preview_display import ImageContainer
from components.preferences_window import PreferencesWindow, getpref, Prefs
from components.helpers import validate_name_against, suggest_unique_name
from components.Element import (
    Element as _ElBase,
    EType
)

# ---------- Default UI layout (edit these to change the initial appearance) ----------
DEFAULT_WINDOW_GEOMETRY = (350, 100, 1200, 800)  # x, y, width, height
DEFAULT_SPLITTER_V_SIZES = [400, 600]            # top/bottom heights (px)
DEFAULT_SPLITTER_H_SIZES = [600, 600]            # left/right widths (px)
DEFAULT_TABLE_COLUMN_PROPORTIONS = [0.2, 0.2, 0.2, 0.4]  # Name, Type, Distance, Value
# ------------------------------------------------------------------------------------
VERSION = "0.1.2.element-refacotr" # Application version string
# ------------------------------------------------------------------------------------

class WorkspaceTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        self.sys_params = SystemParametersWidget()
        main_layout.addWidget(self.sys_params)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.visualizer = PhysicalSetupVisualizer()
        # --- Wire engine selector to visualizer engine-dependent UI ---
        try:
            cb = self.sys_params.engine_combo
            # Ensure single connection (idempotent)
            try:
                cb.currentTextChanged.disconnect()
            except Exception:
                pass
            cb.currentTextChanged.connect(self.visualizer.set_engine_mode)
            # Initialize mapping to current combo text
            self.visualizer.set_engine_mode(cb.currentText())
        except Exception:
            pass
        # ---
        self.splitter.addWidget(self.visualizer)
        self.img_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.aperture_img = ImageContainer("Aperture image")
        self.screen_img = ImageContainer("Screen image")
        self.img_splitter.addWidget(self.aperture_img)
        self.img_splitter.addWidget(self.screen_img)
        self.splitter.addWidget(self.img_splitter)
        main_layout.addWidget(self.splitter)
        # Geometry restored centrally by MainWindow

    def get_workspace_name(self):
        """Get the workspace name from the tab title"""
        # Find the QTabWidget that contains this WorkspaceTab
        widget = self
        tab_widget = None
        
        # Traverse up the parent hierarchy to find the QTabWidget
        while widget is not None:
            parent = widget.parent()
            if isinstance(parent, QTabWidget):
                tab_widget = parent
                break
            widget = parent
        
        # If we found the tab widget, get the tab text
        if tab_widget is not None:
            index = tab_widget.indexOf(self)
            if index >= 0:
                return tab_widget.tabText(index)
        
        # Fallback to default name
        return "Workspace_1"


class MainWindow(QMainWindow):
    # Configuration constants
    MIN_WORKSPACE_NAME_LENGTH = 3
    # Character filter: allows alphanumeric, spaces, underscores, hyphens
    # Edit this regex pattern to change allowed characters
    WORKSPACE_NAME_ALLOWED_CHARS = r'^[a-zA-Z0-9_ -]+$'
    
    def __init__(self, force_single_workspace: bool = False):
        super().__init__()
        self.setWindowTitle("DOEsim GUI Proof of Concept")
        self.setWindowIcon(QIcon("fzp_icon.ico")) 
        self.resize(1200, 800)
        self._createMenuBar()
        # Central stacked widget: placeholder when no tabs, tabs when present
        self._central_stack = QStackedWidget(self)
        # Startup override flag
        self._force_single_workspace = bool(force_single_workspace)
        # Rich-text placeholder with clickable actions
        self._placeholder = QLabel(
            "<div style='font-size:18pt; font-style:italic; color:#777777;'>" #  font-weight:bold;
            "<b><a href='new'>Create</a></b> a new Workspace,<br/>or<br/>"
            "<b><a href='load'>Load</a></b> an existing one."
            "</div>"
            "<div style='font-size:10pt; color:#777777; margin-top:20px; font-style:italic;'>"
            "Read the <b><a href='help'>documentation</a></b> for getting started." 
            "</div>"
        )
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setWordWrap(True)
        self._placeholder.setTextFormat(Qt.TextFormat.RichText)
        self._placeholder.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self._placeholder.setOpenExternalLinks(False)
        self._placeholder.linkActivated.connect(self._on_placeholder_link)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)  # Enable close buttons on tabs
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.tabBarDoubleClicked.connect(self.rename_tab)
        # Context menu on tabs: right-click to rename or close (deferred to ensure tab bar exists)
        QTimer.singleShot(0, self._setup_tab_context_menu)
        self._central_stack.addWidget(self._placeholder)
        self._central_stack.addWidget(self.tabs)
        self.setCentralWidget(self._central_stack)
        # Restore window geometry first
        self._restore_window_geometry()
        # Conditionally open an empty workspace tab on startup
        if self._force_single_workspace or bool(getpref(Prefs.OPEN_TAB_ON_STARTUP)):
            if self.tabs.count() == 0:
                self.add_new_tab()
        # elif bool(getpref(SET_AUTO_OPEN_NEW_WORKSPACE)):
        #     self.add_new_tab()
        # Update placeholder visibility either way
        self._update_empty_placeholder()

    def _createMenuBar(self):
        menubar = QMenuBar(self)
        self.setMenuBar(menubar)
        file_menu = QMenu("File", self)
        menubar.addMenu(file_menu)
        file_menu.addAction("New Workspace", self.add_new_tab)
        file_menu.addAction("Save Workspace", self.save_workspace)
        file_menu.addAction("Load Workspace", self.load_workspace)
        edit_menu = QMenu("Edit", self)
        menubar.addMenu(edit_menu)
        edit_menu.addAction("Preferences", self.open_preferences_tab)
        help_menu = QMenu("Help", self)
        menubar.addMenu(help_menu)
        help_menu.addAction("Help", self.open_help)
        help_menu.addAction("About", self.show_about)

    def save_workspace(self):
        """Save the active workspace to a JSON file (name, params, elements, order, column widths)."""
        try:
            import json
            import os
            # Active tab and name
            idx = self.tabs.currentIndex()
            if idx < 0:
                QMessageBox.information(self, "Save Workspace", "No active workspace to save.")
                return
            tab = self.tabs.widget(idx)
            if tab is None or not isinstance(tab, WorkspaceTab):
                QMessageBox.warning(self, "Save Workspace", "Active workspace is invalid.")
                return
            workspace_name = self.tabs.tabText(idx)

            # System params
            sys_params = tab.sys_params
            params = {
                'engine': sys_params.engine_combo.currentText(),
                'field_type': sys_params.field_type.currentText(),
                'wavelength_nm': float(sys_params.wavelength.value()),
                'extent_x_mm': float(sys_params.extension_x.value()),
                'extent_y_mm': float(sys_params.extension_y.value()),
                'resolution_px_per_mm': float(sys_params.resolution.value()),
            }

            # Elements (preserve order) via new list model
            visualizer = tab.visualizer
            items = visualizer.get_ui_elements() if hasattr(visualizer, 'get_ui_elements') else []
            elements = []
            for e in items:
                try:
                    # Use each element's export to ensure all per-type fields are saved
                    if hasattr(e, 'export') and callable(getattr(e, 'export')):
                        elements.append(e.export())
                    else:
                        # Fallback minimal serialization
                        elements.append({
                            'name': getattr(e, 'name', None),
                            'type': getattr(e, 'element_type', None),
                            'distance': float(getattr(e, 'distance', 0.0)),
                        })
                except Exception:
                    # Skip elements that fail to serialize
                    continue

            data = {
                'workspace_name': workspace_name,
                'system_params': params,
                'elements': elements,
                'saved_at': __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'app': 'Diffractsim GUI',
                'version': VERSION,
            }

            # Choose file path
            default_dir = os.path.join(os.getcwd(), 'workspaces')
            os.makedirs(default_dir, exist_ok=True)
            suggested = os.path.join(default_dir, f"{workspace_name}.json")
            file_path, _ = QFileDialog.getSaveFileName(self, "Save Workspace", suggested, "Workspace Files (*.json)")
            if not file_path:
                return
            # Ensure .json extension
            if not file_path.lower().endswith('.json'):
                file_path += '.json'

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            if bool(getpref(Prefs.CONFIRM_ON_SAVE)):
                QMessageBox.information(self, "Save Workspace", f"Workspace saved to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Workspace", f"Failed to save workspace:\n{e}")

    def load_workspace(self):
        """Load a workspace JSON into a NEW tab (name, params, elements, order, column widths)."""
        try:
            import json
            import os
            from components.Element import Element as _ElementFactory
            from components.Element import EType as _EType
            # Pick file
            default_dir = os.path.join(os.getcwd(), 'workspaces')
            os.makedirs(default_dir, exist_ok=True)
            file_path, _ = QFileDialog.getOpenFileName(self, "Load Workspace", default_dir, "Workspace Files (*.json)")
            if not file_path:
                return

            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, dict):
                QMessageBox.warning(self, "Load Workspace", "Invalid workspace file format.")
                return

            # Determine unique tab name BEFORE adding the tab
            desired_name = data.get('workspace_name') or "Workspace"
            existing_names = [self.tabs.tabText(i) for i in range(self.tabs.count())]
            vr = validate_name_against(desired_name, existing_names, self.MIN_WORKSPACE_NAME_LENGTH, self.WORKSPACE_NAME_ALLOWED_CHARS)
            if vr is True:
                name = desired_name
                rename_reason = None
            else:
                name = suggest_unique_name(desired_name, existing_names, self.MIN_WORKSPACE_NAME_LENGTH, self.WORKSPACE_NAME_ALLOWED_CHARS)
                rename_reason = vr
            was_renamed = (name != desired_name)

            # Create a new workspace tab and select it
            new_tab = WorkspaceTab()
            new_index = self.tabs.addTab(new_tab, name)
            self.tabs.setCurrentIndex(new_index)
            self._update_empty_placeholder()
            self._apply_saved_layout_to_tab(new_tab)

            if was_renamed:
                msg = f"Loaded workspace name was adjusted: '{desired_name}' → '{name}'."
                if isinstance(rename_reason, str) and rename_reason:
                    msg += f"\nReason: {rename_reason}"
                QMessageBox.information(self, "Workspace renamed", msg)

            # Populate system params
            sys_params = new_tab.sys_params
            params = data.get('system_params', {})
            eng = params.get('engine')
            if isinstance(eng, str):
                cb = sys_params.engine_combo
                idx_eng = cb.findText(eng)
                if idx_eng >= 0:
                    cb.setCurrentIndex(idx_eng)
            ft = params.get('field_type')
            if isinstance(ft, str):
                cb = sys_params.field_type
                idx_ft = cb.findText(ft)
                if idx_ft >= 0:
                    cb.setCurrentIndex(idx_ft)
            try:
                sys_params.wavelength.setValue(float(params.get('wavelength_nm', sys_params.wavelength.value())))
                sys_params.extension_x.setValue(float(params.get('extent_x_mm', sys_params.extension_x.value())))
                sys_params.extension_y.setValue(float(params.get('extent_y_mm', sys_params.extension_y.value())))
                sys_params.resolution.setValue(float(params.get('resolution_px_per_mm', sys_params.resolution.value())))
            except Exception:
                pass

            # Populate elements (preserve order) using the new model
            elems: list[_ElBase] = []
            for e in data.get('elements', []):
                try:
                    # Normalize type labels across all known values and legacy aliases
                    t = e.get('type')
                    t_str = str(t).strip() if t is not None else ''
                    norm_map = {
                        'aperture': _EType.APERTURE.value,
                        'lens': _EType.LENS.value,
                        'screen': _EType.SCREEN.value,
                        'aperture result': _EType.APERTURE_RESULT.value,
                        'apertureresult': _EType.APERTURE_RESULT.value,
                        'aperture_result': _EType.APERTURE_RESULT.value,
                        'target intensity': _EType.TARGET_INTENSITY.value,
                        'targetintensity': _EType.TARGET_INTENSITY.value,
                        'target_intensity': _EType.TARGET_INTENSITY.value,
                    }
                    key = t_str.replace('-', ' ').replace('/', ' ').replace('\t', ' ').replace('\n', ' ').strip().lower()
                    if key in norm_map:
                        e['type'] = norm_map[key]

                    # Support legacy keys
                    if 'aperture_path' in e and 'image_path' not in e:
                        e['image_path'] = e.get('aperture_path')
                    if 'aperture_width_mm' in e and 'width_mm' not in e:
                        e['width_mm'] = e.get('aperture_width_mm')
                    if 'aperture_height_mm' in e and 'height_mm' not in e:
                        e['height_mm'] = e.get('aperture_height_mm')
                    if 'focal_length_mm' in e and 'focal_length' not in e:
                        e['focal_length'] = e.get('focal_length_mm')
                    if 'range_end_mm' in e and 'range_end' not in e:
                        e['range_end'] = e.get('range_end_mm')
                    # Legacy aperture flags
                    if 'inverted' in e and 'is_inverted' not in e:
                        e['is_inverted'] = bool(e.get('inverted'))
                    if 'phasemask' in e and 'is_phasemask' not in e:
                        e['is_phasemask'] = bool(e.get('phasemask'))
                    # ApertureResult reverse extras (legacy)
                    if 'max_iter' in e and 'maxiter' not in e:
                        e['maxiter'] = e.get('max_iter')
                    if 'padding_px' in e and 'padding' not in e:
                        e['padding'] = e.get('padding_px')
                    if 'method' in e and 'phase_retrieval_method' not in e:
                        e['phase_retrieval_method'] = e.get('method')

                    # Ensure distance key exists
                    if 'distance' not in e and 'distance_mm' in e:
                        e['distance'] = e.get('distance_mm')
                    # Inject name
                    if 'name' not in e:
                        e['name'] = f"{e.get('type')}"
                    elem = _ElementFactory.from_dict(e)
                    elems.append(elem)
                except Exception:
                    continue
            new_tab.visualizer.set_ui_elements(elems)

            # Column widths restoration removed (native header persistence is used)
        except Exception as e:
            QMessageBox.critical(self, "Load Workspace", f"Failed to load workspace:\n{e}")

    def add_new_tab(self):
        tab = WorkspaceTab()
        # Apply saved layout to newly created tab
        self._apply_saved_layout_to_tab(tab)
        # Add and switch to the new workspace tab
        new_index = self.tabs.addTab(tab, f"Workspace {self.tabs.count() + 1}")
        self.tabs.setCurrentIndex(new_index)
        # Re-establish context menu in case the tab bar was created late
        try:
            self._setup_tab_context_menu()
        except Exception:
            pass
        self._update_empty_placeholder()
    
    def close_tab(self, index):
        """Close a tab with confirmation if it's the last tab"""
        ask = bool(getpref(Prefs.ASK_BEFORE_CLOSING))
        autoopen = bool(getpref(Prefs.AUTO_OPEN_NEW_WORKSPACE))
        if self.tabs.count() <= 1:
            proceed = True
            if ask:
                if autoopen:
                    reply = QMessageBox.question(
                        self,
                        "Close Workspace",
                        "This is the last workspace. Closing it will create a new empty workspace. Continue?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    proceed = reply == QMessageBox.StandardButton.Yes
                else:
                    reply = QMessageBox.question(
                        self,
                        "Close Workspace",
                        f"Are you sure you want to close '{self.tabs.tabText(index)}'?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    proceed = reply == QMessageBox.StandardButton.Yes
            if proceed:
                # Save geometry/layout before removing the last tab
                try:
                    self._save_ui_state()
                except Exception:
                    pass
                self.tabs.removeTab(index)
                if bool(getpref(Prefs.AUTO_OPEN_NEW_WORKSPACE)):
                    self.add_new_tab()
                self._update_empty_placeholder()
        else:
            proceed = True
            if ask:
                reply = QMessageBox.question(
                    self,
                    "Close Workspace",
                    f"Are you sure you want to close '{self.tabs.tabText(index)}'?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                proceed = reply == QMessageBox.StandardButton.Yes
            if proceed:
                # Save geometry/layout before removing the tab
                try:
                    self._save_ui_state()
                except Exception:
                    pass
                self.tabs.removeTab(index)
                self._update_empty_placeholder()
    
    def rename_tab(self, index):
        """Rename a tab by double-clicking on it"""
        if index < 0:  # Double-click on empty area
            return
        
        current_name = self.tabs.tabText(index)
        # Show input dialog
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Workspace",
            f"Enter new name for workspace (min {self.MIN_WORKSPACE_NAME_LENGTH} characters):",
            QLineEdit.EchoMode.Normal,
            current_name
        )
        
        if ok and new_name:
            # Build existing list and validate against it, excluding current tab name
            existing = []
            for i in range(self.tabs.count()):
                if i == index:
                    continue
                existing.append(self.tabs.tabText(i))
            vr = validate_name_against(new_name, existing, self.MIN_WORKSPACE_NAME_LENGTH, self.WORKSPACE_NAME_ALLOWED_CHARS)
            if vr is True:
                self.tabs.setTabText(index, new_name)
            else:
                QMessageBox.warning(self, "Invalid Name", vr)

    def _on_tabbar_context_menu(self, pos):
        """Show context menu for a tab (rename/close) at right-click position."""
        try:
            bar = self.tabs.tabBar()
            if bar is None:
                return
            index = bar.tabAt(pos)
            if index < 0:
                return
            menu = QMenu(self)
            act_rename = menu.addAction("Rename")
            act_close = menu.addAction("Close")
            chosen = menu.exec(bar.mapToGlobal(pos))
            if chosen == act_rename:
                self.rename_tab(index)
            elif chosen == act_close:
                self.close_tab(index)
        except Exception:
            pass

    def _setup_tab_context_menu(self):
        """Ensure the tab bar has a custom context menu connected (idempotent)."""
        try:
            bar = self.tabs.tabBar()
            if bar is None:
                return
            bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            try:
                # Avoid duplicate connections if already connected
                bar.customContextMenuRequested.disconnect()
            except Exception:
                pass
            bar.customContextMenuRequested.connect(self._on_tabbar_context_menu)
        except Exception:
            pass

    def validate_workspace_name(self, name, exclude_index=None):
        """
        Validate workspace name according to rules using shared helper.
        """
        existing = []
        for i in range(self.tabs.count()):
            if exclude_index is not None and i == exclude_index:
                continue
            existing.append(self.tabs.tabText(i))
        return validate_name_against(name, existing, self.MIN_WORKSPACE_NAME_LENGTH, self.WORKSPACE_NAME_ALLOWED_CHARS)

    def _update_empty_placeholder(self):
        """Show an italic hint when there are no workspace tabs; otherwise show tabs."""
        if self.tabs.count() == 0:
            self._central_stack.setCurrentWidget(self._placeholder)
        else:
            self._central_stack.setCurrentWidget(self.tabs)

    def open_preferences_tab(self):
        """Open the Preferences window (standalone), creating it if necessary."""
        # Reuse existing window if open and valid
        win = getattr(self, "_preferences_window", None)
        if win is not None:
            try:
                if hasattr(win, 'isVisible') and win.isVisible():
                    win.activateWindow()
                    win.raise_()
                    return
            except RuntimeError:
                # The window was deleted, clear the reference
                self._preferences_window = None
        # Create and show
        self._preferences_window = PreferencesWindow(self)
        # Clear reference when window is destroyed
        self._preferences_window.destroyed.connect(lambda: setattr(self, '_preferences_window', None))
        self._preferences_window.show()

    def _restore_window_geometry(self):
        """Restore QMainWindow geometry using the Qt docs example."""
        try:
            s = QSettings("diffractsim", "app")
            s.beginGroup("MainWindow")
            geo = s.value("geometry", b"")
            try:
                geo_bytes = bytes(geo) if isinstance(geo, (bytearray, bytes)) else geo
            except Exception:
                geo_bytes = geo
            if not geo_bytes:
                # Default position/size if no saved geometry exists
                x, y, w, h = DEFAULT_WINDOW_GEOMETRY
                self.setGeometry(x, y, w, h)
            else:
                try:
                    self.restoreGeometry(geo_bytes)
                except Exception:
                    # Fallback to a sane default if restore fails
                    x, y, w, h = DEFAULT_WINDOW_GEOMETRY
                    self.setGeometry(x, y, w, h)
            s.endGroup()
        except Exception:
            pass

    def _save_ui_state(self):
        """Save window geometry and current workspace layout (splitters and table columns)."""
        try:
            s = QSettings("diffractsim", "app")
            # Save main window geometry
            s.beginGroup("MainWindow")
            s.setValue("geometry", self.saveGeometry())
            s.endGroup()
            # Save current workspace splitter layout and table header widths
            idx = self.tabs.currentIndex()
            if idx >= 0:
                tab = self.tabs.widget(idx)
                if isinstance(tab, WorkspaceTab):
                    s.beginGroup("Workspace")
                    try:
                        s.setValue("splitter_v", tab.splitter.saveState())
                        s.setValue("splitter_h", tab.img_splitter.saveState())
                    except Exception:
                        pass
                    try:
                        header = tab.visualizer.table.horizontalHeader()
                        if header is not None:
                            s.setValue("table_header_state", header.saveState())
                    except Exception:
                        pass
                    s.endGroup()
        except Exception:
            pass

    def _apply_saved_layout_to_tab(self, tab: 'WorkspaceTab'):
        """Apply saved splitter layout and table header widths to the given WorkspaceTab."""
        try:
            s = QSettings("diffractsim", "app")
            s.beginGroup("Workspace")
            # Splitters
            applied_v = False
            applied_h = False
            try:
                v = s.value("splitter_v", None)
                if v is not None:
                    if tab.splitter.restoreState(v):
                        applied_v = True
                h = s.value("splitter_h", None)
                if h is not None:
                    if tab.img_splitter.restoreState(h):
                        applied_h = True
            except Exception:
                pass
            if not applied_v:
                try:
                    tab.splitter.setSizes(DEFAULT_SPLITTER_V_SIZES)
                except Exception:
                    pass
            if not applied_h:
                try:
                    tab.img_splitter.setSizes(DEFAULT_SPLITTER_H_SIZES)
                except Exception:
                    pass
            # Table header
            try:
                header_state = s.value("table_header_state", None)
                header = tab.visualizer.table.horizontalHeader()
                if header is not None and header_state is not None:
                    header.restoreState(header_state)
                elif header is not None:
                    self._apply_default_table_columns(tab.visualizer.table)
            except Exception:
                pass
            s.endGroup()
        except Exception:
            pass

    def _apply_default_table_columns(self, table):
        try:
            header = table.horizontalHeader()
            viewport = table.viewport() if hasattr(table, 'viewport') else None
            total_width = viewport.width() if viewport is not None and viewport.width() > 0 else 1000
            for i, prop in enumerate(DEFAULT_TABLE_COLUMN_PROPORTIONS):
                if header is not None:
                    header.resizeSection(i, int(total_width * prop))
        except Exception:
            pass

    def closeEvent(self, a0):
        """Ensure preferences are saved and the Preferences window is closed when quitting."""
        # Close Preferences window if active
        try:
            win = getattr(self, "_preferences_window", None)
            if win is not None and hasattr(win, 'isVisible') and win.isVisible():
                win.close()
                self._preferences_window = None
        except Exception:
            pass
        # Save consolidated UI state (window geometry + current workspace layout)
        self._save_ui_state()
        # Flush QSettings to disk
        try:
            QSettings("diffractsim", "app").sync()
        except Exception:
            pass
        return super().closeEvent(a0)

    def _on_placeholder_link(self, href: str):
        """Handle clicks on the placeholder links."""
        if href == 'new':
            self.add_new_tab()
        elif href == 'load':
            self.load_workspace()
        elif href == 'help':
                self.open_help()

    def not_implemented(self):
        QMessageBox.information(self, "Not implemented", "This feature is not implemented in the proof of concept.")

    def show_about(self):
        QMessageBox.about(self, "About", f"Diffractsim GUI Proof of Concept\n\nVersion: {VERSION}\n\nDeveloped using PyQt6.")

    def open_help(self):
        QDesktopServices.openUrl(QUrl("https://github.com/Qawes/DOEsim"))
