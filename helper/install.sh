#!/bin/sh
# Installs the BrainFodder helper on this Mac. macOS then starts it only when the
# page's Fetch button connects, and it quits when that fetch is done.
set -e
mkdir -p "$HOME/Library/Logs/BrainFodder" "$HOME/Library/Application Support/BrainFodder/run"
cp "$(dirname "$0")/com.cesarxdesign.brainfodder.plist" "$HOME/Library/LaunchAgents/"
launchctl bootout "gui/$(id -u)/com.cesarxdesign.brainfodder" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.cesarxdesign.brainfodder.plist"
echo "Installed. Nothing runs until you press Fetch."
