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
import time

from components.preferences_window import Prefs, getpref
from .helpers import slugify, set_working_dir, check_writeable_folder, check_image_path
from components.Element import Element, ElementParamKey, EType

#def distance3D(x1: float, y1: float, z1: float, x2: float, y2: float, z2: float) -> float:
#    return ((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2) ** 0.5

def distance3D(x1, y1, z1, x2, y2, z2):
    return np.sqrt((x1 - x2)**2 + (y1 - y2)**2 + (z1 - z2)**2)

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
    print("Starting Bitmap Reverse Engine Calculation...")
    width = int(ExtentX * Resolution)
    height = int(ExtentY * Resolution)

    workdir = set_working_dir(workspace_name, getpref(Prefs.RETAIN_WORKING_FILES, True))
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
    # Export all properties of original elements (mirrors other engines)
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

    resultpath = None
    targetpath = None
    ap_width = width
    ap_height = height
    is_inverted = False
    is_phasemask = False
    distance = 0.0 # mm
    _result_distance = None
    _target_distance = None

    sorted_elements = sorted(Elements, key=lambda e: e.distance)
    for e in sorted_elements:
        params = e.params_dict() or {}
        if e.element_type == EType.APERTURE_RESULT and resultpath is None:
            result_dir = check_writeable_folder(workdir)
            if result_dir is None:
                print("Aperture Result directory is not writeable.")
                metadata['reverse'] = {
                    'error': 'aperture_result_dir_not_writeable',
                }
                try:
                    with open(workdir / 'metadata.txt', 'w') as f:
                        f.write(str(metadata))
                except Exception:
                    pass
                return np.zeros((height, width, 3), dtype=np.uint8)
            # Prefer slugified name to keep filesystem safe
            try:
                nm_slug = slugify(getattr(e, 'name', 'ApertureResult'))
            except Exception:
                nm_slug = getattr(e, 'name', 'ApertureResult') or 'ApertureResult'
            resultpath = str(Path(result_dir) / f"{nm_slug}.png")
            ap_width = params.get(ElementParamKey.WIDTH_MM.value, getattr(e, 'width_mm', ap_width))
            ap_height = params.get(ElementParamKey.HEIGHT_MM.value, getattr(e, 'height_mm', ap_height))
            # These keys do not exist for ApertureResult; use safe default
            is_inverted = params.get(ElementParamKey.IS_INVERTED.value, getattr(e, 'is_inverted', False))
            is_phasemask = params.get(ElementParamKey.IS_PHASEMASK.value, getattr(e, 'is_phasemask', False))
            _result_distance = float(getattr(e, 'distance', 0.0))
        elif e.element_type == EType.TARGET_INTENSITY and targetpath is None:
            raw_path = params.get(ElementParamKey.IMAGE_PATH.value, getattr(e, 'image_path', None))
            raw_path_str = str(raw_path) if raw_path is not None else ''
            targetpath = check_image_path(raw_path_str)
            if targetpath is None:
                print("Target Intensity path invalid.")
                metadata['reverse'] = {
                    'error': 'target_intensity_path_invalid',
                }
                try:
                    with open(workdir / 'metadata.txt', 'w') as f:
                        f.write(str(metadata))
                except Exception:
                    pass
                return np.zeros((height, width, 3), dtype=np.uint8)
            _target_distance = float(getattr(e, 'distance', 0.0))

    if resultpath is None or targetpath is None:
        print("Error: Missing required elements (Aperture Result and Target Intensity).")
        metadata['reverse'] = {
            'error': 'missing_required_elements',
            'result_present': resultpath is not None,
            'target_present': targetpath is not None,
        }
        try:
            with open(workdir / 'metadata.txt', 'w') as f:
                f.write(str(metadata))
        except Exception:
            pass
        return np.zeros((height, width, 3), dtype=np.uint8)

    # Compute distance as target minus result along axis (ensure positive)
    if _result_distance is not None and _target_distance is not None:
        distance = _target_distance - _result_distance
    if distance <= 1e-12:
        print("Error: Total distance between target and result must be positive.")
        metadata['reverse'] = {
            'error': 'non_positive_distance',
            'distance_mm': float(distance),
        }
        try:
            with open(workdir / 'metadata.txt', 'w') as f:
                f.write(str(metadata))
        except Exception:
            pass
        return np.zeros((height, width, 3), dtype=np.uint8)
    
    px_distance = distance * Resolution # from mm to px
            
    assert targetpath is not None
    # Load target image and resize to fit the model
    target_im = Image.open(targetpath)
    # resize image to width by height
    target_im = target_im.resize((width, height))
    # convert resized image to numpy array of size (height, width, 1), grayscale, with float values 0..1
    target_array = np.array(target_im.convert("L")) / 255.0
    if is_inverted:
        target_array = 1.0 - target_array
    # init aperture result array
    rw = int(ap_width * Resolution)
    rh = int(ap_height * Resolution)
    result_array = np.zeros((rh, rw), dtype=float)
    #for row in range(rh):
    #    for col in range(rw):
    #        # calculate each pixels contribution from target_array
    #        pxtotal = 0.0
    #        for ty in range(height):
    #            for tx in range(width):
    #                # distance factor (simple inverse square law)
    #                px_dist = distance3D(col - rw / 2.0, row - rh / 2.0, 0.0, tx - width / 2.0, ty - height / 2.0, px_distance) # px
    #                dist = px_dist / Resolution # mm
    #                lam = Wavelength / 1000.0 # mm
    #                phase = (dist % lam) / lam * 2.0 * np.pi # fázis
    #                pxtotal += np.sin(phase) * target_array[ty, tx] # fényerő remélem
    #
    #        result_array[row, col] = pxtotal

    compute_numba(
                                            target_array,
                                            result_array,
                                            Resolution,
                                            Wavelength,
                                            px_distance)

    # remap result_array to 0..255
    normalized_result = np.interp(result_array, (result_array.min(), result_array.max()), (0, 255)).astype(np.uint8)
    # write result array to grayscale image
    result_im = Image.fromarray(normalized_result, mode="L")
    result_im.save(resultpath)

    # Write metadata on success
    try:
        metadata['reverse'] = {
            'target_path': targetpath,
            'result_path': resultpath,
            'distance_mm': float(distance),
            'aperture_result_width_mm': float(ap_width),
            'aperture_result_height_mm': float(ap_height),
            'is_inverted': bool(is_inverted),
            'is_phasemask': bool(is_phasemask),
            'new_size_px': [int(width), int(height)],
        }
        md_path = workdir / 'metadata.txt'
        with open(md_path, 'w') as f:
            f.write("Simulation Metadata\n")
            f.write("="*60 + "\n\n")
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
            try:
                f.write(f"Elements: {len(metadata.get('elements', []))}\n")
                f.write('-'*60 + '\n')
                for i, el in enumerate(metadata.get('elements', []), start=1):
                    f.write(f"\nElement {i}:\n")
                    for k, v in (el.items() if isinstance(el, dict) else []):
                        f.write(f"  {k}: {v}\n")
                f.write("\n")
            except Exception:
                pass
            f.write("Reverse Solve:\n")
            for k, v in metadata['reverse'].items():
                f.write(f"  {k}: {v}\n")
        print(f"Metadata saved: {md_path}")
    except Exception:
        pass

