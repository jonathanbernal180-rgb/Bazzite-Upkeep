"""Upkeep Decky plugin backend: reads reports, runs checks/updates, sets the schedule."""
import json
import os
import re
import subprocess

import decky

BASE = os.path.join(decky.DECKY_USER_HOME, "upkeep")
REPORT = os.path.join(BASE, "latest.json")
CHECK = os.path.join(BASE, "check.json")
ACTION = os.path.join(BASE, "action.json")
PROGRESS = os.path.join(BASE, "progress.json")
SEEN = os.path.join(decky.DECKY_PLUGIN_SETTINGS_DIR, "seen.json")
SCHEDULE = os.path.join(decky.DECKY_PLUGIN_SETTINGS_DIR, "schedule.json")
SETUP = os.path.join(decky.DECKY_PLUGIN_SETTINGS_DIR, "setup.json")
CONF = "/etc/upkeep.conf"
UPKEEP_CANDIDATES = ("/usr/local/bin/upkeep", os.path.join(decky.DECKY_USER_HOME, "homebrew", "upkeep", "upkeep"))
DISTROS = ("bazzite", "steamos")
TIMER = "upkeep-run.timer"
DROPIN = "/etc/systemd/system/upkeep-run.timer.d/schedule.conf"

UNITS = {
    "update": ("upkeep-run.service", "upkeep-manual.service"),
    "check": ("upkeep-check.service",),
    "reinstall": ("upkeep-reinstall.service",),
    "rollback": ("upkeep-rollback.service",),
}
# What "Install selected" may ask for (see Selection in upkeep.py). Anything else is dropped.
SELECT_KEY = re.compile(r"^(system|decky|runtimes|plugin:[^/\x00-\x1f]{1,100}|flatpak:(system|user):[A-Za-z0-9._-]{1,200})$")
FREQUENCIES = ("daily", "every_other_day", "weekly", "manual")
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
DEFAULT_SCHEDULE = {"frequency": "daily", "hour": 4, "minute": 0, "weekday": "Sun"}


def _env():
    # Decky's bundled libraries can break system tools; drop them.
    env = os.environ.copy()
    env.pop("LD_LIBRARY_PATH", None)
    return env


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, env=_env())


def _read(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def _conf():
    conf = {}
    try:
        with open(CONF) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    conf[k.strip()] = v.strip().strip('"')
    except FileNotFoundError:
        pass
    return conf


def _set_conf(key, value):
    lines, found = [], False
    try:
        with open(CONF) as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        pass
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i], found = f"{key}={value}", True
    if not found:
        lines.append(f"{key}={value}")
    with open(CONF, "w") as f:
        f.write("\n".join(lines) + "\n")


def _upkeep_path():
    path = _conf().get("UPKEEP_PATH")
    if path and os.path.exists(path):
        return path
    for c in UPKEEP_CANDIDATES:
        if os.path.exists(c):
            return c
    return UPKEEP_CANDIDATES[0]


def _detect_distro():
    info = {}
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    info[k] = v.strip('"')
    except FileNotFoundError:
        pass
    ids = " ".join(info.get(k, "") for k in ("ID", "ID_LIKE", "VARIANT_ID", "NAME")).lower()
    if "steamos" in ids:
        return "steamos"
    if "bazzite" in ids:
        return "bazzite"
    return None


def _start(unit, *args):
    # Its own systemd unit, so it survives Decky restarting mid-run.
    subprocess.Popen(
        ["systemd-run", f"--unit={unit}", "--collect",
         "-p", "Nice=19", "-p", "IOSchedulingClass=idle", _upkeep_path(), *args],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=_env())


def _on_calendar(s):
    t = f"{s['hour']:02d}:{s['minute']:02d}:00"
    if s["frequency"] == "weekly":
        return f"{s['weekday']} *-*-* {t}"
    if s["frequency"] == "every_other_day":
        return f"*-*-1/2 {t}"
    return f"*-*-* {t}"


def _next_run():
    out = _run(["systemctl", "show", TIMER, "-p", "NextElapseUSecRealtime", "--value"]).stdout.strip()
    if not out or out == "n/a":
        return None
    iso = _run(["date", "-d", out, "--iso-8601=seconds"]).stdout.strip()
    return iso or None


