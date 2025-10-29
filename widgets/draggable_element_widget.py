from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QComboBox, QLineEdit, QDoubleSpinBox, QWidget
from PyQt6.QtCore import Qt, QMimeData
from PyQt6.QtGui import QDrag

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
        dots = QLabel("<center>● ● ● ● ●</center>")
        dots.setStyleSheet("font-size: 18px; color: #222;")
        layout.addWidget(dots)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Aperture", "Lens"])
        self.type_combo.setCurrentText(element.element_type.capitalize())
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        layout.addWidget(QLabel("<b>Type:</b>"))
        layout.addWidget(self.type_combo)
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
        self.distance_spin = QDoubleSpinBox()
        self.distance_spin.setSuffix(" mm")
        self.distance_spin.setDecimals(2)
        self.distance_spin.setValue(element.distance)
        layout.addWidget(QLabel("Distance:"))
        layout.addWidget(self.distance_spin)
        layout.addStretch()
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def on_type_changed(self, text):
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
