# Contributing

This repository holds Pharaoh Gold's configuration, tests and docs on top of
[recomp-kit](https://github.com/veritr1x/recomp-kit), the submodule at
`kit/`. Runtime, translator, host and tooling changes go to the kit; open an
issue there before a large architecture change. Here, the useful work is the
bring-up itself: identifying the hooks and globals that `game.toml` still
marks as sentinels, curating symbols in `globals.toml`, and keeping
[docs/analysis.md](docs/analysis.md) true.

## Prerequisites

- Python 3.9 or later; create `.venv` and install `kit/requirements-dev.txt`.
- Native builds on macOS: Apple Silicon, Xcode Command Line Tools and Git.
  CMake and Ninja come from the requirements file. iPad builds need Xcode
  with the iOS SDK and a developer team.
- Listings: [Ghidra 12.1.3](https://github.com/NationalSecurityAgency/ghidra/releases/tag/Ghidra_12.1.3_build)
  and a Java runtime compatible with it (tested with OpenJDK 26.0.1; set
  `JAVA_HOME` to the JDK directory or pass `--java-home`).
- Your own copy of Pharaoh Gold from GOG, either installed or as the offline
  installer plus [innoextract](https://constexpr.org/innoextract/)
  (`brew install innoextract`).

The executable must be `Pharaoh.exe` with SHA-256:

```text
b21b7d719491bb45dfb324ba95231a5b0960ab25fea1bf3fb21da65da7eca662
```

That is the 2.1.0.0 build the GOG installer 2.1.0.15 ships. The loader
refuses other binaries because translated addresses and data layouts are
tied to this image. Do not bypass the hash to add support for another
version (the retail Pharaoh, the retail Cleopatra, the Steam release); a
second version is a second `game.toml`.

## Prepare your game installation

The game directory must contain `Pharaoh.exe` and its `AUDIO`, `BINKS`,
`Data` and `Maps` directories. Either extract the GOG installer into
`original/gog`, which puts the game directory at `original/gog/app`, where
`game.toml` expects it:

```sh
innoextract --extract --output-dir original/gog /path/to/setup_pharaoh_gold_2.1.0.15.exe
.venv/bin/python tools/setup.py --install original/gog/app --link-only
```

or link an installed copy (paths containing spaces are supported when
quoted):

```sh
.venv/bin/python tools/setup.py --install "/path/to/GOG Games/Pharaoh Gold" --link-only
```

Setup verifies the executable and links the installation at ignored
`original/gog/app` (a copy or extraction placed there directly is accepted,
as above). It does not download the game. Then export the listings:

```sh
.venv/bin/python tools/analyze.py \
  --ghidra-home "/path/to/ghidra_12.1.3_PUBLIC" \
  --java-home "/path/to/your/jdk/Contents/Home"
```

`tools/analyze.py` imports the executable into a disposable Ghidra project,
runs Ghidra's default analyzers and exports translation inputs into ignored
`analysis/decompiled/Pharaoh.exe` with the kit's export script; the log is
`build/analyze.log`. The kit's own `tools/setup.py` without `--link-only` is
not used here: it exports with analysis off and expects a curated
annotation set, which this executable does not have.

## Build and run

```sh
.venv/bin/python tools/build.py --regenerate --jobs 8   # translate, then compile
.venv/bin/python tools/build.py --jobs 8                # afterwards
```

See [docs/analysis.md](docs/analysis.md) for how far the bring-up has got.
`--target ios` builds, signs and installs the iPad app (`RECOMP_IOS_TEAM` or
`--team`) once a macOS build runs. The CMake tree lives in
`build/cmake/<preset>`.

## Check your change

```sh
.venv/bin/python tools/test.py             # the kit's portable suites; no game files required
.venv/bin/python -m pytest -q tests        # this repository's config tests
.venv/bin/python tools/build.py --stub     # link-only configure of this config through the kit
.venv/bin/python kit/tools/format.py       # handwritten native code style (kit sources)
```

See [docs/testing.md](docs/testing.md).

## Updating the kit

`git -C kit checkout <commit>` then commit the submodule pointer here, with a
changelog line naming what changed. Keep the pin on a kit tag when one exists.
