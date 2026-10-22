#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
test -f "$ROOT/build/libbaogu.so"
TARGET="${XDG_DATA_HOME:-$HOME/.local/share}/fcitx5/addon"
mkdir -p "$TARGET"
# Remove the pre-rename addon so two bridges cannot claim the same D-Bus name.
rm -f "$TARGET/voiceime.conf"
cat > "$TARGET/baogu.conf" <<EOF
[Addon]
Name=Baogu IME native text input
Type=SharedLibrary
Library=$ROOT/build/libbaogu
Category=Module
Version=0.1
OnDemand=False
EOF
echo "Installed $TARGET/baogu.conf; restart Fcitx5 to load the addon."
