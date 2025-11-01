from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QTableWidget, QTableWidgetItem, QComboBox, QDoubleSpinBox, QHeaderView, QFileDialog, QLineEdit, QMessageBox, QCheckBox, QSpinBox, QApplication
from PyQt6.QtCore import Qt, QSettings, QEvent, QTimer
from typing import Optional
from widgets.preferences_window import getpref
from widgets.preferences_window import (
    SET_ENABLE_SCROLLWHEEL,
    SET_SELECT_ALL_ON_FOCUS,
    SET_USE_RELATIVE_PATHS,
    SET_RENAME_ON_TYPE_CHANGE,
    SET_WARN_BEFORE_DELETE,
)

GLOBAL_MINIMUM_DISTANCE_MM = 0.01
GLOBAL_MAXIMUM_DISTANCE_MM = 100000.0
GLOBAL_DEFAULT_DISTANCE_MM = 10.0
LENS_DEFAULT_FOCUS_MM = 1000.0
GLOBAL_DISTANCE_TEXT = "Placement"

class ElementNode:
    def __init__(self, name, elem_type, distance, focal_length=None, aperture_path=None, is_range=None, range_end=None, steps=None):
        self.name = name
        self.type = elem_type
        self.distance = distance
        self.focal_length = focal_length
        self.aperture_path = aperture_path
        # Screen-specific
        self.is_range = is_range  # boolean indicating if it's a range of screens
        self.range_end = range_end if range_end is not None else distance + GLOBAL_DEFAULT_DISTANCE_MM
        self.steps = int(steps) if steps is not None else 10
        self.next: Optional[ElementNode] = None

