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


def all_not_none(active_touches):
    for touch in active_touches.values():
        for record in touch.values():
            if record is None:
                return False
    return True


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
    three_finger_down = False
    touch_dev_name = str(touch_dev.name).replace(" ", "-").lower()
    max_x, max_y = get_device_xy_limit(touch_dev)
    last_rx = last_ry = 0
    touch_start_time = None
    active_touches = {}  # Key: slot, Value: dict with tracking_id, start_time, x, y
    current_slot = 0  # to track the current slot being updated
    scroll_mode = False
    scroll_initial_avg_x = None
    scroll_initial_avg_y = None
    already_scrolled = False

    capture_report(touch_dev_name, max_x, max_y, ORIENTATION)
    toggle_original_input(touch_dev_name, False)

    for event in touch_dev.read_loop():
        if event.type == ecodes.EV_ABS:
            if event.code == ecodes.ABS_MT_SLOT:
                current_slot = (
                    event.value
                )  # update the current slot for subsequent MT events

            elif event.code == ecodes.ABS_MT_TRACKING_ID:
                if event.value == -1:
                    # Finger lifted: mark it in active_touches
                    if current_slot in active_touches:
                        active_touches[current_slot]["lifted"] = True
                else:
                    active_touches[current_slot] = {
                        "tracking_id": event.value,
                        "start_time": event.timestamp(),
                        "initial_x": None,
                        "initial_y": None,
                        "x": None,
                        "y": None,
                        "lifted": False,
                    }

            elif event.code == ecodes.ABS_MT_POSITION_X:
                if current_slot in active_touches:
                    # Save initial position once
                    if active_touches[current_slot]["initial_x"] is None:
                        active_touches[current_slot]["initial_x"] = event.value
                    active_touches[current_slot]["x"] = event.value

            elif event.code == ecodes.ABS_MT_POSITION_Y:
                if current_slot in active_touches:
                    if active_touches[current_slot]["initial_y"] is None:
                        active_touches[current_slot]["initial_y"] = event.value
                    active_touches[current_slot]["y"] = event.value

        elif event.type == ecodes.EV_SYN and event.code == ecodes.SYN_REPORT:
            if all_not_none(active_touches):
                if len(active_touches) == 1:
                    finger_move = all(
                        abs(t["x"] - t["initial_x"]) > TAP_MOVEMENT_THRESHOLD
                        or abs(t["y"] - t["initial_y"]) > TAP_MOVEMENT_THRESHOLD
                        for t in active_touches.values()
                    )
                    if finger_move:
                        rx, ry = apply_rotation(
                            active_touches[current_slot]["x"],
                            active_touches[current_slot]["y"],
                            ORIENTATION,
                            max_x,
                            max_y,
                        )
                        if last_rx is not None and last_ry is not None:
                            rel_x = int((rx - last_rx) * CURSOR_SENSITIVITY)
                            rel_y = int((ry - last_ry) * CURSOR_SENSITIVITY)
                            device.emit(uinput.REL_X, rel_x)
                            device.emit(uinput.REL_Y, rel_y)
                        last_rx, last_ry = rx, ry
                elif len(active_touches) == 2 and not already_scrolled:
                    avg_x = sum(t["x"] for t in active_touches.values()) / 2
                    avg_y = sum(t["y"] for t in active_touches.values()) / 2
                    finger_move = all(
                        abs(t["x"] - t["initial_x"]) > SCROLL_MOVEMENT_THRESHOLD
                        or abs(t["y"] - t["initial_y"]) > SCROLL_MOVEMENT_THRESHOLD
                        for t in active_touches.values()
                    )
                    if finger_move:
                        rx, ry = apply_rotation(
                            avg_x,
                            avg_y,
                            ORIENTATION,
                            max_x,
                            max_y,
                        )
                        if last_rx is not None and last_ry is not None:
                            rel_x = qualify(rx - last_rx) * SCROLL_SENSITIVITY
                            rel_y = qualify(ry - last_ry) * SCROLL_SENSITIVITY
                            device.emit(uinput.REL_HWHEEL, rel_x)
                            device.emit(uinput.REL_WHEEL, rel_y)
                            already_scrolled = True
                        last_rx, last_ry = rx, ry
                elif len(active_touches) == 3:
                    avg_x = sum(t["x"] for t in active_touches.values()) / 3
                    avg_y = sum(t["y"] for t in active_touches.values()) / 3
                    finger_move = all(
                        abs(t["x"] - t["initial_x"]) > TAP_MOVEMENT_THRESHOLD
                        or abs(t["y"] - t["initial_y"]) > TAP_MOVEMENT_THRESHOLD
                        for t in active_touches.values()
                    )
                    if finger_move:
                        if not three_finger_down:
                            device.emit(uinput.BTN_LEFT, 1)
                            three_finger_down = True
                        rx, ry = apply_rotation(
                            avg_x,
                            avg_y,
                            ORIENTATION,
                            max_x,
                            max_y,
                        )
                        if last_rx is not None and last_ry is not None:
                            rel_x = int((rx - last_rx) * CURSOR_SENSITIVITY)
                            rel_y = int((ry - last_ry) * CURSOR_SENSITIVITY)
                            device.emit(uinput.REL_X, rel_x)
                            device.emit(uinput.REL_Y, rel_y)
                        last_rx, last_ry = rx, ry

        elif event.type == ecodes.EV_KEY and event.code == ecodes.BTN_TOUCH:
            if event.value == 1:  # Touch down
                touch_start_time = event.timestamp()
                last_rx = last_ry = None
            elif event.value == 0:  # Touch up
                if touch_start_time is not None:
                    touch_duration = event.timestamp() - touch_start_time
                    finger_tap = all(
                        (event.timestamp() - t["start_time"]) < TAP_DURATION_THRESHOLD
                        and abs(t["x"] - t["initial_x"]) < TAP_MOVEMENT_THRESHOLD
                        and abs(t["y"] - t["initial_y"]) < TAP_MOVEMENT_THRESHOLD
                        for t in active_touches.values()
                    )
                    if finger_tap:
                        if len(active_touches) == 2:
                            device.emit(uinput.BTN_RIGHT, 1)
                        if len(active_touches) <= 1:
                            device.emit(uinput.BTN_LEFT, 1)
                device.emit(uinput.BTN_LEFT, 0)
                three_finger_down = False
                already_scrolled = False
                active_touches.clear()
except KeyboardInterrupt:
    toggle_original_input(touch_dev_name, True)
    print("Restored touchscreen input")
