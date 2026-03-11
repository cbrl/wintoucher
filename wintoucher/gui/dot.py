import time
import tkinter as tk
from abc import ABC
from dataclasses import dataclass
from math import cos, radians, sin
from threading import Thread
from tkinter import ttk
from typing import Callable, ClassVar, Optional

from wintoucher.data.dot import Dot, FlickDot, PinchDot, RotateDot
from wintoucher.gui.tkutils import DetailDict
from wintoucher.util.key import key_to_str
from wintoucher.util.touch import TouchManager


@dataclass
class DotView(ABC):
    """
    A view class for a dot.
    """

    dot: Dot

    COLOR: ClassVar[str] = "red"
    RADIUS: ClassVar[int] = 10
    KEY_LABEL_OFFSET_X: ClassVar[int] = 0
    KEY_LABEL_OFFSET_Y: ClassVar[int] = 25

    @property
    def color(self):
        return self.COLOR if self.dot.key else "snow4"

    def draw(self, canvas: tk.Canvas, outlined: bool):
        """
        Draw the dot on the canvas.

        Args:
            canvas (tk.Canvas): The canvas to draw the dot on.
            outlined (bool): Whether to outline the dot.
        """

        # Create dot
        canvas.create_oval(
            self.dot.x - self.RADIUS,
            self.dot.y - self.RADIUS,
            self.dot.x + self.RADIUS,
            self.dot.y + self.RADIUS,
            fill=self.color,
            outline="red" if outlined else "",
        )

        # Create key text
        if self.dot.key:
            text = canvas.create_text(
                self.dot.x + self.KEY_LABEL_OFFSET_X,
                self.dot.y + self.KEY_LABEL_OFFSET_Y,
                text=key_to_str(self.dot.key),
                fill="black",
            )
            text_bbox = canvas.bbox(text)

            # Add padding to bbox
            PADDING = (5, 2)
            text_bbox = (
                text_bbox[0] - PADDING[0],
                text_bbox[1] - PADDING[1],
                text_bbox[2] + PADDING[0],
                text_bbox[3] + PADDING[1],
            )

            rect = canvas.create_rectangle(text_bbox, fill="#E1E1E1", outline="#ADADAD")
            canvas.tag_lower(rect, text)

    def detail(self, draw_dots: Callable[[], None]) -> DetailDict:
        """
        Get the detail view for the dot.

        Args:
            draw_dots (Callable[[], None]): A callback function to redraw the dots.

        Returns:
            DetailDict: The detail view for the dot.
        """

        return {
            "Type": {
                "widget_type": ttk.Label,
                "params": {"text": self.dot.__class__.__name__},
            },
            "Key": {
                "widget_type": ttk.Label,
                "params": {"text": key_to_str(self.dot.key)},
            },
        }


@dataclass
class PressDotView(DotView):
    """
    A view class for a PressDot.
    """

    COLOR: ClassVar[str] = "green"


