from typing import Literal
from evdev import InputDevice, ecodes
import pyudev
import uinput
import subprocess
import argparse
import sys


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rotate",
        type=int,
        choices=[0, 90, 180, 270],
        default=270,
        help="Screen rotation (0, 90, 180, 270 degrees)",
    )
    parser.add_argument(
        "--tap-threshold",
        type=int,
        default=50,
        help="Tap movement threshold",
    )
    parser.add_argument(
        "--tap-duration",
        type=float,
        default=0.12,
        help="Tap duration threshold",
    )
    parser.add_argument(
        "--scroll-threshold",
        type=int,
        default=50,
        help="Scroll movement threshold",
    )
    parser.add_argument(
        "--scroll-sensitivity",
        type=int,
        default=2,
        help="Scroll sensitivity",
    )
    parser.add_argument(
        "--cursor-sensitivity",
        type=float,
        default=0.6,
        help="Cursor sensitivity",
    )

    return parser.parse_args()


class TrackPad:
    def __init__(self) -> None:
        self.scroll_sensitivity = args.scroll_sensitivity
        self.cursor_sensitivity = args.cursor_sensitivity
        self.device = uinput.Device(
            [
                uinput.REL_X,
                uinput.REL_Y,
                uinput.BTN_LEFT,
                uinput.BTN_RIGHT,
                uinput.REL_WHEEL,
                uinput.REL_HWHEEL,
            ]
        )

    def _qualify(self, x):
        qualified_x = 0
        if x > 0:
            qualified_x = 1
        if x < 0:
            qualified_x = -1
        return qualified_x

    def move_cursor(self, current_x, current_y, last_x, last_y):
        rel_x = int((current_x - last_x) * self.cursor_sensitivity)
        rel_y = int((current_y - last_y) * self.cursor_sensitivity)
        self.device.emit(uinput.REL_X, rel_x)
        self.device.emit(uinput.REL_Y, rel_y)

    def scroll_wheel(self, current_x, current_y, last_x, last_y):
        rel_x = self._qualify(current_x - last_x) * self.scroll_sensitivity
        rel_y = self._qualify(current_y - last_y) * self.scroll_sensitivity
        self.device.emit(uinput.REL_HWHEEL, -rel_x)
        self.device.emit(uinput.REL_WHEEL, rel_y)

    def click_button(
        self, button: Literal["right", "left"], status: Literal["down", "up", "click"]
    ):
        if button == "left":
            if status == "down":
                self.device.emit(uinput.BTN_LEFT, 1)
            elif status == "up":
                self.device.emit(uinput.BTN_LEFT, 0)
            else:
                self.device.emit(uinput.BTN_LEFT, 1)
                self.device.emit(uinput.BTN_LEFT, 0)
        else:
            if status == "down":
                self.device.emit(uinput.BTN_RIGHT, 1)
            elif status == "up":
                self.device.emit(uinput.BTN_RIGHT, 0)
            else:
                self.device.emit(uinput.BTN_RIGHT, 1)
                self.device.emit(uinput.BTN_RIGHT, 0)


class NoValidDeviceError(Exception):
    """Exception raised when no valid touchscreen device is found."""

    def __init__(self, message="No touchscreen detected"):
        super().__init__(message)


class TouchscreenHandler:
    def __init__(self) -> None:
        self.rotation = args.rotate
        self.device = self._find_touchscreen()
        self.name = str(self.device.name).replace(" ", "-").lower()
        self.max_x, self.max_y = self._get_device_xy_limit()
        self._capture_report()
        self.toggle_input(False)

    def events_loop(self):
        return self.device.read_loop()

    def _find_touchscreen(self):
        context = pyudev.Context()
        for device in context.list_devices(subsystem="input"):
            if (
                device.properties.get("ID_INPUT_TOUCHSCREEN") == "1"
                and device.device_node is not None
            ):
                dev = InputDevice(device.device_node)
                return dev
        raise NoValidDeviceError("no touchscreen detected")

    def _get_device_xy_limit(self):
        max_x = max_y = 0
        for abs_code, abs_info in self.device.capabilities().get(ecodes.EV_ABS, []):
            if abs_code == ecodes.ABS_X:
                max_x = abs_info.max
            elif abs_code == ecodes.ABS_Y:
                max_y = abs_info.max
        return max_x, max_y

    def _capture_report(self):
        print(f"Capturing input from {self.name}")
        print(f"Max X: {self.max_x}, Max Y: {self.max_y}")
        print(f"Active rotation: {self.rotation}°")

    def toggle_input(self, enabled):
        if enabled:
            subprocess.run(
                ["hyprctl", "-r", "keyword", f"device[{self.name}]:enabled", "1"]
            )
            print(f"{self.name} enabled")
        else:
            subprocess.run(
                ["hyprctl", "-r", "keyword", f"device[{self.name}]:enabled", "0"]
            )
            print(f"{self.name} disabled")

    def apply_rotation(self, x, y):
        if self.rotation == 0:
            return x, y
        elif self.rotation == 180:
            return (self.max_x - x, self.max_y - y)
        elif self.rotation == 90:
            return (y, self.max_x - x)
        elif self.rotation == 270:
            return (self.max_y - y, x)
        else:
            raise ValueError("Invalid rotation value")


