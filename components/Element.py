from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Type, TypeVar, Optional
from enum import Enum

class ElementParamKey(str, Enum):
    # Common
    IMAGE_PATH = "image_path"
    WIDTH_MM = "width_mm"
    HEIGHT_MM = "height_mm"
    IS_INVERTED = "is_inverted"
    IS_PHASEMASK = "is_phasemask"
    FOCAL_LENGTH = "focal_length"
    IS_RANGE = "is_range"
    RANGE_END = "range_end"
    STEPS = "steps"
    PADDING = "padding"
    MAXITER = "maxiter"
    PR_METHOD = "phase_retrieval_method"

class EType(str, Enum):
    APERTURE = "Aperture"
    LENS = "Lens"
    SCREEN = "Screen"
    APERTURE_RESULT = "Aperture Result"
    TARGET_INTENSITY = "Target Intensity"

class PRMethods(str, Enum):
    G_S = "Gerchberg-Saxton"
    C_GRAD = "Conjugate-Gradient"
    

T = TypeVar("T", bound="Element")

@dataclass
class Element:
    """
    Base class for all optical elements.
    - element_type: logical type string
    - distance: placement along optical axis (mm)
    - name: optional display name
    """
    element_type: str
    distance: float = 0.0
    name: str | None = None

    def export(self) -> Dict[str, Any]:
        """Export a serializable dict of this element including type, distance and name.
        Subclasses extend this with their own fields.
        """
        return {
            "type": self.element_type,
            "distance": float(self.distance),
            "name": self.name,
        }

    def get_type(self) -> str:
        """Return the element's type string."""
        return self.element_type

    def get_distance(self) -> float:
        """Return the element's distance (mm)."""
        return float(self.distance)

    def get_name(self) -> str | None:
        """Return the element's name (or None)."""
        return self.name

    def params_dict(self) -> Dict[str, Any]:
        """Return a dictionary of this element's parameters (base: empty)."""
        return {}

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Factory: build an Element (or subclass) from a dict.
        Expects key 'type' to select subclass.
        Accepts several legacy keys for back-compat.
        """
        # Normalize type to an EType value string for comparison
        et_raw = data.get("type", "")
        et_str = str(et_raw).strip()
        nm = data.get("name")
        # Common legacy distance key
        dist_val = data.get("distance", data.get("distance_mm", 0.0))

        # Helper: parse PR method into enum
        def _parse_pr_method(val: Any) -> PRMethods:
            if isinstance(val, PRMethods):
                return val
            if isinstance(val, Enum):
                try:
                    return PRMethods(val.value)  # type: ignore[arg-type]
                except Exception:
                    pass
            s = str(val).strip()
            # Accept common aliases
            aliases = {
                "gs": PRMethods.G_S,
                "g_s": PRMethods.G_S,
                "gerchberg-saxton": PRMethods.G_S,
                "gerchberg saxton": PRMethods.G_S,
                "cgrad": PRMethods.C_GRAD,
                "c_grad": PRMethods.C_GRAD,
                "conjugate-gradient": PRMethods.C_GRAD,
                "conjugate gradient": PRMethods.C_GRAD,
            }
            key = s.lower()
            if key in aliases:
                return aliases[key]
            try:
                return PRMethods(s)
            except Exception:
                return PRMethods.C_GRAD

        if et_str == EType.APERTURE.value:
            # Legacy aperture keys and flags
            img_path = data.get("image_path", data.get("aperture_path", ""))
            w_mm = data.get("width_mm", data.get("aperture_width_mm", 1.0))
            h_mm = data.get("height_mm", data.get("aperture_height_mm", 1.0))
            inv = data.get("is_inverted", data.get("inverted", False))
            pm = data.get("is_phasemask", data.get("phasemask", False))
            return Aperture(
                distance=float(dist_val),
                image_path=str(img_path),
                width_mm=float(w_mm),
                height_mm=float(h_mm),
                is_inverted=bool(inv),
                is_phasemask=bool(pm),
                name=nm,
            )  # type: ignore
        if et_str == EType.LENS.value:
            return Lens(
                distance=float(dist_val),
                focal_length=float(data.get("focal_length", data.get("f", 0.0))),
                name=nm,
            )  # type: ignore
        if et_str == EType.SCREEN.value:
            # steps key could be 'step' or 'steps'
            steps_val = data.get("steps", data.get("step", 10))
            return Screen(
                distance=float(dist_val),
                is_range=bool(data.get("is_range", False)),
                range_end=float(data.get("range_end", data.get("range_end_mm", data.get("distance", dist_val)))),
                steps=int(steps_val),
                name=nm,
            )  # type: ignore
        if et_str == EType.APERTURE_RESULT.value:
            # Support legacy/alternate keys
            w_mm = data.get("width_mm", 1.0)
            h_mm = data.get("height_mm", 1.0)
            maxiter = data.get("maxiter", data.get("max_iter", data.get("iterations", 100)))
            padding = data.get("padding", data.get("padding_px", 0))
            method_val = data.get(
                ElementParamKey.PR_METHOD,
                data.get("pr_method", data.get("method", PRMethods.C_GRAD.value)),
            )
            return ApertureResult(
                distance=float(dist_val),
                width_mm=float(w_mm),
                height_mm=float(h_mm),
                maxiter=int(maxiter),
                padding=int(padding),
                method=_parse_pr_method(method_val),
                name=nm,
            )  # type: ignore
        if et_str == EType.TARGET_INTENSITY.value:
            img_path = data.get("image_path", data.get("aperture_path", ""))
            w_mm = data.get("width_mm", data.get("aperture_width_mm", 1.0))
            h_mm = data.get("height_mm", data.get("aperture_height_mm", 1.0))
            return TargetIntensity(
                distance=float(dist_val),
                image_path=str(img_path),
                width_mm=float(w_mm),
                height_mm=float(h_mm),
                name=nm,
            )  # type: ignore
        # Unknown type -> generic Element
        return cls(element_type=et_str or "Unknown", distance=float(dist_val), name=nm)


@dataclass
class Aperture(Element):
    image_path: str = ""
    width_mm: float = 1.0
    height_mm: float = 1.0
    is_inverted: bool = False
    is_phasemask: bool = False

    def __init__(self, distance: float = 0.0, image_path: str = "", width_mm: float = 1.0, height_mm: float = 1.0,
                 is_inverted: bool = False, is_phasemask: bool = False, name: str | None = None):
        super().__init__(EType.APERTURE, float(distance), name)
        self.image_path = image_path
        self.width_mm = float(width_mm)
        self.height_mm = float(height_mm)
        self.is_inverted = bool(is_inverted)
        self.is_phasemask = bool(is_phasemask)

    def export(self) -> Dict[str, Any]:
        d = super().export()
        d.update({
            ElementParamKey.IMAGE_PATH: self.image_path,
            ElementParamKey.WIDTH_MM: float(self.width_mm),
            ElementParamKey.HEIGHT_MM: float(self.height_mm),
            ElementParamKey.IS_INVERTED: bool(self.is_inverted),
            ElementParamKey.IS_PHASEMASK: bool(self.is_phasemask),
        })
        return d

    def params_dict(self) -> Dict[str, Any]:
        return {
            ElementParamKey.IMAGE_PATH: self.image_path,
            ElementParamKey.WIDTH_MM: self.width_mm,
            ElementParamKey.HEIGHT_MM: self.height_mm,
            ElementParamKey.IS_INVERTED: self.is_inverted,
            ElementParamKey.IS_PHASEMASK: self.is_phasemask,
        }


@dataclass
class Lens(Element):
    focal_length: float = 0.0

    def __init__(self, distance: float = 0.0, focal_length: float = 0.0, name: str | None = None):
        super().__init__(EType.LENS, float(distance), name)
        self.focal_length = float(focal_length)

    def export(self) -> Dict[str, Any]:
        d = super().export()
        d.update({
            ElementParamKey.FOCAL_LENGTH: float(self.focal_length),
            # also include common alias used by engines
            "f": float(self.focal_length),
        })
        return d

    def params_dict(self) -> Dict[str, Any]:
        return {
            ElementParamKey.FOCAL_LENGTH: self.focal_length,
        }


@dataclass
class Screen(Element):
    is_range: bool = False
    range_end: float = 0.0
    steps: int = 10

    def __init__(self, distance: float = 0.0, is_range: bool = False, range_end: Optional[float] = None, steps: int = 10, name: str | None = None):
        super().__init__(EType.SCREEN, float(distance), name)
        self.is_range = bool(is_range)
        # default range_end to distance when not provided
        self.range_end = float(distance if range_end is None else range_end)
        self.steps = max(1, int(steps))
        # clamp: range_end cannot be smaller than distance
        if self.range_end < self.distance:
            self.range_end = float(self.distance)
        if not self.is_range:
            # when not a range, force steps >= 1 and keep range_end matching distance for clarity
            self.range_end = float(self.distance)
            self.steps = max(1, int(self.steps))

    def export(self) -> Dict[str, Any]:
        d = super().export()
        d.update({
            ElementParamKey.IS_RANGE: bool(self.is_range),
            ElementParamKey.RANGE_END: float(self.range_end),
            ElementParamKey.STEPS: int(self.steps),
        })
        return d

    def params_dict(self) -> Dict[str, Any]:
        return {
            ElementParamKey.IS_RANGE: self.is_range,
            ElementParamKey.RANGE_END: self.range_end,
            ElementParamKey.STEPS: self.steps,
        }


@dataclass
class ApertureResult(Element):
    width_mm: float = 1.0
    height_mm: float = 1.0
    maxiter: int = 200
    padding: int = 0
    method: PRMethods = PRMethods.C_GRAD

    def __init__(self, distance: float = 0.0, width_mm: float = 1.0, height_mm: float = 1.0, maxiter: int = 200, padding: int = 0, method = PRMethods.C_GRAD, name: str | None = None):
        super().__init__(EType.APERTURE_RESULT, float(distance), name)
        self.width_mm = float(width_mm)
        self.height_mm = float(height_mm)
        # ensure attributes exist even with custom __init__
        self.maxiter = int(maxiter)
        self.padding = int(padding)
        # allow string or enum for method
        if isinstance(method, PRMethods):
            self.method = method
        else:
            try:
                self.method = PRMethods(str(method))
            except Exception:
                # accept value strings
                try:
                    self.method = PRMethods(str(getattr(method, "value", PRMethods.C_GRAD.value)))
                except Exception:
                    self.method = PRMethods.C_GRAD

    def export(self) -> Dict[str, Any]:
        d = super().export()
        d.update({
            ElementParamKey.WIDTH_MM: float(self.width_mm),
            ElementParamKey.HEIGHT_MM: float(self.height_mm),
            ElementParamKey.MAXITER: int(self.maxiter),
            ElementParamKey.PADDING: int(self.padding),
            ElementParamKey.PR_METHOD: str(self.method.value),
        })
        return d

    def params_dict(self) -> Dict[str, Any]:
        return {
            ElementParamKey.WIDTH_MM: self.width_mm,
            ElementParamKey.HEIGHT_MM: self.height_mm,
            ElementParamKey.MAXITER: self.maxiter,
            ElementParamKey.PADDING: self.padding,
            ElementParamKey.PR_METHOD: self.method,
        }


@dataclass
class TargetIntensity(Element):
    image_path: str = ""
    width_mm: float = 1.0
    height_mm: float = 1.0

    def __init__(self, distance: float = 0.0, image_path: str = "", width_mm: float = 1.0, height_mm: float = 1.0, name: str | None = None):
        super().__init__(EType.TARGET_INTENSITY, float(distance), name)
        self.image_path = image_path
        self.width_mm = float(width_mm)
        self.height_mm = float(height_mm)

    def export(self) -> Dict[str, Any]:
        d = super().export()
        d.update({
            ElementParamKey.IMAGE_PATH: self.image_path,
            ElementParamKey.WIDTH_MM: float(self.width_mm),
            ElementParamKey.HEIGHT_MM: float(self.height_mm),
        })
        return d

    def params_dict(self) -> Dict[str, Any]:
        return {
            ElementParamKey.IMAGE_PATH: self.image_path,
            ElementParamKey.WIDTH_MM: self.width_mm,
            ElementParamKey.HEIGHT_MM: self.height_mm,
        }

