"""
CSP Discord Presence
Shows what you're working on in Clip Studio Paint as your Discord status,
e.g. "Playing Clip Studio Paint - Painting: sketch - 00:42 elapsed".

Run:   double-click csp_presence.pyw   (or: py csp_presence.pyw)
Settings live in config.json next to this file (created on first run).
Everything else is controlled from the tray icon.
"""
import json
import os
import re
import subprocess
import sys
import threading
import time

import psutil
import pystray
from PIL import Image, ImageDraw
from pypresence import Presence

APP_NAME = "CSPDiscordPresence"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
TRAY_ICON_FILE = os.path.join(APP_DIR, "tray_icon.png")
IS_WINDOWS = sys.platform == "win32"

DEFAULT_CONFIG = {
    "client_id": "",
    "large_image": "csp",
    "large_text": "Clip Studio Paint",
    "activity": "Painting",
    "activities": ["Painting", "Editing", "Drafting"],
    "show_file_name": True,
    "show_extension": False,
    "update_seconds": 15,
    "art_folders": ["~/Documents", "~/Pictures", "~/Desktop"],
    "recent_minutes": 120,
}

ART_EXT = (".clip", ".lip", ".cmc", ".psd")
FILE_RE = re.compile(r"([^\\/\[\]]+?\.(?:clip|psd|lip|cmc))", re.I)
SKIP_PATH_PARTS = ("\\appdata\\", "/library/", "\\temp\\", "/tmp/", "\\celsys\\", "/celsys/")
SKIP_DIRS = {"appdata", "node_modules", ".git", "celsys", "$recycle.bin"}

cfg = dict(DEFAULT_CONFIG)
state = {"status": "Starting...", "paused": False}
stop_event = threading.Event()
wake_event = threading.Event()   # wakes the worker early after a menu change
tray = None
_mutex = None


# ---------------------------------------------------------------- config
def load_config():
    global cfg
    data = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            set_status("config.json has an error - using defaults")
            cfg = dict(DEFAULT_CONFIG)
            return
    merged = dict(DEFAULT_CONFIG)
    merged.update(data)
    if not merged.get("activities"):
        merged["activities"] = list(DEFAULT_CONFIG["activities"])
    if merged.get("activity") not in merged["activities"]:
        merged["activity"] = merged["activities"][0]
    cfg = merged
    if data != merged:
        save_config()   # writes the file on first run / fills in new keys


def save_config():
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        set_status("Couldn't save config.json")


def open_config():
    try:
        if IS_WINDOWS:
            subprocess.Popen(["notepad.exe", CONFIG_PATH])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-t", CONFIG_PATH])
        else:
            subprocess.Popen(["xdg-open", CONFIG_PATH])
    except Exception:
        pass


# ---------------------------------------------------------------- status
def set_status(text):
    if state["status"] == text:
        return
    state["status"] = text
    print(text)
    if tray is not None:
        try:
            tray.title = f"CSP Presence - {text}"[:127]
            tray.update_menu()
        except Exception:
            pass


# ---------------------------------------------------------------- file detection
def csp_processes():
    procs = []
    for p in psutil.process_iter(["name"]):
        name = (p.info["name"] or "").lower().replace(" ", "")
        if "clipstudiopaint" in name:
            procs.append(p)
    return procs


def usable_path(path):
    low = path.lower()
    return low.endswith(ART_EXT) and not any(part in low for part in SKIP_PATH_PARTS)


def file_from_open_handles(procs):
    """Method 1: files the CSP process currently has open."""
    found = []
    for p in procs:
        try:
            for f in p.open_files():
                if usable_path(f.path):
                    found.append(f.path)
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
    if not found:
        return None
    return max(found, key=lambda f: os.path.getmtime(f) if os.path.exists(f) else 0)


def file_from_windows(pids):
    """Method 2: window / canvas tab titles (Windows only)."""
    if not IS_WINDOWS:
        return None
    import win32gui
    import win32process

    top = []

    def top_cb(hwnd, _):
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid in pids:
            top.append(hwnd)

    win32gui.EnumWindows(top_cb, None)
    titles = []
    for hwnd in top:
        titles.append(win32gui.GetWindowText(hwnd))
        try:
            win32gui.EnumChildWindows(hwnd, lambda h, _: titles.append(win32gui.GetWindowText(h)), None)
        except Exception:
            pass
    for t in titles:
        m = FILE_RE.search(t or "")
        if m:
            return m.group(1).strip(" *")
    return None


def file_from_recent_saves():
    """Method 3: the most recently saved art file in your art folders."""
    cutoff = time.time() - float(cfg["recent_minutes"]) * 60
    best, best_time = None, cutoff
    for folder in cfg["art_folders"]:
        folder = os.path.expanduser(folder)
        for root, dirs, files in os.walk(folder):
            dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS and not d.startswith(".")]
            for name in files:
                if name.lower().endswith(ART_EXT):
                    path = os.path.join(root, name)
                    try:
                        mtime = os.path.getmtime(path)
                    except OSError:
                        continue
                    if mtime > best_time:
                        best, best_time = path, mtime
    return best


def find_file(procs):
    pids = {p.pid for p in procs}
    for func in (lambda: file_from_open_handles(procs),
                 lambda: file_from_windows(pids),
                 file_from_recent_saves):
        try:
            result = func()
        except Exception:
            result = None
        if result:
            return os.path.basename(result)
    return None


