> [!NOTE]
>
> This fork adds support for additional gestures and a new mode that triggers touch events at the
> current cursor position instead of a fixed coordinate. These changes are mostly AI-generated, so
> they may contain bugs and need further refinement.

> [!NOTE]
>
> WinToucher is still under development. The current version is a prototype and may contain bugs.

<img src="assets/WinToucher.svg" width="150" align="right">

# WinToucher
Powered by Win32 API and tkinter, WinToucher is a Python application that allows you to simulate touch events on Windows through keyboard input. It is useful for testing touch-based applications on Windows without a physical touch screen.

![](./assets/Preview.png)

## Features
- 📝 Mark touch points on the screen (when the overlay is shown)
  - **Click blank space** to create a new touch point
  - **Double click touch point** to check its detail
  - **Drag touch point** to move it
  - **Right click touch point** to unset its key binding or delete it (if it is not bound to any key)
- Cursor-based Mode
  - **New cursor mode**: Trigger touch events at the current mouse position instead of a fixed coordinate.
- 👇 Support for Gestures
  - **Press**: Single tap at the touch point.
  - **Flick**: Swipe gesture with customizable direction (angle) and distance.
  - **Pinch**: Two-finger pinch in/out gesture with customizable start and end distances.
  - **Rotate**: Two-finger rotation gesture with customizable angle and radius.
- ⌨️ Bindings Editor
  - View and manage all key bindings in a list.
  - Add bindings manually for cursor-based gestures without using the overlay.
  - Customize all parameters of gestures (e.g., rotation angle, pinch distance) via the detail panel.
- 📃 Save and load touch configurations in JSON format
- 👂 Global, togglable keyboard listener
- 👻 Hide window to the system tray

## Usage
This tool is managed using [Poetry](https://python-poetry.org/).

To install the dependencies, run:
```bash
poetry install
```

After that, you can run the application with:
```bash
poetry run wintoucher
```

## To-do
- [x] Further modularize the code and decouple current `__main__.py`
- [x] Fix bugs with touch simulation when calling `InjectTouchInput` in some certain cases
- [ ] Improve overlay GUI
- [ ] Try to build with `nuitka`

## License
[MIT](./LICENSE)