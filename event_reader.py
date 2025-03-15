import pyudev
import evdev
import subprocess


def find_touchscreen_udev():
    context = pyudev.Context()
    for device in context.list_devices(subsystem="input"):
        # Check if the udev property indicates a touchscreen
        if (
            device.properties.get("ID_INPUT_TOUCHSCREEN") == "1"
            and device.device_node is not None
        ):
            dev = evdev.InputDevice(device.device_node)
            return dev  # Return the first touchscreen device found
    print("Touch device not found")
    return None


# Try to detect the touchscreen using udev properties
dev = find_touchscreen_udev()

if dev:
    print(f"Found touchscreen: {dev.path} ({dev.name})")  # Output device path and name
    try:
        for event in dev.read_loop():
            print(evdev.categorize(event))
            print(event.value)
    except KeyboardInterrupt:
        print("Exiting")
else:
    print("No touchscreen device found.")
