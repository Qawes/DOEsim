import os
import sys
import unittest
import time
import json
from unittest.mock import patch
from typing import Optional, cast

TESTING_TAB_NAME = "Testing"
TESTING_WAVELENGTH_NM = 440
TESTING_EXTENSION_X_MM = 6
TESTING_EXTENSION_Y_MM = 6
TESTING_RESOLUTION_PX_PER_MM = 128

# Allow running headless via: python GUI_test.py --headless
HEADLESS = "--headless" in sys.argv
if HEADLESS:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    # Remove the flag so unittest doesn't see it
    sys.argv = [a for a in sys.argv if a != "--headless"]

from PyQt6.QtWidgets import (
    QApplication,
    QInputDialog,
    QMessageBox,
    QLineEdit,
    QDoubleSpinBox,
    QAbstractItemView,
    QComboBox,
    QWidget,
    QCheckBox,
    QMenuBar,
)
from PyQt6.QtCore import Qt

from main_window import MainWindow, WorkspaceTab
from widgets.system_parameters_widget import (
    DEFAULT_WAVELENGTH_NM,
    DEFAULT_EXTENSION_X_MM,
    DEFAULT_EXTENSION_Y_MM,
    DEFAULT_RESOLUTION_PX_PER_MM,
)

# --- Concise test result logging (per-test in tearDown) ---

def wait_until(predicate, timeout_ms=5000, step_ms=25):
    start = time.time()
    while (time.time() - start) * 1000 < timeout_ms:
        QApplication.processEvents()
        try:
            if predicate():
                return True
        except Exception:
            pass
        time.sleep(step_ms / 1000.0)
    return False


def find_row_by_name(table, name: str) -> int:
    for r in range(table.rowCount()):
        w = table.cellWidget(r, 0)
        if isinstance(w, QLineEdit) and w.text() == name:
            return r
    return -1


def set_name(table, row: int, new_name: str):
    editor = table.cellWidget(row, 0)
    assert isinstance(editor, QLineEdit)
    editor.setText(new_name)
    try:
        editor.editingFinished.emit()
    except Exception:
        pass


def set_distance(table, row: int, new_dist: float):
    w = table.cellWidget(row, 2)
    # If it's a single QDoubleSpinBox
    if isinstance(w, QDoubleSpinBox):
        w.setValue(new_dist)
        try:
            w.editingFinished.emit()
        except Exception:
            pass
        return
    # If it's a composite widget (range enabled): the "From" editor is the first QDoubleSpinBox
    if isinstance(w, QWidget):
        spins = w.findChildren(QDoubleSpinBox)
        if spins:
            spins[0].setValue(new_dist)
            try:
                spins[0].editingFinished.emit()
            except Exception:
                pass


def set_aperture_image_path(table, row: int, path: str):
    type_w = table.cellWidget(row, 1)
    if not isinstance(type_w, QComboBox):
        return
    if "aperture" not in type_w.currentText().strip().lower():
        return
    cell = table.cellWidget(row, 3)
    if cell is None:
        return
    line = cell.findChild(QLineEdit)
    if line is None:
        return
    line.setText(path)
    try:
        line.editingFinished.emit()
    except Exception:
        pass


