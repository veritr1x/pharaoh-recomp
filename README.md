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
export) and docs.

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
cinematics use Bink video, with unused Smacker imports. Cinematics play
through FFmpeg on macOS and on the iPad, where the intro plays from the
installed app. Android APKs include FFmpeg but have not run on a device.
Linux now defaults video ON; Windows enables it with MSYS2 tools and a
MinGW-compatible compiler. Neither platform's video build or playback has
been verified. Smacker refuses to open a video.
The measurements are in [docs/analysis.md](docs/analysis.md).

## Platform status

Status as of 2026-09-14, from the [run log](docs/analysis.md). Build
commands assume the game preparation and translation steps below; platform
sections give prerequisites and installation commands. A stub or package
build does not establish first-mission play.

| Platform | Verified status / first-mission play | Build command | Known issues and remaining checks |
| --- | --- | --- | --- |
| macOS 14+ | Cinematics decode through FFmpeg; intro smoke and headless audio capture pass. Earlier smoke reaches the title, menu and an advancing first mission; WAV effects work. The app shows the title and captures non-silent music. | `.venv/bin/python tools/build.py` (app); `.venv/bin/python tools/build.py --target smoke` | Shutdown SIGSEGV at `0x0056478f` remains open. Hand play is untested; the automated app click did not advance the title. Smoke music streaming is unverified. |
| iPadOS 17+ | Plays by touch on an iPad Pro: the intro cinematic runs through the embedded FFmpeg dylibs, the front end and the first mission run at 800x600 with music, taps click where the finger is and the minimap moves the camera to the tapped spot (kit `4ab4604`). | `.venv/bin/python tools/build.py --target ios --team <TEAM_ID> --no-install` | Hardware keyboard and trackpad also work. Manual save/load is untested on the device. At 800x600 only the left and top screen edges scroll (see the iPad section). |
| Linux | Host/tooling checks only on macOS; packager tests use fake binaries. Never built or run on Linux; first mission unverified. | `.venv/bin/python tools/build.py --regenerate --jobs 8` | Native package, Vulkan window/driver validation and gameplay remain untested. |
| Windows | Host/tooling checks only on macOS; packager tests use fake binaries. Never built or run on Windows; first mission unverified. | `.venv\Scripts\python tools\build.py --regenerate --jobs 8` | Native package, Vulkan validation, guest path separators and gameplay remain untested. |
| Android 10+, arm64, Vulkan 1.1 | Stub and real-translation APKs contain all three FFmpeg libraries; ELF dependencies pass. No device was attached; never run, first mission unverified. | `.venv/bin/python tools/build.py --target android` | Install, boot, cinematics, music, touch and lifecycle behavior await a device. Existing NDK/CMake and Gradle warnings remain. |

### macOS smoke evidence

`smoke/intro.script` captures the moving intro at 2, 6 and 12 seconds,
presses Return to skip and captures the Cleopatra title four seconds later.
All 6 steps pass. The headless host's 35-second intro audio capture contains
34.7 seconds of non-silent audio, with a peak near full scale; the smoke host
lacks streaming audio. The menu smoke was rerun with an intro skip in
Task 10.4; the campaign recording below predates FFmpeg intro playback.

`smoke/main-menu.script` waits four seconds, presses Return for 100 ms to
skip the intro and waits eight seconds before capturing the 640x480
Cleopatra title screen with
“Click to Start”, clicks its centre, and captures the five-button main menu
four seconds later and again after another two seconds. Both menu captures
are identical. The Task 10.4 rerun passes all 6 steps in 18.1 seconds,
presents 393 frames and exits through `ExitProcess(0)`. Miles WAV effects
reach the smoke host's mixer; the effects
run records the title-screen click at peak 0.782. In the headless host, the
title-screen MP3 capture contains 24.092 seconds of audio, 23.8 seconds
non-silent, with no logged underrun. The smoke host lacks streaming
callbacks, so these smoke runs do not verify music. Task 4.2 also records
38.0 seconds of non-silent music in the interactive app's mixer capture.

