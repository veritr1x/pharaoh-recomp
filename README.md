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
(`mss32.dll`), which the kit currently handles with silent shims; its
cinematics are Bink and Smacker video. The Bink shim returns a finished
video record to skip decoding; Smacker still refuses to open a video.
The measurements are in [docs/analysis.md](docs/analysis.md).

## Status: Bink open failure removed; smoke still exits before the menu on macOS

The app, headless and smoke hosts build. The latest run of
`smoke/main-menu.script` selects 640x480 at 16 bpp and no longer logs
`Unable to load BINK!`, but still calls `ExitProcess(0)`. Its captured
frame is uniformly black; the main menu and campaign click remain unverified.
The [run log](docs/analysis.md) records the commands, diagnostics and dump.

The working kit includes silent Miles shims (41 imports), Bink and Smacker
shims (19 imports), and the 15 missing user32, gdi32 and kernel32 shims.
Native checks pass for the finished Bink record and its release. Task 2.7
stopped at the unmet smoke capture expectation, so its changes are not
committed and the kit pin remains `17b31a0`. The run does not establish a
working menu, gameplay or audio; the remaining guest exit is undiagnosed.

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
