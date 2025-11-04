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
from os import path
from . import engine_diff_fwd as _fwd
import diffractsim, numpy as np
from diffractsim import MonochromaticField, FourierPhaseRetrieval, ApertureFromImage, Lens, mm, nm, cm
from components.Element import (
    Element,
    EType,
    ElementParamKey,
)
from components.helpers import (
    ensure_dirs,
    check_image_path,
    ensure_white_image,
    set_working_dir,
    check_writeable_folder,
)
from components.preferences_window import getpref, Prefs

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
    diffractsim.set_backend(Backend)
    height = int(ExtentY * Resolution)
    width = int(ExtentX * Resolution)
    F = MonochromaticField(
        wavelength=Wavelength * nm, extent_x=ExtentX * mm, extent_y=ExtentY * mm, Nx=width, Ny=height
    )

    implemented_methods = ('Gerchberg-Saxton', 'Conjugate-Gradient') # diffractsim provided implementations

    maxiter = 1
    method = ""
    targetpath = None
    resultpath = None
    workdir = set_working_dir(workspace_name, getpref(Prefs.RETAIN_WORKING_FILES, True))
    sorted_elements = sorted(Elements, key=lambda e: e.distance)
    for e in sorted_elements:
        params = e.params_dict()
        if e.element_type == EType.APERTURE_RESULT and resultpath is None:
            resultpath = check_writeable_folder(workdir)
            resultpath = f"{resultpath}\\{e.name}.png"
            if resultpath is None:
                print("Aperture Result path is not writeable.")
                return np.zeros((height, width, 3), dtype=np.uint8)
            maxiter = params[ElementParamKey.MAXITER.value]
            method = params[ElementParamKey.PR_METHOD.value]

        if e.element_type == EType.TARGET_INTENSITY and targetpath is None:
            targetpath = params.get(ElementParamKey.IMAGE_PATH, None)
            targetpath = check_image_path(targetpath)
            if targetpath is None:
                return np.zeros((height, width, 3), dtype=np.uint8)

    PR = FourierPhaseRetrieval(target_amplitude_path=targetpath, new_size=(width, height), pad = (0,0))
    PR.retrieve_phase_mask(max_iter= maxiter, method=method)
    PR.save_retrieved_phase_as_image(resultpath)

    return None


"""
if not Path(phasepath).exists():
        PR = FourierPhaseRetrieval(target_amplitude_path = f"./apertures/{target_image}.{target_im_ext}",
          new_size= (prsizex,prsizex))#,
            pad = (padx, padx)
            )
        PR.retrieve_phase_mask(max_iter = iters, method = 'Conjugate-Gradient')
        PR.save_retrieved_phase_as_image(phasepath)
        print(f" --- Saved {prsizex} x {prsizex} image to {phasepath}")
        del PR
"""
