from dataclasses import dataclass
from typing import Any

from shapely import Polygon


@dataclass(eq=False)
class Carpet:
    polygon: Polygon
    filename: str = "unknown"
    color: str = "серый"
    order_id: str = "unknown"
    priority: int = 1
    
    def __eq__(self, other):
        if not isinstance(other, Carpet):
            return False
        return (self.filename == other.filename and 
                self.color == other.color and 
                self.order_id == other.order_id and
                self.priority == other.priority)
    
    def __hash__(self):
        return hash((self.filename, self.color, self.order_id, self.priority))


@dataclass(eq=False)
class PlacedCarpet:
    polygon: Polygon
    x_offset: float = 0
    y_offset: float = 0
    angle: int = 0
    filename: str = ""
    color: str = ""
    order_id: str = ""
    
    def __eq__(self, other):
        if not isinstance(other, PlacedCarpet):
            return False
        return (self.filename == other.filename and 
                self.color == other.color and 
                self.order_id == other.order_id and
                abs(self.x_offset - other.x_offset) < 0.1 and
                abs(self.y_offset - other.y_offset) < 0.1 and
                self.angle == other.angle)
    
    def __hash__(self):
        return hash((self.filename, self.color, self.order_id, 
                    round(self.x_offset, 1), round(self.y_offset, 1), self.angle))


@dataclass(eq=False)
class UnplacedCarpet:
    polygon: Polygon
    filename: str = ""
    color: str = ""
    order_id: str = ""
    
    def __eq__(self, other):
        if not isinstance(other, UnplacedCarpet):
            return False
        return (self.filename == other.filename and 
                self.color == other.color and 
                self.order_id == other.order_id)
    
    def __hash__(self):
        return hash((self.filename, self.color, self.order_id))


@dataclass
class PlacedSheet:
    placed_polygons: list[PlacedCarpet]
    usage_percent: float
    sheet_size: tuple[float, float]
    sheet_color: str
    orders_on_sheet: list[str]
    sheet_type: dict[str, Any]
    sheet_number: int
