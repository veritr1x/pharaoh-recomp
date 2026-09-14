# Pharaoh Recomp

[Build & contribute](CONTRIBUTING.md) · [Port analysis](docs/analysis.md) ·
[Testing](docs/testing.md) · [Changelog](CHANGELOG.md)

A native recompilation of **Pharaoh Gold** (the GOG release
of Impressions Games' Pharaoh with its Cleopatra expansion, patch 2.1), in
progress, with hosts for macOS, iPad, Linux, Windows and Android.
Original game instructions are translated to C ahead of time and
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

## Platform status

Status as of 2026-09-14, from the [run log](docs/analysis.md). Build
commands assume the game preparation and translation steps below; platform
sections give prerequisites and installation commands. A stub or package
build does not establish first-mission play.

| Platform | Verified status / first-mission play | Build command | Known issues and remaining checks |
| --- | --- | --- | --- |
| macOS 14+ | Smoke reaches the title, menu and an advancing first mission; WAV effects work. The app shows the title and captures non-silent music. | `.venv/bin/python tools/build.py` (app); `.venv/bin/python tools/build.py --target smoke` | Shutdown SIGSEGV at `0x0056478f` remains open. Hand play is untested; the automated app click did not advance the title. Smoke music streaming is unverified. |
| iPadOS 17+ | Device boots at **640x480x16** with a music stream active; audible output and first-mission touch play are unverified. | `.venv/bin/python tools/build.py --target ios --team <TEAM_ID> --no-install` | Presenter acknowledgement timeout uses a fallback. No title/menu capture or touch-play check; iOS configure fails from some shells. |
| Linux | Host/tooling checks only on macOS; packager tests use fake binaries. Never built or run on Linux; first mission unverified. | `.venv/bin/python tools/build.py --regenerate --jobs 8` | Native package, Vulkan window/driver validation and gameplay remain untested. |
| Windows | Host/tooling checks only on macOS; packager tests use fake binaries. Never built or run on Windows; first mission unverified. | `.venv\Scripts\python tools\build.py --regenerate --jobs 8` | Native package, Vulkan validation, guest path separators and gameplay remain untested. |
| Android 10+, arm64, Vulkan 1.1 | APK builds with the real translation. No device was attached; never run, first mission unverified. | `.venv/bin/python tools/build.py --target android` | Install, boot, music, touch and lifecycle behavior await a device. Existing NDK/CMake and Gradle warnings remain. |

### macOS smoke evidence

`smoke/main-menu.script` captures the 640x480 Cleopatra title screen with
“Click to Start”, clicks its centre, and captures the five-button main menu
four seconds later and again after another two seconds. Both menu captures
are identical. The 21-second smoke run presents 438 frames and exits through
`ExitProcess(0)`. Miles WAV effects reach the smoke host's mixer; the effects
run records the title-screen click at peak 0.782. In the headless host, the
title-screen MP3 capture contains 24.092 seconds of audio, 23.8 seconds
non-silent, with no logged underrun. The smoke host lacks streaming
callbacks, so these smoke runs do not verify music. Task 4.2 also records
38.0 seconds of non-silent music in the interactive app's mixer capture.

`smoke/first-mission.script` enters a new family name, starts the Predynastic
campaign, opens the Nubt briefing and dismisses the housing tutorial. Its
two timed city captures show moving animals and an advancing date. The
eight-round run record, every screen's capture path and the remaining
limits are in [docs/analysis.md](docs/analysis.md). The game created profile
autosaves; **saving through the menu and reloading remain unverified**.
Housing construction and human walkers remain unverified. The interactive
macOS app displays the title screen, but its automated click did not advance
it, and quitting ended with a host fault; see the Task 4.2 run record.

The kit is pinned to `502ad1c` and includes Miles shims (41
imports), Bink and Smacker shims (19 imports), and the 15 missing user32,
gdi32 and kernel32 shims. The
[run record](docs/analysis.md) gives the commands, captures, button
coordinates and limits.

### Known issues

- The macOS app faults during shutdown after guest `ExitProcess(0)`:
  **SIGSEGV at `0x0056478f`**, process exit 5. Presenter acknowledgement
  timeouts also trigger a fallback on macOS and iPad.
- `runtime_tests` retains **32 Populous-bound failures** (520 checks in
  the recorded baseline). The portable Python checks below do not run
  this game-backed suite.
- GDI `TextOutA` is accepted but not drawn.
- Cinematics are skipped by the Bink/Smacker stubs. `BINKS/` stays
  excluded from bundles and staged game data, saving about **140 MiB**
  on iPad and Android; see the [cinematics decision](docs/analysis.md#cinematics-decision-task-81).
- Manual Save/Load remains unverified; profile autosaves do not establish
  that saving through the menu and reloading work.
- iOS configure fails from some shells: the compiler probe targets
  `arm64-apple-macos17.0` with the macOS SDK. The orchestrator's other shell
  built successfully, and Task 8.1's iOS stub build also passes from the
  current shell. The earlier environment override remains unidentified.

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

## Build on Linux

**Not run yet:** neither the native Linux build/package nor the game has
been run on Linux. Task 6.3's Linux run is deferred because the development
Mac has no Linux machine or VM with the game. CI checks portable tests and
a stub build without game code; it does not establish gameplay.

Start in a recursive checkout with your supported game installation copied
to `original/gog/app`. Install Python with venv support, Ghidra 12.1.3 and
a compatible JDK as described in [CONTRIBUTING.md](CONTRIBUTING.md).
The Ubuntu packages below match the kit's CI:

```sh
sudo apt-get update -qq
sudo apt-get install -y -qq clang lld build-essential pkg-config libasound2-dev \
  libpulse-dev libaudio-dev libjack-dev libsndio-dev libx11-dev libxext-dev \
  libxrandr-dev libxcursor-dev libxfixes-dev libxi-dev libxss-dev libxtst-dev \
  libxkbcommon-dev libdrm-dev libgbm-dev libgl1-mesa-dev libgles2-mesa-dev \
  libegl1-mesa-dev libdbus-1-dev libibus-1.0-dev libudev-dev \
  libpipewire-0.3-dev libwayland-dev libdecor-0-dev liburing-dev \
  mesa-vulkan-drivers glslc
python3 -m venv .venv && .venv/bin/python -m pip install -r kit/requirements-dev.txt
.venv/bin/python tools/setup.py --install original/gog/app --link-only
.venv/bin/python tools/analyze.py --ghidra-home /path/to/ghidra_12.1.3_PUBLIC
.venv/bin/python tools/build.py --regenerate --jobs 8
.venv/bin/python tools/build.py --target smoke --jobs 8
RECOMP_SCRIPT=$PWD/smoke/first-mission.script RECOMP_HOST_DUMP_DIR=build/smoke build/recomp/pop_smoke
RECOMP_EXE="$PWD/original/gog/app/Pharaoh.exe" RECOMP_GPU_VALIDATE=1 \
  build/package/PharaohRecomp/PharaohRecomp
```

The separate smoke build is needed on a clean checkout: the default build
target builds only the app. Use a fresh profile and the same display
settings as the macOS campaign smoke above when comparing captures.
Compare matching dumps with `kit/tools/recomp/compare_frames.py`; the
expected result is only small timing differences, still unverified.
Check that the app opens a Vulkan window and reaches and plays the first
mission. Record the GPU/driver and validation output with
`RECOMP_GPU_VALIDATE=1`, including whether validation layers were available.

The packager writes `build/package/PharaohRecomp/` and
`build/package/PharaohRecomp-linux-<arch>.tar.gz` (`x86_64` or `aarch64`).
This is the current output directory, replacing the plan's
`build/linux/PharaohRecomp/`. As its generated `README.txt` explains,
`RECOMP_EXE` names the original **executable**, not a directory; its parent
is the game data root. The package contains no game files. Keep
`resources/` beside the app and keep the original executable with its data.

## Build on Windows

**Not run yet:** neither the native Windows build/package nor the game has
been run on Windows. Task 6.3's Windows run is deferred because no Windows
machine with the game is available. The new `windows-2025` CI entry runs
portable tests and a stub build; it has not been run yet.

Start in a recursive checkout with the supported installation copied to
`original\gog\app`, Python, Ghidra 12.1.3 and a compatible JDK. Run these
commands in a Visual Studio developer PowerShell with clang and lld on
`PATH`:

```powershell
py -3 -m venv .venv; .venv\Scripts\python -m pip install -r kit\requirements-dev.txt
.venv\Scripts\python tools\setup.py --install original\gog\app --link-only
.venv\Scripts\python tools\analyze.py --ghidra-home C:\path\to\ghidra_12.1.3_PUBLIC
.venv\Scripts\python tools\build.py --regenerate --jobs 8
$env:RECOMP_EXE = (Resolve-Path original\gog\app\Pharaoh.exe).Path
$env:RECOMP_GPU_VALIDATE = "1"
build\package\PharaohRecomp\PharaohRecomp.exe
```

The packager writes `build\package\PharaohRecomp\`, replacing the plan's
`build\windows\PharaohRecomp\`. Its `README.txt` also shows how to launch
from the package folder with `$env:RECOMP_EXE` set to the full path to your
original `Pharaoh.exe`. Keep it in the installation with all its data
directories; the package includes no game files. Keep `resources\` beside
the app.

Check the same Vulkan window, first mission and capture agreement as on
Linux, and record the GPU/driver and `RECOMP_GPU_VALIDATE=1` output. Watch
for guest paths containing `\` being handled against the host's own path
separator, especially game-data lookup and save/load. A confirmed separator
failure needs a kit `platform/os_win32.cpp` fix with a `platform_tests`
regression case; none has been observed or fixed in this task.

## Play on an Android tablet

**Build verified; device play unverified.** The real translation compiles
and packages for arm64-v8a, Android 10 (API 29) or later, with Vulkan 1.1
required. No Android device was attached for Task 7.3; installation, boot,
music, touch play and lifecycle behavior still need a tablet check.

First complete the game preparation and translation steps under
[Build on macOS](#build-on-macos). The Android preset uses the existing
`build/recomp/gen/`; do not pass `--stub` or regenerate for this build.
Install Android Studio, SDK platform 36, build-tools 37.0.0,
platform-tools and NDK 27.2.12479018. From this checkout on the development
Mac (adjust SDK paths on another machine):

```sh
export JAVA_HOME='/Applications/Android Studio.app/Contents/jbr/Contents/Home'
export ANDROID_HOME="$HOME/Library/Android/sdk"
export ANDROID_NDK_HOME="$ANDROID_HOME/ndk/27.2.12479018"
export PATH="$PWD/.venv/bin:$ANDROID_HOME/platform-tools:$PATH"
.venv/bin/python tools/build.py --target android
```

The APK is `build/android/app/build/outputs/apk/debug/app-debug.apk`;
the native library is `build/cmake/android/host/libmain.so`. With no
device, the build skips install and launch. Add `--no-install` to build
without device actions even when a tablet is connected.

Enable USB debugging, connect and authorize the tablet, then run:

```sh
adb devices
.venv/bin/python tools/build.py --target android --push-game --console
```

Use `--device <adb serial>` when more than one device is ready. This
command rebuilds as needed, installs the APK, stages `original/gog/app`
minus `[bundle].exclude` into `build/android/game`, pushes it, launches
the activity and streams logcat. An explicit `--push-game` fails when no
device is ready. The current install contributes 1,304 files / 605.360 MiB
plus an executable-hash `.stamp`; GOG support files, Windows libraries,
manuals and undecoded `BINKS` cinematics are excluded. The equivalent push
and launch commands, once staging exists and the APK is installed, are:

```sh
adb shell mkdir -p /sdcard/Android/data/dev.recompkit.pharaoh/files
adb push build/android/game /sdcard/Android/data/dev.recompkit.pharaoh/files/
adb shell am start -n dev.recompkit.pharaoh/dev.recompkit.RecompActivity
adb logcat
```

SDL supplies the app's external files path; the host expects
`game/Pharaoh.exe` beneath it and the loader still verifies the pinned
hash. Missing data logs the expected path and push instruction, then
exits. Android uses the pushed files directly; it does not copy a bundled
game or reseed on a stamp change. The default writable profile is
`/sdcard/Android/data/dev.recompkit.pharaoh/files/profile/`. Push does not
delete device files or that profile; retain a backup before uninstalling
the app or clearing its storage.

For a manual check, tap **Click to Start**, **Play Pharaoh/Cleopatra**,
create a new family, enter its name with the split keypad and press Return.
Choose **Begin Family History**, **Predynastic Period**, its **Begin**
arrow, and **Nubt → To the city**, then dismiss the housing tutorial.
Build houses, hold each screen edge to scroll, and long-press a building
for its right-click panel. Listen for music and effects, try Save/Load,
background and resume the app, and use the game's Quit command. The host
uses the shared touch mapper, pauses audio/presentation in the background,
and calls `exit(code)` after `SDL_Quit()` on normal guest shutdown.
These are implementation choices awaiting device verification.

To collect frame timings, put full `RECOMP_` names in external
`switches.txt`; `FRAME_TIMINGS` takes a CSV path, not a boolean:

```sh
cat > build/android-switches.txt <<'EOF'
RECOMP_FRAME_TIMINGS=/sdcard/Android/data/dev.recompkit.pharaoh/files/frame-timings.csv
EOF
adb push build/android-switches.txt /sdcard/Android/data/dev.recompkit.pharaoh/files/switches.txt
adb shell am force-stop dev.recompkit.pharaoh
adb shell am start -n dev.recompkit.pharaoh/dev.recompkit.RecompActivity
# After playing and quitting normally:
adb pull /sdcard/Android/data/dev.recompkit.pharaoh/files/frame-timings.csv build/android-frame-timings.csv
```

Record device/GPU, display mode, timing results, audible audio and touch
issues in the [run record](docs/analysis.md). A successful APK build alone
does not establish that the game boots or plays.

## Play on macOS

Press **fn+F10** to open the host settings page (F10 alone is a macOS system
shortcut). **Hold Escape** to release the mouse. Window mode, frame limit
and performance overlay are available; renderer controls appear only when
the port has a usable symbol table. Changes are saved in the active profile
and restored on relaunch.

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

After completing the preparation and translation steps above, use Xcode
with the iOS SDK, a developer team and a paired iPad running iPadOS 17 or
later. From this checkout, build without installing, then install and
launch separately. These are the commands for the development iPad; replace
the team and device identifiers for your own device:

```sh
xcrun devicectl list devices
set -o pipefail
.venv/bin/python tools/build.py --target ios --team BDFW2Z27HA \
  --device 15A75531-8976-580D-AF09-5DAA939FDF32 --console --no-install \
  2>&1 | tee build/ios-2.log | tail -30
```

Only after the build succeeds:

```sh
xcrun devicectl device install app \
  --device 15A75531-8976-580D-AF09-5DAA939FDF32 \
  build/ios/Release/PharaohRecomp.app
perl -e 'alarm 100; exec @ARGV' xcrun devicectl device process launch \
  --device 15A75531-8976-580D-AF09-5DAA939FDF32 --terminate-existing \
  --console dev.recompkit.pharaoh > build/ios-console-1.log 2>&1
```

The alarm bounds the console capture to 100 seconds; the recorded
`App terminated due to signal 14` is that timer, not an app fault. For hand
play, open the installed app from the iPad Home Screen. The bundle excludes GOG support
files, Windows DLLs, Miles plug-ins, manuals and `BINKS` cinematics (there
is no decoder). The current installation contributes **605 MiB** of game
files. The host copies the bundled game into writable `Documents/game`
when its executable or stamp is missing or the stamp differs; it replaces
that directory on a stamp change, so retain a copy of any saves before
updating to a different executable.

Taps click where the finger is, including near the top menu bar and bottom
sidebar buttons. Holding a finger on an edge scrolls; lifting it moves the
cursor back inside to stop scrolling. Task 9.3 verifies this in the native
touch tests; the iPad rebuild and device check remain pending in the
[run log](docs/analysis.md).

For a manual check, tap **Click to Start**, **Play Pharaoh/Cleopatra**,
then create a new family (choose **Create** if the Family Registry appears).
Use the on-screen keypad to enter a name and press Return, choose
**Begin Family History**, select **Predynastic Period** and its **Begin**
arrow, then enter **Nubt** using **To the city** and dismiss the housing
tutorial. The default keypad mode is `auto`, visible without a hardware
keyboard; its tabs collapse or expand each half. Try building houses,
holding a finger at each screen edge to scroll, and long-pressing a building
for its right-click information panel. Check that music plays and record
which actions work.

Task 5.1's automated install and launch are recorded in the
[run log](docs/analysis.md), including the presenter fallback fault.
That run included no hand input: the displayed title/main menu, audible
music and the checklist above were unverified. The first shell's compiler probe
used `arm64-apple-macos17.0` and the macOS SDK despite the iOS target; the
orchestrator built successfully from another shell. This is an environment
note, not a kit bug.

## Check a change

```sh
.venv/bin/python tools/test.py              # the kit's portable suites
.venv/bin/python -m pytest -q tests         # this game's config
.venv/bin/python tools/build.py --stub      # the kit configures against this config, no game code
```

Changes to the runtime, hosts or tools belong in the kit's repository; bump
the submodule here once they land.
