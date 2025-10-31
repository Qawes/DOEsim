from PyQt6.QtWidgets import QVBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt
import threading
import engine
from widgets.system_parameters_widget import DEFAULT_WAVELENGTH_NM, DEFAULT_EXTENSION_X_MM, DEFAULT_EXTENSION_Y_MM, DEFAULT_RESOLUTION_PX_PER_MM
import numpy as np

class ImageContainer(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title  # Store title for later use
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
        tab = self.parent()
        from main_window import WorkspaceTab
        while tab and not isinstance(tab, WorkspaceTab):
            tab = tab.parent()
        if tab and hasattr(tab, 'sys_params') and hasattr(tab, 'visualizer'):
            sys_params = getattr(tab, 'sys_params')
            field_type = sys_params.field_type.currentText()
            wavelength = sys_params.wavelength.value()
            extent_x = sys_params.extension_x.value()
            extent_y = sys_params.extension_y.value()
            resolution = sys_params.resolution.value()
            elements = tab.visualizer.export_elements_for_engine()
        else:
            field_type = "Monochromatic"
            wavelength = DEFAULT_WAVELENGTH_NM
            extent_x = DEFAULT_EXTENSION_X_MM
            extent_y = DEFAULT_EXTENSION_Y_MM
            resolution = DEFAULT_RESOLUTION_PX_PER_MM
            elements = []
        Backend = "CPU"
        side = None
        if "Aperture" in self.title:
            side = "aperture"
        elif "Screen" in self.title:
            side = "screen"
        arr = engine.calculate_screen_images(
            FieldType=field_type,
            Wavelength=wavelength,
            ExtentX=extent_x,
            ExtentY=extent_y,
            Resolution=resolution,
            Elements=elements,
            Backend=Backend,
            side=side,
            workspace_name=tab.get_workspace_name() if tab else "Workspace_1"
        )
        # Handle color or grayscale
        image = QImage()
        try:
            arr = np.asarray(arr)
        except Exception:
            arr = None
        if arr is not None and hasattr(arr, "ndim"):
            if arr.ndim == 3 and arr.shape[2] == 3:
                h = int(arr.shape[0])
                w = int(arr.shape[1])
                if arr.dtype != np.uint8:
                    arr = (255 * np.clip(arr, 0, 1)).astype(np.uint8)
                if not arr.flags["C_CONTIGUOUS"]:
                    arr = np.ascontiguousarray(arr)
                bytes_per_line = 3 * w
                image = QImage(arr.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                self._last_image_array = arr
            elif arr.ndim == 2:
                h = int(arr.shape[0])
                w = int(arr.shape[1])
                if arr.dtype != np.uint8:
                    arr = (255 * np.clip(arr, 0, 1)).astype(np.uint8)
                if not arr.flags["C_CONTIGUOUS"]:
                    arr = np.ascontiguousarray(arr)
                bytes_per_line = w
                image = QImage(arr.data, w, h, bytes_per_line, QImage.Format.Format_Grayscale8)
                self._last_image_array = arr
        pixmap = QPixmap.fromImage(image)
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
