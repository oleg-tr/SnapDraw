#!/usr/bin/env python3
"""
SnapDraw – a macOS screenshot tool with annotation support.
Replaces the native cmd+5 screenshot menu.
"""

import rumps
import subprocess
import threading
import time
import os
import sys
from pathlib import Path
from datetime import datetime


# ── defaults ──────────────────────────────────────────────────────────────────
DEFAULT_SAVE_DIR = str(Path.home() / "Desktop")
CONFIG_FILE = str(Path.home() / ".snapdraw_config")

# ── config helpers ─────────────────────────────────────────────────────────────

def load_config():
    cfg = {"save_to": DEFAULT_SAVE_DIR, "timer": 0, "show_cursor": True}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            for line in f:
                k, _, v = line.strip().partition("=")
                if k == "save_to":
                    cfg["save_to"] = v
                elif k == "timer":
                    cfg["timer"] = int(v)
                elif k == "show_cursor":
                    cfg["show_cursor"] = v == "True"
    return cfg


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        for k, v in cfg.items():
            f.write(f"{k}={v}\n")


# ── annotation window ─────────────────────────────────────────────────────────

ANNOTATOR_SCRIPT = """
import sys
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw
import os

image_path = sys.argv[1]
save_path  = sys.argv[2]

img = Image.open(image_path).convert("RGBA")
draw_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
pil_draw   = ImageDraw.Draw(draw_layer)

root = tk.Tk()
root.title("SnapDraw – Annotate")
root.configure(bg="#1a1a2e")
root.resizable(True, True)

# ── state ──────────────────────────────────────────────────────────────────────
current_tool   = tk.StringVar(value="pen")
current_color  = tk.StringVar(value="#FF3B30")
brush_size     = tk.IntVar(value=4)
last_x = last_y = None
history = []   # list of draw_layer snapshots for undo

COLORS = [
    "#FF3B30","#FF9500","#FFCC00","#34C759",
    "#00C7BE","#007AFF","#AF52DE","#FFFFFF","#000000",
]

# ── save snapshot for undo ─────────────────────────────────────────────────────
def push_history():
    history.append(draw_layer.copy())
    if len(history) > 40:
        history.pop(0)

# ── canvas setup ──────────────────────────────────────────────────────────────
SCREEN_W = root.winfo_screenwidth()
SCREEN_H = root.winfo_screenheight()
MAX_W    = min(img.width,  SCREEN_W - 40)
MAX_H    = min(img.height, SCREEN_H - 160)

canvas = tk.Canvas(root, width=MAX_W, height=MAX_H,
                   cursor="crosshair", bg="#0f0f1a",
                   highlightthickness=0)
canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))

# scrollbars if image is larger than display
hbar = tk.Scrollbar(root, orient=tk.HORIZONTAL, command=canvas.xview)
vbar = tk.Scrollbar(root, orient=tk.VERTICAL,   command=canvas.yview)
canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set,
                 scrollregion=(0, 0, img.width, img.height))
if img.width > MAX_W or img.height > MAX_H:
    hbar.pack(fill=tk.X, padx=10)
    vbar.pack(side=tk.RIGHT, fill=tk.Y)

tk_img   = None
img_item = None

def refresh_canvas():
    global tk_img, img_item
    composite = Image.alpha_composite(img, draw_layer)
    tk_img = ImageTk.PhotoImage(composite)
    if img_item:
        canvas.itemconfig(img_item, image=tk_img)
    else:
        img_item = canvas.create_image(0, 0, anchor=tk.NW, image=tk_img)

refresh_canvas()

# ── drawing logic ─────────────────────────────────────────────────────────────
def canvas_xy(event):
    return canvas.canvasx(event.x), canvas.canvasy(event.y)

def on_press(event):
    global last_x, last_y
    push_history()
    last_x, last_y = canvas_xy(event)

    tool = current_tool.get()
    if tool == "arrow":
        # store start point in event's widget tag for release
        canvas._arrow_start = (last_x, last_y)

def on_drag(event):
    global last_x, last_y
    if last_x is None:
        return
    x, y = canvas_xy(event)
    tool  = current_tool.get()
    color = current_color.get()
    size  = brush_size.get()
    r     = size // 2

    if tool == "pen":
        pil_draw.line([last_x, last_y, x, y],
                      fill=(*bytes.fromhex(color.lstrip("#")), 220),
                      width=size)
        refresh_canvas()
        last_x, last_y = x, y

    elif tool == "eraser":
        pil_draw.ellipse([x - r*3, y - r*3, x + r*3, y + r*3],
                         fill=(0, 0, 0, 0))
        refresh_canvas()
        last_x, last_y = x, y

    elif tool == "highlight":
        pil_draw.line([last_x, last_y, x, y],
                      fill=(*bytes.fromhex(color.lstrip("#")), 90),
                      width=size * 5)
        refresh_canvas()
        last_x, last_y = x, y

def on_release(event):
    global last_x, last_y
    x, y  = canvas_xy(event)
    tool  = current_tool.get()
    color = current_color.get()
    size  = brush_size.get()
    rgb   = tuple(bytes.fromhex(color.lstrip("#")))

    if tool == "arrow" and hasattr(canvas, "_arrow_start"):
        sx, sy = canvas._arrow_start
        # draw line
        pil_draw.line([sx, sy, x, y],
                      fill=(*rgb, 255), width=max(2, size))
        # draw arrowhead
        import math
        angle  = math.atan2(y - sy, x - sx)
        alen   = max(12, size * 4)
        spread = 0.5
        for side in (-spread, spread):
            ax = x - alen * math.cos(angle + side)
            ay = y - alen * math.sin(angle + side)
            pil_draw.line([x, y, ax, ay],
                          fill=(*rgb, 255), width=max(2, size))
        refresh_canvas()

    elif tool == "rect" and last_x is not None:
        pil_draw.rectangle([last_x, last_y, x, y],
                           outline=(*rgb, 230), width=max(2, size))
        refresh_canvas()

    elif tool == "oval" and last_x is not None:
        pil_draw.ellipse([last_x, last_y, x, y],
                         outline=(*rgb, 230), width=max(2, size))
        refresh_canvas()

    last_x = last_y = None

canvas.bind("<ButtonPress-1>",   on_press)
canvas.bind("<B1-Motion>",       on_drag)
canvas.bind("<ButtonRelease-1>", on_release)

# ── toolbar ────────────────────────────────────────────────────────────────────
toolbar = tk.Frame(root, bg="#1a1a2e", pady=8)
toolbar.pack(fill=tk.X, padx=10, pady=(6, 8))

TOOL_BTN_STYLE = dict(
    relief=tk.FLAT, bd=0, padx=8, pady=4,
    font=("SF Pro Text", 13), cursor="hand2"
)

def make_tool_btn(parent, label, tool_name, icon=""):
    def select():
        current_tool.set(tool_name)
        for b in tool_buttons:
            b.configure(bg="#1a1a2e", fg="#8888aa")
        btn.configure(bg="#2d2d5e", fg="#ffffff")
    btn = tk.Button(parent, text=f"{icon} {label}",
                    command=select, **TOOL_BTN_STYLE,
                    bg="#1a1a2e", fg="#8888aa")
    btn.pack(side=tk.LEFT, padx=2)
    return btn

tool_buttons = []
tools = [("Pen","pen","✏️"),("Highlight","highlight","🖊"),
         ("Arrow","arrow","↗"),("Rect","rect","▭"),
         ("Oval","oval","⬭"),("Eraser","eraser","⌫")]
for label, name, icon in tools:
    b = make_tool_btn(toolbar, label, name, icon)
    tool_buttons.append(b)

# activate pen by default
tool_buttons[0].configure(bg="#2d2d5e", fg="#ffffff")

# ── separator ─────────────────────────────────────────────────────────────────
tk.Frame(toolbar, width=1, bg="#333366").pack(side=tk.LEFT, padx=8, fill=tk.Y)

# ── color palette ─────────────────────────────────────────────────────────────
def pick_color(c):
    current_color.set(c)
    for btn, col in color_btns:
        btn.configure(
            relief=tk.SUNKEN if col == c else tk.FLAT,
            bd=2 if col == c else 0
        )

color_btns = []
for c in COLORS:
    btn = tk.Button(toolbar, bg=c, width=2, height=1,
                    relief=tk.FLAT, bd=0, cursor="hand2",
                    command=lambda col=c: pick_color(col))
    btn.pack(side=tk.LEFT, padx=2)
    color_btns.append((btn, c))
pick_color("#FF3B30")

# ── separator ─────────────────────────────────────────────────────────────────
tk.Frame(toolbar, width=1, bg="#333366").pack(side=tk.LEFT, padx=8, fill=tk.Y)

# ── brush size ────────────────────────────────────────────────────────────────
tk.Label(toolbar, text="Size", bg="#1a1a2e", fg="#8888aa",
         font=("SF Pro Text", 11)).pack(side=tk.LEFT)
size_slider = ttk.Scale(toolbar, from_=1, to=20,
                        variable=brush_size, orient=tk.HORIZONTAL,
                        length=80)
size_slider.pack(side=tk.LEFT, padx=6)

# ── separator ─────────────────────────────────────────────────────────────────
tk.Frame(toolbar, width=1, bg="#333366").pack(side=tk.LEFT, padx=8, fill=tk.Y)

# ── undo / save / discard ─────────────────────────────────────────────────────
def undo():
    global draw_layer, pil_draw
    if history:
        draw_layer = history.pop()
        pil_draw   = ImageDraw.Draw(draw_layer)
        refresh_canvas()

def save_and_close():
    composite = Image.alpha_composite(img, draw_layer).convert("RGB")
    if save_path == "clipboard":
        import io, time
        from AppKit import NSPasteboard, NSPasteboardItem, NSPasteboardTypePNG
        from Foundation import NSData
        buf = io.BytesIO()
        composite.save(buf, format="PNG")
        png_bytes = buf.getvalue()
        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        item = NSPasteboardItem.alloc().init()
        data = NSData.dataWithBytes_length_(png_bytes, len(png_bytes))
        item.setData_forType_(data, NSPasteboardTypePNG)
        pb.writeObjects_([item])
        time.sleep(0.5)
    else:
        composite.save(save_path)
    root.destroy()

def discard():
    root.destroy()

action_style = dict(relief=tk.FLAT, bd=0, padx=10, pady=4,
                    font=("SF Pro Text", 13, "bold"), cursor="hand2")

tk.Button(toolbar, text="↩ Undo", command=undo,
          bg="#1a1a2e", fg="#8888aa", **action_style).pack(side=tk.LEFT, padx=2)
tk.Button(toolbar, text="✕ Discard", command=discard,
          bg="#1a1a2e", fg="#FF453A", **action_style).pack(side=tk.RIGHT, padx=4)
tk.Button(toolbar, text="Save ✓", command=save_and_close,
          bg="#30D158", fg="#ffffff", **action_style).pack(side=tk.RIGHT, padx=4)

root.mainloop()
"""


