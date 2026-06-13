"""
claude_sessions.py — JSONL session parser and usage cache for Claude Code Launcher.
Runs on Windows Python; reads session files via UNC path (wsl.localhost).
"""

import json
import os
import re
import time
import threading
from datetime import datetime, timezone

# ── Pricing (USD per million tokens) ── #
# (input, output, cache_write, cache_read)
_PRICING = {
    "claude-sonnet-4-6":       (3.00, 15.00, 3.75,  0.30),
    "claude-haiku-4-5":        (1.00,  5.00, 1.25,  0.10),
    "claude-opus-4-8":         (5.00, 25.00, 6.25,  0.50),
    "claude-opus-4-5":         (5.00, 25.00, 6.25,  0.50),
    "claude-fable-5":          (10.00, 50.00, 12.50, 1.00),
}
_DEFAULT_PRICE = _PRICING["claude-sonnet-4-6"]
_CACHE_VERSION = 1

_usage_cache      = {}     # abs_path -> file-level parsed data
_usage_cache_lock = threading.Lock()
_sessions_root    = None   # resolved UNC root, or None if unavailable


def _model_key(model):
    """Normalise 'claude-haiku-4-5-20251001' -> 'claude-haiku-4-5'."""
    if not model or "<synthetic>" in model:
        return None
    m = re.match(r'(claude-[a-z0-9]+-[0-9]+(?:-[0-9]+)?)', model)
    return m.group(1) if m else model.split("-20")[0]


def _price(model_key):
    if model_key and model_key in _PRICING:
        return _PRICING[model_key]
    return _DEFAULT_PRICE


def _cost_usd(usage_dict):
    """Estimate cost from a {in, out, cw, cr} dict."""
    total = 0.0
    for mk, counts in usage_dict.items():
        pi, po, pcw, pcr = _price(mk)
        total += counts["in"]  * pi  / 1_000_000
        total += counts["out"] * po  / 1_000_000
        total += counts["cw"]  * pcw / 1_000_000
        total += counts["cr"]  * pcr / 1_000_000
    return total


def encode_project_dir(wsl_path):
    return re.sub(r"[^A-Za-z0-9]", "-", wsl_path)


def _claude_projects_root(settings):
    """Return the Windows-accessible path to ~/.claude/projects/, or None."""
    distro = settings.get("wsl_distro", "Ubuntu")
    for prefix in (f"\\\\wsl.localhost\\{distro}", f"\\\\wsl$\\{distro}"):
        p = os.path.join(prefix, "home", "admins", ".claude", "projects")
        try:
            if os.path.isdir(p):
                return p
        except Exception:
            pass
    return None


def _parse_file(path):
    """
    Parse one JSONL session file. Returns:
      {"usage": {model_key: {in, out, cw, cr}},
       "session": {id, start, end, first_prompt, msg_count}}
    Returns None on any fatal error.
    """
    usage      = {}
    session_id = None
    start_ts   = None
    end_ts     = None
    first_prompt = ""
    msg_count  = 0

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    d = json.loads(raw)
                except Exception:
                    continue

                typ = d.get("type")
                ts  = d.get("timestamp", "")
                if ts and (start_ts is None or ts < start_ts):
                    start_ts = ts
                if ts and (end_ts is None or ts > end_ts):
                    end_ts = ts

                sid = d.get("sessionId")
                if sid and not session_id:
                    session_id = sid

                if typ == "assistant":
                    msg  = d.get("message") or {}
                    model = _model_key(msg.get("model", ""))
                    if not model:
                        continue
                    u = msg.get("usage") or {}
                    counts = usage.setdefault(model, {"in": 0, "out": 0, "cw": 0, "cr": 0})
                    counts["in"]  += u.get("input_tokens", 0) or 0
                    counts["out"] += u.get("output_tokens", 0) or 0
                    counts["cw"]  += u.get("cache_creation_input_tokens", 0) or 0
                    counts["cr"]  += u.get("cache_read_input_tokens", 0) or 0
                    if not d.get("isSidechain"):
                        msg_count += 1

                elif typ == "user" and not first_prompt:
                    content = (d.get("message") or {}).get("content", "")
                    if isinstance(content, str) and content.strip() and not content.strip().startswith("<"):
                        first_prompt = content.strip()[:80]

    except Exception:
        return None

    return {
        "usage": usage,
        "session": {
            "id":           session_id or os.path.splitext(os.path.basename(path))[0],
            "start":        start_ts or "",
            "end":          end_ts or "",
            "first_prompt": first_prompt,
            "msg_count":    msg_count,
        },
    }


def _fmt_ts_ago(iso_str):
    if not iso_str:
        return ""
    try:
        ts = datetime.fromisoformat(iso_str.replace("Z", "+00:00")).timestamp()
        diff = time.time() - ts
        if diff < 60:    return "just now"
        if diff < 3600:  return f"{int(diff/60)}m ago"
        if diff < 86400: return f"{int(diff/3600)}h ago"
        if diff < 86400*7: return f"{int(diff/86400)}d ago"
        return datetime.fromtimestamp(ts).strftime("%b %Y")
    except Exception:
        return ""


