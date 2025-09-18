from dataclasses import dataclass, field
from typing import Any, ClassVar

from shapely import Polygon


@dataclass(eq=False)
class Carpet:
    polygon: Polygon
    filename: str = "unknown"
    color: str = "серый"
    order_id: str = "unknown"
    priority: int = 1
    carpet_id: int = field(default_factory=lambda: Carpet._get_next_id())

    # Class variable for tracking IDs
    _id_counter: ClassVar[int] = 0

    @classmethod
    def _get_next_id(cls) -> int:
        cls._id_counter += 1
        return cls._id_counter

    def __eq__(self, other):
        if not isinstance(other, Carpet):
            return False
        return self.carpet_id == other.carpet_id

    def __hash__(self):
        return hash(self.carpet_id)

    def __repr__(self):
        return f"Carpet(id={self.carpet_id}, filename='{self.filename}', color='{self.color}', order_id='{self.order_id}', priority={self.priority})"


@dataclass(eq=False)
class PlacedCarpet:
    polygon: Polygon
    carpet_id: int
    priority: int
    x_offset: float = 0
    y_offset: float = 0
    angle: int = 0
    filename: str = ""
    color: str = ""
    order_id: str = ""

    @classmethod
    def from_carpet(
        cls, carpet: Carpet, x_offset: float = 0, y_offset: float = 0, angle: int = 0
    ) -> "PlacedCarpet":
        """Create PlacedCarpet from Carpet with placement information."""
        return cls(
            polygon=carpet.polygon,
            x_offset=x_offset,
            y_offset=y_offset,
            angle=angle,
            filename=carpet.filename,
            color=carpet.color,
            order_id=carpet.order_id,
            carpet_id=carpet.carpet_id,
            priority=carpet.priority,
        )

    @classmethod
    def from_unplaced_carpet(
        cls,
        unplaced: "UnplacedCarpet",
        x_offset: float = 0,
        y_offset: float = 0,
        angle: int = 0,
    ) -> "PlacedCarpet":
        """Create PlacedCarpet from UnplacedCarpet with placement information."""
        return cls(
            polygon=unplaced.polygon,
            x_offset=x_offset,
            y_offset=y_offset,
            angle=angle,
            filename=unplaced.filename,
            color=unplaced.color,
            order_id=unplaced.order_id,
            carpet_id=unplaced.carpet_id,
            priority=unplaced.priority,
        )

    def __eq__(self, other):
        if not isinstance(other, PlacedCarpet):
            return False
        return self.carpet_id == other.carpet_id

    def __hash__(self):
        return hash(self.carpet_id)

    def __repr__(self):
        return f"PlacedCarpet(id={self.carpet_id}, filename='{self.filename}', pos=({self.x_offset:.1f}, {self.y_offset:.1f}), angle={self.angle}°)"


@dataclass(eq=False)
class UnplacedCarpet:
    polygon: Polygon
    carpet_id: int
    priority: int

    filename: str = ""
    color: str = ""
    order_id: str = ""

    @classmethod
    def from_carpet(cls, carpet: Carpet) -> "UnplacedCarpet":
        """Create UnplacedCarpet from Carpet."""
        return cls(
            polygon=carpet.polygon,
            filename=carpet.filename,
            color=carpet.color,
            order_id=carpet.order_id,
            carpet_id=carpet.carpet_id,
            priority=carpet.priority,
        )

    @classmethod
    def from_placed_carpet(cls, placed: PlacedCarpet) -> "UnplacedCarpet":
        """Create UnplacedCarpet from PlacedCarpet."""
        return cls(
            polygon=placed.polygon,
            filename=placed.filename,
            color=placed.color,
            order_id=placed.order_id,
            carpet_id=placed.carpet_id,
            priority=placed.priority,
        )

    def __eq__(self, other):
        if not isinstance(other, UnplacedCarpet):
            return False
        return self.carpet_id == other.carpet_id

    def __hash__(self):
        return hash(self.carpet_id)

    def __repr__(self):
        return f"UnplacedCarpet(id={self.carpet_id}, filename='{self.filename}', color='{self.color}', order_id='{self.order_id}')"


@dataclass
class PlacedSheet:
    placed_polygons: list[PlacedCarpet]
    usage_percent: float
    sheet_size: tuple[float, float]
    sheet_color: str
    orders_on_sheet: list[str]
    sheet_type: dict[str, Any]
    sheet_number: int
