#!/usr/bin/env bash
# Install the transcript router as a macOS launchd agent. Idempotent.
#
#   ./install.sh            # install / reinstall
#   ./install.sh --uninstall
#
# Optional: export MIRROR_ROOT=/path/to/shared/storage before running, if your
# shared folder isn't at ~/Dropbox or ~/Library/CloudStorage/Dropbox.
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABEL="cc-transcript-sync"
PLIST_SRC="$INSTALL_DIR/$LABEL.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [[ "${1:-}" == "--uninstall" ]]; then
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    rm -f "$PLIST_DEST"
    echo "✅ uninstalled $LABEL"
    exit 0
fi

chmod +x "$INSTALL_DIR/run_transcript_sync.sh"
mkdir -p "$HOME/Library/LaunchAgents"

sed "s|{{INSTALL_DIR}}|$INSTALL_DIR|g" "$PLIST_SRC" > "$PLIST_DEST"

# Unload first: launchctl load is not idempotent, and a stale definition will
# keep running the OLD script path without saying so.
launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"

echo "✅ installed $LABEL  (runs now, then every 15 min)"
echo "   log: $INSTALL_DIR/$LABEL.log"
echo
echo "Verify it actually ran — a loaded agent is not a working one:"
echo "   launchctl list | grep $LABEL"
echo "   sleep 5 && cat '$INSTALL_DIR/$LABEL.log'"
echo
echo "🔴 Before you leave this running: check transcript_sync_excludes.txt."
echo "   Every repo you work in gets copied to shared storage unless excluded."