def refresh_sessions(settings, script_dir):
    """
    Scan all project session dirs, update _usage_cache.
    Called from the background scan thread in launcher.py.
    """
    global _sessions_root
    root = _claude_projects_root(settings)
    _sessions_root = root
    if not root:
        return

    # Load persisted cache
    cache_file = os.path.join(script_dir, "claude_usage_cache.json")
    with _usage_cache_lock:
        persisted = dict(_usage_cache)

    try:
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("v") == _CACHE_VERSION:
                with _usage_cache_lock:
                    for k, v in data.get("files", {}).items():
                        if k not in _usage_cache:
                            _usage_cache[k] = v
    except Exception:
        pass

    # Scan JSONL files
    changed = False
    try:
        for proj_dir in os.scandir(root):
            if not proj_dir.is_dir():
                continue
            try:
                for entry in os.scandir(proj_dir.path):
                    if not entry.name.endswith(".jsonl"):
                        continue
                    path = entry.path
                    try:
                        st = os.stat(path)
                    except OSError:
                        continue
                    mtime = st.st_mtime
                    size  = st.st_size

                    with _usage_cache_lock:
                        cached = _usage_cache.get(path)

                    if cached and cached.get("mtime") == mtime and cached.get("size") == size:
                        continue

                    parsed = _parse_file(path)
                    if parsed is None:
                        continue

                    entry_data = {"mtime": mtime, "size": size, **parsed}
                    with _usage_cache_lock:
                        _usage_cache[path] = entry_data
                    changed = True
            except Exception:
                continue
    except Exception:
        return

    if changed:
        # Persist cache
        try:
            with _usage_cache_lock:
                snapshot = dict(_usage_cache)
            payload = {"v": _CACHE_VERSION, "files": snapshot}
            import tempfile
            fd, tmp = tempfile.mkstemp(dir=script_dir, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            os.replace(tmp, cache_file)
        except Exception:
            pass


def get_claude_usage(settings, billing_day=None):
    """
    Return aggregated usage data.
    {
      per_project: {encoded_dir: {tokens, est_cost, last_active_ts, live}},
      total:       {tokens, est_cost},
      period:      {tokens, est_cost},   # since billing day
    }
    """
    if _sessions_root is None:
        return None

    now = time.time()
    # Billing period start
    period_start = 0.0
    if billing_day:
        try:
            from datetime import date
            today = date.today()
            bd = int(billing_day)
            if today.day >= bd:
                p = today.replace(day=bd)
            else:
                # previous month
                import calendar
                prev_month = today.month - 1 or 12
                prev_year  = today.year if today.month > 1 else today.year - 1
                last_day   = calendar.monthrange(prev_year, prev_month)[1]
                p = date(prev_year, prev_month, min(bd, last_day))
            from datetime import datetime as _dt
            period_start = _dt(p.year, p.month, p.day).timestamp()
        except Exception:
            pass

    per_project  = {}
    total_tokens = {"in": 0, "out": 0, "cw": 0, "cr": 0}
    total_cost   = 0.0
    period_tokens= {"in": 0, "out": 0, "cw": 0, "cr": 0}
    period_cost  = 0.0

    with _usage_cache_lock:
        snapshot = dict(_usage_cache)

    for path, entry in snapshot.items():
        proj_dir   = os.path.basename(os.path.dirname(path))
        mtime      = entry.get("mtime", 0)
        file_usage = entry.get("usage", {})
        file_cost  = _cost_usd(file_usage)

        p = per_project.setdefault(proj_dir, {
            "tokens":        {"in": 0, "out": 0, "cw": 0, "cr": 0},
            "est_cost":      0.0,
            "last_active_ts": 0.0,
            "live":          False,
        })
        for mk, counts in file_usage.items():
            for k in ("in", "out", "cw", "cr"):
                v = counts.get(k, 0)
                p["tokens"][k]  += v
                total_tokens[k] += v
                if mtime >= period_start:
                    period_tokens[k] += v
        p["est_cost"] += file_cost
        total_cost    += file_cost
        if mtime >= period_start:
            period_cost += file_cost
        if mtime > p["last_active_ts"]:
            p["last_active_ts"] = mtime
        if now - mtime < 120:
            p["live"] = True

    def _tok_sum(t): return t["in"] + t["out"] + t["cw"] + t["cr"]

    return {
        "per_project": per_project,
        "total": {
            "tokens":   total_tokens,
            "tok_sum":  _tok_sum(total_tokens),
            "est_cost": total_cost,
        },
        "period": {
            "tokens":   period_tokens,
            "tok_sum":  _tok_sum(period_tokens),
            "est_cost": period_cost,
        },
    }


def get_sessions(wsl_path, max_results=20):
    """
    Return list of sessions for a project, sorted by end time desc.
    Each: {id, start_ts, start_ago, first_prompt, msg_count}
    """
    if _sessions_root is None:
        return []

    proj_dir = os.path.join(_sessions_root, encode_project_dir(wsl_path))
    sessions = []

    with _usage_cache_lock:
        for path, entry in _usage_cache.items():
            if not path.startswith(proj_dir):
                continue
            s = entry.get("session", {})
            start_ts_raw = s.get("end") or s.get("start") or ""
            try:
                end_ts = datetime.fromisoformat(start_ts_raw.replace("Z", "+00:00")).timestamp()
            except Exception:
                end_ts = entry.get("mtime", 0)
            sessions.append({
                "id":           s.get("id", ""),
                "start_ts":     end_ts,
                "start_ago":    _fmt_ts_ago(s.get("end") or s.get("start", "")),
                "first_prompt": s.get("first_prompt", ""),
                "msg_count":    s.get("msg_count", 0),
            })

    sessions.sort(key=lambda x: x["start_ts"], reverse=True)
    return sessions[:max_results]


def project_usage_for_name(wsl_path):
    """
    Return (tokens_sum, est_cost, live) for one project, or None.
    """
    if _sessions_root is None:
        return None
    key = encode_project_dir(wsl_path)
    usage = get_claude_usage({})  # reads from cache only
    if usage is None:
        return None
    p = usage["per_project"].get(key)
    if not p:
        return None
    tok = p["tokens"]
    return {
        "tok_sum":  tok["in"] + tok["out"] + tok["cw"] + tok["cr"],
        "est_cost": p["est_cost"],
        "live":     p["live"],
    }
