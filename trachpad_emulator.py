from evdev import InputDevice, ecodes, categorize
import uinput
import subprocess
import argparse

TOUCH_DEVICE_PATH = "/dev/input/event17"
TOUCH_DEVICE_NAME = "gxtp7386:00-27c6:0113"
SENSITIVITY = 0.6
MOVEMENT_THRESHOLD = 50
CLICK_THRESHOLD = 0.12

device = uinput.Device(
    [
        uinput.REL_X,
        uinput.REL_Y,
        uinput.BTN_LEFT,
    ]
)


def apply_rotation(x, y, rotation, max_x, max_y):
    """Transform coordinates based on rotation"""
    if rotation == 0:  # Normal
        return x, y
    elif rotation == 180:  # Inverted
        return (max_x - x, max_y - y)
    elif rotation == 90:  # 90° clockwise
        return (y, max_x - x)
    elif rotation == 270:  # 90° counter-clockwise
        return (max_y - y, x)
    else:
        raise ValueError("Invalid rotation value")


try:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rotate",
        type=int,
        choices=[0, 90, 180, 270],
        default=90,
        help="Screen rotation (0, 90, 180, 270 degrees)",
    )
    args = parser.parse_args()

    subprocess.run(["hyprctl", "keyword", "device[gxtp7386:00-27c6:0113]:enabled", "0"])
    touch_dev = InputDevice(TOUCH_DEVICE_PATH)

    # Get screen dimensions from device capabilities
    max_x = max_y = 0
    for abs_code, abs_info in touch_dev.capabilities().get(ecodes.EV_ABS, []):
        if abs_code == ecodes.ABS_X:
            max_x = abs_info.max
        elif abs_code == ecodes.ABS_Y:
            max_y = abs_info.max

    print(f"Capturing input from {touch_dev.name}")
    print(f"Max X: {max_x}, Max Y: {max_y}")
    print(f"Active rotation: {args.rotate}°")

    current_x = current_y = last_rx = last_ry = 0
    touch_start_time = None
    touch_down_x = touch_down_y = None

    for event in touch_dev.read_loop():
        if event.type == ecodes.EV_ABS:
            if event.code == ecodes.ABS_X:
                current_x = event.value
            elif event.code == ecodes.ABS_Y:
                current_y = event.value
        elif event.type == ecodes.EV_SYN and event.code == ecodes.SYN_REPORT:
            if touch_down_x is not None and touch_down_y is not None:
                dx = abs(current_x - touch_down_x)
                dy = abs(current_y - touch_down_y)

                if dx > MOVEMENT_THRESHOLD or dy > MOVEMENT_THRESHOLD:
                    rx, ry = apply_rotation(
                        current_x, current_y, args.rotate, max_x, max_y
                    )

                    if last_rx is not None and last_ry is not None:
                        rel_x = int((rx - last_rx) * SENSITIVITY)
                        rel_y = int((ry - last_ry) * SENSITIVITY)

                        device.emit(uinput.REL_X, rel_x)
                        device.emit(uinput.REL_Y, rel_y)

                    last_rx = rx
                    last_ry = ry
        elif event.type == ecodes.EV_KEY and event.code == ecodes.BTN_TOUCH:
            if event.value == 1:  # Touch down
                last_rx = last_ry = None  # Reset tracking when touch is lifted
                touch_start_time = event.timestamp()
                touch_down_x = current_x
                touch_down_y = current_y
            elif event.value == 0:  # Touch up
                if touch_start_time is not None:
                    touch_duration = event.timestamp() - touch_start_time

                    if touch_duration < CLICK_THRESHOLD:
                        device.emit(uinput.BTN_LEFT, 1)  # Press
                        device.emit(uinput.BTN_LEFT, 0)  # Release
                touch_down_x = touch_down_y = None  # Reset touch-down position

except KeyboardInterrupt:
    subprocess.run(["hyprctl", "keyword", "device[gxtp7386:00-27c6:0113]:enabled", "1"])
    print("\nRestored touchscreen input")
