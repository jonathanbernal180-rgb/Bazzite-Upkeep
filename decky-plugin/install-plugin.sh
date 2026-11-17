#!/usr/bin/env bash
# Installs the Upkeep Decky plugin, building it first if dist/ is missing. Run from this folder.
#   bash install-plugin.sh            (uses the built panel in dist/ if there is one)
#   bash install-plugin.sh --rebuild  (build again after editing src/)
# Builds on Bazzite (Homebrew) and SteamOS (container build, no installs needed).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

if [[ -f dist/index.js && "${1:-}" != "--rebuild" ]]; then
  echo "→ Using the panel that's already built (bash install-plugin.sh --rebuild to build it again)"
elif command -v pnpm >/dev/null; then
  echo "→ Building with local pnpm"
  pnpm install && pnpm run build
elif command -v brew >/dev/null; then
  echo "→ Installing Node + pnpm with Homebrew"
  brew install node pnpm
  pnpm install && pnpm run build
elif command -v podman >/dev/null; then
  echo "→ Building inside a temporary Node container (nothing gets installed)"
  podman run --rm -v "$HERE":/w:Z -w /w docker.io/library/node:22 \
    sh -c "corepack enable && pnpm install && pnpm run build"
else
  echo "Need pnpm, Homebrew or podman to build the plugin."; exit 1
fi

DEST="$HOME/homebrew/plugins/Upkeep"
echo "→ Installing to $DEST"
sudo rm -rf "$DEST"
sudo mkdir -p "$DEST"
sudo cp -r dist main.py plugin.json package.json "$DEST/"
sudo systemctl restart plugin_loader
echo "Done. Open the Quick Access menu (…) → Upkeep."
