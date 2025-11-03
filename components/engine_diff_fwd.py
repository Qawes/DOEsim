import diffractsim
from diffractsim import MonochromaticField, ApertureFromImage, Lens, mm, nm, cm
from diffractsim.diffractive_elements import CircularAperture, RectangularSlit, BinaryGrating, PhaseGrating
import numpy as np
from copy import deepcopy
from pathlib import Path
from PIL import Image
from datetime import datetime
import time
from components.helpers import (
    slugify as _slugify, 
    fmt_fixed as _fmt2, 
    Element,
    TYPE_APERTURE,
    TYPE_LENS,
    TYPE_SCREEN
)

# Preferences
try:
    from components.preferences_window import getpref
    from components.preferences_window import (
        SET_RETAIN_WORKING_FILES,
        SET_AUTO_GENERATE_GIF,
    )
except Exception:
    # Fallbacks if preferences module is unavailable
    def getpref(key, default=None):
        return default
    SET_RETAIN_WORKING_FILES = 'retain_working_files'
    SET_AUTO_GENERATE_GIF = 'auto_generate_gif'


"""
Function that renders a light intensity field given by parameters.
Field type: monochromatic / polychromatic (to be implemented)
Wavelength [nm]: float
Extension X [mm]: float
Extension Y [mm]: float
Resolution [px/mm]: float
Elements: list of element class objects
(optional) Backend: "CPU" / "CUDA"
"""

