import diffractsim
from diffractsim import MonochromaticField, ApertureFromImage, Lens, mm, nm, cm
from diffractsim.diffractive_elements import CircularAperture, RectangularSlit, BinaryGrating, PhaseGrating
import numpy as np
import time



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

def calculate_random_image(FieldType, Wavelength, ExtentX, ExtentY, Resolution, Elements, Backend="CPU", side=None):
    """
    Simulate a calculation by returning a random color image as a NumPy array, depending on 'side'.
    """
    diffractsim.set_backend(Backend)
    height = int(ExtentY * Resolution)
    width = int(ExtentX * Resolution)
    F = MonochromaticField(
        wavelength=Wavelength * nm, extent_x=ExtentX * mm, extent_y=ExtentY * mm, Nx=width, Ny=height
    )
    # Sort elements by distance
    Elements_sorted = sorted(Elements, key=lambda e: e.distance)
    propagated_distance = 0.0 * mm
    for idx, elem in enumerate(Elements_sorted):
        if elem.element_type == "aperture":
            print(f"Adding aperture element {idx} with params: {elem.params}")
            if "image_path" in elem.params:
                width_mm = elem.params.get("width_mm", 1.0)
                height_mm = elem.params.get("height_mm", 1.0)
                F.add(ApertureFromImage(elem.params["image_path"], 
                                        image_size=(width_mm * mm, height_mm * mm), 
                                        simulation = F))
            # TODO: remove these, aperatures should be added only from the image path
            elif elem.params.get("shape") == "circle":
                F.add(CircularAperture(radius=elem.params.get("radius", 1) * mm))
            elif elem.params.get("shape") == "rectangle":
                F.add(RectangularSlit(width=elem.params.get("width", 1) * mm,
                                     height=elem.params.get("height", 1) * mm))
            elif elem.params.get("shape") == "binary_grating":
                F.add(BinaryGrating(period=elem.params.get("period", 1) * mm,
                                   width=elem.params.get("width", 1) * mm,
                                   height=elem.params.get("height", 1) * mm))
            elif elem.params.get("shape") == "phase_grating":
                F.add(PhaseGrating(period=elem.params.get("period", 1) * mm,
                                  width=elem.params.get("width", 1) * mm,
                                  height=elem.params.get("height", 1) * mm))
        elif elem.element_type == "lens":
            print(f"Adding lens element {idx} with focal length: {elem.params.get('f', 100)} mm")
            F.add(Lens(f=elem.params.get("f", 100) * mm))
        # Add more element types as needed
        F.propagate((elem.distance * mm - propagated_distance))
        propagated_distance = elem.distance * mm
    # Keep this in for fallback
    # time.sleep(1)  # Simulate computation delay
    # arr = np.random.rand(height, width)
    # if side == "aperture":
    #     # Green image
    #     img = np.zeros((height, width, 3), dtype=np.uint8)
    #     img[..., 1] = (arr * 255).astype(np.uint8)
    # elif side == "screen":
    #     # Red image
    #     img = np.zeros((height, width, 3), dtype=np.uint8)
    #     img[..., 0] = (arr * 255).astype(np.uint8)
    # else:
    #     # Grayscale fallback
    #     img = (arr * 255).astype(np.uint8)
    # return img

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
