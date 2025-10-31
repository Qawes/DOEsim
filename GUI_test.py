import os
import sys
import unittest
import time
from unittest.mock import patch
from typing import Optional, cast

TESTING_TAB_NAME = "Testing"
TESTING_WAVELENGTH_NM = 440
TESTING_EXTENSIONX_MM = 6
TESTING_EXTENSIONY_MM = 6
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
)
from PyQt6.QtCore import Qt

from main_window import MainWindow, WorkspaceTab

# --- Concise test result logging (per-test in tearDown) ---
# Note: We avoid custom unittest result classes to keep type checkers happy.

def wait_until(predicate, timeout_ms=5000, step_ms=25):
    """Process events and wait until predicate() returns True or times out."""
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
        # Light Source row is not a QLineEdit; skip
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
    spin = table.cellWidget(row, 2)
    assert isinstance(spin, QDoubleSpinBox)
    spin.setValue(new_dist)
    try:
        spin.editingFinished.emit()
    except Exception:
        pass


def set_aperture_image_path(table, row: int, path: str):
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


def snapshot_elements(table):
    """Serialize rows > 0 into a list of dicts: type, name, distance, and type-dependent fields."""
    elements = []
    row_count = table.rowCount()
    for r in range(1, row_count):
        name_w = table.cellWidget(r, 0)
        type_w = table.cellWidget(r, 1)
        dist_w = table.cellWidget(r, 2)
        if not isinstance(name_w, QLineEdit) or not isinstance(type_w, QComboBox) or not isinstance(dist_w, QDoubleSpinBox):
            # Skip malformed rows
            continue
        elem_type = type_w.currentText()
        entry = {
            'type': elem_type,
            'name': name_w.text(),
            'distance': float(dist_w.value()),
            'focal_length': None,
            'aperture_path': None,
            'is_range': None,
        }
        # Value column
        val_cell = table.cellWidget(r, 3)
        if elem_type == 'Lens' and isinstance(val_cell, QDoubleSpinBox):
            entry['focal_length'] = float(val_cell.value())
        elif elem_type == 'Aperture' and val_cell is not None:
            line = val_cell.findChild(QLineEdit)
            if isinstance(line, QLineEdit):
                entry['aperture_path'] = line.text()
        elif elem_type == 'Screen' and val_cell is not None:
            from PyQt6.QtWidgets import QCheckBox
            chk = val_cell.findChild(QCheckBox)
            if chk is not None:
                entry['is_range'] = bool(chk.isChecked())
        elements.append(entry)
    return elements


def _canon(elem: dict) -> str:
    """Canonical string for comparison independent of order and minor float noise."""
    t = elem.get('type', '')
    n = elem.get('name', '')
    d = float(elem.get('distance', 0.0))
    f = elem.get('focal_length')
    a = elem.get('aperture_path')
    r = elem.get('is_range')
    d_s = f"{d:.6f}"
    f_s = "" if f is None else f"{float(f):.6f}"
    a_s = "" if a is None else str(a)
    r_s = "" if r is None else ("1" if r else "0")
    return f"{t}|{n}|{d_s}|f={f_s}|ap={a_s}|range={r_s}"


def normalize_elements(elems: list[dict]) -> list[str]:
    return sorted(_canon(e) for e in elems)


def expected_from_base(base: list[dict], add: list[dict] | None = None, remove_names: list[str] | None = None) -> list[dict]:
    import copy
    out = copy.deepcopy(base)
    if add:
        out.extend(add)
    if remove_names:
        out = [e for e in out if e.get('name') not in set(remove_names)]
    return out


def make_elem(elem_type: str, name: str, distance: float, focal_length: float | None = None, aperture_path: str | None = None, is_range: bool | None = None) -> dict:
    return {
        'type': elem_type,
        'name': name,
        'distance': float(distance),
        'focal_length': focal_length,
        'aperture_path': aperture_path,
        'is_range': is_range,
    }

def clear_all_elements(window: MainWindow):
    """Clear all visualizer elements (keep Light Source) without dialogs."""
    try:
        tab = window.tabs.widget(0)
        tab_widget = cast(WorkspaceTab, tab)
        visualizer = tab_widget.visualizer
        # Reset linked list to only head (Light Source)
        visualizer.head.next = None
        visualizer.refresh_table()
    except Exception:
        pass

