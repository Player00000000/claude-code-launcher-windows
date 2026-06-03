import webview
import json
import os
import subprocess
import time
import threading
import ctypes
from datetime import datetime

try:
    import pystray
    from PIL import Image as PILImage
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

WIN_BASE   = r"D:\Claude Code"
WSL_BASE   = "/mnt/d/Claude Code"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
META_FILE  = os.path.join(SCRIPT_DIR, "projects.json")
USAGE_FILE = os.path.join(SCRIPT_DIR, "usage.json")
EXCLUDE    = {"launcher", ".git", "__pycache__"}
SKIP_DIRS  = {".git", "node_modules", "__pycache__", ".next", "venv", ".venv", ".mypy_cache", "dist", "build"}

STATUS_COLORS = {
    "ACTIVE": "#a8e063",
    "WIP":    "#ffe66d",
    "PAUSED": "#888899",
    "DONE":   "#4ecdc4",
}

_always_on_top = False
_closing       = False


def _get_hwnd():
    """Get launcher top-level HWND."""
    GA_ROOT = 2

    def root(hwnd):
        """Walk up to top-level ancestor."""
        r = ctypes.windll.user32.GetAncestor(hwnd, GA_ROOT)
        return r if r else hwnd

    # Primary: pywebview WinForms Form.Handle
    try:
        hwnd = int(webview.windows[0]._window.Handle)
        if hwnd:
            return root(hwnd)
    except Exception:
        pass

    # Fallback: EnumWindows by title
    found = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_ulong, ctypes.c_ulong)

    def cb(hwnd, _):
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
        if "Claude Code Launcher" in buf.value:
            found.append(hwnd)
            return False
        return True

    proc = WNDENUMPROC(cb)
    ctypes.windll.user32.EnumWindows(proc, 0)
    return root(found[0]) if found else 0


