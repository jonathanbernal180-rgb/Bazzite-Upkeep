# Bazzite Upkeep

Hands-off updates for a couch-gaming PC, with a Decky panel to watch and control them.

> **Designed specifically for Bazzite, built to be compatible with SteamOS.**
> On first open, the Decky panel asks which one you're running (it detects it for you),
> and you can switch later with **Change distro**.

It runs on a schedule you choose, or when you press the button. It waits for games to
close and runs at the lowest CPU/disk priority. No AI, no GPU use.

## Features

**Updates four things**
- The **system** (`rpm-ostree` on Bazzite, `steamos-update` on SteamOS)
- **Flatpak** apps and runtimes
- **Decky Loader**
- **Decky plugins**, from the Decky store

**You choose what gets installed**
- **Update all** in one go, or **Check for updates** and switch off anything you want to skip
- Keep plugins you've patched by hand on their current version with a hold list
- Run it nightly, every other day, weekly, or only when you press the button

**You can see what it's doing**
- A live percentage beside each thing while it updates
- A plain report afterwards in the Decky panel, with a toast when something needs a look
- Reports are also saved as text files, readable without Decky

**It protects what it touches**
- Backs up Decky and each plugin before updating them
- Checks afterwards, and again after every boot, that Decky is running and each plugin loaded
- Fixes what it safely can: restarts or reinstalls Decky, and puts back a plugin that broke after its update
- **Roll back Decky** one version if a Decky update is what broke things
- Never rolls back the system itself; it tells you how instead

