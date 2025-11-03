from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QTableWidget, QTableWidgetItem, QComboBox, QDoubleSpinBox, QHeaderView, QFileDialog, QLineEdit, QMessageBox, QCheckBox, QSpinBox, QApplication, QToolTip, QDialog, QFormLayout, QDialogButtonBox
from PyQt6.QtCore import Qt, QSettings, QEvent, QTimer, QRect
from PyQt6.QtGui import QCursor, QIcon, QPixmap
from typing import Optional, List
from components.preferences_window import getpref
from components.preferences_window import (
    SET_ENABLE_SCROLLWHEEL,
    SET_SELECT_ALL_ON_FOCUS,
    SET_USE_RELATIVE_PATHS,
    SET_RENAME_ON_TYPE_CHANGE,
    SET_WARN_BEFORE_DELETE,
    SET_ERR_MESS_DUR,
    SET_DEFAULT_LENS_FOCUS_MM,
    SET_DEFAULT_ELEMENT_OFFSET_MM
)
from components.helpers import (
    validate_name_against,
    is_default_generated_element_name,
    generate_unique_default_name,
    name_exists,
    show_temp_tooltip,
    abs_path as _abs_path_helper,
    to_pref_path as _to_pref_path_helper,
    normalize_path_for_display as _normalize_path_for_display,
    extract_default_suffix,
    DEFAULT_ALLOWED_NAME_PATTERN,
)
# Use the unified Element class hierarchy
from components.Element import (
    Element as _BaseElement,
    Aperture as _Aperture,
    Lens as _Lens,
    Screen as _Screen,
    ApertureResult as _ApertureResult,
    TargetIntensity as _TargetIntensity,
    TYPE_APERTURE,
    TYPE_LENS,
    TYPE_SCREEN,
    TYPE_APERTURE_RESULT,
    TYPE_TARGET_INTENSITY,
)

GLOBAL_MINIMUM_DISTANCE_MM = 0
GLOBAL_MAXIMUM_DISTANCE_MM = 100000.0
GLOBAL_DISTANCE_TEXT = "Placement"