@dataclass
class FlickDotView(DotView):
    """
    A view class for a FlickDot.
    """

    dot: FlickDot
    COLOR: ClassVar[str] = "orange"
    KEY_LABEL_OFFSET_Y: ClassVar[int] = 40
    ARROW_LENGTH: ClassVar[int] = 25
    ARROW_WIDTH: ClassVar[int] = 5
    running: bool = False

    def draw(self, canvas: tk.Canvas, outlined: bool):
        # Create arrow line
        dx, dy = (
            self.ARROW_LENGTH * cos(radians(self.dot.angle.get())),
            self.ARROW_LENGTH * sin(radians(self.dot.angle.get())),
        )
        canvas.create_line(
            self.dot.x - dx,
            self.dot.y - dy,
            self.dot.x + dx,
            self.dot.y + dy,
            arrow=tk.LAST,
            fill=self.color,
            width=self.ARROW_WIDTH,
        )

        # Create dot
        super().draw(canvas, outlined)

    def detail(self, draw_dots: Callable[[], None]) -> DetailDict:
        def on_angle_change_factory(var: tk.IntVar):
            def round_var(step: int):
                value = var.get()
                value = round(value / step) * step
                var.set(value)

            def on_angle_change(_=None):
                round_var(1)
                draw_dots()

            return on_angle_change

        return {
            **super().detail(draw_dots),
            "Angle": {
                "widget_type": ttk.Spinbox,
                "params": {
                    "from_": 0,
                    "to": 360,
                    "textvariable": self.dot.angle,
                    "state": "readonly",
                    "command": on_angle_change_factory(self.dot.angle),
                },
            },
            "": {
                "widget_type": ttk.Scale,
                "params": {
                    "from_": 0,
                    "to": 360,
                    "variable": self.dot.angle,
                    "orient": tk.HORIZONTAL,
                    "command": on_angle_change_factory(self.dot.angle),
                },
            },
            "Distance": {
                "widget_type": ttk.Spinbox,
                "params": {
                    "from_": 0,
                    "to": 360,
                    "textvariable": self.dot.distance,
                    "state": "readonly",
                    "command": on_angle_change_factory(self.dot.distance),
                },
            },
        }

    def run(self, touch_manager: TouchManager, cx: Optional[int] = None, cy: Optional[int] = None):
        """
        Run the flick. This will simulate a flick on the screen.
        """

        if not self.running:

            def runner():
                self.running = True

                x: float = cx if cx is not None else self.dot.x
                y: float = cy if cy is not None else self.dot.y
                dx = cos(radians(self.dot.angle.get())) * self.dot.delta
                dy = sin(radians(self.dot.angle.get())) * self.dot.delta

                touch_manager.down(self.dot.id, int(x), int(y))
                touch_manager.apply_touches()

                for _ in range(self.dot.distance.get() // self.dot.delta):
                    if not self.running:
                        return
                    x += dx
                    y += dy
                    touch_manager.move(self.dot.id, int(x), int(y))
                    touch_manager.apply_touches()
                    time.sleep(self.dot.delay)

                touch_manager.up(self.dot.id)
                touch_manager.apply_touches()
                self.running = False

            thread = Thread(target=runner)
            thread.start()

    def stop(self):
        """
        Stop the flick.
        """

        self.running = False


@dataclass
class PinchDotView(DotView):
    """
    A view class for a PinchDot.
    """

    dot: PinchDot
    COLOR: ClassVar[str] = "DeepPink"
    KEY_LABEL_OFFSET_Y: ClassVar[int] = 40
    running: bool = False

    def draw(self, canvas: tk.Canvas, outlined: bool):
        super().draw(canvas, outlined)
        dist = self.dot.start_distance.get()
        end_dist = self.dot.end_distance.get()
        canvas.create_line(
            self.dot.x - dist, self.dot.y,
            self.dot.x - end_dist, self.dot.y,
            arrow=tk.LAST, fill=self.color, width=3,
        )
        canvas.create_line(
            self.dot.x + dist, self.dot.y,
            self.dot.x + end_dist, self.dot.y,
            arrow=tk.LAST, fill=self.color, width=3,
        )

    def detail(self, draw_dots: Callable[[], None]) -> DetailDict:
        def on_change_factory(var: tk.IntVar):
            def on_change(_=None):
                value = var.get()
                var.set(round(value))
                draw_dots()
            return on_change

        return {
            **super().detail(draw_dots),
            "Start Dist": {
                "widget_type": ttk.Spinbox,
                "params": {
                    "from_": 10,
                    "to": 500,
                    "textvariable": self.dot.start_distance,
                    "state": "readonly",
                    "command": on_change_factory(self.dot.start_distance),
                },
            },
            "End Dist": {
                "widget_type": ttk.Spinbox,
                "params": {
                    "from_": 10,
                    "to": 500,
                    "textvariable": self.dot.end_distance,
                    "state": "readonly",
                    "command": on_change_factory(self.dot.end_distance),
                },
            },
        }

    def run(self, touch_manager: TouchManager, cx: Optional[int] = None, cy: Optional[int] = None):
        if not self.running:
            def runner():
                self.running = True
                x = cx if cx is not None else self.dot.x
                y = cy if cy is not None else self.dot.y
                start_dist = self.dot.start_distance.get()
                end_dist = self.dot.end_distance.get()
                if start_dist == end_dist:
                    self.running = False
                    return
                steps = max(1, abs(end_dist - start_dist) // self.dot.delta)
                for step in range(steps + 1):
                    if not self.running:
                        return
                    t = step / steps
                    dist = start_dist + (end_dist - start_dist) * t
                    x1, y1 = int(x + dist), y
                    x2, y2 = int(x - dist), y
                    if step == 0:
                        touch_manager.down(self.dot.id, x1, y1)
                        touch_manager.down(self.dot.id2, x2, y2)
                    else:
                        touch_manager.move(self.dot.id, x1, y1)
                        touch_manager.move(self.dot.id2, x2, y2)
                    touch_manager.apply_touches()
                    time.sleep(self.dot.delay)
                touch_manager.up(self.dot.id)
                touch_manager.up(self.dot.id2)
                touch_manager.apply_touches()
                self.running = False
            thread = Thread(target=runner)
            thread.start()

    def stop(self):
        self.running = False


@dataclass
class RotateDotView(DotView):
    """
    A view class for a RotateDot.
    """

    dot: RotateDot
    COLOR: ClassVar[str] = "DodgerBlue"
    KEY_LABEL_OFFSET_Y: ClassVar[int] = 40
    running: bool = False

    def draw(self, canvas: tk.Canvas, outlined: bool):
        super().draw(canvas, outlined)
        radius = self.dot.radius.get()
        angle = self.dot.rotation_angle.get()
        canvas.create_arc(
            self.dot.x - radius, self.dot.y - radius,
            self.dot.x + radius, self.dot.y + radius,
            start=0, extent=angle,
            style=tk.ARC, outline=self.color, width=3,
        )

    def detail(self, draw_dots: Callable[[], None]) -> DetailDict:
        def on_change_factory(var: tk.IntVar):
            def on_change(_=None):
                value = var.get()
                var.set(round(value))
                draw_dots()
            return on_change

        return {
            **super().detail(draw_dots),
            "Angle": {
                "widget_type": ttk.Spinbox,
                "params": {
                    "from_": -360,
                    "to": 360,
                    "textvariable": self.dot.rotation_angle,
                    "state": "readonly",
                    "command": on_change_factory(self.dot.rotation_angle),
                },
            },
            "": {
                "widget_type": ttk.Scale,
                "params": {
                    "from_": -360,
                    "to": 360,
                    "variable": self.dot.rotation_angle,
                    "orient": tk.HORIZONTAL,
                    "command": on_change_factory(self.dot.rotation_angle),
                },
            },
            "Radius": {
                "widget_type": ttk.Spinbox,
                "params": {
                    "from_": 10,
                    "to": 500,
                    "textvariable": self.dot.radius,
                    "state": "readonly",
                    "command": on_change_factory(self.dot.radius),
                },
            },
        }

    def run(self, touch_manager: TouchManager, cx: Optional[int] = None, cy: Optional[int] = None):
        if not self.running:
            def runner():
                self.running = True
                x = cx if cx is not None else self.dot.x
                y = cy if cy is not None else self.dot.y
                radius = self.dot.radius.get()
                total_angle = self.dot.rotation_angle.get()
                if total_angle == 0 or radius == 0:
                    self.running = False
                    return
                steps = max(1, abs(total_angle) // self.dot.delta)
                for step in range(steps + 1):
                    if not self.running:
                        return
                    t = step / steps
                    angle_rad = radians(total_angle * t)
                    x1 = int(x + radius * cos(angle_rad))
                    y1 = int(y + radius * sin(angle_rad))
                    x2 = int(x - radius * cos(angle_rad))
                    y2 = int(y - radius * sin(angle_rad))
                    if step == 0:
                        touch_manager.down(self.dot.id, x1, y1)
                        touch_manager.down(self.dot.id2, x2, y2)
                    else:
                        touch_manager.move(self.dot.id, x1, y1)
                        touch_manager.move(self.dot.id2, x2, y2)
                    touch_manager.apply_touches()
                    time.sleep(self.dot.delay)
                touch_manager.up(self.dot.id)
                touch_manager.up(self.dot.id2)
                touch_manager.apply_touches()
                self.running = False
            thread = Thread(target=runner)
            thread.start()

    def stop(self):
        self.running = False
