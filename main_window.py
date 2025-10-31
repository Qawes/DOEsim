from PyQt6.QtWidgets import QMainWindow, QTabWidget, QSplitter, QVBoxLayout, QMessageBox, QMenuBar, QMenu, QWidget, QInputDialog, QLineEdit, QFileDialog
from PyQt6.QtCore import Qt
from widgets.system_parameters_widget import SystemParametersWidget
from widgets.physical_setup_visualizer import PhysicalSetupVisualizer
from widgets.image_container import ImageContainer
import re

class WorkspaceTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        self.sys_params = SystemParametersWidget()
        main_layout.addWidget(self.sys_params)
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.visualizer = PhysicalSetupVisualizer()
        splitter.addWidget(self.visualizer)
        img_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.aperture_img = ImageContainer("Aperture image")
        self.screen_img = ImageContainer("Screen image")
        img_splitter.addWidget(self.aperture_img)
        img_splitter.addWidget(self.screen_img)
        splitter.addWidget(img_splitter)
        splitter.setSizes([300, 500])
        main_layout.addWidget(splitter)
        
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
        self.setWindowTitle("Diffractsim GUI Proof of Concept")
        self.resize(1200, 800)
        self._createMenuBar()
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)  # Enable close buttons on tabs
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.tabBarDoubleClicked.connect(self.rename_tab)
        self.setCentralWidget(self.tabs)
        self.add_new_tab()

    def _createMenuBar(self):
        menubar = QMenuBar(self)
        self.setMenuBar(menubar)
        file_menu = QMenu("File", self)
        menubar.addMenu(file_menu)
        file_menu.addAction("New", self.add_new_tab)
        file_menu.addAction("Save", self.save_workspace)
        file_menu.addAction("Load", self.load_workspace)
        edit_menu = QMenu("Edit", self)
        menubar.addMenu(edit_menu)
        edit_menu.addAction("Options", self.not_implemented)
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
                elements.append(entry)
                node = node.next

            # Column widths
            table = visualizer.table
            header = table.horizontalHeader()
            col_widths = []
            if header is not None:
                for i in range(table.columnCount()):
                    col_widths.append(int(header.sectionSize(i)))

            data = {
                'workspace_name': workspace_name,
                'system_params': params,
                'elements': elements,
                'column_widths': col_widths,
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

            QMessageBox.information(self, "Save Workspace", f"Workspace saved to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Workspace", f"Failed to save workspace:\n{e}")

    def load_workspace(self):
        """Load a workspace JSON into the active tab (name, params, elements, order, column widths)."""
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

            idx = self.tabs.currentIndex()
            if idx < 0:
                self.add_new_tab()
                idx = self.tabs.currentIndex()
            tab = self.tabs.widget(idx)
            if tab is None or not isinstance(tab, WorkspaceTab):
                QMessageBox.warning(self, "Load Workspace", "Active workspace is invalid.")
                return

            # Name (ensure it's valid/unique)
            name = data.get('workspace_name') or "Workspace"
            valid = self.validate_workspace_name(name, exclude_index=idx)
            if valid is not True:
                # Try to make it unique by appending a counter
                base = name
                counter = 2
                while True:
                    candidate = f"{base} ({counter})"
                    if self.validate_workspace_name(candidate, exclude_index=idx) is True:
                        name = candidate
                        break
                    counter += 1
            self.tabs.setTabText(idx, name)

            # System params
            sys_params = tab.sys_params
            params = data.get('system_params', {})
            ft = params.get('field_type')
            if isinstance(ft, str):
                # set combobox to matching text if present
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

            # Elements (rebuild linked list preserving order)
            visualizer = tab.visualizer
            # Clear current elements
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
                        node = ElementNode(ename, 'Screen', dist, is_range=bool(e.get('is_range', False)))
                    else:
                        continue
                    tail.next = node
                    tail = node
                except Exception:
                    continue
            visualizer.refresh_table()

            # Column widths
            widths = data.get('column_widths', [])
            header = visualizer.table.horizontalHeader()
            try:
                if header is not None:
                    for i, w in enumerate(widths):
                        if i < visualizer.table.columnCount():
                            header.resizeSection(i, int(w))
            except Exception:
                pass

            QMessageBox.information(self, "Load Workspace", f"Workspace loaded from:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Load Workspace", f"Failed to load workspace:\n{e}")

    def add_new_tab(self):
        tab = WorkspaceTab()
        self.tabs.addTab(tab, f"Workspace {self.tabs.count() + 1}")
    
    def close_tab(self, index):
        """Close a tab with confirmation if it's the last tab"""
        if self.tabs.count() <= 1:
            reply = QMessageBox.question(
                self,
                "Close Workspace",
                "This is the last workspace. Closing it will create a new empty workspace. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.tabs.removeTab(index)
                self.add_new_tab()  # Add a new tab to replace the closed one
        else:
            reply = QMessageBox.question(
                self,
                "Close Workspace",
                f"Are you sure you want to close '{self.tabs.tabText(index)}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.tabs.removeTab(index)
    
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

    def not_implemented(self):
        QMessageBox.information(self, "Not implemented", "This feature is not implemented in the proof of concept.")

    def show_about(self):
        QMessageBox.about(self, "About", "Diffractsim GUI Proof of Concept\n\nDeveloped using PyQt6.")
