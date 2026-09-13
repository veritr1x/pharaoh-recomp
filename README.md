# Pharaoh Recomp

[Build & contribute](CONTRIBUTING.md) · [Port analysis](docs/analysis.md) ·
[Testing](docs/testing.md) · [Changelog](CHANGELOG.md)

A native macOS and iPad recompilation of **Pharaoh Gold** (the GOG release
of Impressions Games' Pharaoh with its Cleopatra expansion, patch 2.1), in
progress. Original game instructions are translated to C ahead of time and
compiled with the native host, the way
[populous-recomp](https://github.com/veritr1x/populous-recomp) and
[majesty-recomp](https://github.com/veritr1x/majesty-recomp) do it.

The runtime, translator, hosts and mod foundation are
[recomp-kit](https://github.com/veritr1x/recomp-kit), pulled in as the git
submodule `kit/`. This repository holds what is Pharaoh's: `game.toml` and
`globals.toml` (identity, addresses, curated symbols), `tests/` (the
config's contract with the kit), `tools/analyze.py` (this game's listing
export) and docs. The kit is private at the moment, so the submodule needs
access to it.

**You need your own copy of the game.** Game executables, artwork, sound,
music, maps, generated game code and replacement packs are prepared locally
and are not included. See [NOTICE](NOTICE) for ownership and dependency
credits.

## Which executable

The GOG installer ships one game executable, **`Pharaoh.exe`** (Pharaoh
2.1.0.0, built 2000-08-28, Visual C++ 6 with the C runtime linked
statically). It renders through **DirectDraw** version 1, which the kit
models, and plays sound and MP3 music through the **Miles Sound System**
(`mss32.dll`), which the kit does not serve yet; its cinematics are Bink and
Smacker video. The measurements are in [docs/analysis.md](docs/analysis.md).

## Status: the executable translates with one gate waived; nothing runs yet

The config loads through the kit, the config tests pass, the game links,
Ghidra exports the listings (4,502 functions) and the kit's translator
turns the executable into C (6,138 of 6,141 functions) once its jump-table
gate is waived for one Visual C++ switch whose function Ghidra missed.
`tools/build.py --regenerate` stops at that gate, so nothing has been
compiled or run; the run log at the end of
[docs/analysis.md](docs/analysis.md) has the measurements.

The kit work this game will need, from the import table alone: a Miles
Sound System shim (41 imports, the whole audio path), Bink and Smacker
video stubs or decoders (19 imports), and 15 user32, gdi32 and kernel32
functions the kit has not needed before.

## Build on macOS

The steps are the kit's.

```sh
git clone --recurse-submodules https://github.com/veritr1x/pharaoh-recomp.git
cd pharaoh-recomp
python3 -m venv .venv
.venv/bin/python -m pip install -r kit/requirements-dev.txt
innoextract --extract --output-dir original/gog /path/to/setup_pharaoh_gold_2.1.0.15.exe
.venv/bin/python tools/setup.py --install original/gog/app --link-only
.venv/bin/python tools/analyze.py --ghidra-home /path/to/ghidra_12.1.3_PUBLIC
.venv/bin/python tools/build.py --regenerate
```

`original/gog/app` is where `game.toml` expects the game; that is where
[innoextract](https://constexpr.org/innoextract/) puts the installer's game
directory, so extracting there is the same as linking an installed copy with
`tools/setup.py --install /path/to/installed/game --link-only`.
`tools/setup.py`, `tools/build.py`, `tools/test.py` and `tools/ios_logs.py`
are four-line wrappers around the kit's tools; every option is the kit's
(`--help` lists them). `tools/analyze.py` is this game's own: the kit's
setup exports listings from a curated annotation set, and none exists for
this executable, so this script runs Ghidra's analyzers instead. Outputs
(the translation, the apps, the logs) live under ignored `build/`; the game
lives in ignored `original/` and the Ghidra listings in ignored `analysis/`.

## Play on an iPad

Not yet: the game has to run on macOS first. When it does, the kit's
`tools/build.py --target ios` builds, signs and installs `PharaohRecomp.app`
with the game minus `[bundle].exclude` in `game.toml` (GOG's support files,
the Windows DLLs, the Miles plug-ins, the manuals).

## Check a change

```sh
.venv/bin/python tools/test.py              # the kit's portable suites
.venv/bin/python -m pytest -q tests         # this game's config
.venv/bin/python tools/build.py --stub      # the kit configures against this config, no game code
```

Changes to the runtime, hosts or tools belong in the kit's repository; bump
the submodule here once they land.
