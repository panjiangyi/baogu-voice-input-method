#!/usr/bin/env bash
set -u
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
UNIT="baogu-ptt.service"
LOCK="${XDG_RUNTIME_DIR:-/tmp}/baogu.lock"
COOKIE="${XDG_RUNTIME_DIR:-/tmp}/baogu-$(id -u).cookie"
STATE="${XDG_RUNTIME_DIR:-/tmp}/baogu-engine.state"
READY="${XDG_RUNTIME_DIR:-/tmp}/baogu-engine.ready"
CORRECTION_STATE="${XDG_RUNTIME_DIR:-/tmp}/baogu-correction.state"
ASK_REQUEST="${XDG_RUNTIME_DIR:-/tmp}/baogu-ask.request"
ASK_STATE="${XDG_RUNTIME_DIR:-/tmp}/baogu-ask.state"

export DISPLAY="${DISPLAY:-:1}"
export LD_LIBRARY_PATH="$ROOT/bin:${LD_LIBRARY_PATH:-}"
export PATH="$ROOT/bin:$PATH"

baogu_lock() { exec 9>"$LOCK"; flock -w 5 9 || exit 1; }
baogu_unlock() { exec 9>&-; }

baogu_engine_pids() {
  pgrep -u "$(id -u)" -f -- "^[^ ]*python[0-9.]* $ROOT/baogu-engine" 2>/dev/null || true
}
baogu_legacy_pids() {
  pgrep -u "$(id -u)" -f -- "^[^ ]*python[0-9.]* $ROOT/nerd-dictation/nerd-dictation begin" 2>/dev/null || true
}
baogu_pids() {
  { baogu_engine_pids; baogu_legacy_pids; } | awk 'NF && !seen[$0]++'
}

baogu_pid() {
  local pid
  pid="$(baogu_engine_pids | head -1)"
  if [ -n "$pid" ]; then echo "$pid"; return 0; fi
  pid="$(cat "$COOKIE" 2>/dev/null || true)"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  [ -d "/proc/$pid" ] || return 1
  echo "$pid"
}

baogu_state() {
  local pid state
  pid="$(baogu_pid)" || { echo none; return; }

  if [ -r "$STATE" ]; then
    state="$(tr -d '\r\n' < "$STATE" 2>/dev/null || true)"
    case "$state" in
      suspended|recording) echo "$state"; return ;;
    esac
  fi

  state="$(awk '{print $3}' "/proc/$pid/stat" 2>/dev/null)" || { echo none; return; }
  [ "$state" = T ] && echo suspended || echo starting
}

baogu_resume() {
  local pid; pid="$(baogu_pid)" || return 1
  if tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null | grep -q 'nerd-dictation'; then
    kill -CONT "$pid" 2>/dev/null || return 1
  else
    kill -USR2 "$pid" 2>/dev/null || return 1
  fi
}

baogu_suspend() {
  local pid; pid="$(baogu_pid)" || return 1
  kill -USR1 "$pid" 2>/dev/null || return 1
  for _ in $(seq 1 40); do
    [ "$(baogu_state)" != recording ] && return 0
    sleep 0.05
  done
  return 0
}

baogu_ensure_daemon() {
  case "$(baogu_state)" in suspended|recording) return 0 ;; esac
  systemctl --user start "$UNIT" >/dev/null 2>&1 ||     setsid "$ROOT/baogu-ptt" >/dev/null 2>&1 < /dev/null &
  for _ in $(seq 1 300); do
    case "$(baogu_state)" in suspended|recording) return 0 ;; esac
    sleep 0.1
  done
  return 1
}

baogu_kill_all() {
  local pid pids
  pids="$(baogu_pids)"
  for pid in $pids; do
    kill -TERM "$pid" 2>/dev/null || true
    kill -CONT "$pid" 2>/dev/null || true
  done
  sleep 0.2
  pids="$(baogu_pids)"
  [ -n "$pids" ] && kill -KILL $pids 2>/dev/null || true
  pkill -u "$(id -u)" -x parec 2>/dev/null || true
  rm -f "$COOKIE" "$STATE" "$READY" "$CORRECTION_STATE" "$ASK_REQUEST" "$ASK_STATE"
}