**It stays out of the way**
- Waits while a game is open
- Can wake the PC from sleep for its run, then put it back to sleep
- Everything also works from Konsole, for when Decky itself is broken (see [Workarounds](#workarounds))

## Status: early test build

This is new and lightly tested, and it updates your whole system. Try it on a PC you
can afford to troubleshoot.

- **Tested on one PC:** Bazzite 45 (`bazzite-deck` image) with Decky Loader v3.3.1. An
  earlier build ran a full **Update now** there (Flatpak apps and one plugin), and the
  current panel loads in Decky.
- **Only tested in sandbox folders, not in a real run:** choosing which updates to
  install, the live percentages, and rolling Decky back.
- **Not tested at all:** SteamOS (written for it, never run), a system-image update, a
  real Decky update, the scheduled run with wake-from-sleep, and the after-boot check.
- **Plugin updates:** on that first real run a plugin update left the plugin broken (a
  file it downloads separately was skipped, and file ownership was wrong). That is fixed
  in the code, but the fix hasn't done a real plugin update yet. Until it has, consider
  listing plugins you rely on in `HOLD_PLUGINS` (see Settings).
- **Known gap:** the health check reads Decky's logs. A plugin whose screen breaks inside
  Steam's menu without logging an error still counts as loaded.

If something goes wrong, see [Workarounds](#workarounds). Copies of Decky and of each
plugin from before an update are in `~/upkeep/backups/`.

Found a problem? Please open an issue with `~/upkeep/latest.txt` and the output of
`journalctl -u 'upkeep-*' --since today`.

## How to install on Bazzite

You need Decky Loader already installed.

1. Switch to **Desktop Mode** and open **Konsole**.
2. Download the project and go into its folder:
   ```bash
   git clone https://github.com/jonathanbernal180-rgb/Bazzite-Upkeep.git
   cd Bazzite-Upkeep
   ```
   Prefer a download? On the GitHub page click **Code → Download ZIP**, unpack it, and
   use `cd ~/Downloads/Bazzite-Upkeep-main` instead.
3. Install the updater and its timers. It asks for your password.
   ```bash
   bash install.sh
   ```
   If Bazzite's own auto-updater (`uupd`) is switched on, the installer offers to turn it
   off, so the two don't both update the system.
4. See what it would update. This changes nothing.
   ```bash
   sudo upkeep check
   ```
5. Install the Decky panel:
   ```bash
   cd decky-plugin
   bash install-plugin.sh
   ```
6. Back in Game Mode, open the Quick Access menu (**…** button) → Decky → **Upkeep**, and
   confirm **Bazzite** on the first screen.

To run the first update straight away, press **Update now** in the panel, or run
`sudo upkeep run --manual` and then `upkeep show` to read the report.

Installing switches on a nightly 4:00 AM run straight away. To change or stop it, use
**Schedule** in the panel, or run `sudo systemctl disable --now upkeep-run.timer`.

## How to install on SteamOS

> Not tested on SteamOS yet. See [Status](#status-early-test-build).

You need Decky Loader already installed.

1. Switch to **Desktop Mode** and open **Konsole**. If you have never set a password, set
   one now, because the installer needs `sudo`:
   ```bash
   passwd
   ```
2. Download the project and go into its folder:
   ```bash
   git clone https://github.com/jonathanbernal180-rgb/Bazzite-Upkeep.git
   cd Bazzite-Upkeep
   ```
   Prefer a download? On the GitHub page click **Code → Download ZIP**, unpack it, and
   use `cd ~/Downloads/Bazzite-Upkeep-main` instead.
3. Install the updater and its timers. It asks for your password.
   ```bash
   bash install.sh
   ```
   On SteamOS the updater goes to `~/homebrew/upkeep/upkeep`, because the system folders
   are read-only. That is why the commands below use the full path.
4. See what it would update. This changes nothing.
   ```bash
   sudo ~/homebrew/upkeep/upkeep check
   ```
5. Install the Decky panel:
   ```bash
   cd decky-plugin
   bash install-plugin.sh
   ```
6. Back in Gaming Mode, open the Quick Access menu (**…** button) → Decky → **Upkeep**, and
   confirm **SteamOS** on the first screen.

To run the first update straight away, press **Update now** in the panel, or run
`sudo ~/homebrew/upkeep/upkeep run --manual` and then `~/homebrew/upkeep/upkeep show`.

As on Bazzite, installing switches on a nightly 4:00 AM run. Change or stop it under
**Schedule** in the panel, or run `sudo systemctl disable --now upkeep-run.timer`.

## What's different per distro

| | Bazzite | SteamOS |
|---|---|---|
| System updates | `rpm-ostree upgrade` | `steamos-update` |
| Script location | `/usr/local/bin/upkeep` | `~/homebrew/upkeep/upkeep` (SteamOS system folders are read-only) |
| Undo a system update | Previous boot entry or `sudo rpm-ostree rollback` | Previous version in the SteamOS boot menu |
| Built-in auto-updater | `uupd` (installer offers to turn it off) | Steam handles prompts; nothing to turn off |
| Plugin build | Homebrew | Temporary `podman` container |

Flatpaks, Decky, plugins, schedule and reports work the same on both.
`install.sh` auto-detects the distro; force it with `bash install.sh --distro steamos`.

The Decky panel ships already built, so installing it needs no extra tools. The "Plugin
build" row only applies if you edit `decky-plugin/src/` and run
`bash install-plugin.sh --rebuild`.

## When things run

| What | When |
|---|---|
| Updates + health check | On your schedule (default 4:00 AM daily). Wakes from sleep; if the PC was off, it runs at the next boot |
| Health check only | 2 min after every boot (catches Steam updates breaking Decky) |
| Manual update | **Update now** in the Decky panel asks: **Update all**, or **Choose updates**. Or `sudo upkeep run --manual` |
| Only some updates | **Check for updates**, switch off what you want to skip, then **Install selected**. Or `sudo upkeep run --manual --only ...` (see below) |
| Reinstall Decky | **Reinstall Decky** in the panel, or `sudo upkeep reinstall-decky` (use this in Desktop Mode if Decky is gone) |
| Roll back Decky | **Roll back Decky** in the panel, or `sudo upkeep rollback-decky` |
| Check only | **Check for updates** in the Decky panel, or `sudo upkeep check` (installs nothing) |

While an update runs, the panel lists each thing being updated with a percentage beside it.
Flatpak runtimes share one line.

### Picking updates from Konsole

`--only` takes any of: `system`, `decky`, `runtimes`, `plugin:<folder name>`,
`flatpak:<system|user>:<app id>`. For example:

```bash
sudo upkeep run --manual --only decky flatpak:system:org.mozilla.firefox
```

Naming something installs it even if its `UPDATE_*` switch is `no`. Plugins in
`HOLD_PLUGINS` stay held.

## Rolling back Decky

For when plugins stopped loading, or the Decky menu misbehaves, right after Decky updated.

- Goes back **one version**: to the copy Upkeep saved before it updated Decky, or, if
  there is no saved copy, to Decky's previous release (downloaded from Decky's GitHub).
- Saves the current version first. If the older one doesn't start, the current one is kept.
- Afterwards Upkeep leaves Decky alone until a release newer than the one you left comes
  out. **Reinstall Decky**, or picking Decky under **Check for updates**, ends that hold.

## Schedule

Set it in the Decky panel under **Schedule**:

- **How often:** Daily (default), Every other day, Weekly (pick the day), or Manual only
- **Time:** hour and minute (:00, :15, :30, :45)
- Shows when the next run is

The panel saves this as a systemd override in `/etc/systemd/system/upkeep-run.timer.d/schedule.conf`.
Without the plugin, the default is 4:00 AM daily.

## Settings — `/etc/upkeep.conf`

Set any `UPDATE_*` to `no` to only *report* available updates for that part.
`SLEEP_AFTER_WAKE=yes` puts the PC back to sleep if it woke up just for upkeep.
`HOLD_PLUGINS=Name One, Name Two` keeps those plugins on their current version (new
versions are still reported). Use it for a plugin you've patched by hand, since an update
replaces the patch.

## Files

- `~/upkeep/latest.txt` – latest report (also `latest.json` for the Decky panel)
- `~/upkeep/check.txt` – latest update check (also `check.json`)
- `~/upkeep/progress.json` – what a running update is doing right now (the panel reads it)
- `~/upkeep/reports/` – past reports (30 days)
- `~/upkeep/backups/` – Decky + plugin backups (last 5 runs)
- Logs: `journalctl -u upkeep-run -u upkeep-boot`

## If the system update breaks something

- **Bazzite:** pick the previous entry in the boot menu, or run `sudo rpm-ostree rollback` and restart.
- **SteamOS:** restart and choose the previous version in the SteamOS boot menu.

## Uninstall

```bash
sudo systemctl disable --now upkeep-run.timer upkeep-boot.timer
sudo rm -rf /etc/systemd/system/upkeep-* /etc/upkeep.conf
sudo rm -f /usr/local/bin/upkeep           # Bazzite
sudo rm -rf ~/homebrew/upkeep              # SteamOS
sudo rm -rf ~/homebrew/plugins/Upkeep && sudo systemctl restart plugin_loader
sudo systemctl enable --now uupd.timer   # Bazzite: turn its own auto-updater back on
```

## Workarounds

Use these in **Desktop Mode → Konsole** when a button in the Decky panel can't help.
The same list is shown read-only at the bottom of the Upkeep panel, matched to your distro.
On **SteamOS**, replace `upkeep` with `~/homebrew/upkeep/upkeep`.

| Problem | What to do |
|---|---|
| Decky is missing or won't open | `sudo upkeep reinstall-decky` |
| A Decky update broke something | `sudo upkeep rollback-decky` (`upkeep rollback-info` shows where it would go) |
| See the latest report without Decky | `upkeep show` (or open `~/upkeep/latest.txt`) |
| Update manually | `sudo upkeep run --manual` |
| Check for updates manually | `sudo upkeep check` (installs nothing) |
| Game Mode update stuck at 100% (Bazzite) | Skip Steam's update button: use **Update now** or `sudo upkeep run --manual` |
| A system update broke something (Bazzite) | Pick the previous entry in the boot menu, or `sudo rpm-ostree rollback` and restart |
| A system update broke something (SteamOS) | Restart and choose the previous version in the SteamOS boot menu (Steam Deck: hold ••• while powering on) |
| `sudo` asks for a password you never set (SteamOS) | Set one once with `passwd` |
| A plugin broke and wasn't fixed | `sudo rm -rf ~/homebrew/plugins/<name> && sudo cp -a ~/upkeep/backups/<date>/plugins/<name> ~/homebrew/plugins/ && sudo systemctl restart plugin_loader` |
| Turn off automatic updates without Decky | `sudo systemctl disable --now upkeep-run.timer` (back on: `enable --now`) |
| Watch what upkeep is doing | `journalctl -fu upkeep-run -u upkeep-manual` |
