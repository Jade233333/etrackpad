from typing import Literal
from evdev import InputDevice, ecodes
import pyudev
import uinput
import argparse
# import subprocess


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
        "--movement-threshold",
        type=int,
        default=50,
        help="movement threshold to distinguish between a tap and cursor movement",
    )
    parser.add_argument(
        "--duration_threshold",
        type=float,
        default=0.12,
        help="Time duration threshold to distinguish between a tap and cursor movement",
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
    def __init__(self, max_x, max_y):
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
        self.max_x, self.max_y = max_x, max_y
        self.rotation = args.rotate

    def _apply_rotation(self, x, y):
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

    def _qualify(self, x):
        qualified_x = 0
        if x > 0:
            qualified_x = 1
        if x < 0:
            qualified_x = -1
        return qualified_x

    def move_cursor(self, current_x, current_y, last_x, last_y):
        current_x, current_y = self._apply_rotation(current_x, current_y)
        last_x, last_y = self._apply_rotation(last_x, last_y)
        rel_x = int((current_x - last_x) * self.cursor_sensitivity)
        rel_y = int((current_y - last_y) * self.cursor_sensitivity)
        self.device.emit(uinput.REL_X, rel_x)
        self.device.emit(uinput.REL_Y, rel_y)

    def scroll_wheel(self, current_x, current_y, last_x, last_y):
        current_x, current_y = self._apply_rotation(current_x, current_y)
        last_x, last_y = self._apply_rotation(last_x, last_y)
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
    def __init__(self):
        self.rotation = args.rotate
        self.device = self._find_touchscreen()
        self.name = str(self.device.name).replace(" ", "-").lower()
        self.max_x, self.max_y = self._get_xy_limit()
        self._capture_report()

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

    def _get_capabilities(self) -> list:
        capabilities = self.device.capabilities().get(ecodes.EV_ABS, [])
        return capabilities

    def _get_xy_limit(self):
        max_x = max_y = 0
        capabilities = self._get_capabilities()
        for abs_code, abs_info in capabilities:
            if abs_code == ecodes.ABS_X:
                max_x = abs_info.max
            elif abs_code == ecodes.ABS_Y:
                max_y = abs_info.max
        return max_x, max_y

    def _capture_report(self):
        print(f"Capturing input from {self.name}")
        print(f"Max X: {self.max_x}, Max Y: {self.max_y}")
        print(f"Active rotation: {self.rotation}°")

    # def toggle_input(self, enabled):
    #     if enabled:
    #         print(f"enabling {self.name}")
    #         subprocess.run(
    #             ["hyprctl", "-r", "keyword", f"device[{self.name}]:enabled", "1"]
    #         )
    #     else:
    #         print(f"disabling {self.name}")
    #         subprocess.run(
    #             ["hyprctl", "-r", "keyword", f"device[{self.name}]:enabled", "0"]
    #         )


class GestureRecognizer:
    def __init__(self):
        self.movement_threshold = args.movement_threshold
        self.duration_threshold = args.duration_threshold
        self.touch_start_time = None
        self.last_x = None
        self.last_y = None
        self.active_touches = {}
        self.current_slot = 0
        self.already_scrolled = False
        self.already_moved = False
        self.already_dragged = False

    def process_event(self, event):
        # Process ABS events for multitouch data
        if event.type == ecodes.EV_ABS:
            if event.code == ecodes.ABS_MT_SLOT:
                self.current_slot = event.value

            elif event.code == ecodes.ABS_MT_TRACKING_ID:
                if event.value != -1:
                    self.active_touches[self.current_slot] = {
                        "initial_x": None,
                        "initial_y": None,
                        "current_x": None,
                        "current_y": None,
                    }

            elif event.code == ecodes.ABS_MT_POSITION_X:
                if self.current_slot in self.active_touches:
                    if self.active_touches[self.current_slot]["initial_x"] is None:
                        self.active_touches[self.current_slot]["initial_x"] = (
                            event.value
                        )
                    self.active_touches[self.current_slot]["current_x"] = event.value

            elif event.code == ecodes.ABS_MT_POSITION_Y:
                if self.current_slot in self.active_touches:
                    if self.active_touches[self.current_slot]["initial_y"] is None:
                        self.active_touches[self.current_slot]["initial_y"] = (
                            event.value
                        )
                    self.active_touches[self.current_slot]["current_y"] = event.value

        # Process synchronization events to generate actions
        elif event.type == ecodes.EV_SYN and event.code == ecodes.SYN_REPORT:
            valid_touches = [
                t
                for t in self.active_touches.values()
                if t["current_x"] is not None and t["current_y"] is not None
            ]
            if valid_touches:
                rx = sum(t["current_x"] for t in valid_touches) / len(valid_touches)
                ry = sum(t["current_y"] for t in valid_touches) / len(valid_touches)
                if not self.already_moved:
                    if all(
                        abs(t["current_x"] - t["initial_x"]) > self.movement_threshold
                        or abs(t["current_y"] - t["initial_y"])
                        > self.movement_threshold
                        for t in self.active_touches.values()
                    ):
                        self.already_moved = True
                elif self.last_x is not None and self.last_y is not None:
                    if len(self.active_touches) == 1:
                        yield (
                            "move_cursor",
                            {
                                "current_x": rx,
                                "current_y": ry,
                                "last_x": self.last_x,
                                "last_y": self.last_y,
                            },
                        )
                    elif len(self.active_touches) == 2 and not self.already_scrolled:
                        yield (
                            "scroll_wheel",
                            {
                                "current_x": rx,
                                "current_y": ry,
                                "last_x": self.last_x,
                                "last_y": self.last_y,
                            },
                        )
                        self.already_scrolled = True
                    elif len(self.active_touches) == 3:
                        if not self.already_dragged:
                            yield ("click_button", {"button": "left", "action": "down"})
                            self.already_dragged = True
                        yield (
                            "move_cursor",
                            {
                                "current_x": rx,
                                "current_y": ry,
                                "last_x": self.last_x,
                                "last_y": self.last_y,
                            },
                        )
                self.last_x, self.last_y = rx, ry

        # Process touch key events to generate click actions
        elif event.type == ecodes.EV_KEY and event.code == ecodes.BTN_TOUCH:
            if event.value == 1:
                self.touch_start_time = event.timestamp()
            elif event.value == 0:
                if self.touch_start_time is not None:
                    touch_duration = event.timestamp() - self.touch_start_time
                    finger_tap = all(
                        touch_duration < self.duration_threshold
                        and abs(t["current_x"] - t["initial_x"])
                        < self.movement_threshold
                        and abs(t["current_y"] - t["initial_y"])
                        < self.movement_threshold
                        for t in self.active_touches.values()
                    )
                    if finger_tap:
                        if len(self.active_touches) == 2:
                            yield (
                                "click_button",
                                {"button": "right", "action": "down"},
                            )
                        elif len(self.active_touches) == 1:
                            yield ("click_button", {"button": "left", "action": "down"})
                # Release click for both buttons
                yield ("click_button", {"button": "right", "action": "up"})
                yield ("click_button", {"button": "left", "action": "up"})
                # Reset states
                self.already_dragged = False
                self.already_scrolled = False
                self.already_moved = False
                self.active_touches.clear()


args = parse_arguments()
touchscreen_handler = TouchscreenHandler()
track_pad = TrackPad(touchscreen_handler.max_x, touchscreen_handler.max_y)
gesture_recognizer = GestureRecognizer()

for event in touchscreen_handler.events_loop():
    for action, params in gesture_recognizer.process_event(event):
        if action == "move_cursor":
            track_pad.move_cursor(**params)
        elif action == "scroll_wheel":
            track_pad.scroll_wheel(**params)
        elif action == "click_button":
            track_pad.click_button(params["button"], params["action"])
