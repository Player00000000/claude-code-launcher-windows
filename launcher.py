import webview
import json
import os
import subprocess
import time
from datetime import datetime

WIN_BASE   = r"D:\Claude Code"
WSL_BASE   = "/mnt/d/Claude Code"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
META_FILE  = os.path.join(SCRIPT_DIR, "projects.json")
EXCLUDE    = {"launcher", ".git", "__pycache__"}
SKIP_DIRS  = {".git", "node_modules", "__pycache__", ".next", "venv", ".venv", ".mypy_cache", "dist", "build"}

STATUS_COLORS = {
    "ACTIVE": "#a8e063",
    "WIP":    "#ffe66d",
    "PAUSED": "#888899",
    "DONE":   "#4ecdc4",
}


def load_meta():
    if os.path.exists(META_FILE):
        with open(META_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_meta(data):
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_last_modified(win_path):
    latest = 0
    try:
        for root, dirs, files in os.walk(win_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                try:
                    mt = os.path.getmtime(os.path.join(root, f))
                    if mt > latest:
                        latest = mt
                except OSError:
                    pass
    except OSError:
        pass
    return latest


def fmt_ago(ts):
    if not ts:
        return "unknown"
    diff = time.time() - ts
    if diff < 60:
        return "just now"
    if diff < 3600:
        m = int(diff / 60)
        return f"{m}m ago"
    if diff < 86400:
        h = int(diff / 3600)
        return f"{h}h ago"
    if diff < 86400 * 7:
        d = int(diff / 86400)
        return f"{d}d ago"
    if diff < 86400 * 30:
        w = int(diff / (86400 * 7))
        return f"{w}w ago"
    return datetime.fromtimestamp(ts).strftime("%b %Y")


def scan_projects():
    meta = load_meta()
    projects = []
    try:
        for folder in sorted(os.listdir(WIN_BASE)):
            if folder in EXCLUDE:
                continue
            win_path = os.path.join(WIN_BASE, folder)
            if not os.path.isdir(win_path):
                continue
            info     = meta.get(folder, {})
            status   = info.get("status", "ACTIVE")
            mtime    = get_last_modified(win_path)
            projects.append({
                "name":         folder,
                "wsl_path":     f"{WSL_BASE}/{folder}",
                "description":  info.get("description", "Click ✎ to edit description."),
                "color":        info.get("color", "#888899"),
                "tech":         info.get("tech", []),
                "status":       status,
                "status_color": STATUS_COLORS.get(status, "#888899"),
                "last_modified": fmt_ago(mtime),
            })
    except Exception as e:
        print(f"Scan error: {e}")
    return projects


class Api:
    def get_projects(self):
        return scan_projects()

    def launch_project(self, name, wsl_path):
        try:
            subprocess.Popen(
                ["wt.exe", "wsl.exe", "-e", "bash", "-ic",
                 f"cd '{wsl_path}' && claude"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def update_project(self, name, description, color, tech, status):
        meta = load_meta()
        if name not in meta:
            meta[name] = {}
        meta[name]["description"] = description
        meta[name]["color"]       = color
        meta[name]["tech"]        = tech if isinstance(tech, list) else []
        meta[name]["status"]      = status if status in STATUS_COLORS else "ACTIVE"
        save_meta(meta)
        return {"ok": True}

    def add_project(self, name, description, color, tech, status="ACTIVE"):
        name = name.strip()
        if not name:
            return {"ok": False, "error": "Name required"}
        win_path = os.path.join(WIN_BASE, name)
        os.makedirs(win_path, exist_ok=True)
        meta = load_meta()
        meta[name] = {
            "description": description or "New project.",
            "color":       color or "#888899",
            "tech":        tech if isinstance(tech, list) else [],
            "status":      status if status in STATUS_COLORS else "ACTIVE",
        }
        save_meta(meta)
        return {"ok": True}


if __name__ == "__main__":
    index = os.path.join(SCRIPT_DIR, "index.html").replace("\\", "/")
    window = webview.create_window(
        "Claude Code Launcher",
        f"file:///{index}",
        js_api=Api(),
        width=1280,
        height=740,
        min_size=(800, 500),
        resizable=True,
    )
    webview.start()