class GUITestCase(unittest.TestCase):
    app: Optional[QApplication] = None
    window: Optional[MainWindow] = None
    _orig_engine: Optional[object] = None
    _has_failures: bool = False

    @classmethod
    def setUpClass(cls):
        # Create a single QApplication for all tests
        existing_app = QApplication.instance()
        if existing_app is None:
            existing_app = QApplication(sys.argv)
        cls.app = cast(QApplication, existing_app)
        # Create the main window
        cls.window = MainWindow()
        cls.window.show()
        # Wait briefly for the window to initialize
        wait_until(lambda: True, 300)  # process a few events

        # Speed up tests by monkey-patching the engine calculation to a fast stub
        import engine
        import numpy as np

        cls._orig_engine = engine.calculate_screen_images

        def _fast_calc_stub(**kwargs):
            # Return a small, valid RGB image quickly
            return np.zeros((64, 64, 3), dtype=np.uint8)

        engine.calculate_screen_images = _fast_calc_stub

    @classmethod
    def tearDownClass(cls):
        # Restore engine function
        try:
            import engine
            if cls._orig_engine is not None:
                engine.calculate_screen_images = cls._orig_engine  # type: ignore[assignment]
        except Exception:
            pass
        # Only close window if all tests passed
        if not cls._has_failures and cls.window is not None:
            cls.window.close()

    def tearDown(self):
        # Track failures/errors to decide whether to keep window open and print concise status
        label = getattr(self, "_testMethodName", self.__class__.__name__)
        if label.startswith("test_"):
            label = label[len("test_"):]
        label = label.replace("_", " ")
        status = "PASS"
        outcome = getattr(self, "_outcome", None)
        try:
            result = getattr(outcome, "result", None)
            if result and any(t is self for t, _ in getattr(result, "failures", [])):
                status = "FAIL"
            elif result and any(t is self for t, _ in getattr(result, "errors", [])):
                status = "ERROR"
        except Exception:
            pass
        if status != "PASS":
            GUITestCase._has_failures = True
            # If a table-modifying test failed, clear the table to avoid cascading failures
            method_name = getattr(self, "_testMethodName", "")
            table_mod_tests = {
                "test_04_add_three_then_delete_one_by_one",
                "test_05_add_three_then_batch_delete",
                "test_06_add_aperture_rename_distance_image",
                "test_07_add_lens_rename_distance_focus",
                "test_08_add_screen_rename_distance_small",
                "test_09_add_screen_rename_distance_far",
                "test_10_add_screen_rename_distance_and_delete_other",
            }
            if method_name in table_mod_tests and isinstance(self.window, MainWindow):
                clear_all_elements(self.window)
        print(f"[{status}] {label}")

    def test_01_create_and_rename_workspace(self):
        window = cast(MainWindow, self.window)
        window.add_new_tab()
        new_index = window.tabs.count() - 1
        with patch.object(QInputDialog, 'getText', return_value=(TESTING_TAB_NAME, True)):
            window.rename_tab(new_index)
        self.assertEqual(window.tabs.tabText(new_index), TESTING_TAB_NAME)

    def test_02_close_old_default_workspace(self):
        window = cast(MainWindow, self.window)
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            window.close_tab(0)
        self.assertEqual(window.tabs.count(), 1)
        self.assertEqual(window.tabs.tabText(0), TESTING_TAB_NAME)

    def test_03_change_system_parameters(self):
        window = cast(MainWindow, self.window)
        tab = window.tabs.widget(0)
        tab_widget = cast(WorkspaceTab, tab)
        sys_params = tab_widget.sys_params
        sys_params.wavelength.setValue(TESTING_WAVELENGTH_NM)
        sys_params.extension_x.setValue(TESTING_EXTENSIONX_MM)
        sys_params.extension_y.setValue(TESTING_EXTENSIONY_MM)
        sys_params.resolution.setValue(TESTING_RESOLUTION_PX_PER_MM)
        self.assertEqual(sys_params.wavelength.value(), TESTING_WAVELENGTH_NM)
        self.assertEqual(sys_params.extension_x.value(), TESTING_EXTENSIONX_MM)
        self.assertEqual(sys_params.extension_y.value(), TESTING_EXTENSIONY_MM)
        self.assertEqual(sys_params.resolution.value(), TESTING_RESOLUTION_PX_PER_MM)

    def test_04_add_three_then_delete_one_by_one(self):
        window = cast(MainWindow, self.window)
        tab_widget = cast(WorkspaceTab, window.tabs.widget(0))
        visualizer = tab_widget.visualizer
        table = visualizer.table
        base = snapshot_elements(table)
        visualizer.add_aperture_btn.click()
        visualizer.add_lens_btn.click()
        visualizer.add_screen_btn.click()
        # Ensure the rows are present (row 0 is Light Source)
        self.assertGreaterEqual(table.rowCount(), 4)

        # One-by-one delete rows > 0 and verify remaining types and counts
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            for _ in range(3):
                table.clearSelection()
                table.selectRow(1)
                visualizer.del_btn.click()
                wait_until(lambda: True, 50)
        self.assertEqual(table.rowCount(), 1)
        # Compare final state to base (superimposition result)
        actual = snapshot_elements(table)
        expected = expected_from_base(base)  # deletes restore base
        self.assertEqual(normalize_elements(actual), normalize_elements(expected))

    def test_05_add_three_then_batch_delete(self):
        window = cast(MainWindow, self.window)
        tab_widget = cast(WorkspaceTab, window.tabs.widget(0))
        visualizer = tab_widget.visualizer
        table = visualizer.table
        base = snapshot_elements(table)
        visualizer.add_aperture_btn.click()
        visualizer.add_lens_btn.click()
        visualizer.add_screen_btn.click()
        wait_until(lambda: True, 50)
        self.assertGreaterEqual(table.rowCount(), 4)
        table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        table.clearSelection()
        table.selectRow(1)
        table.selectRow(2)
        table.selectRow(3)
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            visualizer.del_btn.click()
        actual = snapshot_elements(table)
        expected = expected_from_base(base)
        self.assertEqual(normalize_elements(actual), normalize_elements(expected))

    def test_06_add_aperture_rename_distance_image(self):
        window = cast(MainWindow, self.window)
        tab_widget = cast(WorkspaceTab, window.tabs.widget(0))
        visualizer = tab_widget.visualizer
        table = visualizer.table
        base = snapshot_elements(table)
        visualizer.add_aperture_btn.click()
        wait_until(lambda: table.rowCount() == 2, 500)
        r = 1
        set_name(table, r, "fzpelem")
        set_distance(table, r, 0.01)
        set_aperture_image_path(table, r, os.path.join("aperatures", "20250320 00_11_58 manual pattern.png"))
        actual = snapshot_elements(table)
        expected = expected_from_base(base, add=[make_elem('Aperture', 'fzpelem', 0.01, aperture_path=os.path.join('aperatures', '20250320 00_11_58 manual pattern.png'))])
        self.assertEqual(normalize_elements(actual), normalize_elements(expected))

    def test_07_add_lens_rename_distance_focus(self):
        window = cast(MainWindow, self.window)
        tab_widget = cast(WorkspaceTab, window.tabs.widget(0))
        visualizer = tab_widget.visualizer
        table = visualizer.table
        base = snapshot_elements(table)
        visualizer.add_lens_btn.click()
        wait_until(lambda: table.rowCount() == 3, 500)
        lens_row = table.rowCount() - 1
        set_name(table, lens_row, "gyujto")
        set_distance(table, lens_row, 3.0)
        lens_focus = table.cellWidget(lens_row, 3)
        assert isinstance(lens_focus, QDoubleSpinBox)
        lens_focus.setValue(800)
        try:
            lens_focus.editingFinished.emit()
        except Exception:
            pass
        actual = snapshot_elements(table)
        expected = expected_from_base(base, add=[make_elem('Lens', 'gyujto', 3.0, focal_length=800.0)])
        self.assertEqual(normalize_elements(actual), normalize_elements(expected))

    def test_08_add_screen_rename_distance_small(self):
        window = cast(MainWindow, self.window)
        tab_widget = cast(WorkspaceTab, window.tabs.widget(0))
        visualizer = tab_widget.visualizer
        table = visualizer.table
        base = snapshot_elements(table)
        visualizer.add_screen_btn.click()
        wait_until(lambda: table.rowCount() == 4, 500)
        screen_row = table.rowCount() - 1
        set_name(table, screen_row, "lemezkep")
        set_distance(table, screen_row, 0.01)
        actual = snapshot_elements(table)
        expected = expected_from_base(base, add=[make_elem('Screen', 'lemezkep', 0.01)])
        self.assertEqual(normalize_elements(actual), normalize_elements(expected))

    def test_09_add_screen_rename_distance_far(self):
        window = cast(MainWindow, self.window)
        tab_widget = cast(WorkspaceTab, window.tabs.widget(0))
        visualizer = tab_widget.visualizer
        table = visualizer.table
        base = snapshot_elements(table)
        visualizer.add_screen_btn.click()
        wait_until(lambda: table.rowCount() == 5, 500)
        screen2_row = table.rowCount() - 1
        set_name(table, screen2_row, "lencsekep")
        set_distance(table, screen2_row, 1000.0)
        actual = snapshot_elements(table)
        expected = expected_from_base(base, add=[make_elem('Screen', 'lencsekep', 1000.0)])
        self.assertEqual(normalize_elements(actual), normalize_elements(expected))

    def test_10_add_screen_rename_distance_and_delete_other(self):
        window = cast(MainWindow, self.window)
        tab_widget = cast(WorkspaceTab, window.tabs.widget(0))
        visualizer = tab_widget.visualizer
        table = visualizer.table
        base = snapshot_elements(table)
        visualizer.add_screen_btn.click()
        wait_until(lambda: table.rowCount() == 6, 500)
        screen3_row = table.rowCount() - 1
        set_name(table, screen3_row, "kep")
        set_distance(table, screen3_row, 1000.0)
        row_lencse = find_row_by_name(table, "lencsekep")
        self.assertGreaterEqual(row_lencse, 1)
        table.clearSelection()
        table.selectRow(row_lencse)
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            visualizer.del_btn.click()
        self.assertEqual(find_row_by_name(table, "lencsekep"), -1)
        actual = snapshot_elements(table)
        expected = expected_from_base(base, add=[make_elem('Screen', 'kep', 1000.0)], remove_names=['lencsekep'])
        self.assertEqual(normalize_elements(actual), normalize_elements(expected))

    def test_11_click_solve_button_under_screen(self):
        window = cast(MainWindow, self.window)
        tab_widget = cast(WorkspaceTab, window.tabs.widget(0))
        screen_container = getattr(tab_widget, "screen_img")
        solve_btn = screen_container.solve_button
        solve_btn.click()
        self.assertTrue(wait_until(lambda: solve_btn.isEnabled(), 5000))


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(GUITestCase)
    unittest.TextTestRunner(verbosity=0).run(suite)
