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
(`mss32.dll`), which the kit handles with WAV sample and MP3 stream shims; its
cinematics are Bink and Smacker video. The Bink shim returns a finished
video record to skip decoding; Smacker still refuses to open a video.
The measurements are in [docs/analysis.md](docs/analysis.md).

## Status: macOS smoke bring-up

`smoke/main-menu.script` captures the 640x480 Cleopatra title screen with
“Click to Start”, clicks its centre, and captures the five-button main menu
four seconds later and again after another two seconds. Both menu captures
are identical. The 21-second smoke run presents 438 frames and exits through
`ExitProcess(0)`. Miles WAV effects reach the smoke host's mixer; the effects
run records the title-screen click at peak 0.782. In the headless host, the
title-screen MP3 capture contains 24.092 seconds of audio, 23.8 seconds
non-silent, with no logged underrun. The smoke host lacks streaming
callbacks, so music output is verified in headless only.

`smoke/first-mission.script` enters a new family name, starts the Predynastic
campaign, opens the Nubt briefing and dismisses the housing tutorial. Its
two timed city captures show moving animals and an advancing date. The
eight-round run record, every screen's capture path and the remaining
limits are in [docs/analysis.md](docs/analysis.md). The game created profile
autosaves; **saving through the menu and reloading remain unverified**.
Housing construction and human walkers remain unverified. The interactive
macOS app displays the title screen, but its automated click did not advance
it, and quitting ended with a host fault; see the Task 4.2 run record.

The kit is pinned to landed main `2fe5c5d` and includes Miles shims (41
imports), Bink and Smacker shims (19 imports), and the 15 missing user32,
gdi32 and kernel32 shims. The
[run record](docs/analysis.md) gives the commands, captures, button
coordinates and limits.

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

To run the campaign smoke after preparing and translating the game:

```sh
.venv/bin/python tools/build.py --target smoke --jobs 8
mkdir -p build/recomp/profile
smoke_profile=$(mktemp -d "$PWD/build/recomp/profile/first-mission.XXXXXX")
RECOMP_PROFILE_DIR="$smoke_profile" \
RECOMP_SCRIPT="$PWD/smoke/first-mission.script" \
RECOMP_HOST_DUMP_DIR=build/smoke/first-mission \
RECOMP_DDRAW_MODES=640x480x16 RECOMP_SMOKE_DRAWABLE=1024x768 \
RECOMP_MAX_SECONDS=150 build/recomp/pop_smoke
```

Use a fresh profile each time: an existing family opens the Family Registry
instead of name entry. Keep the profile to retain the game's files. Dumps
are named `smoke_<name>_present.ppm`, including `smoke_city-10s_present.ppm`
and `smoke_city-30s_present.ppm`. The script ends after those captures and
does not test menu saving or loading. The current smoke host ignores
`RECOMP_MAX_SECONDS`; its own deadline is 180 seconds plus grace, and the
verified script finished in 71.8 seconds.

## Play on macOS

After completing the build steps above, launch from this checkout with
`open build/PharaohRecomp.app`, or double-click that app in Finder. For a
manual check, click the title screen, choose **Play Pharaoh/Cleopatra**,
then create a **new family** (choose **Create** if the Family Registry
appears). Enter a name, choose **Begin Family History**, select
**Predynastic Period** and its **Begin** arrow, then enter **Nubt** using
the **To the city** arrow and dismiss the housing tutorial. Choose the
housing tool and build a few houses, right-click a house for information,
try edge scrolling and the arrow keys, then press Escape and try the
in-game options and **Save/Load**. Keep your family/profile files in
`build/recomp/profile`. These hand checks remain unverified: the automated
app run reached only the title, and quitting faulted after guest exit 0.
The captures, resolution, cursor limitations and pacing measurements are
in [docs/analysis.md](docs/analysis.md).

## Play on an iPad

Not yet verified on iPad. The kit's
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