def set_screen_range(table, row: int, is_enabled: bool, start_val: float | None = None, end_val: float | None = None, steps: int | None = None):
    # Toggle the checkbox
    val_cell = table.cellWidget(row, 3)
    if val_cell is None:
        return
    chk = val_cell.findChild(QCheckBox)
    if chk is None:
        return
    chk.setChecked(is_enabled)
    QApplication.processEvents()

    # Wait for the range UI (two spinboxes) to appear when enabling range
    if is_enabled:
        wait_until(
            lambda: isinstance(table.cellWidget(row, 2), QWidget)
                    and len(table.cellWidget(row, 2).findChildren(QDoubleSpinBox)) >= 2,
            timeout_ms=500
        )

    # Set steps if provided
    if steps is not None:
        from PyQt6.QtWidgets import QSpinBox
        sp = val_cell.findChild(QSpinBox)
        if sp is not None:
            sp.setValue(int(steps))
            try:
                sp.editingFinished.emit()
            except Exception:
                pass
            # steps change may rebuild the row; ensure widgets are recreated
            QApplication.processEvents()
            wait_until(
                lambda: isinstance(table.cellWidget(row, 2), QWidget)
                        and len(table.cellWidget(row, 2).findChildren(QDoubleSpinBox)) >= 2,
                timeout_ms=500
            )

    # Set start/end in distance cell if provided
    dist_cell = table.cellWidget(row, 2)
    if isinstance(dist_cell, QWidget):
        spins = dist_cell.findChildren(QDoubleSpinBox)
        # Ensure left-to-right ordering: [From, To]
        if len(spins) >= 2:
            spins = sorted(spins, key=lambda s: s.geometry().x())
        if start_val is not None and spins:
            spins[0].setValue(float(start_val))
            try:
                spins[0].editingFinished.emit()
            except Exception:
                pass
            # Setting start may rebuild the row; reacquire the spinboxes
            QApplication.processEvents()
            dist_cell = table.cellWidget(row, 2)
            if isinstance(dist_cell, QWidget):
                spins = dist_cell.findChildren(QDoubleSpinBox)
                if len(spins) >= 2:
                    spins = sorted(spins, key=lambda s: s.geometry().x())
        if end_val is not None and len(spins) > 1:
            spins[1].setValue(float(end_val))
            try:
                spins[1].editingFinished.emit()
            except Exception:
                pass


def ensure_dirs():
    os.makedirs(os.path.join(os.getcwd(), "workspaces"), exist_ok=True)
    os.makedirs(os.path.join(os.getcwd(), "aperatures"), exist_ok=True)


