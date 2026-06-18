import webview
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import threading
from datetime import datetime

import claude_sessions

try:
    import pystray
    from PIL import Image as PILImage
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

# ── Single-instance guard ──
import ctypes
_MUTEX_NAME = "Global\\ClaudeCodeLauncher_SingleInstance"
_mutex = ctypes.windll.kernel32.CreateMutexW(None, False, _MUTEX_NAME)
if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
    # Bring existing window to foreground via EnumWindows
    import ctypes.wintypes
    HWND_found = ctypes.wintypes.HWND(0)
    target = "Claude Code Launcher"
    def _enum(hwnd, _):
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
        if target in buf.value:
            ctypes.windll.user32.ShowWindow(hwnd, 9)   # SW_RESTORE
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            return False
        return True
    ctypes.windll.user32.EnumWindows(
        ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)(_enum),
        0,
    )
    sys.exit(0)

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
META_FILE     = os.path.join(SCRIPT_DIR, "projects.json")
USAGE_FILE    = os.path.join(SCRIPT_DIR, "usage.json")
SETTINGS_FILE = os.path.join(SCRIPT_DIR, "settings.json")
EXCLUDE       = {"launcher", ".git", "__pycache__"}
SKIP_DIRS     = {".git", "node_modules", "__pycache__", ".next", "venv", ".venv", ".mypy_cache", "dist", "build"}

# Defaults — overridden at startup from settings.json
_DEFAULT_WIN_BASE = os.path.dirname(SCRIPT_DIR)
WIN_BASE   = _DEFAULT_WIN_BASE
WSL_BASE   = "/mnt/d/Claude Code"

DEFAULT_SETTINGS = {
    "win_base":          _DEFAULT_WIN_BASE,
    "wsl_base":          "",
    "wsl_distro":        "Ubuntu",
    "poll_interval_sec": 5,
    "scan_interval_sec": 60,
    "theme":             "neon",
    "summer":            True,
}


def _derive_wsl_base(win_base):
    """D:\\Claude Code -> /mnt/d/Claude Code"""
    import pathlib
    try:
        wp   = pathlib.PureWindowsPath(win_base)
        drive= wp.drive.lower().rstrip(":")
        rest = "/".join(p for p in wp.parts[1:])
        return f"/mnt/{drive}/{rest}"
    except Exception:
        return WSL_BASE

STATUS_COLORS = {
    "ACTIVE": "#a8e063",
    "WIP":    "#ffe66d",
    "PAUSED": "#888899",
    "DONE":   "#4ecdc4",
}

_closing  = False
_io_lock  = threading.Lock()


def _save_json(path, data):
    with _io_lock:
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


def sq(s):
    """POSIX single-quote escape for embedding paths in bash -ic strings."""
    return "'" + str(s).replace("'", "'\\''") + "'"


_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}


def _repo_name_from_url(url):
    """Extract repo name from GitHub URL or gh shorthand (user/repo)."""
    url = url.strip().rstrip("/")
    name = url.split("/")[-1].split(":")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name


def validate_name(name):
    name = name.strip()
    if not name or len(name) > 100:
        return "Name required (max 100 chars)"
    if re.search(r'[<>:"/\\|?*\x00-\x1f]', name):
        return "Illegal characters in name"
    if ".." in name or name != name.rstrip(". "):
        return "Invalid name"
    if name.split(".")[0].upper() in _RESERVED:
        return "Reserved Windows name"
    target = os.path.realpath(os.path.join(WIN_BASE, name))
    base   = os.path.realpath(WIN_BASE) + os.sep
    if not target.startswith(base):
        return "Name resolves outside base dir"
    return None


