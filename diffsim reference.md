# diffractsim Reference Guide

This guide provides a concise overview of how to use the `diffractsim` package for optical simulations, based on its examples and source code.

---

## 1. Installation

Install from source (if not already installed):
```bash
pip install -e ./diffractsim-main
```

---

## 2. Basic Usage

### Importing
```python
from diffractsim import MonochromaticField, Aperture, Lens, Screen, nm, mm, cm
```

### Using Units
- Use the provided unit helpers (`nm`, `mm`, `cm`) for all physical parameters:
  - `wavelength = 532 * nm`
  - `extent_x = 10 * mm`
  - `focal_length = 10 * cm`
- This ensures correct SI units (meters) are used internally.

### Creating a Field
```python
F = MonochromaticField(wavelength=532 * nm, extent_x=10 * mm, extent_y=10 * mm, Nx=512, Ny=512)
```
- `wavelength`: use `nm`, `mm`, or `cm` as needed
- `extent_x`, `extent_y`: use `mm` or `cm`
- `Nx`, `Ny`: resolution (pixels)

### Adding Optical Elements
```python
F.add(Aperture(shape="circle", diameter=2 * mm))
F.add(Lens(f=10 * cm))  # f in cm, mm, etc.
```

### Propagation
```python
F.propagate(distance=10 * cm)  # distance in cm, mm, etc.
```

### Adding a Screen
```python
F.add(Screen())
```

---

## 3. Running the Simulation

```python
F.run()
```

---

## 4. Accessing Results

### Get Intensity or Field
```python
intensity = F.get_intensity()
field = F.get_field()
```

### Show or Save Images
```python
F.plot()  # Show result
F.save("output.png")  # Save result
```

---

## 5. Example: Double Slit Simulation
```python
from diffractsim import MonochromaticField, Aperture, Screen, nm, mm, cm

F = MonochromaticField(wavelength=532 * nm, extent_x=10 * mm, extent_y=10 * mm, Nx=512, Ny=512)
F.add(Aperture(shape="double_slit", slit_width=0.1 * mm, slit_distance=0.3 * mm))
F.propagate(5 * cm)
F.add(Screen())
F.run()
F.plot()
```

---

## 6. Notes
- Always use the provided unit helpers (`nm`, `mm`, `cm`) for all physical parameters.
- All values are converted to meters internally.
- For polychromatic simulations, use `PolychromaticField` instead of `MonochromaticField`.
- More complex elements (gratings, custom apertures, etc.) are available in the `diffractive_elements` submodule.
- See the `examples/` folder for more advanced usage.

---

## 7. Useful Links
- [diffractsim GitHub](https://github.com/valispace/diffractsim)
- See the package's README and examples for further details.
