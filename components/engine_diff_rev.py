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
from datetime import datetime

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
    width = int(ExtentX * Resolution)
    height = int(ExtentY * Resolution)
    F = MonochromaticField(
        wavelength=Wavelength * nm, extent_x=ExtentX * mm, extent_y=ExtentY * mm, Nx=width, Ny=height
    )

    implemented_methods = ('Gerchberg-Saxton', 'Conjugate-Gradient') # diffractsim provided implementations

    maxiter = 1
    method = ""
    targetpath = None
    resultpath = None
    workdir = set_working_dir(workspace_name, getpref(Prefs.RETAIN_WORKING_FILES, True))
    # Prepare metadata similar to forward engine
    try:
        _retain = bool(getpref(Prefs.RETAIN_WORKING_FILES, True))
    except Exception:
        _retain = True
    metadata = {
        'workspace_name': workspace_name,
        'timestamp': datetime.now().strftime("%Y-%M-%d %H:%M:%S"),
        'field_type': FieldType,
        'wavelength_nm': Wavelength,
        'extent_x_mm': ExtentX,
        'extent_y_mm': ExtentY,
        'resolution_px_per_mm': Resolution,
        'backend': Backend,
        'output_dir': str(workdir),
        'retain_working_files': _retain,
        'reverse': {},
    }
    # Export all properties of all original elements
    try:
        from dataclasses import asdict as _asdict
        def _elem_dict(_e):
            try:
                return _asdict(_e)
            except Exception:
                d = {
                    'element_type': str(getattr(_e, 'element_type', None)),
                    'distance': float(getattr(_e, 'distance', 0.0)),
                    'name': getattr(_e, 'name', None),
                }
                for k in ('image_path','width_mm','height_mm','is_inverted','is_phasemask','focal_length','is_range','range_end','steps','maxiter','padding','method'):
                    if hasattr(_e, k):
                        d[k] = getattr(_e, k)
                return d
        metadata['elements'] = [_elem_dict(e) for e in (Elements or [])]
    except Exception:
        metadata['elements'] = []
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
                # Write metadata even on failure
                try:
                    metadata['reverse'] = {
                        'method': method,
                        'maxiter': int(maxiter),
                        'target_path': targetpath,
                        'result_path': resultpath,
                        'new_size': [int(width), int(height)],
                    }
                    metadata_path = workdir / "metadata.txt"
                    with open(metadata_path, 'w') as f:
                        f.write(f"Simulation Metadata\n")
                        f.write(f"{'='*60}\n\n")
                        f.write(f"Workspace: {metadata['workspace_name']}\n")
                        f.write(f"Timestamp: {metadata['timestamp']}\n")
                        f.write(f"Field Type: {metadata['field_type']}\n")
                        f.write(f"Wavelength: {metadata['wavelength_nm']} nm\n")
                        f.write(f"Extent X: {metadata['extent_x_mm']} mm\n")
                        f.write(f"Extent Y: {metadata['extent_y_mm']} mm\n")
                        f.write(f"Resolution: {metadata['resolution_px_per_mm']} px/mm\n")
                        f.write(f"Backend: {metadata['backend']}\n")
                        f.write(f"Output Dir: {metadata['output_dir']}\n")
                        f.write(f"Retain Working Files: {metadata['retain_working_files']}\n\n")
                        # Dump all element properties
                        try:
                            f.write(f"Elements: {len(metadata.get('elements', []))}\n")
                            f.write(f"{'-'*60}\n")
                            for i, el in enumerate(metadata.get('elements', []), start=1):
                                f.write(f"\nElement {i}:\n")
                                for k, v in (el.items() if isinstance(el, dict) else []):
                                    f.write(f"  {k}: {v}\n")
                            f.write("\n")
                        except Exception:
                            pass
                        f.write(f"Reverse Solve:\n")
                        f.write(f"  Method: {metadata['reverse'].get('method', '')}\n")
                        f.write(f"  Max Iterations: {metadata['reverse'].get('maxiter', '')}\n")
                        f.write(f"  Target Path: {metadata['reverse'].get('target_path', '')}\n")
                        f.write(f"  Result Path: {metadata['reverse'].get('result_path', '')}\n")
                        ns = metadata['reverse'].get('new_size', [width, height])
                        f.write(f"  New Size: {ns[0]} x {ns[1]}\n")
                    print(f"Metadata saved: {metadata_path}")
                except Exception:
                    pass
                return np.zeros((height, width, 3), dtype=np.uint8)

    PR = FourierPhaseRetrieval(target_amplitude_path=targetpath, new_size=(width, height), pad = (0,0))
    PR.retrieve_phase_mask(max_iter= maxiter, method=method)
    PR.save_retrieved_phase_as_image(resultpath)

    # Finalize and write metadata
    try:
        metadata['reverse'] = {
            'method': method,
            'maxiter': int(maxiter),
            'target_path': targetpath,
            'result_path': resultpath,
            'new_size': [int(width), int(height)],
        }
        metadata_path = workdir / "metadata.txt"
        with open(metadata_path, 'w') as f:
            f.write(f"Simulation Metadata\n")
            f.write(f"{'='*60}\n\n")
            f.write(f"Workspace: {metadata['workspace_name']}\n")
            f.write(f"Timestamp: {metadata['timestamp']}\n")
            f.write(f"Field Type: {metadata['field_type']}\n")
            f.write(f"Wavelength: {metadata['wavelength_nm']} nm\n")
            f.write(f"Extent X: {metadata['extent_x_mm']} mm\n")
            f.write(f"Extent Y: {metadata['extent_y_mm']} mm\n")
            f.write(f"Resolution: {metadata['resolution_px_per_mm']} px/mm\n")
            f.write(f"Backend: {metadata['backend']}\n")
            f.write(f"Output Dir: {metadata['output_dir']}\n")
            f.write(f"Retain Working Files: {metadata['retain_working_files']}\n\n")
            # Dump all element properties
            try:
                f.write(f"Elements: {len(metadata.get('elements', []))}\n")
                f.write(f"{'-'*60}\n")
                for i, el in enumerate(metadata.get('elements', []), start=1):
                    f.write(f"\nElement {i}:\n")
                    for k, v in (el.items() if isinstance(el, dict) else []):
                        f.write(f"  {k}: {v}\n")
                f.write("\n")
            except Exception:
                pass
            f.write(f"Reverse Solve:\n")
            f.write(f"  Method: {metadata['reverse'].get('method', '')}\n")
            f.write(f"  Max Iterations: {metadata['reverse'].get('maxiter', '')}\n")
            f.write(f"  Target Path: {metadata['reverse'].get('target_path', '')}\n")
            f.write(f"  Result Path: {metadata['reverse'].get('result_path', '')}\n")
            ns = metadata['reverse'].get('new_size', [width, height])
            f.write(f"  New Size: {ns[0]} x {ns[1]}\n")
        print(f"Metadata saved: {metadata_path}")
    except Exception:
        pass

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
