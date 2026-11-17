#!/usr/bin/env python3
"""
upkeep - nightly Bazzite + Decky Loader maintenance with a readable report.

  sudo upkeep run            update everything, then health-check (nightly timer)
  sudo upkeep run --manual   same, but don't wait for games to close
  sudo upkeep run --manual --only ITEM...   update just the things you name
  sudo upkeep boot           health-check after a restart (boot timer)
  sudo upkeep check          see what updates are available, change nothing
  sudo upkeep reinstall-decky   fresh copy of the latest Decky, with rollback
  sudo upkeep rollback-decky    go back to the Decky version you had before
  upkeep rollback-info       show what rollback-decky would do
  upkeep show                print the latest report

--only takes: system, decky, runtimes, plugin:<folder>, flatpak:<system|user>:<app id>

Reports:  ~/upkeep/latest.txt  ~/upkeep/latest.json  ~/upkeep/reports/
Progress: ~/upkeep/progress.json  (live, while a run is going)
Backups:  ~/upkeep/backups/   (Decky binary + plugins, before each update)
Config:   /etc/upkeep.conf
"""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import pwd
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile

CONF_PATH = "/etc/upkeep.conf"
DEFAULTS = {
    "USER": "",
    "DISTRO": "",          # bazzite | steamos  (blank = auto-detect)
    "UPKEEP_PATH": "",     # where this script is installed (set by install.sh)
    "UPDATE_SYSTEM": "yes",
    "UPDATE_FLATPAKS": "yes",
    "UPDATE_DECKY": "yes",
    "UPDATE_PLUGINS": "yes",
    "HOLD_PLUGINS": "",    # comma-separated plugin names to report on but never update
    "SLEEP_AFTER_WAKE": "yes",
    "GAME_WAIT_HOURS": "6",
    "KEEP_REPORTS_DAYS": "30",
    "KEEP_BACKUPS": "5",
}
DECKY_SERVICE = "plugin_loader.service"
DECKY_PORT = 1337
DECKY_RELEASE_API = "https://api.github.com/repos/SteamDeckHomebrew/decky-loader/releases/latest"
DECKY_RELEASES_API = "https://api.github.com/repos/SteamDeckHomebrew/decky-loader/releases?per_page=30"
STORE_URL = "https://plugins.deckbrew.xyz/plugins"
STORE_CDN = "https://cdn.tzatzikiweeb.moe/file/steam-deck-homebrew/versions/{hash}.zip"
LOCK_PATH = "/run/upkeep.lock"
DISTRO_NAMES = {"bazzite": "Bazzite", "steamos": "SteamOS"}

# What counts as "this plugin had a problem" in Decky's logs
JOURNAL_ERR = re.compile(r"Traceback|\bERROR\b|\bCRITICAL\b|Exception|[Ff]ailed to (load|start|import)|timed out")
# In a plugin's own log only a crash counts. Plain ERROR lines are routine in
# healthy plugins (Decky Sunshine logs one on every normal start).
PLUGIN_LOG_ERR = re.compile(r"\bCRITICAL\b|Traceback")
LOG_STAMP = re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})")


# ----------------------------------------------------------------- helpers

def log(msg):
    print(f"[upkeep] {msg}", flush=True)  # ends up in journalctl -u upkeep-*


def yes(v):
    return str(v).strip().lower() in ("1", "yes", "true", "on")


def now_iso():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def fmt_time(iso):
    try:
        d = dt.datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return str(iso)
    return d.strftime("%a %b %-d · %-I:%M %p")


def tail(text, n=40):
    return "\n".join((text or "").strip().splitlines()[-n:])


def last_line(text, width=90):
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    return lines[-1][:width] if lines else "No details given"


def load_conf():
    conf = dict(DEFAULTS)
    try:
        with open(CONF_PATH) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                conf[k.strip()] = v.strip().strip('"')
    except FileNotFoundError:
        pass
    return conf


def os_release():
    info = {}
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    info[k] = v.strip('"')
    except FileNotFoundError:
        pass
    return info


def detect_distro():
    info = os_release()
    ids = " ".join([info.get("ID", ""), info.get("ID_LIKE", ""), info.get("VARIANT_ID", ""),
                    info.get("NAME", "")]).lower()
    if "steamos" in ids:
        return "steamos"
    if "bazzite" in ids:
        return "bazzite"
    return None


class Ctx:
    def __init__(self, conf):
        self.conf = conf
        d = (conf.get("DISTRO") or "").lower() or detect_distro() or "bazzite"
        self.distro = d if d in DISTRO_NAMES else "bazzite"
        self.os_name = DISTRO_NAMES[self.distro]
        user = conf.get("USER") or os.environ.get("SUDO_USER") or ""
        if not user or user == "root":
            sys.exit("Set USER= in /etc/upkeep.conf (your normal login name).")
        pw = pwd.getpwnam(user)
        self.user, self.uid, self.gid, self.home = user, pw.pw_uid, pw.pw_gid, pw.pw_dir
        self.homebrew = os.path.join(self.home, "homebrew")
        self.plugins_dir = os.path.join(self.homebrew, "plugins")
        self.logs_dir = os.path.join(self.homebrew, "logs")
        self.loader_bin = os.path.join(self.homebrew, "services", "PluginLoader")
        self.loader_ver = os.path.join(self.homebrew, "services", ".loader.version")
        self.base = os.path.join(self.home, "upkeep")
        self.reports = os.path.join(self.base, "reports")
        self.backups = os.path.join(self.base, "backups")
        self.state_path = os.path.join(self.base, "state.json")
        self.latest_json = os.path.join(self.base, "latest.json")
        self.latest_txt = os.path.join(self.base, "latest.txt")


def clean_env():
    env = os.environ.copy()
    env.pop("LD_LIBRARY_PATH", None)
    return env


def sh(cmd, ctx_user=None, timeout=600):
    """Run a command. ctx_user=(name, home) runs it as that user."""
    env = clean_env()
    if ctx_user:
        name, home = ctx_user
        cmd = ["runuser", "-u", name, "--", "env", f"HOME={home}"] + cmd
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"Timed out after {timeout}s: {' '.join(cmd)}"
    except FileNotFoundError:
        return 127, "", f"Command not found: {cmd[0]}"


def sh_stream(cmd, on_line, ctx_user=None, timeout=3600):
    """Like sh(), but hands each line of output to on_line as it arrives.
    Returns (exit code, all output)."""
    env = clean_env()
    if ctx_user:
        name, home = ctx_user
        cmd = ["runuser", "-u", name, "--", "env", f"HOME={home}"] + cmd
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, errors="replace", env=env)
    except FileNotFoundError:
        return 127, f"Command not found: {cmd[0]}"
    timer = threading.Timer(timeout, p.kill)
    timer.start()
    lines = []
    try:
        for raw in p.stdout:
            line = raw.rstrip()
            if not line:
                continue
            lines.append(line)
            try:
                on_line(line)
            except Exception as e:  # a display problem must never stop an update
                log(f"progress: {e}")
        rc = p.wait()
    finally:
        timer.cancel()
    return rc, "\n".join(lines)


