# This file is now obsolete. All main classes have been moved to widgets/ and main_window.py.
# You can safely remove this file or keep it as a reference.

"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget, QSplitter, QMenuBar, QMenu, QMessageBox, QComboBox, QDoubleSpinBox, QSizePolicy, QFrame, QLineEdit, QSpinBox
)
from PyQt6.QtGui import QPixmap, QImage, QDrag, QGuiApplication, QMouseEvent, QCursor
from PyQt6.QtCore import Qt, QMimeData
import numpy as np
import engine
import threading
import time


class SystemParametersWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        self.field_type = QComboBox()
        self.field_type.addItems(["Monochromatic", "Polychromatic"])
        layout.addWidget(QLabel("Field type:"))
        layout.addWidget(self.field_type)
        self.wavelength = QDoubleSpinBox()
        self.wavelength.setRange(200, 2000)
        self.wavelength.setValue(532)
        self.wavelength.setSuffix(" nm")
        self.wavelength.setDecimals(2)
        layout.addWidget(QLabel("Wavelength:"))
        layout.addWidget(self.wavelength)
        self.extension_x = QDoubleSpinBox()
        self.extension_x.setRange(0.01, 1000)
        self.extension_x.setValue(10)
        self.extension_x.setSuffix(" mm")
        self.extension_x.setDecimals(3)
        self.extension_y = QDoubleSpinBox()
        self.extension_y.setRange(0.01, 1000)
        self.extension_y.setValue(10)
        self.extension_y.setSuffix(" mm")
        self.extension_y.setDecimals(3)
        layout.addWidget(QLabel("Extension X:"))
        layout.addWidget(self.extension_x)
        layout.addWidget(QLabel("Y:"))
        layout.addWidget(self.extension_y)
        self.resolution = QDoubleSpinBox()
        self.resolution.setRange(1, 10000)
        self.resolution.setValue(512)
        self.resolution.setSuffix(" px/mm")
        self.resolution.setDecimals(1)
        layout.addWidget(QLabel("Resolution:"))
        layout.addWidget(self.resolution)
        layout.addStretch()

class DraggableElementWidget(QFrame):
    def __init__(self, element, parent=None):
        super().__init__(parent)
        self.element = element
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("background: #fff; border: 2px solid #222; border-radius: 12px; margin: 8px; padding: 8px;")
        self.setMinimumWidth(200)
        self.setMinimumHeight(240)
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        # Dots at the top for drag handle
        dots = QLabel("<center>● ● ● ● ●</center>")
        dots.setStyleSheet("font-size: 18px; color: #222;")
        layout.addWidget(dots)
        # Type selector
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Aperture", "Lens"])
        self.type_combo.setCurrentText(element.element_type.capitalize())
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        layout.addWidget(QLabel("<b>Type:</b>"))
        layout.addWidget(self.type_combo)
        # File/shape/focus fields
        self.param_widgets = {}
        if element.element_type == "aperture":
            if "image_path" in element.params:
                self.param_widgets['image_path'] = QLineEdit(element.params['image_path'])
                layout.addWidget(QLabel("File:"))
                layout.addWidget(self.param_widgets['image_path'])
            else:
                self.param_widgets['shape'] = QLineEdit(element.params.get('shape', 'circle'))
                layout.addWidget(QLabel("Shape:"))
                layout.addWidget(self.param_widgets['shape'])
            self.param_widgets['radius'] = QDoubleSpinBox()
            self.param_widgets['radius'].setSuffix(" mm")
            self.param_widgets['radius'].setDecimals(2)
            self.param_widgets['radius'].setValue(element.params.get('radius', 1))
            layout.addWidget(QLabel("Radius:"))
            layout.addWidget(self.param_widgets['radius'])
        elif element.element_type == "lens":
            self.param_widgets['f'] = QDoubleSpinBox()
            self.param_widgets['f'].setSuffix(" mm")
            self.param_widgets['f'].setDecimals(2)
            self.param_widgets['f'].setValue(element.params.get('f', 80))
            layout.addWidget(QLabel("Focus:"))
            layout.addWidget(self.param_widgets['f'])
        # Distance field
        self.distance_spin = QDoubleSpinBox()
        self.distance_spin.setSuffix(" mm")
        self.distance_spin.setDecimals(2)
        self.distance_spin.setValue(element.distance)
        layout.addWidget(QLabel("Distance:"))
        layout.addWidget(self.distance_spin)
        layout.addStretch()
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def on_type_changed(self, text):
        # Optionally: update UI for new type
        pass

    def mousePressEvent(self, a0):
        if a0 is not None and hasattr(a0, 'button') and a0.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(str(id(self)))
            drag.setMimeData(mime)
            pixmap = self.grab()
            drag.setPixmap(pixmap)
            if hasattr(a0, 'position'):
                drag.setHotSpot(a0.position().toPoint())
            drag.exec()
        super().mousePressEvent(a0)

    def mouseReleaseEvent(self, a0):
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(a0)