class GUITestCase(unittest.TestCase):
    app: Optional[QApplication] = None
    window: Optional[MainWindow] = None
    _orig_engine: Optional[object] = None
    _has_failures: bool = False

    @classmethod
    def setUpClass(cls):
        ensure_dirs()
        # Create a single QApplication for all tests
        existing_app = QApplication.instance()
        if existing_app is None:
            existing_app = QApplication(sys.argv)
        cls.app = cast(QApplication, existing_app)
        # Create the main window
        cls.window = MainWindow()
        cls.window.show()
        wait_until(lambda: True, 200)
        # Speed up tests by monkey-patching the engine calculation to a fast stub
        import engine
        import numpy as np
        cls._orig_engine = engine.calculate_screen_images
        def _fast_calc_stub(**kwargs):
            return np.zeros((64, 64, 3), dtype=np.uint8)
        engine.calculate_screen_images = _fast_calc_stub
        print("\n")  # Newline before test logs

    @classmethod
    def tearDownClass(cls):
        try:
            import engine
            if cls._orig_engine is not None:
                engine.calculate_screen_images = cls._orig_engine  # type: ignore[assignment]
        except Exception:
            pass
        if not cls._has_failures and cls.window is not None:
            cls.window.close()

    def tearDown(self):
        # Reset to a single blank default workspace after each test
        try:
            window = cast(MainWindow, self.window)
            tabs = window.tabs
            # Remove all existing tabs without prompting
            while tabs.count() > 0:
                tabs.removeTab(0)
            # Add one default workspace tab
            window.add_new_tab()
            tabs.setCurrentIndex(0)
        except Exception:
            pass
        # Concise per-test log line with failure details when applicable
        label = getattr(self, "_testMethodName", self.__class__.__name__)
        if label.startswith("test_"):
            label = label[len("test_"):]
        label = label.replace("_", " ")
        status = "PASS"
        detail = ""
        outcome = getattr(self, "_outcome", None)
        try:
            result = getattr(outcome, "result", None)
            if result:
                # Find this test in failures or errors and extract the last traceback line
                def _extract_msg(pairs):
                    for t, tb in pairs:
                        if t is self and isinstance(tb, str):
                            lines = [ln for ln in tb.splitlines() if ln.strip()]
                            return lines[-1] if lines else ""
                    return ""
                if any(t is self for t, _ in getattr(result, "failures", [])):
                    status = "FAIL"
                    detail = _extract_msg(getattr(result, "failures", []))
                elif any(t is self for t, _ in getattr(result, "errors", [])):
                    status = "ERROR"
                    detail = _extract_msg(getattr(result, "errors", []))
        except Exception:
            pass
        if status != "PASS":
            GUITestCase._has_failures = True
        # Print status with optional detail
        if detail:
            print(f"[{status}] {label} - {detail}")
        else:
            print(f"[{status}] {label}")

    # 1) create new workspace and rename; close old default
    def test_01_new_and_rename_close_old(self):
        window = cast(MainWindow, self.window)
        window.add_new_tab() # TODO: simulate clicking the button from "File" menubar option instead of invoking directly
        new_index = window.tabs.count() - 1
        with patch.object(QInputDialog, 'getText', return_value=(TESTING_TAB_NAME, True)):
            window.rename_tab(new_index)
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            window.close_tab(0)
        self.assertEqual(window.tabs.count(), 1)
        self.assertEqual(window.tabs.tabText(0), TESTING_TAB_NAME)

    # 2) change system params to DEFAULTs
    def test_02_change_system_params_to_defaults(self):
        window = cast(MainWindow, self.window)
        tab_widget = cast(WorkspaceTab, window.tabs.widget(0))
        sys_params = tab_widget.sys_params
        # Set to default values explicitly
        sys_params.field_type.setCurrentIndex(1)  # Polychromatic
        sys_params.wavelength.setValue(TESTING_WAVELENGTH_NM)
        sys_params.extension_x.setValue(TESTING_EXTENSION_X_MM)
        sys_params.extension_y.setValue(TESTING_EXTENSION_Y_MM)
        sys_params.resolution.setValue(TESTING_RESOLUTION_PX_PER_MM)
        self.assertEqual(sys_params.field_type.currentText(), "Polychromatic")
        self.assertEqual(sys_params.wavelength.value(), TESTING_WAVELENGTH_NM)
        self.assertEqual(sys_params.extension_x.value(), TESTING_EXTENSION_X_MM)
        self.assertEqual(sys_params.extension_y.value(), TESTING_EXTENSION_Y_MM)
        self.assertEqual(sys_params.resolution.value(), TESTING_RESOLUTION_PX_PER_MM)

    # 3) add A/L/S then delete one-by-one
    def test_03_add_three_then_delete_one_by_one(self):
        window = cast(MainWindow, self.window)
        vw = cast(WorkspaceTab, window.tabs.widget(0)).visualizer
        table = vw.table
        vw.add_aperture_btn.click()
        vw.add_lens_btn.click()
        vw.add_screen_btn.click()
        # Wait for the table to fully populate before proceeding
        self.assertTrue(wait_until(lambda: table.rowCount() == 4, 1000), "Table did not reach 4 rows after adding elements")
        self.assertEqual(table.rowCount(), 4)  # Strict Equality in element table rows!
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            for idx in range(3):
                table.clearSelection()
                QApplication.processEvents()
                table.setFocus()
                table.selectRow(1)
                QApplication.processEvents()
                prev_rows = table.rowCount()
                vw.del_btn.click()
                expected_rows = prev_rows - 1
                self.assertTrue(
                    wait_until(lambda e=expected_rows: table.rowCount() == e, 2000),
                    f"Expected {expected_rows} rows after deletion {idx + 1}, got {table.rowCount()}"
                )
                self.assertEqual(table.rowCount(), expected_rows)
        self.assertEqual(table.rowCount(), 1)

    # 4) add A/L/S then multi-delete by index
    def test_04_add_three_then_batch_delete(self):
        window = cast(MainWindow, self.window)
        vw = cast(WorkspaceTab, window.tabs.widget(0)).visualizer
        table = vw.table
        vw.add_aperture_btn.click()
        vw.add_lens_btn.click()
        vw.add_screen_btn.click()
        wait_until(lambda: table.rowCount() == 4, 300) # Strict equality!
        table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection) 
        table.clearSelection()
        table.selectRow(1)
        table.selectRow(2)
        table.selectRow(3)
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            vw.del_btn.click()
        self.assertEqual(table.rowCount(), 1)

    # 5) add aperture and set properties
    def test_05_add_aperture_rename_distance_image(self):
        window = cast(MainWindow, self.window)
        vw = cast(WorkspaceTab, window.tabs.widget(0)).visualizer
        table = vw.table
        vw.add_aperture_btn.click()
        wait_until(lambda: table.rowCount() == 2, 500)
        tmp_row = table.rowCount() - 1
        set_name(table, tmp_row, "fzpelem")
        set_distance(table, tmp_row, 0.01)
        set_aperture_image_path(table, tmp_row, os.path.join("aperatures", "20250320 00_11_58 manual pattern.png"))
        aperture_row = find_row_by_name(table, "fzpelem")
        self.assertEqual(aperture_row, 1) # Strict equality!
        self.assertEqual(cast(QComboBox, table.cellWidget(aperture_row, 1)).currentText(), 'Aperture')
        self.assertAlmostEqual(cast(QDoubleSpinBox, table.cellWidget(aperture_row, 2)).value(), 0.01, places=3)

    # 6) add lens and set properties
    def test_06_add_lens_rename_distance_focus(self):
        window = cast(MainWindow, self.window)
        vw = cast(WorkspaceTab, window.tabs.widget(0)).visualizer
        table = vw.table
        vw.add_lens_btn.click()
        wait_until(lambda: table.rowCount() == 2, 500) # Table gets reset between tests
        tmp_row = table.rowCount() - 1
        set_name(table, tmp_row, "gyujto")
        set_distance(table, tmp_row, 3.0)
        lens_row = find_row_by_name(table, "gyujto")
        self.assertEqual(lens_row, 1) # Strict equality!
        lens_focus = table.cellWidget(lens_row, 3)
        self.assertIsInstance(lens_focus, QDoubleSpinBox)
        cast(QDoubleSpinBox, lens_focus).setValue(800.0)
        try:
            cast(QDoubleSpinBox, lens_focus).editingFinished.emit()
        except Exception:
            pass
        self.assertEqual(cast(QComboBox, table.cellWidget(lens_row, 1)).currentText(), 'Lens')
        self.assertAlmostEqual(cast(QDoubleSpinBox, table.cellWidget(lens_row, 2)).value(), 3.0, places=3)
        self.assertAlmostEqual(cast(QDoubleSpinBox, lens_focus).value(), 800.0, places=3) # But it is 800 mm! why does it fail this test?

    # 7) add screen lemezkep distance 0.01 not range
    def test_07_add_screen_rename_distance_small(self):
        window = cast(MainWindow, self.window)
        vw = cast(WorkspaceTab, window.tabs.widget(0)).visualizer
        table = vw.table
        vw.add_screen_btn.click()
        wait_until(lambda: table.rowCount() == 2, 500)
        tmp_row = table.rowCount() - 1
        set_name(table, tmp_row, "lemezkep")
        set_distance(table, tmp_row, 0.01)
        screen_row = find_row_by_name(table, "lemezkep")
        self.assertEqual(screen_row, 1)
        self.assertEqual(cast(QComboBox, table.cellWidget(screen_row, 1)).currentText(), 'Screen')
        self.assertAlmostEqual(cast(QDoubleSpinBox, table.cellWidget(screen_row, 2)).value(), 0.01, places=3)

    # 8) add screen longitude distance from 1 to 100 step 15
    def test_08_add_screen_rename_distance_far(self):
        from PyQt6.QtWidgets import QSpinBox  # local import to avoid changing globals
        window = cast(MainWindow, self.window)
        vw = cast(WorkspaceTab, window.tabs.widget(0)).visualizer
        table = vw.table
        vw.add_screen_btn.click()
        self.assertTrue(wait_until(lambda: table.rowCount() == 2, 500))
        tmp_row = table.rowCount() - 1
        set_name(table, tmp_row, "lencsekep")
        set_screen_range(table, tmp_row, True, start_val=1.0, end_val=100.0, steps=15) # does not set to: distance properly

        screen_row = find_row_by_name(table, "lencsekep")
        self.assertEqual(screen_row, 1)

        # Check each cell
        # Column 0: name
        name_w = table.cellWidget(screen_row, 0)
        self.assertIsInstance(name_w, QLineEdit)
        self.assertEqual(cast(QLineEdit, name_w).text(), "lencsekep")

        # Column 1: type
        type_w = table.cellWidget(screen_row, 1)
        self.assertIsInstance(type_w, QComboBox)
        self.assertEqual(cast(QComboBox, type_w).currentText(), "Screen")

        # Column 2: distance range (From/To)
        dist_cell = table.cellWidget(screen_row, 2)
        self.assertIsInstance(dist_cell, QWidget)
        dist_spins = cast(QWidget, dist_cell).findChildren(QDoubleSpinBox)
        self.assertGreaterEqual(len(dist_spins), 2)
        self.assertAlmostEqual(dist_spins[0].value(), 1.0, places=3)
        self.assertAlmostEqual(dist_spins[1].value(), 100.0, places=3)

        # Column 3: range enabled + steps
        val_cell = table.cellWidget(screen_row, 3)
        self.assertIsNotNone(val_cell)
        chk = cast(QWidget, val_cell).findChild(QCheckBox)
        self.assertIsNotNone(chk)
        self.assertTrue(cast(QCheckBox, chk).isChecked())
        steps_spin = cast(QWidget, val_cell).findChild(QSpinBox)
        self.assertIsNotNone(steps_spin)
        self.assertEqual(cast(QSpinBox, steps_spin).value(), 15)

    # 9) advanced reordering test
    def test_09_advanced_reordering(self):
        window = cast(MainWindow, self.window)
        vw = cast(WorkspaceTab, window.tabs.widget(0)).visualizer
        table = vw.table

        def get_order():
            names = []
            for r in range(1, table.rowCount()):
                w = table.cellWidget(r, 0)
                if isinstance(w, QLineEdit):
                    names.append(cast(QLineEdit, w).text())
            return names

        # Build sequence A1, A2, L1, L2, S1, S2
        vw.add_aperture_btn.click()
        self.assertTrue(wait_until(lambda: table.rowCount() == 2, 500))
        set_name(table, 1, "A1")

        vw.add_aperture_btn.click()
        self.assertTrue(wait_until(lambda: table.rowCount() == 3, 500))
        set_name(table, 2, "A2")

        vw.add_lens_btn.click()
        self.assertTrue(wait_until(lambda: table.rowCount() == 4, 500))
        set_name(table, 3, "L1")

        vw.add_lens_btn.click()
        self.assertTrue(wait_until(lambda: table.rowCount() == 5, 500))
        set_name(table, 4, "L2")

        vw.add_screen_btn.click()
        self.assertTrue(wait_until(lambda: table.rowCount() == 6, 500))
        set_name(table, 5, "S1")

        vw.add_screen_btn.click()
        self.assertTrue(wait_until(lambda: table.rowCount() == 7, 500))
        set_name(table, 6, "S2")

        # Initial order
        self.assertEqual(get_order(), ["A1", "A2", "L1", "L2", "S1", "S2"])

        # set A1 dist to 15
        set_distance(table, find_row_by_name(table, "A1"), 15.0)
        self.assertTrue(wait_until(lambda: get_order() == ["A1", "A2", "L1", "L2", "S1", "S2"], 500))
        self.assertEqual(get_order(), ["A1", "A2", "L1", "L2", "S1", "S2"])

        # set A1 dist to 100
        set_distance(table, find_row_by_name(table, "A1"), 100.0)
        self.assertTrue(wait_until(lambda: get_order() == ["A2", "L1", "L2", "S1", "S2", "A1"], 500))
        self.assertEqual(get_order(), ["A2", "L1", "L2", "S1", "S2", "A1"])

        # set A1 dist to 60 (ties with S2 -> expect after S2 due to stable rule)
        set_distance(table, find_row_by_name(table, "A1"), 60.0)
        self.assertTrue(wait_until(lambda: get_order() == ["A2", "L1", "L2", "S1", "S2", "A1"], 500))
        self.assertEqual(get_order(), ["A2", "L1", "L2", "S1", "S2", "A1"])

        # set L1 dist to 0.01
        set_distance(table, find_row_by_name(table, "L1"), 0.01)
        self.assertTrue(wait_until(lambda: get_order() == ["L1", "A2", "L2", "S1", "S2", "A1"], 500))
        self.assertEqual(get_order(), ["L1", "A2", "L2", "S1", "S2", "A1"])

        # set A2 dist to 0.01 (equal to L1 -> expect after L1)
        set_distance(table, find_row_by_name(table, "A2"), 0.01)
        self.assertTrue(wait_until(lambda: get_order() == ["L1", "A2", "L2", "S1", "S2", "A1"], 500))
        self.assertEqual(get_order(), ["L1", "A2", "L2", "S1", "S2", "A1"])

        # set L1 dist to 1
        set_distance(table, find_row_by_name(table, "L1"), 1.0)
        self.assertTrue(wait_until(lambda: get_order() == ["A2", "L1", "L2", "S1", "S2", "A1"], 500))
        self.assertEqual(get_order(), ["A2", "L1", "L2", "S1", "S2", "A1"])

        # set L1 dist to 0.01 (equal to A2 -> expect after A2)
        set_distance(table, find_row_by_name(table, "L1"), 0.01)
        self.assertTrue(wait_until(lambda: get_order() == ["A2", "L1", "L2", "S1", "S2", "A1"], 500))
        self.assertEqual(get_order(), ["A2", "L1", "L2", "S1", "S2", "A1"])

        # set S1 dist to 60 (equal to S2/A1)
        set_distance(table, find_row_by_name(table, "S1"), 60.0)
        self.assertTrue(wait_until(lambda: get_order() == ["A2", "L1", "L2", "S1", "S2", "A1"], 500))
        self.assertEqual(get_order(), ["A2", "L1", "L2", "S1", "S2", "A1"])

        # delete S2
        s2_row = find_row_by_name(table, "S2")
        table.clearSelection()
        table.selectRow(s2_row)
        from PyQt6.QtWidgets import QMessageBox as _QMB
        with patch.object(_QMB, 'question', return_value=_QMB.StandardButton.Yes):
            vw.del_btn.click()
        self.assertTrue(wait_until(lambda: get_order() == ["A2", "L1", "L2", "S1", "A1"], 500))
        self.assertEqual(get_order(), ["A2", "L1", "L2", "S1", "A1"])

        # set A2 type to screen; verify is_range is False
        a2_row = find_row_by_name(table, "A2")
        type_w = table.cellWidget(a2_row, 1)
        self.assertIsInstance(type_w, QComboBox)
        cast(QComboBox, type_w).setCurrentText("Screen")
        # Reacquire row after refresh
        a2_row = find_row_by_name(table, "A2")
        self.assertEqual(cast(QComboBox, table.cellWidget(a2_row, 1)).currentText(), "Screen")
        val_cell = table.cellWidget(a2_row, 3)
        self.assertIsNotNone(val_cell)
        chk = cast(QWidget, val_cell).findChild(QCheckBox)
        self.assertIsNotNone(chk)
        self.assertFalse(cast(QCheckBox, chk).isChecked())

        # select L1, L2, S1 and delete
        from PyQt6.QtWidgets import QAbstractItemView as _QAI
        table.setSelectionMode(_QAI.SelectionMode.MultiSelection)
        for nm in ("L1", "L2", "S1"):
            r = find_row_by_name(table, nm)
            table.selectRow(r)
        with patch.object(_QMB, 'question', return_value=_QMB.StandardButton.Yes):
            vw.del_btn.click()
        # remaining order and types
        self.assertEqual(get_order(), ["A2", "A1"])
        self.assertEqual(cast(QComboBox, table.cellWidget(find_row_by_name(table, "A2"), 1)).currentText(), "Screen")
        self.assertEqual(cast(QComboBox, table.cellWidget(find_row_by_name(table, "A1"), 1)).currentText(), "Aperture")

    # 10) load Scene_1 and verify params/elements
    def test_10_load_scene_1_and_verify(self):
        window = cast(MainWindow, self.window)
        workdir = os.path.join(os.getcwd(), "workspaces")
        scene1_path = os.path.join(workdir, "Scene_1_hand.json") # Load a pre-saved scene - known good content
        sys_params = {
            'field_type': 'Monochromatic',
            'wavelength_nm': float(TESTING_WAVELENGTH_NM),
            'extent_x_mm': float(TESTING_EXTENSION_X_MM),
            'extent_y_mm': float(TESTING_EXTENSION_Y_MM),
            'resolution_px_per_mm': float(TESTING_RESOLUTION_PX_PER_MM),
        }
        elements = [
            { 'name': 'white', 'type': 'Aperture', 'distance_mm': 0.01, 'aperture_path': os.path.join('aperatures', 'white.png') },
            { 'name': 'fokusz', 'type': 'Lens', 'distance_mm': 0.01, 'focal_length_mm': 30.0 },
            { 'name': 'initial', 'type': 'Screen', 'distance_mm': 0.01, 'is_range': False },
            { 'name': 'longitudinal', 'type': 'Screen', 'distance_mm': 1.0, 'is_range': True, 'range_end_mm': 100.0, 'steps': 15 },
        ]
        with patch('PyQt6.QtWidgets.QFileDialog.getOpenFileName', return_value=(scene1_path, '')):
            window.load_workspace()
        # Current tab should be Scene_1_hand
        self.assertEqual(window.tabs.tabText(window.tabs.currentIndex()), 'Scene_1_hand')
        tab_widget = cast(WorkspaceTab, window.tabs.currentWidget())
        # Verify system params
        sp = tab_widget.sys_params
        self.assertEqual(sp.field_type.currentText(), sys_params['field_type'])
        self.assertAlmostEqual(sp.wavelength.value(), sys_params['wavelength_nm'], places=3)
        self.assertAlmostEqual(sp.extension_x.value(), sys_params['extent_x_mm'], places=3)
        self.assertAlmostEqual(sp.extension_y.value(), sys_params['extent_y_mm'], places=3)
        self.assertAlmostEqual(sp.resolution.value(), sys_params['resolution_px_per_mm'], places=3)
        # Verify elements by name and attributes
        table = tab_widget.visualizer.table
        # white aperture
        r = find_row_by_name(table, 'white')
        self.assertEqual(r, 1)
        self.assertEqual(cast(QComboBox, table.cellWidget(r, 1)).currentText(), 'Aperture')
        self.assertAlmostEqual(cast(QDoubleSpinBox, table.cellWidget(r, 2)).value(), 0.01, places=3)
        # TODO: check aperture image path
        # fokusz lens
        r = find_row_by_name(table, 'fokusz')
        self.assertEqual(r, 2)
        self.assertEqual(cast(QComboBox, table.cellWidget(r, 1)).currentText(), 'Lens')
        self.assertAlmostEqual(cast(QDoubleSpinBox, table.cellWidget(r, 2)).value(), 0.01, places=3)
        lens_focus = table.cellWidget(r, 3)
        self.assertIsInstance(lens_focus, QDoubleSpinBox)
        self.assertAlmostEqual(cast(QDoubleSpinBox, lens_focus).value(), 30.0, places=3)
        # initial screen
        r = find_row_by_name(table, 'initial')
        self.assertEqual(r, 3)
        self.assertEqual(cast(QComboBox, table.cellWidget(r, 1)).currentText(), 'Screen')
        self.assertAlmostEqual(cast(QDoubleSpinBox, table.cellWidget(r, 2)).value(), 0.01, places=3)
        val_cell = table.cellWidget(r, 3)
        self.assertIsNotNone(val_cell)
        rc = cast(QWidget, val_cell).findChild(QCheckBox)
        self.assertIsNotNone(rc)
        self.assertFalse(cast(QCheckBox, rc).isChecked())
        # longitudinal screen (range)
        r = find_row_by_name(table, 'longitudinal')
        self.assertEqual(r, 4)
        self.assertEqual(cast(QComboBox, table.cellWidget(r, 1)).currentText(), 'Screen')
        val_cell = table.cellWidget(r, 3)
        self.assertIsNotNone(val_cell)
        rc = cast(QWidget, val_cell).findChild(QCheckBox)
        self.assertIsNotNone(rc)
        self.assertTrue(cast(QCheckBox, rc).isChecked())
        # Verify From/To spins
        dist_cell = table.cellWidget(r, 2)
        spins = []
        if isinstance(dist_cell, QWidget):
            spins = dist_cell.findChildren(QDoubleSpinBox)
        self.assertGreaterEqual(len(spins), 2)
        self.assertAlmostEqual(spins[0].value(), 1.0, places=3)
        self.assertAlmostEqual(spins[1].value(), 100.0, places=3)

    # 11) build and save Generated_1, compare with Scene_2
    def test_11_generate_and_save_compare_to_scene_2(self):
        window = cast(MainWindow, self.window)
        # Switch back to first tab (Testing) to build there
        window.tabs.setCurrentIndex(0)
        tab_widget = cast(WorkspaceTab, window.tabs.currentWidget())
        vw = tab_widget.visualizer
        table = vw.table
        # Clear elements
        vw.head.next = None
        vw.refresh_table()
        # Add aperture 'white' d=0.01
        vw.add_aperture_btn.click()
        wait_until(lambda: table.rowCount() == 2, 300)
        r = table.rowCount() - 1
        set_name(table, r, 'white')
        set_distance(table, r, 0.01)
        set_aperture_image_path(table, r, os.path.join('aperatures', 'white.png'))
        # Add lens 'fokusz' d=0.01 f=30
        vw.add_lens_btn.click()
        wait_until(lambda: table.rowCount() == 3, 300)
        r = table.rowCount() - 1
        set_name(table, r, 'fokusz')
        set_distance(table, r, 0.01)
        lf = table.cellWidget(find_row_by_name(table, 'fokusz'), 3)
        self.assertIsInstance(lf, QDoubleSpinBox)
        cast(QDoubleSpinBox, lf).setValue(30.0)
        try:
            cast(QDoubleSpinBox, lf).editingFinished.emit()
        except Exception:
            pass
        # Add screen 'initial' d=0.01
        vw.add_screen_btn.click()
        wait_until(lambda: table.rowCount() == 4, 300)
        r = table.rowCount() - 1
        set_name(table, r, 'initial')
        set_distance(table, r, 0.01)
        # Add screen 'longitudinal' range 1..100 steps 15
        vw.add_screen_btn.click()
        wait_until(lambda: table.rowCount() == 5, 300)
        r = table.rowCount() - 1
        set_name(table, r, 'longitudinal')
        set_screen_range(table, r, True, start_val=1.0, end_val=100.0, steps=15)
        # Rename workspace to Generated_1 and save
        with patch.object(QInputDialog, 'getText', return_value=("Generated_1", True)):
            window.rename_tab(window.tabs.currentIndex())
        save_path = os.path.join(os.getcwd(), 'workspaces', 'Generated_1.json')
        # Ensure old file does not trigger overwrite dialog (and auto-answer any modal dialogs)
        try:
            os.remove(save_path)
        except FileNotFoundError:
            pass
        with patch('PyQt6.QtWidgets.QFileDialog.getSaveFileName', return_value=(save_path, '')), \
             patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes), \
             patch.object(QMessageBox, 'information', return_value=QMessageBox.StandardButton.Ok):
            window.save_workspace()
        # Build expected Scene_2 and write
        scene2_path = os.path.join(os.getcwd(), 'workspaces', 'Scene_2.json')
        sys_params = {
            'field_type': 'Monochromatic',
            'wavelength_nm': float(DEFAULT_WAVELENGTH_NM),
            'extent_x_mm': float(DEFAULT_EXTENSION_X_MM),
            'extent_y_mm': float(DEFAULT_EXTENSION_Y_MM),
            'resolution_px_per_mm': float(DEFAULT_RESOLUTION_PX_PER_MM),
        }
        elements = [
            { 'name': 'white', 'type': 'Aperture', 'distance_mm': 0.01, 'aperture_path': os.path.join('aperatures', 'white.png') },
            { 'name': 'fokusz', 'type': 'Lens', 'distance_mm': 0.01, 'focal_length_mm': 30.0 },
            { 'name': 'initial', 'type': 'Screen', 'distance_mm': 0.01, 'is_range': False },
            { 'name': 'longitudinal', 'type': 'Screen', 'distance_mm': 1.0, 'is_range': True, 'range_end_mm': 100.0, 'steps': 15 },
        ]
        #write_scene_json(scene2_path, 'Generated_1', sys_params, elements)
        # Load both and compare relevant sections
        with open(save_path, 'r', encoding='utf-8') as f:
            saved = json.load(f)
        with open(scene2_path, 'r', encoding='utf-8') as f:
            expected = json.load(f)
        self.assertEqual(saved.get('workspace_name'), expected.get('workspace_name'))
        self.assertEqual(saved.get('system_params'), expected.get('system_params'))
        # Compare elements ignoring order by mapping name->dict trimmed
        def _trim(e: dict):
            out = {k: v for k, v in e.items() if k in {'name','type','distance_mm','aperture_path','focal_length_mm','is_range','range_end_mm','steps'}}
            return out
        saved_map = {e.get('name'): _trim(e) for e in saved.get('elements', [])}
        exp_map = {e.get('name'): _trim(e) for e in expected.get('elements', [])}
        self.assertEqual(saved_map, exp_map)

    # 12) click solve under screen
    def test_12_click_solve_button_under_screen(self):
        window = cast(MainWindow, self.window)
        # Work on current tab
        tab_widget = cast(WorkspaceTab, window.tabs.currentWidget())
        solve_btn = getattr(tab_widget, 'screen_img').solve_button
        solve_btn.click()
        self.assertTrue(wait_until(lambda: solve_btn.isEnabled(), 5000))


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(GUITestCase)
    unittest.TextTestRunner(verbosity=0).run(suite)