def open_annotator(image_path: str, save_path: str):
    """Launch the Tk annotator in a separate Python process."""
    import tempfile
    script_file = tempfile.NamedTemporaryFile(
        suffix=".py", delete=False, mode="w", encoding="utf-8"
    )
    script_file.write(ANNOTATOR_SCRIPT)
    script_file.flush()
    script_file.close()

    # Inside a py2app bundle, sys.executable is the bundle launcher, not python.
    # Locate a real python3 interpreter that has Pillow + pyobjc installed.
    python_bin = os.environ.get("SNAPDRAW_PYTHON")
    if not python_bin:
        for candidate in (
            str(Path(__file__).resolve().parent.parent.parent.parent / ".venv" / "bin" / "python"),
            "/opt/homebrew/opt/python@3.12/bin/python3.12",
            "/opt/homebrew/bin/python3.12",
            "/usr/local/bin/python3.12",
            sys.executable,
        ):
            if candidate and os.path.exists(candidate):
                python_bin = candidate
                break

    subprocess.Popen(
        [python_bin, script_file.name, image_path, save_path]
    )


# ── menu-bar app ───────────────────────────────────────────────────────────────

class SnapDrawApp(rumps.App):
    def __init__(self):
        super().__init__("📷", quit_button=None)
        self.cfg = load_config()
        self._build_menu()

    # ── menu construction ──────────────────────────────────────────────────────
    def _build_menu(self):
        self.menu.clear()

        # ── capture modes ──────────────────────────────────────────────────────
        self.menu.add(rumps.MenuItem("Capture Entire Screen",
                                    callback=self.capture_screen))
        self.menu.add(rumps.MenuItem("Capture Selected Window",
                                    callback=self.capture_window))
        self.menu.add(rumps.MenuItem("Capture Selected Portion",
                                     callback=self.capture_portion))
        self.menu.add(rumps.separator)

        # ── Save To ────────────────────────────────────────────────────────────
        save_item = rumps.MenuItem("Save To")
        locations = {
            "Clipboard":  "clipboard",
            "Desktop":    str(Path.home() / "Desktop"),
            "Documents":  str(Path.home() / "Documents"),
            "Downloads":  str(Path.home() / "Downloads"),
            "Pictures":   str(Path.home() / "Pictures"),
        }
        for name, path in locations.items():
            item = rumps.MenuItem(
                ("✓ " if self.cfg["save_to"] == path else "   ") + name,
                callback=self._make_save_to_cb(path, name, locations, save_item)
            )
            save_item.add(item)
        save_item.add(rumps.separator)
        save_item.add(rumps.MenuItem("Other Location…",
                                     callback=self.choose_other_location))
        self.menu.add(save_item)

        # ── Timer ─────────────────────────────────────────────────────────────
        timer_item = rumps.MenuItem("Timer")
        for seconds in [0, 5, 10]:
            label = "None" if seconds == 0 else f"{seconds} seconds"
            item  = rumps.MenuItem(
                ("✓ " if self.cfg["timer"] == seconds else "   ") + label,
                callback=self._make_timer_cb(seconds, timer_item)
            )
            timer_item.add(item)
        self.menu.add(timer_item)

        # ── Options ───────────────────────────────────────────────────────────
        options_item = rumps.MenuItem("Options")
        self._cursor_item = rumps.MenuItem(
            ("✓ " if self.cfg["show_cursor"] else "   ") + "Show Mouse Pointer",
            callback=self.toggle_cursor
        )
        options_item.add(self._cursor_item)
        self.menu.add(options_item)

        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Quit SnapDraw",
                                     callback=rumps.quit_application))

    def _make_save_to_cb(self, path, name, locations, save_item):
        def cb(_):
            self.cfg["save_to"] = path
            save_config(self.cfg)
            # refresh checkmarks
            for item_name, item_path in locations.items():
                prefix = "✓ " if item_path == path else "   "
                save_item[prefix.strip() + item_name] = None   # won't work—rebuild instead
            self._build_menu()
        return cb

    def _make_timer_cb(self, seconds, timer_item):
        def cb(_):
            self.cfg["timer"] = seconds
            save_config(self.cfg)
            self._build_menu()
        return cb

    # ── options callbacks ──────────────────────────────────────────────────────
    def toggle_cursor(self, _):
        self.cfg["show_cursor"] = not self.cfg["show_cursor"]
        save_config(self.cfg)
        self._build_menu()

    def choose_other_location(self, _):
        result = subprocess.run(
            ["osascript", "-e",
             'POSIX path of (choose folder with prompt "Save screenshots to:")'],
            capture_output=True, text=True
        )
        path = result.stdout.strip()
        if path:
            self.cfg["save_to"] = path
            save_config(self.cfg)
            self._build_menu()

    # ── capture helpers ───────────────────────────────────────────────────────
    def _timestamp(self):
        return datetime.now().strftime("Screenshot %Y-%m-%d at %H.%M.%S")

    def _save_path(self):
        if self.cfg["save_to"] == "clipboard":
            return "clipboard"
        return os.path.join(self.cfg["save_to"],
                            self._timestamp() + ".png")

    def _do_capture(self, screencapture_args: list):
        delay = self.cfg["timer"]
        if delay:
            time.sleep(delay)

        tmp_path  = f"/tmp/snapdraw_{int(time.time())}.png"
        save_path = self._save_path()

        extra = [] if self.cfg["show_cursor"] else ["-C"]
        cmd   = ["screencapture"] + extra + screencapture_args + [tmp_path]
        result = subprocess.run(cmd)

        if result.returncode == 0 and os.path.exists(tmp_path):
            open_annotator(tmp_path, save_path)
        else:
            rumps.notification("SnapDraw", "Capture cancelled", "")

    def capture_screen(self, _):
        threading.Thread(
            target=self._do_capture, args=([],), daemon=True
        ).start()

    def capture_window(self, _):
        threading.Thread(
            target=self._do_capture, args=(["-w"],), daemon=True
        ).start()

    def capture_portion(self, _):
        threading.Thread(
            target=self._do_capture, args=(["-s"],), daemon=True
        ).start()


# ── entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    SnapDrawApp().run()