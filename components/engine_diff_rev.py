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
from .helpers import Element as _Elem

#This will get deleted prob
def _map_reverse_elements_to_forward(elements: list[object]) -> list[object]:
    mapped: list[object] = []
    for e in elements or []:
        et = getattr(e, 'element_type', None)
        params = dict(getattr(e, 'params', {}) or {})
        if et == 'apertureresult':
            # Behave like a Screen (capture at distance, supports range)
            mapped.append(_Elem(
                name=getattr(e, 'name', None),
                element_type='screen',
                distance=float(getattr(e, 'distance', 0.0)),
                params=params,
            ))
        elif et == 'targetintensity':
            # Behave like an Aperture (image-based)
            mapped.append(_Elem(
                name=getattr(e, 'name', None),
                element_type='aperture',
                distance=float(getattr(e, 'distance', 0.0)),
                params=params,
            ))
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
        Elements=Elements, # or use mapped (dont)
        Backend=Backend,
        side=side,
        workspace_name=workspace_name,
    )
