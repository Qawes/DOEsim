from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QTableWidget, QTableWidgetItem, QComboBox, QDoubleSpinBox, QHeaderView, QFileDialog, QLineEdit, QStackedLayout, QMessageBox
from PyQt6.QtCore import Qt, QSettings
from typing import Optional
from widgets.system_parameters_widget import DEFAULT_RESOLUTION_PX_PER_MM, DEFAULT_EXTENSION_Y_MM, DEFAULT_EXTENSION_X_MM, DEFAULT_WAVELENGTH_NM

UpdateNameOnTypeChange = False

class ElementNode:
    def __init__(self, name, elem_type, distance, focal_length=None, aperture_path=None):
        self.name = name
        self.type = elem_type
        self.distance = distance
        self.focal_length = focal_length
        self.aperture_path = aperture_path
        self.next: Optional[ElementNode] = None

class PhysicalSetupVisualizer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("diffractsim", "PhysicalSetupVisualizer")
        layout = QVBoxLayout(self)
        label = QLabel("<b>Physical Setup</b>")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Name", "Element type", "Distance (mm)", "Value (type dependent)"])
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
        self.del_btn = QPushButton("Delete selected element(s)")
        self.del_btn.setEnabled(False)
        self.del_btn.clicked.connect(self.delete_selected_elements)
        btn_layout.addWidget(self.del_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        # Linked list head: always the light source
        self.head = ElementNode("Light Source", "LightSource", 0)
        self._restore_column_widths()
        self.table.itemSelectionChanged.connect(self._update_delete_button_state)
        self.refresh_table()

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
                name_edit.editingFinished.connect(lambda n=name_edit, nd=node: self._on_name_edited(nd, n.text()))
                self.table.setCellWidget(idx, 0, name_edit)
            # Type
            if node.type == "LightSource":
                type_item = QTableWidgetItem("(White Aperture)")
                type_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(idx, 1, type_item)
            else:
                combo = QComboBox()
                combo.addItems(["Aperture", "Lens"])
                combo.setCurrentText(node.type)
                combo.currentTextChanged.connect(lambda t, nd=node: self._on_type_changed(nd, t))
                self.table.setCellWidget(idx, 1, combo)
            # Distance
            if node.type == "LightSource":
                dist_item = QTableWidgetItem("0 mm")
                dist_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(idx, 2, dist_item)
            else:
                dist_spin = QDoubleSpinBox()
                dist_spin.setRange(0.01, 1000)
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
                path_widget = QWidget()
                path_layout = QHBoxLayout(path_widget)
                path_layout.setContentsMargins(0, 0, 0, 0)
                path_edit = QLineEdit(node.aperture_path or "")
                browse_btn = QPushButton("...")
                browse_btn.setFixedWidth(28)
                browse_btn.clicked.connect(lambda _=None, nd=node, pe=path_edit: self._browse_aperture(nd, pe))
                path_edit.editingFinished.connect(lambda nd=node, pe=path_edit: self._on_aperture_path_edited(nd, pe.text()))
                path_layout.addWidget(path_edit)
                path_layout.addWidget(browse_btn)
                self.table.setCellWidget(idx, 3, path_widget)
            elif node.type == "Lens":
                f_spin = QDoubleSpinBox()
                f_spin.setRange(0.01, 1000)
                f_spin.setDecimals(2)
                f_spin.setValue(node.focal_length or 80)
                f_spin.setSuffix(" mm")
                f_spin.editingFinished.connect(lambda nd=node, w=f_spin: self._on_focal_length_edited(nd, w.value()))
                self.table.setCellWidget(idx, 3, f_spin)
            node = node.next
            idx += 1
        self._update_delete_button_state()

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
            new_node = ElementNode(name, "Aperture", last_distance+10, aperture_path=white_path)
        else:
            name = f"Lens {self._count_type('Lens')+1}"
            new_node = ElementNode(name, "Lens", last_distance+10, focal_length=80)
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

    def _on_name_edited(self, node, new_name):
        node.name = new_name

    def _on_type_changed(self, node, new_type):
        node.type = new_type
        if new_type == "Aperture":
            node.focal_length = None
            node.aperture_path = ""
        else:
            node.focal_length = 80
            node.aperture_path = None
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

        old_distance = node.distance
        node.distance = new_distance

        # Remove node from current list (if present)
        prev = self.head
        cur = self.head.next
        while cur and cur is not node:
            prev = cur
            cur = cur.next
        if cur is node:
            assert cur is not None # TODO: what is this
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
        node.aperture_path = new_path

    def _browse_aperture(self, node, path_edit):
        dlg = QFileDialog(self, "Select Aperture Bitmap", "", "Images (*.png *.jpg *.bmp)")
        if dlg.exec():
            files = dlg.selectedFiles()
            if files:
                node.aperture_path = files[0]
                path_edit.setText(files[0])

    def _update_delete_button_state(self):
        selected_rows = set(idx.row() for idx in self.table.selectedIndexes())
        valid_rows = [r for r in selected_rows if r > 0]
        self.del_btn.setEnabled(bool(valid_rows))

    def delete_selected_elements(self):
        # Reverse should be False, so that we ensure proper order
        selected_rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()), reverse=False)
        valid_rows = [r for r in selected_rows if r > 0]
        if not valid_rows:
            return
        # Gather names and nodes
        names = []
        nodes_to_delete = []
        node = self.head
        idx = 0
        while node and node.next:
            next_node = node.next
            idx += 1
            if idx in valid_rows:
                names.append(next_node.name)
                nodes_to_delete.append((node, next_node))
            node = node.next
        # A +1 offset is needed to match table numbering
        msg = f"Are you sure you want to delete {len(valid_rows)} element(s)?\n\n" + "\n".join(f"Element {r + 1}: {n}" for r, n in zip(valid_rows, names))
        reply = QMessageBox.question(self, "Delete elements", msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            for prev, n in nodes_to_delete:
                prev.next = n.next
            self.refresh_table()

    def resizeEvent(self, a0):
        super().resizeEvent(a0)
        header = self.table.horizontalHeader()
        viewport = self.table.viewport()
        if header is not None and viewport is not None:
            self._resize_columns_proportionally(header, viewport)
            self._save_column_widths(header)

    def _resize_columns_proportionally(self, header, viewport):
        total_width = viewport.width() if viewport is not None else 1
        proportions = [0.2, 0.2, 0.2, 0.4]
        for i, prop in enumerate(proportions):
            if header is not None:
                header.resizeSection(i, int(total_width * prop))

    def _save_column_widths(self, header):
        if header is not None:
            for i in range(self.table.columnCount()):
                self.settings.setValue(f"col_width_{i}", header.sectionSize(i))

    def _restore_column_widths(self):
        header = self.table.horizontalHeader()
        if header is not None:
            for i in range(self.table.columnCount()):
                w = self.settings.value(f"col_width_{i}", None)
                if w is not None:
                    header.resizeSection(i, int(w))

    def export_elements_for_engine(self):
        import engine
        elements = []
        node = self.head.next  # skip light source
        while node:
            params = {}
            if node.type == "Aperture":
                if node.aperture_path:
                    params["image_path"] = node.aperture_path
                    # Always include physical size for image apertures - Not using right now, but keep in for future use
                    params["width_mm"] = 1.0
                    params["height_mm"] = 1.0
            elif node.type == "Lens":
                params["f"] = node.focal_length
            elements.append(engine.Element(distance=node.distance, element_type=node.type.lower(), params=params))
            node = node.next
        return elements
