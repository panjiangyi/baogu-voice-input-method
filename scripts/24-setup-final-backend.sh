#!/usr/bin/env bash
# Install an optional offline final backend model.
#
# Usage: bash scripts/24-setup-final-backend.sh [firered2-aed|firered2-ctc|funasr-nano|qwen3]
#
# The download is resumable: GitHub release transfers stall on a single stream
# on some hosts, so curl aborts a stalled transfer and continues where it
# stopped instead of restarting the whole archive.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
MODELS="$ROOT/models"
mkdir -p "$MODELS"

BACKEND="${1:-}"
case "$BACKEND" in
  firered2-aed)
    NAME="sherpa-onnx-fire-red-asr2-zh_en-int8-2026-02-26"
    REQUIRED=("encoder.int8.onnx" "decoder.int8.onnx" "tokens.txt")
    ;;
  firered2-ctc)
    NAME="sherpa-onnx-fire-red-asr2-ctc-zh_en-int8-2026-02-25"
    REQUIRED=("model.int8.onnx" "tokens.txt")
    ;;
  funasr-nano)
    NAME="sherpa-onnx-funasr-nano-int8-2025-12-30"
    REQUIRED=("encoder_adaptor.int8.onnx" "llm.int8.onnx" "embedding.int8.onnx"
              "Qwen3-0.6B/vocab.json" "Qwen3-0.6B/merges.txt" "Qwen3-0.6B/tokenizer.json")
    ;;
  qwen3)
    NAME="sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25"
    REQUIRED=("conv_frontend.onnx" "encoder.int8.onnx" "decoder.int8.onnx"
              "tokenizer/vocab.json" "tokenizer/merges.txt" "tokenizer/tokenizer_config.json")
    ;;
  *)
    echo "Usage: $0 [firered2-aed|firered2-ctc|funasr-nano|qwen3]" >&2
    exit 1
    ;;
esac

URL="https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/$NAME.tar.bz2"
DEST="$MODELS/$NAME"

complete_install() {
  local name
  for name in "${REQUIRED[@]}"; do
    [ -s "$DEST/$name" ] || return 1
  done
  return 0
}

if complete_install; then
  echo "$NAME is already installed; skipping download."
  exit 0
fi

echo "Downloading $NAME ..."
ARCHIVE="$(mktemp --suffix=.tar.bz2)"
trap 'rm -f "$ARCHIVE"' EXIT
curl -fL --retry 5 --retry-delay 3 --connect-timeout 20 \
  --speed-limit 20000 --speed-time 60 -C - \
  -o "$ARCHIVE" "$URL"

echo "Extracting..."
STAGE="$(mktemp -d "$MODELS/.final-backend.XXXXXX")"
trap 'rm -rf "$STAGE" "$ARCHIVE"' EXIT
tar -xjf "$ARCHIVE" -C "$STAGE"
[ -d "$STAGE/$NAME" ] || { echo "unexpected archive layout: $STAGE" >&2; exit 1; }
mkdir -p "$DEST"
cp -a "$STAGE/$NAME/." "$DEST/"
complete_install || { echo "extracted model is missing required files" >&2; exit 1; }
touch "$DEST/.complete"
echo "Installed $NAME. Set BAOGU_FINAL_BACKEND=$BACKEND to use it."
