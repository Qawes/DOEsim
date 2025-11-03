from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Type, TypeVar, Optional

# Type constants (display names)
TYPE_APERTURE = "Aperture"
TYPE_LENS = "Lens"
TYPE_SCREEN = "Screen"
TYPE_APERTURE_RESULT = "ApertureResult"
TYPE_TARGET_INTENSITY = "TargetIntensity"

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

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Factory: build an Element (or subclass) from a dict.
        Expects key 'type' to select subclass.
        Accepts several legacy keys for back-compat.
        """
        et = str(data.get("type", "")).strip()
        nm = data.get("name")
        # Common legacy distance key
        dist_val = data.get("distance", data.get("distance_mm", 0.0))
        if et == TYPE_APERTURE:
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
        if et == TYPE_LENS:
            return Lens(
                distance=float(dist_val),
                focal_length=float(data.get("focal_length", data.get("f", 0.0))),
                name=nm,
            )  # type: ignore
        if et == TYPE_SCREEN:
            # steps key could be 'step' or 'steps'
            steps_val = data.get("steps", data.get("step", 10))
            return Screen(
                distance=float(dist_val),
                is_range=bool(data.get("is_range", False)),
                range_end=float(data.get("range_end", data.get("range_end_mm", data.get("distance", dist_val)))),
                steps=int(steps_val),
                name=nm,
            )  # type: ignore
        if et == TYPE_APERTURE_RESULT:
            return ApertureResult(
                distance=float(dist_val),
                width_mm=float(data.get("width_mm", 1.0)),
                height_mm=float(data.get("height_mm", 1.0)),
                name=nm,
            )  # type: ignore
        if et == TYPE_TARGET_INTENSITY:
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
        return cls(element_type=et or "Unknown", distance=float(dist_val), name=nm)


@dataclass
class Aperture(Element):
    image_path: str = ""
    width_mm: float = 1.0
    height_mm: float = 1.0
    is_inverted: bool = False
    is_phasemask: bool = False

    def __init__(self, distance: float = 0.0, image_path: str = "", width_mm: float = 1.0, height_mm: float = 1.0,
                 is_inverted: bool = False, is_phasemask: bool = False, name: str | None = None):
        super().__init__(TYPE_APERTURE, float(distance), name)
        self.image_path = image_path
        self.width_mm = float(width_mm)
        self.height_mm = float(height_mm)
        self.is_inverted = bool(is_inverted)
        self.is_phasemask = bool(is_phasemask)

    def export(self) -> Dict[str, Any]:
        d = super().export()
        d.update({
            "image_path": self.image_path,
            "width_mm": float(self.width_mm),
            "height_mm": float(self.height_mm),
            "is_inverted": bool(self.is_inverted),
            "is_phasemask": bool(self.is_phasemask),
        })
        return d


@dataclass
class Lens(Element):
    focal_length: float = 0.0

    def __init__(self, distance: float = 0.0, focal_length: float = 0.0, name: str | None = None):
        super().__init__(TYPE_LENS, float(distance), name)
        self.focal_length = float(focal_length)

    def export(self) -> Dict[str, Any]:
        d = super().export()
        d.update({
            "focal_length": float(self.focal_length),
            # also include common alias used by engines
            "f": float(self.focal_length),
        })
        return d


@dataclass
class Screen(Element):
    is_range: bool = False
    range_end: float = 0.0
    steps: int = 10

    def __init__(self, distance: float = 0.0, is_range: bool = False, range_end: Optional[float] = None, steps: int = 10, name: str | None = None):
        super().__init__(TYPE_SCREEN, float(distance), name)
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
            "is_range": bool(self.is_range),
            "range_end": float(self.range_end),
            "steps": int(self.steps),
        })
        return d


@dataclass
class ApertureResult(Element):
    width_mm: float = 1.0
    height_mm: float = 1.0

    def __init__(self, distance: float = 0.0, width_mm: float = 1.0, height_mm: float = 1.0, name: str | None = None):
        super().__init__(TYPE_APERTURE_RESULT, float(distance), name)
        self.width_mm = float(width_mm)
        self.height_mm = float(height_mm)

    def export(self) -> Dict[str, Any]:
        d = super().export()
        d.update({
            "width_mm": float(self.width_mm),
            "height_mm": float(self.height_mm),
        })
        return d


@dataclass
class TargetIntensity(Element):
    image_path: str = ""
    width_mm: float = 1.0
    height_mm: float = 1.0

    def __init__(self, distance: float = 0.0, image_path: str = "", width_mm: float = 1.0, height_mm: float = 1.0, name: str | None = None):
        super().__init__(TYPE_TARGET_INTENSITY, float(distance), name)
        self.image_path = image_path
        self.width_mm = float(width_mm)
        self.height_mm = float(height_mm)

    def export(self) -> Dict[str, Any]:
        d = super().export()
        d.update({
            "image_path": self.image_path,
            "width_mm": float(self.width_mm),
            "height_mm": float(self.height_mm),
        })
        return d


__all__ = [
    "TYPE_APERTURE",
    "TYPE_LENS",
    "TYPE_SCREEN",
    "TYPE_APERTURE_RESULT",
    "TYPE_TARGET_INTENSITY",
    "Element",
    "Aperture",
    "Lens",
    "Screen",
    "ApertureResult",
    "TargetIntensity",
]