`smoke/first-mission.script` uses the same intro skip, then enters a new
family name, starts the Predynastic
campaign, opens the Nubt briefing and dismisses the housing tutorial. Its
two timed city captures show moving animals and an advancing date. The
eight-round run record, every screen's capture path and the remaining
limits are in [docs/analysis.md](docs/analysis.md). The game created profile
autosaves; **saving through the menu and reloading remain unverified**.
The updated first-mission script has not been rerun. Housing construction
and human walkers remain unverified. The interactive
macOS app displays the title screen, but its automated click did not advance
it, and quitting ended with a host fault; see the Task 4.2 run record.

The pinned kit includes Miles shims (41
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
- Bink cinematics play through FFmpeg on macOS and the iPad. Android
  includes FFmpeg but has not run on a device. Linux defaults video ON; Windows requires MSYS2 bash/make and a
  MinGW-compatible compiler, otherwise video stays OFF. Native video
  builds and playback on Linux/Windows remain unverified. `BINKS/` is included in
  bundles and staged data, adding about **140 MiB**. Smacker remains refused;
  see the [cinematics decision](docs/analysis.md#cinematics-decision-task-81).
- Manual Save/Load remains unverified; profile autosaves do not establish
  that saving through the menu and reloading work.
- iOS configure fails from some shells: the compiler probe targets
  `arm64-apple-macos17.0` with the macOS SDK. A plain interactive shell
  builds successfully; the environment override behind the failing shell
  remains unidentified.
- The game scrolls the map while the pointer rests on a screen edge, and it
  measures the screen once per resolution change, before it sets the new
  mode, as Windows does. The kit reports a 1024x768 desktop between modes,
  so at 800x600 only the left and top edges scroll; choose 1024x768 in the
  game's own settings for all four. The stale-mode variant of this, which
  made every tap in the right or bottom part of an 800x600 city scroll the
  camera to the map's edge, was fixed in kit `4ab4604`.

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

`RECOMP_VIDEO` now defaults ON. The first build downloads the pinned
FFmpeg source and builds shared libraries with the native C compiler and
`--enable-pic`; the packages below already supply make and the compiler,
so no FFmpeg development package is needed. The app's rpath includes
`$ORIGIN`; the packager places `libavformat.so.61`, `libavcodec.so.61` and
`libavutil.so.59` beside it and includes `resources/ffmpeg-NOTICE.md` in
the folder and tarball. Keep these libraries with the app. CMake branches
were reviewed and fake-file packaging tests passed on macOS; Linux
compilation, shared-library loading and cinematic playback remain unverified.
An existing Linux CMake cache with video OFF needs `-DRECOMP_VIDEO=ON`
once: from `kit/`, with the venv on `PATH`, run
`cmake --preset linux -B ../build/cmake/linux -DRECOMP_VIDEO=ON`.
Use OFF in the same command to disable video.

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

Windows CI explicitly sets `-DRECOMP_VIDEO=OFF`. For local video builds,
CMake looks for MSYS2 `bash` and GNU `make` on `PATH`; video defaults ON
only with both tools and a MinGW-compatible compiler. Missing tools or an
MSVC-ABI compiler keep it OFF with a status message. `--toolchain=msvc`
and clang-cl FFmpeg builds are out of scope, so the Visual Studio workflow
below remains video OFF. Enabling video requires a matching MinGW clang
toolchain for the entire kit. The enabled packaging path copies
`avformat-61.dll`, `avcodec-61.dll`, `avutil-59.dll` beside the app and
includes `resources/ffmpeg-NOTICE.md`. These branches were reviewed and
staging tested with fake files on macOS; Windows video compilation, DLL
loading and cinematic playback remain unverified.

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
cinematics, music, touch play and lifecycle behavior still need a tablet check.
Task 10.3 verifies the stub and real APKs with dynamically linked FFmpeg:
`libavformat.so`, `libavcodec.so` and `libavutil.so` sit beside `libmain.so`
under `lib/arm64-v8a/`. The first build fetches and cross-builds FFmpeg;
the APK also carries `assets/ffmpeg-NOTICE.md`.

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
device is ready. GOG support files, Windows libraries and manuals are
excluded; `BINKS` cinematics are retained for playback on hosts with FFmpeg.
The equivalent push and launch commands, once staging exists and the APK
is installed, are:

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
create a new family, enter its name with the on-screen keyboard (the pad's
**KEYS** tab, or **Select** for the system keyboard) and press Return.
Choose **Begin Family History**, **Predynastic Period**, its **Begin**
arrow, and **Nubt → To the city**, then dismiss the housing tutorial.
Build houses, scroll with the pad's left stick, and long-press a building
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
launch separately. `<TEAM_ID>` is your Apple developer team identifier and
`<DEVICE_ID>` the iPad's identifier from the first command:

```sh
xcrun devicectl list devices
set -o pipefail
.venv/bin/python tools/build.py --target ios --team <TEAM_ID> \
  --device <DEVICE_ID> --console --no-install \
  2>&1 | tee build/ios.log | tail -30
```

Only after the build succeeds:

```sh
xcrun devicectl device install app \
  --device <DEVICE_ID> \
  build/ios/Release/PharaohRecomp.app
perl -e 'alarm 100; exec @ARGV' xcrun devicectl device process launch \
  --device <DEVICE_ID> --terminate-existing \
  --console dev.recompkit.pharaoh > build/ios-console.log 2>&1
```

There is no downloadable IPA: the app bundle carries your own game files,
so it can only be built from a checkout with the game installed and signed
with your own team. A development install expires after seven days on a
free Apple account and after a year on a paid one; rebuild to renew it. If
the device shows as `unavailable` right after it is connected or unlocked,
wait a few seconds and retry.

The alarm bounds the console capture to 100 seconds; the recorded
`App terminated due to signal 14` is that timer, not an app fault. For hand
play, open the installed app from the iPad Home Screen. The bundle excludes GOG support
files, Windows DLLs, Miles plug-ins and manuals. It retains `BINKS`
cinematics; the current installation contributes about **745 MiB** of game
files. The host copies the bundled game into writable `Documents/game`
when its executable or stamp is missing or the stamp differs; it replaces
that directory on a stamp change, so retain a copy of any saves before
updating to a different executable.

FFmpeg's three dylibs are built for arm64/iOS 17 and embedded through
Xcode's signed Embed Frameworks phase, under `Frameworks/` with the app
rpath `@executable_path/Frameworks`. The intro cinematic plays on the
device from the installed app.

Taps click where the finger is, including the top menu bar, the sidebar
buttons and the minimap. Holding a finger on an edge scrolls; lifting it
moves the cursor back inside to stop scrolling. A long press is a right
click, a drag after a long press scrolls the map, two fingers pan, a
two-finger tap is a right click and a three-finger tap opens the settings page.
The [run log](docs/analysis.md) records the device checks.

For a manual check, tap **Click to Start**, **Play Pharaoh/Cleopatra**,
then create a new family (choose **Create** if the Family Registry appears).
Use the on-screen keypad to enter a name and press Return, choose
**Begin Family History**, select **Predynastic Period** and its **Begin**
arrow, then enter **Nubt** using **To the city** and dismiss the housing
tutorial. Try building houses, scrolling the map, and long-pressing a
building for its right-click information panel. Check that music plays and
record which actions work.

Without a hardware keyboard the on-screen controls start on the **pad**,
which `layouts/pad.tablet.json` keeps on the left of the screen so that the
minimap and the build menu stay clear. Its **KEYS** tab switches to the
split keyboard (for the family name and save names, which the pad's
**Select** also reaches through the system keyboard), and **F10** opens the
settings page, where the layout, its size and opacity, and **Edit
controls** live. The pad presses the game's own keys: the sticks and the
dpad scroll with the arrow keys, ✕ and ○ are left and right click, □ pauses,
**L1**/**R1** move the game speed, △ and **L2** jump to the F1 and F2
viewpoints, and **R2** held is Ctrl — the game's 8x scroll, and what turns
△ and **L2** into "save this viewpoint". `[controls]` in `game.toml` is the
whole table, and `docs/analysis.md` records the keys it came from.

The steps through entering Nubt and playing the first mission have been
done by hand on an iPad Pro; manual save and load on the device have not.
`RECOMP_*` switches for a device with no shell go in the app's
`Documents/switches.txt`, and `tools/ios_logs.py --device <DEVICE_ID>` pulls
the app's Documents folder, including frame dumps, to `build/ios-pull`.

## Check a change

```sh
.venv/bin/python tools/test.py              # the kit's portable suites
.venv/bin/python -m pytest -q tests         # this game's config
.venv/bin/python tools/build.py --stub      # the kit configures against this config, no game code
```

Changes to the runtime, hosts or tools belong in the kit's repository; bump
the submodule here once they land.
