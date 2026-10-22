<a id="english-version"></a>

**English** · [中文版 / Chinese version ↓](#chinese-version)

# Baogu IME (苞谷输入法) — Ubuntu Chinese & Mixed Chinese/English Voice Input

> **PR #6 recommended architecture**: Sherpa bilingual streaming Paraformer real-time preedit →
> offline Paraformer large fast final → deterministic glossary correction →
> local safe punctuation → optional DeepSeek correction → single Fcitx5 commit.

Targets **Ubuntu 24.04 + GNOME + Fcitx5**; the PTT hotkey listener currently focuses on X11.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Quick Reference](#quick-reference)
- [Recommended Install (daily path)](#recommended-install-daily-path)
- [Daily Use](#daily-use)
- [PR #6 Architecture](#pr-6-architecture-preedit--bounded-final)
- [Optional DeepSeek Correction](#optional-deepseek-correction)
- [Using an OpenAI-Compatible API](#using-an-openai-compatible-api)
- [Typeless-Inspired Dictation](#typeless-inspired-dictation)
- [Mixed Chinese/English Glossary](#mixed-chineseenglish-glossary)
  - [Customize Your Word Bank](#customize-your-word-bank)
- [Service & Troubleshooting](#service--troubleshooting)
- [Why Vosk Is No Longer the Default](#why-vosk-is-no-longer-the-default)
- [Evaluating with Real-Voice Recordings](#evaluating-with-real-voice-recordings)
- [Development & Testing](#development--testing)
- [Environment Requirements](#environment-requirements)
- [Legacy POC Reference](#legacy-poc-reference)
- [Known Issues](#known-issues)

---

## Getting Started

### 1. Check your system

- **Ubuntu 24.04 + GNOME on X11.** On the login screen choose **"Ubuntu on Xorg"**, then
  confirm with `echo $XDG_SESSION_TYPE` (it should print `x11`). Wayland is not supported yet.
- **Fcitx5 as your input-method framework.** If you are still on IBus:

  ```bash
  sudo apt-get install -y fcitx5
  im-config -n fcitx5     # then log out and log back in
  ```

- A working microphone (USB mics work best).
- Run everything as your normal user, **not root**. The installer asks for your sudo
  password only when system packages are missing.

### 2. Clone and deploy

```bash
git clone https://github.com/panjiangyi/baogu-voice-input-method.git
cd baogu-voice-input-method
./deploy.sh
```

`deploy.sh` is the one command you need. It:

1. installs any missing apt packages and the `sherpa-onnx` Python runtime;
2. downloads the speech models into `models/` (first run only);
3. builds and installs the Fcitx5 addon, then restarts Fcitx5;
4. installs and starts the `baogu-ptt` and `baogu-overlay` user services.

During the run it asks **"Enable DeepSeek correction after each utterance? [y/N]"**. Answer
`N` for a fully local setup. You can turn AI correction on later; see
[Optional DeepSeek Correction](#optional-deepseek-correction) or
[Using an OpenAI-Compatible API](#using-an-openai-compatible-api).

If deploy prints `WARNING: final quality models are incomplete`, run
`bash scripts/11-setup-quality.sh` once, then run `./deploy.sh` again.

### 3. Verify and dictate

```bash
./baogu-status        # "state: suspended" means idle and ready
```

Click into any text field, **hold right Alt**, speak, and **release**. Text appears live
while you talk and is committed when you let go.

### 4. Update

```bash
git pull && ./deploy.sh
```

Deploy is idempotent: anything already installed or downloaded is skipped.

---

## Quick Reference

### Hotkeys

| Action | Behavior |
|---|---|
| **Hold right Alt** | Record + stream preedit in real time; **release** to finalize and commit |
| Ctrl + Alt + V | Hands-free toggle: press once to start, again to stop |
| Ctrl + Alt + B | End current dictation and commit |
| Ctrl + Shift + F9 | Toggle DeepSeek auto-correction (state is persisted) |
| **Hold Alt + A** (left Alt) | Ask a spoken question about the mouse-selected text; the AI answer opens in its own window. Say nothing and it explains the selection (or clipboard) instead |
| **Alt + W** (left Alt) | Add the selected text (else the clipboard) to your personal hotword list, with a desktop confirmation |

### CLI / Service

```bash
./baogu-status         # Daemon / dictation status / current microphone
./baogu-reset          # Force-clean engine and recorder on abnormal state
./baogu-hotwords ...   # Personal hotword add / list / remove

journalctl --user -u baogu-ptt        -f   # PTT daemon
journalctl --user -u baogu-engine     -f   # Default DeepSeek-path engine log
journalctl --user -u baogu-corrector  -f   # Legacy FireRed + local corrector only
```

### Key Environment Variables

| Variable | Purpose |
|---|---|
| `BAOGU_LLM_ENABLED` | 1 = enable DeepSeek post-processing; 0 = disabled |
| `BAOGU_LLM_MODE` | `aggressive` (default) / `punctuation` / `dictation` |
| `BAOGU_LLM_TIMEOUT` | Cloud-correction request timeout (seconds) |
| `BAOGU_LLM_MAX_WAIT` | Total time final commit waits for cloud correction (seconds) |
| `DEEPSEEK_MODEL` | Model ID; default `deepseek-v4-flash` (set at deploy time) |
| `DEEPSEEK_BASE_URL` / `DEEPSEEK_API_KEY` | AI correction endpoint and key, in `.env` (any provider, despite the name) |
| `BAOGU_LLM_API` | `anthropic` (default, `/v1/messages`) or `openai` (`/chat/completions`) |
| `BAOGU_CORRECTOR_ZEN_MODEL` / `_REASONING` | Switch model / reasoning tier (low/medium/high/xhigh) |
| `BAOGU_RELEASE_GRACE_SEC` | Trailing-sound wait after key release (default 0.25, capped at 3s, 0 = stop immediately) |
| `BAOGU_CONTEXT_ENABLED` | 0 = disable app name / surrounding-text context |
| `BAOGU_PTT_KEYCODE` | Override PTT physical keycode (default right Alt = 108) |
| `BAOGU_ASK_ENABLED` | 1 (default) = enable selection question with Alt + A |
| `BAOGU_ASK_KEYCODE` / `BAOGU_ASK_MODIFIER_KEYCODE` | Ask hotkey keycodes (default 38 = `a`, 64 = left Alt) |
| `BAOGU_ASK_MAX_TOKENS` | Answer length budget for the selection question (default 2048) |
| `BAOGU_HOTWORD_ENABLED` | 1 (default) = enable the one-key hotword teach with Alt + W |
| `BAOGU_HOTWORD_KEYCODE` / `BAOGU_HOTWORD_MODIFIER_KEYCODE` | Hotword hotkey keycodes (default 25 = `w`, 64 = left Alt; keycodes come from the X keymap, which may not match the PC105 reference — check with `xmodmap -pke`) |
| `BAOGU_HOTWORD_MAX_CHARS` | Longest selection accepted as one hotword (default 80) |

Secrets are read only from the project root `.env` (mode 600).

---

## Recommended Install (daily path)

For first-time install and routine updates, just run:

```bash
./deploy.sh
```

The script checks system packages, the Python runtime, and the streaming/final/punctuation models
and only installs what is missing; already-installed dependencies are not re-installed or
re-downloaded. A first install may prompt for the sudo password.

The script does not enable DeepSeek correction by default. During interactive deploy, choosing
`y` will prompt for mode (default `aggressive`), model and timeout; deploy sends a fixed test
sentence against the API and does not refresh service config if the test fails.

### Non-Interactive Configuration

For CI or scripted scenarios, the same configuration is available through environment variables:

- `aggressive`: allows fixing typos and English words; the default when enabled. May change
  meaning.
- `punctuation`: only adjusts punctuation and CJK/Latin spacing; does not fix misrecognized
  words.
- `dictation`: cleans up meaningless filler, repetition, and verbal self-corrections during
  cloud correction (see below).

```bash
# 1. Fcitx5 native bridge
sudo apt-get install -y g++ libfcitx5core-dev libfcitx5utils-dev libfcitx5config-dev
bash native/build.sh
bash native/install.sh
fcitx5 -r

# 2. One-shot install of the full production ASR stack:
#    streaming Paraformer + offline final Paraformer + local punctuation model
bash scripts/09-setup-sherpa.sh

# 3. Optional DeepSeek post-processing
echo 'DEEPSEEK_API_KEY=...'      >  .env
echo 'DEEPSEEK_BASE_URL=https://api.deepseek.com/anthropic' >> .env
echo 'DEEPSEEK_MODEL=deepseek-v4-flash'                    >> .env
chmod 600 .env
# Choose y during deploy, or set BAOGU_LLM_ENABLED=1

# 4. Install and start user-level systemd services
bash scripts/10-install-service.sh

# 5. Check
./baogu-status
```

> **`baogu-engine` calls DeepSeek's Anthropic-compatible API directly, with thinking
> explicitly disabled**; no OpenCode, cc-switch, or local corrector service is required. The
> legacy path (FireRedASR2 + local corrector service) is only used when `BAOGU_OUTPUT_MODE`
> is set to something other than `preedit` AND `BAOGU_LLM_ENABLED=1`.

---

## Daily Use

### Full flow of a single dictation

1. **Hold right Alt** and start speaking. Real-time recognition results show as Fcitx preedit
   and do **not** modify application text yet.
2. **Release right Alt**:
   - The recording waveform closes immediately and shows "识别优化中" / "Optimizing".
   - If the audio is still close to recent speech volume, trailing audio is captured; the
     recorder stops after about 0.25s of continuous silence, capped at 3s of total extension
     (configurable via `BAOGU_RELEASE_GRACE_SEC`; 0 stops immediately).
   - Then wait up to 1.2s for the offline Paraformer final, followed by glossary normalization
     and local safe punctuation.
   - If DeepSeek is enabled, "纠错中" / "Correcting" is shown while waiting (default up to
     15s), then a single commit happens and the engine returns to idle.
3. Pressing the key again during wrap-up ends the current sentence early and starts the next.
4. Fallback to streaming-only triggers: sentences longer than 10s, final timeout, or the
   previous final still running.

### On-screen indicators

- While recording, a live waveform is shown centered below the current active display.
- AI post-processing shows "纠错中" / "Correcting"; on completion a brief "纠错完成" /
  "Done", "纠错失败" / "Failed", "纠错超时" / "Timeout", "纠错已开启" / "On", or
  "纠错已关闭" / "Off" appears.
- The indicator window **does not grab keyboard focus**.

### Legacy mode

Setting `BAOGU_OUTPUT_MODE` to anything other than `preedit` still keeps the
FireRedASR2 + LLM legacy rewrite path, but it is off by default. It requires explicitly
setting `BAOGU_LLM_ENABLED=1`. The `punctuation` safe mode only accepts
punctuation/spacing changes; content-word changes are rejected and the ASR original is
kept. If the API call fails, a trailing full stop is still appended.

---

## PR #6 Architecture: preedit + bounded final

The old implementation wrote streaming partials directly into the application text and then
backspaced/surrounding-text overwrote it with the final/LLM output. Different GTK, Qt,
Electron, and terminal apps behaved inconsistently under late rewrites, and we saw
"old text not removed, new text appended" cases.

PR #6 changes it to:

```text
Real-time streaming Paraformer
        ↓
Fcitx preedit (preview only, never into app text)
        ↓ on key release
Offline Paraformer large (wait at most 1.2s)
        ↓
Deterministic glossary correction
        ↓
Local punctuation model + semantic guard
        ↓
Single CommitString
```

### Protection rules

- **Final takes more than 1.2s**: immediately fall back to streaming.
- **Speech longer than 10s**: do not start the offline final.
- **At most one final inference at a time**; no queueing.
- **Next PTT has already started**: stop waiting for the previous final.
- **Focus / input field / session changes**: final commit fails closed.
- **Final/punctuation model missing**: streaming fallback still works normally.

---

## Optional DeepSeek Correction

DeepSeek runs right before the preedit final commit, via `baogu-engine` → DeepSeek's
Anthropic-compatible API (thinking disabled).

### Three modes

| Mode | Behavior | When to use |
|---|---|---|
| `punctuation` | Only adjusts punctuation and CJK/Latin spacing; no word correction | Safe default; want "the most conservative polish" |
| `aggressive` (default) | Fixes typos and English content words | Most everyday scenarios; may lightly rephrase |
| `dictation` | Cleans meaningless filler, repetition, and explicit verbal self-corrections; requires keeping tone and meaning | Long dictation, draft writing |

> Detailed evidence, trade-offs, and verification scope live in
> [docs/typeless-research.md](docs/typeless-research.md).

### Context assistance

Enabled by default. The cloud corrector receives the **current app name** and **up to 500
Unicode characters before and after the input position**:

- Only the current Fcitx session is queried; no other windows.
- No selected-text content is included.
- Passwords and sensitive input fields do not provide context.
- If the app does not support surrounding-text or the native plugin has not been upgraded
  yet, a context-less correction is used automatically.
- Set `BAOGU_CONTEXT_ENABLED=0` to disable.
- **When cloud correction is enabled**, this surrounding text is sent together with the
  current dictation to the configured DeepSeek endpoint; it is not sent when disabled.

### Timeout and concurrency

`BAOGU_LLM_MAX_WAIT` sets the total time the final commit waits for cloud correction
(seconds; default follows `BAOGU_LLM_TIMEOUT`). On timeout or a new PTT press, the local
candidate is kept immediately; late results never overwrite committed text. Underlying HTTP
requests may still run until the network timeout, during which subsequent sentences skip
the cloud and **do not pile up requests**. Local recognition continues working. Long-sentence
output budget grows with length; the server explicitly reports output truncation, in which
case the full original is kept.

### Deploy example

```bash
# Enable dictation cleanup, limit cloud wait to 3 seconds
BAOGU_LLM_ENABLED=1 BAOGU_LLM_MODE=dictation \
BAOGU_LLM_MAX_WAIT=3 ./deploy.sh
```

During interactive deploy, choose `3) dictation`.

---

## Using an OpenAI-Compatible API

AI correction talks to DeepSeek's Anthropic-compatible endpoint by default. It can use **any
provider that speaks the OpenAI Chat Completions API** instead: OpenAI, DeepSeek (OpenAI
format), OpenRouter, SiliconFlow, Alibaba DashScope, or a local Ollama / vLLM / LM Studio
server.

### 1. Put the endpoint in `.env`

Create or edit `.env` in the project root:

```bash
BAOGU_LLM_API=openai
DEEPSEEK_BASE_URL=https://api.openai.com/v1
DEEPSEEK_API_KEY=sk-your-key
```

```bash
chmod 600 .env
```

- The variables keep their historical `DEEPSEEK_` prefix but work for **any provider**.
- `DEEPSEEK_BASE_URL` is everything **before** `/chat/completions`. Baogu IME appends
  `/chat/completions` itself, so do not include it.
- The key is sent as `Authorization: Bearer <key>`. Local servers that ignore keys still
  need a non-empty placeholder such as `DEEPSEEK_API_KEY=local`.

Common base URLs:

| Provider | `DEEPSEEK_BASE_URL` |
|---|---|
| OpenAI | `https://api.openai.com/v1` |
| DeepSeek (OpenAI format) | `https://api.deepseek.com/v1` |
| OpenRouter | `https://openrouter.ai/api/v1` |
| SiliconFlow | `https://api.siliconflow.cn/v1` |
| Alibaba DashScope | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| Ollama (local) | `http://localhost:11434/v1` |

### 2. Choose the model and enable correction at deploy time

The model ID is written into the systemd service by `deploy.sh`, so set it there, **not** in
`.env`:

```bash
BAOGU_LLM_ENABLED=1 DEEPSEEK_MODEL=<your-model-id> ./deploy.sh
```

Or run `./deploy.sh`, answer `y`, and type the model ID at the
`DeepSeek model [...]` prompt. Use the exact model ID from your provider's model list.

Deploy sends one fixed test sentence through the API. If that call fails, deploy stops and
the running service keeps its old configuration. Check the URL, key, and model, then run it
again.

### 3. Tips

- Pick a **fast, non-reasoning** chat model. Every sentence waits for the reply, at most
  `BAOGU_LLM_MAX_WAIT` seconds, before it is committed. Slow models just time out, and the
  local text is used instead.
- Modes (`punctuation` / `aggressive` / `dictation`), context assistance, and the
  `Ctrl + Shift + F9` toggle behave the same with every provider.
- To switch back to DeepSeek's default endpoint, delete the `BAOGU_LLM_API` line (or set
  it to `anthropic`) and restore
  `DEEPSEEK_BASE_URL=https://api.deepseek.com/anthropic`, then run `./deploy.sh` again.
- Privacy: when correction is on, the dictated sentence, your personal hotwords, and (unless
  `BAOGU_CONTEXT_ENABLED=0`) up to 500 characters of surrounding text are sent to the
  provider you configure.

---

## Typeless-Inspired Dictation

`BAOGU_LLM_MODE=dictation` cleans meaningless filler, repetition, and explicit verbal
self-corrections during cloud correction while requiring the tone and meaning to be preserved.
This mode permits rewrites; the result still needs real-voice acceptance. The existing
`punctuation` / `aggressive` modes remain available. Full evidence chain in
[docs/typeless-research.md](docs/typeless-research.md).

Two safeguards come with it:

- **Profanity is never cleaned up.** The `dictation` and `rewrite` prompts require the
  speaker's profanity and crude wording to be preserved verbatim, never replaced with
  a softened phrase.
- **Every polish is compared with the original.** When the polished text differs from the
  raw ASR text, one short reviewer call picks between them. If the reviewer chooses the
  original — or that call fails, times out, or answers ambiguously — the raw transcription
  is kept and the status becomes `kept-original`.

---

## Mixed Chinese/English Glossary

No replacement of the current Paraformer and no change to the Chinese recognition pipeline.
Every streaming partial/final result is run through a single English glossary normalization
step before display; Chinese characters are never rewritten by the glossary.

### Built-in glossary coverage

- Frontend, backend, DevOps, Git/GitHub, database, and AI common terms;
- Stripe, Linear, Vercel, AWS;
- Henry Schein, Darby Dental, DC Dental, Patterson Dental, Benco Dental, and other dental
  suppliers / brands.

Full glossary files live in `hotwords/`: `aliases.tsv` / `compiled.txt` /
`contextual-aliases.tsv` / `dental.txt` / `priority.txt` / `programming.txt` /
`work-tools.txt`.

### Customize Your Word Bank

There are three layers. Pick the one that matches the problem:

| You want to… | Edit | Format |
|---|---|---|
| Teach a term and its correct spelling (brand, project, code name) | `~/.config/baogu/hotwords.txt` | one term per line |
| Fix one specific English mishearing everywhere | `hotwords/aliases.tsv` | `misheard<TAB>correct` |
| Fix a mishearing that is only wrong in a certain context | `hotwords/contextual-aliases.tsv` | `misheard<TAB>correct<TAB>ctx1\|ctx2` |

All three are reloaded **at the start of every dictation**. You don't need to restart
anything.

#### 1. Personal terms (start here)

```bash
./baogu-hotwords add "MyProject" "Customer Brand" "New Dental Product"
./baogu-hotwords list
./baogu-hotwords remove "MyProject"
./baogu-hotwords path      # print the file location
```

Or do it from the keyboard: select the term you keep having to spell, press **Alt + W**
(left Alt), and a notification confirms the addition. The glossary is rebuilt and picked
up on the next utterance, with no service restart.

The list lives in `~/.config/baogu/hotwords.txt` (UTF-8, one term per line; blank lines
and `#` comments are ignored). You can also edit the file directly. Your personal terms:

- are used **locally** to repair the spelling, case, and spacing of English / ASCII terms
  (for example `get hub` → `GitHub`);
- are sent to the AI corrector, when it is enabled, as a vocabulary hint (the first 128
  terms). This is the only way Chinese terms help, because the local glossary never rewrites
  Chinese characters.

Add proper nouns, product names, and identifiers. Don't add ordinary English words; they
bias the corrector toward false matches.

#### 2. Mishearing → correct term

When the recognizer keeps producing the same wrong English phrase, map it in
`hotwords/aliases.tsv`. Separate the two columns with a **real tab character**:

```tsv
Henry Shine	Henry Schein
Dabby Dental	Darby Dental
```

Matching ignores case, spaces, and punctuation, and must cover the whole phrase. It only
applies to English / ASCII text.

#### 3. Context-guarded replacements

Some English names come out as ordinary Chinese words (for example "Linear" → `力量`).
Replacing those everywhere would damage normal Chinese. `hotwords/contextual-aliases.tsv`
replaces them only when one of the listed context words appears nearby:

```tsv
力量	Linear	ticket|issue|sprint|cycle|backlog|workspace
```

Columns: exact misrecognized text, correct term, then trigger words separated by `|` or `,`.
Only add artifacts you have actually seen in your own dictation.

> `hotwords/*.tsv` and the built-in `*.txt` lists are tracked in git. If you edit them,
> commit the changes to your fork so `git pull` doesn't conflict. Your personal
> `~/.config/baogu/hotwords.txt` is outside the repo and never conflicts.

> The word bank fixes spelling and wording **after** recognition. It cannot make the
> acoustic model hear a word it never recognized.

### DeepSeek toggle

`Ctrl + Shift + F9` toggles DeepSeek auto-correction; the screen shows on/off indicators.
State is saved to `~/.config/baogu/deepseek-enabled.txt` (`1` on, `0` off), preserved
across restarts. When off, subsequent correction requests skip the cloud; requests already
in flight still wait to finish. **Local recognition, glossary, and punctuation keep working**.
The hotkey uses the current X11 global keyboard listener.

---

## Service & Troubleshooting

```bash
# Daemon / dictation status / current microphone
./baogu-status

# Force-stop everything on abnormal state
./baogu-reset

# Live logs
journalctl --user -u baogu-ptt        -f   # PTT daemon
journalctl --user -u baogu-engine     -f   # Default DeepSeek-path engine log
journalctl --user -u baogu-corrector  -f   # Legacy FireRed + local corrector only
```

`baogu-ptt.service` auto-starts with the graphical session and auto-restarts on abnormal
exit.

---

## Why Vosk Is No Longer the Default

Three issues observed in real use — long-session freezing, poor mixed Chinese/English
input, low Chinese accuracy — all trace to the old main pipeline. The new pipeline makes
these changes:

1. **Vosk small-cn → Sherpa streaming Paraformer (bilingual)** to fix the lack of
   foundational Chinese and code-switch capability.
2. **Optional FireRedASR2 second-pass correction**: streaming handles speed, post-release
   offline CTC handles accuracy.
3. **No more spawning a `busctl` subprocess for every partial**: prefer one persistent
   Gio D-Bus connection straight to Fcitx5.
4. **PTT supervisor with timeout recovery**: if final recognition is not back to idle
   within 4s, the engine is restarted directly, instead of letting the whole IME freeze
   permanently.
5. **Independent ASR stream / recorder per dictation**: one anomaly cannot poison the
   next dictation.

Historical POC-stage issues — Vosk small recognition quality, xdotool wrapper scripts, POC
compatibility — no longer apply after the switch to Sherpa streaming + Fcitx5 native
bridge; detailed data is preserved in `POC-REPORT.md`.

---

## Evaluating with Real-Voice Recordings

The manifest produced by `scripts/14-record-samples.sh` can be fed straight into the current
recognition pipeline. Evaluation reports content, raw-format, English-word, number, and
punctuation accuracy, and writes per-sentence results to TSV:

```bash
python3 scripts/08-offline-suite.py \
  --manifest samples/voice-input-session-20260921-211507/manifest.tsv
```

The default is the daily path (Sherpa streaming). To test FireRed, temporarily add
`BAOGU_FINAL_ENABLED=1`; **do not enable it by default just because the model is already
downloaded**. For the current batch of 30 real-voice recordings, streaming content accuracy
is 90.66% and FireRed is 82.71%. This batch participated in tuning, so it can only act as a
**development set**; final accuracy needs an additional sample set that did not participate
in tuning.

### Acceptance metrics

Going forward, the acceptance metrics are: first-character latency, final-correction
latency, Chinese CER, Chinese/English code-switch WER, and 100-continuous-PTT no-freeze
rate. Whether we reach "Doubao IME 80%" must be A/B benchmarked on the same batch of
real-voice recordings, not based only on subjective description.

---

## Development & Testing

### Directory structure

```
baogu-voice-input-method/
├── deploy.sh                   # Daily rebuild + start script
├── baogu-ptt / -engine / -corrector   # User-level service entrypoints
├── baogu-lib.sh             # Shared shell library (single-instance lock, signal I/O, state query)
├── baogu_glossary.py        # Glossary deterministic correction
├── baogu_settings.py        # Settings and persistence
├── native/                     # Fcitx5 native bridge (C++)
│   ├── baogu.cpp
│   ├── build.sh
│   └── install.sh
├── hotwords/                   # Built-in glossary (TSV)
├── scripts/                    # Numbered scripts 00–21 + lib.sh
│   ├── 00-user-test.sh          # One-click real-voice evaluation
│   ├── 09-setup-sherpa.sh       # Full production ASR stack
│   ├── 10-install-service.sh    # User-level systemd service
│   ├── 12-setup-corrector.sh / 13-…   # Legacy path
│   ├── 14-record-samples.sh     # Real-voice manifest
│   └── 20-build-glossary.sh     # Glossary compile
├── tests/                      # Unit and regression (no recording, no typing)
│   └── python -m unittest discover -s tests -v
├── docs/                       # Research, evaluation, landing
│   └── typeless-research.md
├── nerd-dictation/             # Upstream project (still usable as manual nerddictation path)
├── models/                     # Default ASR model directory
├── POC-REPORT.md               # POC v0.1 complete record
└── README.md                   # This file
```

### Unit and regression

```bash
python3 -m unittest discover -s tests -v   # No recording, no typing into the desktop
```

Coverage: native bridge (`tests/native_bridge.py`), glossary, engine logic, bounded
cleanup, LLM correction, settings, etc.

### Latency and compatibility

Historical results live in `logs/latency_results_*.tsv` and `logs/app_compat_*.tsv`. The
latency log only records character counts, not recognized content; use
`journalctl --user -u baogu-ptt` to inspect.

---

## Environment Requirements

- **OS**: Ubuntu 24.04 LTS (GNOME)
- **Display protocol**: X11 (Wayland would need ydotool and similar root services; the
  project currently scopes to X11)
- **Input framework**: Fcitx5 (with `libfcitx5core-dev` / `libfcitx5utils-dev` /
  `libfcitx5config-dev`)
- **Build tools**: `g++`, `make`
- **Python**: 3.10+, with `vosk` / `sherpa-onnx` / `sounddevice` via `pip`
- **Audio**: PipeWire or PulseAudio; default sample rate 16 kHz
- **Microphone**: USB input preferred; re-resolved on every key press (`baogu-mic`)

### Models

| Model | Role | Size |
|---|---|---|
| streaming Paraformer (Sherpa, bilingual) | Real-time partial → preedit | Smaller, resident in memory |
| offline Paraformer large | Post-release final → commit | Larger, loaded on demand |
| Local punctuation model | Deterministic punctuation after final | Smaller |
| FireRedASR2 (legacy) | Optional final second-pass correction | Larger |
| DeepSeek `deepseek-v4-flash` | Optional cloud post-processing | Cloud, no local resource |

---

## Legacy POC Reference

> Codename: Baogu IME POC ｜ Version v0.1 ｜ Status: in progress
> Full conclusions in [`POC-REPORT.md`](POC-REPORT.md) (conclusion B: POC partially passed;
> finish real-voice verification before further development).

### Core goal

On Ubuntu, verify: **user focuses any input field → speaks Chinese → recognized text goes
directly into the current input field without copy-paste**.

### POC environment

| Item | Value |
|---|---|
| OS | Ubuntu 24.04.4 LTS |
| Desktop | GNOME (ubuntu) |
| Display protocol | X11 (`DISPLAY=:1`) |
| Old POC input tool | xdotool |
| ASR | Vosk (Python API) |
| Model | `vosk-model-small-cn-0.22` |
| Sample rate | 16000 Hz |

### Manual nerd-dictation path (still usable)

```bash
./nerd-dictation/nerd-dictation begin \
    --vosk-model-dir models/vosk-model-small-cn-0.22 \
    --sample-rate 16000 \
    --defer-output

# Speak...

./nerd-dictation/nerd-dictation end
```

- The `end` command touches a cookie file; the background `begin` process detects it and
  runs the final recognition and commits text.
- `--defer-output`: does not commit while speaking; one-shot input at the end.
- `cancel` discards the recording.
- xdotool is based on XTEST, **X11 only**.

### Daemon design notes

- **Only one nerd-dictation process at a time**. `begin` writes the PID into a public
  cookie; a second invocation overwrites it, leaving the first instance orphaned. Pressing
  the hotkey N times leaves N instances (each ~260MB, each grabbing a microphone). The
  process is therefore owned by the `baogu-ptt` daemon and switched via signals:
  - `SIGCONT`: start recording (spawn `parec`)
  - `SIGUSR1`: flush text → close `parec` → process self-`SIGSTOP`
- When idle the process is in `T` (stopped) state: **0% CPU, no microphone**, model stays
  in memory, ~100ms to record on key press.
- **Key source**: `xinput test-xi2 --root` (GNOME's own shortcut only emits key-down and
  cannot bind a single modifier). Right Alt = keycode 108; use `BAOGU_PTT_KEYCODE` to
  override for a different layout. Auto-repeated key-down events are ignored.
- **Ignore XTEST-synthesized key events**: `xdotool --clearmodifiers` during commit emits
  modifier release/restore events that should not be treated as real PTT. Backspace clears
  modifiers to avoid becoming Alt+BackSpace and similar app shortcuts.
- **Read buffered audio promptly**: read all currently available data per round, keep
  fragments shorter than a full PCM sample. Daily service checks every 20ms.
- **Re-resolve the microphone on every key press** (`baogu-mic`): prefer the current
  default input (if USB) → any USB input → current default → any input.
- **Independent state files**: daily service uses `$XDG_RUNTIME_DIR/baogu-<uid>.cookie`,
  isolated from the default cookie used by manual testing.

> Right Alt is still a normal Alt key; while held, other programs also see it as Alt. If you
> do not want this side effect, remap it: `xmodmap -e 'keycode 108 = VoidSymbol'` (xinput reads
> the pre-mapping keycode, so PTT is unaffected).

---

## Known Issues

1. **GNOME/mutter programmatic focus is unstable**: automated tests need a `windowactivate`
   + click combination; real-user scenarios are unaffected because the user focuses manually.
2. **Acoustic loopback (speaker → mic) degrades quality**: loopback tests recognize worse
   than real voice; **real-voice tests are authoritative**.
3. **X11 global keyboard listener**: both PTT and `Ctrl+Shift+F9` listen via
   `xinput test-xi2 --root`; Wayland would need ydotool and similar root services. The
   project currently scopes to X11.
4. **2026-09-08 POC fix verification**: in an isolated X11 desktop, replaying 16kHz
   recordings with real Vosk and xdotool three times in a row, the first text segment
   appeared in about 1 second; Chinese backspace correction while Alt is held passed.
   **This does not replace real-voice acceptance on the current microphone.**
5. **Subsequent native input verification**: Fcitx5 + GTK4 three consecutive real-time
   recognition commits passed; first text segment appeared in about 1 second; VTE / Bash
   terminal Chinese input and correction while Alt is held passed. Native interface tests
   also covered focus loss and the rejection of deleting text from before the current
   dictation; source in `tests/native_bridge.py`.

---

<a id="chinese-version"></a>

[English version ↑](#english-version) · **中文**

# 苞谷输入法 — Ubuntu 中文 / 中英混合语音输入

> **PR #6 推荐架构**：Sherpa 双语 streaming Paraformer 实时 preedit →
> offline Paraformer large 快速 final → 领域词库确定性纠正 →
> 本地安全标点 → 可选 DeepSeek 纠错 → Fcitx5 一次性 commit。

适用于 **Ubuntu 24.04 + GNOME + Fcitx5**；PTT 热键监听当前以 X11 为主。

---

## 目录

- [快速上手](#快速上手)
- [快速参考](#快速参考)
- [推荐安装（日用路径）](#推荐安装日用路径)
- [日常使用](#日常使用)
- [PR #6 架构](#pr-6-架构preedit--bounded-final)
- [可选 DeepSeek 纠错](#可选-deepseek-纠错)
- [接入 OpenAI 兼容 API](#接入-openai-兼容-api)
- [选中文字提问（Alt+A）](#选中文字提问alta)
- [借鉴 Typeless 的输入体验](#借鉴-typeless-的输入体验)
- [中英混输词库](#中英混输词库)
  - [自定义词库](#自定义词库)
- [服务与排错](#服务与排错)
- [为什么不再默认使用 Vosk](#为什么不再默认使用-vosk)
- [用真人录音评测](#用真人录音评测)
- [开发与测试](#开发与测试)
- [环境要求](#环境要求)
- [Legacy POC 资料](#legacy-poc-资料)
- [已知问题](#已知问题)

---

## 快速上手

### 1. 检查系统

- **Ubuntu 24.04 + GNOME，X11 会话。** 登录界面选择 **“Ubuntu on Xorg”**，再用
  `echo $XDG_SESSION_TYPE` 确认输出为 `x11`。暂不支持 Wayland。
- **输入法框架为 Fcitx5。** 如果还在用 IBus：

  ```bash
  sudo apt-get install -y fcitx5
  im-config -n fcitx5     # 然后注销并重新登录
  ```

- 一个能用的麦克风（推荐 USB 麦克风）。
- 用普通用户运行，**不要用 root**。只有缺少系统包时安装脚本才会要 sudo 密码。

### 2. 克隆并部署

```bash
git clone https://github.com/panjiangyi/baogu-voice-input-method.git
cd baogu-voice-input-method
./deploy.sh
```

只需要这一条命令。`deploy.sh` 会：

1. 安装缺少的 apt 包和 `sherpa-onnx` Python 运行时；
2. 把语音模型下载到 `models/`（仅首次）；
3. 编译并安装 Fcitx5 插件，然后重启 Fcitx5；
4. 安装并启动 `baogu-ptt` 和 `baogu-overlay` 两个用户级服务。

运行过程中会问 **“Enable DeepSeek correction after each utterance? [y/N]”**。想要完全本地
运行就答 `N`。之后随时可以开启 AI 纠错，见 [可选 DeepSeek 纠错](#可选-deepseek-纠错) 或
[接入 OpenAI 兼容 API](#接入-openai-兼容-api)。

如果部署提示 `WARNING: final quality models are incomplete`，先运行一次
`bash scripts/11-setup-quality.sh`，再重新运行 `./deploy.sh`。

### 3. 验证并开始听写

```bash
./baogu-status        # 显示 "state: suspended" 表示已就绪、处于待机
```

点进任意输入框，**按住右 Alt** 说话，**松开**即上屏。说话时文字实时显示，松键后一次性提交。

想针对某段文字提问：用鼠标**选中文字**，**按住左 Alt + A** 说话，松开后 AI 回答会弹出一个独立窗口。

详见「[选中文字提问](#选中文字提问alta)」。

### 4. 更新

```bash
git pull && ./deploy.sh
```

部署是幂等的：已安装、已下载的内容会自动跳过。

---

## 快速参考

### 热键

| 操作 | 行为 |
|---|---|
| **按住右 Alt** | 录音 + 边说边实时上屏（preedit）；**松开**结束并最终 commit |
| Ctrl + Alt + V | 免手持切换：按一下开始，再按一下停止 |
| Ctrl + Alt + B | 结束当前听写并上屏 |
| Ctrl + Shift + F9 | 切换 DeepSeek 自动纠错（状态持久化） |
| **按住 Alt + A**（左 Alt） | 用鼠标选中文字后，按住说话提问；松开后 AI 回答在独立窗口弹出。不说话则改为解释选区（或剪贴板）内容 |
| **Alt + W**（左 Alt） | 把选中的文字（没有选区就用剪贴板）一键加入个人热词，并弹通知确认 |

### CLI / 服务

```bash
./baogu-status         # 守护进程 / 听写状态 / 当前麦克风
./baogu-reset          # 异常时强制清理引擎和录音进程
./baogu-hotwords ...   # 个人热词 add / list / remove

journalctl --user -u baogu-ptt        -f   # PTT 守护进程
journalctl --user -u baogu-engine     -f   # 默认 DeepSeek 路径的引擎日志
journalctl --user -u baogu-corrector  -f   # 仅 legacy FireRed + 本地纠错服务
```

### 关键环境变量

| 变量 | 用途 |
|---|---|
| `BAOGU_LLM_ENABLED` | 1 = 启用 DeepSeek 后处理；0 = 关闭 |
| `BAOGU_LLM_MODE` | `aggressive`（默认）/ `punctuation` / `dictation` |
| `BAOGU_LLM_TIMEOUT` | 等待云端纠错的超时（秒） |
| `BAOGU_LLM_MAX_WAIT` | 最终提交等待云端纠错的总时间（秒） |
| `DEEPSEEK_MODEL` | 模型 ID，默认 `deepseek-v4-flash`（部署时设置） |
| `DEEPSEEK_BASE_URL` / `DEEPSEEK_API_KEY` | AI 纠错的地址和密钥，写在 `.env`（名字带 DeepSeek，但适用于任何服务商） |
| `BAOGU_LLM_API` | `anthropic`（默认，`/v1/messages`）或 `openai`（`/chat/completions`） |
| `BAOGU_CORRECTOR_ZEN_MODEL` / `_REASONING` | 换模型 / 推理档（low/medium/high/xhigh） |
| `BAOGU_RELEASE_GRACE_SEC` | 松键后尾音等待秒数（默认 0.25，封顶 3s，0 立即停） |
| `BAOGU_CONTEXT_ENABLED` | 0 = 关闭应用名 / surrounding-text 上下文 |
| `BAOGU_PTT_KEYCODE` | 覆盖 PTT 物理 keycode（默认右 Alt = 108） |
| `BAOGU_HOTWORD_ENABLED` | 1（默认）= 启用 Alt + W 一键加常用词 |
| `BAOGU_HOTWORD_KEYCODE` / `BAOGU_HOTWORD_MODIFIER_KEYCODE` | 常用词快捷键 keycode（默认 25 = `w`，64 = 左 Alt；keycode 取自 X keymap，未必等同 PC105 标准表，用 `xmodmap -pke` 查） |
| `BAOGU_HOTWORD_MAX_CHARS` | 单个热词接受的最长选区长度（默认 80） |

密钥只从项目根目录的 `.env` 读取（权限 600）。

---

## 推荐安装（日用路径）

首次安装和日常更新都直接运行：

```bash
./deploy.sh
```

脚本会检查系统包、Python 运行时以及 streaming/final/标点模型，只安装缺失项；
已安装的依赖不会重复安装或下载。首次安装可能需要输入 sudo 密码。

脚本默认不启用 DeepSeek 纠错。交互部署时选择 `y` 后会引导选择模式（默认 `aggressive`）、
模型和超时；部署时用固定测试句验证 API，失败则不刷新服务配置。

### 非交互配置

CI 或脚本场景可用环境变量提供同样配置：

- `aggressive`：允许修正错字和英文词，启用时的默认模式；可能改变原意。
- `punctuation`：只调整标点和中英文空格，不修正识别错词。
- `dictation`：在云端纠错时整理无意义口头语、重复和口头自我纠正（详见下文）。

```bash
# 1. Fcitx5 原生桥
sudo apt-get install -y g++ libfcitx5core-dev libfcitx5utils-dev libfcitx5config-dev
bash native/build.sh
bash native/install.sh
fcitx5 -r

# 2. 一次安装完整生产 ASR 栈：
#    streaming Paraformer + offline final Paraformer + 本地标点模型
bash scripts/09-setup-sherpa.sh

# 3. 可选 DeepSeek 后处理
echo 'DEEPSEEK_API_KEY=...'      >  .env
echo 'DEEPSEEK_BASE_URL=https://api.deepseek.com/anthropic' >> .env
echo 'DEEPSEEK_MODEL=deepseek-v4-flash'                    >> .env
chmod 600 .env
# 部署时选择 y，或设置 BAOGU_LLM_ENABLED=1

# 4. 安装并启动用户级 systemd 服务
bash scripts/10-install-service.sh

# 5. 检查
./baogu-status
```

> **`baogu-engine` 直接调用 DeepSeek 的 Anthropic 兼容接口，明确关闭 thinking**；
> 不需要 OpenCode、cc-switch 或本地纠错服务。Legacy 路径（FireRedASR2 + 本地纠错服务）
> 仅在 `BAOGU_OUTPUT_MODE` 设为非 `preedit` 且 `BAOGU_LLM_ENABLED=1` 时启用。

---

## 日常使用

### 一次听写的完整流程

1. **按住右 Alt** 开始说话。实时识别结果显示为 Fcitx preedit，**不修改应用正文**。
2. **松开右 Alt**：
   - 立即关闭录音声波，显示「识别优化中」。
   - 若仍有接近最近说话音量的声音，继续收取尾音；连续安静约 0.25 秒即停止，最多延长 3 秒（`BAOGU_RELEASE_GRACE_SEC` 可配置，设为 0 则立即停）。
   - 随后最多等待 1.2 秒的 offline Paraformer final，再应用词库规范化和本地安全标点。
   - 如启用 DeepSeek，还会显示「纠错中」并等待结果（默认最多 15 秒），最后只 commit 一次，引擎回到待机。
3. **收尾期间再次按键**会提前结束本句并开始下一句。
4. 触发回退（streaming 优先）的条件：长句超过 10 秒、final 超时、上一条 final 仍在运行。

### 屏幕提示

- 录音时在当前活动显示器下方居中显示动态声波。
- AI 后处理显示「纠错中」；结束短暂显示「纠错完成」「纠错失败」「纠错超时」「纠错已开启」「纠错已关闭」。
- 提示窗**不获取键盘焦点**。

### Legacy 模式

`BAOGU_OUTPUT_MODE` 设为 `preedit` 以外的值时仍保留 FireRedASR2 + LLM 旧重写路径，但默认关闭。
需要显式设 `BAOGU_LLM_ENABLED=1` 才会启用：`punctuation` 安全模式只接受标点/空格变化，
实词变化会被拒绝并保留 ASR 原文；API 失败时仍会补一个句末句号。

---

## PR #6 架构：preedit + bounded final

旧实现把 streaming partial 直接写入应用正文，final/LLM 再用 Backspace 或 surrounding-text
回删改写。不同 GTK、Qt、Electron、终端对 late rewrite 行为不一致，曾出现「旧文本没有删掉，
新文本又追加」的情况。

PR #6 改成：

```text
实时 streaming Paraformer
        ↓
Fcitx preedit（只是预览，不进应用正文）
        ↓ 松键
offline Paraformer large（最多等 1.2 秒）
        ↓
确定性 glossary correction
        ↓
本地 punctuation model + semantic guard
        ↓
一次 CommitString
```

### 保护规则

- **final 超过 1.2 秒**：立即回退 streaming；
- **语音超过 10 秒**：不启动 offline final；
- **同一时间最多一个 final inference**，不允许积压；
- **下一句 PTT 已经开始**：停止等待上一句 final；
- **焦点/输入框/session 改变**：最终提交 fail closed；
- **final/punctuation 模型缺失**：仍可正常使用 streaming fallback。

---

## 可选 DeepSeek 纠错

DeepSeek 在 preedit 最终提交前运行，路径为 `baogu-engine` → DeepSeek
Anthropic 兼容接口（thinking 已关闭）。

### 三种模式

| 模式 | 行为 | 何时用 |
|---|---|---|
| `punctuation` | 只调整标点和中英文空格，不修正错词 | 安全默认；想要「最保守的润色」 |
| `aggressive`（默认） | 修正错字和英文实词 | 大多数日常场景；可能轻微改写 |
| `dictation` | 整理无意义口头语、重复和口头自我纠正；要求保留语气和原意 | 长口述、稿件草稿 |

> 详细证据、取舍和验证范围见 [docs/typeless-research.md](docs/typeless-research.md)。

### 上下文辅助

默认开启，可为云端纠错提供**当前应用名**和**输入位置前后各最多 500 个 Unicode 字符**：

- 仅从当前 Fcitx 会话获取，不读取其他窗口；
- 不包含选区正文；
- 密码或 sensitive 输入框不提供上下文；
- 应用不支持 surrounding-text 或尚未升级原生插件时自动使用无上下文纠错；
- `BAOGU_CONTEXT_ENABLED=0` 关闭；
- **启用云端纠错时**，这部分文字会随当前口述文本发送到已配置的 DeepSeek 接口；关闭时不会发送。

### 超时与并发

`BAOGU_LLM_MAX_WAIT` 设置最终提交等待云端纠错的总时间（秒，默认沿用 `BAOGU_LLM_TIMEOUT`）。
超时或再次按下 PTT 时立即保留本地候选；迟到结果不会再改正文。底层 HTTP 请求可能仍运行
到网络超时，期间后续句子跳过云端，**不堆积请求**。本地识别继续工作。长句输出预算随长度
增长，服务端明确报告输出截断时保留完整原文。

### 部署示例

```bash
# 启用口语整理，将云端等待限制为 3 秒
BAOGU_LLM_ENABLED=1 BAOGU_LLM_MODE=dictation \
BAOGU_LLM_MAX_WAIT=3 ./deploy.sh
```

交互部署时选择 `3) dictation`。

---

## 接入 OpenAI 兼容 API

AI 纠错默认走 DeepSeek 的 Anthropic 兼容接口，也可以换成**任何支持 OpenAI Chat Completions
接口的服务**：OpenAI、DeepSeek（OpenAI 格式）、OpenRouter、硅基流动、阿里云百炼 DashScope，
或本地的 Ollama / vLLM / LM Studio。

### 1. 在 `.env` 中配置接口

在项目根目录创建或编辑 `.env`：

```bash
BAOGU_LLM_API=openai
DEEPSEEK_BASE_URL=https://api.openai.com/v1
DEEPSEEK_API_KEY=sk-your-key
```

```bash
chmod 600 .env
```

- 变量沿用历史上的 `DEEPSEEK_` 前缀，但**适用于任何服务商**。
- `DEEPSEEK_BASE_URL` 填 `/chat/completions` **之前**的部分。苞谷输入法会自己拼上
  `/chat/completions`，不要重复写。
- 密钥以 `Authorization: Bearer <key>` 发送。不校验密钥的本地服务也要填一个非空占位值，
  例如 `DEEPSEEK_API_KEY=local`。

常用 Base URL：

| 服务商 | `DEEPSEEK_BASE_URL` |
|---|---|
| OpenAI | `https://api.openai.com/v1` |
| DeepSeek（OpenAI 格式） | `https://api.deepseek.com/v1` |
| OpenRouter | `https://openrouter.ai/api/v1` |
| 硅基流动 SiliconFlow | `https://api.siliconflow.cn/v1` |
| 阿里云百炼 DashScope | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| Ollama（本地） | `http://localhost:11434/v1` |

### 2. 部署时选择模型并开启纠错

模型 ID 由 `deploy.sh` 写进 systemd 服务，所以要在部署时指定，**不要**写在 `.env` 里：

```bash
BAOGU_LLM_ENABLED=1 DEEPSEEK_MODEL=<你的模型ID> ./deploy.sh
```

也可以直接运行 `./deploy.sh`，答 `y`，然后在 `DeepSeek model [...]` 提示处输入模型 ID。
模型 ID 要和服务商模型列表里的写法完全一致。

部署时会用一条固定测试句调用一次 API。调用失败时部署会中止，正在运行的服务保持原配置。
检查 URL、密钥和模型后重新运行即可。

### 3. 提示

- 选**快速、非推理**的对话模型。每句话提交前都要等它返回，最多等 `BAOGU_LLM_MAX_WAIT`
  秒。模型太慢只会超时，然后直接用本地识别结果。
- 三种模式（`punctuation` / `aggressive` / `dictation`）、上下文辅助和 `Ctrl + Shift + F9`
  开关在任何服务商下表现一致。
- 想换回 DeepSeek 默认接口：删除 `BAOGU_LLM_API` 这一行（或设为 `anthropic`），把
  `DEEPSEEK_BASE_URL` 改回 `https://api.deepseek.com/anthropic`，再运行 `./deploy.sh`。
- 隐私：开启纠错后，当前这句话、你的个人热词，以及（除非设置 `BAOGU_CONTEXT_ENABLED=0`）
  光标前后最多 500 个字符会发送给你配置的服务商。

---

## 选中文字提问（Alt+A）

用鼠标**选中一段文字**，**按住左 Alt + A** 说出你的问题，**松开**后 AI 回答会在独立窗口弹出。
适合「这段什么意思」「帮我翻译」「总结一下」这类针对选中内容的提问。
仅在没有同时按住 Ctrl、Shift、Super 或右 Alt 等其他修饰键时触发，避免与其他快捷键冲突。

```text
鼠标选中文字
    ↓
按住左 Alt + A 提问（复用当前麦克风与本地流式识别）
    ↓
松开 → 本地识别出问题文字（不写进应用正文）
    ↓
选中文字 + 问题 → 已配置的 AI 接口
    ↓
独立窗口显示回答（可选中、可复制、Esc 关闭）

没说话时：
    ↓
选中文字（没有就用剪贴板）+ 固定的「解释这段内容」问题 → 同一个 AI 接口
```

### 不说话就直接解释

按了 Alt + A 却一句话没说，不算失败：你多半只是想搞懂手上这段文字。此时直接用固定
问题去问「选区（没有选区就用剪贴板）里这段内容」，英文单词或句子解释含义和用法，
其他语言就解释它在说什么。窗口标题显示「解释选区 / 剪贴板内容」。

如果既没有说话、选区和剪贴板也都是空的，窗口才会提示「没有听清问题，选区和剪贴板
也没有内容」。

### 为什么是左 Alt

右 Alt 是听写键，所以提问用**左 Alt**，两者互不干扰。`BAOGU_ASK_KEYCODE`
（默认 38 = `a`）和 `BAOGU_ASK_MODIFIER_KEYCODE`（默认 64 = 左 Alt）可以覆盖。

### 选中文字是怎么读到的

1. 先读 X11 的 **PRIMARY** 选区，也就是你刚用鼠标高亮的文字。GTK / Qt / 终端
   都支持，**不碰系统剪贴板**。
2. 如果该程序不导出 PRIMARY（少数 Electron 应用），回退到模拟 `Ctrl+C`：先保存
   剪贴板，复制后再还原，尽量不破坏你原来的剪贴板内容。
3. 剪贴板（CLIPBOARD）会在按键那一刻先读一份，只用于「没说话就解释」的兜底，
   以及 Alt + W 加热词时的后备来源。

选区文本不写进应用；提问识别结果也不会插入正文，只用于提问。

### 关于 AI 接口

- 复用「[接入 OpenAI 兼容 API](#接入-openai-兼容-api)」里配置的接口和 `.env` 密钥。
- 与纠错开关独立：即使关闭了自动纠错（`Ctrl + Shift + F9`），只要配好密钥，提问仍可用。
- `BAOGU_LLM_DISABLED=1` 会同时禁止纠错和提问。
- 回答长度预算用 `BAOGU_ASK_MAX_TOKENS`（默认 2048）。
- 隐私：**选中的文字和你说的问题会一起发送**给你配置的服务商。

### 窗口

- 弹出后不抢焦点；等回答好了才聚焦，方便直接复制。
- 回答可以选中复制，`Ctrl+C` 或「复制回答」按钮都行。
- `Esc` 或「关闭」隐藏窗口；下次按 Alt + A 复用同一个窗口。

### 限制

- 只能用左 Alt，右 Alt 留给听写。
- 有些应用既不导出 PRIMARY，又把 `Ctrl+C` 绑定成别的功能（个别终端要用
  `Ctrl+Shift+C`），这类应用可能读不到选区，此时窗口会提示「没有听清你的问题，请重试」。
- 密码框里的选中通常无法复制，属预期行为。
- `BAOGU_ASK_ENABLED=0` 可整体关闭这个功能。

---

## 借鉴 Typeless 的输入体验

`BAOGU_LLM_MODE=dictation` 在云端纠错时整理无意义口头语、重复和明确的口头自我纠正，
同时要求保留语气和原意。此模式允许改写，效果仍需真人录音验收；原有 `punctuation` /
`aggressive` 模式继续可用。完整证据链见 [docs/typeless-research.md](docs/typeless-research.md)。

两点额外的保险：

- **不净化脏话**：`dictation` 和 `rewrite` 提示词都明确要求逐字保留说话者的脏话和粗口，
  禁止用委婉说法替换。
- **润色后与原文对比**：只要润色结果和识别原文不同，就会再跑一次很短的评审调用，让模型
  在「原文 / 润色版」之间二选一。判给原文、或评审调用失败/超时/答非所问时，一律保留原始
  转写，状态记为 `kept-original`。也就是说多花一次小请求，换「润色后还不如原来」时能退回。

---

## 中英混输词库

不更换现有 Paraformer，也不改中文识别链路。当前 streaming ASR 的每次 partial/final 结果
只在上屏前经过一次英文词库规范化；中文字符不会被词库改写。

### 内置词库覆盖

- 前端、后端、DevOps、Git/GitHub、数据库、AI 常用词；
- Stripe、Linear、Vercel、AWS；
- Henry Schein、Darby Dental、DC Dental、Patterson Dental、Benco Dental 等牙科供应商/品牌。

完整词库文件在 `hotwords/`：`aliases.tsv` / `compiled.txt` / `contextual-aliases.tsv` /
`dental.txt` / `priority.txt` / `programming.txt` / `work-tools.txt`。

### 自定义词库

词库分三层，按问题选择：

| 你想要… | 编辑 | 格式 |
|---|---|---|
| 教它一个词和正确写法（品牌、项目名、代码标识符） | `~/.config/baogu/hotwords.txt` | 一行一个词 |
| 把某个固定的英文误识别全局改对 | `hotwords/aliases.tsv` | `误识别<TAB>正确写法` |
| 只在特定上下文里才算错的误识别 | `hotwords/contextual-aliases.tsv` | `误识别<TAB>正确写法<TAB>上下文1\|上下文2` |

三层都会在**每次听写开始时**重新加载，不需要重启任何东西。

#### 1. 个人热词（从这里开始）

```bash
./baogu-hotwords add "MyProject" "Customer Brand" "New Dental Product"
./baogu-hotwords list
./baogu-hotwords remove "MyProject"
./baogu-hotwords path      # 打印文件位置
```

也可以直接用键盘：选中那个老是要拼错的词，按 **Alt + W**（左 Alt），弹通知即已加入。
词库会重建，下次听写自动生效，不用重启服务。

词表保存在 `~/.config/baogu/hotwords.txt`（UTF-8，一行一个词，空行和 `#` 注释会被忽略），
也可以直接编辑这个文件。个人热词：

- 在**本地**用来修正英文 / ASCII 词的拼写、大小写和空格（例如 `get hub` → `GitHub`）；
- 开启 AI 纠错时，前 128 个词会作为词汇提示发给纠错模型。中文词只能通过这条路起作用，
  因为本地词库从不改写中文字符。

适合加专有名词、产品名和标识符。不要加普通英文单词，会让纠错误匹配。

#### 2. 误识别 → 正确写法

识别器总是把某个英文短语听成同一个错误写法时，在 `hotwords/aliases.tsv` 里加一条映射。
两列之间用**真正的 Tab 字符**分隔：

```tsv
Henry Shine	Henry Schein
Dabby Dental	Darby Dental
```

匹配时忽略大小写、空格和标点，且必须匹配整个短语。只作用于英文 / ASCII 文本。

#### 3. 带上下文保护的替换

有些英文名会被识别成普通中文词（例如 “Linear” → `力量`），全局替换会破坏正常中文。
`hotwords/contextual-aliases.tsv` 只在附近出现指定上下文词时才替换：

```tsv
力量	Linear	ticket|issue|sprint|cycle|backlog|workspace
```

三列依次为：误识别原文（精确匹配）、正确写法、触发词（用 `|` 或 `,` 分隔）。
只添加你在自己听写中真实遇到过的误识别。

> `hotwords/*.tsv` 和内置的 `*.txt` 词表都在 git 仓库里。修改后请提交到你自己的 fork，
> 避免 `git pull` 冲突。个人词表 `~/.config/baogu/hotwords.txt` 在仓库之外，不会冲突。

> 词库是在识别**之后**修正拼写和用词，无法让声学模型听出它根本没识别出的词。

### DeepSeek 切换

`Ctrl + Shift + F9` 切换 DeepSeek 自动纠错，屏幕显示开启/关闭提示。状态保存在
`~/.config/baogu/deepseek-enabled.txt`（`1` 开启、`0` 关闭），重启后保留。关闭后
后续纠错请求跳过云端；已经发出的请求仍等待结束。**本地识别、词库和标点继续工作**。
快捷键沿用当前 X11 全局键盘监听。

---

## 服务与排错

```bash
# 看守护进程 / 听写状态 / 当前麦克风
./baogu-status

# 异常时全部停掉
./baogu-reset

# 实时日志
journalctl --user -u baogu-ptt        -f   # PTT 守护进程
journalctl --user -u baogu-engine     -f   # 默认 DeepSeek 路径的引擎日志
journalctl --user -u baogu-corrector  -f   # 仅 legacy FireRed + 本地纠错服务
```

`baogu-ptt.service` 随图形会话自启，异常自动重启。

---

## 为什么不再默认使用 Vosk

真实使用中暴露的三个问题——长时间使用卡死、中英混输差、中文准确率低——都和旧主链路有关。
新链路做了这些调整：

1. **Vosk small-cn → Sherpa streaming Paraformer（中英双语）**，解决基础中文和 code-switch 能力不足。
2. **可选 FireRedASR2 第二遍纠错**：实时结果负责速度，松键后的离线 CTC 结果负责准确率。
3. **不再每个 partial 都启动一次 `busctl` 子进程**：优先使用一个持久化 Gio D-Bus 连接直达 Fcitx5。
4. **PTT supervisor 有超时恢复**：最终识别超过 4 秒未回到 idle 时直接重启引擎，而不是整套输入法永久卡住。
5. **每次听写独立 ASR stream / recorder**，一次异常不会污染下一次听写。

历史 POC 阶段的 Vosk small 模型识别差、xdotool 包装脚本、POC 兼容性等问题，已随链路切换
到 Sherpa streaming + Fcitx5 native bridge 不再适用；详细数据保留在 `POC-REPORT.md`。

---

## 用真人录音评测

`scripts/14-record-samples.sh` 产生的 manifest 可以直接交给当前识别链路。评测会同时报告内容、
原始格式、英文词、数字和标点准确率，并把逐句结果写成 TSV：

```bash
python3 scripts/08-offline-suite.py \
  --manifest samples/voice-input-session-20260921-211507/manifest.tsv
```

默认使用日常路径（Sherpa streaming）。测试 FireRed 时临时加 `BAOGU_FINAL_ENABLED=1`；
**不要仅因模型已经下载就默认启用**。当前这批 30 条真人录音的 streaming 内容准确率为
90.66%，FireRed 为 82.71%。这批数据参与了调优，**只能作为开发集**；最终准确率需要另录
未参与调优的样本验收。

### 验收指标

后续以首字延迟、最终纠错延迟、中文 CER、中英 code-switch WER、连续 100 次 PTT 无卡死率
作为验收指标。是否达到「豆包输入法 80%」必须用同一批真人录音做 A/B 基准，不能只靠主观描述。

---

## 开发与测试

### 目录结构

```
baogu-voice-input-method/
├── deploy.sh                   # 日常重建 + 启动脚本
├── baogu-ptt / -engine / -corrector   # 用户级服务入口
├── baogu-lib.sh             # 公共 shell 库（单实例锁、信号收发、状态查询）
├── baogu_glossary.py        # 词库确定性纠正
├── baogu_settings.py        # 设置与持久化
├── native/                     # Fcitx5 原生桥（C++）
│   ├── baogu.cpp
│   ├── build.sh
│   └── install.sh
├── hotwords/                   # 内置词库（TSV）
├── scripts/                    # 编号脚本 00–21 + lib.sh
│   ├── 00-user-test.sh          # 一键真人评测
│   ├── 09-setup-sherpa.sh       # 完整生产 ASR 栈
│   ├── 10-install-service.sh    # 用户级 systemd 服务
│   ├── 12-setup-corrector.sh / 13-…   # legacy 路径
│   ├── 14-record-samples.sh     # 真人录音 manifest
│   └── 20-build-glossary.sh     # 词库编译
├── tests/                      # 单元与回归（不录音、不向桌面打字）
│   └── python -m unittest discover -s tests -v
├── docs/                       # 调研、评测、landing
│   └── typeless-research.md
├── nerd-dictation/             # 上游项目（仍可用作手动 nerddictation 路径）
├── models/                     # 默认 ASR 模型目录
├── POC-REPORT.md               # POC v0.1 完整记录
└── README.md                   # 本文件
```

### 单元与回归

```bash
python3 -m unittest discover -s tests -v   # 不录音、不向桌面打字
```

覆盖：原生桥（`tests/native_bridge.py`）、词库、引擎逻辑、有界清理、LLM 纠错、设置等。

### 延迟与兼容性

历史结果在 `logs/latency_results_*.tsv` 和 `logs/app_compat_*.tsv`。耗时日志只记录字符数，
不保存识别内容，可用 `journalctl --user -u baogu-ptt` 查看。

---

## 环境要求

- **OS**：Ubuntu 24.04 LTS（GNOME）
- **显示协议**：X11（Wayland 需 ydotool 等 root 服务，本项目目前限定 X11）
- **输入框架**：Fcitx5（含 `libfcitx5core-dev` / `libfcitx5utils-dev` / `libfcitx5config-dev`）
- **构建工具**：`g++`、`make`
- **Python**：3.10+，`pip` 装 `vosk` / `sherpa-onnx` / `sounddevice` 等
- **音频**：PipeWire 或 PulseAudio；默认采样率 16 kHz
- **麦克风**：USB 输入优先；每次按键重新解析（`baogu-mic`）

### 模型

| 模型 | 角色 | 大小 |
|---|---|---|
| streaming Paraformer (Sherpa, 中英双语) | 实时 partial → preedit | 较小，常驻内存 |
| offline Paraformer large | 松键后 final → commit | 较大，按需加载 |
| 本地 punctuation model | final 后确定性标点 | 较小 |
| FireRedASR2 (legacy) | final 第二遍纠错，可选 | 较大 |
| DeepSeek `deepseek-v4-flash` | 云端后处理，可选 | 云端，无需本地资源 |

---

## Legacy POC 资料

> 项目代号：苞谷输入法 POC ｜ 版本 v0.1 ｜ 状态：执行中
> 完整结论见 [`POC-REPORT.md`](POC-REPORT.md)（结论 B：POC 部分通过，先完成真人语音验证再二开）。

### 核心目标

在 Ubuntu 上验证：**用户聚焦任意输入框 → 说中文 → 识别文字不经复制粘贴，直接进入当前输入框**。

### POC 环境

| 项目 | 值 |
|---|---|
| OS | Ubuntu 24.04.4 LTS |
| 桌面 | GNOME (ubuntu) |
| 显示协议 | X11 (`DISPLAY=:1`) |
| 旧版 POC 输入工具 | xdotool |
| ASR | Vosk（Python API） |
| 模型 | `vosk-model-small-cn-0.22` |
| 采样率 | 16000 Hz |

### 手动 nerd-dictation 路径（仍可用）

```bash
./nerd-dictation/nerd-dictation begin \
    --vosk-model-dir models/vosk-model-small-cn-0.22 \
    --sample-rate 16000 \
    --defer-output

# 说话...

./nerd-dictation/nerd-dictation end
```

- `end` 命令 touch cookie 文件，后台 `begin` 进程检测到后执行最终识别并上屏。
- `--defer-output`：说话过程中不上屏，结束时一次性输入。
- `cancel` 丢弃本次录音。
- xdotool 基于 XTEST，**仅 X11 可用**。

### 守护进程设计要点

- **只允许一个 nerd-dictation 进程**。`begin` 把 PID 写入公共 cookie，第二次直接覆盖，
  第一个实例就成为孤儿；按 N 次热键就留 N 个实例（每个约 260MB、各占一路麦克风）。
  所以进程由 `baogu-ptt` 守护进程独占，用信号切换状态：
  - `SIGCONT`：开始录音（`parec` 起来）
  - `SIGUSR1`：冲刷文字 → 关掉 `parec` → 进程自己 `SIGSTOP`
- 空闲时进程是 `T`（停止）状态：**0% CPU、不占麦克风**，模型留在内存里，按下键 ~100ms 就能录。
- **按键来源**：`xinput test-xi2 --root`（GNOME 自己的快捷键只有按下事件，也绑不了单独修饰键）。
  右 Alt = keycode 108，换布局时用 `BAOGU_PTT_KEYCODE` 覆盖。自动重复的按下事件被忽略。
- **忽略 XTEST 合成按键**：上屏时 `xdotool --clearmodifiers` 会产生修饰键松开/恢复事件，
  不能当作真人的 PTT 操作。退格会清除修饰键，避免变成 Alt+BackSpace 等应用快捷键。
- **及时读取积压音频**：每轮读取当前可用数据，保留不足完整 PCM 采样的碎片。日常服务每 20ms 检查一次。
- **麦克风每次按键重新解析**（`baogu-mic`）：优先当前默认输入（若是 USB）→ 任意 USB 输入 → 当前默认 → 任意输入。
- **独立状态文件**：日常服务使用 `$XDG_RUNTIME_DIR/baogu-<uid>.cookie`，与手动测试的默认 cookie 隔离。

> 右 Alt 仍然是普通 Alt 键，按住时其它程序也会当成 Alt。若不想要这个副作用，可以把它
> 映射掉：`xmodmap -e 'keycode 108 = VoidSymbol'`（xinput 读的是映射前的 keycode，PTT 不受影响）。

---

## 已知问题

1. **GNOME/mutter 程序化焦点不稳定**：自动化测试需 `windowactivate`+点击组合；真人场景由用户手动聚焦，不受影响。
2. **声学回环（扬声器→mic）降质**：回环测试识别率低于真人语音，**真人测试为准**。
3. **X11 全局键盘监听**：PTT 与 `Ctrl+Shift+F9` 都通过 `xinput test-xi2 --root` 监听；Wayland 需 ydotool 等 root 服务，本项目目前限定 X11。
4. **2026-09-08 POC 修复验证**：隔离 X11 桌面中，以 16kHz 录音重放、真实 Vosk 和 xdotool 连续测试 3 次即时上屏，约 1 秒出现首段文字；按住 Alt 的中文退格修正通过。**此项不替代当前麦克风的真人语音验收**。
5. **后续原生输入验证**：Fcitx5 + GTK4 连续 3 次实时识别上屏通过；首段文字约 1 秒出现；VTE/Bash 终端按住 Alt 的中文输入与修正通过。原生接口测试还覆盖焦点丢失、拒绝删除本次听写之前的文字，源码见 `tests/native_bridge.py`。

### 外放视频时语音输入（WebRTC 回声消除）

PipeWire / PulseAudio 支持 `module-echo-cancel` 时，可以使用系统 WebRTC AEC。
在项目目录执行：

```bash
./baogu-aec on       # 创建虚拟麦克风，将当前输出上的播放流接入回声消除
./baogu-aec status   # 查看状态
./baogu-aec off      # 恢复原设备并卸载本工具创建的模块
```

开启后松开并重新按下语音输入快捷键，输入法会优先录制 `baogu_echo_source`。
播放默认设备会切到 `baogu_echo_sink`，实际声音仍从开启时的扬声器播放。
现有播放流会迁移；手动绑定其他输出设备的应用需要在声音设置中选用此虚拟输出，
否则这部分播放声音无法作为消除参考。关闭时只在默认设备仍是本工具虚拟设备时恢复默认值，
保留期间手动选择的其他设备。虚拟麦克风消失后，输入法下次录音会恢复选择物理麦克风。

此开关只对当前音频服务会话有效，重启电脑或音频服务后需重新执行 `on`。
更换麦克风或扬声器后，先 `off` 再 `on`，以绑定新设备。
依赖 `pactl` 和服务端 WebRTC AEC 支持；模块加载失败会显示错误。
如出现播放或识别异常，可执行 `./baogu-aec off` 恢复。

验收时分别测试：仅视频播放（不应输入视频台词）、仅自己说话、双方同时说话。
音量、房间回声和设备延迟会影响效果，软件路由验证不能代替真人测试。
