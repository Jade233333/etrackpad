# Trackpad Emulator

## Introduction

A simple program to simulate trackpad behavior from a touchscreen.

For current stage, it only works under hyprland as I personally use it. Although the simulation process should work no matter what the environment is, one important prerequisite is to disable the original output. As "we are wayland now", `libinput` no longer provides a universal cli to disable output like `xinput` we had in xorg. Instead, the control of input device are directly handled by Desktop Environment. As a result, in the code, `subprocess` is ran to manipulate `hyprctl` to disable the touchscreen.

## Installation

Download source code.

For hyprland user, it should works straightaway

```
pip install -r requirements.txt
python trackpad_emulator.py
```

For the others, you would have to change the `toggle_original_output` function in `trackpad_emulator.py` and then run the code.

## Usage

| Action | Function |
| -------------- | --------------- |
| one-finger move | move cursor |
| two-finger move | scroll |
| three-finger move | drag |
| one-finger tap | left-click |
| two-finger tap| right-click |

Use `-h` flag for help to adjust key variables

> [!NOTE]
> Scrolling simulation is not perfect. For current stage, one complete two-finger swipe is transcribe to one unit, which is adjustable by passing arguments, of mouse-wheel scrolling. It means that you cannot get seamless scrolling behavior like a real trackpad That is because the program is actually simulate mouse instead of trackpad and due to the wheel simulation provided by python-uinput is not stepless. If binding two-finger move amount to wheel scrolling amount, the result will look inconsistent.