def fast_aperture_projection_lowmem(
    target_array,          # shape (height, width), dtype=float
    ap_width, ap_height,   # aperture size in "units"
    Resolution,            # pixels per unit
    Wavelength,            # nm
    px_distance            # distance from aperture to screen (same unit as ap_*)
):
    rw = int(ap_width  * Resolution)
    rh = int(ap_height * Resolution)
    height, width = target_array.shape

    # Pre-compute source coordinates (centred)
    tx = np.arange(width) - width / 2.0
    ty = np.arange(height) - height / 2.0
    Xs, Ys = np.meshgrid(tx, ty, indexing='xy')  # (height, width)

    # Pre-compute constants
    lam = Wavelength / 1000.0
    z2 = px_distance**2
    scale = 1.0 / Resolution

    # Output array
    result = np.zeros((rh, rw), dtype=np.float64)

    # Process **row-by-row** to keep memory < 1 GiB
    for row in range(rh):
        Yc = row - rh / 2.0
        dY = Yc - Ys[None, :, :]                    # (1, height, width)

        for col in range(rw):
            Xc = col - rw / 2.0
            dX = Xc - Xs[None, :, :]                # (1, height, width)

            # 3D distance in mm
            dist_mm = np.sqrt(dX**2 + dY**2 + z2) * scale

            # Phase and contribution
            phase = (dist_mm % lam) / lam * (2.0 * np.pi)
            contrib = np.sin(phase) * target_array

            result[row, col] = contrib.sum()

    return result

