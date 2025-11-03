# filepath: components/engine_diff_rev.py
"""
Reverse diffraction engine (Diffractsim Reverse).
For compatibility, exposes calculate_screen_images with the same signature
as the forward engine. Currently delegates to the forward implementation
so UI features (saving PNG/GIF, metadata, progress) continue to work.
You can replace the internals later with true reverse propagation.
"""
from __future__ import annotations

from typing import Any

# Delegate to forward engine to preserve behavior and file outputs
from . import engine_diff_fwd as _fwd
# Build mapped Element.py instances
try:
    from .Element import Aperture as _Aperture, Screen as _Screen, TYPE_APERTURE_RESULT as _TYPE_AR, TYPE_TARGET_INTENSITY as _TYPE_TI
except Exception:
    _Aperture = None
    _Screen = None
    _TYPE_AR = 'ApertureResult'
    _TYPE_TI = 'TargetIntensity'

#This will get deleted prob
def _map_reverse_elements_to_forward(elements: list[object]) -> list[object]:
    mapped: list[object] = []
    for e in elements or []:
        et = getattr(e, 'element_type', None)
        et_norm = str(et).replace(' ', '').lower() if et is not None else None
        name = getattr(e, 'name', None)
        dist = float(getattr(e, 'distance', 0.0))
        # Image parameters, when present
        p = getattr(e, 'params', {}) or {}
        img = getattr(e, 'image_path', None) or p.get('image_path')
        wmm = getattr(e, 'width_mm', None) or p.get('width_mm')
        hmm = getattr(e, 'height_mm', None) or p.get('height_mm')
        if et_norm in ('apertureresult',) or et in (_TYPE_AR, 'ApertureResult'):
            if _Screen is not None:
                mapped.append(_Screen(distance=dist, is_range=False, range_end=dist, steps=1, name=name))
            else:
                mapped.append(e)
        elif et_norm in ('targetintensity',) or et in (_TYPE_TI, 'TargetIntensity'):
            if _Aperture is not None:
                mapped.append(_Aperture(distance=dist, image_path=img or '', width_mm=float(wmm or 1.0), height_mm=float(hmm or 1.0), name=name))
            else:
                mapped.append(e)
        else:
            mapped.append(e)
    return mapped


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
    """Reverse engine entrypoint.
    Currently calls the forward engine to produce outputs with the same
    file layout expected by the UI. Replace this with a true reverse
    diffraction computation when available.
    """
    mapped = _map_reverse_elements_to_forward(Elements)
    return _fwd.calculate_screen_images(
        FieldType=FieldType,
        Wavelength=Wavelength,
        ExtentX=ExtentX,
        ExtentY=ExtentY,
        Resolution=Resolution,
        Elements=mapped,
        Backend=Backend,
        side=side,
        workspace_name=workspace_name,
    )
