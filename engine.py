import diffractsim
from diffractsim import MonochromaticField, ApertureFromImage, Lens, mm, nm, cm
from diffractsim.diffractive_elements import CircularAperture, RectangularSlit, BinaryGrating, PhaseGrating
import numpy as np
import time
import os
from pathlib import Path
from PIL import Image
from datetime import datetime



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
    """
    Simulate a calculation by returning a random color image as a NumPy array, depending on 'side'.
    
    Args:
        workspace_name: Name of the workspace for organizing output files
    """
    diffractsim.set_backend(Backend)
    height = int(ExtentY * Resolution)
    width = int(ExtentX * Resolution)
    F = MonochromaticField(
        wavelength=Wavelength * nm, extent_x=ExtentX * mm, extent_y=ExtentY * mm, Nx=width, Ny=height
    )
    
    # Create output folder for this workspace
    output_dir = Path("simulation_results") / workspace_name
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize metadata
    metadata = {
        'workspace_name': workspace_name,
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'field_type': FieldType,
        'wavelength_nm': Wavelength,
        'extent_x_mm': ExtentX,
        'extent_y_mm': ExtentY,
        'resolution_px_per_mm': Resolution,
        'backend': Backend,
        'screens': []
    }
    
    # Sort elements by distance
    Elements_sorted = sorted(Elements, key=lambda e: e.distance)
    propagated_distance = 0.0 * mm
    screen_element_index = 0
    
    for idx, elem in enumerate(Elements_sorted):

        F.propagate((elem.distance * mm - propagated_distance))
        propagated_distance = elem.distance * mm
        
        if elem.element_type == "aperture":
            print(f"Adding aperture element {idx} with params: {elem.params}")
            if "image_path" in elem.params:
                width_mm = elem.params.get("width_mm", 1.0)
                height_mm = elem.params.get("height_mm", 1.0)
                F.add(ApertureFromImage(elem.params["image_path"], 
                                        image_size=(width_mm * mm, height_mm * mm), 
                                        simulation = F))
                
        elif elem.element_type == "lens":
            print(f"Adding lens element {idx} with focal length: {elem.params.get('f', 100)} mm")
            F.add(Lens(f=elem.params.get("f", 100) * mm))
        
        elif elem.element_type == "screen":
            is_range = bool(elem.params.get("is_range", False))
            range_end = float(elem.params.get("range_end_mm", elem.distance))
            steps = int(elem.params.get("steps", 10))
            if steps < 1:
                steps = 1
            print(f"Adding screen element {idx} at distance {elem.distance} mm (range: {is_range}, to: {range_end}, steps: {steps})")

            # Build list of distances to capture
            capture_distances = [float(elem.distance)]
            if is_range:
                import numpy as _np
                # Include both endpoints, evenly spaced
                capture_distances = list(_np.linspace(float(elem.distance), float(range_end), steps))

            # For each capture distance, propagate from current propagated_distance if needed
            last_capture = float(propagated_distance / mm)
            for di, d_mm in enumerate(capture_distances):
                # Propagate delta from current field to desired distance
                delta_mm = d_mm - last_capture
                if abs(delta_mm) > 1e-12:
                    F.propagate(delta_mm * mm)
                    propagated_distance = d_mm * mm
                    last_capture = d_mm

                # Get field colors
                screen_image = F.get_colors()
                screen_uint8 = (np.clip(screen_image * 255, 0, 255)).astype(np.uint8)
                if not screen_uint8.flags['C_CONTIGUOUS']:
                    screen_uint8 = np.ascontiguousarray(screen_uint8)

                # Create filename with slice index when range
                if is_range:
                    filename = f"Screen_{screen_element_index}_{d_mm:.2f}_mm_slice_{di+1:03d}.png"
                else:
                    filename = f"Screen_{screen_element_index}_{d_mm:.2f}_mm.png"
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

                metadata['screens'].append({
                    'element_index': screen_element_index,
                    'distance_mm': d_mm,
                    'is_range': is_range,
                    'range_end_mm': range_end if is_range else None,
                    'steps': steps if is_range else None,
                    'slice_index': di+1 if is_range else None,
                    'filename': filename,
                    'shape': list(screen_uint8.shape)
                })

            screen_element_index += 1

    # Save metadata file
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
        f.write(f"Backend: {metadata['backend']}\n\n")
        
        f.write(f"Screen Elements: {len(metadata['screens'])}\n")
        f.write(f"{'-'*60}\n")
        for screen in metadata['screens']:
            f.write(f"\nScreen {screen['element_index']}:\n")
            f.write(f"  Distance: {screen['distance_mm']} mm\n")
            f.write(f"  Is Range: {screen['is_range']}\n")
            f.write(f"  Filename: {screen['filename']}\n")
            f.write(f"  Image Shape: {screen['shape']}\n")
    
    print(f"Metadata saved: {metadata_path}")

    rgb = F.get_colors()
    # Ensure rgb is uint8 and C-contiguous for QImage
    rgb_uint8 = (np.clip(rgb * 255, 0, 255)).astype(np.uint8)
    if not rgb_uint8.flags['C_CONTIGUOUS']:
        rgb_uint8 = np.ascontiguousarray(rgb_uint8)
    # QImage expects shape (height, width, 3)
    return rgb_uint8

class Element:
    """
    This is a generic class for optical elements in the simulation.
    Every element has to have a distance (> 0 float).
    A type (string) to identify the element (eg. "lens", "aperture", etc.).
    Additional parameters can be stored in a dictionary. For apertures, these are the image path, and a bool for inversion, and size in mm
    For lens, its focal distance in mm.
    """
    def __init__(self, distance, element_type, params=None):
        self.distance = distance
        self.element_type = element_type
        self.params = params or {}
