import tkinter as tk
from abc import ABC
from dataclasses import dataclass, field
from typing import Optional

from wintoucher.util.key import Key


@dataclass
class Dot(ABC):
    """
    Data class representing a touch dot on the screen.
    """

    id: int
    x: int
    y: int
    key: Optional[Key]
    mode: str = "overlay"

    @classmethod
    def __json__(cls):
        return ("id", "x", "y", "key", "mode")


@dataclass
class PressDot(Dot):
    """
    A touch dot that represents a press.
    """

    pass


@dataclass
class FlickDot(Dot):
    """
    A touch dot that represents a flick.
    """

    angle: tk.IntVar = field(default_factory=tk.IntVar)
    distance: tk.IntVar = field(default_factory=tk.IntVar)
    delay: float = 0.005
    delta: int = 10

    def __post_init__(self):
        self.distance.set(100)

    @classmethod
    def __json__(cls):
        return (*super().__json__(), "angle", "distance")


@dataclass
class PinchDot(Dot):
    """
    A touch dot that represents a two-finger pinch gesture.
    """

    start_distance: tk.IntVar = field(default_factory=tk.IntVar)
    end_distance: tk.IntVar = field(default_factory=tk.IntVar)
    id2: int = -1
    delay: float = 0.005
    delta: int = 5

    def __post_init__(self):
        self.start_distance.set(100)
        self.end_distance.set(30)

    @classmethod
    def __json__(cls):
        return (*super().__json__(), "start_distance", "end_distance", "id2")


@dataclass
class RotateDot(Dot):
    """
    A touch dot that represents a two-finger rotation gesture.
    """

    rotation_angle: tk.IntVar = field(default_factory=tk.IntVar)
    radius: tk.IntVar = field(default_factory=tk.IntVar)
    id2: int = -1
    delay: float = 0.005
    delta: int = 5

    def __post_init__(self):
        self.rotation_angle.set(90)
        self.radius.set(60)

    @classmethod
    def __json__(cls):
        return (*super().__json__(), "rotation_angle", "radius", "id2")
