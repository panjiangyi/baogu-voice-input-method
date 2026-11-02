#!/usr/bin/env python3
"""Evaluate optional local GPU candidates using the existing corpus and metrics.

This does not change the running input method. Model paths must already exist;
inference never downloads models or submits audio to a hosted service.
Run with the Python environment containing the selected optional runtime.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]


class Candidate:
    def __init__(self, args):
        self.backend = args.backend
        self.recognizer = None
        self.args = args
        if args.backend == "whisper":
            from faster_whisper import WhisperModel
            self.recognizer = WhisperModel(
                str(args.model), device=args.device,
                compute_type=args.compute_type, cpu_threads=4,
                local_files_only=True,
            )
        else:
            import torch
            from qwen_asr import Qwen3ASRModel
            torch.set_num_threads(4)
            model_kwargs = {}
            if args.load_in_4bit:
                from transformers import BitsAndBytesConfig
                model_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True, bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=torch.bfloat16,
                )
            self.recognizer = Qwen3ASRModel.from_pretrained(
                str(args.model), dtype=torch.bfloat16 if args.device == "cuda" else torch.float32,
                device_map="cuda:0" if args.device == "cuda" else "cpu",
                max_inference_batch_size=1, max_new_tokens=512,
                local_files_only=True,
                **model_kwargs,
            )

    def transcribe(self, pcm: bytes) -> str:
        import numpy as np
        samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        if self.backend == "whisper":
            segments, _ = self.recognizer.transcribe(
                samples, language=self.args.language, task="transcribe",
                beam_size=5, temperature=0, condition_on_previous_text=False,
                vad_filter=False, initial_prompt=self.args.context or None,
            )
            return "".join(segment.text for segment in segments).strip()
        results = self.recognizer.transcribe(
            audio=(samples, 16000), language=self.args.language,
            context=self.args.context,
        )
        return "".join(result.text for result in results).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    parser.add_argument("--backend", choices=("whisper", "qwen-transformers"), required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--compute-type", default="int8_float16", help="Whisper compute type")
    parser.add_argument("--language", help="optional language hint; otherwise auto-detect")
    parser.add_argument("--context", default="", help="optional acoustic vocabulary/context prompt")
    parser.add_argument("--load-in-4bit", action="store_true", help="quantize Qwen for limited CUDA memory")
    args, remaining = parser.parse_known_args()
    if not args.model.is_dir():
        parser.error("--model must be an existing local model directory")
    if args.load_in_4bit and (args.backend != "qwen-transformers" or args.device != "cuda"):
        parser.error("--load-in-4bit requires qwen-transformers on CUDA")
    print(f"Candidate backend={args.backend} model={args.model.resolve()} "
          f"device={args.device} four_bit={args.load_in_4bit} "
          f"language={args.language or 'auto'} context_chars={len(args.context)}", flush=True)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    suite = runpy.run_path(str(ROOT / "scripts/08-offline-suite.py"))
    suite["main"].__globals__["FinalRecognizer"] = lambda: Candidate(args)
    if "--mode" in remaining:
        parser.error("this diagnostic runner only supports raw-final mode")
    sys.argv = [sys.argv[0], "--mode", "raw-final", *remaining]
    return suite["main"]()


if __name__ == "__main__":
    raise SystemExit(main())
