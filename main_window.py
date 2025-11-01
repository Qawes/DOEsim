from PyQt6.QtWidgets import QMainWindow, QTabWidget, QSplitter, QVBoxLayout, QMessageBox, QMenuBar, QMenu, QWidget, QInputDialog, QLineEdit, QFileDialog, QLabel, QStackedWidget
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QIcon
from widgets.system_parameters_widget import SystemParametersWidget
from widgets.physical_setup_visualizer import PhysicalSetupVisualizer
from widgets.image_container import ImageContainer
from widgets.preferences_window import PreferencesWindow, getpref
from widgets.preferences_window import (
    SET_DEFAULT_ELEMENT_OFFSET_MM,
    SET_CONFIRM_ON_SAVE,
    SET_ASK_BEFORE_CLOSING,
    SET_AUTO_OPEN_NEW_WORKSPACE,
    SET_OPEN_TAB_ON_STARTUP,
)
import re

# ---------- Default UI layout (edit these to change the initial appearance) ----------
DEFAULT_WINDOW_GEOMETRY = (350, 100, 1200, 800)  # x, y, width, height
DEFAULT_SPLITTER_V_SIZES = [400, 600]            # top/bottom heights (px)
DEFAULT_SPLITTER_H_SIZES = [600, 600]            # left/right widths (px)
DEFAULT_TABLE_COLUMN_PROPORTIONS = [0.2, 0.2, 0.2, 0.4]  # Name, Type, Distance, Value
# ------------------------------------------------------------------------------------

class WorkspaceTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        self.sys_params = SystemParametersWidget()
        main_layout.addWidget(self.sys_params)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.visualizer = PhysicalSetupVisualizer()
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
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DOEsim GUI Proof of Concept")
        self.setWindowIcon(QIcon("fzp_icon.ico")) 
        self.resize(1200, 800)
        self._createMenuBar()
        # Central stacked widget: placeholder when no tabs, tabs when present
        self._central_stack = QStackedWidget(self)
        # Rich-text placeholder with clickable actions
        self._placeholder = QLabel(
            "<div style='font-size:18pt; font-style:italic; color:#777777;'>" #  font-weight:bold;
            "<b><a href='new'>Create</a></b> a new Workspace,<br/>or<br/>"
            "<b><a href='load'>Load</a></b> an existing one."
            "</div>"
        )
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setWordWrap(True)
        self._placeholder.setTextFormat(Qt.TextFormat.RichText)
        self._placeholder.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self._placeholder.setOpenExternalLinks(False)
        self._placeholder.linkActivated.connect(self._on_placeholder_link)
        # Apply default-dependent globals from preferences
        self._apply_default_distance(getpref(SET_DEFAULT_ELEMENT_OFFSET_MM))

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)  # Enable close buttons on tabs
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.tabBarDoubleClicked.connect(self.rename_tab)
        self._central_stack.addWidget(self._placeholder)
        self._central_stack.addWidget(self.tabs)
        self.setCentralWidget(self._central_stack)
        # Restore window geometry first
        self._restore_window_geometry()
        # Conditionally open an empty workspace tab on startup
        if bool(getpref(SET_OPEN_TAB_ON_STARTUP)):
            self.add_new_tab()
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
        help_menu.addAction("Help", self.not_implemented)
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
                'field_type': sys_params.field_type.currentText(),
                'wavelength_nm': float(sys_params.wavelength.value()),
                'extent_x_mm': float(sys_params.extension_x.value()),
                'extent_y_mm': float(sys_params.extension_y.value()),
                'resolution_px_per_mm': float(sys_params.resolution.value()),
            }

            # Elements (preserve order)
            visualizer = tab.visualizer
            elements = []
            node = getattr(visualizer, 'head', None)
            node = node.next if node is not None else None  # skip light source
            while node is not None:
                entry = {
                    'name': node.name,
                    'type': node.type,
                    'distance_mm': float(node.distance),
                }
                if node.type == 'Lens':
                    entry['focal_length_mm'] = float(node.focal_length) if node.focal_length is not None else None
                elif node.type == 'Aperture':
                    entry['aperture_path'] = node.aperture_path or ""
                elif node.type == 'Screen':
                    entry['is_range'] = bool(node.is_range) if node.is_range is not None else False
                    entry['range_end_mm'] = float(node.range_end) if node.range_end is not None else float(node.distance)
                    entry['steps'] = int(node.steps) if node.steps is not None else 10
                elements.append(entry)
                node = node.next

            data = {
                'workspace_name': workspace_name,
                'system_params': params,
                'elements': elements,
                'saved_at': __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'app': 'Diffractsim GUI',
                'version': '1.0',
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

            if bool(getpref(SET_CONFIRM_ON_SAVE)):
                QMessageBox.information(self, "Save Workspace", f"Workspace saved to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Workspace", f"Failed to save workspace:\n{e}")

    def load_workspace(self):
        """Load a workspace JSON into a NEW tab (name, params, elements, order, column widths)."""
        try:
            import json
            import os
            from widgets.physical_setup_visualizer import ElementNode

            # Pick file
            default_dir = os.path.join(os.getcwd(), 'workspaces')
            os.makedirs(default_dir, exist_ok=True)
            file_path, _ = QFileDialog.getOpenFileName(self, "Load Workspace", default_dir, "Workspace Files (*.json)")
            if not file_path:
                return

            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Validate structure lightly
            if not isinstance(data, dict):
                QMessageBox.warning(self, "Load Workspace", "Invalid workspace file format.")
                return

            # Determine unique tab name BEFORE adding the tab
            desired_name = data.get('workspace_name') or "Workspace"
            name = desired_name
            if self.validate_workspace_name(name) is not True:
                # Try to make it acceptable/unique by appending a counter
                base = desired_name or "Workspace"
                counter = 2
                while True:
                    candidate = f"{base} ({counter})"
                    if self.validate_workspace_name(candidate) is True:
                        name = candidate
                        break
                    counter += 1

            # Create a new workspace tab and select it
            new_tab = WorkspaceTab()
            new_index = self.tabs.addTab(new_tab, name)
            self.tabs.setCurrentIndex(new_index)
            self._update_empty_placeholder()
            # Apply saved layout (splitters and table columns)
            self._apply_saved_layout_to_tab(new_tab)

            # Populate system params
            sys_params = new_tab.sys_params
            params = data.get('system_params', {})
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

            # Populate elements (preserve order)
            visualizer = new_tab.visualizer
            visualizer.head.next = None
            tail = visualizer.head
            for e in data.get('elements', []):
                try:
                    etype = e.get('type')
                    ename = e.get('name') or f"{etype}"
                    dist = float(e.get('distance_mm', 0.0))
                    if etype == 'Aperture':
                        node = ElementNode(ename, 'Aperture', dist, aperture_path=e.get('aperture_path') or "")
                    elif etype == 'Lens':
                        node = ElementNode(ename, 'Lens', dist, focal_length=e.get('focal_length_mm'))
                    elif etype == 'Screen':
                        is_range = bool(e.get('is_range', False))
                        range_end = e.get('range_end_mm')
                        steps = e.get('steps')
                        node = ElementNode(ename, 'Screen', dist, is_range=is_range, range_end=range_end, steps=steps)
                    else:
                        continue
                    tail.next = node
                    tail = node
                except Exception:
                    continue
            visualizer.refresh_table()

            # Column widths restoration removed (native header persistence is used)

            # Normally do not display this message
            # QMessageBox.information(self, "Load Workspace", f"Workspace loaded into new tab:\n{name}")
        except Exception as e:
            QMessageBox.critical(self, "Load Workspace", f"Failed to load workspace:\n{e}")

    def add_new_tab(self):
        tab = WorkspaceTab()
        # Apply saved layout to newly created tab
        self._apply_saved_layout_to_tab(tab)
        self.tabs.addTab(tab, f"Workspace {self.tabs.count() + 1}")
        self._update_empty_placeholder()
    
    def close_tab(self, index):
        """Close a tab with confirmation if it's the last tab"""
        ask = bool(getpref(SET_ASK_BEFORE_CLOSING))
        autoopen = bool(getpref(SET_AUTO_OPEN_NEW_WORKSPACE))
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
                if bool(getpref(SET_AUTO_OPEN_NEW_WORKSPACE)):
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
            # Validate the new name
            validation_result = self.validate_workspace_name(new_name, exclude_index=index)
            if validation_result is True:
                self.tabs.setTabText(index, new_name)
            else:
                QMessageBox.warning(self, "Invalid Name", validation_result)
    
    def validate_workspace_name(self, name, exclude_index=None):
        """
        Validate workspace name according to rules.
        
        Args:
            name: The proposed workspace name
            exclude_index: Tab index to exclude from duplicate check (for renaming)
        
        Returns:
            True if valid, or error message string if invalid.
        """
        # Check minimum length
        if len(name) < self.MIN_WORKSPACE_NAME_LENGTH:
            return f"Workspace name must be at least {self.MIN_WORKSPACE_NAME_LENGTH} characters long."
        
        # Check allowed characters
        if not re.match(self.WORKSPACE_NAME_ALLOWED_CHARS, name):
            return "Workspace name can only contain letters, numbers, spaces, underscores, and hyphens."
        
        # Check for duplicate names
        for i in range(self.tabs.count()):
            if i == exclude_index:  # Skip the tab being renamed
                continue
            if self.tabs.tabText(i) == name:
                return f"A workspace with the name '{name}' already exists."
        
        return True

    def _update_empty_placeholder(self):
        """Show an italic hint when there are no workspace tabs; otherwise show tabs."""
        if self.tabs.count() == 0:
            self._central_stack.setCurrentWidget(self._placeholder)
        else:
            self._central_stack.setCurrentWidget(self.tabs)

    def open_preferences_tab(self):
        """Open the Preferences window (standalone), creating it if necessary."""
        # Reuse existing window if open
        win = getattr(self, "_preferences_window", None)
        if win is not None and hasattr(win, 'isVisible') and win.isVisible():
            win.activateWindow()
            win.raise_()
            return
        # Create and show
        self._preferences_window = PreferencesWindow(self)
        self._preferences_window.show()

    def _apply_default_distance(self, val: float):
        try:
            import widgets.physical_setup_visualizer as psv
            psv.GLOBAL_DEFAULT_DISTANCE_MM = float(val)
        except Exception:
            pass

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

    def not_implemented(self):
        QMessageBox.information(self, "Not implemented", "This feature is not implemented in the proof of concept.")

    def show_about(self):
        QMessageBox.about(self, "About", "Diffractsim GUI Proof of Concept\n\nDeveloped using PyQt6.")