def calculate_screen_images(FieldType, Wavelength, ExtentX, ExtentY, Resolution, Elements, Backend="CPU", side=None, workspace_name="Workspace_1"):

    diffractsim.set_backend(Backend)
    height = int(ExtentY * Resolution)
    width = int(ExtentX * Resolution)
    F = MonochromaticField(
        wavelength=Wavelength * nm, extent_x=ExtentX * mm, extent_y=ExtentY * mm, Nx=width, Ny=height
    )

    # delete folders if not retained, not just files
    # Output directory behavior based on preferences
    retain = bool(getpref(SET_RETAIN_WORKING_FILES, False))
    base_dir = Path("simulation_results") / workspace_name
    if retain:
        ts = int(time.time())
        output_dir = base_dir / str(ts)
    else:
        output_dir = base_dir
        # Per spec: delete previous Screen_* files right after clicking Solve in the same workspace
        try:
            if output_dir.exists():
                for p in list(output_dir.glob("Screen_*.png")) + list(output_dir.glob("Screen_*.gif")):
                    try:
                        p.unlink()
                    except Exception:
                        pass
        except Exception:
            pass
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize metadata
    metadata = {
        'workspace_name': workspace_name,
        'timestamp': datetime.now().strftime("%Y-%M-%d %H:%M:%S"),
        'field_type': FieldType,
        'wavelength_nm': Wavelength,
        'extent_x_mm': ExtentX,
        'extent_y_mm': ExtentY,
        'resolution_px_per_mm': Resolution,
        'backend': Backend,
        'screens': [],
        'output_dir': str(output_dir),
        'retain_working_files': retain,
    }
    
    # --- Preprocess: expand screen ranges into per-slice Element entries (retain attributes) ---
    expanded_elements = []
    for e in Elements:
        et = getattr(e, 'element_type', None)
        if et == TYPE_SCREEN:
            is_range = bool(getattr(e, 'params', {}).get("is_range", False))
            range_end = float(getattr(e, 'params', {}).get("range_end_mm", e.distance))
            steps = int(getattr(e, 'params', {}).get("steps", 10))
            if steps < 1:
                steps = 1
            # Distances to capture for this screen element
            capture_distances = [float(e.distance)]
            if is_range:
                import numpy as _np
                capture_distances = list(_np.linspace(float(e.distance), float(range_end), steps))
            # Create one Element per slice
            for i, d_mm in enumerate(capture_distances, start=1):
                slice_params = deepcopy(getattr(e, 'params', {}) or {})
                slice_params.update({
                    'is_from_range': bool(is_range),
                    'slice_index': i if is_range else None,
                    'range_start_mm': float(getattr(e, 'distance', 0.0)) if is_range else None, # Not necesserally needed
                    'range_end_mm': range_end if is_range else None,
                    'steps': steps if is_range else None,
                })
                expanded_elements.append(Element(
                    distance=float(d_mm),
                    element_type=TYPE_SCREEN,
                    params=slice_params,
                    name=getattr(e, 'name', None)
                ))
        else:
            expanded_elements.append(Element(
                distance=float(getattr(e, 'distance', 0.0)),
                element_type=getattr(e, 'element_type', None),
                params=deepcopy(getattr(e, 'params', {}) or {}),
                name=getattr(e, 'name', None)
            ))

    # --- Sort by distance; non-screen elements before screens at equal distance ---
    expanded_elements.sort(key=lambda el: (float(getattr(el, 'distance', 0.0)), 0 if getattr(el, 'element_type', '') != TYPE_SCREEN else 1))

    # --- Simulation over expanded list ---
    propagated_distance = expanded_elements[0].distance * mm
    # For GIF generation: group frames per range
    range_groups = {}
    for e in expanded_elements:
        if e.element_type != TYPE_SCREEN:
            # Propagate to this element distance, then add element to field
            delta = float(e.distance) * mm - propagated_distance
            if abs(float(delta / mm)) > 1e-12:
                F.propagate(delta)
                propagated_distance = float(e.distance) * mm
            if e.element_type == TYPE_APERTURE:
                if "image_path" in e.params: # TODO: the madman actually implemented size, set a flag for this!!
                    width_mm = e.params.get("width_mm", 1.0)
                    height_mm = e.params.get("height_mm", 1.0)
                    # TODO: as a possible failsafe, check if image_path exists, and fall back to white, while logging it to console
                    F.add(ApertureFromImage(e.params["image_path"], 
                                            image_size=(width_mm * mm, height_mm * mm), 
                                            simulation = F))
            elif e.element_type == TYPE_LENS:
                F.add(Lens(f=e.params.get("f", 100) * mm))
            continue

        # Screen slice: propagate and capture at the slice distance
        d_mm = float(e.distance)
        delta_mm = d_mm - float(propagated_distance / mm)
        if abs(delta_mm) > 1e-12: # TODO: Nice touch or possible error?
            F.propagate(delta_mm * mm)
            propagated_distance = d_mm * mm
        # Capture
        screen_image = F.get_colors()
        screen_uint8 = (np.clip(screen_image * 255, 0, 255)).astype(np.uint8)
        if not screen_uint8.flags['C_CONTIGUOUS']:
            screen_uint8 = np.ascontiguousarray(screen_uint8)
        # Filename: use element name for uniqueness; include slice index when present
        def _slug(nm: str | None) -> str: # TODO: great, but replace '_' with space, as '_' will be a delimiter for determining grouping of slices of a screen range
            return _slugify(nm)
        safe_name = _slug(getattr(e, 'name', None))
        slice_idx = e.params.get('slice_index')
        if slice_idx is not None:
            filename = f"{safe_name}_{d_mm:.2f}_mm_slice_{int(slice_idx):03d}.png"
        else:
            filename = f"{safe_name}_{d_mm:.2f}_mm.png"
        filepath = output_dir / filename
        # Save
        if screen_uint8.ndim == 3 and screen_uint8.shape[2] == 3:
            img = Image.fromarray(screen_uint8, mode='RGB')
        elif screen_uint8.ndim == 2:
            img = Image.fromarray(screen_uint8, mode='L')
        else:
            print(f"Warning: Unsupported image shape {screen_uint8.shape}")
            continue
        img.save(filepath)
        print(f"Saved screen image: {filepath}")
        # Append metadata
        md_entry = {
            'distance_mm': d_mm,
            'is_range': bool(e.params.get('is_from_range', False)),
            'range_start_mm': e.params.get('range_start_mm'),
            'range_end_mm': e.params.get('range_end_mm'),
            'steps': e.params.get('steps'),
            'slice_index': slice_idx,
            'filename': filename,
            'shape': list(screen_uint8.shape),
            'name': getattr(e, 'name', None),
        }
        metadata['screens'].append(md_entry)
        # Range grouping for GIFs
        if md_entry['is_range'] and md_entry['slice_index'] is not None:
            key = (
                md_entry.get('name'),
                float(md_entry.get('range_start_mm') or 0.0),
                float(md_entry.get('range_end_mm') or 0.0),
                int(md_entry.get('steps') or 0),
            )
            range_groups.setdefault(key, []).append((int(md_entry['slice_index']), filepath))

    # --- Optional: generate GIFs for screen ranges ---
    try:
        if bool(getpref(SET_AUTO_GENERATE_GIF, True)) and range_groups:
            for key, frames in range_groups.items():
                # Sort by slice index
                frames_sorted = [fp for _, fp in sorted(frames, key=lambda t: t[0])]
                if len(frames_sorted) < 2:
                    continue
                name, start_mm, end_mm, steps = key
                slug = _slugify(name)
                gif_name = f"{slug}_{start_mm:.2f}_to_{end_mm:.2f}_mm_steps_{int(steps)}.gif"
                gif_path = output_dir / gif_name
                pil_frames = []
                for p in frames_sorted:
                    try:
                        im = Image.open(p)
                        # Convert to palette mode for GIF (avoid palette constant for compatibility)
                        pil_frames.append(im.convert('P'))
                    except Exception:
                        continue
                if pil_frames:
                    try: # TODO: add gif options to preferences
                        pil_frames[0].save(
                            gif_path,
                            save_all=True,
                            append_images=pil_frames[1:],
                            duration=120,
                            loop=0,
                            optimize=True,
                            disposal=2,
                        )
                        print(f"Saved GIF: {gif_path}")
                    except Exception as _gif_err:
                        print(f"Failed to save GIF {gif_path}: {_gif_err}")
    except Exception:
        pass

    # --- Write metadata ---
    metadata_path = output_dir / "metadata.txt"
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
        
        f.write(f"Screen Captures: {len(metadata['screens'])}\n")
        f.write(f"{'-'*60}\n")
        for i, screen in enumerate(metadata['screens'], start=1):
            f.write(f"\nScreen {i}:\n")
            f.write(f"  Name: {screen.get('name')}\n")
            f.write(f"  Distance: {screen['distance_mm']} mm\n")
            f.write(f"  Is Range: {screen['is_range']}\n")
            if screen.get('slice_index') is not None:
                f.write(f"  Slice: {int(screen['slice_index'])}\n")
            if screen.get('range_start_mm') is not None:
                f.write(f"  Range Start: {screen.get('range_start_mm')} mm\n")
            if screen.get('range_end_mm') is not None:
                f.write(f"  Range End: {screen.get('range_end_mm')} mm\n")
            if screen.get('steps') is not None:
                f.write(f"  Steps: {screen['steps']}\n")
            f.write(f"  Filename: {screen['filename']}\n")
            f.write(f"  Image Shape: {screen['shape']}\n")
    
    print(f"Metadata saved: {metadata_path}")

    # --- Return ---
    rgb = F.get_colors()
    # Ensure rgb is uint8 and C-contiguous for QImage
    rgb_uint8 = (np.clip(rgb * 255, 0, 255)).astype(np.uint8)
    if not rgb_uint8.flags['C_CONTIGUOUS']:
        rgb_uint8 = np.ascontiguousarray(rgb_uint8)
    # QImage expects shape (height, width, 3)
    return rgb_uint8
