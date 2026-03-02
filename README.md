# Screamer Audio RAW > WAV Batch Converter

A small Python utility to batch-conbine headerless `.RAW` audio dumps from ShOUT into standard `.WAV` files.

This repo is designed for game/console reverse-engineering workflows where audio is stored as raw PCM without a container header. Default settings target the confirmed case:

- **Sample rate:** `11025 Hz`
- **Channels:** `mono (1)`
- **Encoding:** `8-bit unsigned PCM (u8)`

If your dumps differ (signed 8-bit, 16-bit, byte-swapped, or have a fixed header), the script exposes flags to handle that.

---

## Features

- Batch convert **individual files**, **folders**, or **recursive directory trees**
- Writes standard PCM `.WAV` files using Python’s built-in `wave` module (no external deps)
- Supports common raw encodings:
  - `u8`   (8-bit unsigned PCM) **default**
  - `s8`   (8-bit signed PCM; converted to WAV-compatible unsigned)
  - `s16le` (16-bit signed little-endian PCM)
  - `s16be` (16-bit signed big-endian PCM; byte-swapped to little-endian)
- Optional:
  - Skip a fixed header (`--skip`)
  - Trim leading/trailing `0x80` silence for `u8` (`--trim-u8-silence`)
  - Overwrite existing outputs (`--overwrite`)

---

## Repository Layout
```
.
├── scrraw_to_wav_batch.py  # main converter script
└── README.md
```
Outputs are written to `./wav_out` by default (configurable via `--outdir`).

## Requirements

Python 3.8+ (recommended)

No third-party packages

Install / Run

Clone/download the repository and run directly:

`python scrraw_to_wav_batch.py --help`

Quick Start (11025 Hz, 8-bit unsigned, mono)

Convert all `.RAW` files in a directory (recursively) to `./wavs`:

`python scrraw_to_wav_batch.py ./raws --outdir ./wavs --rate 11025 --enc u8`

Convert specific files:

`python scrraw_to_wav_batch.py AIRPLANE.RAW ALL0.RAW ALL1.RAW --outdir ./wavs --rate 11025 --enc u8`

Common Scenarios
1) The .RAW has a fixed header before PCM

Skip the header (hex or decimal accepted):

`python scrraw_to_wav_batch.py ./raws --outdir ./wavs --rate 11025 --enc u8 --skip 0x800`

2) The audio is signed 8-bit (sounds distorted with u8)

Try s8:

`python scrraw_to_wav_batch.py ./raws --outdir ./wavs --rate 11025 --enc s8`

3) The audio is 16-bit PCM

Little-endian:

`python scrraw_to_wav_batch.py ./raws --outdir ./wavs --rate 11025 --enc s16le`

Big-endian / byte-swapped:

`python scrraw_to_wav_batch.py ./raws --outdir ./wavs --rate 11025 --enc s16be`

4) Trim silence padding (typical 0x80 for unsigned 8-bit)

Useful if files include long silent tails/heads:

`python scrraw_to_wav_batch.py ./raws --outdir ./wavs --rate 11025 --enc u8 --trim-u8-silence`

5) Overwrite existing WAVs

By default, existing outputs are kept:

`python scrraw_to_wav_batch.py ./raws --outdir ./wavs --overwrite`
