from dataclasses import dataclass
from typing import Any

from shapely import Polygon


@dataclass
class Carpet:
    polygon: Polygon
    filename: str = "unknown"
    color: str = "серый"
    order_id: str = "unknown"
    priority: int = 1


@dataclass
class PlacedCarpet:
    polygon: Polygon
    x_offset: float = 0
    y_offset: float = 0
    angle: int = 0
    filename: str = ""
    color: str = ""
    order_id: str = ""


@dataclass
class UnplacedCarpet:
    polygon: Polygon
    filename: str = ""
    color: str = ""
    order_id: str = ""


@dataclass
class PlacedSheet:
    placed_polygons: list[PlacedCarpet]
    usage_percent: float
    sheet_size: tuple[float, float]
    sheet_color: str
    orders_on_sheet: list[str]
    sheet_type: dict[str, Any]
    sheet_number: int
