from evdev import InputDevice, ecodes
import pyudev
import uinput
import subprocess
import argparse
import sys


def find_touchscreen_udev():
    context = pyudev.Context()
    for device in context.list_devices(subsystem="input"):
        if (
            device.properties.get("ID_INPUT_TOUCHSCREEN") == "1"
            and device.device_node is not None
        ):
            dev = InputDevice(device.device_node)
            return dev
    print("Touch device not found")
    sys.exit()


def apply_rotation(x, y, rotation, max_x, max_y):
    """Transform coordinates based on rotation"""
    if rotation == 0:
        return x, y
    elif rotation == 180:
        return (max_x - x, max_y - y)
    elif rotation == 90:
        return (y, max_x - x)
    elif rotation == 270:
        return (max_y - y, x)
    else:
        raise ValueError("Invalid rotation value")


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


def toggle_original_input(touch_dev_name, enabled):
    if enabled:
        subprocess.run(
            ["hyprctl", "-r", "keyword", f"device[{touch_dev_name}]:enabled", "1"]
        )
        print(f"{touch_dev_name} enabled")
    else:
        subprocess.run(
            ["hyprctl", "-r", "keyword", f"device[{touch_dev_name}]:enabled", "0"]
        )
        print(f"{touch_dev_name} disabled")


def get_device_xy_limit(touch_dev):
    max_x = max_y = 0
    for abs_code, abs_info in touch_dev.capabilities().get(ecodes.EV_ABS, []):
        if abs_code == ecodes.ABS_X:
            max_x = abs_info.max
        elif abs_code == ecodes.ABS_Y:
            max_y = abs_info.max
    return max_x, max_y


def capture_report(touch_dev_name, max_x, max_y, rotation):
    print(f"Capturing input from {touch_dev_name}")
    print(f"Max X: {max_x}, Max Y: {max_y}")
    print(f"Active rotation: {rotation}°")


def qualify(x):
    qualified_x = 0
    if x > 0:
        qualified_x = 1
    if x < 0:
        qualified_x = -1
    return qualified_x


args = parse_arguments()
ORIENTATION = args.rotate
TAP_MOVEMENT_THRESHOLD = args.tap_threshold
TAP_DURATION_THRESHOLD = args.tap_duration
SCROLL_MOVEMENT_THRESHOLD = args.scroll_threshold
SCROLL_SENSITIVITY = args.scroll_sensitivity
CURSOR_SENSITIVITY = args.cursor_sensitivity

device = uinput.Device(
    [
        uinput.REL_X,
        uinput.REL_Y,
        uinput.BTN_LEFT,
        uinput.BTN_RIGHT,
        uinput.REL_WHEEL,
        uinput.REL_HWHEEL,
    ]
)

try:
    # load original input
    touch_dev = find_touchscreen_udev()

    # variable initialization
    touch_dev_name = str(touch_dev.name).replace(" ", "-").lower()
    max_x, max_y = get_device_xy_limit(touch_dev)
    touch_start_time = None
    active_touches = {}
    current_slot = 0
    already_scrolled = False
    already_moved = False
    three_finger_down = False

    capture_report(touch_dev_name, max_x, max_y, ORIENTATION)
    toggle_original_input(touch_dev_name, False)

    for event in touch_dev.read_loop():
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
                        "last_x": None,
                        "last_y": None,
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
            if len(active_touches) != 0:
                print(active_touches)
                avg_x = sum(t["current_x"] for t in active_touches.values()) / len(
                    active_touches
                )
                avg_y = sum(t["current_y"] for t in active_touches.values()) / len(
                    active_touches
                )
                rx, ry = apply_rotation(
                    avg_x,
                    avg_y,
                    ORIENTATION,
                    max_x,
                    max_y,
                )
                if not already_moved:
                    if all(
                        abs(t["current_x"] - t["initial_x"]) > TAP_MOVEMENT_THRESHOLD
                        or abs(t["current_y"] - t["initial_y"]) > TAP_MOVEMENT_THRESHOLD
                        for t in active_touches.values()
                    ):
                        already_moved = True
                elif (
                    active_touches[current_slot]["last_x"] is not None
                    and active_touches[current_slot]["last_y"] is not None
                ):
                    if len(active_touches) == 1:
                        rel_x = int(
                            (rx - active_touches[current_slot]["last_x"])
                            * CURSOR_SENSITIVITY
                        )
                        rel_y = int(
                            (ry - active_touches[current_slot]["last_y"])
                            * CURSOR_SENSITIVITY
                        )
                        device.emit(uinput.REL_X, rel_x)
                        device.emit(uinput.REL_Y, rel_y)
                    elif len(active_touches) == 2 and not already_scrolled:
                        rel_x = (
                            qualify(rx - active_touches[current_slot]["last_x"])
                            * SCROLL_SENSITIVITY
                        )
                        rel_y = (
                            qualify(ry - active_touches[current_slot]["last_y"])
                            * SCROLL_SENSITIVITY
                        )
                        device.emit(uinput.REL_HWHEEL, -rel_x)
                        device.emit(uinput.REL_WHEEL, rel_y)
                        already_scrolled = True
                    elif len(active_touches) == 3:
                        if not three_finger_down:
                            device.emit(uinput.BTN_LEFT, 1)
                            three_finger_down = True
                            rel_x = int(
                                (rx - active_touches[current_slot]["last_x"])
                                * CURSOR_SENSITIVITY
                            )
                            rel_y = int(
                                (ry - active_touches[current_slot]["last_y"])
                                * CURSOR_SENSITIVITY
                            )
                            device.emit(uinput.REL_X, rel_x)
                            device.emit(uinput.REL_Y, rel_y)
                (
                    active_touches[current_slot]["last_x"],
                    active_touches[current_slot]["last_y"],
                ) = rx, ry

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
                            device.emit(uinput.BTN_RIGHT, 1)
                        if len(active_touches) <= 1:
                            device.emit(uinput.BTN_LEFT, 1)
                device.emit(uinput.BTN_LEFT, 0)
                three_finger_down = already_scrolled = already_moved = False
                active_touches.clear()
except KeyboardInterrupt:
    toggle_original_input(touch_dev_name, True)
    print("Restored touchscreen input")
