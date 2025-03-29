import pyudev
import argparse
import subprocess
from evdev import InputDevice


class NoValidDeviceError(Exception):
    """Exception raised when no valid touchscreen device is found."""

    def __init__(self, message="No touchscreen detected"):
        super().__init__(message)


class TouchscreenHandler:
    def __init__(self):
        self.device = self._find_touchscreen()
        self.name = str(self.device.name).replace(" ", "-").lower()

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

    def toggle_input(self, enabled):
        if enabled:
            print(f"enabling {self.name}")
            subprocess.run(
                ["hyprctl", "-r", "keyword", f"device[{self.name}]:enabled", "1"]
            )
        else:
            print(f"disabling {self.name}")
            subprocess.run(
                ["hyprctl", "-r", "keyword", f"device[{self.name}]:enabled", "0"]
            )


parser = argparse.ArgumentParser()
parser.add_argument(
    "--enabled",
    type=int,
    choices=[0, 1],
    default=0,
    help="1 to enable touchscreen input, 0 to disable touchscreen input",
)
args = parser.parse_args()
touchscreen_handler = TouchscreenHandler()
touchscreen_handler.toggle_input(args.enabled)
