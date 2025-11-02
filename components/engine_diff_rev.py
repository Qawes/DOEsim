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
    # Optionally you could tweak parameters to distinguish output, e.g.,
    # different backend tag, or post-process the RGB.
    return _fwd.calculate_screen_images(
        FieldType=FieldType,
        Wavelength=Wavelength,
        ExtentX=ExtentX,
        ExtentY=ExtentY,
        Resolution=Resolution,
        Elements=Elements,
        Backend=Backend,
        side=side,
        workspace_name=workspace_name,
    )