class PhysicalSetupVisualizer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Widget layout
        layout = QVBoxLayout(self)
        label = QLabel("<b>Physical Setup</b>")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Name", "Element type", f"{GLOBAL_DISTANCE_TEXT} (mm)", "Value (type dependent)"])
        header = self.table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        layout.addWidget(self.table)
        btn_layout = QHBoxLayout()
        self.add_aperture_btn = QPushButton("Add Aperture")
        self.add_aperture_btn.clicked.connect(lambda: self.add_element("Aperture"))
        btn_layout.addWidget(self.add_aperture_btn)
        self.add_lens_btn = QPushButton("Add Lens")
        self.add_lens_btn.clicked.connect(lambda: self.add_element("Lens"))
        btn_layout.addWidget(self.add_lens_btn)
        self.add_screen_btn = QPushButton("Add Screen")
        self.add_screen_btn.clicked.connect(lambda: self.add_element("Screen"))
        btn_layout.addWidget(self.add_screen_btn)
        self.del_btn = QPushButton("Delete selected element(s)")
        self.del_btn.setEnabled(True)  # Keep enabled; handler is a no-op when nothing valid is selected
        self.del_btn.clicked.connect(self.delete_selected_elements)
        btn_layout.addWidget(self.del_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        # Linked list head: always the light source
        self.head = ElementNode("Light Source", "LightSource", 0)
        self._restore_header_state()
        self.table.itemSelectionChanged.connect(self._update_delete_button_state)
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
        return super().eventFilter(a0, a1)

    def _to_pref_path(self, path: str) -> str:
        import os
        if not path:
            return path
        if bool(getpref(SET_USE_RELATIVE_PATHS)):
            try:
                return os.path.relpath(path, os.getcwd())
            except Exception:
                return path
        return path

    def _abs_path(self, path: Optional[str]) -> Optional[str]:
        import os
        if not path:
            return path
        try:
            return path if os.path.isabs(path) else os.path.abspath(path)
        except Exception:
            return path

    def _normalize_aperture_display_path(self, stored_path: Optional[str]) -> str:
        # Always display according to current preference, regardless of how it is stored
        ap = self._abs_path(stored_path)
        return self._to_pref_path(ap) if ap else ""

    def _find_row_for_node(self, target) -> Optional[int]:
        """Return table row index for a given node, or None if not found."""
        row = 0
        cur = self.head
        while cur is not None:
            if cur is target:
                return row
            cur = cur.next
            row += 1
        return None

    def _build_screen_distance_widget(self, node):
        """Create the distance cell widget for a Screen row based on node.is_range."""
        if bool(node.is_range):
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
            dist_from.setValue(node.distance)
            dist_from.editingFinished.connect(lambda nd=node, w=dist_from: self._on_distance_edited(nd, w.value()))
            to_lbl = QLabel("To:", dist_widget)
            dist_to = QDoubleSpinBox(dist_widget)
            # Install event filter for preferences
            dist_to.installEventFilter(self)
            dist_to.setRange(GLOBAL_MINIMUM_DISTANCE_MM, GLOBAL_MAXIMUM_DISTANCE_MM)
            dist_to.setDecimals(3)
            dist_to.setSuffix(" mm")
            dist_to.setValue(node.range_end if node.range_end is not None else node.distance)
            dist_to.editingFinished.connect(lambda nd=node, w=dist_to: self._on_screen_range_end_edited(nd, w.value()))
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
            dist_spin.setValue(node.distance)
            dist_spin.setSuffix(" mm")
            dist_spin.editingFinished.connect(lambda nd=node, w=dist_spin: self._on_distance_edited(nd, w.value()))
            return dist_spin

    def refresh_table(self):
        self.table.setRowCount(0)
        node = self.head
        idx = 0
        while node:
            self.table.insertRow(idx)
            # Name
            if node.type == "LightSource":
                name_item = QTableWidgetItem(node.name)
                name_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(idx, 0, name_item)
            else:
                name_edit = QLineEdit(node.name)
                name_edit.installEventFilter(self)
                name_edit.editingFinished.connect(lambda n=name_edit, nd=node: self._on_name_edited(nd, n.text()))
                self.table.setCellWidget(idx, 0, name_edit)
            # Type
            if node.type == "LightSource":
                type_item = QTableWidgetItem("(White Aperture)")
                type_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(idx, 1, type_item)
            else:
                combo = QComboBox()
                combo.addItems(["Aperture", "Lens", "Screen"])
                combo.setCurrentText(node.type)
                combo.installEventFilter(self)
                combo.currentTextChanged.connect(lambda t, nd=node: self._on_type_changed(nd, t))
                self.table.setCellWidget(idx, 1, combo)
            # Distance
            if node.type == "LightSource":
                dist_item = QTableWidgetItem("0 mm")
                dist_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(idx, 2, dist_item)
            else:
                if node.type == "Screen":
                    self.table.setCellWidget(idx, 2, self._build_screen_distance_widget(node))
                else:
                    dist_spin = QDoubleSpinBox(self.table)
                    dist_spin.installEventFilter(self)
                    dist_spin.setRange(GLOBAL_MINIMUM_DISTANCE_MM, GLOBAL_MAXIMUM_DISTANCE_MM)
                    dist_spin.setDecimals(2)
                    dist_spin.setValue(node.distance)
                    dist_spin.setSuffix(" mm")
                    dist_spin.editingFinished.connect(lambda nd=node, w=dist_spin: self._on_distance_edited(nd, w.value()))
                    self.table.setCellWidget(idx, 2, dist_spin)
            # Value
            if node.type == "LightSource":
                value_item = QTableWidgetItem("Full white")
                value_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(idx, 3, value_item)
            elif node.type == "Aperture":
                path_widget = QWidget(self.table)
                path_layout = QHBoxLayout(path_widget)
                path_layout.setContentsMargins(0, 0, 0, 0)
                # Normalize path display to current preference
                path_edit = QLineEdit(self._normalize_aperture_display_path(node.aperture_path), path_widget)
                path_edit.installEventFilter(self)
                browse_btn = QPushButton("...", path_widget)
                browse_btn.setFixedWidth(28)
                browse_btn.clicked.connect(lambda _=None, nd=node, pe=path_edit: self._browse_aperture(nd, pe))
                path_edit.editingFinished.connect(lambda nd=node, pe=path_edit: self._on_aperture_path_edited(nd, pe.text()))
                path_layout.addWidget(path_edit)
                path_layout.addWidget(browse_btn)
                self.table.setCellWidget(idx, 3, path_widget)
            elif node.type == "Lens":
                f_spin = QDoubleSpinBox(self.table)
                f_spin.installEventFilter(self)
                f_spin.setRange(GLOBAL_MINIMUM_DISTANCE_MM, GLOBAL_MAXIMUM_DISTANCE_MM)
                f_spin.setDecimals(2)
                f_spin.setValue(node.focal_length or LENS_DEFAULT_FOCUS_MM)
                f_spin.setSuffix(" mm")
                f_spin.editingFinished.connect(lambda nd=node, w=f_spin: self._on_focal_length_edited(nd, w.value()))
                self.table.setCellWidget(idx, 3, f_spin)
            elif node.type == "Screen":
                value_widget = QWidget(self.table)
                vlayout = QHBoxLayout(value_widget)
                vlayout.setContentsMargins(0, 0, 0, 0)
                range_checkbox = QCheckBox("Range of screens", value_widget)
                range_checkbox.setChecked(bool(node.is_range))
                steps_label = QLabel("steps:", value_widget)
                steps_spin = QSpinBox(value_widget)
                steps_spin.installEventFilter(self)
                steps_spin.setRange(2, 10000)
                steps_spin.setValue(int(node.steps or 10))
                steps_label.setVisible(bool(node.is_range))
                steps_spin.setVisible(bool(node.is_range))
                range_checkbox.toggled.connect(lambda checked, nd=node, sl=steps_label, ss=steps_spin: self._on_screen_range_edited(nd, checked, sl, ss))
                steps_spin.valueChanged.connect(lambda val, nd=node: self._on_screen_steps_edited(nd, int(val)))
                vlayout.addWidget(range_checkbox)
                vlayout.addWidget(steps_label)
                vlayout.addWidget(steps_spin)
                vlayout.addStretch()
                self.table.setCellWidget(idx, 3, value_widget)
            node = node.next
            idx += 1
        self._update_delete_button_state()
        # Notify image containers that the element list or attributes changed
        self._notify_image_containers_changed()

    def add_element(self, elem_type):
        import os
        from PIL import Image
        # Ensure white.png exists in ./aperatures/
        aperture_dir = os.path.join(os.getcwd(), "aperatures")
        white_path = os.path.join(aperture_dir, "white.png")
        if elem_type == "Aperture":
            if not os.path.exists(aperture_dir):
                os.makedirs(aperture_dir, exist_ok=True)
            if not os.path.exists(white_path):
                # Create a 256x256 white PNG
                img = Image.new("L", (256, 256), 255)
                img.save(white_path)
        # Find last node
        node = self.head
        while node.next:
            node = node.next
        last_distance = node.distance
        if elem_type == "Aperture":
            name = f"Aperture {self._count_type('Aperture')+1}"
            stored_path = self._to_pref_path(white_path)
            new_node = ElementNode(name, "Aperture", last_distance + GLOBAL_DEFAULT_DISTANCE_MM, aperture_path=stored_path)
        elif elem_type == "Lens":
            name = f"Lens {self._count_type('Lens')+1}"
            new_node = ElementNode(name, "Lens", last_distance + GLOBAL_DEFAULT_DISTANCE_MM, focal_length=LENS_DEFAULT_FOCUS_MM)
        else:  # Screen
            name = f"Screen {self._count_type('Screen')+1}"
            new_node = ElementNode(name, "Screen", last_distance + GLOBAL_DEFAULT_DISTANCE_MM, is_range=False, range_end=last_distance + GLOBAL_DEFAULT_DISTANCE_MM, steps=10)
        node.next = new_node
        self.refresh_table()

    def _count_type(self, elem_type):
        count = 0
        node = self.head.next
        while node:
            if node.type == elem_type:
                count += 1
            node = node.next
        return count

    def _is_default_generated_name(self, node: 'ElementNode') -> bool:
        import re as _re
        m = _re.match(r'^(Aperture|Lens|Screen)\s+(\d+)$', str(node.name))
        return m is not None

    def _name_exists(self, name: str, exclude: Optional['ElementNode'] = None) -> bool:
        cur = self.head
        while cur is not None:
            if cur is not exclude and cur.name == name:
                return True
            cur = cur.next
        return False

    def _on_name_edited(self, node, new_name):
        node.name = new_name
        self._notify_image_containers_changed()

    def _on_type_changed(self, node, new_type):
        # TODO: if the setting is enabled, rename any default element names eg: "Aperture 2" to "Lens 2" when changing type. You should just replace the Lens string to Aperture. BUT if it would result in a non-unique name, abort the renaming! renaming element to a non-unique name should ALWAYS be run against the unique name check, and aborted (silently) if it would result in a non-unique name.
        old_type = node.type
        node.type = new_type
        
        # Rename element if preference enabled and current name is default-generated
        try:
            if bool(getpref(SET_RENAME_ON_TYPE_CHANGE)) and self._is_default_generated_name(node):
                import re as _re
                m = _re.match(r'^(Aperture|Lens|Screen)\s+(\d+)$', str(node.name))
                if m:
                    suffix = m.group(2)
                    desired = f"{new_type} {suffix}"
                    # Abort renaming if it would not be unique
                    if not self._name_exists(desired, exclude=node):
                        node.name = desired
        except Exception:
            pass
        
        # Only set default values if this is a new element or if the specific value wasn't set before
        if new_type == "Aperture":
            # Set default aperture path only if it wasn't set before
            if node.aperture_path is None:
                node.aperture_path = ""
        elif new_type == "Lens":
            # Set default focal length only if it wasn't set before
            if node.focal_length is None:
                node.focal_length = LENS_DEFAULT_FOCUS_MM
        elif new_type == "Screen":
            # Set default is_range only if it wasn't set before
            if node.is_range is None:
                node.is_range = False
        
        self.refresh_table()

    def _on_distance_edited(self, node, new_distance):
        if node is self.head:
            return

        # Snapshot original order so we can compare positions later
        original_order = []
        cur = self.head.next
        while cur:
            original_order.append(cur)
            cur = cur.next

        node.distance = new_distance

        # Remove node from current list (if present)
        prev = self.head
        cur = self.head.next
        while cur and cur is not node:
            prev = cur
            cur = cur.next
        if cur is node:
            assert cur is not None 
            prev.next = cur.next
            cur.next = None  # detach to avoid accidental cycles

        # Find any other element that has the same distance
        match_node = None
        cur = self.head.next
        while cur:
            if cur is not node and cur.distance == new_distance:
                match_node = cur
                break
            cur = cur.next

        # Determine whether node was before the matched node in the original list
        was_before = False
        if match_node:
            try:
                was_before = original_order.index(node) < original_order.index(match_node)
            except ValueError:
                # In the unlikely event one of them isn't in the snapshot, default to insert after
                was_before = False

        # Insert node at the correct position
        if match_node:
            if was_before:
                # Insert BEFORE the matched node
                prev = self.head
                cur = self.head.next
                while cur and cur is not match_node:
                    prev = cur
                    cur = cur.next
                prev.next = node
                node.next = match_node
            else:
                # Insert AFTER the matched node
                node.next = match_node.next
                match_node.next = node
        else:
            # Insert in sorted order by distance (ascending)
            prev = self.head
            cur = self.head.next
            while cur and cur.distance < new_distance:
                prev = cur
                cur = cur.next
            prev.next = node
            node.next = cur

        self.refresh_table()

    def _on_focal_length_edited(self, node, new_f):
        node.focal_length = new_f

    def _on_aperture_path_edited(self, node, new_path):
        # Store path according to current preference
        from os.path import abspath
        try:
            node.aperture_path = self._to_pref_path(abspath(new_path))
        except Exception:
            node.aperture_path = self._to_pref_path(new_path)
        # Refresh aperture image container if needed
        self._notify_image_containers_changed()

    def _on_screen_range_edited(self, node, is_range, steps_label, steps_spin):
        node.is_range = is_range
        # Update steps visibility in-place
        steps_label.setVisible(bool(is_range))
        steps_spin.setVisible(bool(is_range))
        # Update the distance cell widget for this row without refreshing entire table
        row = self._find_row_for_node(node)
        if row is not None:
            self.table.setCellWidget(row, 2, self._build_screen_distance_widget(node))
        # Notify image containers (affects screen browsing UI and solve enablement)
        self._notify_image_containers_changed()

    def _on_screen_range_end_edited(self, node, new_end):
        # Ensure range_end is not less than start
        if new_end < node.distance:
            new_end = node.distance
        node.range_end = new_end
        self._notify_image_containers_changed()

    def _on_screen_steps_edited(self, node, steps):
        node.steps = max(2, int(steps))
        self._notify_image_containers_changed()

    def _browse_aperture(self, node, path_edit):
        dlg = QFileDialog(self, "Select Aperture Bitmap", "", "Images (*.png *.jpg *.bmp)")
        if dlg.exec():
            files = dlg.selectedFiles()
            if files:
                stored = self._to_pref_path(files[0])
                node.aperture_path = stored
                # Display normalized according to current preference
                path_edit.setText(self._normalize_aperture_display_path(node.aperture_path))
                self._notify_image_containers_changed()

    def _update_delete_button_state(self):
        # Always keep delete enabled; the handler checks for valid selection.
        self.del_btn.setEnabled(True)

    def delete_selected_elements(self):
        # Collect selected table rows (skip Light Source at row 0)
        selected_rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        valid_rows = [r for r in selected_rows if r > 0]
        if not valid_rows:
            return

        # Map selected rows -> nodes and names by walking the linked list once
        row_to_node = {}
        cur = self.head.next
        row_idx = 1  # table row index for first real element
        while cur is not None:
            if row_idx in valid_rows:
                row_to_node[row_idx] = cur
            cur = cur.next
            row_idx += 1

        # Build confirmation message with stable ordering by row number
        confirm = bool(getpref(SET_WARN_BEFORE_DELETE))
        if confirm:
            lines = [f"Element {r}: {row_to_node[r].name}" for r in valid_rows if r in row_to_node]
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

        # Robust deletion: rebuild the linked list excluding selected nodes
        to_delete = set(row_to_node.values())
        prev = self.head
        cur = self.head.next
        while cur is not None:
            if cur in to_delete:
                # Skip this node
                prev.next = cur.next
                cur = prev.next
            else:
                prev = cur
                cur = cur.next

        self.refresh_table()

    def _rewrite_aperture_paths_in_table(self):
        # Iterate rows and rewrite only Aperture path editors to reflect preference
        row = 1
        cur = self.head.next
        while cur is not None:
            if cur.type == "Aperture":
                cell = self.table.cellWidget(row, 3)
                if cell is not None:
                    try:
                        pe = cell.findChild(QLineEdit)
                        if pe is not None:
                            pe.setText(self._normalize_aperture_display_path(cur.aperture_path))
                    except Exception:
                        pass
            cur = cur.next
            row += 1

    def _restore_header_state(self):
        try:
            header = self.table.horizontalHeader()
            if header is not None:
                # Keep default header; main window geometry persistence is used for overall window layout
                pass
        except Exception:
            pass

    def export_elements_for_engine(self):
        import engine
        elements = []
        node = self.head.next  # skip light source
        while node:
            params = {}
            params["name"] = node.name
            if node.type == "Aperture":
                if node.aperture_path:
                    params["image_path"] = node.aperture_path
                    # Always include physical size for image apertures - Not using right now, but keep in for future use
                    params["width_mm"] = 1.0
                    params["height_mm"] = 1.0
            elif node.type == "Lens":
                params["f"] = node.focal_length
            elif node.type == "Screen":
                params["is_range"] = bool(node.is_range)
                params["range_end_mm"] = float(node.range_end if node.range_end is not None else node.distance)
                params["steps"] = int(node.steps if node.steps is not None else 10) # TODO: this always fails and returns 10 
            elements.append(engine.Element(distance=node.distance, element_type=node.type.lower(), params=params, name=node.name))
            node = node.next
        return elements

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
