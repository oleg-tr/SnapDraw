# SnapDraw 📷

A macOS menu-bar screenshot tool with built-in annotation — a drop-in replacement for the native `cmd+5` screenshot menu.

## Features
- **Capture Entire Screen / Window / Portion** — same as native macOS
- **Save To** — Clipboard, Desktop, Documents, Downloads, Pictures, or any custom folder
- **Timer** — 0 / 5 / 10 second delay
- **Options** — toggle mouse cursor visibility
- **Annotation popup** — opens every screenshot for drawing before saving
  - ✏️ Pen, 🖊 Highlighter, ↗ Arrow, ▭ Rectangle, ⬭ Oval, ⌫ Eraser
  - 9-color palette + adjustable brush size
  - Undo (up to 40 steps)
  - Save ✓ or Discard ✕

## Setup

SnapDraw needs to be bundled as a `.app` because macOS Sequoia (15+) blocks unbundled Python scripts from owning menu bar items.

```bash
# 1. Create a venv on Python 3.12 (rumps is unstable on 3.13+)
/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install rumps Pillow py2app

# 3. Build the .app bundle (alias mode — source stays live-editable)
rm -rf build dist
python setup.py py2app -A

# 4. Launch
open dist/SnapDraw.app
```

After editing `screenshot_app.py`, relaunch:
```bash
killall SnapDraw 2>/dev/null
open dist/SnapDraw.app
```

## Requirements
- macOS 12+ (tested on Sequoia 15.x)
- Python 3.12 (3.13+ breaks `rumps`/`pyobjc` bindings)

## Auto-start on login
Add `dist/SnapDraw.app` to **System Settings → General → Login Items**.

## Permissions
On first run macOS will ask for:
- **Screen Recording** — required for `screencapture`
  System Settings → Privacy & Security → Screen Recording → enable for SnapDraw
- **Notifications** — for capture cancel / error toasts

## Save To Clipboard
When **Save To → Clipboard** is selected, hitting **Save ✓** in the annotator copies the PNG to the macOS clipboard (via `osascript` + `«class PNGf»`) instead of writing to disk. Paste into any app with `cmd+V`.

## Troubleshooting

**Menu bar icon doesn't appear.**
macOS Sequoia will not display the icon if you run `python screenshot_app.py` directly. You must use the `.app` bundle (see Setup).

**`ModuleNotFoundError: No module named 'rumps'`.**
`python3` is probably a shell alias overriding your venv. Run `unalias python3` or use `.venv/bin/python` directly.

**Icon hidden behind notch.**
On MacBooks with a notch, use `cmd+drag` to rearrange menu bar items, or quit apps with many menu extras to free space.
