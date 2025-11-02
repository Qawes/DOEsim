from PyQt6.QtWidgets import QVBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget, QHBoxLayout
from PyQt6.QtGui import QPixmap, QImage, QMovie, QImageReader
from PyQt6.QtCore import Qt, QSize
import threading
import os
from pathlib import Path
import glob
import numpy as np
import engine

class ImageContainer(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title  # e.g., "Aperture image" or "Screen image"
        self._pixmap = None
        self._movie = None  # for GIFs
        self._movie_src_size = None  # natural GIF frame size
        self._solve_in_progress = False
        self._show_saved_after_solve = False
        self._items = []  # list of nodes relevant to this panel
        self._current_index = 0

        # UI
        layout = QVBoxLayout(self)
        # Header row: title + info + navigation
        header = QHBoxLayout()
        self._title_label = QLabel(title)
        self._title_label.setStyleSheet("font-weight: bold;")
        header.addWidget(self._title_label)
        header.addStretch()
        self.info_label = QLabel("")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        header.addWidget(self.info_label)
        self.nav_up_btn = QPushButton("▲")
        self.nav_up_btn.setFixedWidth(28)
        self.nav_up_btn.clicked.connect(self._nav_up)
        header.addWidget(self.nav_up_btn)
        self.nav_down_btn = QPushButton("▼")
        self.nav_down_btn.setFixedWidth(28)
        self.nav_down_btn.clicked.connect(self._nav_down)
        header.addWidget(self.nav_down_btn)
        layout.addLayout(header)

        # Image area
        self.image_label = QLabel("Image will appear here")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_label.setMinimumSize(100, 100)
        self.image_label.setTextFormat(Qt.TextFormat.RichText)
        self.image_label.setOpenExternalLinks(False)
        self.image_label.linkActivated.connect(self._on_empty_link)
        layout.addWidget(self.image_label)

        # Solve button
        self.solve_button = QPushButton("Solve")
        self.solve_button.clicked.connect(self.solve_async)
        layout.addWidget(self.solve_button)

        # Initial state
        self.refresh_from_visualizer_change()
        self._set_solve_enabled(True)

    # --- Public API for visualizer to call ---
    def refresh_from_visualizer_change(self):
        self._collect_items()
        # Clamp current index
        if not self._items:
            self._current_index = 0
        else:
            self._current_index = max(0, min(self._current_index, len(self._items) - 1))
        self._update_ui_from_selection()

    # --- Solve flow ---
    def _is_release_build(self) -> bool:
        return bool(os.environ.get("RELEASE_BUILD"))

    def _set_solve_enabled(self, enabled: bool):
        # In development, keep the Solve button enabled to avoid UX dead-ends
        if self._is_release_build():
            self.solve_button.setEnabled(bool(enabled))
        else:
            self.solve_button.setEnabled(True)

    def solve_async(self):
        if self._solve_in_progress:
            return
        self._solve_in_progress = True
        self._set_solve_enabled(False)
        self.image_label.setText("Calculating...")
        threading.Thread(target=self._fetch_image, daemon=True).start()

    def _fetch_image(self):
        # Gather context from workspace
        tab = self._find_workspace_tab()
        if tab and hasattr(tab, 'sys_params') and hasattr(tab, 'visualizer'):
            sys_params = getattr(tab, 'sys_params')
            field_type = sys_params.field_type.currentText()
            wavelength = sys_params.wavelength.value()
            extent_x = sys_params.extension_x.value()
            extent_y = sys_params.extension_y.value()
            resolution = sys_params.resolution.value()
            elements = tab.visualizer.export_elements_for_engine()
        else:
            # Fallback defaults
            try:
                from widgets.system_parameters_widget import (
                    DEFAULT_WAVELENGTH_NM,
                    DEFAULT_EXTENSION_X_MM,
                    DEFAULT_EXTENSION_Y_MM,
                    DEFAULT_RESOLUTION_PX_PER_MM,
                )
            except Exception:
                DEFAULT_WAVELENGTH_NM = 532.0
                DEFAULT_EXTENSION_X_MM = 10.0
                DEFAULT_EXTENSION_Y_MM = 10.0
                DEFAULT_RESOLUTION_PX_PER_MM = 10.0
            field_type = "Monochromatic"
            wavelength = DEFAULT_WAVELENGTH_NM
            extent_x = DEFAULT_EXTENSION_X_MM
            extent_y = DEFAULT_EXTENSION_Y_MM
            resolution = DEFAULT_RESOLUTION_PX_PER_MM
            elements = []
        Backend = "CPU"
        side = None
        if self._is_aperture_panel():
            side = "aperture"
        elif self._is_screen_panel():
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
            workspace_name=tab.get_workspace_name() if tab else "Workspace_1",
        )
        # Convert to QImage
        image = QImage()
        try:
            arr = np.asarray(arr)
        except Exception:
            arr = None
        if arr is not None and hasattr(arr, "ndim"):
            if arr.ndim == 3 and arr.shape[2] == 3:
                h = int(arr.shape[0]); w = int(arr.shape[1])
                if arr.dtype != np.uint8:
                    arr = (255 * np.clip(arr, 0, 1)).astype(np.uint8)
                if not arr.flags["C_CONTIGUOUS"]:
                    arr = np.ascontiguousarray(arr)
                bytes_per_line = 3 * w
                image = QImage(arr.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                self._last_image_array = arr
            elif arr.ndim == 2:
                h = int(arr.shape[0]); w = int(arr.shape[1])
                if arr.dtype != np.uint8:
                    arr = (255 * np.clip(arr, 0, 1)).astype(np.uint8)
                if not arr.flags["C_CONTIGUOUS"]:
                    arr = np.ascontiguousarray(arr)
                bytes_per_line = w
                image = QImage(arr.data, w, h, bytes_per_line, QImage.Format.Format_Grayscale8)
                self._last_image_array = arr
        pixmap = QPixmap.fromImage(image)
        self._pixmap = pixmap
        # After a solve, refresh screen image browsing list (if this is the screen panel)
        if self._is_screen_panel():
            try:
                self._refresh_saved_screen_images_cache()
            except Exception:
                pass
            # Prefer showing the saved image/gif per current screen after solve
            self._show_saved_after_solve = True
        self._update_image_async()

    def _update_image_async(self):
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._update_image_main_thread)

    def _update_image_main_thread(self):
        if (self._show_saved_after_solve and self._is_screen_panel()):
            # Switch display to the saved PNG/GIF for the current screen
            self._show_saved_after_solve = False
            self._pixmap = None
            self._clear_movie()
            self._update_ui_from_selection()
        else:
            self.update_image()
        self._solve_in_progress = False
        self._set_solve_enabled(True)

    # --- Navigation ---
    def _nav_up(self):
        if not self._items:
            return
        self._current_index = (self._current_index - 1) % len(self._items)
        self._update_ui_from_selection()

    def _nav_down(self):
        if not self._items:
            return
        self._current_index = (self._current_index + 1) % len(self._items)
        self._update_ui_from_selection()

    # --- Helpers ---
    def _is_aperture_panel(self) -> bool:
        return "Aperture" in (self.title or "")

    def _is_screen_panel(self) -> bool:
        return "Screen" in (self.title or "")

    def _find_workspace_tab(self):
        tab = self.parent()
        # Avoid import cycle at module import time
        from main_window import WorkspaceTab  # type: ignore
        while tab and not isinstance(tab, WorkspaceTab):
            tab = tab.parent()
        return tab

    def _collect_items(self):
        self._items = []
        tab = self._find_workspace_tab()
        vis = getattr(tab, 'visualizer', None) if tab else None
        node = vis.head.next if (vis and hasattr(vis, 'head')) else None
        while node is not None:
            if self._is_aperture_panel() and node.type == 'Aperture':
                self._items.append(node)
            elif self._is_screen_panel() and node.type == 'Screen':
                self._items.append(node)
            node = node.next

    def _update_ui_from_selection(self):
        count = len(self._items)
        # Update nav and info
        self.nav_up_btn.setEnabled(count > 1)
        self.nav_down_btn.setEnabled(count > 1)
        if count == 0:
            kind = "Aperture" if self._is_aperture_panel() else "Screen"
            self.info_label.setText(f"No {kind} elements")
            # Clickable empty state
            self.image_label.setText(f"No {kind.lower()}s yet. Click <a href='add'>add one</a> to create.")
            self._pixmap = None
            self.image_label.setPixmap(QPixmap())
            return
        # Show current item
        cur = self._items[self._current_index]
        name = getattr(cur, 'name', '(unnamed)')
        self.info_label.setText(f"{name}  ({self._current_index+1}/{count})")
        if self._is_aperture_panel():
            self._show_aperture_image(cur)
        else:
            self._show_latest_screen_image_for_item(cur)

    def _on_empty_link(self, href: str):
        if href != 'add':
            return
        # Ask visualizer to add appropriate element, then refresh
        tab = self._find_workspace_tab()
        vis = getattr(tab, 'visualizer', None) if tab else None
        if not vis:
            return
        try:
            vis.add_element('Aperture' if self._is_aperture_panel() else 'Screen')
        except Exception:
            return
        self.refresh_from_visualizer_change()

    def _show_aperture_image(self, node):
        # Display the selected aperture bitmap directly, no solve
        try:
            path = getattr(node, 'aperture_path', '') or ''
            if not path:
                self.image_label.setText("No bitmap selected for this aperture")
                self._pixmap = None
                self.image_label.setPixmap(QPixmap())
                return
            # Make absolute path for loading
            abs_path = path
            try:
                # Best-effort: PhysicalSetupVisualizer has a helper for this
                tab = self._find_workspace_tab()
                vis = getattr(tab, 'visualizer', None) if tab else None
                if vis is not None and hasattr(vis, '_abs_path'):
                    abs_path = vis._abs_path(path)
                else:
                    abs_path = os.path.abspath(path)
            except Exception:
                abs_path = os.path.abspath(path)
            if not os.path.exists(abs_path):
                self.image_label.setText(f"File not found:\n{abs_path}")
                self._pixmap = None
                self.image_label.setPixmap(QPixmap())
                return
            pm = QPixmap(abs_path)
            if pm.isNull():
                self.image_label.setText("Failed to load image")
                self._pixmap = None
                self.image_label.setPixmap(QPixmap())
                return
            self._pixmap = pm
            self.update_image()
        except Exception:
            self.image_label.setText("Failed to display aperture image")
            self._pixmap = None
            self.image_label.setPixmap(QPixmap())

    def _slug(self, nm: str | None) -> str:
        s = (nm or "screen").strip()
        if not s:
            s = "screen"
        return "".join(ch if (ch.isalnum() or ch in ("_", "-")) else "_" for ch in s)

    def _screen_results_dir(self) -> Path:
        tab = self._find_workspace_tab()
        ws = tab.get_workspace_name() if tab else "Workspace_1"
        return Path("simulation_results") / ws

    def _refresh_saved_screen_images_cache(self):
        # Preload list of saved images for all screens in this workspace for quick browsing
        directory = self._screen_results_dir()
        if not directory.exists():
            self._saved_images = []
            self._saved_gifs = []
            return
        try:
            # Search recursively to support retained timestamped runs
            self._saved_images = sorted(directory.rglob("*.png"), key=lambda p: p.stat().st_mtime)
            self._saved_gifs = sorted(directory.rglob("*.gif"), key=lambda p: p.stat().st_mtime)
        except Exception:
            # Fallback to non-recursive
            self._saved_images = sorted(directory.glob("*.png"), key=lambda p: p.stat().st_mtime)
            self._saved_gifs = sorted(directory.glob("*.gif"), key=lambda p: p.stat().st_mtime)

    def _fmt2(self, v: float) -> str:
        try:
            return f"{float(v):.2f}"
        except Exception:
            return str(v)

    def _clear_movie(self):
        try:
            if self._movie is not None:
                self._movie.stop()
                # Detach current movie from label to allow switching to pixmap
                self.image_label.setMovie(None)
        except Exception:
            pass
        self._movie = None
        self._movie_src_size = None

    def _scaled_movie_size(self) -> QSize | None:
        try:
            if self._movie_src_size is None:
                return None
            sw = max(1, int(self._movie_src_size.width()))
            sh = max(1, int(self._movie_src_size.height()))
            lw = max(1, int(self.image_label.width()))
            lh = max(1, int(self.image_label.height()))
            scale = min(lw / sw, lh / sh)
            tw = max(1, int(sw * scale))
            th = max(1, int(sh * scale))
            return QSize(tw, th)
        except Exception:
            return None

    def _show_gif(self, gif_path: Path):
        self._clear_movie()
        try:
            mv = QMovie(str(gif_path))
            self._movie = mv
            # Determine natural GIF size without loading entire movie
            try:
                rdr = QImageReader(str(gif_path))
                nat = rdr.size()
            except Exception:
                nat = QSize()
            if (not nat.isValid()) or nat.isEmpty():
                try:
                    mv.jumpToFrame(0)
                    nat = mv.frameRect().size()
                except Exception:
                    nat = QSize()
            self._movie_src_size = nat if (nat.isValid() and not nat.isEmpty()) else None
            # Scale to fit label while keeping aspect ratio
            try:
                target = self._scaled_movie_size()
                if target is not None:
                    mv.setScaledSize(target)
            except Exception:
                pass
            self.image_label.setMovie(mv)
            mv.start()
        except Exception:
            self.image_label.setText("Failed to display GIF")
            self._movie = None

    def _show_latest_screen_image_for_item(self, node):
        try:
            self._refresh_saved_screen_images_cache()
            # Determine exact target names
            slug = self._slug(getattr(node, 'name', None))
            # Prefer GIF for range screens
            if bool(getattr(node, 'is_range', False)):
                start_s = self._fmt2(getattr(node, 'distance', 0.0))
                end_s = self._fmt2(getattr(node, 'range_end', getattr(node, 'distance', 0.0)))
                steps_s = str(int(getattr(node, 'steps', 0) or 0))
                candidates = [
                    # Preferred explicit patterns without Screen_ prefix and without 'to'
                    f"{slug}_{start_s}_{end_s}_mm_steps_{steps_s}.gif",
                    # With Screen_ prefix
                    f"Screen_{slug}_{start_s}_{end_s}_mm_steps_{steps_s}.gif",
                    # Legacy patterns using 'to'
                    f"{slug}_{start_s}_to_{end_s}_mm_steps_{steps_s}.gif",
                    f"Screen_{slug}_{start_s}_to_{end_s}_mm_steps_{steps_s}.gif",
                ]
                gif_path = None
                for name in candidates:
                    found = [p for p in getattr(self, '_saved_gifs', []) if p.name == name]
                    if found:
                        gif_path = found[-1]
                        break
                # If exact not found, fallback to any GIF containing slug
                if gif_path is None:
                    matching = [p for p in getattr(self, '_saved_gifs', []) if f"{slug}_" in p.name]
                    if matching:
                        gif_path = matching[-1]
                if gif_path is not None:
                    # Show GIF
                    self._pixmap = None
                    self._show_gif(gif_path)
                    return
                # Fallback to latest PNG for this screen name
                # no return here; fall through to PNG logic

            # Single screen or no GIF found: show the exact PNG by distance
            dist_s = self._fmt2(getattr(node, 'distance', 0.0))
            png_candidates = [
                # Preferred pattern without prefix
                f"{slug}_{dist_s}_mm.png",
                # With Screen_ prefix
                f"Screen_{slug}_{dist_s}_mm.png",
            ]
            pm_path = None
            for name in png_candidates:
                found = [p for p in getattr(self, '_saved_images', []) if p.name == name]
                if found:
                    pm_path = found[-1]
                    break
            # If not found, fallback to latest matching any slice/name
            if pm_path is None:
                matching = [p for p in getattr(self, '_saved_images', []) if f"{slug}_" in p.name]
                if matching:
                    pm_path = matching[-1]
            if pm_path is None:
                self.image_label.setText("No saved screen images yet. Click Solve to generate.")
                self._pixmap = None
                self._clear_movie()
                self.image_label.setPixmap(QPixmap())
                return
            # Display PNG
            pm = QPixmap(str(pm_path))
            if pm.isNull():
                self.image_label.setText("Failed to load saved screen image")
                self._pixmap = None
                self._clear_movie()
                self.image_label.setPixmap(QPixmap())
                return
            self._pixmap = pm
            self._clear_movie()
            self.update_image()
        except Exception:
            self.image_label.setText("Failed to browse saved screen images")
            self._pixmap = None
            self._clear_movie()
            self.image_label.setPixmap(QPixmap())

    # --- QWidget overrides ---
    def resizeEvent(self, a0):
        # Keep GIF scaled along with label
        try:
            if self._movie is not None:
                target = self._scaled_movie_size()
                if target is not None:
                    self._movie.setScaledSize(target)
        except Exception:
            pass
        self.update_image()
        super().resizeEvent(a0)

    def update_image(self):
        if self._movie is not None:
            # Movie is already set on the label; ensure scaled size
            try:
                target = self._scaled_movie_size()
                if target is not None:
                    self._movie.setScaledSize(target)
            except Exception:
                pass
            return
        if self._pixmap:
            label_size = self.image_label.size()
            scaled_pixmap = self._pixmap.scaled(label_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.image_label.setPixmap(scaled_pixmap)
        else:
            # Keep whatever text content is set for empty-state messages
            pass