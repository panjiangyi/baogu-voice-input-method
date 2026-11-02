# Natural Mandarin accent acceptance recordings

User clarification (2026-10-31): Mandarin with n/l confusion and front/back nasal
merging; back nasal finals are not distinctly pronounced. This is not a request
to transcribe full Hubei or Southwestern dialect vocabulary.

Read `accent-nl-nasal.txt` naturally with your usual pronunciation. Do not
exaggerate distinctions, imitate a dialect, or practise standard pronunciation.
The task is to recognize intended words using acoustic evidence and context.
Add spontaneous speech separately: reading alone understates daily-use difficulty.

```bash
PROMPTS_FILE="$PWD/docs/evaluation/accent-nl-nasal.txt" \
SESSION_DIR="$PWD/samples/accent-nl-nasal" \
bash scripts/14-record-samples.sh
```

Manually confirm what was actually said at each transcript prompt. Do not use
any recognizer's output as ground truth. Reserve cases 17–20 from tuning, and
collect additional unprompted sentences for final acceptance. This small set
does not itself establish equivalence to Doubao.

For a valid Doubao comparison, feed the same recorded audio to iPhone/Mac Doubao
offline and preserve the returned text, app version, and offline state. If using
speaker playback, record that method and feed its microphone capture to Baogu
too; comparing original WAV inference against a different acoustic capture is
not controlled. Do not upload audio for local-only acceptance.

Measure n/l and nasal-final target word errors with sentence context, general
Chinese/English errors and false corrections of normally recognized words.
Do not add global substitutions for n/l or nasal finals: they are ambiguous and
can change correct words. Keep acoustic ASR, glossary and text formatting scores
separate. Include a normally pronounced control set when evaluating accent tuning.