class PhysicalSetupVisualizer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.elements = []
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        # Lightsource tile
        src = QLabel("<center><b>Lightsource<br>(white aperature)</b></center>")
        src.setAlignment(Qt.AlignmentFlag.AlignCenter)
        src.setStyleSheet("background: #fff; border: 2px solid #222; border-radius: 12px; margin: 8px; padding: 8px; font-size: 18px;")
        src.setMinimumWidth(200)
        src.setMinimumHeight(240)
        row.addWidget(src)
        self.elements_layout = QHBoxLayout()
        row.addLayout(self.elements_layout)
        row.addStretch()
        layout.addLayout(row)
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add Element")
        self.add_btn.clicked.connect(self.add_element)
        btn_layout.addWidget(self.add_btn)
        self.del_btn = QPushButton("Delete Last Element")
        self.del_btn.clicked.connect(self.delete_element)
        btn_layout.addWidget(self.del_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        self.setAcceptDrops(True)
        self.refresh_elements()

    def add_element(self):
        from engine import Element
        new_elem = Element(distance=10, element_type="aperture", params={"shape": "circle", "radius": 1})
        self.elements.append(new_elem)
        self.refresh_elements()

    def delete_element(self):
        if self.elements:
            self.elements.pop()
            self.refresh_elements()

    def refresh_elements(self):
        while self.elements_layout.count():
            item = self.elements_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget:
                widget.deleteLater()
        self.elements.sort(key=lambda e: e.distance)
        for elem in self.elements:
            w = DraggableElementWidget(elem)
            self.elements_layout.addWidget(w)
        self.elements_layout.addStretch()

    def dragEnterEvent(self, a0):
        if a0 is not None and hasattr(a0, 'accept'):
            a0.accept()

    def dragMoveEvent(self, a0):
        if a0 is not None and hasattr(a0, 'accept'):
            a0.accept()

    def dropEvent(self, a0):
        if a0 is not None and hasattr(a0, 'accept'):
            a0.accept()

class ImageContainer(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(title))
        self.image_label = QLabel("Image will appear here")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_label.setMinimumSize(100, 100)
        layout.addWidget(self.image_label)
        self.solve_button = QPushButton("Solve")
        self.solve_button.clicked.connect(self.solve_async)
        layout.addWidget(self.solve_button)
        self._pixmap = None

    def solve_async(self):
        self.solve_button.setEnabled(False)
        self.image_label.setText("Calculating...")
        threading.Thread(target=self._fetch_image, daemon=True).start()

    def _fetch_image(self):
        # Gather parameters from parent WorkspaceTab's SystemParametersWidget
        tab = self.parent()
        while tab and not isinstance(tab, WorkspaceTab):
            tab = tab.parent()
        if tab and hasattr(tab, 'sys_params'):
            sys_params = tab.sys_params
            field_type = sys_params.field_type.currentText()
            wavelength = sys_params.wavelength.value()
            extent_x = sys_params.extension_x.value()
            extent_y = sys_params.extension_y.value()
            resolution = sys_params.resolution.value()
        else:
            field_type = "Monochromatic"
            wavelength = 532
            extent_x = 10
            extent_y = 10
            resolution = 512
        # Elements and Backend are placeholders for now
        Elements = []
        Backend = "CPU"
        arr = engine.calculate_random_image(
            FieldType=field_type,
            Wavelength=wavelength,
            ExtentX=extent_x,
            ExtentY=extent_y,
            Resolution=resolution,
            Elements=Elements,
            Backend=Backend
        )
        h, w = arr.shape
        qimg = QImage(arr.data, w, h, w, QImage.Format.Format_Grayscale8)
        pixmap = QPixmap.fromImage(qimg)
        self._pixmap = pixmap
        self._update_image_async()

    def _update_image_async(self):
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._update_image_main_thread)

    def _update_image_main_thread(self):
        self.update_image()
        self.solve_button.setEnabled(True)

    def resizeEvent(self, a0):
        self.update_image()
        super().resizeEvent(a0)

    def update_image(self):
        if self._pixmap:
            label_size = self.image_label.size()
            scaled_pixmap = self._pixmap.scaled(label_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.image_label.setPixmap(scaled_pixmap)
        else:
            self.image_label.setText("Image will appear here")

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
        QMessageBox.about(self, "About", "Diffractsim GUI Proof of Concept\nby GitHub Copilot")
"""