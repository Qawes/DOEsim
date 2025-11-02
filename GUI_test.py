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

'''
------------------------------------------------------
 Run tests in headless:

python -u GUI_test.py --headless

------------------------------------------------------
'''


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

# Import shared helpers
from components.helpers import (
    wait_until,
    find_row_by_name,
    set_name,
    set_distance,
    set_aperture_image_path,
    set_screen_range,
    ensure_dirs,
    step_spin_to_value,
    step_distance,
    select_row_and_wait,
    get_row_types,
    get_row_names,
)

from main_window import MainWindow, WorkspaceTab
from components.system_parameters import (
    DEFAULT_WAVELENGTH_NM,
    DEFAULT_EXTENSION_X_MM,
    DEFAULT_EXTENSION_Y_MM,
    DEFAULT_RESOLUTION_PX_PER_MM,
)

# --- Concise test result logging (per-test in tearDown) ---


class GUITestCase(unittest.TestCase):
    app: Optional[QApplication] = None
    window: Optional[MainWindow] = None
    _orig_engine: Optional[object] = None
    _has_failures: bool = False
    # Keep originals for all engines we patch
    _orig_engines: dict[str, object] = {}

    @classmethod
    def setUpClass(cls):
        ensure_dirs()
        # Create a single QApplication for all tests
        existing_app = QApplication.instance()
        if (existing_app is None):
            existing_app = QApplication(sys.argv)
        cls.app = cast(QApplication, existing_app)
        # Create the main window
        cls.window = MainWindow(force_single_workspace=True)
        cls.window.show()
        wait_until(lambda: True, 200)
        # Speed up tests by monkey-patching the engine calculation to a fast stub
        import numpy as np
        def _fast_calc_stub(**kwargs):
            return np.zeros((64, 64, 3), dtype=np.uint8)
        # Patch all supported engines
        try:
            import components.engine_diff_fwd as _edf
            cls._orig_engines['diff_fwd'] = _edf.calculate_screen_images
            _edf.calculate_screen_images = _fast_calc_stub  # type: ignore[assignment]
        except Exception:
            pass
        try:
            import components.engine_diff_rev as _edr
            cls._orig_engines['diff_rev'] = _edr.calculate_screen_images
            _edr.calculate_screen_images = _fast_calc_stub  # type: ignore[assignment]
        except Exception:
            pass
        try:
            import components.engine_bmp_rev as _ebr
            cls._orig_engines['bmp_rev'] = _ebr.calculate_screen_images
            _ebr.calculate_screen_images = _fast_calc_stub  # type: ignore[assignment]
        except Exception:
            pass
        print("\n")  # Newline before test logs

    @classmethod
    def tearDownClass(cls):
        # Restore patched engines
        try:
            if 'diff_fwd' in cls._orig_engines:
                import components.engine_diff_fwd as _edf
                _edf.calculate_screen_images = cls._orig_engines['diff_fwd']  # type: ignore[assignment]
        except Exception:
            pass
        try:
            if 'diff_rev' in cls._orig_engines:
                import components.engine_diff_rev as _edr
                _edr.calculate_screen_images = cls._orig_engines['diff_rev']  # type: ignore[assignment]
        except Exception:
            pass
        try:
            if 'bmp_rev' in cls._orig_engines:
                import components.engine_bmp_rev as _ebr
                _ebr.calculate_screen_images = cls._orig_engines['bmp_rev']  # type: ignore[assignment]
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

    # 3) single deletion sequence per spec
    def test_03_single_deletion(self):
        window = cast(MainWindow, self.window)
        vw = cast(WorkspaceTab, window.tabs.widget(0)).visualizer
        table = vw.table
        # Add A, A, L, L, S, S
        vw.add_aperture_btn.click()
        vw.add_aperture_btn.click()
        vw.add_lens_btn.click()
        vw.add_lens_btn.click()
        vw.add_screen_btn.click()
        vw.add_screen_btn.click()
        self.assertTrue(wait_until(lambda: table.rowCount() == 7, 1500), "Table did not reach 7 rows after adding elements")
        # Name them A1, A2, L1, L2, S1, S2 (rows 1..6)
        set_name(table, 1, "A1")
        set_name(table, 2, "A2")
        set_name(table, 3, "L1")
        set_name(table, 4, "L2")
        set_name(table, 5, "S1")
        set_name(table, 6, "S2")
        self.assertEqual(get_row_types(table), ["Aperture", "Aperture", "Lens", "Lens", "Screen", "Screen"])
        def _delete_by_name(nm: str):
            row = find_row_by_name(table, nm)
            self.assertNotEqual(row, -1, f"Row not found for element '{nm}'")
            table.clearSelection()
            table.selectRow(row)
            with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
                vw.del_btn.click()
        # delete A1 -> expect A, L, L, S, S (rowCount 6)
        _delete_by_name("A1")
        self.assertTrue(wait_until(lambda: table.rowCount() == 6, 1000))
        self.assertEqual(get_row_types(table), ["Aperture", "Lens", "Lens", "Screen", "Screen"])
        # delete S2 -> expect A, L, L, S (rowCount 5)
        _delete_by_name("S2")
        self.assertTrue(wait_until(lambda: table.rowCount() == 5, 1000))
        self.assertEqual(get_row_types(table), ["Aperture", "Lens", "Lens", "Screen"])
        # delete L1 -> expect A, L, S (rowCount 4)
        _delete_by_name("L1")
        self.assertTrue(wait_until(lambda: table.rowCount() == 4, 1000))
        self.assertEqual(get_row_types(table), ["Aperture", "Lens", "Screen"])
        # delete A2 -> expect L, S (rowCount 3)
        _delete_by_name("A2")
        self.assertTrue(wait_until(lambda: table.rowCount() == 3, 1000))
        self.assertEqual(get_row_types(table), ["Lens", "Screen"])
        # delete L2 -> expect S (rowCount 2)
        _delete_by_name("L2")
        self.assertTrue(wait_until(lambda: table.rowCount() == 2, 1000))
        self.assertEqual(get_row_types(table), ["Screen"])
        # delete S1 -> expect empty (rowCount 1)
        _delete_by_name("S1")
        self.assertTrue(wait_until(lambda: table.rowCount() == 1, 1000))
        self.assertEqual(get_row_types(table), [])

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
        # Ensure ordering [From, To]
        dist_spins = sorted(dist_spins, key=lambda s: s.geometry().x())
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
        self.assertEqual(get_row_names(table), ["A2", "A1"]) 
        self.assertEqual(cast(QComboBox, table.cellWidget(find_row_by_name(table, "A2"), 1)).currentText(), "Screen")
        self.assertEqual(cast(QComboBox, table.cellWidget(find_row_by_name(table, "A1"), 1)).currentText(), "Aperture")

    # 10) type-change naming sequence as specified
    def test_10_type_change_naming_sequence(self):
        window = cast(MainWindow, self.window)
        vw = cast(WorkspaceTab, window.tabs.widget(0)).visualizer
        table = vw.table

        def get_names():
            names = []
            for r in range(1, table.rowCount()):
                w = table.cellWidget(r, 0)
                if isinstance(w, QLineEdit):
                    names.append(cast(QLineEdit, w).text())
            return names

        # Create elements Aperture 1, Aperture 2, Lens 1, Screen 1, Screen 2 of types A, A, L, S, S
        vw.add_aperture_btn.click()
        self.assertTrue(wait_until(lambda: table.rowCount() == 2, 1000))
        set_name(table, 1, "Aperture 1")

        vw.add_aperture_btn.click()
        self.assertTrue(wait_until(lambda: table.rowCount() == 3, 1000))
        set_name(table, 2, "Aperture 2")

        vw.add_lens_btn.click()
        self.assertTrue(wait_until(lambda: table.rowCount() == 4, 1000))
        set_name(table, 3, "Lens 1")

        vw.add_screen_btn.click()
        self.assertTrue(wait_until(lambda: table.rowCount() == 5, 1000))
        set_name(table, 4, "Screen 1")

        vw.add_screen_btn.click()
        self.assertTrue(wait_until(lambda: table.rowCount() == 6, 1000))
        set_name(table, 5, "Screen 2")

        self.assertEqual(get_names(), ["Aperture 1", "Aperture 2", "Lens 1", "Screen 1", "Screen 2"])

        # change Lens 1 type to aperture, expect names unchanged
        row = find_row_by_name(table, "Lens 1")
        type_w = table.cellWidget(row, 1)
        self.assertIsInstance(type_w, QComboBox)
        cast(QComboBox, type_w).setCurrentText("Aperture")
        self.assertTrue(wait_until(lambda: get_names() == ["Aperture 1", "Aperture 2", "Lens 1", "Screen 1", "Screen 2"], 1000))
        self.assertEqual(get_names(), ["Aperture 1", "Aperture 2", "Lens 1", "Screen 1", "Screen 2"])

        # change Lens 1 type to screen, expect names unchanged
        row = find_row_by_name(table, "Lens 1")
        type_w = table.cellWidget(row, 1)
        self.assertIsInstance(type_w, QComboBox)
        cast(QComboBox, type_w).setCurrentText("Screen")
        self.assertTrue(wait_until(lambda: get_names() == ["Aperture 1", "Aperture 2", "Lens 1", "Screen 1", "Screen 2"], 1000))
        self.assertEqual(get_names(), ["Aperture 1", "Aperture 2", "Lens 1", "Screen 1", "Screen 2"])

        # change Aperture 2 type to lens -> expect Aperture 2 becomes Lens 2
        row = find_row_by_name(table, "Aperture 2")
        type_w = table.cellWidget(row, 1)
        self.assertIsInstance(type_w, QComboBox)
        cast(QComboBox, type_w).setCurrentText("Lens")
        self.assertTrue(wait_until(lambda: get_names() == ["Aperture 1", "Lens 2", "Lens 1", "Screen 1", "Screen 2"], 1500))
        self.assertEqual(get_names(), ["Aperture 1", "Lens 2", "Lens 1", "Screen 1", "Screen 2"])

        # change Lens 2 type to screen -> expect names unchanged
        row = find_row_by_name(table, "Lens 2")
        type_w = table.cellWidget(row, 1)
        self.assertIsInstance(type_w, QComboBox)
        cast(QComboBox, type_w).setCurrentText("Screen")
        self.assertTrue(wait_until(lambda: get_names() == ["Aperture 1", "Lens 2", "Lens 1", "Screen 1", "Screen 2"], 1500))
        self.assertEqual(get_names(), ["Aperture 1", "Lens 2", "Lens 1", "Screen 1", "Screen 2"])

        # change Screen 2 type to aperture -> expect Screen 2 becomes Aperture 2
        row = find_row_by_name(table, "Screen 2")
        type_w = table.cellWidget(row, 1)
        self.assertIsInstance(type_w, QComboBox)
        cast(QComboBox, type_w).setCurrentText("Aperture")
        self.assertTrue(wait_until(lambda: get_names() == ["Aperture 1", "Lens 2", "Lens 1", "Screen 1", "Aperture 2"], 1500))
        self.assertEqual(get_names(), ["Aperture 1", "Lens 2", "Lens 1", "Screen 1", "Aperture 2"])

        # check for types: aperture, screen, screen, screen, aperture (in the current name order)
        expected = {
            "Aperture 1": "Aperture",
            "Lens 2": "Screen",
            "Lens 1": "Screen",
            "Screen 1": "Screen",
            "Aperture 2": "Aperture",
        }
        for name in ["Aperture 1", "Lens 2", "Lens 1", "Screen 1", "Aperture 2"]:
            r = find_row_by_name(table, name)
            self.assertNotEqual(r, -1)
            t = table.cellWidget(r, 1)
            self.assertIsInstance(t, QComboBox)
            self.assertEqual(cast(QComboBox, t).currentText(), expected[name])

        # set Aperture 1 name to Lens 1 -> expect conflict error and names unchanged
        a1_row = find_row_by_name(table, "Aperture 1")
        set_name(table, a1_row, "Lens 1")
        QApplication.processEvents()
        # final names should remain the same and contain both Aperture 1 and Lens 1
        self.assertEqual(get_names(), ["Aperture 1", "Lens 2", "Lens 1", "Screen 1", "Aperture 2"])

    # 11) advanced reordering via spinbox steps (no direct setValue)
    def test_11_advanced_reordering_via_steps(self):
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
        self.assertTrue(wait_until(lambda: table.rowCount() == 2, 1000))
        set_name(table, 1, "A1")

        vw.add_aperture_btn.click()
        self.assertTrue(wait_until(lambda: table.rowCount() == 3, 1000))
        set_name(table, 2, "A2")

        vw.add_lens_btn.click()
        self.assertTrue(wait_until(lambda: table.rowCount() == 4, 1000))
        set_name(table, 3, "L1")

        vw.add_lens_btn.click()
        self.assertTrue(wait_until(lambda: table.rowCount() == 5, 1000))
        set_name(table, 4, "L2")

        vw.add_screen_btn.click()
        self.assertTrue(wait_until(lambda: table.rowCount() == 6, 1000))
        set_name(table, 5, "S1")

        vw.add_screen_btn.click()
        self.assertTrue(wait_until(lambda: table.rowCount() == 7, 1000))
        set_name(table, 6, "S2")

        # Initial order
        self.assertEqual(get_order(), ["A1", "A2", "L1", "L2", "S1", "S2"])

        # set A1 dist to 15 via steps
        step_distance(table, find_row_by_name(table, "A1"), 15.0)
        self.assertTrue(wait_until(lambda: get_order() == ["A1", "A2", "L1", "L2", "S1", "S2"], 1000))
        self.assertEqual(get_order(), ["A1", "A2", "L1", "L2", "S1", "S2"])

        # set A1 dist to 100 via steps
        step_distance(table, find_row_by_name(table, "A1"), 100.0)
        self.assertTrue(wait_until(lambda: get_order() == ["A2", "L1", "L2", "S1", "S2", "A1"], 2000))
        self.assertEqual(get_order(), ["A2", "L1", "L2", "S1", "S2", "A1"])

        # set A1 dist to 60 (ties with S2 -> expect after S2)
        step_distance(table, find_row_by_name(table, "A1"), 60.0)
        self.assertTrue(wait_until(lambda: get_order() == ["A2", "L1", "L2", "S1", "S2", "A1"], 1000))
        self.assertEqual(get_order(), ["A2", "L1", "L2", "S1", "S2", "A1"])

        # set L1 dist to 0.01
        step_distance(table, find_row_by_name(table, "L1"), 0.01)
        self.assertTrue(wait_until(lambda: get_order() == ["L1", "A2", "L2", "S1", "S2", "A1"], 2000))
        self.assertEqual(get_order(), ["L1", "A2", "L2", "S1", "S2", "A1"])

        # set A2 dist to 0.01 (equal to L1 -> after L1)
        step_distance(table, find_row_by_name(table, "A2"), 0.01)
        self.assertTrue(wait_until(lambda: get_order() == ["L1", "A2", "L2", "S1", "S2", "A1"], 2000))
        self.assertEqual(get_order(), ["L1", "A2", "L2", "S1", "S2", "A1"])

        # set L1 dist to 1
        step_distance(table, find_row_by_name(table, "L1"), 1.0)
        self.assertTrue(wait_until(lambda: get_order() == ["A2", "L1", "L2", "S1", "S2", "A1"], 2000))
        self.assertEqual(get_order(), ["A2", "L1", "L2", "S1", "S2", "A1"])

        # set L1 dist to 0.01 (equal to A2 -> after A2)
        step_distance(table, find_row_by_name(table, "L1"), 0.01)
        self.assertTrue(wait_until(lambda: get_order() == ["A2", "L1", "L2", "S1", "S2", "A1"], 2000))
        self.assertEqual(get_order(), ["A2", "L1", "L2", "S1", "S2", "A1"])

        # set S1 dist to 60
        step_distance(table, find_row_by_name(table, "S1"), 60.0)
        self.assertTrue(wait_until(lambda: get_order() == ["A2", "L1", "L2", "S1", "S2", "A1"], 2000))
        self.assertEqual(get_order(), ["A2", "L1", "L2", "S1", "S2", "A1"])

    # 12) click solve under screen
    def test_12_click_solve_button_under_screen(self):
        window = cast(MainWindow, self.window)
        # Work on current tab
        tab_widget = cast(WorkspaceTab, window.tabs.currentWidget())
        solve_btn = getattr(tab_widget, 'screen_img').solve_button
        solve_btn.click()
        self.assertTrue(wait_until(lambda: solve_btn.isEnabled(), 5000))

    # 13) workspace naming and validation across delimiters (space, comma, dot)
    def test_13_workspace_naming_and_validation_delimiters(self):
        window = cast(MainWindow, self.window)
        workdir = os.path.join(os.getcwd(), "workspaces")
        os.makedirs(workdir, exist_ok=True)

        def _write_ws(path, ws_name: str):
            data = {
                'workspace_name': ws_name,
                'system_params': {
                    'engine': 'Diffractsim Forward',
                    'field_type': 'Monochromatic',
                    'wavelength_nm': float(DEFAULT_WAVELENGTH_NM),
                    'extent_x_mm': float(DEFAULT_EXTENSION_X_MM),
                    'extent_y_mm': float(DEFAULT_EXTENSION_Y_MM),
                    'resolution_px_per_mm': float(DEFAULT_RESOLUTION_PX_PER_MM),
                },
                'elements': [],
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f)

        # Base tab named "Scene 1"
        window.add_new_tab()
        base_idx = window.tabs.count() - 1
        with patch.object(QInputDialog, 'getText', return_value=("Scene 1", True)):
            window.rename_tab(base_idx)
        self.assertEqual(window.tabs.tabText(base_idx), "Scene 1")

        # Case 1: load workspace with same name "Scene 1" -> expect auto-increment to "Scene 2"
        p1 = os.path.join(workdir, "tmp_scene_space.json")
        _write_ws(p1, "Scene 1")
        with patch('PyQt6.QtWidgets.QFileDialog.getOpenFileName', return_value=(p1, '')), \
             patch.object(QMessageBox, 'information', return_value=QMessageBox.StandardButton.Ok):
            window.load_workspace()
        self.assertEqual(window.tabs.tabText(window.tabs.currentIndex()), "Scene 2")

        # Case 2: load workspace with name using comma delimiter -> expect sanitized + increment to "Scene_2"
        p2 = os.path.join(workdir, "tmp_scene_comma.json")
        _write_ws(p2, "Scene,1")
        with patch('PyQt6.QtWidgets.QFileDialog.getOpenFileName', return_value=(p2, '')), \
             patch.object(QMessageBox, 'information', return_value=QMessageBox.StandardButton.Ok):
            window.load_workspace()
        self.assertEqual(window.tabs.tabText(window.tabs.currentIndex()), "Scene_2")
        self.assertNotIn(',', window.tabs.tabText(window.tabs.currentIndex()))

        # Case 3: dot delimiter -> expect "Scene_2" as well
        p3 = os.path.join(workdir, "tmp_scene_dot.json")
        _write_ws(p3, "Scene.1")
        with patch('PyQt6.QtWidgets.QFileDialog.getOpenFileName', return_value=(p3, '')), \
             patch.object(QMessageBox, 'information', return_value=QMessageBox.StandardButton.Ok):
            window.load_workspace()
        self.assertEqual(window.tabs.tabText(window.tabs.currentIndex()), "Scene_3")
        self.assertNotIn('.', window.tabs.tabText(window.tabs.currentIndex()))

    # 14) element table renaming sync when changing type (auto-rename unique only)
    def test_14_element_auto_rename_on_type_change_unique(self):
        window = cast(MainWindow, self.window)
        vw = cast(WorkspaceTab, window.tabs.widget(0)).visualizer
        table = vw.table
        # Add Aperture -> default name "Aperture 1"
        vw.add_aperture_btn.click()
        self.assertTrue(wait_until(lambda: table.rowCount() == 2, 500))
        # Change type to Lens; name should become "Lens 1"
        type_w = table.cellWidget(1, 1)
        self.assertIsInstance(type_w, QComboBox)
        cast(QComboBox, type_w).setCurrentText("Lens")
        self.assertTrue(wait_until(lambda: find_row_by_name(table, "Lens 1") == 1, 500))
        self.assertEqual(find_row_by_name(table, "Lens 1"), 1)
        self.assertEqual(cast(QComboBox, table.cellWidget(1, 1)).currentText(), 'Lens')

    def test_15_element_auto_rename_on_type_change_conflict(self):
        window = cast(MainWindow, self.window)
        vw = cast(WorkspaceTab, window.tabs.widget(0)).visualizer
        table = vw.table
        # Ensure a Lens 1 exists
        vw.add_lens_btn.click()
        self.assertTrue(wait_until(lambda: table.rowCount() == 2, 500))
        self.assertEqual(find_row_by_name(table, "Lens 1"), 1)
        # Add Aperture -> default "Aperture 1"
        vw.add_aperture_btn.click()
        self.assertTrue(wait_until(lambda: table.rowCount() == 3, 500))
        a_row = 2
        self.assertEqual(cast(QLineEdit, table.cellWidget(a_row, 0)).text(), "Aperture 1")
        # Change its type to Lens; due to conflict, name should remain "Aperture 1"
        type_w = table.cellWidget(a_row, 1)
        self.assertIsInstance(type_w, QComboBox)
        cast(QComboBox, type_w).setCurrentText("Lens")
        # Reacquire row for name after refresh
        row = find_row_by_name(table, "Aperture 1")
        self.assertNotEqual(row, -1)
        self.assertEqual(cast(QComboBox, table.cellWidget(row, 1)).currentText(), 'Lens')

    # 16) screen end distance clamp and minimum follows start
    def test_16_screen_end_distance_limits(self):
        window = cast(MainWindow, self.window)
        vw = cast(WorkspaceTab, window.tabs.widget(0)).visualizer
        table = vw.table
        vw.add_screen_btn.click()
        self.assertTrue(wait_until(lambda: table.rowCount() == 2, 500))
        # Enable range and set From to 5.0, To to 3.0 (should clamp to 5.0)
        set_screen_range(table, 1, True, start_val=5.0)
        dist_cell = table.cellWidget(1, 2)
        spins = []
        if isinstance(dist_cell, QWidget):
            spins = dist_cell.findChildren(QDoubleSpinBox)
        self.assertGreaterEqual(len(spins), 2)
        # Ensure ordering [From, To]
        spins = sorted(spins, key=lambda s: s.geometry().x())
        # Try to set To below From
        spins[1].setValue(3.0)
        try:
            spins[1].editingFinished.emit()
        except Exception:
            pass
        QApplication.processEvents()
        # Reacquire after any rebuild
        dist_cell = table.cellWidget(1, 2)
        spins = []
        if isinstance(dist_cell, QWidget):
            spins = dist_cell.findChildren(QDoubleSpinBox)
        spins = sorted(spins, key=lambda s: s.geometry().x()) if spins else []
        self.assertGreaterEqual(spins[1].value(), 5.0)
        self.assertGreaterEqual(spins[1].minimum(), 5.0)
        # Increase From to 12.0 -> To min should follow and clamp if lower
        spins[0].setValue(12.0)
        try:
            spins[0].editingFinished.emit()
        except Exception:
            pass
        QApplication.processEvents()
        dist_cell = table.cellWidget(1, 2)
        spins = []
        if isinstance(dist_cell, QWidget):
            spins = dist_cell.findChildren(QDoubleSpinBox)
        spins = sorted(spins, key=lambda s: s.geometry().x()) if spins else []
        self.assertGreaterEqual(spins[1].minimum(), 12.0)

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(GUITestCase)
    unittest.TextTestRunner(verbosity=0).run(suite)