class Plugin:
    # ---- reports
    async def get_report(self):
        return _read(REPORT)

    async def get_check(self):
        return _read(CHECK)

    async def get_action(self):
        return _read(ACTION)

    async def was_seen(self, key, ns="report"):
        return (_read(SEEN) or {}).get(ns) == key

    async def mark_seen(self, key, ns="report"):
        seen = _read(SEEN) or {}
        seen[ns] = key
        os.makedirs(os.path.dirname(SEEN), exist_ok=True)
        with open(SEEN, "w") as f:
            json.dump(seen, f)

    # ---- actions
    async def is_running(self):
        """Returns "update", "check", "reinstall", "rollback", or None."""
        for kind, units in UNITS.items():
            for unit in units:
                if _run(["systemctl", "is-active", unit]).stdout.strip() in ("active", "activating"):
                    return kind
        return None

    async def run_now(self, only=None):
        """only: list of things to update (keys from the update check). None = everything."""
        if await self.is_running():
            return False
        args = ["run", "--manual"]
        if only is not None:
            keys = [k for k in only if isinstance(k, str) and SELECT_KEY.match(k)]
            if not keys:
                return False
            args += ["--only", *keys]
        _start("upkeep-manual", *args)
        return True

    async def get_progress(self):
        """What the update that's running right now is doing (None when nothing is)."""
        p = _read(PROGRESS)
        return p if p and p.get("running") else None

    async def rollback_info(self):
        """Which Decky version a rollback would go back to."""
        try:
            # The answer is the last line; anything above it is upkeep's own log output.
            return json.loads(_run([_upkeep_path(), "rollback-info"]).stdout.strip().splitlines()[-1])
        except Exception:
            return None

    async def rollback_decky(self):
        if await self.is_running():
            return False
        _start("upkeep-rollback", "rollback-decky")
        return True

    async def reinstall_decky(self):
        if await self.is_running():
            return False
        _start("upkeep-reinstall", "reinstall-decky")
        return True

    async def check_now(self):
        if await self.is_running():
            return False
        _start("upkeep-check", "check")
        return True

    # ---- setup / distro
    async def get_setup(self):
        conf = _conf()
        path = _upkeep_path()
        home = decky.DECKY_USER_HOME
        return {
            "done": bool((_read(SETUP) or {}).get("done")),
            "distro": conf.get("DISTRO") or _detect_distro() or "bazzite",
            "detected": _detect_distro(),
            "installed": os.path.exists(path),
            # How to type the command in Konsole on this machine
            "cli": "upkeep" if path == "/usr/local/bin/upkeep" else path.replace(home, "~", 1),
        }

    async def set_distro(self, distro):
        if distro not in DISTROS:
            return await self.get_setup()
        _set_conf("DISTRO", distro)
        os.makedirs(os.path.dirname(SETUP), exist_ok=True)
        with open(SETUP, "w") as f:
            json.dump({"done": True, "distro": distro}, f)
        decky.logger.info(f"Distro set to {distro}")
        return await self.get_setup()

    # ---- schedule
    async def get_schedule(self):
        s = dict(DEFAULT_SCHEDULE)
        s.update(_read(SCHEDULE) or {})
        s["next_run"] = None if s["frequency"] == "manual" else _next_run()
        return s

    async def set_schedule(self, frequency, hour, minute, weekday):
        if frequency not in FREQUENCIES:
            frequency = "daily"
        hour = min(23, max(0, int(hour)))
        minute = min(59, max(0, int(minute)))
        weekday = weekday if weekday in DAYS else "Sun"
        s = {"frequency": frequency, "hour": hour, "minute": minute, "weekday": weekday}

        os.makedirs(os.path.dirname(SCHEDULE), exist_ok=True)
        with open(SCHEDULE, "w") as f:
            json.dump(s, f)

        if frequency == "manual":
            _run(["systemctl", "disable", "--now", TIMER])
        else:
            os.makedirs(os.path.dirname(DROPIN), exist_ok=True)
            with open(DROPIN, "w") as f:
                # Empty OnCalendar= clears the default 4 AM before setting ours
                f.write(f"[Timer]\nOnCalendar=\nOnCalendar={_on_calendar(s)}\nRandomizedDelaySec=0\n")
            _run(["systemctl", "daemon-reload"])
            _run(["systemctl", "enable", TIMER])
            _run(["systemctl", "restart", TIMER])
        decky.logger.info(f"Schedule set: {s}")
        return await self.get_schedule()

    async def _main(self):
        decky.logger.info("Upkeep plugin loaded")

    async def _unload(self):
        pass
