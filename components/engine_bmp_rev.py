# filepath: components/engine_bmp_rev.py
"""
Bitmap-based reverse engine.
Implements calculate_screen_images with the same public signature used by the
UI so it can be swapped via SystemParametersWidget.engine_combo.
For now, it synthesizes a simple placeholder image and writes outputs in the
same structure as the forward engine for UI compatibility.
"""
from __future__ import annotations

from typing import Any
from pathlib import Path
from datetime import datetime
import numpy as np
from PIL import Image

from .helpers import slugify as _slugify, Element


def _ensure_output_dir(workspace_name: str, retain: bool = False) -> Path:
    base = Path("simulation_results") / workspace_name
    if not retain:
        # Best-effort cleanup of previous Screen files (PNG/GIF)
        try:
            if base.exists():
                for p in list(base.glob("Screen_*.png")) + list(base.glob("Screen_*.gif")):
                    try:
                        p.unlink()
                    except Exception:
                        pass
        except Exception:
            pass
    base.mkdir(parents=True, exist_ok=True)
    return base


def _synth_image(height: int, width: int) -> np.ndarray:
    # Simple synthetic pattern (radial gradient) as a placeholder
    yy, xx = np.mgrid[0:height, 0:width]
    cy, cx = height / 2.0, width / 2.0
    r = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    r = (r / r.max())
    img = np.stack([r, 1.0 - r, 0.5 * np.ones_like(r)], axis=-1)
    return (np.clip(img * 255, 0, 255)).astype(np.uint8)


def calculate_screen_images(
    FieldType: Any,
    Wavelength: float,
    ExtentX: float,
    ExtentY: float,
    Resolution: float,
    Elements: list[Any],
    Backend: str = "CPU",
    side: str | None = None,
    workspace_name: str = "Workspace_1",
):
    height = int(ExtentY * Resolution)
    width = int(ExtentX * Resolution)

    out_dir = _ensure_output_dir(workspace_name, retain=False)

    # Just like the forward engine, expand screen ranges into slices so the UI
    # can display series/GIFs in the same way (but we'll only save PNGs here).
    expanded = []
    for e in Elements:
        et = getattr(e, 'element_type', None)
        if et == 'screen':
            p = getattr(e, 'params', {}) or {}
            is_range = bool(p.get('is_range', False))
            range_end = float(p.get('range_end_mm', getattr(e, 'distance', 0.0)))
            steps = int(p.get('steps', 1) or 1)
            if steps < 1:
                steps = 1
            if is_range:
                import numpy as _np
                dists = list(_np.linspace(float(getattr(e, 'distance', 0.0)), range_end, steps))
            else:
                dists = [float(getattr(e, 'distance', 0.0))]
            for i, d in enumerate(dists, start=1):
                expanded.append(Element(
                    name=getattr(e, 'name', None),
                    element_type='screen',
                    distance=float(d),
                    params={
                        'is_from_range': is_range,
                        'slice_index': i if is_range else None,
                        'range_start_mm': float(getattr(e, 'distance', 0.0)) if is_range else None,
                        'range_end_mm': range_end if is_range else None,
                        'steps': steps if is_range else None,
                    },
                ))
        else:
            expanded.append(e)

    # Sort by distance and ensure non-screens first at ties
    expanded.sort(key=lambda el: (float(getattr(el, 'distance', 0.0)), 0 if getattr(el, 'element_type', '') != 'screen' else 1))

    last_rgb = None
    for e in expanded:
        if getattr(e, 'element_type', None) != 'screen':
            continue
        # Produce a synthetic image
        rgb_uint8 = _synth_image(height, width)
        last_rgb = rgb_uint8
        # Save to file with same naming convention used by forward engine
        name = _slugify(getattr(e, 'name', None))
        d_mm = float(getattr(e, 'distance', 0.0))
        slice_idx = getattr(e, 'params', {}).get('slice_index')
        if slice_idx is not None:
            fname = f"{name}_{d_mm:.2f}_mm_slice_{int(slice_idx):03d}.png"
        else:
            fname = f"{name}_{d_mm:.2f}_mm.png"
        path = out_dir / fname
        Image.fromarray(rgb_uint8, mode='RGB').save(path)

    # Return last image for preview in the widget
    if last_rgb is None:
        last_rgb = _synth_image(height, width)
    return last_rgb
