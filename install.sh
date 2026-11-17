#!/usr/bin/env bash
# Installs the upkeep script + timers. Run from this folder:
#   bash install.sh                  (auto-detects Bazzite or SteamOS)
#   bash install.sh --distro steamos (force one)
# Designed specifically for Bazzite; built to be compatible with SteamOS.
set -euo pipefail
# "sudo bash", not just "sudo": a copy downloaded from GitHub's website isn't marked executable.
[[ $EUID -eq 0 ]] || exec sudo bash "$0" "$@"

USER_NAME="${SUDO_USER:-}"
if [[ -z "$USER_NAME" || "$USER_NAME" == root ]]; then
  echo "Run this as your normal user (it will ask for sudo itself)."; exit 1
fi
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
USER_GROUP="$(id -gn "$USER_NAME")"
HERE="$(cd "$(dirname "$0")" && pwd)"

# ---- which distro?
DISTRO=""
if [[ "${1:-}" == "--distro" ]]; then DISTRO="${2:-}"; fi
if [[ -z "$DISTRO" ]]; then
  . /etc/os-release
  case "${ID:-} ${ID_LIKE:-} ${VARIANT_ID:-} ${NAME:-}" in
    *[Ss]team[Oo][Ss]*) DISTRO=steamos ;;
    *[Bb]azzite*)       DISTRO=bazzite ;;
    *) echo "Couldn't tell if this is Bazzite or SteamOS."
       echo "Re-run with: bash install.sh --distro bazzite   (or steamos)"; exit 1 ;;
  esac
fi
[[ "$DISTRO" == bazzite || "$DISTRO" == steamos ]] || { echo "Unknown distro: $DISTRO"; exit 1; }
echo "→ Setting up for: $DISTRO"

# ---- where the script lives
# Bazzite keeps /usr/local writable. SteamOS's system folders are read-only and
# get replaced on updates, so it lives next to Decky in ~/homebrew instead.
if [[ "$DISTRO" == bazzite ]]; then
  UPKEEP=/usr/local/bin/upkeep
else
  UPKEEP="$USER_HOME/homebrew/upkeep/upkeep"
fi
install -d "$(dirname "$UPKEEP")"
install -m 0755 "$HERE/upkeep.py" "$UPKEEP"
echo "→ Installed script to $UPKEEP"

# ---- config
set_conf() {  # set_conf KEY VALUE
  if grep -q "^$1=" /etc/upkeep.conf; then sed -i "s#^$1=.*#$1=$2#" /etc/upkeep.conf
  else echo "$1=$2" >> /etc/upkeep.conf; fi
}
FRESH=no   # yes = first install on this PC (no settings file yet)
[[ -f /etc/upkeep.conf ]] || { cp "$HERE/upkeep.conf" /etc/upkeep.conf; FRESH=yes; }
set_conf USER "$USER_NAME"
set_conf DISTRO "$DISTRO"
set_conf UPKEEP_PATH "$UPKEEP"
echo "→ Settings in /etc/upkeep.conf"

# ---- systemd units (/etc survives updates on both distros)
for f in "$HERE"/systemd/*; do
  sed "s#@UPKEEP@#$UPKEEP#" "$f" > "/etc/systemd/system/$(basename "$f")"
  chmod 0644 "/etc/systemd/system/$(basename "$f")"
done
systemctl daemon-reload
if [[ "$FRESH" == yes ]]; then
  # --now starts the schedule right away instead of after the next restart.
  systemctl enable --now upkeep-run.timer
  SCHEDULE="Nightly run: 4:00 AM (change it in the Decky panel)."
else
  # Updating an existing install: keep the schedule however it was set (it may be switched off).
  SCHEDULE="Schedule left as it was: $(systemctl is-enabled upkeep-run.timer 2>/dev/null || true)."
fi
# The boot check is left to start at the next boot (starting it now would run it immediately).
systemctl enable upkeep-boot.timer
install -d -o "$USER_NAME" -g "$USER_GROUP" "$USER_HOME/upkeep"

# ---- Bazzite only: its own background auto-updater
if [[ "$DISTRO" == bazzite ]] && systemctl is-enabled uupd.timer &>/dev/null; then
  echo
  echo "Bazzite's built-in auto-updater (uupd.timer) is on."
  read -rp "Turn it off so upkeep handles (and reports) all updates? [Y/n] " ans
  if [[ ! "$ans" =~ ^[Nn] ]]; then
    systemctl disable --now uupd.timer
    echo "→ uupd.timer disabled (undo: sudo systemctl enable --now uupd.timer)"
  fi
fi

CMD=$([[ "$DISTRO" == bazzite ]] && echo upkeep || echo "$UPKEEP")
echo
echo "Done. $SCHEDULE Boot check: 2 min after startup."
echo "Try it now:   sudo $CMD run --manual"
echo "See report:   $CMD show"
