from dataclasses import dataclass

from shapely import Polygon


@dataclass
class Carpet:
    polygon: Polygon
    filename: str = "unknown"
    color: str = "серый"
    order_id: str = "unknown"
    priority: int = 1