def load_meta():
    with _io_lock:
        try:
            if os.path.exists(META_FILE):
                with open(META_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
    return {}


def save_meta(data):
    _save_json(META_FILE, data)


def load_usage():
    with _io_lock:
        try:
            if os.path.exists(USAGE_FILE):
                with open(USAGE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
    return {"billing_start_day": None, "launches": {}}


def save_usage(data):
    _save_json(USAGE_FILE, data)


def load_settings():
    with _io_lock:
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {**DEFAULT_SETTINGS, **data}
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)


def _save_settings_data(data):
    _save_json(SETTINGS_FILE, data)


# ── Apply settings to module globals at startup ──
def _apply_settings_globals():
    global WIN_BASE, WSL_BASE
    cfg = load_settings()
    WIN_BASE = cfg.get("win_base", WIN_BASE)
    WSL_BASE = cfg.get("wsl_base") or _derive_wsl_base(WIN_BASE)

_apply_settings_globals()


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
        lines  = result.stdout.strip().splitlines()
        branch = "main"
        ahead  = 0
        behind = 0
        if lines and lines[0].startswith("## "):
            b = lines[0][3:]
            if "..." in b:
                branch = b.split("...")[0]
                m = re.search(r'\[ahead (\d+)', b)
                if m:
                    ahead = int(m.group(1))
                m = re.search(r'behind (\d+)', b)
                if m:
                    behind = int(m.group(1))
            elif b.startswith("HEAD"):
                branch = "HEAD"
            else:
                branch = b.strip()
        dirty = len([l for l in lines[1:] if l.strip()])
        return {"branch": branch, "dirty": dirty, "ahead": ahead, "behind": behind}
    except Exception:
        return None


_scan_cache = {}
_scan_lock  = threading.Lock()


def _get_remote_url(win_path):
    """Return normalized HTTPS remote URL, or None."""
    try:
        r = subprocess.run(
            ["git", "-C", win_path, "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=3,
            encoding="utf-8", errors="replace",
        )
        if r.returncode != 0:
            return None
        url = r.stdout.strip()
        # Normalize ssh -> https
        if url.startswith("git@github.com:"):
            url = "https://github.com/" + url[len("git@github.com:"):].removesuffix(".git")
        elif url.endswith(".git"):
            url = url[:-4]
        if url.startswith(("https://", "http://")):
            return url
        return None
    except Exception:
        return None


def _refresh_folder(folder):
    win_path = os.path.join(WIN_BASE, folder)
    try:
        mtime, sz  = scan_folder(win_path)
        git        = get_git_status(win_path)
        readme     = get_readme_description(win_path)
        remote_url = _get_remote_url(win_path)
    except Exception:
        return
    with _scan_lock:
        _scan_cache[folder] = {
            "mtime":       mtime,
            "size":        sz,
            "git":         git,
            "readme_desc": readme,
            "remote_url":  remote_url,
            "scanned_at":  time.time(),
        }


def _scan_once():
    try:
        folders = [
            f for f in sorted(os.listdir(WIN_BASE))
            if f not in EXCLUDE and os.path.isdir(os.path.join(WIN_BASE, f))
        ]
        for folder in folders:
            _refresh_folder(folder)
    except Exception as e:
        print(f"Scan error: {e}")
    try:
        claude_sessions.refresh_sessions(load_settings(), SCRIPT_DIR)
    except Exception as e:
        print(f"Session scan error: {e}")


def _scan_worker():
    while True:
        _scan_once()
        interval = load_settings().get("scan_interval_sec", 60)
        time.sleep(max(10, interval))


def refresh_now(name):
    threading.Thread(target=_refresh_folder, args=(name,), daemon=True).start()


DEFAULT_DESC = "Click ✎ to edit description."


def scan_projects(show_archived=False):
    meta = load_meta()
    projects = []
    # Compute usage map once — O(files) not O(projects × files)
    _all_usage = claude_sessions.get_claude_usage({})
    usage_map  = _all_usage["per_project"] if _all_usage else {}
    try:
        new_folders = []
        for folder in sorted(os.listdir(WIN_BASE)):
            if folder in EXCLUDE:
                continue
            win_path = os.path.join(WIN_BASE, folder)
            if not os.path.isdir(win_path):
                continue
            info = meta.get(folder, {})
            if info.get("archived", False) and not show_archived:
                continue

            with _scan_lock:
                cached = _scan_cache.get(folder)

            if cached is None:
                new_folders.append(folder)
                mtime, sz, git, readme = 0, 0, None, None
            else:
                mtime  = cached["mtime"]
                sz     = cached["size"]
                git    = cached["git"]
                readme = cached["readme_desc"]

            status      = info.get("status", "ACTIVE")
            last_launch = info.get("last_launched", 0)

            desc = info.get("description", "")
            if not desc or desc == DEFAULT_DESC:
                desc = readme or DEFAULT_DESC

            wsl_path   = f"{WSL_BASE}/{folder}"
            usage_key  = claude_sessions.encode_project_dir(wsl_path)
            proj_usage = usage_map.get(usage_key)
            has_sessions = usage_key in usage_map

            projects.append({
                "name":             folder,
                "wsl_path":         wsl_path,
                "description":      desc,
                "color":            info.get("color", "#888899"),
                "tech":             info.get("tech", []),
                "status":           status,
                "status_color":     STATUS_COLORS.get(status, "#888899"),
                "last_modified":    fmt_ago(mtime) if mtime else "...",
                "last_modified_ts": mtime,
                "last_launched":    fmt_ago(last_launch),
                "last_launched_ts": last_launch,
                "launch_cmd":       info.get("launch_cmd", ""),
                "notes":            info.get("notes", ""),
                "archived":         info.get("archived", False),
                "port":             info.get("port", ""),
                "git":              git,
                "disk_size":        fmt_size(sz) if sz else "...",
                "pinned":           info.get("pinned", False),
                "remote_url":       (cached or {}).get("remote_url"),
                "live":             (proj_usage or {}).get("live", False),
                "tok_sum":          (proj_usage or {}).get("tok_sum", 0),
                "est_cost":         (proj_usage or {}).get("est_cost", 0.0),
                "has_sessions":     has_sessions,
            })

        for folder in new_folders:
            refresh_now(folder)

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

            win_path = os.path.join(WIN_BASE, name)
            custom = launch_cmd or meta.get(name, {}).get("launch_cmd", "")
            shell_cmd = custom if custom else "claude"

            wt = shutil.which("wt.exe") or shutil.which("wt")
            if wt:
                subprocess.Popen(
                    [wt, "cmd.exe", "/k", shell_cmd],
                    cwd=win_path,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.Popen(
                    ["cmd.exe", "/k", shell_cmd],
                    cwd=win_path,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                    close_fds=True,
                )
            refresh_now(name)
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
            code = shutil.which("code")
            if not code:
                return {"ok": False, "error": "VS Code not found in PATH"}
            subprocess.Popen([code, os.path.join(WIN_BASE, name)])
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

    def add_project(self, name, description, color, tech, status="ACTIVE", create_repo=False):
        name = name.strip()
        err = validate_name(name)
        if err:
            return {"ok": False, "error": err}
        os.makedirs(os.path.join(WIN_BASE, name), exist_ok=True)
        meta = load_meta()
        meta[name] = {
            "description": description or DEFAULT_DESC,
            "color":       color or "#888899",
            "tech":        tech if isinstance(tech, list) else [],
            "status":      status if status in STATUS_COLORS else "ACTIVE",
        }
        save_meta(meta)
        refresh_now(name)
        result = {"ok": True}
        if create_repo:
            import threading as _t
            _t.Thread(target=lambda: self.create_github_repo(name, description), daemon=True).start()
            result["repo_creating"] = True
        return result

    def toggle_archive(self, name):
        meta = load_meta()
        meta.setdefault(name, {})
        archived = not meta[name].get("archived", False)
        meta[name]["archived"] = archived
        save_meta(meta)
        refresh_now(name)
        return {"ok": True, "archived": archived}

    def toggle_pin(self, name):
        meta = load_meta()
        meta.setdefault(name, {})
        pinned = not meta[name].get("pinned", False)
        meta[name]["pinned"] = pinned
        save_meta(meta)
        refresh_now(name)
        return {"ok": True, "pinned": pinned}

    def open_repo(self, name):
        with _scan_lock:
            cached = _scan_cache.get(name, {})
        url = cached.get("remote_url")
        if not url:
            return {"ok": False, "error": "No remote URL found"}
        if not url.startswith(("https://", "http://")):
            return {"ok": False, "error": "Invalid URL"}
        try:
            subprocess.Popen(["cmd.exe", "/c", "start", "", url])
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def git_pull(self, name):
        def _do_pull():
            win_path = os.path.join(WIN_BASE, name)
            try:
                r = subprocess.run(
                    ["git", "-C", win_path, "pull", "--ff-only"],
                    capture_output=True, text=True, timeout=30,
                    encoding="utf-8", errors="replace",
                )
                refresh_now(name)
                out = (r.stdout + r.stderr).strip()[:200]
                if r.returncode == 0:
                    return {"ok": True, "msg": out or "Already up to date."}
                return {"ok": False, "error": out}
            except subprocess.TimeoutExpired:
                return {"ok": False, "error": "Timed out"}
            except Exception as e:
                return {"ok": False, "error": str(e)}
        import concurrent.futures
        fut = concurrent.futures.ThreadPoolExecutor(max_workers=1).submit(_do_pull)
        try:
            return fut.result(timeout=35)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_commit_preview(self, name):
        win_path = os.path.join(WIN_BASE, name)
        try:
            r = subprocess.run(
                ["git", "-C", win_path, "status", "--porcelain"],
                capture_output=True, text=True, timeout=5,
                encoding="utf-8", errors="replace",
            )
            lines = r.stdout.strip().splitlines()[:25]
            n = len(r.stdout.strip().splitlines())
            today = datetime.now().strftime("%Y-%m-%d")
            default_msg = f"Update: {n} file(s) changed ({today})"
            return {"ok": True, "files": "\n".join(lines), "default_msg": default_msg, "count": n}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def commit_push(self, name, message):
        def _do():
            win_path = os.path.join(WIN_BASE, name)
            try:
                if not message or not message.strip():
                    return {"ok": False, "error": "Commit message required"}
                msg = message.strip()[:200]
                # Stage
                r = subprocess.run(["git", "-C", win_path, "add", "-A"],
                    capture_output=True, text=True, timeout=10)
                if r.returncode != 0:
                    return {"ok": False, "error": r.stderr.strip()[:200]}
                # Commit
                r = subprocess.run(["git", "-C", win_path, "commit", "-m", msg],
                    capture_output=True, text=True, timeout=10,
                    encoding="utf-8", errors="replace")
                if r.returncode != 0:
                    err = r.stderr.strip() or r.stdout.strip()
                    return {"ok": False, "error": err[:200]}
                # Push only if remote exists
                with _scan_lock:
                    remote_url = _scan_cache.get(name, {}).get("remote_url")
                if remote_url:
                    r = subprocess.run(["git", "-C", win_path, "push"],
                        capture_output=True, text=True, timeout=60,
                        encoding="utf-8", errors="replace")
                    if r.returncode != 0:
                        err = (r.stderr + r.stdout).strip()[:200]
                        return {"ok": False, "error": f"Committed but push failed: {err}"}
                    refresh_now(name)
                    return {"ok": True, "msg": "Committed and pushed."}
                else:
                    refresh_now(name)
                    return {"ok": True, "msg": "Committed (no remote — push skipped)."}
            except subprocess.TimeoutExpired:
                return {"ok": False, "error": "Timed out"}
            except Exception as e:
                return {"ok": False, "error": str(e)}
        import concurrent.futures
        fut = concurrent.futures.ThreadPoolExecutor(max_workers=1).submit(_do)
        try:
            return fut.result(timeout=70)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def create_github_repo(self, name, description):
        def _do():
            win_path = os.path.join(WIN_BASE, name)
            try:
                gh = shutil.which("gh")
                if not gh:
                    return {"ok": False, "error": "gh CLI not found in PATH"}
                # git init
                subprocess.run(["git", "-C", win_path, "init", "-b", "main"],
                    capture_output=True, timeout=10)
                # Write README if missing
                readme_path = os.path.join(win_path, "README.md")
                if not os.path.exists(readme_path):
                    with open(readme_path, "w", encoding="utf-8") as f:
                        desc = description or "A Claude Code project."
                        f.write(f"# {name}\n\n{desc}\n")
                # git add + commit
                subprocess.run(["git", "-C", win_path, "add", "-A"],
                    capture_output=True, timeout=10)
                r = subprocess.run(["git", "-C", win_path, "commit", "-m", "Initial commit"],
                    capture_output=True, text=True, timeout=10)
                if r.returncode != 0 and "nothing to commit" not in (r.stdout + r.stderr):
                    return {"ok": False, "error": r.stderr.strip()[:200]}
                # gh repo create
                r = subprocess.run(
                    [gh, "repo", "create", name, "--private", "--source", win_path, "--push"],
                    capture_output=True, text=True, timeout=60,
                    encoding="utf-8", errors="replace",
                )
                if r.returncode != 0:
                    return {"ok": False, "error": (r.stderr + r.stdout).strip()[:300]}
                refresh_now(name)
                return {"ok": True}
            except subprocess.TimeoutExpired:
                return {"ok": False, "error": "Timed out"}
            except Exception as e:
                return {"ok": False, "error": str(e)}
        import concurrent.futures
        fut = concurrent.futures.ThreadPoolExecutor(max_workers=1).submit(_do)
        try:
            return fut.result(timeout=70)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def clone_project(self, url, custom_name=""):
        name = custom_name.strip() or _repo_name_from_url(url)
        err = validate_name(name)
        if err:
            return {"ok": False, "error": err}
        win_path = os.path.join(WIN_BASE, name)
        if os.path.isdir(win_path):
            return {"ok": False, "error": "exists", "name": name}

        def _do():
            try:
                gh = shutil.which("gh")
                cmd = [gh, "repo", "clone", url, win_path] if gh else ["git", "clone", url, win_path]
                r = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=120, encoding="utf-8", errors="replace",
                )
                if r.returncode != 0:
                    return {"ok": False, "error": (r.stderr + r.stdout).strip()[:300]}
                meta = load_meta()
                meta[name] = {"description": "", "color": "#888899",
                              "tech": [], "status": "ACTIVE"}
                save_meta(meta)
                refresh_now(name)
                return {"ok": True, "name": name}
            except subprocess.TimeoutExpired:
                return {"ok": False, "error": "Timed out (120s)"}
            except Exception as e:
                return {"ok": False, "error": str(e)}

        import concurrent.futures
        fut = concurrent.futures.ThreadPoolExecutor(max_workers=1).submit(_do)
        try:
            return fut.result(timeout=125)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_claude_usage(self):
        usage_data = load_usage()
        billing_day = usage_data.get("billing_start_day")
        return claude_sessions.get_claude_usage(load_settings(), billing_day)

    def get_sessions(self, name, wsl_path):
        return claude_sessions.get_sessions(wsl_path)

    def resume_project(self, name, wsl_path, session_id=""):
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

            win_path = os.path.join(WIN_BASE, name)
            if session_id:
                if not re.match(r'^[0-9a-f\-]{36}$', session_id):
                    return {"ok": False, "error": "Invalid session id"}
                shell_cmd = f"claude --resume {session_id}"
            else:
                shell_cmd = "claude --continue"

            wt = shutil.which("wt.exe") or shutil.which("wt")
            if wt:
                subprocess.Popen(
                    [wt, "cmd.exe", "/k", shell_cmd],
                    cwd=win_path,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.Popen(
                    ["cmd.exe", "/k", shell_cmd],
                    cwd=win_path,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                    close_fds=True,
                )
            refresh_now(name)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_settings(self):
        return load_settings()

    def api_save_settings(self, settings):
        global WIN_BASE, WSL_BASE
        try:
            wb = settings.get("win_base", WIN_BASE).strip()
            if not os.path.isdir(wb):
                return {"ok": False, "error": f"Directory not found: {wb}"}
            wsl = settings.get("wsl_base", "").strip() or _derive_wsl_base(wb)
            existing = load_settings()
            merged = {**existing, **settings, "win_base": wb, "wsl_base": wsl}
            _save_settings_data(merged)
            WIN_BASE = wb
            WSL_BASE = wsl
            with _scan_lock:
                _scan_cache.clear()
            threading.Thread(target=_scan_once, daemon=True).start()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def delete_project(self, name, confirm_name):
        if name != confirm_name:
            return {"ok": False, "error": "Name mismatch — type the project name exactly"}
        err = validate_name(name)
        if err:
            return {"ok": False, "error": err}
        win_path = os.path.join(WIN_BASE, name)
        if not os.path.isdir(win_path):
            return {"ok": False, "error": "Folder not found"}
        try:
            try:
                import send2trash
                send2trash.send2trash(win_path)
            except ImportError:
                import base64
                ps_cmd = (
                    f"Add-Type -AssemblyName Microsoft.VisualBasic; "
                    f"[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory("
                    f"'{win_path.replace(chr(39), chr(39)+chr(39))}', "
                    f"'OnlyErrorDialogs', 'SendToRecycleBin')"
                )
                encoded = base64.b64encode(ps_cmd.encode("utf-16-le")).decode("ascii")
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-EncodedCommand", encoded],
                    capture_output=True, timeout=15)
                if r.returncode != 0:
                    return {"ok": False, "error": "Could not send to Recycle Bin"}
            meta = load_meta()
            meta.pop(name, None)
            save_meta(meta)
            with _scan_lock:
                _scan_cache.pop(name, None)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def rename_project(self, old_name, new_name):
        new_name = new_name.strip()
        err = validate_name(new_name)
        if err:
            return {"ok": False, "error": err}
        old_path = os.path.join(WIN_BASE, old_name)
        new_path = os.path.join(WIN_BASE, new_name)
        if not os.path.isdir(old_path):
            return {"ok": False, "error": "Source folder not found"}
        if os.path.exists(new_path):
            return {"ok": False, "error": f"'{new_name}' already exists"}
        try:
            os.rename(old_path, new_path)
            meta = load_meta()
            if old_name in meta:
                meta[new_name] = meta.pop(old_name)
                save_meta(meta)
            with _scan_lock:
                old_cached = _scan_cache.pop(old_name, None)
                if old_cached:
                    _scan_cache[new_name] = old_cached
            refresh_now(new_name)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def create_desktop_shortcut(self, icon_name="icon0"):
        """Create a desktop shortcut for the launcher with the selected icon."""
        try:
            icon_file_map = {"icon0": "icon.ico", "icon1": "PixelArt.ico", "icon2": "Gold.ico"}
            icon_file = icon_file_map.get(icon_name, "icon.ico")
            icon_path   = os.path.join(SCRIPT_DIR, icon_file).replace("/", "\\")
            vbs_path    = os.path.join(SCRIPT_DIR, "start_silent.vbs").replace("/", "\\")
            lnk_name    = "Claude Code Launcher.lnk"
            ps_script = (
                f'$s = (New-Object -ComObject WScript.Shell).CreateShortcut('
                f'[System.IO.Path]::Combine([System.Environment]::GetFolderPath("Desktop"), "{lnk_name}"));'
                f'$s.TargetPath = "wscript.exe";'
                f'$s.Arguments = \'"{vbs_path}"\';'
                f'$s.IconLocation = "{icon_path}";'
                f'$s.Description = "Claude Code Launcher";'
                f'$s.WorkingDirectory = "{SCRIPT_DIR.replace("/", chr(92))}";'
                f'$s.Save()'
            )
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True, text=True, timeout=10,
                encoding="utf-8", errors="replace",
            )
            if r.returncode != 0:
                return {"ok": False, "error": (r.stderr + r.stdout).strip()[:300]}
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def open_self(self):
        """Open the launcher project itself in Claude Code."""
        try:
            wt = shutil.which("wt.exe") or shutil.which("wt")
            if wt:
                subprocess.Popen(
                    [wt, "cmd.exe", "/k", "claude"],
                    cwd=SCRIPT_DIR,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.Popen(
                    ["cmd.exe", "/k", "claude"],
                    cwd=SCRIPT_DIR,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                    close_fds=True,
                )
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def prune_meta(self):
        try:
            existing = {
                f for f in os.listdir(WIN_BASE)
                if f not in EXCLUDE and os.path.isdir(os.path.join(WIN_BASE, f))
            }
            meta = load_meta()
            orphans = [k for k in meta if k not in existing]
            for k in orphans:
                del meta[k]
            if orphans:
                save_meta(meta)
            return {"ok": True, "pruned": orphans}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_orphan_count(self):
        try:
            existing = {
                f for f in os.listdir(WIN_BASE)
                if f not in EXCLUDE and os.path.isdir(os.path.join(WIN_BASE, f))
            }
            meta = load_meta()
            return {"ok": True, "count": len([k for k in meta if k not in existing])}
        except Exception as e:
            return {"ok": False, "count": 0, "error": str(e)}

    def force_rescan(self):
        with _scan_lock:
            _scan_cache.clear()
        threading.Thread(target=_scan_once, daemon=True).start()
        return {"ok": True}

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
                next_reset = today.replace(day=billing_day) if today.day <= billing_day else (
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
    threading.Thread(target=_scan_worker, daemon=True).start()

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
