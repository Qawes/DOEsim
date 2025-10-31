from PyQt6.QtWidgets import QMainWindow, QTabWidget, QSplitter, QVBoxLayout, QMessageBox, QMenuBar, QMenu, QWidget, QInputDialog, QLineEdit
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
        file_menu.addAction("Save", self.not_implemented)
        file_menu.addAction("Load", self.not_implemented)
        edit_menu = QMenu("Edit", self)
        menubar.addMenu(edit_menu)
        edit_menu.addAction("Options", self.not_implemented)
        help_menu = QMenu("Help", self)
        menubar.addMenu(help_menu)
        help_menu.addAction("Help", self.not_implemented)
        help_menu.addAction("About", self.show_about)

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