def load_meta():
    if os.path.exists(META_FILE):
        with open(META_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_meta(data):
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_usage():
    if os.path.exists(USAGE_FILE):
        with open(USAGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"billing_start_day": None, "launches": {}}


def save_usage(data):
    with open(USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def scan_folder(win_path):
    """Single os.walk pass — returns (latest_mtime, total_size_bytes)."""
    latest = 0
    total  = 0
    try:
        for root, dirs, files in os.walk(win_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                try:
                    st = os.stat(os.path.join(root, f))
                    if st.st_mtime > latest:
                        latest = st.st_mtime
                    total += st.st_size
                except OSError:
                    pass
    except OSError:
        pass
    return latest, total


def fmt_ago(ts):
    if not ts:
        return ""
    diff = time.time() - ts
    if diff < 60:
        return "just now"
    if diff < 3600:
        return f"{int(diff/60)}m ago"
    if diff < 86400:
        return f"{int(diff/3600)}h ago"
    if diff < 86400 * 7:
        return f"{int(diff/86400)}d ago"
    if diff < 86400 * 30:
        return f"{int(diff/(86400*7))}w ago"
    return datetime.fromtimestamp(ts).strftime("%b %Y")


def fmt_size(b):
    if b < 1024:
        return f"{b}B"
    if b < 1024 ** 2:
        return f"{b/1024:.0f}KB"
    if b < 1024 ** 3:
        return f"{b/1024**2:.1f}MB"
    return f"{b/1024**3:.1f}GB"


def get_readme_description(win_path):
    """Return first meaningful text line from README, or None."""
    for name in ("README.md", "readme.md", "README.MD", "README.txt", "readme.txt"):
        path = os.path.join(win_path, name)
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    # Skip headings, badges, HTML, horizontal rules, list markers
                    if line[0] in ('#', '!', '[', '<', '>', '-', '*', '=', '|', '+'):
                        continue
                    if line.startswith("http"):
                        continue
                    # Strip markdown bold/italic/code
                    for ch in ('**', '*', '__', '_', '`'):
                        line = line.replace(ch, '')
                    line = line.strip()
                    if len(line) > 15:
                        return line[:160]
        except Exception:
            pass
    return None


def get_git_status(win_path):
    if not os.path.isdir(os.path.join(win_path, ".git")):
        return None
    try:
        result = subprocess.run(
            ["git", "-C", win_path, "status", "--porcelain", "-b"],
            capture_output=True, text=True, timeout=3,
            encoding="utf-8", errors="replace",
        )
        if result.returncode != 0:
            return None
        lines = result.stdout.strip().splitlines()
        branch = "main"
        if lines and lines[0].startswith("## "):
            b = lines[0][3:]
            if "..." in b:
                branch = b.split("...")[0]
            elif b.startswith("HEAD"):
                branch = "HEAD"
            else:
                branch = b.strip()
        dirty = len([l for l in lines[1:] if l.strip()])
        return {"branch": branch, "dirty": dirty}
    except Exception:
        return None


DEFAULT_DESC = "Click ✎ to edit description."


def scan_projects(show_archived=False):
    meta = load_meta()
    projects = []
    try:
        for folder in sorted(os.listdir(WIN_BASE)):
            if folder in EXCLUDE:
                continue
            win_path = os.path.join(WIN_BASE, folder)
            if not os.path.isdir(win_path):
                continue
            info = meta.get(folder, {})
            if info.get("archived", False) and not show_archived:
                continue

            status     = info.get("status", "ACTIVE")
            mtime, sz  = scan_folder(win_path)
            git        = get_git_status(win_path)
            last_launch= info.get("last_launched", 0)

            # Description: manual > README fallback > default
            desc = info.get("description", "")
            if not desc or desc == DEFAULT_DESC:
                desc = get_readme_description(win_path) or DEFAULT_DESC

            projects.append({
                "name":             folder,
                "wsl_path":         f"{WSL_BASE}/{folder}",
                "description":      desc,
                "color":            info.get("color", "#888899"),
                "tech":             info.get("tech", []),
                "status":           status,
                "status_color":     STATUS_COLORS.get(status, "#888899"),
                "last_modified":    fmt_ago(mtime),
                "last_modified_ts": mtime,
                "last_launched":    fmt_ago(last_launch),
                "last_launched_ts": last_launch,
                "launch_cmd":       info.get("launch_cmd", ""),
                "notes":            info.get("notes", ""),
                "archived":         info.get("archived", False),
                "port":             info.get("port", ""),
                "git":              git,
                "disk_size":        fmt_size(sz),
                "pinned":           info.get("pinned", False),
            })
    except Exception as e:
        print(f"Scan error: {e}")
    return projects


class Api:
    def get_projects(self, show_archived=False):
        return scan_projects(show_archived)

    def get_project_meta(self, name):
        return load_meta().get(name, {})

    def launch_project(self, name, wsl_path, launch_cmd=""):
        try:
            meta = load_meta()
            if name not in meta:
                meta[name] = {}
            meta[name]["last_launched"] = time.time()
            save_meta(meta)

            usage = load_usage()
            mk = datetime.now().strftime("%Y-%m")
            usage.setdefault("launches", {})[mk] = usage.get("launches", {}).get(mk, 0) + 1
            save_usage(usage)

            cmd = launch_cmd or meta.get(name, {}).get("launch_cmd", "")
            if not cmd:
                cmd = f"cd '{wsl_path}' && claude"

            subprocess.Popen(
                ["wt.exe", "wsl.exe", "-e", "bash", "-ic", cmd],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def open_explorer(self, name):
        try:
            subprocess.Popen(["explorer.exe", os.path.join(WIN_BASE, name)])
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def open_vscode(self, name):
        try:
            subprocess.Popen(f'code "{os.path.join(WIN_BASE, name)}"', shell=True)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def open_browser(self, name, port):
        try:
            if not port:
                return {"ok": False, "error": "No port set"}
            subprocess.Popen(["cmd.exe", "/c", "start", "", f"http://localhost:{port}"])
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def open_console(self):
        try:
            subprocess.Popen(["cmd.exe", "/c", "start", "", "https://console.anthropic.com"])
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def update_project(self, name, description, color, tech, status,
                       launch_cmd="", notes="", port=""):
        meta = load_meta()
        if name not in meta:
            meta[name] = {}
        meta[name].update({
            "description": description,
            "color":       color,
            "tech":        tech if isinstance(tech, list) else [],
            "status":      status if status in STATUS_COLORS else "ACTIVE",
            "launch_cmd":  launch_cmd,
            "notes":       notes,
            "port":        str(port) if port else "",
        })
        save_meta(meta)
        return {"ok": True}

    def add_project(self, name, description, color, tech, status="ACTIVE"):
        name = name.strip()
        if not name:
            return {"ok": False, "error": "Name required"}
        os.makedirs(os.path.join(WIN_BASE, name), exist_ok=True)
        meta = load_meta()
        meta[name] = {
            "description": description or DEFAULT_DESC,
            "color":       color or "#888899",
            "tech":        tech if isinstance(tech, list) else [],
            "status":      status if status in STATUS_COLORS else "ACTIVE",
        }
        save_meta(meta)
        return {"ok": True}

    def toggle_archive(self, name):
        meta = load_meta()
        meta.setdefault(name, {})
        archived = not meta[name].get("archived", False)
        meta[name]["archived"] = archived
        save_meta(meta)
        return {"ok": True, "archived": archived}

    def toggle_pin(self, name):
        meta = load_meta()
        meta.setdefault(name, {})
        pinned = not meta[name].get("pinned", False)
        meta[name]["pinned"] = pinned
        save_meta(meta)
        return {"ok": True, "pinned": pinned}

    def toggle_always_on_top(self):
        global _always_on_top
        _always_on_top = not _always_on_top
        try:
            hwnd = _get_hwnd()
            if not hwnd:
                _always_on_top = not _always_on_top
                return {"ok": False, "error": "Window handle not found"}
            result = ctypes.windll.user32.SetWindowPos(
                hwnd,
                -1 if _always_on_top else -2,  # HWND_TOPMOST / HWND_NOTOPMOST
                0, 0, 0, 0,
                0x0002 | 0x0001,               # SWP_NOMOVE | SWP_NOSIZE
            )
            if not result:
                err = ctypes.windll.kernel32.GetLastError()
                _always_on_top = not _always_on_top
                return {"ok": False, "error": f"Win32 error {err}"}
            return {"ok": True, "on_top": _always_on_top}
        except Exception as e:
            _always_on_top = not _always_on_top
            return {"ok": False, "error": str(e)}

    def get_usage(self):
        usage = load_usage()
        billing_day = usage.get("billing_start_day")
        mk = datetime.now().strftime("%Y-%m")
        launches_this_month = usage.get("launches", {}).get(mk, 0)
        reset_in = None
        if billing_day:
            try:
                billing_day = int(billing_day)
                today = datetime.now()
                next_reset = today.replace(day=billing_day) if today.day < billing_day else (
                    today.replace(year=today.year + 1, month=1, day=billing_day)
                    if today.month == 12
                    else today.replace(month=today.month + 1, day=billing_day)
                )
                reset_in = (next_reset.date() - today.date()).days
            except Exception:
                reset_in = None
        return {
            "billing_start_day":  billing_day,
            "launches_this_month": launches_this_month,
            "reset_in_days":      reset_in,
        }

    def set_billing_day(self, day):
        try:
            day = int(day)
            if not (1 <= day <= 28):
                return {"ok": False, "error": "Day must be 1-28"}
            usage = load_usage()
            usage["billing_start_day"] = day
            save_usage(usage)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    index = os.path.join(SCRIPT_DIR, "index.html").replace("\\", "/")
    window = webview.create_window(
        "Claude Code Launcher",
        f"file:///{index}",
        js_api=Api(),
        width=1280, height=740,
        min_size=(800, 500),
        resizable=True,
    )

    # ── System tray (Feature 4) ──
    tray_icon = None
    if HAS_TRAY:
        def on_closing():
            global _closing
            if _closing:
                return
            window.hide()
            return False

        def show_window(icon=None, item=None):
            window.show()

        def exit_app(icon=None, item=None):
            global _closing
            _closing = True
            if tray_icon:
                tray_icon.stop()
            window.destroy()

        icon_path = os.path.join(SCRIPT_DIR, "icon.ico")
        if os.path.exists(icon_path):
            tray_img = PILImage.open(icon_path).resize((64, 64)).convert("RGBA")
        else:
            tray_img = PILImage.new("RGBA", (64, 64), (30, 30, 80, 255))

        tray_icon = pystray.Icon(
            "claude_launcher",
            tray_img,
            "Claude Code Launcher",
            menu=pystray.Menu(
                pystray.MenuItem("Show", show_window, default=True),
                pystray.MenuItem("Exit", exit_app),
            ),
        )
        window.events.closing += on_closing
        threading.Thread(target=tray_icon.run, daemon=True).start()

    webview.start()
