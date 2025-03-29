# Trackpad Emulator

## Introduction

A simple program to simulate trackpad behavior from a touchscreen.

## Installation

### Prerequisite

> [!IMPORTANT]
> Before running the program, you have to find a way to stop your Desktop Environment from reading events from touchscreen. Otherwise, the output of virtual trackpad and the real touchscreen would conflict.

#### Hyprland

As I use hyprland, a utility to toggle touchscreen is provided.

```shell
./dist/hyprland_toggle_touchscreen -h
```

#### Others

If you use xorg, `xinput` command should be helpful. If you use wayland, input devices are managed by Desktop Environment. Read through the DE's official docs to find out how to disable a input device.

### Run from compiled file

```shell
git clone https://github.com/Jade233333/etrackpad.git
cd etrackpad
./dist/etrackpad
```

## Usage

| Action | Function |
| -------------- | --------------- |
| one-finger move | move cursor |
| two-finger move | scroll |
| three-finger move | drag |
| one-finger tap | left-click |
| two-finger tap| right-click |

Use `-h` flag for help to adjust important variables

> [!NOTE]
> Scrolling simulation is not perfect. For current stage, one complete two-finger swipe is transcribe to one unit, which is adjustable by passing arguments, of mouse-wheel scrolling. It means that you cannot get seamless scrolling behavior like a real trackpad That is because the program is actually simulate mouse instead of trackpad and due to the wheel simulation provided by python-uinput is not stepless. If binding two-finger move amount to wheel scrolling amount, the result will look inconsistent.
