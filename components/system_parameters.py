from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel, QComboBox, QDoubleSpinBox, QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QStandardItemModel, QStandardItem

DEFAULT_WAVELENGTH_NM = 633
DEFAULT_EXTENSION_X_MM = 4
DEFAULT_EXTENSION_Y_MM = 4
DEFAULT_RESOLUTION_PX_PER_MM = 256

class SystemParametersWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        
        # Engine selector (placed first)
        self.engine_combo = QComboBox()        # Build model and enable all implemented engines
        eng_model = QStandardItemModel(self.engine_combo)
        for text, disabled, tip in [
            ("Diffractsim Forward", False, None),
            ("Diffractsim Reverse", False, None),
            ("Bitmap Reverse", True, "This engine is disabled"),
        ]:
            it = QStandardItem(text)
            if disabled:
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            if tip:
                it.setData(tip, Qt.ItemDataRole.ToolTipRole)
            eng_model.appendRow(it)
        self.engine_combo.setModel(eng_model)
        self.engine_combo.setCurrentIndex(0)
        layout.addWidget(QLabel("Engine:"))
        layout.addWidget(self.engine_combo)
        
        # Field type selector
        self.field_type = QComboBox()
        # Build model and disable "Polychromatic"
        ft_model = QStandardItemModel(self.field_type)
        it_mono = QStandardItem("Monochromatic")
        it_poly = QStandardItem("Polychromatic")
        it_poly.setFlags(it_poly.flags() & ~Qt.ItemFlag.ItemIsEnabled)
        it_poly.setData("Polychromatic not supported yet", Qt.ItemDataRole.ToolTipRole)
        ft_model.appendRow(it_mono)
        ft_model.appendRow(it_poly)
        self.field_type.setModel(ft_model)
        self.field_type.setCurrentIndex(0)
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