def http_get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "bazzite-upkeep/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def http_download(url, dest, on_pct=None, timeout=300):
    """Download to a file, calling on_pct(0-100) as it goes. Returns the sha256."""
    req = urllib.request.Request(url, headers={"User-Agent": "bazzite-upkeep/1.0"})
    digest = hashlib.sha256()
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as f:
        total = int(resp.headers.get("Content-Length") or 0)
        got = 0
        while True:
            chunk = resp.read(262144)
            if not chunk:
                break
            f.write(chunk)
            digest.update(chunk)
            got += len(chunk)
            if on_pct and total:
                on_pct(min(100, got * 100 // total))
    return digest.hexdigest()


def write_json(path, data, ctx=None):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)
    if ctx:
        os.chown(path, ctx.uid, ctx.gid)


def read_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


class Lock:
    def __enter__(self):
        self.f = open(LOCK_PATH, "w")
        fcntl.flock(self.f, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        fcntl.flock(self.f, fcntl.LOCK_UN)
        self.f.close()


# ----------------------------------------------------------------- live progress
# While `upkeep run` is going, ~/upkeep/progress.json lists what it is working
# on, so the Decky panel can show a percentage beside each thing being updated.

class Progress:
    FINISHED = ("done", "error", "skipped")

    def __init__(self, ctx, kind):
        self.ctx = ctx
        self.path = os.path.join(ctx.base, "progress.json")
        self.data = {"kind": kind, "running": True, "started": now_iso(),
                     "updated": now_iso(), "items": []}
        self.runtimes = {"total": 0, "done": 0}   # Flatpak runtimes share one row
        self._written = 0.0

    def _get(self, key):
        return next((i for i in self.data["items"] if i["key"] == key), None)

    def add(self, key, name, group, state="waiting", detail=None, before=()):
        """Add a row. `before` names rows it should sit above (first one found wins)."""
        if self._get(key) is None:
            items = self.data["items"]
            pos = len(items)
            for anchor in before:
                found = next((n for n, i in enumerate(items) if i["key"] == anchor), None)
                if found is not None:
                    pos = found
                    break
            items.insert(pos, {"key": key, "name": name, "group": group, "state": state,
                               "percent": None, "detail": detail})
        self.write(force=True)

    def set(self, key, **fields):
        item = self._get(key)
        if item is None:
            return
        changed_state = "state" in fields and fields["state"] != item["state"]
        item.update(fields)
        if item["state"] in self.FINISHED:
            item["percent"] = None
        self.write(force=changed_state)

    def remove(self, key):
        self.data["items"] = [i for i in self.data["items"] if i["key"] != key]
        self.write(force=True)

    def write(self, force=False):
        now = time.time()
        if not force and now - self._written < 0.4:
            return
        self._written = now
        self.data["updated"] = now_iso()
        try:
            write_json(self.path, self.data, self.ctx)
        except OSError as e:
            log(f"progress: {e}")

    def finish(self):
        self.data["running"] = False
        self.write(force=True)


PROG = None   # a Progress while `upkeep run` is going, otherwise None


def prog(key, **fields):
    if PROG:
        PROG.set(key, **fields)


class Selection:
    """What a run may update. No keys = everything switched on in upkeep.conf.
    Keys: system, decky, runtimes, plugin:<folder>, flatpak:<system|user>:<app id>."""

    def __init__(self, keys=None):
        self.all = not keys
        self.keys = set(keys or [])

    def system(self):
        return self.all or "system" in self.keys

    def decky(self):
        return self.all or "decky" in self.keys

    def runtimes(self):
        return self.all or "runtimes" in self.keys

    def plugin(self, folder):
        return self.all or f"plugin:{folder}" in self.keys

    def any_plugins(self):
        return self.all or any(k.startswith("plugin:") for k in self.keys)

    def flatpak_apps(self, scope):
        prefix = f"flatpak:{scope}:"
        return sorted(k[len(prefix):] for k in self.keys if k.startswith(prefix))

    def any_flatpaks(self):
        return self.all or "runtimes" in self.keys or any(k.startswith("flatpak:") for k in self.keys)


# ----------------------------------------------------------------- report model

def new_report():
    return {
        "generated": now_iso(),
        "health_checked": None,
        "issues": [],
        "system": [],
        "plugins": [],
        "flatpaks": [],
        "runtimes_updated": 0,
        "health": [],
    }


def row(name, old=None, new=None, status="unchanged", note=None, **extra):
    d = {"name": name, "old": old, "new": new, "status": status, "note": note}
    d.update(extra)
    return d


def add_issue(r, name, problem, reason=None, action=None, action_detail=None,
              log_text=None, hint=None, phase="update"):
    r["issues"].append({
        "name": name, "problem": problem, "reason": reason, "action": action,
        "action_detail": action_detail, "log": log_text or None, "hint": hint, "phase": phase,
    })


# ----------------------------------------------------------------- games / sleep / network

def game_running():
    rc, out, _ = sh(["pgrep", "-af", "SteamLaunch"])
    return rc == 0 and "AppId=" in out


def wait_for_idle(hours):
    deadline = time.time() + hours * 3600
    while game_running():
        if time.time() > deadline:
            return False
        log("A game is running - waiting 15 minutes so nothing hitches.")
        time.sleep(900)
    return True


def woke_recently():
    rc, out, _ = sh(["journalctl", "-k", "--since=-10min", "--no-pager", "-o", "cat",
                     "-g", "PM: suspend exit"])
    return rc == 0 and "suspend exit" in out


def wait_for_network(seconds=120):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with socket.create_connection(("flathub.org", 443), timeout=5):
                return True
        except OSError:
            time.sleep(5)
    log("No network after waiting; continuing anyway (updates will report errors).")
    return False


# ----------------------------------------------------------------- Bazzite system image

def ostree_versions():
    rc, out, _ = sh(["rpm-ostree", "status", "--json"])
    booted = staged = None
    try:
        for d in json.loads(out).get("deployments", []):
            if d.get("booted"):
                booted = d.get("version")
            if d.get("staged"):
                staged = d.get("version")
    except json.JSONDecodeError:
        pass
    return booted, staged


def update_system_bazzite(r):
    booted, _ = ostree_versions()
    log("Updating Bazzite system image...")
    prog("system", state="working", detail="Checking")
    seen = {"need": 0, "got": 0}

    def on_line(line):
        # rpm-ostree says how many image layers it needs, then prints one line
        # per layer fetched. No such lines = no percentage, just "working".
        m = re.search(r"layers needed:\s*(\d+)", line)
        if m:
            seen["need"] += int(m.group(1))
        elif line.startswith("Fetched "):
            seen["got"] += 1
        elif "Staging deployment" in line:
            prog("system", percent=95, detail="Finishing")
            return
        if seen["need"]:
            prog("system", percent=min(94, seen["got"] * 100 // seen["need"]), detail="Downloading")

    rc, out = sh_stream(["rpm-ostree", "upgrade", "--unchanged-exit-77"], on_line, timeout=3600)
    booted, staged = ostree_versions()
    if rc not in (0, 77):
        r["system"].append(row("Bazzite", booted, None, "error"))
        add_issue(r, "Bazzite", "System update failed", last_line(out),
                  log_text=tail(out),
                  hint="Nothing was changed. It will try again next run.")
        prog("system", state="error", detail="Update failed")
    elif staged and staged != booted:
        r["system"].append(row("Bazzite", booted, staged, "staged", note="Installs on next restart"))
        prog("system", state="done", detail="Installs on next restart")
    else:
        r["system"].append(row("Bazzite", booted))
        prog("system", state="done", detail="Up to date")


# ----------------------------------------------------------------- SteamOS system image
# SteamOS uses A/B partitions: steamos-update writes the new version to the
# other slot, and it becomes active on the next restart.
STEAMOS_NO_UPDATE = 7  # steamos-update exit code for "already up to date"


def steamos_version():
    info = os_release()
    v, b = info.get("VERSION_ID"), info.get("BUILD_ID")
    return f"{v} ({b})" if v and b else (v or b)


def steamos_offered_version(text):
    v = re.search(r'"?version"?\s*[:=]\s*"?(\d+(?:\.\d+)+)', text or "", re.I)
    b = re.search(r'"?build_?id"?\s*[:=]\s*"?(\d{8}(?:\.\d+)?)', text or "", re.I)
    if v and b:
        return f"{v.group(1)} ({b.group(1)})"
    return v.group(1) if v else (b.group(1) if b else None)


def steamos_check():
    """Returns (available: bool|None, offered_version, output). None = check failed."""
    rc, out, err = sh(["steamos-update", "check"], timeout=300)
    text = (out or "") + (err or "")
    if rc == STEAMOS_NO_UPDATE or "no update" in text.lower():
        return False, None, text
    if rc != 0:
        return None, None, text
    return True, steamos_offered_version(text), text


def update_system_steamos(r):
    cur = steamos_version()
    log("Checking for SteamOS updates...")
    prog("system", state="working", detail="Checking")
    avail, offered, text = steamos_check()
    if avail is None:
        r["system"].append(row("SteamOS", cur, None, "error"))
        add_issue(r, "SteamOS", "Couldn't check for system updates", last_line(text), log_text=tail(text),
                  hint="Nothing was changed. It will try again next run.")
        prog("system", state="error", detail="Couldn't check")
        return
    if not avail:
        r["system"].append(row("SteamOS", cur))
        prog("system", state="done", detail="Up to date")
        return
    log("Installing SteamOS update...")
    prog("system", detail="Downloading")

    def on_line(line):
        m = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", line)   # if steamos-update prints a percentage, show it
        if m and float(m.group(1)) <= 100:
            prog("system", percent=int(float(m.group(1))))

    rc, out = sh_stream(["steamos-update"], on_line, timeout=3600)
    if rc == 0:
        r["system"].append(row("SteamOS", cur, offered, "staged", note="Installs on next restart"))
        prog("system", state="done", detail="Installs on next restart")
    elif rc == STEAMOS_NO_UPDATE:
        r["system"].append(row("SteamOS", cur))
        prog("system", state="done", detail="Up to date")
    else:
        r["system"].append(row("SteamOS", cur, None, "error"))
        add_issue(r, "SteamOS", "System update failed", last_line(out), log_text=tail(out),
                  hint="Your current version is untouched. It will try again next run.")
        prog("system", state="error", detail="Update failed")


def check_system_steamos(r):
    cur = steamos_version()
    avail, offered, text = steamos_check()
    if avail is None:
        r["system"].append(row("SteamOS", cur, None, "error"))
        add_issue(r, "SteamOS", "Couldn't check for system updates", last_line(text), log_text=tail(text))
    elif avail:
        r["system"].append(row("SteamOS", cur, offered, "available", key="system"))
    else:
        r["system"].append(row("SteamOS", cur))


# ----------------------------------------------------------------- distro dispatch

def system_version(ctx):
    return steamos_version() if ctx.distro == "steamos" else ostree_versions()[0]


def update_system(ctx, r):
    (update_system_steamos if ctx.distro == "steamos" else update_system_bazzite)(r)


def check_system(ctx, r):
    (check_system_steamos if ctx.distro == "steamos" else check_system_bazzite)(r)



# ----------------------------------------------------------------- Flatpaks

def flatpak_list(scope, kind, as_user=None):
    cols = "application,name,version,active" if kind == "app" else "application,branch,active"
    rc, out, _ = sh(["flatpak", "list", f"--{scope}", f"--{kind}", f"--columns={cols}"], ctx_user=as_user)
    res = {}
    for line in out.splitlines():
        p = line.split("\t")
        if kind == "app" and len(p) >= 4:
            res[p[0]] = {"name": p[1] or p[0], "version": p[2], "commit": p[3]}
        elif kind == "runtime" and len(p) >= 3:
            res[f"{p[0]}//{p[1]}"] = {"commit": p[2]}
    return res


def flatpak_worker(scope, everything, runtimes, apps):
    """Does the actual Flatpak update for one installation, through Flatpak's own
    library so it can report a percentage per app. Runs as a child of `upkeep run`
    (as root for the system installation, as the user for theirs) and prints one
    JSON object per line: plan, op, pct, done, err, end."""
    def emit(**ev):
        print(json.dumps(ev), flush=True)

    try:
        import warnings
        warnings.simplefilter("ignore")   # the bindings grumble about a value this code never reads
        import gi
        gi.require_version("Flatpak", "1.0")
        from gi.repository import Flatpak, GLib
    except Exception as e:  # no Python bindings here: the caller falls back to the flatpak command
        emit(ev="nogi", msg=str(e))
        return 3

    def kind_of(ref):
        return "app" if ref.startswith("app/") else "runtime"

    try:
        inst = Flatpak.Installation.new_user(None) if scope == "user" else Flatpak.Installation.new_system(None)
        tx = Flatpak.Transaction.new_for_installation(inst, None)
        tx.set_no_interaction(True)
        tx.add_default_dependency_sources()   # user apps may rely on system-wide runtimes
        if everything:
            tx.set_include_unused_uninstall_ops(True)   # same tidy-up `flatpak update` does

        added = 0
        for ref in inst.list_installed_refs(None):
            is_app = ref.get_kind() == Flatpak.RefKind.APP
            if not (everything or (is_app and ref.get_name() in apps) or (runtimes and not is_app)):
                continue
            try:
                tx.add_update(ref.format_ref(), None, None)
                added += 1
            except GLib.Error as e:   # e.g. its remote was removed: skip it, keep going
                emit(ev="skip", ref=ref.format_ref(), msg=e.message)
        if not added:
            emit(ev="end", ok=True)
            return 0

        counted = set()

        def on_ready(t):
            ops = []
            for op in t.get_operations():
                if op.get_is_skipped() or op.get_operation_type() == Flatpak.TransactionOperationType.UNINSTALL:
                    continue
                counted.add(op.get_ref())
                ops.append({"ref": op.get_ref(), "kind": kind_of(op.get_ref()),
                            "id": op.get_ref().split("/")[1], "size": op.get_download_size()})
            emit(ev="plan", ops=ops)
            return True

        def on_new_operation(t, op, progress):
            ref = op.get_ref()
            if ref not in counted:
                return
            emit(ev="op", ref=ref)
            last = [-1]

            def changed(p):
                pct = int(p.get_progress())
                if pct != last[0]:
                    last[0] = pct
                    emit(ev="pct", ref=ref, pct=pct)

            progress.set_update_frequency(250)
            progress.connect("changed", changed)

        def on_done(t, op, commit, result):
            if op.get_ref() in counted:
                emit(ev="done", ref=op.get_ref())

        def on_error(t, op, error, details):
            emit(ev="err", ref=op.get_ref(), msg=error.message)
            return True   # carry on with the other apps

        def on_rebase(t, remote, ref, reason, rebased_to_ref, previous_ids):
            # The app moved to a new name. `flatpak update -y` follows the move, so do the same.
            try:
                t.add_rebase_and_uninstall(remote, rebased_to_ref, ref, None, previous_ids)
                return True
            except Exception as e:
                emit(ev="skip", ref=ref, msg=str(e))
                return False

        tx.connect("ready", on_ready)
        tx.connect("new-operation", on_new_operation)
        tx.connect("operation-done", on_done)
        tx.connect("operation-error", on_error)
        tx.connect("end-of-lifed-with-rebase", on_rebase)
        tx.run(None)
        emit(ev="end", ok=True)
        return 0
    except Exception as e:
        emit(ev="end", ok=False, msg=getattr(e, "message", None) or str(e))
        return 1


def flatpak_cli_update(scope, as_user, apps, runtimes, everything):
    """Plain `flatpak update`, for systems without the Python Flatpak bindings.
    Works the same, just without live percentages."""
    base = ["flatpak", "update", f"--{scope}", "-y", "--noninteractive"]
    cmds = [base] if everything else ([base + list(apps)] if apps else []) + ([base + ["--runtime"]] if runtimes else [])
    ok, text = True, []
    for cmd in cmds:
        rc, out, err = sh(cmd, ctx_user=as_user, timeout=3600)
        if rc != 0:
            ok = False
            text.append(err or out)
    return ok, "\n".join(text)


def flatpak_update_scope(scope, as_user, apps, runtimes, everything, names):
    """Update one Flatpak installation, feeding the live progress as it goes.
    Returns (ok, error text, how many things it set out to update)."""
    cmd = [sys.executable or "python3", os.path.abspath(__file__), "_flatpak-worker", "--scope", scope]
    if everything:
        cmd.append("--all")
    elif runtimes:
        cmd.append("--runtimes")
    for app in apps or []:
        cmd += ["--app", app]
    seen = {"nogi": False, "end": None, "errors": [], "count": 0, "runtimes": set()}
    anchors = ("flatpaks", "decky", "plugins", "health")

    def runtime_row(current=0, started=True):
        t = PROG.runtimes
        if t["done"] >= t["total"]:
            PROG.set("runtimes", state="done", detail=f"{t['total']} updated")
        elif started:
            pct = int((t["done"] + current / 100) * 100 / t["total"])
            PROG.set("runtimes", state="working", percent=min(99, pct),
                     detail=f"{t['done'] + 1} of {t['total']}")
        else:
            PROG.set("runtimes", state="waiting", detail=f"{t['total']} to update")

    def on_line(line):
        if not line.startswith("{"):
            return
        try:
            ev = json.loads(line)
        except ValueError:
            return
        kind, ref = ev.get("ev"), ev.get("ref") or ""
        if kind == "nogi":
            seen["nogi"] = True
        elif kind == "end":
            seen["end"] = ev
        elif kind == "plan":
            for op in ev.get("ops", []):
                seen["count"] += 1
                if op["kind"] != "app":
                    seen["runtimes"].add(op["ref"])
                    if PROG:
                        PROG.runtimes["total"] += 1
                elif PROG:
                    PROG.add(f"flatpak:{scope}:{op['id']}", (names.get(op["id"]) or {}).get("name") or op["id"],
                             "flatpaks", before=anchors)
            if PROG and seen["runtimes"]:
                PROG.add("runtimes", "System runtimes", "flatpaks", before=anchors)
                runtime_row(started=PROG.runtimes["done"] > 0)
            if PROG and seen["count"]:
                PROG.remove("flatpaks")
        elif kind in ("op", "pct", "done", "err"):
            if kind == "err":
                seen["errors"].append(f"{ref.split('/')[1] if '/' in ref else ref}: {ev.get('msg')}")
            if not PROG:
                return
            if ref in seen["runtimes"]:
                if kind in ("done", "err"):
                    PROG.runtimes["done"] += 1
                runtime_row(ev.get("pct", 0) if kind == "pct" else 0)
                return
            key = f"flatpak:{scope}:{ref.split('/')[1]}" if "/" in ref else ref
            if kind == "op":
                PROG.set(key, state="working", percent=0)
            elif kind == "pct":
                PROG.set(key, state="working", percent=ev.get("pct", 0))
            elif kind == "done":
                PROG.set(key, state="done")
            else:
                PROG.set(key, state="error", detail="Update failed")

    rc, out = sh_stream(cmd, on_line, ctx_user=as_user, timeout=3600)
    if seen["nogi"]:
        log("Python Flatpak bindings not found - updating without live percentages.")
        prog("flatpaks", detail="Updating")
        ok, text = flatpak_cli_update(scope, as_user, apps, runtimes, everything)
        return ok, text, 0
    if seen["errors"]:
        return False, "\n".join(seen["errors"]), seen["count"]
    end = seen["end"]
    if end is None or not end.get("ok"):
        plain = "\n".join(l for l in out.splitlines() if not l.startswith("{"))
        return False, (end or {}).get("msg") or plain or f"Flatpak update stopped (exit {rc})", seen["count"]
    return True, "", seen["count"]


def update_flatpaks(ctx, r, sel):
    scopes = [("system", None), ("user", (ctx.user, ctx.home))]
    prog("flatpaks", state="working", detail="Checking")
    for scope, as_user in scopes:
        apps = [] if sel.all else sel.flatpak_apps(scope)
        if not sel.all and not apps and not sel.runtimes():
            continue
        apps_before = flatpak_list(scope, "app", as_user)
        rts_before = flatpak_list(scope, "runtime", as_user)
        log(f"Updating {scope} Flatpaks...")
        ok, detail, _ = flatpak_update_scope(scope, as_user, apps, sel.runtimes(), sel.all, apps_before)
        if not ok:
            add_issue(r, "Flatpaks", f"Some {scope} Flatpaks didn't update",
                      last_line(detail), log_text=tail(detail))
        apps_after = flatpak_list(scope, "app", as_user)
        rts_after = flatpak_list(scope, "runtime", as_user)

        for app_id, a in sorted(apps_after.items(), key=lambda kv: kv[1]["name"].lower()):
            b = apps_before.get(app_id)
            if not b or b["commit"] == a["commit"]:
                continue
            if b["version"] and a["version"] and b["version"] != a["version"]:
                r["flatpaks"].append(row(a["name"], b["version"], a["version"], "updated"))
            else:  # app didn't publish a version number
                r["flatpaks"].append(row(a["name"], None, None, "updated"))
        r["runtimes_updated"] += sum(
            1 for k, v in rts_after.items() if k in rts_before and rts_before[k]["commit"] != v["commit"])
    prog("flatpaks", state="done", detail="Up to date")   # only still listed if nothing needed updating



def check_system_bazzite(r):
    booted, staged = ostree_versions()
    rc, out, err = sh(["rpm-ostree", "upgrade", "--check"], timeout=600)
    avail = None
    try:
        avail = (json.loads(sh(["rpm-ostree", "status", "--json"])[1]).get("cached-update") or {}).get("version")
    except json.JSONDecodeError:
        pass
    if not avail:
        m = re.search(r"Version:\s*(\S+)", out)
        avail = m.group(1) if m else None
    if staged and staged != booted:
        r["system"].append(row("Bazzite", booted, staged, "staged", note="Already downloaded, installs on next restart"))
    elif avail and avail != booted:
        r["system"].append(row("Bazzite", booted, avail, "available", key="system"))
    elif rc not in (0, 77) and "error" in (out + err).lower():
        r["system"].append(row("Bazzite", booted, None, "error"))
        add_issue(r, "Bazzite", "Couldn't check for system updates", last_line(err or out), log_text=tail(err or out))
    else:
        r["system"].append(row("Bazzite", booted))


def check_flatpaks(ctx, r):
    for scope, as_user in (("system", None), ("user", (ctx.user, ctx.home))):
        installed = flatpak_list(scope, "app", as_user)
        rc, out, err = sh(["flatpak", "remote-ls", "--updates", f"--{scope}", "--app",
                           "--columns=application,name,version"], ctx_user=as_user, timeout=300)
        if rc != 0:
            add_issue(r, "Flatpaks", f"Couldn't check {scope} Flatpaks", last_line(err or out))
            continue
        for line in out.splitlines():
            p = line.split("\t")
            if not p or not p[0]:
                continue
            name = (p[1] if len(p) > 1 and p[1] else None) or installed.get(p[0], {}).get("name") or p[0]
            new = p[2] if len(p) > 2 and p[2] else None
            old = installed.get(p[0], {}).get("version") or None
            r["flatpaks"].append(row(name, old, new if new != old else None, "available",
                                     key=f"flatpak:{scope}:{p[0]}"))
        rc, out, _ = sh(["flatpak", "remote-ls", "--updates", f"--{scope}", "--runtime",
                         "--columns=application"], ctx_user=as_user, timeout=300)
        if rc == 0:
            r["runtimes_updated"] += sum(1 for l in out.splitlines() if l.strip())
    r["flatpaks"].sort(key=lambda x: x["name"].lower())


# ----------------------------------------------------------------- Decky Loader

def decky_version(ctx):
    try:
        with open(ctx.loader_ver) as f:
            return f.read().strip() or None
    except FileNotFoundError:
        return None


def vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3])


def is_newer(latest, cur):
    a, b = vtuple(latest), vtuple(cur)
    if a != b:
        return a > b
    return "pre" in (cur or "").lower() and "pre" not in (latest or "").lower()


def latest_decky_release():
    rel = json.loads(http_get(DECKY_RELEASE_API))
    for a in rel.get("assets", []):
        if a.get("name") == "PluginLoader":
            return rel["tag_name"], a["browser_download_url"]
    raise RuntimeError("Latest Decky release has no PluginLoader file")


def put_binary(ctx, src_path, version):
    """Swap in a Decky binary, keeping the old file's SELinux label."""
    tmp = ctx.loader_bin + ".new"
    shutil.copyfile(src_path, tmp)
    os.chmod(tmp, 0o755)
    if os.path.exists(ctx.loader_bin):
        sh(["chcon", "--reference", ctx.loader_bin, tmp])
    os.replace(tmp, ctx.loader_bin)
    with open(ctx.loader_ver, "w") as f:
        f.write(version)


def download_decky(url, on_pct=None):
    fd, path = tempfile.mkstemp(prefix="upkeep-decky-")
    os.close(fd)
    try:
        http_download(url, path, on_pct)
    except Exception:
        os.remove(path)
        raise
    return path


def save_decky_backup(ctx, backup_root, version):
    """Copy the installed Decky into a backup folder, with its version beside it
    (rollback-decky needs to know which version each saved copy is)."""
    bdir = os.path.join(backup_root, "decky")
    os.makedirs(bdir, exist_ok=True)
    dest = os.path.join(bdir, "PluginLoader")
    shutil.copy2(ctx.loader_bin, dest)
    with open(os.path.join(bdir, "version"), "w") as f:
        f.write(version or "")
    return dest


def service_active(name):
    _, out, _ = sh(["systemctl", "is-active", name])
    return out.strip() == "active"


def decky_healthy(timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if service_active(DECKY_SERVICE):
            try:
                with socket.create_connection(("127.0.0.1", DECKY_PORT), timeout=3):
                    return True
            except OSError:
                pass
        time.sleep(3)
    return False


def restart_decky():
    log("Restarting Decky...")
    sh(["systemctl", "restart", DECKY_SERVICE])


def decky_journal():
    _, inv, _ = sh(["systemctl", "show", "-p", "InvocationID", "--value", DECKY_SERVICE])
    inv = inv.strip()
    if not inv:
        return []
    _, out, _ = sh(["journalctl", f"_SYSTEMD_INVOCATION_ID={inv}", "--no-pager", "-o", "cat"])
    return out.splitlines()


def decky_started_ts():
    _, out, _ = sh(["systemctl", "show", "-p", "ActiveEnterTimestamp", "--value", DECKY_SERVICE])
    if out.strip():
        _, o, _ = sh(["date", "-d", out.strip(), "+%s"])
        try:
            return float(o.strip())
        except ValueError:
            pass
    return time.time() - 600


def update_decky(ctx, r, backup_root, do_update, state=None, forced=False):
    """state: upkeep's saved state (holds the version a rollback-decky is steering
    clear of). forced: the user picked Decky by name, so a rollback hold is lifted."""
    state = state if state is not None else {}
    prog("decky", state="working", detail="Checking")
    cur = decky_version(ctx)
    if cur is None:
        r["system"].append(row("Decky", None, None, "error"))
        add_issue(r, "Decky", "Couldn't find Decky", "No version file in ~/homebrew/services",
                  hint="Is Decky installed? Reinstall it, then this check will pick it up.")
        prog("decky", state="error", detail="Not found")
        return False
    try:
        tag, url = latest_decky_release()
    except Exception as e:
        log(f"Couldn't check Decky releases: {e}")
        r["system"].append(row("Decky", cur, note="Couldn't check for updates"))
        prog("decky", state="error", detail="Couldn't check")
        return False
    if not is_newer(tag, cur):
        r["system"].append(row("Decky", cur))
        prog("decky", state="done", detail="Up to date")
        return False
    skip = state.get("decky_skip")
    if skip and not is_newer(tag, skip) and not forced:
        # Still the release the user rolled back from: wait for a newer one.
        r["system"].append(row("Decky", cur, tag, "available", key="decky", held=True,
                               note="On hold since you rolled back. Updates again with the next release."))
        prog("decky", state="skipped", detail="On hold after rollback")
        return False
    if not do_update:
        r["system"].append(row("Decky", cur, tag, "available", key="decky"))
        prog("decky", state="skipped")
        return False

    backup = save_decky_backup(ctx, backup_root, cur)
    log(f"Updating Decky {cur} -> {tag}...")
    reason = None
    try:
        path = download_decky(url, lambda p: prog("decky", percent=min(90, p), detail="Downloading"))
        put_binary(ctx, path, tag)
        os.remove(path)
        prog("decky", percent=95, detail="Restarting")
        restart_decky()
        if decky_healthy():
            r["system"].append(row("Decky", cur, tag, "updated"))
            state.pop("decky_skip", None)
            prog("decky", state="done")
            return True
        reason = "Didn't start after updating"
    except Exception as e:
        reason = str(e)[:90]

    log("Decky update failed - restoring previous version.")
    put_binary(ctx, backup, cur)
    restart_decky()
    decky_healthy()
    r["system"].append(row("Decky", cur, tag, "rolled_back"))
    add_issue(r, "Decky", f"Update to {tag} failed", reason, "Restored previous version",
              f"({tag} → {cur})", log_text=tail("\n".join(decky_journal())))
    prog("decky", state="error", detail="Update failed, old version restored")
    return True


def reinstall_decky(ctx):
    try:
        tag, url = latest_decky_release()
        path = download_decky(url)
        put_binary(ctx, path, tag)
        os.remove(path)
        return tag
    except Exception as e:
        log(f"Decky reinstall failed: {e}")
        return None


# ----------------------------------------------------------------- Decky rollback
# For when a Decky update itself is the problem: go back one version, using the
# copy saved before the update, or Decky's previous release if there is no copy.

def decky_backups(ctx):
    """Saved Decky copies that have a known version, newest first."""
    found = []
    if os.path.isdir(ctx.backups):
        for stamp in sorted(os.listdir(ctx.backups), reverse=True):
            binary = os.path.join(ctx.backups, stamp, "decky", "PluginLoader")
            try:
                with open(os.path.join(ctx.backups, stamp, "decky", "version")) as f:
                    version = f.read().strip()
            except OSError:
                continue
            if version and os.path.isfile(binary):
                found.append({"version": version, "path": binary, "stamp": stamp})
    return found


def previous_decky_release(cur):
    """The newest full Decky release older than `cur`: (tag, download url) or None."""
    best = None
    for rel in json.loads(http_get(DECKY_RELEASES_API)):
        tag = rel.get("tag_name") or ""
        if rel.get("draft") or rel.get("prerelease") or not is_newer(cur, tag):
            continue
        url = next((a["browser_download_url"] for a in rel.get("assets", [])
                    if a.get("name") == "PluginLoader"), None)
        if url and (best is None or is_newer(tag, best[0])):
            best = (tag, url)
    return best


def rollback_target(ctx):
    """Where rollback-decky would go: {"version", "source": "backup"|"download", ...} or None."""
    cur = decky_version(ctx)
    if not cur:
        return None
    for b in decky_backups(ctx):
        if is_newer(cur, b["version"]):
            saved = None
            try:
                saved = dt.datetime.strptime(b["stamp"], "%Y-%m-%d_%H%M").astimezone().isoformat(timespec="seconds")
            except ValueError:
                pass
            return {"version": b["version"], "source": "backup", "path": b["path"], "saved": saved}
    try:
        prev = previous_decky_release(cur)
    except Exception as e:
        log(f"Couldn't look up Decky's earlier releases: {e}")
        prev = None
    if prev:
        return {"version": prev[0], "source": "download", "url": prev[1]}
    return None


# ----------------------------------------------------------------- Decky plugins

def installed_plugins(ctx):
    res = []
    if not os.path.isdir(ctx.plugins_dir):
        return res
    for d in sorted(os.listdir(ctx.plugins_dir)):
        p = os.path.join(ctx.plugins_dir, d)
        meta = read_json(os.path.join(p, "plugin.json"))
        if not isinstance(meta, dict):
            continue
        pkg = read_json(os.path.join(p, "package.json"), {}) or {}
        res.append({"dir": d, "name": meta.get("name", d), "version": pkg.get("version"), "path": p})
    return res


def fetch_remote_binaries(plugin_dir, on_pct=None):
    """Download the files a plugin lists under "remote_binary" in package.json
    into its bin/ folder, like Decky's own installer does. They aren't in the
    store zip (Game Theme Music's yt-dlp is one), so skipping this step leaves
    the plugin installed but not working."""
    pkg = read_json(os.path.join(plugin_dir, "package.json"), {}) or {}
    bins = (pkg.get("remote_binary") if isinstance(pkg, dict) else None) or []
    for n, b in enumerate(bins):
        name, url, want = str(b["name"]), str(b["url"]), str(b["sha256hash"]).lower()
        if not name or name in (".", "..") or os.path.basename(name) != name:
            raise RuntimeError("Plugin lists an extra file with an unsafe name")
        if not url.startswith("https://"):
            raise RuntimeError(f"Plugin's extra file {name} isn't an https download")
        log(f"  downloading {name}...")
        bindir = os.path.join(plugin_dir, "bin")
        os.makedirs(bindir, exist_ok=True)
        step = (lambda p, n=n: on_pct((n * 100 + p) // len(bins))) if on_pct else None
        if http_download(url, os.path.join(bindir, name), step, timeout=600) != want:
            raise RuntimeError(f"Extra file {name} didn't match the plugin's checksum")


def plugin_layout(path):
    """Who owns an installed plugin's files, and its SELinux label. Decky keeps
    the folder and plugin.json owned by root and the rest owned by the user
    (all root for plugins that run as root)."""
    def owner(p, fallback):
        try:
            st = os.stat(p)
            return st.st_uid, st.st_gid
        except OSError:
            return fallback
    top = owner(path, (0, 0))
    try:
        label = os.getxattr(path, "security.selinux").rstrip(b"\0").decode()
    except (OSError, AttributeError, UnicodeDecodeError):
        label = None
    return {"top": top,
            "manifest": owner(os.path.join(path, "plugin.json"), top),
            "files": owner(os.path.join(path, "package.json"), top),
            "label": label}


def apply_plugin_layout(path, layout):
    """Give freshly unpacked plugin files the owners, modes and SELinux label
    Decky's installer would have. Unpacked as-is they'd be root-owned, not
    executable, and carry the temp folder's label."""
    steps = [["chown", "-R", "%d:%d" % layout["files"], path],
             ["chown", "%d:%d" % layout["top"], path],
             ["chmod", "-R", "755", path]]
    if os.path.exists(os.path.join(path, "plugin.json")):
        steps.append(["chown", "%d:%d" % layout["manifest"], os.path.join(path, "plugin.json")])
    if layout["label"]:
        steps.append(["chcon", "-R", layout["label"], path])
    for cmd in steps:
        rc, _, err = sh(cmd)
        if rc != 0:
            raise RuntimeError(err.strip() or f"{cmd[0]} failed")


def install_plugin(pl, version, backup_root, on_pct=None):
    """on_pct(0-100): the download is the first half, any extra files the plugin
    needs take it to 90, and swapping the folders finishes it."""
    step = on_pct or (lambda p: None)
    tmpd = tempfile.mkdtemp(prefix="upkeep-plugin-")
    try:
        zpath = os.path.join(tmpd, "plugin.zip")
        got = http_download(STORE_CDN.format(hash=version["hash"]), zpath, lambda p: step(p // 2))
        if got != version["hash"]:
            raise RuntimeError("Download didn't match the store's checksum")
        xdir = os.path.join(tmpd, "x")
        with zipfile.ZipFile(zpath) as z:
            for n in z.namelist():
                if n.startswith("/") or ".." in n.split("/"):
                    raise RuntimeError("Plugin zip has unsafe paths")
            z.extractall(xdir)
        entries = os.listdir(xdir)
        src = os.path.join(xdir, entries[0]) if len(entries) == 1 and os.path.isdir(
            os.path.join(xdir, entries[0])) else xdir
        # Still in the temp folder: if a download fails, the installed plugin is untouched.
        fetch_remote_binaries(src, lambda p: step(50 + p * 2 // 5))
        step(92)

        layout = plugin_layout(pl["path"])
        bdir = os.path.join(backup_root, "plugins", pl["dir"])
        os.makedirs(os.path.dirname(bdir), exist_ok=True)
        sh(["cp", "-a", pl["path"], bdir])            # keep a backup copy
        shutil.rmtree(pl["path"])
        try:
            shutil.copytree(src, pl["path"], symlinks=True)
            apply_plugin_layout(pl["path"], layout)
        except Exception:
            shutil.rmtree(pl["path"], ignore_errors=True)
            sh(["cp", "-a", bdir, pl["path"]])        # put the old one back
            raise
        return bdir
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)


def restore_plugin(ctx, d, backup):
    path = os.path.join(ctx.plugins_dir, d)
    shutil.rmtree(path, ignore_errors=True)
    rc, _, err = sh(["cp", "-a", backup, path])
    if rc != 0:
        raise RuntimeError(err.strip() or "copy failed")


def update_plugins(ctx, r, backup_root, do_update, sel=None):
    """sel: a Selection naming the plugins to update (None = every one that has an update)."""
    prog("plugins", state="working", detail="Checking")
    plugins = installed_plugins(ctx)
    try:
        store = json.loads(http_get(STORE_URL))
    except Exception as e:
        log(f"Couldn't reach the Decky plugin store: {e}")
        store = []
        add_issue(r, "Plugin store", "Couldn't check for plugin updates", str(e)[:90],
                  hint="Plugins weren't changed. It will try again tomorrow.")
    by_name = {p.get("name"): p for p in store if isinstance(p, dict)}
    held = {x.strip().lower() for x in ctx.conf.get("HOLD_PLUGINS", "").split(",") if x.strip()}

    todo = []
    for pl in plugins:
        s = by_name.get(pl["name"])
        versions = list((s or {}).get("versions") or [])
        if versions and all("created" in v for v in versions):
            versions.sort(key=lambda v: v["created"], reverse=True)
        names = [v.get("name") for v in versions]
        # Only update if we're on an older store version (never "downgrade" dev builds)
        if not versions or pl["version"] == names[0] or pl["version"] not in names[1:]:
            r["plugins"].append(row(pl["name"], pl["version"], dir=pl["dir"]))
            continue
        latest = versions[0]
        key = f"plugin:{pl['dir']}"
        if pl["name"].lower() in held or pl["dir"].lower() in held:
            # Hand-patched plugins: an update would replace the patch, so only report it.
            r["plugins"].append(row(pl["name"], pl["version"], latest["name"], "available",
                                    note="On hold in upkeep.conf, not installed", dir=pl["dir"],
                                    key=key, held=True, locked=True))
            continue
        if not do_update or (sel is not None and not sel.plugin(pl["dir"])):
            r["plugins"].append(row(pl["name"], pl["version"], latest["name"], "available",
                                    dir=pl["dir"], key=key))
            continue
        todo.append((pl, latest, key))

    if PROG:
        for pl, _, key in todo:
            PROG.add(key, pl["name"], "plugins", before=("plugins", "health"))
        if todo:
            PROG.remove("plugins")
        else:
            prog("plugins", state="done", detail="Up to date" if store else "Couldn't check")

    pending = {}
    for pl, latest, key in todo:
        log(f"Updating plugin {pl['name']} {pl['version']} -> {latest['name']}...")
        prog(key, state="working", percent=0)
        try:
            bdir = install_plugin(pl, latest, backup_root, lambda p, key=key: prog(key, percent=p))
            r["plugins"].append(row(pl["name"], pl["version"], latest["name"], "updated", dir=pl["dir"]))
            pending[pl["dir"]] = {"backup": bdir, "old": pl["version"], "new": latest["name"]}
            prog(key, state="done")
        except Exception as e:
            r["plugins"].append(row(pl["name"], pl["version"], None, "error", dir=pl["dir"]))
            add_issue(r, pl["name"], f"Update to {latest['name']} failed", str(e)[:90],
                      hint="The plugin was left on its current version.")
            prog(key, state="error", detail="Update failed")
    return pending


def classify(lines):
    text = "\n".join(lines)
    if "timed out" in text.lower():
        kind = "Hung while loading (timed out)"
    elif "Traceback" in text or re.search(r"\w+Error:", text):
        kind = "Python error in backend"
    else:
        kind = "Error while loading"
    detail = None
    for l in reversed(lines):
        m = re.search(r"(\w+(?:Error|Exception)\b.*)", l)
        if m:
            detail = m.group(1).strip()[:90]
            break
    return kind, detail or last_line(text)


def plugin_log_errors(ctx, pl, since):
    for cand in dict.fromkeys((pl["dir"], pl["name"])):
        d = os.path.join(ctx.logs_dir, cand)
        if not os.path.isdir(d):
            continue
        files = [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".log")]
        files = [f for f in files if os.path.getmtime(f) >= since - 5]
        if not files:
            continue
        newest = max(files, key=os.path.getmtime)
        with open(newest, errors="replace") as f:
            lines = f.read().splitlines()
        # Some plugins keep one log file forever, so skip lines written before
        # Decky last started. Lines with no timestamp follow the line above them.
        current = True
        for i, l in enumerate(lines):
            m = LOG_STAMP.search(l[:60])
            if m:
                try:
                    stamp = dt.datetime.strptime(" ".join(m.groups()), "%Y-%m-%d %H:%M:%S")
                    current = stamp.timestamp() >= since - 5
                except ValueError:
                    pass
            if current and PLUGIN_LOG_ERR.search(l):
                return lines[max(0, i - 2):i + 15]
    return None


def check_plugins(ctx):
    """Returns ({dir: {reason, detail, log}}, total) for plugins that look broken."""
    journal = decky_journal()
    since = decky_started_ts()
    broken = {}
    plugins = installed_plugins(ctx)
    for pl in plugins:
        if not os.path.isfile(os.path.join(pl["path"], "dist", "index.js")):
            broken[pl["dir"]] = {"reason": "Missing files after update",
                                 "detail": "dist/index.js not found", "log": None}
            continue
        keys = {pl["name"].lower(), pl["dir"].lower()}
        hits = None
        for i, l in enumerate(journal):
            if JOURNAL_ERR.search(l) and any(k in l.lower() for k in keys):
                hits = journal[max(0, i - 2):i + 15]
                break
        if hits is None:
            hits = plugin_log_errors(ctx, pl, since)
        if hits:
            kind, detail = classify(hits)
            broken[pl["dir"]] = {"reason": kind, "detail": detail, "log": "\n".join(hits)}
    return broken, len(plugins)


# ----------------------------------------------------------------- health check

def add_disk(ctx, r):
    free = shutil.disk_usage(ctx.home).free / 1e9
    r["health"].append({"ok": free >= 20, "text": f"Disk space: {free:.0f} GB free"})


def plugin_row(r, d, name, version):
    for p in r["plugins"]:
        if p.get("dir") == d:
            return p
    p = row(name, version, dir=d, health_only=True)
    r["plugins"].append(p)
    return p


def health_check(ctx, r, pending):
    """Checks Decky + plugins, fixes what it safely can. Mutates `pending`."""
    r["health_checked"] = now_iso()
    healthy, fixed = decky_healthy(), None
    if not healthy:
        restart_decky()
        healthy, fixed = decky_healthy(), "restarted"
    if not healthy:
        tag = reinstall_decky(ctx)
        if tag:
            restart_decky()
            healthy, fixed = decky_healthy(), "reinstalled"
    if not healthy:
        add_issue(r, "Decky", "Decky isn't running", "Didn't come back after a restart and reinstall",
                  log_text=tail("\n".join(decky_journal())), phase="health",
                  hint="Usually caused by a Steam update. Decky may need a fix release.")
        r["health"].append({"ok": False, "text": "Decky not running"})
        add_disk(ctx, r)
        return
    r["health"].append({"ok": True, "text": "Decky running" + (f" (auto-{fixed})" if fixed else "")})

    time.sleep(20)  # give plugins a moment to finish loading
    broken, total = check_plugins(ctx)

    rolled = {}
    for d, info in broken.items():
        if d in pending:
            try:
                log(f"Plugin {d} broke after its update - restoring previous version.")
                restore_plugin(ctx, d, pending[d]["backup"])
                rolled[d] = dict(pending.pop(d), info=info)
            except Exception as e:
                log(f"Restore of {d} failed: {e}")
    if rolled:
        restart_decky()
        decky_healthy()
        time.sleep(20)
        broken, total = check_plugins(ctx)

    names = {pl["dir"]: pl for pl in installed_plugins(ctx)}
    for d, p in rolled.items():
        pl = names.get(d, {"name": d, "version": p["old"]})
        rw = plugin_row(r, d, pl["name"], p["old"])
        rw.update(status="rolled_back", old=p["old"], new=p["new"])
        still = d in broken
        add_issue(r, pl["name"], "Failed to load after update", p["info"]["reason"],
                  "Restored previous version", f"({p['new']} → {p['old']})",
                  log_text=p["info"]["log"],
                  hint="Still has errors on the old version too." if still else None)
        broken.pop(d, None)

    for d, info in broken.items():
        pl = names.get(d, {"name": d, "version": None})
        rw = plugin_row(r, d, pl["name"], pl.get("version"))
        if rw["status"] != "error":
            rw["prev_status"] = rw["status"]
            rw["status"] = "error"
        add_issue(r, pl["name"], "Failed to load", f"{info['reason']}: {info['detail']}",
                  log_text=info["log"], phase="health",
                  hint="Wasn't updated tonight, so this is likely a Steam or Decky change.")

    bad = len(broken)
    r["health"].append({"ok": bad == 0, "text": f"{total - bad} of {total} plugins loaded cleanly"})
    add_disk(ctx, r)


# ----------------------------------------------------------------- rendering

ICON = {"updated": "✅", "unchanged": "✅", "staged": "⏳", "error": "⚠️",
        "rolled_back": "↩️", "available": "⬆️"}
WIDTH = 31


def bar(title):
    t = f"── {title} "
    return t + "─" * max(3, WIDTH - len(t))


def change_text(x):
    s, o, n = x["status"], x.get("old"), x.get("new")
    if s == "unchanged":
        return "no change"
    if s == "rolled_back":
        return f"kept on {o}"
    if s == "available":
        if o and n:
            return f"{o} → {n}"
        return f"update available: {n}" if n else "update available"
    if s == "error":
        return o or "see issues"
    if s == "staged" and not n:
        return f"{o} → update downloaded" if o else "update downloaded"
    if o and n:
        return f"{o} → {n}"
    return "updated"


def rows_block(rows):
    if not rows:
        return []
    w = min(16, max(len(x["name"]) for x in rows))
    out = []
    for x in rows:
        out.append(f"{ICON.get(x['status'], '•')} {x['name']:<{w}}  {change_text(x)}")
        if x.get("note"):
            out.append(f"   {x['note']}")
    return out


def render_text(r):
    n = len(r["issues"])
    good = "✅ Selected updates installed and working" if r.get("partial") else "✅ Everything updated and working"
    L = [f"UPKEEP REPORT · {fmt_time(r['generated'])}",
         good if n == 0 else f"⚠️ {n} issue{'s need' if n > 1 else ' needs'} a look"]

    if r["issues"]:
        L += ["", bar("ISSUES")]
        for i in r["issues"]:
            L += [f"⚠️ {i['name']}", f"   {i['problem']}"]
            if i.get("reason"):
                L.append(f"   Reason: {i['reason']}")
            if i.get("action"):
                L.append(f"   ↩️ {i['action']}")
                if i.get("action_detail"):
                    L.append(f"      {i['action_detail']}")
            if i.get("hint"):
                L.append(f"   {i['hint']}")

    L += ["", bar("SYSTEM")] + rows_block(r["system"])

    total = len(r["plugins"])
    changed = [p for p in r["plugins"] if p["status"] != "unchanged"]
    same = total - len(changed)
    L += ["", bar("DECKY PLUGINS")] + rows_block(changed)
    if same:
        L.append(f"   {'All ' if not changed and same > 1 else ''}{same} plugin{'s' if same != 1 else ''} already up to date")
    elif not total:
        L.append("   No plugins installed")

    L += ["", bar("FLATPAKS")] + rows_block(r["flatpaks"])
    if not r["flatpaks"]:
        L.append("   No app updates")
    ru = r.get("runtimes_updated", 0)
    if ru:
        L.append(f"   + {ru} system runtime{'s' if ru != 1 else ''} updated")

    if r["health"]:
        L += ["", bar("HEALTH CHECK")]
        L += [f"{'✅' if h['ok'] else '⚠️'} {h['text']}" for h in r["health"]]
        if r.get("health_checked"):
            L.append(f"   Checked {fmt_time(r['health_checked'])}")
    return "\n".join(L) + "\n"


def write_report(ctx, r):
    os.makedirs(ctx.reports, exist_ok=True)
    for p in (ctx.base, ctx.reports):
        os.chown(p, ctx.uid, ctx.gid)
    txt = render_text(r)
    write_json(ctx.latest_json, r, ctx)
    stamp = dt.datetime.fromisoformat(r["generated"]).strftime("%Y-%m-%d_%H%M")
    for path in (ctx.latest_txt, os.path.join(ctx.reports, f"{stamp}.txt")):
        with open(path, "w") as f:
            f.write(txt)
        os.chown(path, ctx.uid, ctx.gid)
    print(txt, flush=True)


def render_check(r):
    groups = [("SYSTEM", r["system"]), ("DECKY PLUGINS", r["plugins"]), ("FLATPAKS", r["flatpaks"])]
    count = sum(1 for _, rows in groups for x in rows if x["status"] in ("available", "staged"))
    count += 1 if r.get("runtimes_updated") else 0
    L = [f"UPDATE CHECK · {fmt_time(r['generated'])}",
         "✅ Everything is up to date" if count == 0
         else f"⬆️ {count} update{'s' if count != 1 else ''} available"]
    for i in r["issues"]:
        L += ["", f"⚠️ {i['name']}: {i['problem']}"]
        if i.get("reason"):
            L.append(f"   Reason: {i['reason']}")
    for title, rows in groups:
        avail = [x for x in rows if x["status"] in ("available", "staged")]
        L += ["", bar(title)] + (rows_block(avail) or ["   Up to date"])
        if title == "FLATPAKS" and r.get("runtimes_updated"):
            ru = r["runtimes_updated"]
            L.append(f"   + {ru} system runtime{'s' if ru != 1 else ''} to update")
    if count:
        L += ["", "Nothing was changed. Use Update now to install."]
    return "\n".join(L) + "\n"


def write_check(ctx, r):
    os.makedirs(ctx.base, exist_ok=True)
    write_json(os.path.join(ctx.base, "check.json"), r, ctx)
    txt = render_check(r)
    path = os.path.join(ctx.base, "check.txt")
    with open(path, "w") as f:
        f.write(txt)
    os.chown(path, ctx.uid, ctx.gid)
    print(txt, flush=True)


def prune(ctx):
    keep_days = int(ctx.conf["KEEP_REPORTS_DAYS"])
    cutoff = time.time() - keep_days * 86400
    if os.path.isdir(ctx.reports):
        for f in os.listdir(ctx.reports):
            p = os.path.join(ctx.reports, f)
            if os.path.getmtime(p) < cutoff:
                os.remove(p)
    if os.path.isdir(ctx.backups):
        dirs = sorted(d for d in os.listdir(ctx.backups) if os.path.isdir(os.path.join(ctx.backups, d)))
        for d in dirs[:-int(ctx.conf["KEEP_BACKUPS"])]:
            shutil.rmtree(os.path.join(ctx.backups, d), ignore_errors=True)


# ----------------------------------------------------------------- commands

def cmd_run(ctx, manual, only=None):
    """only: the things the user picked in the panel (see Selection). Picking
    something by name installs it even if its UPDATE_* switch is off."""
    global PROG
    conf = ctx.conf
    sel = Selection(only)
    woke = woke_recently()
    if not manual and not wait_for_idle(float(conf["GAME_WAIT_HOURS"])):
        log("A game stayed open the whole time - skipping until next run.")
        return
    with Lock():
        wait_for_network()
        os.makedirs(ctx.base, exist_ok=True)
        state = read_json(ctx.state_path, {}) or {}
        r = new_report()
        if not sel.all:
            r["partial"] = True
        backup_root = os.path.join(ctx.backups, dt.datetime.now().strftime("%Y-%m-%d_%H%M"))

        booted = system_version(ctx)
        if state.get("distro") != ctx.distro:   # first run, or distro changed
            state["booted_version"] = booted
            state["distro"] = ctx.distro
        state.setdefault("booted_version", booted)

        do_system = sel.system() and (not sel.all or yes(conf["UPDATE_SYSTEM"]))
        do_flatpaks = sel.any_flatpaks() and (not sel.all or yes(conf["UPDATE_FLATPAKS"]))
        do_decky = sel.decky() and (not sel.all or yes(conf["UPDATE_DECKY"]))
        do_plugins = sel.any_plugins() and (not sel.all or yes(conf["UPDATE_PLUGINS"]))

        PROG = Progress(ctx, "update")
        if do_system:
            PROG.add("system", ctx.os_name, "system")
        if do_flatpaks:
            PROG.add("flatpaks", "Flatpak apps", "flatpaks")
        if do_decky:
            PROG.add("decky", "Decky", "decky")
        if do_plugins:
            PROG.add("plugins", "Decky plugins", "plugins")
        PROG.add("health", "Health check", "health")
        try:
            if do_system:
                update_system(ctx, r)
            else:
                r["system"].append(row(ctx.os_name, booted))
            if do_flatpaks:
                update_flatpaks(ctx, r, sel)
            update_decky(ctx, r, backup_root, do_decky, state, forced=not sel.all and sel.decky())
            pending = update_plugins(ctx, r, backup_root, do_plugins, None if sel.all else sel)
            if pending:
                restart_decky()

            prog("health", state="working", detail="Checking Decky and plugins")
            health_check(ctx, r, pending)
            prog("health", state="done")
            state["pending_rollbacks"] = pending  # can still roll back at next boot
            write_json(ctx.state_path, state, ctx)
            write_report(ctx, r)
            prune(ctx)
        finally:
            PROG.finish()
            PROG = None

    if woke and not manual and yes(conf["SLEEP_AFTER_WAKE"]) and not game_running():
        log("Woke up just for this - going back to sleep.")
        sh(["systemctl", "suspend"])


def cmd_boot(ctx):
    with Lock():
        os.makedirs(ctx.base, exist_ok=True)
        state = read_json(ctx.state_path, {}) or {}
        r = read_json(ctx.latest_json) or new_report()

        booted = system_version(ctx)
        last = state.get("booted_version") if state.get("distro", ctx.distro) == ctx.distro else None
        state["distro"] = ctx.distro
        r["system"] = [x for x in r["system"] if x["name"] not in DISTRO_NAMES.values() or x["name"] == ctx.os_name]
        sysrow = next((x for x in r["system"] if x["name"] == ctx.os_name), None)
        if sysrow is None:
            sysrow = row(ctx.os_name, booted)
            r["system"].insert(0, sysrow)
        if last and booted and booted != last:
            sysrow.update(old=last, new=booted, status="updated", note=None)
        elif sysrow["status"] == "staged" and booted == sysrow.get("new"):
            sysrow.update(status="updated", note=None)
        if sysrow["status"] == "updated" and not sysrow.get("old"):
            sysrow["old"] = last
        state["booted_version"] = booted

        reset_health(r)

        health_check(ctx, r, state.get("pending_rollbacks", {}) or {})
        state["pending_rollbacks"] = {}
        write_json(ctx.state_path, state, ctx)
        write_report(ctx, r)


def cmd_check(ctx):
    with Lock():
        wait_for_network(60)
        r = new_report()
        r["kind"] = "check"
        check_system(ctx, r)
        update_decky(ctx, r, None, do_update=False, state=read_json(ctx.state_path, {}) or {})
        update_plugins(ctx, r, None, do_update=False)
        check_flatpaks(ctx, r)
        write_check(ctx, r)


def reset_health(r):
    """Clear the last health check's results before re-checking."""
    r["issues"] = [i for i in r["issues"] if i.get("phase") != "health"]
    r["plugins"] = [p for p in r["plugins"] if not p.get("health_only")]
    for p in r["plugins"]:
        if "prev_status" in p:
            p["status"] = p.pop("prev_status")
    r["health"] = []


def cmd_reinstall_decky(ctx):
    with Lock():
        wait_for_network(60)
        os.makedirs(ctx.base, exist_ok=True)
        cur = decky_version(ctx)
        backup = None
        if os.path.exists(ctx.loader_bin):
            backup = save_decky_backup(
                ctx, os.path.join(ctx.backups, dt.datetime.now().strftime("%Y-%m-%d_%H%M")), cur)

        log("Reinstalling Decky...")
        tag = reinstall_decky(ctx)
        ok = False
        if not tag:
            msg = "Couldn't download Decky. Check your internet connection."
        else:
            restart_decky()
            ok = decky_healthy()
            if ok:
                msg = f"Decky reinstalled ({tag})"
                # Asking for the latest Decky by hand ends any hold left by a rollback.
                state = read_json(ctx.state_path, {}) or {}
                if state.pop("decky_skip", None):
                    write_json(ctx.state_path, state, ctx)
            elif backup and cur:
                put_binary(ctx, backup, cur)
                restart_decky()
                decky_healthy()
                msg = "The fresh copy didn't start, so the previous version was restored."
            else:
                msg = "Decky didn't start after reinstalling."

        r = read_json(ctx.latest_json) or new_report()
        reset_health(r)
        drow = next((x for x in r["system"] if x["name"] == "Decky"), None)
        if drow is None:
            drow = row("Decky", cur)
            r["system"].append(drow)
        if ok:
            changed = cur and tag and cur != tag
            drow.update(old=cur if changed else tag, new=tag if changed else None,
                        status="updated" if changed else "unchanged",
                        note=f"Reinstalled {fmt_time(now_iso())}")
        health_check(ctx, r, {})
        write_report(ctx, r)
        write_json(os.path.join(ctx.base, "action.json"),
                   {"action": "reinstall_decky", "ok": ok, "message": msg, "time": now_iso()}, ctx)
        log(msg)


def cmd_rollback_info(ctx):
    """What rollback-decky would do, as JSON (the Decky panel reads this)."""
    state = read_json(ctx.state_path, {}) or {}
    target = rollback_target(ctx)
    print(json.dumps({
        "current": decky_version(ctx),
        "target": {k: target.get(k) for k in ("version", "source", "saved")} if target else None,
        "held": state.get("decky_skip"),
    }))


def cmd_rollback_decky(ctx):
    with Lock():
        os.makedirs(ctx.base, exist_ok=True)
        state = read_json(ctx.state_path, {}) or {}
        cur = decky_version(ctx)
        target = rollback_target(ctx) if cur and os.path.exists(ctx.loader_bin) else None
        ok = False
        if not cur or not os.path.exists(ctx.loader_bin):
            msg = "Couldn't find Decky, so there is nothing to roll back."
        elif not target:
            msg = "No earlier Decky version is available to go back to."
        else:
            old = target["version"]
            log(f"Rolling Decky back {cur} -> {old}...")
            backup = save_decky_backup(
                ctx, os.path.join(ctx.backups, dt.datetime.now().strftime("%Y-%m-%d_%H%M")), cur)
            swapped = False
            try:
                if target["source"] == "backup":
                    put_binary(ctx, target["path"], old)
                else:
                    wait_for_network(60)
                    path = download_decky(target["url"])
                    put_binary(ctx, path, old)
                    os.remove(path)
                swapped = True
                restart_decky()
                ok = decky_healthy()
                problem = f"{old} didn't start"
            except Exception as e:
                problem = f"Couldn't put {old} back ({str(e)[:60]})"
            if ok:
                # Don't let the next run update straight back to the version just left
                # (or to an even newer one left by an earlier rollback).
                held = state.get("decky_skip")
                state["decky_skip"] = held if held and is_newer(held, cur) else cur
                write_json(ctx.state_path, state, ctx)
                msg = f"Decky rolled back to {old} (was {cur})"
            else:
                if swapped or decky_version(ctx) != cur:
                    put_binary(ctx, backup, cur)
                    restart_decky()
                    decky_healthy()
                msg = f"{problem}, so {cur} was kept."

        r = read_json(ctx.latest_json) or new_report()
        reset_health(r)
        if ok:
            drow = next((x for x in r["system"] if x["name"] == "Decky"), None)
            if drow is None:
                drow = row("Decky", cur)
                r["system"].append(drow)
            drow.update(old=target["version"], new=cur, status="rolled_back",
                        note=f"Rolled back by you · {fmt_time(now_iso())}")
        health_check(ctx, r, {})
        write_report(ctx, r)
        write_json(os.path.join(ctx.base, "action.json"),
                   {"action": "rollback_decky", "ok": ok, "message": msg, "time": now_iso()}, ctx)
        log(msg)


def main():
    ap = argparse.ArgumentParser(description="Bazzite + Decky upkeep")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run", help="update everything, then health-check")
    p.add_argument("--manual", action="store_true", help="don't wait for games to close")
    p.add_argument("--only", nargs="+", metavar="ITEM",
                   help="update just these: system, decky, runtimes, plugin:<folder>, "
                        "flatpak:<system|user>:<app id>")
    sub.add_parser("boot", help="health-check after a restart")
    sub.add_parser("check", help="see what updates are available, change nothing")
    sub.add_parser("reinstall-decky", help="fresh copy of the latest Decky, with rollback")
    sub.add_parser("rollback-decky", help="go back to the Decky version you had before")
    sub.add_parser("rollback-info", help="show what rollback-decky would do")
    sub.add_parser("show", help="print the latest report")
    w = sub.add_parser("_flatpak-worker")   # internal: started by `run`, see flatpak_worker()
    w.add_argument("--scope", choices=("system", "user"), required=True)
    w.add_argument("--all", action="store_true")
    w.add_argument("--runtimes", action="store_true")
    w.add_argument("--app", action="append", default=[])
    a = ap.parse_args()

    if a.cmd == "_flatpak-worker":
        sys.exit(flatpak_worker(a.scope, a.all, a.runtimes, set(a.app)))

    ctx = Ctx(load_conf())
    if a.cmd == "show":
        try:
            with open(ctx.latest_txt) as f:
                print(f.read(), end="")
        except FileNotFoundError:
            print("No report yet. Run: sudo upkeep run --manual")
        return
    if a.cmd == "rollback-info":
        cmd_rollback_info(ctx)
        return
    if os.geteuid() != 0:
        sys.exit("Run with sudo.")
    if a.cmd == "run":
        cmd_run(ctx, a.manual, a.only)
    elif a.cmd == "check":
        cmd_check(ctx)
    elif a.cmd == "reinstall-decky":
        cmd_reinstall_decky(ctx)
    elif a.cmd == "rollback-decky":
        cmd_rollback_decky(ctx)
    else:
        cmd_boot(ctx)


if __name__ == "__main__":
    main()