def build_details(fname):
    activity = cfg["activity"]
    if not fname:
        return activity
    if not cfg["show_extension"]:
        fname = os.path.splitext(fname)[0]
    return f"{activity}: {fname}"[:128]


# ---------------------------------------------------------------- discord worker
def close_rpc(rpc):
    if rpc is None:
        return
    for fn in (rpc.clear, rpc.close):
        try:
            fn()
        except Exception:
            pass


def try_connect(client_id):
    try:
        rpc = Presence(client_id)
        rpc.connect()
        return rpc
    except Exception:
        return None


def sleep_until_next():
    wake_event.wait(max(5, float(cfg["update_seconds"])))
    wake_event.clear()


def worker():
    rpc, rpc_id = None, None
    start, last = None, None

    while not stop_event.is_set():
        try:
            client_id = str(cfg["client_id"]).strip()
            if not client_id:
                set_status("Add your client_id in Settings")
                sleep_until_next()
                continue

            if rpc is None or rpc_id != client_id:
                close_rpc(rpc)
                rpc = try_connect(client_id)
                rpc_id, last = client_id, None
                if rpc is None:
                    set_status("Waiting for Discord...")
                    sleep_until_next()
                    continue

            procs = csp_processes()
            if state["paused"] or not procs:
                if last is not None:
                    rpc.clear()
                last, start = None, None
                set_status("Paused" if state["paused"] else "Clip Studio Paint not open")
            else:
                if start is None:
                    start = int(time.time())
                fname = find_file(procs) if cfg["show_file_name"] else None
                details = build_details(fname)
                if details != last:
                    rpc.update(details=details,
                               large_image=cfg["large_image"],
                               large_text=cfg["large_text"],
                               start=start)
                    last = details
                set_status(f"Showing: {details}")
        except Exception:
            set_status("Lost Discord, reconnecting...")
            close_rpc(rpc)
            rpc, last = None, None
        sleep_until_next()

    close_rpc(rpc)


# ---------------------------------------------------------------- run on startup (Windows)
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def startup_command():
    exe = sys.executable
    if exe.lower().endswith("python.exe"):
        windowless = exe[:-len("python.exe")] + "pythonw.exe"
        if os.path.exists(windowless):
            exe = windowless
    return f'"{exe}" "{os.path.abspath(__file__)}"'


def startup_enabled():
    if not IS_WINDOWS:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except OSError:
        return False


def toggle_startup(icon, item):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if startup_enabled():
            winreg.DeleteValue(key, APP_NAME)
        else:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, startup_command())
    icon.update_menu()


def already_running():
    """Stops a second copy from starting (Windows)."""
    global _mutex
    if not IS_WINDOWS:
        return False
    try:
        import win32api
        import win32event
        import winerror
        _mutex = win32event.CreateMutex(None, False, "CSPDiscordPresence_SingleInstance")
        return win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS
    except Exception:
        return False


# ---------------------------------------------------------------- tray
def make_icon_image():
    if os.path.exists(TRAY_ICON_FILE):
        try:
            return Image.open(TRAY_ICON_FILE)
        except Exception:
            pass
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2, 2, 62, 62), radius=14, fill=(88, 101, 242))
    d.polygon([(20, 46), (40, 18), (48, 26), (26, 52)], fill="white")
    d.polygon([(20, 46), (26, 52), (16, 56)], fill=(255, 210, 120))
    return img


def refresh(icon):
    wake_event.set()
    icon.update_menu()


def make_activity_setter(name):
    def setter(icon, item):
        cfg["activity"] = name
        save_config()
        refresh(icon)
    return setter


def make_activity_checker(name):
    return lambda item: cfg["activity"] == name


def toggle_pause(icon, item):
    state["paused"] = not state["paused"]
    refresh(icon)


def toggle_file(icon, item):
    cfg["show_file_name"] = not cfg["show_file_name"]
    save_config()
    refresh(icon)


def open_settings(icon, item):
    open_config()


def reload_settings(icon, item):
    load_config()
    icon.menu = build_menu()   # activity list may have changed
    refresh(icon)


def quit_app(icon, item):
    stop_event.set()
    wake_event.set()
    icon.stop()


def build_menu():
    activity_items = [
        pystray.MenuItem(name, make_activity_setter(name),
                         checked=make_activity_checker(name), radio=True)
        for name in cfg["activities"]
    ]
    return pystray.Menu(
        pystray.MenuItem(lambda item: state["status"], None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Activity", pystray.Menu(*activity_items)),
        pystray.MenuItem("Show file name", toggle_file,
                         checked=lambda item: cfg["show_file_name"]),
        pystray.MenuItem("Pause", toggle_pause,
                         checked=lambda item: state["paused"]),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Start with Windows", toggle_startup,
                         checked=lambda item: startup_enabled(), visible=IS_WINDOWS),
        pystray.MenuItem("Open settings", open_settings),
        pystray.MenuItem("Reload settings", reload_settings),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", quit_app),
    )


def main():
    global tray
    if already_running():
        sys.exit(0)

    load_config()
    if not str(cfg["client_id"]).strip():
        open_config()   # first run: let the user paste their Application ID

    tray = pystray.Icon(APP_NAME, make_icon_image(), "CSP Presence", build_menu())
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    tray.run()          # blocks until Quit
    stop_event.set()
    wake_event.set()
    thread.join(timeout=5)


if __name__ == "__main__":
    main()
