from dataclasses import dataclass


@dataclass(slots=True)
class AOIRegion:
    name: str
    left: float
    right: float
    bottom: float
    top: float

    def contains(self, x_pos: float, y_pos: float) -> bool:
        return self.left <= x_pos <= self.right and self.bottom <= y_pos <= self.top
