#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$UNIT_DIR"

# One-time migration from the pre-rename layout: keep the user's hotwords and
# settings, then retire the legacy units so they cannot race this daemon.
LEGACY_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/voiceime"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}/baogu"
if [ -d "$LEGACY_CONFIG" ] && [ ! -e "$CONFIG_HOME" ]; then
  cp -a "$LEGACY_CONFIG" "$CONFIG_HOME"
fi
for legacy_unit in voiceime-ptt.service voiceime-overlay.service voiceime-corrector.service; do
  systemctl --user disable --now "$legacy_unit" >/dev/null 2>&1 || true
  rm -f "$UNIT_DIR/$legacy_unit"
done

LLM_ENABLED="${BAOGU_LLM_ENABLED:-0}"
LLM_MODE="${BAOGU_LLM_MODE:-aggressive}"
LLM_TIMEOUT="${BAOGU_LLM_TIMEOUT:-15.0}"
DEEPSEEK_MODEL="${DEEPSEEK_MODEL:-deepseek-v4-flash}"
# Emergency operator kill switch. The normal path is safe now: streaming text
# stays in Fcitx preedit and FinishSession commits the corrected sentence once.
LLM_DISABLED="${BAOGU_LLM_DISABLED:-0}"
OUTPUT_MODE="${BAOGU_OUTPUT_MODE:-preedit}"
FINAL_ENABLED="${BAOGU_FINAL_ENABLED:-1}"
FINAL_BACKEND="${BAOGU_FINAL_BACKEND:-paraformer}"
FINAL_MAX_WAIT="${BAOGU_FINAL_MAX_WAIT:-1.2}"
FINAL_MAX_AUDIO="${BAOGU_FINAL_MAX_AUDIO_SEC:-10.0}"
PUNCTUATION_ENABLED="${BAOGU_PUNCTUATION_ENABLED:-1}"
RELEASE_GRACE="${BAOGU_RELEASE_GRACE_SEC:-3.0}"
CONTEXT_ENABLED="${BAOGU_CONTEXT_ENABLED:-1}"
LLM_MAX_WAIT="${BAOGU_LLM_MAX_WAIT:-$LLM_TIMEOUT}"
ASK_ENABLED="${BAOGU_ASK_ENABLED:-1}"
ASK_KEYCODE="${BAOGU_ASK_KEYCODE:-38}"
ASK_MODIFIER="${BAOGU_ASK_MODIFIER_KEYCODE:-64}"

cat > "$UNIT_DIR/baogu-ptt.service" <<EOF
[Unit]
Description=Baogu IME push-to-talk daemon
After=graphical-session.target
PartOf=graphical-session.target
# A login manager can start the user service before X11/Xwayland is ready.
# Never permanently give up because a graphical session took too long.
StartLimitIntervalSec=0

[Service]
Type=simple
WorkingDirectory=$ROOT
ExecStart=$ROOT/scripts/wait-for-x11.sh $ROOT/baogu-ptt
ExecStopPost=$ROOT/baogu-reset --keep-service
Restart=on-failure
RestartSec=1
Environment=PYTHONUNBUFFERED=1
Environment=BAOGU_ENGINE=sherpa
Environment=BAOGU_OUTPUT_MODE=$OUTPUT_MODE
Environment=BAOGU_FINAL_ENABLED=$FINAL_ENABLED
Environment=BAOGU_FINAL_BACKEND=$FINAL_BACKEND
Environment=BAOGU_FINAL_MAX_WAIT=$FINAL_MAX_WAIT
Environment=BAOGU_FINAL_MAX_AUDIO_SEC=$FINAL_MAX_AUDIO
Environment=BAOGU_PUNCTUATION_ENABLED=$PUNCTUATION_ENABLED
Environment=BAOGU_RELEASE_GRACE_SEC=$RELEASE_GRACE
Environment=BAOGU_LLM_ENABLED=$LLM_ENABLED
Environment=BAOGU_LLM_DISABLED=$LLM_DISABLED
Environment=BAOGU_LLM_MODE=$LLM_MODE
Environment=BAOGU_LLM_TIMEOUT=$LLM_TIMEOUT
Environment=BAOGU_LLM_MAX_WAIT=$LLM_MAX_WAIT
Environment=BAOGU_CONTEXT_ENABLED=$CONTEXT_ENABLED
Environment=BAOGU_ASK_ENABLED=$ASK_ENABLED
Environment=BAOGU_ASK_KEYCODE=$ASK_KEYCODE
Environment=BAOGU_ASK_MODIFIER_KEYCODE=$ASK_MODIFIER
Environment=DEEPSEEK_MODEL=$DEEPSEEK_MODEL

[Install]
WantedBy=default.target
EOF

cat > "$UNIT_DIR/baogu-overlay.service" <<EOF
[Unit]
Description=Baogu IME on-screen recording indicator
After=graphical-session.target baogu-ptt.service
PartOf=baogu-ptt.service
StartLimitIntervalSec=0

[Service]
Type=simple
WorkingDirectory=$ROOT
ExecStart=$ROOT/scripts/wait-for-x11.sh /usr/bin/python3 $ROOT/baogu-overlay
Restart=on-failure
RestartSec=1
Environment=PYTHONUNBUFFERED=1
Environment=DISPLAY=${DISPLAY:-:1}

[Install]
WantedBy=default.target
EOF

chmod +x "$ROOT/baogu-engine" "$ROOT/baogu-ptt" "$ROOT/baogu-reset" "$ROOT/baogu-mic" "$ROOT/baogu-aec" "$ROOT/baogu-overlay" "$ROOT/baogu-ask" "$ROOT/baogu-hotwords" "$ROOT/scripts/wait-for-x11.sh"
systemctl --user daemon-reload
systemctl --user enable baogu-ptt.service
systemctl --user enable baogu-overlay.service
# enable --now does not restart an already-running unit after Environment changes.
# restart both starts an inactive unit and refreshes an active one.
systemctl --user restart baogu-ptt.service
systemctl --user restart baogu-overlay.service
sleep 1
"$ROOT/baogu-status"