import numpy as np
from numba import njit, prange

@njit(parallel=True)
def compute_aperture_projection(
    result,                # output array (rh, rw), pre-allocated
    Xs, Ys,                # source grids (height, width)
    target_array,          # (height, width)
    rh, rw,                # output dims
    height, width,         # source dims
    z2, scale, lam         # precomputed constants
):
    for row in prange(rh):
        Yc = row - rh / 2.0
        
        # dY is row-specific, shape (height, width)
        dY = Yc - Ys
        
        # Precompute dY**2 + z2 (saves some ops inside col loop)
        dyz2 = dY**2 + z2
        
        for col in prange(rw):
            Xc = col - rw / 2.0
            
            # dX is col-specific, shape (height, width)
            dX = Xc - Xs
            
            # Distance in mm
            dist_mm = np.sqrt(dX**2 + dyz2) * scale
            
            # Phase and contribution
            phase = (dist_mm % lam) / lam * (2.0 * np.pi)
            contrib = np.sin(phase) * target_array
            
            # Sum
            result[row, col] = np.sum(contrib)

def fast_aperture_projection_parallel(
    target_array,          # shape (height, width), dtype=float
    ap_width, ap_height,   # aperture size in "units"
    Resolution,            # pixels per unit
    Wavelength,            # nm
    px_distance            # distance from aperture to screen (same unit as ap_*)
):
    rw = int(ap_width  * Resolution)
    rh = int(ap_height * Resolution)
    height, width = target_array.shape

    # Pre-compute source coordinates (centred)
    tx = np.arange(width, dtype=np.float64) - width / 2.0
    ty = np.arange(height, dtype=np.float64) - height / 2.0
    Xs, Ys = np.meshgrid(tx, ty, indexing='xy')  # (height, width)

    # Pre-compute constants
    lam = Wavelength / 1000.0
    z2 = px_distance**2
    scale = 1.0 / Resolution

    # Output array
    result = np.zeros((rh, rw), dtype=np.float64)

    # Compile and run the parallel computation
    compute_aperture_projection(
        result, Xs, Ys, target_array.astype(np.float64),
        rh, rw, height, width, z2, scale, lam
    )

    return result


import numpy as np
from numba import njit, prange

@njit(parallel=True, fastmath=True)
def compute_numba(target_array,
                  result_array,
                  Resolution,
                  Wavelength,
                  px_distance):
    height, width = target_array.shape
    rh, rw = result_array.shape

    lam = Wavelength / 1000.0  # mm

    cx_r = rw / 2.0
    cy_r = rh / 2.0
    cx_t = width / 2.0
    cy_t = height / 2.0

    for row in prange(rh):  # parallel over rows
        y_r = row - cy_r
        for col in range(rw):
            x_r = col - cx_r
            pxtotal = 0.0
            for ty in range(height):
                y_t = ty - cy_t
                for tx in range(width):
                    x_t = tx - cx_t
                    dx = x_r - x_t
                    dy = y_r - y_t
                    dz = px_distance  # constant z offset
                    px_dist = (dx*dx + dy*dy + dz*dz) ** 0.5  # Euclidean
                    dist = px_dist / Resolution  # mm
                    # normalized phase:
                    phase = (dist % lam) / lam * 2.0 * np.pi
                    pxtotal += np.sin(phase) * target_array[ty, tx]
            result_array[row, col] = pxtotal

