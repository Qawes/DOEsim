from PyQt6.QtWidgets import QMainWindow, QTabWidget, QSplitter, QVBoxLayout, QMessageBox, QMenuBar, QMenu, QWidget
from PyQt6.QtCore import Qt
from widgets.system_parameters_widget import SystemParametersWidget
from widgets.physical_setup_visualizer import PhysicalSetupVisualizer
from widgets.image_container import ImageContainer

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

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Diffractsim GUI Proof of Concept")
        self.resize(1200, 800)
        self._createMenuBar()
        self.tabs = QTabWidget()
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

    def not_implemented(self):
        QMessageBox.information(self, "Not implemented", "This feature is not implemented in the proof of concept.")

    def show_about(self):
        QMessageBox.about(self, "About", "Diffractsim GUI Proof of Concept\n\nDeveloped using PyQt6.")
