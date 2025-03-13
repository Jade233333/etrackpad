from evdev import InputDevice, categorize

# Replace with your device path
TOUCH_DEVICE = "/dev/input/event17"

dev = InputDevice(TOUCH_DEVICE)
print(f"Reading from {dev.name}")

try:
    for event in dev.read_loop():
        print(categorize(event))
except KeyboardInterrupt:
    print("Exiting")
