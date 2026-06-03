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
USAGE_FILE = os.path.join(SCRIPT_DIR, "usage.json")
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


def load_usage():
    if os.path.exists(USAGE_FILE):
        with open(USAGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"billing_start_day": None, "launches": {}}


def save_usage(data):
    with open(USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


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


def get_git_status(win_path):
    git_dir = os.path.join(win_path, ".git")
    if not os.path.isdir(git_dir):
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
            status = info.get("status", "ACTIVE")
            mtime  = get_last_modified(win_path)
            git    = get_git_status(win_path)
            projects.append({
                "name":          folder,
                "wsl_path":      f"{WSL_BASE}/{folder}",
                "description":   info.get("description", "Click ✎ to edit description."),
                "color":         info.get("color", "#888899"),
                "tech":          info.get("tech", []),
                "status":        status,
                "status_color":  STATUS_COLORS.get(status, "#888899"),
                "last_modified": fmt_ago(mtime),
                "last_launched": fmt_ago(info.get("last_launched")),
                "launch_cmd":    info.get("launch_cmd", ""),
                "notes":         info.get("notes", ""),
                "archived":      info.get("archived", False),
                "port":          info.get("port", ""),
                "git":           git,
            })
    except Exception as e:
        print(f"Scan error: {e}")
    return projects


class Api:
    def get_projects(self, show_archived=False):
        return scan_projects(show_archived)

    def get_project_meta(self, name):
        meta = load_meta()
        return meta.get(name, {})

    def launch_project(self, name, wsl_path, launch_cmd=""):
        try:
            meta = load_meta()
            if name not in meta:
                meta[name] = {}
            meta[name]["last_launched"] = time.time()
            save_meta(meta)

            usage = load_usage()
            month_key = datetime.now().strftime("%Y-%m")
            launches = usage.get("launches", {})
            launches[month_key] = launches.get(month_key, 0) + 1
            usage["launches"] = launches
            save_usage(usage)

            cmd = launch_cmd or meta.get(name, {}).get("launch_cmd", "")
            if not cmd:
                cmd = f"cd '{wsl_path}' && claude"

            subprocess.Popen(
                ["wt.exe", "wsl.exe", "-e", "bash", "-ic", cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def open_explorer(self, name):
        try:
            win_path = os.path.join(WIN_BASE, name)
            subprocess.Popen(["explorer.exe", win_path])
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def open_vscode(self, name):
        try:
            win_path = os.path.join(WIN_BASE, name)
            subprocess.Popen(f'code "{win_path}"', shell=True)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def open_browser(self, name, port):
        try:
            if not port:
                return {"ok": False, "error": "No port set"}
            url = f"http://localhost:{port}"
            subprocess.Popen(["cmd.exe", "/c", "start", "", url])
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
        meta[name]["description"] = description
        meta[name]["color"]       = color
        meta[name]["tech"]        = tech if isinstance(tech, list) else []
        meta[name]["status"]      = status if status in STATUS_COLORS else "ACTIVE"
        meta[name]["launch_cmd"]  = launch_cmd
        meta[name]["notes"]       = notes
        meta[name]["port"]        = str(port) if port else ""
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

    def toggle_archive(self, name):
        meta = load_meta()
        if name not in meta:
            meta[name] = {}
        archived = not meta[name].get("archived", False)
        meta[name]["archived"] = archived
        save_meta(meta)
        return {"ok": True, "archived": archived}

    def get_usage(self):
        usage = load_usage()
        billing_day = usage.get("billing_start_day")
        month_key = datetime.now().strftime("%Y-%m")
        launches_this_month = usage.get("launches", {}).get(month_key, 0)
        reset_in = None
        if billing_day:
            try:
                billing_day = int(billing_day)
                today = datetime.now()
                if today.day < billing_day:
                    next_reset = today.replace(day=billing_day)
                else:
                    if today.month == 12:
                        next_reset = today.replace(year=today.year + 1, month=1, day=billing_day)
                    else:
                        next_reset = today.replace(month=today.month + 1, day=billing_day)
                reset_in = (next_reset.date() - today.date()).days
            except Exception:
                reset_in = None
        return {
            "billing_start_day": billing_day,
            "launches_this_month": launches_this_month,
            "reset_in_days": reset_in,
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
        width=1280,
        height=740,
        min_size=(800, 500),
        resizable=True,
    )
    webview.start()