args = parse_arguments()

TAP_MOVEMENT_THRESHOLD = args.tap_threshold
TAP_DURATION_THRESHOLD = args.tap_duration
SCROLL_MOVEMENT_THRESHOLD = args.scroll_threshold


track_pad = TrackPad()
touchscreen_handler = TouchscreenHandler()

# variable initialization
touch_start_time = None
last_x = last_y = None
active_touches = {}
current_slot = 0
already_scrolled = False
already_moved = False
already_dragged = False


try:
    for event in touchscreen_handler.events_loop():
        if event.type == ecodes.EV_ABS:
            if event.code == ecodes.ABS_MT_SLOT:
                current_slot = event.value

            elif event.code == ecodes.ABS_MT_TRACKING_ID:
                if event.value != -1:
                    active_touches[current_slot] = {
                        "initial_x": None,
                        "initial_y": None,
                        "current_x": None,
                        "current_y": None,
                    }

            elif event.code == ecodes.ABS_MT_POSITION_X:
                if current_slot in active_touches:
                    if active_touches[current_slot]["initial_x"] is None:
                        active_touches[current_slot]["initial_x"] = event.value
                    active_touches[current_slot]["current_x"] = event.value

            elif event.code == ecodes.ABS_MT_POSITION_Y:
                if current_slot in active_touches:
                    if active_touches[current_slot]["initial_y"] is None:
                        active_touches[current_slot]["initial_y"] = event.value
                    active_touches[current_slot]["current_y"] = event.value

        elif event.type == ecodes.EV_SYN and event.code == ecodes.SYN_REPORT:
            valid_touches_set = [
                t for t in active_touches.values() if t["current_x"] and t["current_y"]
            ]
            if len(valid_touches_set) != 0:
                avg_x = sum(t["current_x"] for t in valid_touches_set) / len(
                    valid_touches_set
                )
                avg_y = sum(t["current_y"] for t in valid_touches_set) / len(
                    valid_touches_set
                )
                rx, ry = touchscreen_handler.apply_rotation(
                    avg_x,
                    avg_y,
                )
                if not already_moved:
                    if all(
                        abs(t["current_x"] - t["initial_x"]) > TAP_MOVEMENT_THRESHOLD
                        or abs(t["current_y"] - t["initial_y"]) > TAP_MOVEMENT_THRESHOLD
                        for t in active_touches.values()
                    ):
                        already_moved = True
                elif last_x is not None and last_y is not None:
                    if len(active_touches) == 1:
                        track_pad.move_cursor(
                            current_x=rx,
                            current_y=ry,
                            last_x=last_x,
                            last_y=last_y,
                        )
                    elif len(active_touches) == 2 and not already_scrolled:
                        track_pad.scroll_wheel(
                            current_x=rx,
                            current_y=ry,
                            last_x=last_x,
                            last_y=last_y,
                        )
                        already_scrolled = True
                    elif len(active_touches) == 3:
                        if not already_dragged:
                            track_pad.click_button("left", "down")
                            already_dragged = True
                        track_pad.move_cursor(
                            current_x=rx,
                            current_y=ry,
                            last_x=last_x,
                            last_y=last_y,
                        )
                last_x, last_y = rx, ry

        elif event.type == ecodes.EV_KEY and event.code == ecodes.BTN_TOUCH:
            if event.value == 1:  # Touch down
                touch_start_time = event.timestamp()
            elif event.value == 0:  # Touch up
                if touch_start_time is not None:
                    touch_duration = event.timestamp() - touch_start_time
                    finger_tap = all(
                        touch_duration < TAP_DURATION_THRESHOLD
                        and abs(t["current_x"] - t["initial_x"])
                        < TAP_MOVEMENT_THRESHOLD
                        and abs(t["current_y"] - t["initial_y"])
                        < TAP_MOVEMENT_THRESHOLD
                        for t in active_touches.values()
                    )
                    if finger_tap:
                        if len(active_touches) == 2:
                            track_pad.click_button("right", "down")
                        if len(active_touches) == 1:
                            track_pad.click_button("left", "down")
                track_pad.click_button("right", "up")
                track_pad.click_button("left", "up")
                already_dragged = already_scrolled = already_moved = False
                active_touches.clear()
                # do not need to clear last_xy explicitly here
                # as my if logic, the first coords report after touch is ignored
except KeyboardInterrupt:
    touchscreen_handler.toggle_input(True)
    print("Restored touchscreen input")
