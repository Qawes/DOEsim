from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel, QComboBox, QDoubleSpinBox, QWidget

DEFAULT_WAVELENGTH_NM = 633
DEFAULT_EXTENSION_X_MM = 4
DEFAULT_EXTENSION_Y_MM = 4
DEFAULT_RESOLUTION_PX_PER_MM = 256

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
        self.wavelength.setValue(DEFAULT_WAVELENGTH_NM)
        self.wavelength.setSuffix(" nm")
        self.wavelength.setDecimals(2)
        layout.addWidget(QLabel("Wavelength:"))
        layout.addWidget(self.wavelength)
        self.extension_x = QDoubleSpinBox()
        self.extension_x.setRange(0.01, 1000)
        self.extension_x.setValue(DEFAULT_EXTENSION_X_MM)
        self.extension_x.setSuffix(" mm")
        self.extension_x.setDecimals(3)
        self.extension_y = QDoubleSpinBox()
        self.extension_y.setRange(0.01, 1000)
        self.extension_y.setValue(DEFAULT_EXTENSION_Y_MM)
        self.extension_y.setSuffix(" mm")
        self.extension_y.setDecimals(3)
        layout.addWidget(QLabel("Extension X:"))
        layout.addWidget(self.extension_x)
        layout.addWidget(QLabel("Y:"))
        layout.addWidget(self.extension_y)
        self.resolution = QDoubleSpinBox()
        self.resolution.setRange(1, 10000)
        self.resolution.setValue(DEFAULT_RESOLUTION_PX_PER_MM)
        self.resolution.setSuffix(" px/mm")
        self.resolution.setDecimals(1)
        layout.addWidget(QLabel("Resolution:"))
        layout.addWidget(self.resolution)
        layout.addStretch()
