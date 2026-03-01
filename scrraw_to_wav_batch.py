#!/usr/bin/env python3
"""
scrraw_to_wav_batch.py

Batch convert Screamer .RAW (headerless) audio to .WAV.

Screamer audio:
  - 8-bit unsigned PCM mono @ 11025 Hz  (WAV 8-bit is always unsigned)

Also supports:
  - 8-bit signed PCM (converted to WAV unsigned)
  - 16-bit PCM little-endian
  - 16-bit PCM big-endian (byteswapped to little-endian WAV)
  - Skipping a fixed header
  - Optional trimming of leading/trailing 0x80 for u8 (silence)

Examples:
  python scrraw_to_wav_batch.py ./in_dir --outdir ./wav --rate 11025 --enc u8
  python scrraw_to_wav_batch.py AIRPLANE.RAW ALL0.RAW --rate 11025 --enc u8
  python scrraw_to_wav_batch.py ./in_dir --enc s16be --skip 0x800
  python scrraw_to_wav_batch.py ./in_dir --enc u8 --trim-u8-silence
"""

from __future__ import annotations

import argparse
import os
import sys
import wave
from pathlib import Path
from typing import Iterable, List, Tuple


def parse_int_auto(x: str) -> int:
    """Parse int in decimal or 0x... hex form."""
    x = x.strip().lower()
    return int(x, 0)


def iter_input_files(inputs: List[str], exts: Tuple[str, ...] = (".raw",)) -> List[Path]:
    files: List[Path] = []
    for s in inputs:
        p = Path(s)
        if p.is_dir():
            for e in exts:
                files.extend(sorted(p.rglob(f"*{e}")))
        elif p.is_file():
            files.append(p)
        else:
            # Allow glob-like patterns without using glob module: Path().glob from parent.
            parent = p.parent if p.parent != Path("") else Path(".")
            pattern = p.name
            matched = list(parent.glob(pattern))
            matched = [m for m in matched if m.is_file()]
            files.extend(sorted(matched))
    # De-dup while preserving order
    seen = set()
    out: List[Path] = []
    for f in files:
        rp = f.resolve()
        if rp not in seen:
            seen.add(rp)
            out.append(f)
    return out


def trim_u8_silence(data: bytes, silence_byte: int = 0x80) -> bytes:
    """Trim leading/trailing 0x80 bytes (typical u8 silence)."""
    if not data:
        return data
    start = 0
    end = len(data)

    # leading
    while start < end and data[start] == silence_byte:
        start += 1
    # trailing
    while end > start and data[end - 1] == silence_byte:
        end -= 1

    return data[start:end]


def convert_payload(data: bytes, enc: str) -> Tuple[bytes, int]:
    """
    Convert raw payload into WAV-ready PCM frames.
    Returns: (frames_bytes, sampwidth_bytes)
    """
    enc = enc.lower()

    if enc == "u8":
        # WAV 8-bit PCM is unsigned; pass through.
        return data, 1

    if enc == "s8":
        # Convert signed 8-bit [-128..127] to unsigned [0..255] for WAV:
        # unsigned = signed + 128 (mod 256)
        out = bytes(((b + 128) & 0xFF) for b in data)
        return out, 1

    if enc == "s16le":
        # WAV expects little-endian signed 16-bit.
        # Ensure even length
        if len(data) % 2 != 0:
            data = data[:-1]
        return data, 2

    if enc == "s16be":
        # Swap to little-endian
        if len(data) % 2 != 0:
            data = data[:-1]
        b = bytearray(data)
        b[0::2], b[1::2] = b[1::2], b[0::2]
        return bytes(b), 2

    raise ValueError(f"Unsupported --enc: {enc}")


def write_wav(out_path: Path, frames: bytes, rate: int, channels: int, sampwidth: int) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(sampwidth)
        w.setframerate(rate)
        w.writeframes(frames)


def main() -> int:
    ap = argparse.ArgumentParser(description="Batch convert .RAW audio to .WAV.")
    ap.add_argument(
        "inputs",
        nargs="+",
        help="Input .RAW files and/or directories. Directories are searched recursively for *.raw",
    )
    ap.add_argument("--outdir", default="wav_out", help="Output directory (default: wav_out)")
    ap.add_argument("--rate", type=int, default=11025, help="Sample rate Hz (default: 11025)")
    ap.add_argument("--channels", type=int, default=1, help="Number of channels (default: 1)")
    ap.add_argument(
        "--enc",
        default="u8",
        choices=["u8", "s8", "s16le", "s16be"],
        help="Raw PCM encoding (default: u8)",
    )
    ap.add_argument(
        "--skip",
        default="0",
        help="Skip N bytes at start (header). Accepts decimal or hex (e.g. 512 or 0x200). Default 0",
    )
    ap.add_argument(
        "--trim-u8-silence",
        action="store_true",
        help="Trim leading/trailing 0x80 bytes (only meaningful for --enc u8)",
    )
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing WAVs",
    )

    args = ap.parse_args()

    skip = parse_int_auto(args.skip)
    if skip < 0:
        print("[ERR] --skip must be >= 0", file=sys.stderr)
        return 2

    in_files = iter_input_files(args.inputs, exts=(".raw", ".RAW"))
    if not in_files:
        print("[ERR] No input files found.", file=sys.stderr)
        return 2

    outdir = Path(args.outdir)
    rate = int(args.rate)
    channels = int(args.channels)
    enc = args.enc.lower()

    ok = 0
    fail = 0

    for f in in_files:
        try:
            raw = f.read_bytes()
            if skip > len(raw):
                print(f"[SKIP] {f} (skip {skip} > file size {len(raw)})")
                fail += 1
                continue

            payload = raw[skip:]

            if args.trim_u8_silence and enc == "u8":
                payload = trim_u8_silence(payload, silence_byte=0x80)

            frames, sampwidth = convert_payload(payload, enc=enc)

            # For 16-bit encodings, enforce sample alignment across channels
            if sampwidth == 2:
                frame_bytes = sampwidth * channels
                if len(frames) % frame_bytes != 0:
                    frames = frames[: len(frames) - (len(frames) % frame_bytes)]

            out_path = outdir / (f.stem + ".wav")
            if out_path.exists() and not args.overwrite:
                print(f"[EXISTS] {out_path} (use --overwrite to replace)")
                continue

            write_wav(out_path, frames, rate=rate, channels=channels, sampwidth=sampwidth)
            print(f"[OK] {f.name} -> {out_path}  (rate={rate}, ch={channels}, enc={enc}, skip={skip}, bytes={len(payload)})")
            ok += 1

        except Exception as e:
            print(f"[FAIL] {f}: {e}", file=sys.stderr)
            fail += 1

    print(f"[DONE] ok={ok} fail={fail} outdir={outdir}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