class PhysicalSetupVisualizer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Widget layout
        layout = QVBoxLayout(self)
        label = QLabel("<b>Physical Setup</b>")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Name", "Edit Element", f"{GLOBAL_DISTANCE_TEXT} (mm)", "Value (type dependent)"])
        header = self.table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        layout.addWidget(self.table)
        btn_layout = QHBoxLayout()
        # Three generic add buttons; text and behavior depend on engine mode
        self.add_btn_1 = QPushButton()
        self.add_btn_1.clicked.connect(lambda: self._on_add_button(0))
        btn_layout.addWidget(self.add_btn_1)
        self.add_btn_2 = QPushButton()
        self.add_btn_2.clicked.connect(lambda: self._on_add_button(1))
        btn_layout.addWidget(self.add_btn_2)
        self.add_btn_3 = QPushButton()
        self.add_btn_3.clicked.connect(lambda: self._on_add_button(2))
        btn_layout.addWidget(self.add_btn_3)
        # Back-compat aliases for tests expecting fixed-named buttons
        self.add_aperture_btn = self.add_btn_1
        self.add_lens_btn = self.add_btn_2
        self.add_screen_btn = self.add_btn_3
        self.del_btn = QPushButton("Delete element")
        self.del_btn.setEnabled(False)  # Disabled by default
        self.del_btn.clicked.connect(self.delete_selected_elements)
        btn_layout.addWidget(self.del_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        # New list-based data model
        self._elements: List[_BaseElement] = []
        # Engine/type mapping state
        self._engine_mode = "Diffractsim Forward"
        self._type_display_list: list[str] = []
        self._display_to_internal: dict[str, str] = {}
        self._internal_to_display: dict[str, str] = {}
        # Initialize mapping and buttons
        self.set_engine_mode(self._engine_mode)
        self._restore_header_state()
        self.table.itemSelectionChanged.connect(self._update_delete_button_state)
        self.refresh_table()

    def get_ui_elements(self) -> list[_BaseElement]:
        return list(self._elements)

    def set_ui_elements(self, elements: list[_BaseElement]):
        self._elements = list(elements or [])
        # Keep sorted by distance ascending, stable
        self._stable_sort_by_distance()
        self.refresh_table()

    def refresh_aperture_path_display(self):
        """Refresh only the aperture path editors to reflect current path preference."""
        self._rewrite_aperture_paths_in_table()

    # Event filtering to support preferences (wheel disable, select-all on focus)
    def eventFilter(self, a0, a1):
        et = a1.type() if a1 is not None else None
        if et == QEvent.Type.Wheel:
            # Optionally disable scrollwheel for spinboxes and combos within the table
            if not bool(getpref(SET_ENABLE_SCROLLWHEEL)):
                if isinstance(a0, (QDoubleSpinBox, QSpinBox, QComboBox)):
                    return True  # consume
        elif et == QEvent.Type.FocusIn:
            if bool(getpref(SET_SELECT_ALL_ON_FOCUS)):
                if isinstance(a0, QLineEdit):
                    a0.selectAll()
                elif isinstance(a0, (QDoubleSpinBox, QSpinBox)):
                    # Improve reliability by using the spinbox's lineEdit() and selecting after focus with a singleshot
                    try:
                        le = a0.lineEdit()  # QAbstractSpinBox provides this
                        if le is not None:
                            QTimer.singleShot(0, le.selectAll)
                    except Exception:
                        pass
        elif et == QEvent.Type.FocusOut:
            # Clamp spinboxes to their min/max on focus loss
            if isinstance(a0, QDoubleSpinBox):
                try:
                    a0.interpretText()
                    v = float(a0.value())
                    v = max(float(a0.minimum()), min(float(a0.maximum()), v))
                    if abs(v - a0.value()) > 1e-12:
                        a0.setValue(v)
                except Exception:
                    pass
            elif isinstance(a0, QSpinBox):
                try:
                    a0.interpretText()
                    v = int(a0.value())
                    v = max(int(a0.minimum()), min(int(a0.maximum()), v))
                    if v != a0.value():
                        a0.setValue(v)
                except Exception:
                    pass
        return super().eventFilter(a0, a1)

    def _to_pref_path(self, path: str) -> str:
        import os
        if not path:
            return path
        return _to_pref_path_helper(path, bool(getpref(SET_USE_RELATIVE_PATHS)))

    def _abs_path(self, path: Optional[str]) -> Optional[str]:
        return _abs_path_helper(path)

    def _normalize_aperture_display_path(self, stored_path: Optional[str]) -> str:
        return _normalize_path_for_display(stored_path, bool(getpref(SET_USE_RELATIVE_PATHS)))

    def _find_row_for_node(self, target) -> Optional[int]:
        """Return table row index for a given element object, or None if not found."""
        try:
            idx = self._elements.index(target)
        except ValueError:
            return None
        return idx + 1  # account for Light Source row at 0

    # Build distance widget based on type
    def _build_screen_distance_widget(self, elem: _Screen | _BaseElement):
        """Create the distance cell widget for a Screen row based on elem.is_range."""
        if isinstance(elem, _Screen) and bool(getattr(elem, 'is_range', False)):
            dist_widget = QWidget(self.table)
            hl = QHBoxLayout(dist_widget)
            hl.setContentsMargins(0, 0, 0, 0)
            from_lbl = QLabel("From:", dist_widget)
            dist_from = QDoubleSpinBox(dist_widget)
            # Install event filter for preferences
            dist_from.installEventFilter(self)
            dist_from.setRange(GLOBAL_MINIMUM_DISTANCE_MM, GLOBAL_MAXIMUM_DISTANCE_MM)
            dist_from.setDecimals(3)
            dist_from.setSuffix(" mm")
            dist_from.setValue(float(elem.distance))
            dist_from.editingFinished.connect(lambda e=elem, w=dist_from: self._on_distance_edited(e, w.value()))
            to_lbl = QLabel("To:", dist_widget)
            dist_to = QDoubleSpinBox(dist_widget)
            dist_to.installEventFilter(self)
            dist_to.setRange(GLOBAL_MINIMUM_DISTANCE_MM, GLOBAL_MAXIMUM_DISTANCE_MM)
            dist_to.setDecimals(3)
            dist_to.setSuffix(" mm")
            dist_to.setValue(float(getattr(elem, 'range_end', elem.distance)))
            try:
                dist_to.setMinimum(dist_from.value())
                dist_from.valueChanged.connect(lambda v, w=dist_to: self._update_range_to_min(w, v))
            except Exception:
                pass
            dist_to.editingFinished.connect(lambda e=elem, w=dist_to: self._on_screen_range_end_edited(e, w.value()))
            hl.addWidget(from_lbl)
            hl.addWidget(dist_from)
            hl.addWidget(to_lbl)
            hl.addWidget(dist_to)
            return dist_widget
        else:
            dist_spin = QDoubleSpinBox(self.table)
            dist_spin.installEventFilter(self)
            dist_spin.setRange(GLOBAL_MINIMUM_DISTANCE_MM, GLOBAL_MAXIMUM_DISTANCE_MM)
            dist_spin.setDecimals(2)
            dist_spin.setValue(float(getattr(elem, 'distance', 0.0)))
            dist_spin.setSuffix(" mm")
            dist_spin.editingFinished.connect(lambda e=elem, w=dist_spin: self._on_distance_edited(e, w.value()))
            return dist_spin

    def _update_range_to_min(self, to_widget: QDoubleSpinBox, new_from: float):
        """Keep the 'To' spinbox minimum in sync with the 'From' value and clamp if needed."""
        try:
            to_widget.setMinimum(float(new_from))
            if to_widget.value() < float(new_from):
                to_widget.setValue(float(new_from))
        except Exception:
            pass

    def refresh_table(self):
        self.table.setRowCount(0)
        # Row 0: Light Source
        self.table.insertRow(0)
        name_item = QTableWidgetItem("Light Source")
        name_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.table.setItem(0, 0, name_item)
        type_item = QTableWidgetItem("")
        type_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.table.setItem(0, 1, type_item)
        dist_item = QTableWidgetItem("-∞")
        dist_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.table.setItem(0, 2, dist_item)
        value_item = QTableWidgetItem("Full white")
        value_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.table.setItem(0, 3, value_item)
        # Subsequent rows: elements from list
        for idx, elem in enumerate(self._elements, start=1):
            self.table.insertRow(idx)
            # Name editor
            name_edit = QLineEdit(getattr(elem, 'name', '') or "")
            name_edit.installEventFilter(self)
            name_edit.editingFinished.connect(lambda n=name_edit, e=elem: self._on_name_edited(e, n))
            self.table.setCellWidget(idx, 0, name_edit)
            # Icon + Edit button
            icon_path = None
            t = getattr(elem, 'element_type', None)
            if t == TYPE_APERTURE:
                icon_path = "resources/aperture-icon.png"
            elif t == TYPE_LENS:
                icon_path = "resources/lens-icon.png"
            elif t == TYPE_SCREEN:
                icon_path = "resources/screen-icon.png"
            elif t == TYPE_APERTURE_RESULT:
                icon_path = "resources/aperture-result-icon.png"
            elif t == TYPE_TARGET_INTENSITY:
                icon_path = "resources/target-intensity-icon.png"
            icon_label = QLabel(self.table)
            if icon_path:
                icon = QIcon(icon_path)
                pixmap = icon.pixmap(20, 20)
                icon_label.setPixmap(pixmap)
            edit_btn = QPushButton("Edit", self.table)
            edit_btn.clicked.connect(lambda _=None, e=elem: self._open_element_edit_dialog(e))
            hbox = QHBoxLayout()
            hbox.setContentsMargins(0, 0, 0, 0)
            hbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hbox.addWidget(icon_label)
            hbox.addWidget(edit_btn)
            cell_widget = QWidget(self.table)
            cell_widget.setLayout(hbox)
            cell_widget.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(idx, 1, cell_widget)
            # Distance
            if t == TYPE_SCREEN:
                self.table.setCellWidget(idx, 2, self._build_screen_distance_widget(elem))
            else:
                self.table.setCellWidget(idx, 2, self._build_screen_distance_widget(elem))
            # Value per type
            if t == TYPE_APERTURE:
                path_widget = QWidget(self.table)
                path_layout = QHBoxLayout(path_widget)
                path_layout.setContentsMargins(0, 0, 0, 0)
                path_edit = QLineEdit(self._normalize_aperture_display_path(getattr(elem, 'image_path', '')))
                path_edit.installEventFilter(self)
                browse_btn = QPushButton("...", path_widget)
                browse_btn.setFixedWidth(28)
                browse_btn.clicked.connect(lambda _=None, e=elem, pe=path_edit: self._browse_aperture(e, pe))
                path_edit.editingFinished.connect(lambda e=elem, pe=path_edit: self._on_aperture_path_edited(e, pe.text()))
                path_layout.addWidget(path_edit)
                path_layout.addWidget(browse_btn)
                self.table.setCellWidget(idx, 3, path_widget)
            elif t == TYPE_LENS:
                f_spin = QDoubleSpinBox(self.table)
                f_spin.installEventFilter(self)
                f_spin.setRange(GLOBAL_MINIMUM_DISTANCE_MM, GLOBAL_MAXIMUM_DISTANCE_MM)
                f_spin.setDecimals(2)
                f_spin.setValue(float(getattr(elem, 'focal_length', float(getpref(SET_DEFAULT_LENS_FOCUS_MM, 1000.0)))))
                f_spin.setSuffix(" mm")
                f_spin.editingFinished.connect(lambda e=elem, w=f_spin: self._on_focal_length_edited(e, w.value()))
                self.table.setCellWidget(idx, 3, f_spin)
            elif t == TYPE_SCREEN:
                value_widget = QWidget(self.table)
                vlayout = QHBoxLayout(value_widget)
                vlayout.setContentsMargins(0, 0, 0, 0)
                range_checkbox = QCheckBox("Range of screens", value_widget)
                range_checkbox.setChecked(bool(getattr(elem, 'is_range', False)))
                steps_label = QLabel("steps:", value_widget)
                steps_spin = QSpinBox(value_widget)
                steps_spin.installEventFilter(self)
                steps_spin.setRange(1, 10000)
                steps_spin.setValue(int(getattr(elem, 'steps', 10)))
                steps_label.setVisible(bool(getattr(elem, 'is_range', False)))
                steps_spin.setVisible(bool(getattr(elem, 'is_range', False)))
                range_checkbox.toggled.connect(lambda checked, e=elem, sl=steps_label, ss=steps_spin: self._on_screen_range_edited(e, checked, sl, ss))
                steps_spin.valueChanged.connect(lambda val, e=elem: self._on_screen_steps_edited(e, int(val)))
                vlayout.addWidget(range_checkbox)
                vlayout.addWidget(steps_label)
                vlayout.addWidget(steps_spin)
                vlayout.addStretch()
                self.table.setCellWidget(idx, 3, value_widget)
            elif t == TYPE_APERTURE_RESULT:
                value_widget = QWidget(self.table)
                vlayout = QHBoxLayout(value_widget)
                vlayout.setContentsMargins(0, 0, 0, 0)
                if float(getattr(elem, 'distance', 0.0)) == 0.0:
                    in_front_label = QLabel("Element placed in front :)", value_widget)
                    place_btn = QPushButton("---", value_widget)
                    place_btn.setEnabled(False)
                else:
                    in_front_label = QLabel("Please place this in front!", value_widget)
                    place_btn = QPushButton("Okay", value_widget)
                    place_btn.setEnabled(True)
                    place_btn.clicked.connect(lambda _=None, e=elem: self._on_aperture_result_place_it(e))
                vlayout.addWidget(in_front_label)
                vlayout.addWidget(place_btn)
                vlayout.addStretch()
                self.table.setCellWidget(idx, 3, value_widget)
            elif t == TYPE_TARGET_INTENSITY:
                path_widget = QWidget(self.table)
                path_layout = QHBoxLayout(path_widget)
                path_layout.setContentsMargins(0, 0, 0, 0)
                path_edit = QLineEdit(self._normalize_aperture_display_path(getattr(elem, 'image_path', '')))
                path_edit.installEventFilter(self)
                browse_btn = QPushButton("...", path_widget)
                browse_btn.setFixedWidth(28)
                browse_btn.clicked.connect(lambda _=None, e=elem, pe=path_edit: self._browse_aperture(e, pe))
                path_edit.editingFinished.connect(lambda e=elem, pe=path_edit: self._on_aperture_path_edited(e, pe.text()))
                path_layout.addWidget(path_edit)
                path_layout.addWidget(browse_btn)
                self.table.setCellWidget(idx, 3, path_widget)
        self._update_delete_button_state()
        # Notify image containers that the element list or attributes changed
        self._notify_image_containers_changed()
        # Engine combo enable/disable logic stays the same
        try:
            parent = self.parent()
            while parent is not None and not hasattr(parent, 'sys_params'):
                parent = parent.parent() if hasattr(parent, 'parent') else None
            if parent is not None and hasattr(parent, 'sys_params'):
                engine_combo = getattr(getattr(parent, 'sys_params', None), 'engine_combo', None)
                if engine_combo is not None:
                    if self.table.rowCount() > 1:
                        engine_combo.setEnabled(False)
                    else:
                        engine_combo.setEnabled(True)
        except Exception:
            pass

    def _stable_sort_by_distance(self):
        order = {id(e): i for i, e in enumerate(self._elements)}
        self._elements.sort(key=lambda e: (float(getattr(e, 'distance', 0.0)), order.get(id(e), 0)))

    def _show_temp_tooltip(self, widget: QWidget, text: str):
        try:
            dur = int(getpref(SET_ERR_MESS_DUR, 3000))
        except Exception:
            dur = 3000
        show_temp_tooltip(widget, text, dur)

    def add_element(self, elem_type):
        import os
        from PIL import Image
        # Ensure white.png exists in ./aperatures/
        aperture_dir = os.path.join(os.getcwd(), "aperatures")
        white_path = os.path.join(aperture_dir, "white.png")
        if elem_type in (TYPE_APERTURE, TYPE_TARGET_INTENSITY):
            if not os.path.exists(aperture_dir):
                os.makedirs(aperture_dir, exist_ok=True)
            if not os.path.exists(white_path):
                img = Image.new("L", (256, 256), 255)
                img.save(white_path)
        last_distance = float(self._elements[-1].distance) if self._elements else 0.0
        width_mm = 1.0
        height_mm = 1.0
        try:
            parent = self.parent()
            while parent is not None and not hasattr(parent, 'sys_params'):
                parent = parent.parent() if hasattr(parent, 'parent') else None
            sys_params = getattr(parent, 'sys_params', None) if parent is not None else None
            if sys_params is not None:
                width_mm = float(sys_params.extension_x.value())
                height_mm = float(sys_params.extension_y.value())
        except Exception:
            pass
        default_distance = float(getpref(SET_DEFAULT_ELEMENT_OFFSET_MM, 10.0))
        default_lens_focus = float(getpref(SET_DEFAULT_LENS_FOCUS_MM, 1000.0))
        dist = last_distance + default_distance
        existing_names = [getattr(e, 'name', '') for e in self._elements]
        if elem_type == TYPE_APERTURE:
            name = generate_unique_default_name(TYPE_APERTURE, existing_names)
            stored_path = self._to_pref_path(white_path)
            elem = _Aperture(distance=dist, image_path=stored_path, width_mm=width_mm, height_mm=height_mm, is_inverted=False, is_phasemask=False, name=name)
        elif elem_type == TYPE_APERTURE_RESULT:
            name = generate_unique_default_name("Aperture Result", existing_names)
            elem = _ApertureResult(distance=dist, width_mm=width_mm, height_mm=height_mm, name=name)
        elif elem_type == TYPE_LENS:
            name = generate_unique_default_name(TYPE_LENS, existing_names)
            elem = _Lens(distance=dist, focal_length=default_lens_focus, name=name)
        elif elem_type == TYPE_TARGET_INTENSITY:
            name = generate_unique_default_name("Target Intensity", existing_names)
            stored_path = self._to_pref_path(white_path)
            elem = _TargetIntensity(distance=dist, image_path=stored_path, width_mm=width_mm, height_mm=height_mm, name=name)
        else:  # Screen
            name = generate_unique_default_name(TYPE_SCREEN, existing_names)
            elem = _Screen(distance=dist, is_range=False, range_end=dist, steps=10, name=name)
        self._elements.append(elem)
        self._stable_sort_by_distance()
        self.refresh_table()

    def _generate_unique_default_name(self, base_type: str) -> str:
        existing = [getattr(e, 'name', '') for e in self._elements]
        return generate_unique_default_name(base_type, existing)

    def _is_default_generated_name(self, elem: _BaseElement) -> bool:
        return is_default_generated_element_name(getattr(elem, 'name', ''))

    def _name_exists(self, name: str, exclude: Optional[_BaseElement] = None) -> bool:
        for e in self._elements:
            if e is not exclude and getattr(e, 'name', None) == name:
                return True
        return False

    def _on_name_edited(self, elem, name_edit):
        try:
            new_name = str(name_edit.text()).strip()
        except Exception:
            new_name = ""
        existing = [getattr(e, 'name', '') for e in self._elements if e is not elem]
        vr = validate_name_against(new_name, existing, 1, DEFAULT_ALLOWED_NAME_PATTERN)
        if vr is not True:
            try:
                name_edit.blockSignals(True)
                name_edit.setText(getattr(elem, 'name', ''))
                name_edit.blockSignals(False)
            except Exception:
                pass
            self._show_temp_tooltip(name_edit, "Element names must be valid and unique.")
            return
        elem.name = new_name
        self._notify_image_containers_changed()

    def _on_distance_edited(self, elem, new_distance):
        elem.distance = float(new_distance)
        # For screen ranges, adjust range_end if needed
        if isinstance(elem, _Screen) and bool(getattr(elem, 'is_range', False)):
            if float(getattr(elem, 'range_end', elem.distance)) < float(elem.distance):
                elem.range_end = float(elem.distance)
            if float(getattr(elem, 'range_end', elem.distance)) == float(elem.distance):
                elem.steps = 1
                # Update UI steps spin if visible
                row = self._find_row_for_node(elem)
                if row is not None:
                    value_widget = self.table.cellWidget(row, 3)
                    if value_widget is not None:
                        steps_spin = value_widget.findChild(QSpinBox)
                        if steps_spin is not None:
                            steps_spin.blockSignals(True)
                            steps_spin.setValue(1)
                            steps_spin.blockSignals(False)
        self._stable_sort_by_distance()
        self.refresh_table()

    def _on_focal_length_edited(self, elem, new_f):
        if isinstance(elem, _Lens):
            elem.focal_length = float(new_f)

    def _on_aperture_path_edited(self, elem, new_path):
        from os.path import abspath
        try:
            stored = self._to_pref_path(abspath(new_path))
        except Exception:
            stored = self._to_pref_path(new_path)
        if isinstance(elem, (_Aperture, _TargetIntensity)):
            elem.image_path = stored
        self._notify_image_containers_changed()

    def _on_screen_range_edited(self, elem, is_range, steps_label, steps_spin):
        if isinstance(elem, _Screen):
            elem.is_range = bool(is_range)
            steps_label.setVisible(bool(is_range))
            steps_spin.setVisible(bool(is_range))
            if elem.is_range and float(getattr(elem, 'range_end', elem.distance)) == float(elem.distance):
                elem.steps = 1
                steps_spin.blockSignals(True)
                steps_spin.setValue(1)
                steps_spin.blockSignals(False)
            row = self._find_row_for_node(elem)
            if row is not None:
                self.table.setCellWidget(row, 2, self._build_screen_distance_widget(elem))
        self._notify_image_containers_changed()

    def _on_screen_range_end_edited(self, elem, new_end):
        if isinstance(elem, _Screen):
            if float(new_end) < float(elem.distance):
                new_end = float(elem.distance)
            elem.range_end = float(new_end)
            if bool(getattr(elem, 'is_range', False)) and float(elem.range_end) == float(elem.distance):
                elem.steps = 1
                row = self._find_row_for_node(elem)
                if row is not None:
                    value_widget = self.table.cellWidget(row, 3)
                    if value_widget is not None:
                        steps_spin = value_widget.findChild(QSpinBox)
                        if steps_spin is not None:
                            steps_spin.blockSignals(True)
                            steps_spin.setValue(1)
                            steps_spin.blockSignals(False)
        self._notify_image_containers_changed()

    def _on_screen_steps_edited(self, elem, steps):
        if isinstance(elem, _Screen):
            elem.steps = max(1, int(steps))
        self._notify_image_containers_changed()

    def _browse_aperture(self, elem, path_edit):
        dlg = QFileDialog(self, "Select Aperture Bitmap", "", "Images (*.png *.jpg *.bmp)")
        if dlg.exec():
            files = dlg.selectedFiles()
            if files:
                stored = self._to_pref_path(files[0])
                if isinstance(elem, (_Aperture, _TargetIntensity)):
                    elem.image_path = stored
                path_edit.setText(self._normalize_aperture_display_path(getattr(elem, 'image_path', '')))
                self._notify_image_containers_changed()

    def _update_delete_button_state(self):
        selected_rows = {idx.row() for idx in self.table.selectedIndexes()}
        valid_rows = [r for r in selected_rows if r > 0]
        if valid_rows:
            self.del_btn.setEnabled(True)
            if len(valid_rows) == 1:
                self.del_btn.setText("Delete element")
            else:
                self.del_btn.setText(f"Delete {len(valid_rows)} elements")
        else:
            self.del_btn.setEnabled(False)
            self.del_btn.setText("Delete element")

    def delete_selected_elements(self):
        selected_rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        valid_rows = [r for r in selected_rows if r > 0]
        if not valid_rows:
            return
        if bool(getpref(SET_WARN_BEFORE_DELETE)):
            lines = [f"Element {r}: {getattr(self._elements[r-1], 'name', '')}" for r in valid_rows if 1 <= r <= len(self._elements)]
            msg = (
                f"Are you sure you want to delete {len(lines)} element(s)?\n\n" + "\n".join(lines)
            )
            reply = QMessageBox.question(
                self,
                "Delete elements",
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        # Delete in reverse order to keep indices valid
        for r in reversed(valid_rows):
            idx = r - 1
            if 0 <= idx < len(self._elements):
                del self._elements[idx]
        self.refresh_table()

    def _rewrite_aperture_paths_in_table(self):
        # Iterate rows and rewrite only Aperture/TargetIntensity path editors to reflect preference
        for row_index, elem in enumerate(self._elements, start=1):
            if getattr(elem, 'element_type', None) in (TYPE_APERTURE, TYPE_TARGET_INTENSITY):
                cell = self.table.cellWidget(row_index, 3)
                if cell is not None:
                    try:
                        pe = cell.findChild(QLineEdit)
                        if pe is not None:
                            pe.setText(self._normalize_aperture_display_path(getattr(elem, 'image_path', '')))
                    except Exception:
                        pass

    def _restore_header_state(self):
        try:
            header = self.table.horizontalHeader()
            if header is not None:
                # Keep default header; main window geometry persistence is used for overall window layout
                pass
        except Exception:
            pass

    def export_elements_for_engine(self):
        """Return Element.py objects directly for the engines."""
        return list(self._elements)

    # --- New: notify image panels helper ---
    def _notify_image_containers_changed(self):
        try:
            parent = self.parent()
            # Avoid importing at top-level to reduce cycle risk
            from main_window import WorkspaceTab  # type: ignore
            while parent is not None and not isinstance(parent, WorkspaceTab):
                parent = parent.parent()
            if parent is None:
                return
            ap = getattr(parent, 'aperture_img', None)
            sc = getattr(parent, 'screen_img', None)
            if ap is not None and hasattr(ap, 'refresh_from_visualizer_change'):
                try:
                    ap.refresh_from_visualizer_change()
                except Exception:
                    pass
            if sc is not None and hasattr(sc, 'refresh_from_visualizer_change'):
                try:
                    sc.refresh_from_visualizer_change()
                except Exception:
                    pass
        except Exception:
            pass

    # --- Engine-dependent types ---
    def _build_type_mapping(self, engine_text: str):
        # Returns (display_list, display->internal map, internal->display map)
        engine = (engine_text or "").strip()
        if engine == "Diffractsim Reverse":
            display = ["Aperture Result", TYPE_LENS, "Target Intensity"]
            d2i = {
                "Aperture Result": TYPE_APERTURE_RESULT,
                TYPE_LENS: TYPE_LENS,
                "Target Intensity": TYPE_TARGET_INTENSITY,
            }
        elif engine == "Bitmap Reverse":
            display = ["Aperture Result", "Target Intensity"]
            d2i = {
                "Aperture Result": TYPE_APERTURE_RESULT,
                "Target Intensity": TYPE_TARGET_INTENSITY,
            }
        else:  # Diffractsim Forward
            display = [TYPE_APERTURE, TYPE_LENS, TYPE_SCREEN]
            d2i = {x: x for x in display}
        i2d = {}
        for d, i in d2i.items():
            if i not in i2d:
                i2d[i] = d
        return display, d2i, i2d

    def set_engine_mode(self, engine_text: str):
        self._engine_mode = engine_text
        self._type_display_list, self._display_to_internal, self._internal_to_display = self._build_type_mapping(engine_text)
        self.refresh_table()
        try:
            self.add_btn_1.setText(self._type_display_list[0] if len(self._type_display_list) > 0 else "Add")
            self.add_btn_2.setText(self._type_display_list[1] if len(self._type_display_list) > 1 else "Add")
            # Hide or show third button depending on list size
            has_third = len(self._type_display_list) > 2
            self.add_btn_3.setVisible(has_third)
            if has_third:
                self.add_btn_3.setText(self._type_display_list[2])
            # Maintain back-compat aliases regardless of engine (tests use them in Forward mode)
            self.add_aperture_btn = self.add_btn_1
            self.add_lens_btn = self.add_btn_2
            self.add_screen_btn = self.add_btn_3
        except Exception:
            pass

    def _on_add_button(self, idx: int):
        # Map the button index to a display label then to an internal type
        if idx < 0 or idx >= len(self._type_display_list):
            return
        display = self._type_display_list[idx]
        internal = self._display_to_internal.get(display, display)
        self.add_element(internal)

    def _on_aperture_result_place_it(self, elem):
        elem.distance = 0.0
        self._stable_sort_by_distance()
        self.refresh_table()

    def _open_element_edit_dialog(self, elem):
        dlg = ElementEditDialog(self, elem)
        if dlg.exec():
            dlg.apply_changes()
            self._stable_sort_by_distance()
            self.refresh_table()

# --- Dialog for editing element parameters ---
class ElementEditDialog(QDialog):
    def __init__(self, parent, elem):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Element: {getattr(elem, 'name', '')}")
        self.elem = elem
        layout = QFormLayout(self)
        self.widgets = {}
        from PyQt6.QtWidgets import QLineEdit, QDoubleSpinBox, QSpinBox, QCheckBox, QLabel
        name_edit = QLineEdit(getattr(elem, 'name', ''))
        layout.addRow("Name", name_edit)
        self.widgets['name'] = name_edit
        # Friendly type label
        t_internal = str(getattr(elem, 'element_type', '') or '')
        friendly_map = {
            TYPE_APERTURE: "Aperture",
            TYPE_LENS: "Lens",
            TYPE_SCREEN: "Screen",
            TYPE_APERTURE_RESULT: "Aperture Result",
            TYPE_TARGET_INTENSITY: "Target Intensity",
        }
        type_label = QLabel(friendly_map.get(t_internal, t_internal))
        layout.addRow("Type", type_label)
        # Distance
        dist_spin = QDoubleSpinBox()
        dist_spin.setRange(GLOBAL_MINIMUM_DISTANCE_MM, GLOBAL_MAXIMUM_DISTANCE_MM)
        dist_spin.setDecimals(2)
        dist_spin.setValue(float(getattr(elem, 'distance', 0.0)))
        dist_spin.setSuffix(" mm")
        layout.addRow("Distance", dist_spin)
        self.widgets['distance'] = dist_spin
        # Type-specific fields
        t = getattr(elem, 'element_type', None)
        if t == TYPE_LENS:
            f_spin = QDoubleSpinBox()
            f_spin.setRange(GLOBAL_MINIMUM_DISTANCE_MM, GLOBAL_MAXIMUM_DISTANCE_MM)
            f_spin.setDecimals(2)
            f_spin.setValue(float(getattr(elem, 'focal_length', 0.0)))
            f_spin.setSuffix(" mm")
            layout.addRow("Focal length", f_spin)
            self.widgets['focal_length'] = f_spin
        if t == TYPE_APERTURE:
            inverted_cb = QCheckBox("Inverted")
            inverted_cb.setChecked(bool(getattr(elem, 'is_inverted', False)))
            layout.addRow(inverted_cb)
            self.widgets['is_inverted'] = inverted_cb
            phasemask_cb = QCheckBox("Phase mask")
            phasemask_cb.setChecked(bool(getattr(elem, 'is_phasemask', False)))
            layout.addRow(phasemask_cb)
            self.widgets['is_phasemask'] = phasemask_cb
        if t in (TYPE_APERTURE, TYPE_TARGET_INTENSITY):
            path_edit = QLineEdit(getattr(elem, 'image_path', ''))
            layout.addRow("Image Path", path_edit)
            self.widgets['image_path'] = path_edit
        if t == TYPE_SCREEN:
            is_range = QCheckBox("Range of screens")
            is_range.setChecked(bool(getattr(elem, 'is_range', False)))
            layout.addRow(is_range)
            self.widgets['is_range'] = is_range
            range_end = QDoubleSpinBox()
            range_end.setRange(GLOBAL_MINIMUM_DISTANCE_MM, GLOBAL_MAXIMUM_DISTANCE_MM)
            range_end.setDecimals(2)
            range_end.setValue(float(getattr(elem, 'range_end', getattr(elem, 'distance', 0.0))))
            range_end.setSuffix(" mm")
            layout.addRow("Range End", range_end)
            self.widgets['range_end'] = range_end
            steps = QSpinBox()
            steps.setRange(1, 10000)
            steps.setValue(int(getattr(elem, 'steps', 10)))
            layout.addRow("Steps", steps)
            self.widgets['steps'] = steps
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.setLayout(layout)

    def apply_changes(self):
        w = self.widgets
        if 'name' in w:
            self.elem.name = w['name'].text()
        if 'distance' in w:
            self.elem.distance = float(w['distance'].value())
        if 'focal_length' in w and hasattr(self.elem, 'focal_length'):
            self.elem.focal_length = float(w['focal_length'].value())
        if 'image_path' in w and hasattr(self.elem, 'image_path'):
            self.elem.image_path = w['image_path'].text()
        if 'is_inverted' in w and hasattr(self.elem, 'is_inverted'):
            self.elem.is_inverted = bool(w['is_inverted'].isChecked())
        if 'is_phasemask' in w and hasattr(self.elem, 'is_phasemask'):
            self.elem.is_phasemask = bool(w['is_phasemask'].isChecked())
        if 'is_range' in w and hasattr(self.elem, 'is_range'):
            self.elem.is_range = bool(w['is_range'].isChecked())
        if 'range_end' in w and hasattr(self.elem, 'range_end'):
            re_val = float(w['range_end'].value())
            if re_val < float(getattr(self.elem, 'distance', 0.0)):
                re_val = float(getattr(self.elem, 'distance', 0.0))
            self.elem.range_end = re_val
        if 'steps' in w and hasattr(self.elem, 'steps'):
            self.elem.steps = max(1, int(w['steps'].value()))
