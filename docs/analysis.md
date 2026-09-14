# Port analysis

What Pharaoh Gold needs from the kit, measured on 2026-09-13 from the GOG
offline installer `setup_pharaoh_gold_2.1.0.15.exe` (511,861,792 bytes)
extracted with innoextract 1.9. This is the `analyze` stage of the kit's
design (its section 3.2) done by hand, since the kit's `analyze` command is
milestone M2 work. Keep this file true as the bring-up moves.

## The executable

The installer's game directory (`app/` in the extraction, 777 MB) holds one
executable, which the GOG launcher (`goggame-1207659046.info`) starts with no
arguments.

| | `Pharaoh.exe` |
| --- | --- |
| Version resource | Pharaoh 2.1.0.0, Sierra, © Sierra 1999,2000 |
| Size, link timestamp | 2,142,208 bytes, 2000-08-28 |
| Linker | Microsoft 6.0 (Visual C++ 6), C runtime linked statically (no `MSVCRT` import) |
| Graphics | **DirectDraw** (`DirectDrawCreate`) plus GDI text |
| Sound | **Miles Sound System** (`mss32.dll`, 41 imports) |
| Video | **Bink** (`binkw32.dll`, 12 imports) and **Smacker** (`smackw32.dll`, 7), both linked at import time, not loaded by name |
| Network | none |
| Image base, entry point | `0x00400000`, `0x00562fea` |
| Relocations, TLS | none, none |
| SHA-256 | `b21b7d719491bb45dfb324ba95231a5b0960ab25fea1bf3fb21da65da7eca662` |

| | |
| --- | --- |
| Sections | `.text` 1.4 MB code (`0x00401000`, 0x16d24d bytes), `.rdata` 0x61a6, `.data` 0xcf1aa8 (13.6 MB, of which 0xc61aa8 uninitialised: the game's world arrays are static), `.rsrc` 0x4590 |
| Packing, protection | none: plain Visual C++ 6 code with statically linked CRT |
| Sentinel padding | `.rsrc` ends at `0x0126c590` and the image at `0x0126d000`; the 2,672 bytes between are zero in the file and never referenced. `game.toml` parks its unidentified hooks and globals in the last 512 (`0x0126ce00`-`0x0126cfff`). |
| Settings | `Pharaoh.ini` at the guest root (`CDDrive=G`, `RAM=-1`, `CPU=2810` as GOG ships it); `Language.inf` and `Pharaoh.inf` name the title; the game also looks for a `sierra.ini` ("Err:Could not read sierra.ini") |
| Saves | `save\*.sav` (`autosave.sav`, `autosave_history.sav`, `autosave_replay.sav`, `last.sav`, rank-named saves) and `save\highscore.jas`, relative to the guest root; `Save\*.dat` is enumerated too |

Ghidra's default analysis of the executable is what `tools/analyze.py`
exports (`analysis/decompiled/Pharaoh.exe/summary.txt` gives the counts).

## Import surface

This is the initial import inventory; the Phase 2-3 run records below
document the later shim implementations and their verification.

197 imports across 10 DLLs. "Shimmed" counts the imports the kit's shim
tables (`runtime/`, `dx/`, `host/`) name as of kit main c2b4e93; the rest
bind to the kit's logging trampolines, which return 0 and pop only the
return address, so a missing stdcall import drifts the guest stack when it
is reached.

| DLL | Imports | Shimmed | Missing, and what the gaps are |
| --- | --- | --- | --- |
| `KERNEL32` | 81 | 79 | `GetDiskFreeSpaceA` (the save-directory space check), `GetSystemDirectoryA` |
| `USER32` | 45 | 35 | `GetMenu`, `WaitMessage`, `FindWindowA` and `OpenIcon` (the single-instance check), `SystemParametersInfoA`, `GetMessagePos`, `GetMessageTime`, `SetForegroundWindow`, `SetActiveWindow`, `IsIconic` |
| `GDI32` | 6 | 3 | `GetTextExtentPointA`, `GetDeviceCaps`, `SetBkColor`; `TextOutA`, `GetPaletteEntries` and `GetStockObject` are served |
| `SHELL32` | 1 | 1 | `ShellExecuteA` |
| `ole32` | 2 | 2 | `CoInitialize`, `CoUninitialize` |
| `DDRAW` | 1 | 1 | `DirectDrawCreate` |
| `WINMM` | 1 | 1 | `timeGetTime` |
| `mss32` | 41 | 0 | the whole Miles Sound System 6 API the game uses: `AIL_startup`/`AIL_shutdown`, `AIL_set_preference`, `AIL_waveOutOpen`, sample handles (`AIL_allocate_sample_handle`, `AIL_init_sample`, `AIL_set_sample_file`, `AIL_start_sample`, `AIL_end_sample`, `AIL_sample_status`, volume, pan, loop count, reverb), streams (`AIL_open_stream`, `AIL_start_stream`, `AIL_stream_status`, `AIL_set_stream_volume`, `AIL_set_stream_loop_count`, `AIL_close_stream`: the MP3 music), 3D providers (`AIL_enumerate_3D_providers`, `AIL_open_3D_provider`, `AIL_3D_provider_attribute`, 3D sample handles, position, orientation), `AIL_file_read`, `AIL_mem_free_lock` |
| `binkw32` | 12 | 0 | `BinkOpen`, `BinkOpenMiles`, `BinkSetSoundSystem`, `BinkDDSurfaceType`, `BinkDoFrame`, `BinkNextFrame`, `BinkWait`, `BinkCopyToBuffer`, `BinkService`, `BinkGetError`, `BinkClose`, `BinkBufferClose` |
| `smackw32` | 7 | 0 | `SmackOpen`, `SmackSoundUseMSS`, `SmackDoFrame`, `SmackNextFrame`, `SmackWait`, `SmackToBuffer`, `SmackClose` |

122 of 197 imports are shimmed. The Windows gaps (15 functions) are
run-report items in the kit's `runtime/`. The three third-party DLLs are
the port's real work:

- **Miles Sound System** is every sound the game makes. The kit has a
  precedent for shimming a third-party audio DLL by its import names (the
  `qmixer.dll` table Populous needed, 28 entries); an `mss32` shim file that
  maps samples onto the kit's mixer channels and streams onto its streaming
  path (the MP3 decoding the kit added for Majesty's DirectShow music
  applies) is the shape. The 3D provider calls can report no providers.
- **Bink and Smacker** play the intro and the campaign cinematics
  (`BINKS/High/*.bik`, 140 MB; no Smacker files ship, so the Smacker imports
  may be dead code). Until a decoder exists a stub that fails `BinkOpen`
  lands on the game's own "Unable to load BINK!" path, which needs checking
  for how the game continues.

## Graphics: inside the envelope

The game creates its DirectDraw object with `DirectDrawCreate` and none of
the DirectDraw interface IIDs (`IDirectDraw2`, `4`, `7`, the surface
versions, clipper, palette, gamma) appear in the image, so it drives the
version-1 `IDirectDraw` and `IDirectDrawSurface` interfaces the create call
returns, without `QueryInterface`. That is the oldest path the kit's
`dx/ddraw.cpp` serves. Its log strings describe the setup: `OK :GFX
DirectDraw enabled.`, `ERR:DD SetMode failed err :` followed by
`ERR:Trying default display mode`, `ERR:GFX couldn't create flipping
surface.` (a page-flipping primary with a back buffer), `ERR:DD Cant set
clipper window handle.` (a clipper, so a windowed mode exists) and `Old
res=%d,%d; Color mode=%d`. Which resolutions and depths the game offers is a
question for the listings; the sprite archives are `.555` files (16-bit
5:5:5 pixels, 220 of them beside 175 `.sg3` indexes in `Data/`), so 16 bpp
is the working assumption.

GDI is text only: `TextOutA`, `GetTextExtentPointA`, `SetBkColor` and
`GetStockObject`, plus `GetDeviceCaps` and `GetPaletteEntries` at setup.
The cursor is the system cursor (`LoadCursorA`, `SetCursor`, `ShowCursor`),
so the kit's host-drawn pointer hook has no DirectDraw surface to point at.

## Sound, video, time, input

- **Sound** goes through Miles (above). `AUDIO/` holds 193 MP3 files
  (`Music/`, named in the executable as `200_mission.mp3`,
  `200_victory.mp3`, `200_mission_classic.mp3` and so on) and 637 WAVs
  (`Ambient/`, `Voice/`, `Wavs/`). The music path is built as
  `%c:\audio\music\%s` with a drive letter, and `Pharaoh.ini` carries
  `CDDrive=G`, so how the GOG build finds `AUDIO/Music/` under the install
  directory (a fallback, or the letter of the install drive) is a question
  for the listings and for the kit's drive mapping.
- **Video** is Bink through `BinkOpenMiles` and `BinkDDSurfaceType` (the
  decoder blits into a DirectDraw surface of the primary's format); the
  `.bik` files are the intro and six campaign cinematics.
- **Time** is `timeGetTime` plus `GetTickCount`, `QueryPerformanceCounter`
  and `QueryPerformanceFrequency`; the kit's frame-clock hook identifies
  draw-loop waits by `GetTickCount` return addresses. Task 4.2 verifies
  that the main-loop draw gate instead uses `timeGetTime` and normally
  admits a draw every 50 ms, so all five frame-clock hooks stay sentinels.
- **Input** is user32: `GetCursorPos`, `GetAsyncKeyState`, `GetMessagePos`
  and window messages. No DirectInput, so the kit's `mouse_*` hooks (a
  DirectInput device object) will never be real for this game; the touch
  mapper would attach to the message pump, as it does for Majesty.
- **Network**: none. The game has no multiplayer.

### Cinematics decision (Task 8.1)

Task 8.1 kept cinematics skipped and excluded `BINKS` from bundles and
staged game data while the decoder integration was undecided. **Task 10.2
supersedes that decision:** the kit now decodes Bink through the dynamically
linked FFmpeg dependency introduced in Task 10.1, and `BINKS` is retained.
The bundle test now keeps `BINKS/High/intro_big.bik` alongside the executable,
model text, graphics, audio and maps. The seven videos add the **146,718,084
bytes / 139.921 MiB** measured in Task 5.1; the previous staged-data totals
were **745.282 MiB** with them and **605.360 MiB** without them.

Cinematics play through FFmpeg on macOS. Task 10.3 packages FFmpeg in both
Android APK variants and verifies its standalone arm64/iOS 17 cross build;
mobile playback remains unverified. Task 10.4 defaults Linux video ON and
enables Windows video with MSYS2 bash/make and a MinGW-compatible compiler;
their native builds and playback remain unverified. Windows CI and builds
without the required tools/compiler stay video OFF and return a finished
Bink record. Smacker remains refused everywhere
(no Smacker files ship).
Keep the complete original installation, including `BINKS`, as the setup
input. The smoke and headless evidence and its limits are recorded below.

## Data

| Directory | Size | |
| --- | --- | --- |
| `Data` | 289 MB | 220 `.555` sprite archives and 175 `.sg3` indexes |
| `AUDIO` | 273 MB | 193 MP3 tracks, 637 WAV effects, ambience and speech |
| `BINKS` | 140 MB | 7 Bink cinematics (`High/`; no `Low/` set ships) |
| `Maps` | 24 MB | 33 `.map` scenarios with 13 `.txt` briefings |
| root | 20 MB | `mission1.pak` (17 MB, the campaigns), `Pharaoh2.emp` (the empire map), `Pharaoh_Text.eng`/`Pharaoh_MM.eng` (strings), the difficulty models (`Pharaoh_Model_*.txt`, `Figure_model_*.txt`, `Tax_Sentiment_Model_*.txt`), `campaign.txt`, `eventmsg.txt`, `music.txt`, `Pharaoh.ini` |
| excluded | 15 MB | `mss32.dll`, `mss16.dll`, the `MSS*.M3D` providers, `MP3DEC.ASI`, `mssb16.tsk`, `BINKW32.DLL`, `SMACKW32.DLL`, `goggame-*.dll/.hashdb/.info/.ico`, `GameuxInstallHelper.dll`, `webcache.zip`, the four PDF manuals, `Readme.txt` |

The model `.txt` files are read at boot (`ERR:No Pharaoh_model.txt file`,
`ERR:Exited Pharaoh, could not load model.`), so `*.txt` must stay in the
bundle; `tests/test_game_config.py` checks that. Paths inside the
executable are relative to the guest root and mixed case (`Binks\high\`,
`binks\high\`, `save\`, `Save\`); the kit's case-folded path index handles
that.

## Translation

The kit's translator reads Ghidra listings and emits one C function per
original function. `tools/analyze.py` exports them with Ghidra's default
analyzers. The translator's own coverage report,
`build/recomp/translate-report.json`, is the record of unsupported
instructions and unresolved indirect targets once a run gets far enough to
write it.

### Run log

Recorded runs of the pipeline against this executable, newest first.

#### 2026-09-14: Task 10.4 Linux/Windows FFmpeg configuration and intro-skipping smoke

Started with clean game `main` at `97a5d4d` and kit `pharaoh` at `11c97a7`.
This task changes desktop dependency configuration, packaging, CI and docs,
plus the two boot smoke scripts. No runtime, translator, addresses or game
inputs changed. Kit changes are committed on `pharaoh` as `86bf512` and
re-pinned here; neither repository was pushed.

- `kit/cmake/Dependencies.cmake` defaults Linux video ON, configures FFmpeg
  with the native C compiler and the common `--enable-pic`, and imports
  `libavformat.so.61`, `libavcodec.so.61`, `libavutil.so.59`.
- On Windows, `find_program` checks for bash and make on PATH. Missing
  tools or an MSVC-ABI compiler force video OFF with a status message.
  With both tools and a MinGW-compatible compiler, video defaults ON;
  explicit OFF is retained. The configure uses `--target-os=mingw32`,
  imports versioned DLLs from `ffmpeg/bin` and `.dll.a` files from
  `ffmpeg/lib`. `--toolchain=msvc`/clang-cl builds remain out of scope.
  Filenames and installation directories were checked against the local
  pinned FFmpeg 7.1.1 configure script's MinGW branch.
- `kit/host/CMakeLists.txt` adds the Linux app's `$ORIGIN` rpath, retaining
  CMake's automatic build-tree paths for local runs. `kit/tools/build.py`
  passes the selected build directory to `package_desktop.stage`; staging
  reads that cache's video flag and copies the three shared libraries
  beside the executable with `resources/ffmpeg-NOTICE.md`. Linux SONAME
  symlinks become regular files in the package. OFF removes only managed
  video files, including the notice, while retaining player files; the
  tarball includes only the current staging manifest.
- The Linux CI package list is unchanged; existing build-essential builds
  FFmpeg from source. Windows CI explicitly configures video OFF. The kit
  README, CONTRIBUTING, FFmpeg notice and changelog, and the game's Linux
  and Windows README sections document the requirements and limits.
- `smoke/main-menu.script` and `smoke/first-mission.script` replace the
  initial 15-second wait with `wait 4000`, Return down, `wait 100`, Return
  up, `wait 8000`, before the first title dump. The intro's logged 3,282
  frames at 24 fps would otherwise take **136.75 seconds**.

Verification on macOS (all commands below exited **0**):

```sh
.venv/bin/python -m pytest -q kit/tools/tests/test_package_desktop.py
.venv/bin/python tools/test.py
.venv/bin/python tools/build.py --target smoke --jobs 8
.venv/bin/python -m pytest -q tests
.venv/bin/python kit/tools/format.py --write
.venv/bin/python kit/tools/check_game_literals.py
```

The focused packaging suite reports **17 passed**, including four new
Linux/Windows cases covering installed fake libraries, symlinks, notices,
OFF cleanup, preserved saves and missing-library failure. Its build-driver
cases verify that staging receives the selected CMake directory. The full
portable suite reports **123 passed, 3 skipped**. Game config tests report
**4 passed**. Formatting processes **243** handwritten source files with
no unrelated changes. The smoke build completes, rebuilding FFmpeg with
**30 compiler/linker warning diagnostics**, zero error diagnostics.

From `kit/`, configured the existing stub tree OFF, then ON (restoring its
initial ON setting):

```sh
../.venv/bin/cmake --preset macos-stub -DPython3_EXECUTABLE=/Users/sattam.thakur/Documents/Tests/pharaoh-recomp/.venv/bin/python -DRECOMP_VIDEO=OFF
../.venv/bin/cmake --preset macos-stub -DPython3_EXECUTABLE=/Users/sattam.thakur/Documents/Tests/pharaoh-recomp/.venv/bin/python -DRECOMP_VIDEO=ON
```

Both configure/generate steps exit **0**. Read-only cache/build-graph checks
pass **3 assertions** for OFF (cache, absent FFmpeg target and decoder
definition) and **6 assertions** for ON (cache, target, decoder definition
and three imported dylib names). These are macOS configurations, not
execution of the Linux/Windows branches. Those branches and CI were
reviewed by reading; no Python platform-decision code was introduced.

The main-menu smoke used a fresh profile and registry under ignored
`build/task-10.4-main-menu-izm6gihk`, with a 90-second subprocess timeout:

```sh
RECOMP_PROFILE_DIR="$PWD/build/task-10.4-main-menu-izm6gihk/profile" \
RECOMP_REGISTRY="$PWD/build/task-10.4-main-menu-izm6gihk/registry.json" \
RECOMP_SCRIPT="$PWD/smoke/main-menu.script" \
RECOMP_HOST_DUMP_DIR="$PWD/build/task-10.4-main-menu-izm6gihk" \
RECOMP_DDRAW_MODES=640x480x16 RECOMP_SMOKE_DRAWABLE=1024x768 \
build/recomp/pop_smoke
```

The smoke exits **0**, guest `ExitProcess(0)`, **6/6 steps**, **18.1 seconds**,
**393 presented frames**, no undeliverable calls. Visually inspected the
640x480 `smoke_title-screen_present.ppm` (Cleopatra, Click to Start) and
`smoke_main-menu_present.ppm` (five-button menu). The settled menu dump is
byte-identical to the first menu. Title/menu have **5,507 / 9,041 distinct
colours**; their SHA-256 values are respectively
`3d9680ceef583a029ba1df936ed5218dc59428633396a4819ed700d506ba585b` and
`62e1f0e5c9d1c5cd6b6cc91ee3612433b42983a3534781d04369a1f3f287839f`.
The existing mod-loader failure, forced 16-bit-mode warning, undrawn
TextOutA and unavailable Bink streaming audio are still logged. This smoke
does not establish music/intro audio playback or campaign play.

Additional read-only assertions confirm the pinned executable's SHA-256,
image base and entry point (**3 passed**). Both repository diff whitespace
checks and the staged kit's `tools/check_repo.py` pass, exit **0**. Logs,
captures and scratch profiles remain ignored under `build/`.

**Not run:** Linux/Windows native configurations or builds, their ELF/DLL
loading and cinematic playback, remote CI, and the updated first-mission
script. Native CTest suites were not needed for these build/packaging
changes and were not run. The existing runtime baseline is not reassessed.
No translation regeneration was needed: `runtime/x86.h` is unchanged.

#### 2026-09-14: Task 10.3 cross-builds FFmpeg for Android and iOS

Started with clean game `main` at `d1e559a` and kit `pharaoh` at `e46dc77`.
Committed the kit changes on `pharaoh` as `c79585b` and re-pinned here.
Only this task's build configuration, packaging and docs changed. No runtime,
translator, game address or executable identity changed; SHA-256, image base
and entry point were rechecked and match the pinned identity above.

- `kit/cmake/Dependencies.cmake` defaults video ON for macOS, iOS and
  Android. Android uses the selected NDK's API-29 arm64 compiler, LLVM tools,
  NDK sysroot and `--disable-symver`; imported libraries use the installed
  unversioned `.so` names and SONAMEs. iOS uses the iPhoneOS clang/sysroot,
  arm64/iOS 17 compile and link flags, and `@rpath` install names. All three
  Apple-framework disable flags are accepted on both mobile targets and
  remain in the common isolation flags. No configure flag had to be dropped.
- `kit/cmake/IosBundle.cmake` uses imported targets in Xcode's **Embed
  Frameworks** phase with `XCODE_EMBED_FRAMEWORKS_CODE_SIGN_ON_COPY=YES`,
  supported since CMake 3.20 (kit minimum 3.24; installed 4.1.2). This is the
  task's alternative to explicit post-build copy/codesign commands. The app
  uses `@executable_path/Frameworks` and carries the notice at its bundle root.
  Actual embedding and team signatures are **not yet verified**.
- `kit/tools/build.py::android_apk` stages the three FFmpeg libraries beside
  `libmain.so` and copies the notice to APK assets. It reads the configured
  video option and removes those generated copies when video is OFF.
  `--push-game` is unchanged. No change to the Gradle template was needed.
- `kit/third_party/ffmpeg/NOTICE.md` records each platform's configure flags,
  library naming, packaging and replacement workflow, preserving the LGPL
  text. Both READMEs and changelogs describe the measured mobile state.

Android verification, in order, from the game repository:

```sh
export ANDROID_NDK_HOME=/Users/sattam.thakur/Library/Android/sdk/ndk/27.2.12479018
export ANDROID_HOME=/Users/sattam.thakur/Library/Android/sdk
export JAVA_HOME='/Applications/Android Studio.app/Contents/jbr/Contents/Home'
export PATH="$PWD/.venv/bin:$ANDROID_HOME/platform-tools:$PATH"
.venv/bin/python tools/build.py --target android --stub
.venv/bin/python tools/build.py --target android
```

Both exited **0**, including fresh FFmpeg downloads/configures/builds, in
**29.77 / 26.10 seconds** (stub / real). Each log has **42 compiler warning
diagnostics, zero error diagnostics**. After updating the notice, repeated
both commands in the same order: **exit 0**, **2.00 / 2.23 seconds**. Gradle
reported **36 tasks** each time: **6 executed / 30 up-to-date** for the stub,
**4 / 32** for the real APK. The existing CMake/NDK and Gradle deprecation
warnings remain. Gradle could not strip the four native libraries and
packaged them as-is; neither `useLegacyPackaging` nor `keepDebugSymbols`
was required for a successful package.

The packager writes both variants to
`build/android/app/build/outputs/apk/debug/app-debug.apk`; each was copied
before the next build to ignored `build/task-10.3/android-{stub,real}.apk`.
The final shared output is the real APK. Final sizes: **78,316,279 bytes**
(stub), **180,631,967 bytes** (real). For each variant:

```sh
unzip -l build/task-10.3/android-stub.apk 'lib/arm64-v8a/*' 'assets/ffmpeg-NOTICE.md'
unzip -l build/task-10.3/android-real.apk 'lib/arm64-v8a/*' 'assets/ffmpeg-NOTICE.md'
"$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/darwin-x86_64/bin/llvm-readelf" -d build/cmake/android-stub/host/libmain.so
"$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/darwin-x86_64/bin/llvm-readelf" -d build/cmake/android/host/libmain.so
```

All exited **0**. Each APK has exactly **4 arm64 libraries**: `libmain.so`,
`libavformat.so`, `libavcodec.so`, `libavutil.so`. Both `libmain.so` files
list all three FFmpeg names as `NEEDED`. FFmpeg installs exactly those
three unversioned `.so` files; `llvm-readelf -h -d` confirms AArch64, matching
SONAMEs and dependencies only on siblings, `libm.so` and `libc.so`.
Byte comparisons confirm every packaged library equals its CMake output
and the packaged notice equals the updated source notice. All **35 files**
in `build/recomp/gen/` have unchanged SHA-256 hashes; the real Android build
reused the translation. No Android device was attached: all four builds
explicitly skipped install, launch and logcat. No `--push-game` was run.

For iOS, ran `/bin/sh build/task-10.3/build-ios-ffmpeg.sh`: **exit 0,
13.90 seconds**, including the exact iOS configure arguments now documented
in the kit's FFmpeg notice, `make -j8` and `make install`. It uses the
hash-verified ExternalProject source from the Android build, with a separate
working directory `build/task-10.3/ios-ffmpeg-build` and prefix
`build/task-10.3/ios-ffmpeg`. The compiler is `xcrun -sdk iphoneos clang`;
`xcrun -sdk iphoneos --show-sdk-path` supplied the **iPhoneOS 26.5 SDK**.
There are **30 upstream compiler warning diagnostics, zero errors**.

For each of `libavformat.61.dylib`, `libavcodec.61.dylib` and
`libavutil.59.dylib` under that prefix, `lipo -info`, `otool -L` and
`otool -l` exited **0**. All three are **arm64**, with `LC_BUILD_VERSION`
platform **2 (iOS)** and minimum **17.0**. Their own install names and
cross-library references are `@rpath/libav*.dylib`. External dependencies
are only `/usr/lib/libSystem.B.dylib` and Apple's CoreFoundation, CoreVideo
and CoreMedia frameworks. No macOS/Homebrew dependency is present.

Then, from `kit/` with the venv on PATH, ran:

```sh
cmake --preset ios-stub -DPython3_EXECUTABLE=/Users/sattam.thakur/Documents/Tests/pharaoh-recomp/.venv/bin/python
```

**Exit 1, 3.77 seconds**, before kit dependency configuration. CMake reports
no C/C++ compiler. `kit/build/cmake/ios-stub/CMakeFiles/CMakeConfigureLog.yaml`
shows the known Xcode probe error: `invalid version number in '-target
arm64-apple-macos17.0'`, with the **MacOSX26.5 SDK** despite the iOS preset.
Stopped this route as explicitly instructed; did not run
`tools/build.py --target ios`. The orchestrator still needs the iOS app
build, `codesign -dv` on the actual embedded dylibs, app signature validation
and a device launch/playback check. Standalone FFmpeg success does not prove
Xcode embedding, signing, app linking or playback.

Additional verification:

- `.venv/bin/python -m pytest -q kit/tests/test_build_py.py kit/tools/tests/test_build.py tests`:
  **34 passed, exit 0** (including all 4 game config tests).
- `.venv/bin/python tools/test.py`: **119 passed, 3 skipped, exit 0**.
- `.venv/bin/python -m pytest -q kit/tests/test_game_literals.py`:
  **3 passed, exit 0**; `.venv/bin/python kit/tools/check_game_literals.py`:
  **exit 0**.
- `.venv/bin/python kit/tools/format.py --write`: **243 handwritten native
  files formatted, exit 0**, with no native source changes.
- `.venv/bin/python build/task-10.3/verify_artifacts.py`: **exit 0**;
  reruns checked unzip/readelf/lipo/otool commands, APK byte comparisons
  and all 35 generated-file hashes. An additional read-only config check
  confirms exactly **5 decoders, 2 demuxers and file protocol** in both
  Android builds and iOS, with GPL/version3/nonfree/network and optional
  external-library flags all disabled.

The staged kit's `.venv/bin/python kit/tools/check_repo.py` passed source
boundaries and local documentation links, **exit 0**. Both repositories'
Git whitespace checks passed, **exit 0**.

Full build/test output, scratch scripts, APK copies and the standalone iOS
libraries remain under ignored `build/task-10.3/`. No game run, native CTest
suite, regeneration, Linux/Windows build, remote push or device action was
performed. The iOS app build, embedded signature checks and mobile device
verification remain deferred to the orchestrator's environment.

#### 2026-09-14: Task 10.2 decodes Bink into the game's DirectDraw surface

Resumed from game `main` at `deb8eac` and kit `pharaoh` at `d8159bb`, with
the decoder, conversion helper, intro script and close-cooperation change
already in the working trees. Kept those changes and all five close checks.
The real COM lookup is `com_this_arg`, with `ComObj::bpp` and `rmask`;
file resolution uses `win32_host_path_op(..., WIN32_FILE_READ)`. The mixer
sequence follows Miles: `host_audio_play`, `host_audio_stream`, then
`host_audio_queue`. No game addresses or executable identity changed.

- `kit/dx/bink.cpp` owns FFmpeg demuxers, decoders, retained frames and audio
  queues in a host map keyed by 0x100-byte guest records. Both frame-count
  layouts are filled; host milliseconds pace playback. The game supplies
  the locked DirectDraw destination and pitch, and the shim validates it
  before converting rows. Successful `BinkGetError` returns an empty string.
  Close releases the decoder, audio channel and guest record; `dx_reset`
  clears host state. Builds without FFmpeg keep the finished-video stub.
- `kit/dx/video_frame.h/.cpp` converts limited-range YUV420P into RGB565,
  RGB555 or XRGB8888 without exposing FFmpeg types. The synthetic 4x2 test
  checks known pixel values and row padding. `test_bink_play` opens
  `pre_dynastic_big.bik`: **560x333, 709 frames, 24 fps**, frame 1 at open,
  two decoded frames, pitch 1280, streamed audio bytes and released resources.
  **Frame 1 is actually black** (`0000` throughout); frame 2 is non-uniform
  (first pixel `0020`). The non-uniform assertion therefore applies to frame
  2, correcting the proposed expectation using the measured file content.
- The retained failing run `build/task-10.2-close-red-tests.log` has exactly
  **138,551 checks / 5 failures**: the close request did not end `BinkWait`
  or finish either record layout before/after `BinkNextFrame`. The retained
  close change exposes `host_close_requested()` from `host/boot.cpp`, with
  a weak false default in `dx/host_api.cpp`; the video wait stops and both
  counters finish on close. The fresh game suite below passes all five.

The intro smoke was rerun once after the close change, using a new scratch
profile under ignored `build/task-10.2-resume/`:

```sh
RECOMP_PROFILE_DIR="$intro_profile" \
RECOMP_SCRIPT="$PWD/smoke/intro.script" \
RECOMP_HOST_DUMP_DIR="$PWD/build/task-10.2-resume/smoke" \
RECOMP_DDRAW_MODES=640x480x16 RECOMP_SMOKE_DRAWABLE=1024x768 \
RECOMP_MAX_SECONDS=30 build/recomp/pop_smoke
```

`intro_profile` was created with Python `tempfile.mkdtemp` in that directory;
stdout/stderr are in `build/task-10.2-resume/smoke.log`. **Exit 0; 6/6 steps;
16.1 seconds reported (16.909 seconds including startup); 383 frames,
258 changed**. The log opens `Binks\high\intro_big.bik` at **560x333,
3,282 frames, 24/1 fps**. The script dumps at 2, 6 and 12 seconds, presses
Return for 100 ms, waits four seconds and dumps the title. Visual inspection
of the four 640x480 captures confirmed:

| Capture under `build/task-10.2-resume/smoke/` | Content | Distinct colours |
| --- | --- | --- |
| `smoke_intro-2s_present.ppm` | Impressions Games logo on black | 75 |
| `smoke_intro-6s_present.ppm` | Gold transition across the centred video rectangle | 316 |
| `smoke_intro-12s_present.ppm` | Horses and chariot crossing the dunes | 2,070 |
| `smoke_title-screen_present.ppm` | Cleopatra title with Click to Start | 5,507 |

Each intro pair differs at **186,480 / 307,200 pixels** (the 560x333 video
rectangle); all three are non-uniform. Python image/audio/identity assertions
exited **0**, saved PNG copies and `build/task-10.2-resume/metrics.json`, and
reconfirmed the pinned SHA-256, image base and entry point. The smoke host
logs `host audio streaming unavailable`, so its two sample plays do not
establish streamed intro audio. The existing mod-loader failure and forced
16-bit mode warning remain in its log; there are no undeliverable calls.

The earlier headless captures were retained and remeasured, not rerun during
this resume. Both logs record a **20-second wall-clock cap**, 640x480x16,
`RECOMP_HOST_AUDIO_CAPTURE` output and an additional 15 seconds before forced
unwind. `build/audio-intro.wav` has **1,680,239 stereo s16 frames at 48 kHz =
35.004979 seconds**, peak **32767 / 32768 = 0.999969**. Its headless log
reports **34.7 seconds non-silent**. With close cooperation,
`build/audio-intro-close.wav` has **1,680,041 frames = 35.000854 seconds**,
peak **32734 / 32768 = 0.998962**; the log again reports 34.7 seconds
non-silent and zero discontinuities or silent gaps over 50 ms while playing.

At 20.0 seconds / frame 490, `build/task-10.2-close-headless.log` records
WM_CLOSE, immediately followed by new front/back surfaces and a new audio
stream: **the video ends at once and the game moves on**. Subsequent headless
frames are black, so this run does not establish the title visually. The
game still does not act on WM_CLOSE; the host forces an unwind at 35 seconds,
**exit 3**. That is the pre-existing headless baseline, not a decoder failure
or an exit-0 requirement. The close run's queue diagnostic also reports
34.7 seconds claimed versus 16.0 seconds handed over on the reused channel;
this task does not resolve that diagnostic. These captures establish mixer
output, not listening quality or full-length playback of every cinematic.

Fresh verification during this resume:

```sh
.venv/bin/python tools/test.py --compile-only
.venv/bin/ctest --test-dir build/cmake/macos -R dx_tests
.venv/bin/python kit/tools/test.py --game-dir /Users/sattam.thakur/Documents/Tests/pharaoh-recomp/kit/games/stub --compile-only
.venv/bin/ctest --test-dir kit/build/cmake/macos -R dx_tests --output-on-failure
.venv/bin/python -m pytest -q tests
```

Both native builds exited **0**, retaining existing compiler warnings in
`build/task-10.2-resume/game-build.log` and `stub-build.log`. Both CTest runs
passed **1/1, zero failures, exit 0**: the game had **138,551 checks** and
executed the video test; the stub had **138,484 checks** and explicitly
skipped the absent developer video. The config suite passed **4 tests,
exit 0**, after dropping `BINKS` from `[bundle].exclude` and moving the
intro file into its retained-files assertions. `runtime_tests` was not run.
Other platform builds, device playback, full cinematic completion and a
fresh app run were outside this task. All captures, logs, binaries and
scratch profiles remain ignored and uncommitted.

Publication checks: `.venv/bin/python kit/tools/format.py --write` formatted
**243 handwritten source files**, exit **0**, without unrelated changes.
`.venv/bin/python kit/tools/check_game_literals.py`,
`.venv/bin/python kit/tools/check_repo.py` (after staging the kit), and both
repositories' `git diff --check` checks exited **0**. Kit commit **`e46dc77`**
on `pharaoh` contains the implementation and tests; this game commit re-pins
it, retains `BINKS`, and adds the script, config coverage and documentation.

#### 2026-09-14: Task 9.3 taps keep their position; edge holds still scroll

The iPad trace supplied with Task 9.3 reports a **1210x834-point** window
and **640x480** game image at **3.475 drawable pixels per game pixel**
(1668 / 480), filling the window vertically. The city menu bar, **File
Options Help**, sits about **14 window points** below the top; sidebar
buttons extend to the bottom. Taps near those controls arrived at **y=0**
or **y=833**, including the supplied trace excerpt
`[pointer] event 94.0,0.0 ... hit 2 at 32,0`. The click missed the control
and triggered edge scrolling. This is the task's existing device evidence;
no new iPad run was performed here.

At kit `27fc958`, `TouchMapper::place` snapped every placed point within
`kTouchEdgeMargin` (**16 points**, plus the system inset on that edge) to
the window edge. `click()` used that path too, and
`test_tap_on_an_edge_clicks_there_then_moves_inside` asserted the unwanted
snap and later inward nudge. Kit `pharaoh` **`9e31983`** adds
`place(out, x, y, bool snap = true)` and passes `false` from `click()`.
The press and delayed release now keep the finger's position, with no
post-release nudge. Drag and edge-hold callers retain the default snapping;
lifting an edge hold still moves the cursor inside to stop scrolling.

Replaced the old test with `test_tap_near_an_edge_clicks_at_the_finger`:
a tap at **(5, 400)** in **800x600** bounds must place, press and release
at **(5, 400)**, with no movement after release or on a later tick.
`test_edge_hold_scrolls_then_moves_the_cursor_inside` is unchanged.

Verification, from this repository using the kit's stub game:

```sh
.venv/bin/python kit/tools/test.py --game-dir /Users/sattam.thakur/Documents/Tests/pharaoh-recomp/kit/games/stub --compile-only
.venv/bin/ctest --test-dir kit/build/cmake/macos -R input_touch_tests --output-on-failure
```

The compile command ran **twice**, before and after the implementation;
both exited **0**. With only the test changed, CTest failed **1/1** with
**3 failed assertions**, exit **8**, covering placement, press, and release
position/action count. After the implementation it passed **1/1**, exit
**0**, including the unchanged edge-hold test.

```sh
.venv/bin/ctest --test-dir kit/build/cmake/macos -R host_tests --output-on-failure
.venv/bin/python kit/tools/format.py --write
.venv/bin/python kit/tools/format.py
.venv/bin/python kit/tools/check_game_literals.py
.venv/bin/python kit/tools/check_repo.py
.venv/bin/python -m pytest -q kit/tests/test_game_literals.py tests
git -C kit diff --cached --check
```

All exited **0**. `host_tests` passed **1/1**, with **3,910,394 checks,
0 failures**. The formatter wrote and then checked **241 handwritten
source files**, leaving only the intended native changes. The literal
scan found no violations; tracked-source boundaries and documentation links
passed with the kit changes staged. Pytest passed **7 tests** (3 kit
literal checks and 4 game config checks); the staged kit diff had no
whitespace errors.

The game re-pins `kit/` to `9e31983` and documents the gestures. No iOS
build, installation or post-fix device validation was performed; the
orchestrator handles that next. The FFmpeg stash was not touched. No game
files, generated output, run logs or saves are committed, and nothing was
pushed or landed in the separate kit checkout.

#### 2026-09-14: Task 9.2 settings restore and fullscreen pass; suite gate blocks commit

Resumed on game `main` `5ba92ac`, with its recorded kit pin `722d51e`
and the submodule on `pharaoh` `362207b`. The latter is the already
committed pre-step that gates `present_events_tests` on its real fixture.
The supplied baseline was **42 passed suites, 3 failed suites, 5 assertion
failures**, then a bus error after 45 completed suites. The new tests run
first in `settings_tests.cpp`, before any symbol map is loaded.

The uncommitted implementation moves
`mods_settings_load(mods_settings_path())` immediately after
`mods_overlay_reset()` in `mods_load_all`. The existing accessor is
`mods_symbols_count()`: only a nonempty, validated map populates that count.
`mods_display_row_applies(DisplayRow)` uses it for rendering, UI scale,
wide view, classic resolution, HD textures and texture filtering; window
mode, frame limit and performance overlay remain available. The fallback
page filters both labels and navigation metadata through this predicate.
README documents fn+F10 and holding Escape to release the mouse.

The loader regression writes `{"host.display/window": 2}` to an isolated
test profile, uses the existing `host_layout_set_exe_path_for_test` seam
to make the symbol file unavailable, confirms loader failure, then checks
the settings store and display value after `mods_display_init()`. The page
regression checks all six hidden and three retained rows, the predicate,
the six-row total including keypad controls, and navigation to window mode.
Together the two suites contain **33 checks**. The existing F10 toggle
test now expects nine rows without symbols (three host controls, three
keypad controls and three mod settings), or its original fifteen with a
symbol map. No game-backed failure was repaired or disabled.

**Verification**, from the game checkout using its venv. Full logs remain
under ignored `build/task-9.2-*.log`; no raw logs or profiles are tracked.

| Command | Actual result |
| --- | --- |
| `.venv/bin/python tools/test.py --mods` before implementation (`red-build`) | Exit **1** after successfully compiling/linking the new tests. The existing fixture exits **2** because `levels/levl2001.hdr` is absent. |
| `.venv/bin/ctest --test-dir build/cmake/macos -R mods_tests --output-on-failure` before implementation (`red-mods`) | Exit **8**. Both new suites fail: saved window remains 0, all six dependent rows remain present, row count is 12 instead of 6, and navigation still targets the old first row. At the original boundary: **42 passed / 5 failed suites / 15 assertion failures**, including ten new failures. Full run: **50 / 8 / 92**, then SIGSEGV. |
| `.venv/bin/python kit/tools/format.py --write` (three invocations) | All exit **0**; each formats 241 handwritten files. Only task files differ. |
| `.venv/bin/python tools/test.py --mods` after implementation and after correcting the existing F10 count (`green-build`, `final-build`) | Both exit **1** after successful test builds, followed by the same fixture exit **2**. |
| Same CTest command, first implementation run (`green-mods`) | Exit **8**, bus error after **43 / 4 / 6**. Both new suites pass; one old F10 row-count assertion still expects 15 instead of 9. Corrected that expectation afterward. |
| Same CTest command, final and confirmation runs (`final-mods`, `confirm-mods`) | Both exit **8**. Both new suites and the existing F10 suite pass. At the original boundary: **44 / 3 / 5**, exactly two additional passing suites. Both continue beyond that boundary and finish **52 / 6 / 82**, then SIGSEGV in the later Options tests. |
| `RECOMP_BUILD_ROOT=/Users/sattam.thakur/Documents/Tests/pharaoh-recomp/build /Users/sattam.thakur/Documents/Tests/pharaoh-recomp/build/recomp/mods_tests`, cwd `kit/` (`direct-mods`) | Exit **139** (SIGSEGV), again **52 / 6 / 82**, with both new suites passing. This matches CTest's binary, working directory and build-root environment. |
| `.venv/bin/python tools/build.py --jobs 8` | Exit **0**; app rebuilt and signed. One existing C-linkage return-type warning. |
| `.venv/bin/python kit/tools/check_game_literals.py` | No findings. |
| `.venv/bin/python -m pytest -q tests kit/tests/test_game_literals.py` | Exit **0**, **7 passed**. |
| `git -C kit diff --check` and `git diff --check` | Both exit **0**. |

Read-only Python assertions exited **0**: the executable SHA-256, image
base and entry match the pinned identity, and generated `x86.h` matches
`kit/runtime/x86.h`. No translator or runtime-header change needed
regeneration. The resumed game-tree mods route was used; no stub mods
execution, runtime or DX suite is claimed for this task.

**Real-app fullscreen relaunch.** The existing
`build/profile-f10/mod-settings.json` already contained window mode 2.
Backed it up to `build/task-9.2-profile-f10-before.json`, then ran the
specified `sed -i '' 's/"host.display\/window": 0/"host.display\/window": 2/'
build/profile-f10/mod-settings.json` and confirmed the parsed value was 2.
AppKit via `osascript -l JavaScript` reports one **1920x1080-point display,
backing scale 2**, origin 0,0.

Launched the rebuilt executable directly with
`RECOMP_PROFILE_DIR=$PWD/build/profile-f10`. The first launch stayed
unfocused: after 14 seconds the app was alive but the requested System
Events query returned only `,` (osascript exit 0, measurement assertion
exit 1). Corrected this launch omission by repeating with
`open build/PharaohRecomp.app` after two seconds to foreground the existing
process, then waiting another twelve seconds. PID 17433 was still alive.
The exact query
`osascript -e 'tell application "System Events" to tell process "PharaohRecomp" to get {position, size} of every window'`
exited **0** and returned **`0, 0, 1920, 1080`**, matching the full display.
The Python measurement assertion exited **0**. The initial startup log
still prints the window's pre-settings dimensions, 1280x960 points; the
14-second Accessibility measurement establishes the applied fullscreen size.

Ran `pkill -9 -f PharaohRecomp.app/Contents/MacOS/PharaohRecomp`
separately before and after each launch: **1, 0, 1, 0**, respectively
(no stray process before, matching app killed afterward). Both apps were
force-stopped as requested; this does not verify clean shutdown, gameplay,
live fn+F10 input or Escape release. Profiles and launch artifacts remain
under ignored `build/`.

**Stopped before Step 5.** The two new suites pass and the original
45-suite prefix retains its baseline failures, but the full run does not
retain the required totals before its actual crash. It reaches later
Populous-bound replay, overlay and Options failures instead. The cause of
the changed crash point is unverified; those failures are outside this
task's permitted repair scope. Per the instruction to stop when a stated
verification outcome cannot be reached, no Task 9.2 commit or game re-pin
was made, including no re-pin of pre-step `362207b`. The changes remain
reviewable in the working trees. Nothing was pushed.

#### 2026-09-14: Task 9.1 confines a captured pointer in a plain window

Started with clean game `main` `cc87394` and kit `pharaoh` `502ad1c`.
Added `host_pointer_confinement_wanted(bool captured, int window_mode)` to
the kit's input gate: it returns `captured` for every window mode. The SDL
host uses it instead of excluding mode 0 from OS pointer confinement.
The existing mode-0 button-drag release at the 8-window-point resize margin
and the startup instruction remain unchanged: "Mouse capture: click inside
to capture; hold Escape to release; drag to the window edge to resize."
Five checks beside the confinement-rectangle tests cover captured modes
0/1/2 and released modes 0/2.

**Regression and build checks**, run from the game checkout with the local
venv; full output remains under ignored `build/task-9.1-*.log`:

| Command | Actual result |
| --- | --- |
| `.venv/bin/python kit/tools/test.py --game-dir "$PWD/kit/games/stub" --compile-only` before implementation | Exit **1**: five `use of undeclared identifier 'host_pointer_confinement_wanted'` errors, one per new check; five existing warnings. |
| `.venv/bin/ctest --test-dir kit/build/cmake/macos -R host_tests --output-on-failure` after the failed build | Exit **0**, 1/1 suite passed, **3,920,226 checks / 0 failures**, using the previously built binary. This does not verify the new checks; the compile errors establish the failing test. |
| `.venv/bin/python kit/tools/format.py --write` | Exit **0**, formatted 241 handwritten source files; only the intended files differ. |
| `.venv/bin/python kit/tools/test.py --game-dir "$PWD/kit/games/stub" --compile-only` after implementation | Exit **0**, all native test binaries built; ten existing warnings, zero errors. |
| `.venv/bin/ctest --test-dir kit/build/cmake/macos -R host_tests --output-on-failure` after rebuilding | Exit **0**, 1/1 suite passed in **1.23 s**, **3,913,493 checks / 0 failures**, including the five new assertions. The suite's total check count varies between runs. |
| `.venv/bin/python tools/build.py --jobs 8` | Exit **0**, app built and signed; six existing C-linkage return-type warnings, zero errors. |
| `.venv/bin/python kit/tools/check_game_literals.py` | Exit **0**, no findings. |
| `.venv/bin/python -m pytest -q kit/tests/test_game_literals.py` | Exit **0**, **3 passed**. |
| `.venv/bin/python kit/tools/check_repo.py` with the five kit files staged | Exit **0**, tracked source boundaries and local documentation links passed. |

Read-only Python checks also exited **0**: the original executable's SHA-256,
image base and entry match the identity above, and generated
`build/recomp/gen/x86.h` is byte-identical to `kit/runtime/x86.h`.
No translation or `x86.h` change required regeneration.

**Real-app probes.** Read the orchestrator's `build/app_outside.py` and
`build/app_click.py`. Preserved the prior captures/log and existing profile
before the driver could replace them. Ran `.venv/bin/python build/app_outside.py`
unchanged, then `.venv/bin/python build/app_inside.py`, a copy changing only
the movement comment and `sx + 120 * i` to `sx + 25 * i`: eight steps now
push 200 rather than 960 window points right. Both drivers exited **0**,
printed `window: 320, 43, 1280, 992`, `scale 2.0 origin 320.0 73.0`, and
`done`. Their first inside click captured the focused app, and both reached
the Nubt city. The screenshots were visually inspected. The 200-point
probe retains the terrain position while animals move; the 960-point
probe moves across the map to the river.

Ran `pkill -9 -f PharaohRecomp.app/Contents/MacOS/PharaohRecomp` separately
before and after each launch: all four invocations returned **1**, with
no matching stray process. Both app logs contain guest `ExitProcess(0)`
followed by the known shutdown fault:
`SIGSEGV in guest thread 1: EIP=0056478f ESP=0effff40 EBP=0effffd8`.
Driver exit 0 is not a clean app-shutdown claim.

After each probe, ran the plan's
`grep -n "pointer confinement\|hit 2 at 6[23][0-9]" build/app-click.log | tail -5`
and PIL difference script, both exit **0**. Fractions use the exact crop
`(0, 1200, 1800, 1900)` and
`sum(h[24:]) / sum(h)` after RGB difference converted to luminance, against
that run's `app-city-before.png`. Captures are **2560x1928 pixels**.

| Probe | Changed fraction at 3 s | At 6 s | Confinement line / resting hit |
| --- | --- | --- | --- |
| Prior saved 960-point run, before this change | **0.990** | **0.990** | No confinement line; `hit 2 at 639,299`. |
| Rebuilt app, 960 points right | **0.990** | **0.990** | Mode-0 confinement logged; `hit 2 at 639,299`. |
| Rebuilt app, 200 points right, inside | **0.008** | **0.010** | Mode-0 confinement logged; `hit 2 at 420,299`. |

Both new logs have the capture line at line 49, immediately before the
first button-down record. Relevant complete trace lines:

```text
[host] pointer confinement: 4.0,4.0 1272.0x952.0 points (window mode 0)
[pointer-game] drawable 2559,1199 hit 2 at 639,299 delivered 1 guest 0,0 bounds 0,0,0,0
[pointer-game] drawable 1683,1199 hit 2 at 420,299 delivered 1 guest 0,0 bounds 0,0,0,0
```

The second line is the 960-point probe's last hit before returning inside;
the third is the 200-point probe's. Both return to `320,299` afterward and
log zero-sized confinement on shutdown. Confinement still lets the pointer
rest at the game's right edge, so that probe retains the original
edge-scroll behavior and **does not reduce the 0.990 fraction**. The inside
probe passes the requested **under-5%** no-scroll criterion at both times.

Prior evidence, both new runs and their profiles are retained under
`build/task-9.1-20260914-064323/{baseline,outside-960,inside-200}/`.
The inside copy keeps the driver's original `city-outside-*` screenshot
names; the archive directory identifies the 200-point run. These artifacts,
drivers and saves are not committed. Live Escape release and resize dragging
were not exercised in these probes; their existing paths and tests remain.
No other platform or task was run.

Kit commit `722d51e` contains only the input helper, its declaration and
five checks, the SDL call/comment and kit changelog. The game re-pins it
with this run record and a changelog entry; nothing was pushed.

#### 2026-09-14: Task 8.1 cinematics decision, platform status and kit publication

Keep the Task 5.1 `BINKS` exclusion and its existing regression test;
`game.toml` changes only the bundle comment to cover iPad and Android.
The [cinematics decision](#cinematics-decision-task-81) records the decoder
options and measured 139.921 MiB saving. README now separates macOS smoke
first-mission progress from app hand play, iPad boot/stream activity from
audible music and touch play, and Linux/Windows/Android build checks from
runtime evidence. Its known-issues list retains shutdown, the 32
Populous-bound runtime failures, undrawn text, skipped videos, manual
Save/Load and the earlier iOS shell problem.

Ran the task's final four-command `&&` chain in order from this game
checkout with `.venv/bin/python`; the chain exited **0**. Output stays in
ignored `build/task-8.1-final-checks.log`.

| Verification command | Actual result |
| --- | --- |
| `.venv/bin/python -m pytest -q tests/test_game_config.py -k test_bundle_exclusions_and_setup` (Step 1) | Exit **0**; **1 passed, 3 deselected** in 0.01 s. |
| `.venv/bin/python tools/test.py` | Exit **0**; **118 passed, 3 skipped** in 6.62 s. |
| `.venv/bin/python -m pytest -q tests` | Exit **0**; **4 passed** in 0.01 s. |
| `.venv/bin/python tools/build.py --stub` | Exit **0**; linked `build/stub/PharaohRecomp.app`, one existing C-linkage warning, zero compiler errors. |
| `.venv/bin/python tools/build.py --stub --target ios` | Exit **0**, **BUILD SUCCEEDED**; linked `build/ios-stub/Release/PharaohRecomp.app` using `arm64-apple-ios17.0` and iPhoneOS26.5 SDK, with signing disabled. Six existing C-linkage warnings, a UIDeviceFamily warning and a duplicate `-lobjc` warning; zero compiler errors. |

The iOS stub build worked in this shell; no compiler-probe workaround or
skip was needed. This does not identify the earlier shell override or
establish a new device run. Native test suites and gameplay were not
rerun for this documentation/comment-only task; the 32 runtime failures
are the previously recorded baseline, not a fresh measurement.

Landing and publication used the explicitly authorized sequence:

```sh
cd /Users/sattam.thakur/Documents/Tests/recomp-kit
git -c protocol.file.allow=always pull --ff-only /Users/sattam.thakur/Documents/Tests/pharaoh-recomp/kit pharaoh
git push origin main
cd /Users/sattam.thakur/Documents/Tests/pharaoh-recomp
git -C kit -c protocol.file.allow=always fetch local main
git -C kit checkout -q -B pharaoh local/main
```

All four Git commands exited **0**. The landing checkout was already at
`502ad1c`, so the fast-forward-only pull reported **Already up to date**.
The push advanced GitHub main from `2fe5c5d` to
**`502ad1ce689ed136b685c35f2df190fd7064cb37`**. Read-only `git ls-remote`
and local ref/status assertions exited **0**: GitHub main, landing main,
submodule `pharaoh` HEAD and its `local/main` all match that hash, and
both kit checkouts are clean. The game's gitlink already names that
commit, so refreshing the pin produces no gitlink diff or new kit commit.
Only the four task files are changed in the game repository; no game
repository push is performed. Assets, saves, generated files and logs
remain uncommitted.

#### 2026-09-14: Task 7.3 real Android translation builds; device boot deferred

Implemented Step 1 and `--push-game` under the explicit no-device
adaptation. Kit `pharaoh` commit
`502ad1ce689ed136b685c35f2df190fd7064cb37` contains:

- `host/sdl/main.cpp`: obtain `SDL_GetAndroidExternalStoragePath()` before
  layout initialization, apply its `switches.txt`, default `RECOMP_PROFILE_DIR`
  to its writable `profile/`, and resolve `game/<executable>` there. The
  loader still checks the fixed executable hash. Missing data logs the
  expected executable and `adb push build/android/game "<external files>/"`,
  names `tools/build.py --target android --push-game`, then quits SDL and
  exits 2. The page overlay requires presenter/mod initialization and a
  frame to draw into, so this uses the explicitly permitted log-and-exit
  fallback instead of a new boot UI.
- `host/game_path.cpp` and `.h`: an optional platform-supplied data root
  searches only `game/<executable>` and requires a regular file; a missing
  mobile file cannot fall back to a baked developer path. No Android API
  or platform guard was added outside `host/sdl/`.
- `host/sdl/platform_ui_desktop.cpp` and `.h`: Android fullscreen hints,
  shared touch/keypad behavior without pointer capture, and a lifecycle
  watcher to suspend/resume presentation and audio. Normal guest shutdown
  calls `exit(code)` after the existing `SDL_Quit()`. This choice ends the
  process after teardown; minimizing would leave a completed game in the
  activity's task. Its device behavior remains unverified.
- `tools/build.py`: `--push-game` installs first, rebuilds only the generated
  `build/android/game` staging directory, and pushes it into
  `/sdcard/Android/data/<bundle_id>/files/` before launching. It reuses
  `stage_game_files.stage()`, hence the real `excluded()` helper and hash
  `.stamp`. It removes no files on the device. Missing adb or no ready
  device produces a clear failure for an explicit push; builds without
  that option retain their device-action skip. Incompatible target or
  `--no-install` combinations are rejected.
- `tools/tests/test_build.py`: a tiny fake `original/gog/app` verifies
  included bytes, excluded top directories and nested DLLs, the stamp,
  stale staging cleanup, destination and install/push/launch order. Further
  cases cover no device and invalid option combinations. The kit changelog
  records the behavior.

Read-only checks confirmed the pinned SHA-256, image base `0x00400000`
and entry `0x00562fea`, and byte-identical generated/kit `x86.h` before
building. Hash snapshots before and after confirm that every file in
`build/recomp/gen/` is unchanged. **No regeneration or stub translation
was used for the Android build.** The real configured install selects
**1,304 files / 634,766,385 bytes / 605.360 MiB**, plus the stager's
`.stamp`, using the existing exclusions. This is a source-file measurement;
the real game was not staged or pushed because no device is attached.

Build environment and command, from this game repository:

```sh
export JAVA_HOME='/Applications/Android Studio.app/Contents/jbr/Contents/Home'
export ANDROID_HOME=/Users/sattam.thakur/Library/Android/sdk
export ANDROID_NDK_HOME=/Users/sattam.thakur/Library/Android/sdk/ndk/27.2.12479018
export PATH="$PWD/.venv/bin:$ANDROID_HOME/platform-tools:$PATH"
.venv/bin/python tools/build.py --target android > build/task-7.3-android-build.log 2>&1
```

The first real build exited **0**, compiling **all 32** generated C files
(`chunk_000.c` through `chunk_030.c`, plus `table.c`) with NDK Clang
**18.0.3**, `--target=aarch64-none-linux-android29`. The shared library
linked and Gradle reported **BUILD SUCCESSFUL**, **36 tasks: 4 executed,
32 up-to-date**. It reported no device, skipping install, launch and logcat.
There were **28 compiler warnings, zero compiler errors**: existing
keypad/presenter C-linkage declarations, Lua's deprecated `tmpnam`, and
one newly unused Android `exe_flag`. Explicitly discarding the desktop
flag corrected the new warning; the final rebuild, logged in
`build/task-7.3-android-final.log`, exited **0**, with **6** existing
C-linkage warnings and zero errors. Gradle again succeeded with **4
executed / 32 up-to-date**. NDK CMake and Gradle deprecation warnings remain.

Final artifacts:

| Artifact | Measured size |
| --- | --- |
| `build/android/app/build/outputs/apk/debug/app-debug.apk` | **180,322,863 bytes** |
| `build/cmake/android/host/libmain.so` | **140,061,976 bytes** |

Python ZIP/ELF checks exited **0**: valid ZIP, exactly one packaged native
library, byte-identical to the NDK output, ELF64 little-endian AArch64
shared object, and no game asset directory, original executable, audio,
cinematic or save entries. SDK `aapt2 dump badging` exited **0** and
confirmed `dev.recompkit.pharaoh`, launch activity
`dev.recompkit.RecompActivity`, minSdk **29**, targetSdk **36**, arm64-v8a
and required Vulkan version **4198400** (1.1).

| Verification command | Actual result |
| --- | --- |
| `.venv/bin/python -m pytest -q kit/tools/tests/test_build.py -k 'push_'` before implementation | Exit **1**; **4 failed, 13 deselected**. Expected missing keyword/option support. |
| `.venv/bin/python -m pytest -q kit/tools/tests/test_build.py` | Exit **0**; **17 passed**. |
| `.venv/bin/python tools/build.py --target android` | Initial and final builds each exit **0**; real translation and APK results above. |
| SDK `adb devices` | Exit **0**; empty device list. |
| `.venv/bin/python tools/build.py --target android --push-game` | Exit **1** as required. Incremental APK build succeeds with **36 up-to-date tasks**; then `No Android device attached; --push-game requires a ready device in adb devices`. No install, push or launch was issued. |
| `.venv/bin/python tools/test.py` | Exit **0**; **118 passed, 3 skipped** in 7.20 s. |
| `.venv/bin/python -m pytest -q tests kit/tests/test_game_literals.py kit/tools/recomp/tests/test_host_boundary.py` | Exit **0**; **9 passed**: 4 game config, 3 literal and 2 host-boundary tests. |
| `.venv/bin/python tools/build.py --stub` | Exit **0**; desktop host links at `build/stub/PharaohRecomp.app`, with **1** existing C-linkage warning and zero errors. Checks the desktop branches of the changed SDL files. |
| `.venv/bin/python kit/tools/format.py --write` | Both runs exit **0**; **241** handwritten files, no unrelated edits. |
| `.venv/bin/python kit/tools/format.py` | Exit **0**; **241** files checked. |
| `.venv/bin/python kit/tools/check_game_literals.py` | Exit **0**; no findings. |
| `.venv/bin/python kit/tools/check_repo.py` on staged kit changes | Exit **0**; tracked source boundaries and local documentation links pass. |
| `unzip -l build/android/app/build/outputs/apk/debug/app-debug.apk` | Exit **0**; **17 entries**, sole native library and sizes verified above. |
| SDK build-tools 37.0.0 `aapt2 dump badging` on the APK | Exit **0**; identity and minimum-platform metadata above. |
| Read-only `.venv/bin/python` identity, staging selection, compile-command, generation snapshot and ZIP/ELF assertions | Exit **0**; counts and identities above. |
| Git whitespace/staged-scope checks | Exit **0**; only scoped source/docs and the gitlink staged. |

An initial ancestry check ran in the landing checkout before it had the
submodule's newer objects and exited **128** (`Not a valid commit name
ae1aa477016a2fe977dad325c653d03bf17578c5`). Repeating it in `kit/`, where
both commits exist, exited **0**. The actual local landing main started
at **`2fe5c5d`**, not the plan's older `31f0f24`. After committing the kit
and the game's pin/docs, landed locally:

```sh
git -C /Users/sattam.thakur/Documents/Tests/recomp-kit -c protocol.file.allow=always pull --ff-only /Users/sattam.thakur/Documents/Tests/pharaoh-recomp/kit pharaoh
git -C kit -c protocol.file.allow=always fetch local main
git -C kit checkout -q -B pharaoh local/main
```

The pull exited **0**, fast-forwarding the landing checkout from
`2fe5c5d` to `502ad1c`, including the four previously unlanded commits.
The first fetch revealed that the existing remote named `local` actually
pointed to `https://github.com/veritr1x/recomp-kit.git`; fetch/reset exited
0 but briefly selected its older `2fe5c5d`. Immediately restored
`pharaoh` to `502ad1c`, then set `remote.local.url` to the specified
`/Users/sattam.thakur/Documents/Tests/recomp-kit` and repeated fetch/reset.
All correction commands exited **0**. Landing main, submodule `pharaoh`,
`local/main` and the game's committed gitlink now all equal
**`502ad1ce689ed136b685c35f2df190fd7064cb37`**. No commits were lost and
no remote push ran. The pin hash needs no further change; this completed
landing record is included in the amended game documentation commit.

README now contains **Play on an Android tablet** with exact build,
filtered push, adb launch, switches/timing-capture commands and the manual
first-mission, house-building, scrolling, right-click, audio, save/load,
background/resume and Quit checklist. Android reads the pushed directory
directly, with no iOS-style bundle seeding or stamp-triggered replacement.
**Steps 2 and 3 are deferred:** no device install, first boot, on-device
missing-data/exit check, logcat game output, audible AAudio music, touch
play or frame-rate measurement exists. Native CTest runtime/DX suites and
iOS/Linux/Windows builds were not run in this host/data-path task. All raw
logs, binaries, generated files, original inputs and saves stay uncommitted
under their ignored directories.

#### 2026-09-14: Task 7.2 Android stub APK packages SDLActivity

Kit `pharaoh` commit `ae1aa47` adds a Gradle project template and
`tools/build.py --target android`. The NDK preset builds the native library
first. The renderer writes `build/android`, substitutes `app_name`,
`bundle_id` and `id`, and points its Java source set at the same CMake
build's `_deps/sdl3-src/android-project/app/src/main/java`. It copies
`build/cmake/android-stub/host/libmain.so` into
`build/android/app/src/main/jniLibs/arm64-v8a/`; Gradle never invokes CMake.
These paths follow the existing external-game build-root convention.

The template pins Gradle 9.7.1 and AGP 9.1.1, build-tools 37.0.0,
compile/target SDK 36, minSdk 29 and arm64-v8a only. `RecompActivity`
extends SDLActivity and loads only `main`. The manifest requires Vulkan
1.1 (`0x401000`), landscape orientation and
`requestLegacyExternalStorage="false"`; its application label resolves to
`PharaohRecomp`. `--no-install` skips device actions, `--device` selects
an adb serial, and `--console` streams logcat after install and launch.
No ready adb device means those three actions are skipped.

The exact prescribed test failed first with missing `android_project`
(`AttributeError`, 1 failed, exit 1). After implementation, the initial
focused file run passed all 5 then-present tests (exit 0). Additional
checks cover the manifest contract, three host-platform preset selections,
ready/offline/absent devices, console commands and ambiguous devices.
`kit/tools/test.py` now includes `tools/tests/test_build.py` in its portable
list; previously that file was not run by the requested suite command.

Build environment and final command, from this repository:

```sh
export JAVA_HOME='/Applications/Android Studio.app/Contents/jbr/Contents/Home'
export ANDROID_HOME=/Users/sattam.thakur/Library/Android/sdk
export ANDROID_NDK_HOME=/Users/sattam.thakur/Library/Android/sdk/ndk/27.2.12479018
export PATH="$PWD/.venv/bin:$ANDROID_HOME/platform-tools:$PATH"
set -o pipefail
.venv/bin/python tools/build.py --target android --stub 2>&1 | tee build/task-7.2-android-final.log | tail -5
```

The SDK initially had only platform `android-36.1`. Gradle installed
Android SDK Platform 36 revision 2 using the already accepted SDK license.
The cached distribution's `gradle wrapper --gradle-version 9.7.1`, run in
`kit/platform/android` with the JDK above, exited 0 (1 task executed).
The wrapper JAR, properties and both launch scripts are committed;
file-specific Git attributes normalize the scripts while retaining CRLF
for the Windows checkout. The first staged whitespace check flagged those
CRLF lines (exit 2); after attributes and `git add --renormalize`, it passed.

| Verification | Actual result |
| --- | --- |
| `.venv/bin/python -m pytest -q kit/tools/tests/test_build.py::test_android_templates_render` before implementation | Exit 1; 1 failed, expected missing helper. |
| `.venv/bin/python -m pytest -q kit/tools/tests/test_build.py` after initial implementation | Exit 0; 5 passed in 0.03 s. |
| `.venv/bin/python tools/build.py --target android --stub` with the pipeline above | Both runs exited 0. First: 36 Gradle tasks executed, 18 s; final: 36 up-to-date, 585 ms. Native link: 22 warning diagnostics, zero errors. |
| `.venv/bin/python tools/test.py` | Both runs exited 0; 114 passed, 3 skipped (6.58 s initially; 6.72 s finally). Includes 13 tests from `tools/tests/test_build.py`. |
| `.venv/bin/python kit/tools/format.py --write` | Exit 0; 241 handwritten files formatted, no native source changes. |
| `.venv/bin/python kit/tools/check_game_literals.py` | Exit 0; no findings. |
| `.venv/bin/python -m pytest -q tests` | Exit 0; 4 passed in 0.01 s. |
| `.venv/bin/python kit/tools/check_repo.py` on staged kit changes | Exit 0; tracked source boundaries and local documentation links passed. |
| `unzip -l build/android/app/build/outputs/apk/debug/app-debug.apk classes.dex lib/arm64-v8a/libmain.so` | Exit 0; entries reproduced below. |
| SDK build-tools 37.0.0 `aapt2 dump badging` on that APK | Exit 0; `dev.recompkit.pharaoh`, label `PharaohRecomp`, SDK 29/36, arm64-v8a only, required Vulkan version 4198400 and launch activity `dev.recompkit.RecompActivity`. |
| SDK `apkanalyzer dex code --class dev.recompkit.RecompActivity` and `dex packages --defined-only` on that APK | Exit 0; both activity classes are defined; bytecode confirms SDLActivity superclass and a one-element `getLibraries()` array containing `main`. The SDK launcher printed a nonfatal integer-expression warning. |
| Read-only Python ZIP/sha256 assertions | Exit 0; ZIP integrity passes, only one native library is packaged, and it exactly matches the NDK output. |
| SDK `adb devices` | Exit 0; empty device list. Build reports install, launch and logcat skipped. |

APK: `build/android/app/build/outputs/apk/debug/app-debug.apk`,
**40,252,530 bytes**. The requested `unzip -l` entries are:

```text
  2419220  01-01-1981 01:01   classes.dex
 37693352  01-01-1981 01:01   lib/arm64-v8a/libmain.so
```

The build also reports SDK XML-version, deprecated Java/source-set API and
source-manifest `package` warnings; the required manifest package is kept
and matches the Gradle namespace/applicationId. None prevents packaging.
Full build output remains in ignored `build/task-7.2-android-build.log`
and `build/task-7.2-android-final.log`. No APK, native library, SDL Java
copy, game asset, save or raw run log is committed. This is a stub
translation: no Android install, launch, logcat capture or gameplay was
performed. Native CTest suites and other-platform builds were not run in
this packaging task; Task 7.3 was not started.

#### 2026-09-14: Task 7.1 Android stub shared library links

Resumed at Step 3, preserving the existing Android preset, CMake, CI and
kit changelog edits. Kit `pharaoh` commit `da6d418` adds arm64-v8a/API 29
presets, position-independent libraries, the shared `recomp_app` target
with output name `main`, static SDL3/libc++, NDK Vulkan/log linkage, and
Android guards around desktop-only targets. The CI job configures and
builds the same stub target; GitHub Actions was not run.

The only additional native source fix is `kit/mods/native/page_track.cpp`:
retain the existing arm64 Darwin body under an Apple guard; on arm64
Linux/Android, walk bounded records in `uc_mcontext.__reserved`, identify
`ESR_MAGIC` (`0x45535201`, `esr_context`), and use the same data-abort EC and
WnR classification. A missing ESR record returns false. The required
ucontext header is guarded for Linux/Android. **No further source-error
rounds were needed**, and `platform/os_posix.cpp` did not change.

From `kit/`, with `ANDROID_NDK_HOME` set to
`/Users/sattam.thakur/Library/Android/sdk/ndk/27.2.12479018` and the game's
`.venv/bin` first on `PATH`:

| Command | Actual result |
| --- | --- |
| `cmake --preset android-stub` | Exit 0; arm64-v8a, android-29, c++_static; SDL shared OFF/static ON. Three NDK CMake deprecation warnings. |
| `cmake --build --preset android-stub --target recomp_app` | Exit 0 on the first resumed build; shared library linked. 21 existing keypad/presenter C-linkage warnings, zero compiler errors. |
| `ls build/cmake/android-stub/host/libmain.so` | Exit 0; library exists. |
| `stat -f '%N: %z bytes' build/cmake/android-stub/host/libmain.so` | Exit 0; 37,676,768 bytes. |
| NDK `llvm-readelf -h -d build/cmake/android-stub/host/libmain.so` | Exit 0; ELF64 AArch64 shared object, SONAME libmain.so, dependencies include libvulkan.so and liblog.so, with no SDL3 or libc++ shared dependency. |

The artifact is
`kit/build/cmake/android-stub/host/libmain.so`; the link rule names
`libSDL3.a` and uses `-static-libstdc++`. Ninja's dependency record includes
`page_track.cpp` in `capture_seam.cpp.o`, and the object is newer than the
modified source (read-only Python/Ninja check, exit 0).

From the game repository, after the Android build:

| Command | Actual result |
| --- | --- |
| `.venv/bin/python tools/test.py` | Exit 0; 101 passed, 3 skipped in 6.47 s. |
| `.venv/bin/python kit/tools/format.py --write` | Exit 0; formatted 241 handwritten files; no unrelated changes. |
| `.venv/bin/python kit/tools/check_game_literals.py` | Exit 0; no findings. |
| `.venv/bin/python -m pytest -q kit/tests/test_game_literals.py` | Exit 0; 3 passed in 0.04 s. |
| `.venv/bin/python kit/tools/check_repo.py` (staged kit) | Exit 0; tracked source boundaries and local documentation links passed. |
| `.venv/bin/python -m pytest -q tests` | Exit 0; 4 passed in 0.01 s. |

Read-only Python assertions confirmed the warning counts and parsed the CI
YAML's configure/build/artifact-check steps (exit 0). Git whitespace checks
passed in both repositories (exit 0).

Full configure/build and portable-suite output stays in ignored
`build/task-7.1-*-resume.log` and `build/task-7.1-portable-tests.log`.
No generated code, binaries, logs, game assets or saves are committed.
The library uses the kit's stub game; no game translation was regenerated.
APK packaging, installation, real Android signal-handler execution and
gameplay were not tested. Native runtime/DX suites were not run in this
task; the evidence is the Android stub link and portable checks above.

#### 2026-09-14: Task 6.3 Linux and Windows CI and instructions only

Steps 1 and 2 were explicitly deferred: this Mac has no Linux or Windows
machine with the game. **Neither native Linux nor native Windows
builds, packages or gameplay have been run yet.** No smoke comparison,
Vulkan window, first-mission play, GPU/driver record or Vulkan validation
result exists for either platform from this task.

Step 3 adds `windows-2025` to `.github/workflows/checks.yml`, retaining
`macos-15` and `ubuntu-24.04`. Windows enters the Visual Studio developer
environment with `ilammy/msvc-dev-cmd@v1`, following the kit's CI for the
runner's clang/lld toolchain. All three entries run the same portable kit
tests, game config tests and `tools/build.py --stub`; the Windows entry
uses `.venv/Scripts/python` under Bash. The existing Linux clang/lld
installation and macOS-only iOS stub step remain. This workflow change
has not been run on GitHub Actions.

Step 4 adds [Build on Linux](../README.md#build-on-linux) and
[Build on Windows](../README.md#build-on-windows) with the task's setup,
analysis and build sequence. The Linux apt packages match the kit's CI.
Source inspection of `kit/tools/build.py` and
`kit/tools/package_desktop.py` corrects the plan's launch paths: both
platforms stage under `build/package/PharaohRecomp/`, and Linux also writes
`build/package/PharaohRecomp-linux-<arch>.tar.gz`. The generated package
README uses `RECOMP_EXE` pointing to `Pharaoh.exe`, whose parent supplies
the game data root; no game files are packaged. A separate `--target smoke`
build is included for Linux because the default app target does not build
`pop_smoke` on a clean checkout.

When machines become available, compare matching first-mission smoke dumps
against macOS using `kit/tools/recomp/compare_frames.py` with fresh profiles
and matching display settings. Only small timing differences are expected,
not yet measured. Verify the interactive Vulkan window and first-mission
play, record the GPU and driver, and collect `RECOMP_GPU_VALIDATE=1` output
(including validation-layer availability). On Windows, check guest `\`
paths against host separators during game-data lookup and save/load; any
confirmed failure belongs in kit `platform/os_win32.cpp` with a
`platform_tests` case. No platform fix is attempted here.

Local verification on this Mac (these checks do not run the game):

| Command | Actual result |
| --- | --- |
| `.venv/bin/python -m pip install pyyaml` | Exit 0; installed PyYAML 6.0.3 after the initial YAML parse reported `ModuleNotFoundError: No module named 'yaml'`. |
| `.venv/bin/python -c "import yaml,sys; yaml.safe_load(open(\".github/workflows/checks.yml\"))"` | Exit 0 after installation; workflow YAML parses. |
| `.venv/bin/python tools/test.py` | Exit 0; 101 passed, 3 skipped in 6.48 s. |
| `.venv/bin/python -m pytest -q tests` | Exit 0; 4 passed in 0.01 s. |
| `.venv/bin/python tools/build.py --stub` | Exit 0; configured `build/cmake/macos-stub` and linked `build/stub/PharaohRecomp.app`. Existing kit keypad/presenter C-linkage warnings were emitted. |

The kit remains unchanged on `pharaoh` at
`4c95977c201c7a1710c9fab051121ee459f3149d`; no re-pin is needed.

#### 2026-09-14: Task 5.1 iOS bundle, install and automated first boot

Started on clean game `main` `210d53ab3eca40877803ec3ba1847c2260913c6d`
and clean kit `pharaoh` `2fe5c5dcd967286138820338dd1cb71975aa0314`,
already pinned here. No kit source, touch setting, address, translation or
submodule pin changed. The kit supplies `[touch] keypad = "auto"` by
default; no touch adjustment was made without device-play evidence.

**Step 1.** Used `.venv/bin/python` with `importlib.util` to load
`kit/tools/stage_game_files.py`, `tomli` to read `game.toml`, and the real
`excluded(relative, patterns)` helper to sum file sizes below
`original/gog/app`. Both measurements exited **0**:

| Bundle selection | Files | Bytes | MiB | Snippet's integer MB output |
| --- | --- | --- | --- | --- |
| Original exclusions | 1,311 | 781,484,469 | 745.282 | 745 |
| Also exclude `BINKS` | 1,304 | 634,766,385 | 605.360 | 605 |

The measured original size supersedes the plan's approximate 760 MB.
Seven undecoded cinematics account for **146,718,084 bytes / 139.921 MiB**.
Added `BINKS` to `[bundle].exclude` and the exclusion test's required
patterns; moved `BINKS/High/intro_big.bik` into its dropped-path cases.
Setup still requires the complete original installation including `BINKS`.
The executable, model text, graphics, audio and maps remain included.
This is a source-file sum, not an installed-app or seeded-directory size.

The post-change Python check also verified the pinned executable's SHA-256,
image base **0x00400000**, entry **0x00562fea**, and byte-identical
generated/kit `x86.h`: exit **0**. No regeneration was needed.
`.venv/bin/python -m pytest -q tests` exited **0**, **4 passed**;
`.venv/bin/python -m pytest -q kit/tests/test_game_literals.py` exited
**0**, **3 passed**. Full test output remains under ignored
`build/task-5.1-config-tests.log` and `build/task-5.1-game-literals.log`.

**Step 2.** `xcrun devicectl list devices` exited **0** and listed
**15A75531-8976-580D-AF09-5DAA939FDF32** as **available (paired)**,
an **iPad Pro 11-inch (M4), iPad16,3**. Ran the adapted build once:

```sh
set -o pipefail
.venv/bin/python tools/build.py --target ios --team BDFW2Z27HA \
  --device 15A75531-8976-580D-AF09-5DAA939FDF32 --console --no-install \
  2>&1 | tee build/ios-1.log | tail -30
```

Captured zsh `pipestatus` immediately: **1 / 0 / 0** for build, `tee`
and `tail`. Read the complete log. CMake reports both compiler identities
as unknown, then at `CMakeLists.txt:2 (project)`:

```text
No CMAKE_C_COMPILER could be found.
No CMAKE_CXX_COMPILER could be found.
```

That shell failed before compilation, signing or staging. **Environment
note:** the orchestrator identified a compiler probe targeting
`arm64-apple-macos17.0` with the macOS SDK: something in that shell's
environment overrides the iOS sysroot. This is not recorded as a kit bug;
the particular override remains unidentified. The orchestrator then built,
installed and launched from another shell, supplying ignored
`build/ios-2.log` and `build/ios-console-1.log` for this resumed write-up.
The build/install/console sequence is:

```sh
set -o pipefail
.venv/bin/python tools/build.py --target ios --team BDFW2Z27HA \
  --device 15A75531-8976-580D-AF09-5DAA939FDF32 --console --no-install \
  2>&1 | tee build/ios-2.log | tail -30
xcrun devicectl device install app \
  --device 15A75531-8976-580D-AF09-5DAA939FDF32 \
  build/ios/Release/PharaohRecomp.app
perl -e 'alarm 100; exec @ARGV' xcrun devicectl device process launch \
  --device 15A75531-8976-580D-AF09-5DAA939FDF32 --terminate-existing \
  --console dev.recompkit.pharaoh > build/ios-console-1.log 2>&1
```

`build/ios-2.log` records AppleClang **21.0.0.21000101**, the
**iPhoneOS26.5 SDK**, `arm64-apple-ios17.0`, eight build jobs and
`** BUILD SUCCEEDED **`, followed by **build exit 0**. The app is
**`build/ios/Release/PharaohRecomp.app`**, bundle size **`626M`** as
reported in that log. The staging line copies **1,304 files** from
`original/gog/app` into that app's `game/` directory. `devicectl` reports
**App installed**, bundle ID **`dev.recompkit.pharaoh`**, and **install
exit 0**. This is app-bundle evidence; the device's seeded-directory size
was not measured.

`build/ios-console-1.log` records a successful application launch and:

- **Game path/seeding:**
  `/var/mobile/Containers/Data/Application/BEB2C1ED-3C90-43E3-9322-359599B38926/Documents/game/Pharaoh.exe`,
  entry **`00562fea`**. There are no explicit seeding-success, stamp or
  copy-count lines and no seeding/path failure. The path confirms use of
  `Documents/game`; the console does not distinguish a fresh copy from
  reuse. The stager writes the executable hash to `.stamp`; the iOS host
  copies when the executable is absent or the stamp differs and logs copy
  failures, not successful stamps or sizes.
- **Display:** `GPU backend: metal`; window **1210x834 points**, **2420x1668
  pixels**, focus yes; presenter drawable **2420x1668**, at most **3**
  submissions in flight. `[host] display mode 640x480 16bpp` appears
  **three times**.
- **Surfaces:** `OutputDebugString` initially reports `Front Surface Ptr:
  15e0e90` and `Back Surface Ptr: 1676e90`, then twice `Front Surface Ptr:
  1705e10` and `Back Surface Ptr: 179be10`. All three sets report
  `Front Buffer: 1404e30` and `Back Buffer:  1404e40`.
- **Audio:** the host logs its original-gain mixing/clipping policy, then
  `audio device running: mixer 48000 Hz stereo, device 48000 Hz 2 ch, 1024
  frames`. The first buffer is channel **0**, **44100 Hz**, **2 ch**,
  **1152 frames**, peak **0.000**, volume **0.79**, rendered at **48000 Hz**
  to the output device. It then reports `audio channel 0 is a stream now,
  continuing from byte 0`. Sink reports at **1,408**, **2,815** and **4,222
  pulls** each have **0 late (>1.5 periods), 0 starved**, max gap **21.5
  ms**, max render **0.1 ms**, period **21.3 ms**, ahead **2,048 frames**.
  This verifies streaming activity and sink service, not audible or
  non-silent music; no listening check was recorded. The separate MIDI warning is
  `no SoundFont was found, so the music is accepted and not heard`.
- **Other diagnostics:** `boot: the mod loader reported a failure`,
  `gdi: TextOutA is accepted and not drawn in this runtime`,
  `AdjustWindowRectEx: no non-client area is modelled`, and UIKit
  unbalanced appearance-transition warnings. No repair was attempted.

The presenter reports this fault before the audio-device/stream lines:

```text
presenter: FAULT: drawable acknowledgement exceeded queue grace; using command completion fallback (unique=0 drops=4 flight=1 mailbox=0)
```

The capture continues through the three audio sink reports. Its final
`App terminated due to signal 14.` is the orchestrator's **100-second
Perl alarm**, not an application fault. `build/ios-2.log` records **launch
exit 1** for that timed console command; it is not a clean guest-exit
result. The presenter fallback fault above is a separate runtime finding.
There is no screen capture proving the title or main menu was displayed.

**Step 3: playing on the iPad by hand was not performed.** Nothing was
touched by hand: title/menu taps, Begin Family History, keypad name entry,
reaching the city, house building, holding each edge to scroll and
long-pressing a building remain unverified. README gives the commands and
this by-hand checklist; no touch fix or `input_touch_tests` case was added.

**Step 4: resumed write-up and commit.** Re-ran
`.venv/bin/python -m pytest -q tests`: **4 passed, exit 0**.
Output is in ignored `build/task-5.1-resume-config-tests.log`.
`git diff --check` exited **0**. The scoped game commit contains
`game.toml`, `tests/test_game_config.py`, `README.md`, `docs/analysis.md`
and `CHANGELOG.md`. Native suites, another device run and other platforms
were not run during this resume. No kit commit, re-pin, landing-checkout
change or push; kit remains **`2fe5c5dcd967286138820338dd1cb71975aa0314`**.
Game inputs, saves, generated files and build logs remain local and
uncommitted.

#### 2026-09-14: Task 4.2 automated macOS title capture and frame pacing

Started on clean game `main` `88197ea` and clean kit `pharaoh`
`2fe5c5dcd967286138820338dd1cb71975aa0314`, already pinned here. Followed
the unattended adaptation: app launch, timed captures and one AppleScript
click attempt, then a menu smoke timing measurement and listing analysis.
**This is not five minutes of hand play or first-mission app verification.**
No kit code, hook value, sentinel test or submodule pin changed.

**Step 1 — app.** Read-only Python/pefile checks exited **0**: pinned
SHA-256, image base and entry point match, and generated `x86.h` is identical
to `kit/runtime/x86.h`. Ran:

```sh
.venv/bin/python tools/build.py --jobs 8 > build/task-4.2-app-build.log 2>&1
```

Exit **0**, app linked and signed, **6** existing C-linkage return-type
warnings and **0** compiler errors. No regeneration was needed. Source
inspection finds no `RECOMP_MAX_SECONDS` reader in the SDL app: its
`BootOptions.deadline_seconds` is explicitly zero. The shared presenter
reads `recomp_env("FRAME_TIMINGS")` as a **CSV filename**, not a boolean.
Launched the rebuilt bundle executable directly with these environment
values (absolute paths below are relative to this checkout's `$PWD`):

```sh
RECOMP_PROFILE_DIR="$PWD/build/recomp/profile/task-4.2-app.evp55p6k" \
RECOMP_MAX_SECONDS=40 \
RECOMP_FRAME_TIMINGS="$PWD/build/task-4.2-app-timings.csv" \
RECOMP_HOST_AUDIO_CAPTURE="$PWD/build/task-4.2-app-audio.wav" \
RECOMP_TRACE_POINTER=1 \
build/PharaohRecomp.app/Contents/MacOS/PharaohRecomp > build/task-4.2-app.log 2>&1
```

The profile was created fresh with Python `tempfile.mkdtemp`; existing
families were preserved. A Python subprocess supervisor waited 12 seconds,
then ran `screencapture -x build/app-title.png`: exit **0**. `cliclick`
is absent. AppleScript's window query returned position `(320,43)` and
size `(1280,992)` points, including the title bar. Ran this click attempt:

```applescript
tell application "System Events"
    tell process "PharaohRecomp"
        set frontmost to true
        click at {960, 555}
    end tell
end tell
```

`osascript` returned **0**, identifying the Pharaoh Gold window. Waited
four seconds, then `screencapture -x build/app-after-click.png` exited
**0**. Both PNGs are **3840x2160** desktop captures, visually inspected:
Cleopatra portrait, gold title, pyramids and **Click to Start**, with the
host timing overlay at upper right. The game artwork below the overlay is
pixel-identical between captures. The title did **not** advance; the
pointer trace contains **zero `[pointer-button]` events**, so AppleScript's
success does not establish delivery of a game click or a cursor offset.

`osascript -e 'quit app "PharaohRecomp"'` exited **0**. The app reported
guest `ExitProcess(0)` at **38.6 s**, then logged **SIGSEGV**,
`EIP=0056478f ESP=0effff40 EBP=0effffd8`; its process exited **5** after
**39.963 s** wall time. The supervisor's fallback termination was unused.
This is a shutdown fault, not a clean app exit or the 40-second switch
taking effect. No repair was attempted in this measurement task.

Observed resolution, pacing, sound and limitations:

- Guest mode **640x480 16bpp**, window content **1280x960 points**, drawable
  **2560x1920 pixels**. The full title is visible with no obvious colour
  corruption. Resolution switching was not exercised.
- **785 guest presents / 38.6 s = 20.34/s** including startup. Both captured
  overlays report **20.0 new FPS**, **50.0 ms** frames and **58.3 ms** P95;
  their displayed/repeated rates differ. One drawable acknowledgement
  timeout used command-completion fallback; the final counters report
  **4 drops, 1 fault**. The timing CSV has **2520 rows** versus **2544**
  completions in the final counters. The presenter buffers CSV writes;
  the 24 missing rows are consistent with the shutdown fault losing that
  tail, so this is not a complete-run timing record.
- The host warns that the sentinel DirectInput pointer has a vtable
  mismatch and uses window position differences. Mouse motion is logged;
  button delivery and cursor alignment remain unverified. No cursor hook
  was changed from this observation.
- The mixer capture is **38.058667 s**, stereo 48 kHz, 16-bit PCM, peak
  **0.760315**. The host reports **38.0 s non-silent**, **0 discontinuities**,
  **0** silent gaps longer than 50 ms with a voice playing, and **0 late / 0
  starved** pulls in its audio-sink diagnostic. Miles streaming reaches
  the app's mixer; subjective listening and click effects were not tested.
  The separate missing-MIDI-SoundFont notice does not negate this PCM output.
- The mod-loader failure, undrawn GDI `TextOutA` and unmodelled non-client
  area diagnostics remain. Mission entry, building houses, right-click
  panels, edge/arrow scrolling, options and menu Save/Load were not tested.

**Step 2 — pacing.** Used the existing smoke binary with a fresh profile.
To supply the requested literal `RECOMP_FRAME_TIMINGS=1` without writing
into the repository root, ran from the fresh ignored directory
`build/task-4.2-smoke.7sjcuty3`. In this command, `task_root` is the absolute
game checkout path captured before changing directory:

```sh
RECOMP_PROFILE_DIR="$task_root/build/recomp/profile/task-4.2-smoke.gbbmeiio" \
RECOMP_SCRIPT="$task_root/smoke/main-menu.script" \
RECOMP_HOST_DUMP_DIR="$task_root/build/task-4.2-smoke.7sjcuty3/frames" \
RECOMP_DDRAW_MODES=640x480x16 RECOMP_SMOKE_DRAWABLE=1024x768 \
RECOMP_FRAME_TIMINGS=1 RECOMP_MAX_SECONDS=20 \
"$task_root/build/recomp/pop_smoke" > "$task_root/build/task-4.2-smoke.log" 2>&1
```

Exit **0**, guest exit **0**, **21.0 s** logged (**21.150 s** process wall
time), **4/4** steps, **438** guest presents (**3** changed from their
predecessor), **3** dumps, **640x480 16bpp**, no undeliverable calls.
Read the complete log. The smoke host also ignores `MAX_SECONDS`; its
deadline is 180 seconds plus grace. The script's waits sum to
**15 + 4 + 2 = 21 seconds**, so it completed naturally and the requested
**20-second measurement** is a window within this run, not a claimed
20-second process lifetime. No script or host deadline was changed.

The file named `1` contains **2488** timing rows: **417 new**, **2071
repeats**, all `display_ack=0` because this is offscreen. Counting
`repeat=0` in `[first presented_s, first presented_s + 20)` gives
**402 / 20 = 20.10 new frames/s**. Including repeats gives **2401 / 20 =
120.05/s**, which is not game frame rate or physical-display evidence.
The whole-run guest-call counter averages **438 / 21 = 20.86/s** including
startup. Its **22366 audio plays**, peak **0.782**, do not prove smoke music
output; the smoke streaming limitation from Task 3.2 still applies.

Ran the task's exact listing search:

```sh
grep -l "timeGetTime\|GetTickCount" analysis/decompiled/Pharaoh.exe/functions/*.asm | head
```

**No matches** (`grep` **1**, `head` **0**): these listings use numeric IAT
operands. Used the adaptation's three supplied return addresses to find
their containing functions with `rg`, then verified the import table and
the actual six-byte `FF 15 2C F2 56 00` calls in the pinned executable:

| Function/listing | Call | Return | Role |
| --- | --- | --- | --- |
| `FUN_004d6b60`, `functions/004d6b60.asm` | `004d6b73` | `004d6b79` | Per-iteration timestamp stored before the update/draw work; calls `FUN_004ddcb0`. |
| `FUN_004ddcb0`, `functions/004ddcb0.asm` | `004ddcb2` | `004ddcb8` | Compares elapsed time with the speed-dependent simulation threshold; returns zero when not due. |
| `FUN_004d0040`, `functions/004d0040.asm` | `004d0040` | `004d0046` | Returns milliseconds since its previous call and updates that timestamp. |

All three target IAT **`0056f22c = WINMM.dll!timeGetTime`**.
`FUN_00413ed0`'s idle message loop calls `FUN_004143c0` at `0041436a`,
which calls `FUN_004d6b60`. Its draw path calls `FUN_004d0280`, which
calls the delta helper at `004d02c5`, accumulates milliseconds, loads
**`0x32 = 50`** at `004d02df`, compares at `004d02f5` and returns without
drawing through `004d02fb` when below the threshold. Forced-redraw paths
can bypass the gate. The outer loop polls this time gate; the helper does
not sleep. This explains the measured approximately 20 FPS menu cadence.

**Keep all five `frame_clock_*` sentinels.** The kit's
`native_frame_clock` is called only by `k_GetTickCount`; `m_timeGetTime`
returns `host_millis()` without that hook. IAT `0056f12c` is `GetTickCount`;
its five numeric references in four listings belong to elapsed-time
instrumentation, a stateful timed routine and the Bink loop, not this
50 ms draw gate. No verified GetTickCount draw-wait site was identified,
so `tests/test_game_config.py` needs no exception. There is no pacing
override or claim of faster gameplay in this task.

**Verification and delivery.** Converted each of the three smoke dumps
with `.venv/bin/python kit/tools/recomp/ppm_to_png.py INPUT.ppm OUTPUT.png`:
**3 conversions, exit 0**, all **640x480**. Visually inspected title and
menu; Pillow confirms all PNGs match their PPMs and both menu captures are
identical. `.venv/bin/python -m pytest -q tests` exited **0**, **4 passed**.
`.venv/bin/python build/task-4.2-verify.py` exited **0**, checking identity,
header parity, all three call instructions, the 50 ms gate, CSV counts,
images, PCM, logged results and ignored artifacts. The original
`Pharaoh.ini` content and timestamp are unchanged; no save/settings files
were added under `original/gog/app`. Both test profiles and all captures,
logs and helper/metric files remain ignored under `build/`.
An extra TOML/link check initially exited **1** because this Python lacks
`tomllib`; using the installed `tomli` fallback exited **0**, confirming
identical parsed config values and valid local documentation links.

Only `game.toml` comments, this record, README's launch/hand-check guidance
and the game changelog are committed. Git whitespace and staged-scope
checks passed. No native suites or formatter were run because native code
and config values are unchanged. No new kit commit, re-pin,
landing-checkout change, other-platform run or push was performed.

#### 2026-09-14: Task 4.1 reaches Nubt; menu save/reload remains untested

Started on clean game `main` `6d5264c` and clean kit `pharaoh`
`2fe5c5dcd967286138820338dd1cb71975aa0314`, already the submodule pin.
Used the existing smoke binary. Read-only Python/pefile assertions exited
**0**: the executable matches the pinned SHA-256, image base and entry
point, and generated `x86.h` matches `kit/runtime/x86.h`. No kit changes,
re-pin, native build, regeneration or landing-checkout work was performed.

**Steps 1 and 2 reach an advancing city. Step 3 is incomplete:** no Escape,
Save-menu confirmation or restart/Load was attempted before the requested
eight-round limit. The files observed below are automatic saves, not proof
of a menu save or reload. The script and this record are committed as partial
Task 4.1 work.

`smoke/first-mission.script` uses guest coordinates at 640x480. Its final
path is title centre `(320,240)` → Play `(320,112)` → name `pyn` using
`key P/Y/N down/up` and Return → Begin Family History `(320,140)` →
Predynastic Begin **arrow** `(612,452)` → Nubt's To the city arrow
`(593,439)` → Housing and Roads checkmark `(611,452)` → city.
The parser's real `host_script_dik` table supports P, Y and N but not A;
100 ms key holds and release waits delivered the name correctly.

Rounds 1–3 used the default `build/recomp/profile`. Round 2 created
`Save/pyn.dat`, so round 3 reopened the Family Registry and could not replay
name entry. Preserved that file and used a separate, initially absent
profile under `build/recomp/profile/task-4.1-round-N` for each round 4–8.
README documents running the final script with a fresh profile; it does
not select or overwrite an existing family's saves.

Each round used this smoke command with `N` replaced by its round number:

```sh
RECOMP_SCRIPT=$PWD/smoke/first-mission.script \
RECOMP_HOST_DUMP_DIR=build/smoke/task-4.1-round-N \
RECOMP_DDRAW_MODES=640x480x16 RECOMP_SMOKE_DRAWABLE=1024x768 \
RECOMP_MAX_SECONDS=150 build/recomp/pop_smoke > build/task-4.1-round-N.log 2>&1
```

For rounds 4–8 it also set
`RECOMP_PROFILE_DIR=$PWD/build/recomp/profile/task-4.1-round-N`.
Each script version is retained in its dump directory as `script.script`.
The current smoke host does **not** read `RECOMP_MAX_SECONDS`: its
`BootOptions` deadline is 180 seconds with 20 seconds' grace. The requested
variable was supplied on all eight runs; each finished through the script's
end and guest `ExitProcess(0)`, before either limit.

| Round | Added or corrected input; observed final screen | Exit | Elapsed | Completed steps | Presented frames (changed from previous) | Dumps |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Play → Enter a family name | **0** | **23.0 s** | **5/5** | **478 (4)** | **3** |
| 2 | P/Y/N and Return → pyn family menu | **0** | **27.8 s** | **15/15** | **574 (5)** | **5** |
| 3 | `(320,140)` after the replayed name keys → Family Registry; persisted family changed the entry flow | **0** | **32.8 s** | **17/17** | **674 (4)** | **6** |
| 4 | Same script, fresh profile → Predynastic Period | **0** | **32.8 s** | **17/17** | **673 (6)** | **6** |
| 5 | Begin text `(445,451)` → unchanged Predynastic screen | **0** | **37.8 s** | **19/19** | **772 (6)** | **7** |
| 6 | Replace text click with Begin arrow `(612,452)` → Nubt briefing | **0** | **37.8 s** | **19/19** | **781 (9)** | **7** |
| 7 | To the city `(593,439)` → Housing and Roads tutorial, including all three provisionally named city captures | **0** | **69.8 s** | **23/23** | **1420 (11)** | **10** |
| 8 | Tutorial checkmark `(611,452)` → city, followed by timed captures | **0** | **71.8 s** | **25/25** | **7055 (3273)** | **11** |

Read every complete run log. All report **640x480 16bpp**, **no
undeliverable calls**, guest exit **0**, and `all expectations met`.
That last line is not a gameplay assertion: this script has no `expect`
commands. No unknown-arity/unimplemented import or guest fault is logged.
The existing diagnostics remain:

```text
[recomp] boot: the mod loader reported a failure
[recomp] ddraw: RECOMP_DDRAW_MODES offers 1 mode instead of the built-in list; SetDisplayMode accepts the same set
[recomp] gdi: TextOutA is accepted and not drawn in this runtime
[recomp] AdjustWindowRectEx: no non-client area is modelled
```

The following DirectDraw line also warns that the offered list omits
640x480x8; every observed selected mode is 640x480x16. No new blocking kit
gap was established. The high smoke audio-play counts do not establish
music output, for the streaming-callback limitation recorded in Task 3.2.

Every dump was converted with the actual filename convention:

```sh
.venv/bin/python kit/tools/recomp/ppm_to_png.py \
  build/smoke/task-4.1-round-N/smoke_NAME_present.ppm \
  build/smoke/task-4.1-round-N/smoke_NAME_present.png
```

**55 conversions, all exit 0, all 640x480.** Read-only Pillow checks exited
**0**: all 55 PNGs match their PPMs pixel-for-pixel. New screens were viewed
directly; repeated captures were checked against the inspected images.
Every PNG path is `build/smoke/task-4.1-round-N/smoke_NAME_present.png`,
with the following complete inventory and readings:

| `NAME` | `N` | Reading |
| --- | --- | --- |
| `title-screen` | 1–8 | Cleopatra portrait, gold title, Click to Start. |
| `main-menu` | 1–8 | Throne room and five orange buttons, Play at `(320,112)`. |
| `after-play` | 1–2, 4–8 | Enter a family name; empty text field. |
| `after-play` | 3 | Family Registry with `pyn`, Create/Delete/Proceed controls. |
| `family-name` | 2, 4–8 | Name field contains `pyn`. |
| `family-name` | 3 | Unchanged Family Registry. |
| `after-family-name` | 2, 4–8 | pyn family menu; Begin Family History at `(320,140)`. |
| `after-family-name` | 3 | Unchanged Family Registry. |
| `after-begin-family-history` | 3 | Family Registry, still no campaign transition. |
| `after-begin-family-history` | 4–8 | Predynastic Period selected; description and Begin arrow at lower right. |
| `after-predynastic-begin` | 5 | Same Predynastic screen; clicking the text had no visible effect. |
| `after-predynastic-begin` | 6–8 | Nubt, A Village is Born; objective 6 Meager Shanties, difficulty Normal, To the city arrow. |
| `city-entry`, `city-10s`, `city-30s` | 7 | Identical Housing and Roads tutorial pages, not city evidence. |
| `housing-and-roads` | 8 | Housing/road instructions and illustration, lower-right checkmark. |
| `city-entry` | 8 | Terrain, roaming animals, right-hand building controls/minimap; population 0, February 3500 BC. |
| `city-10s` | 8 | Animals in different positions; July 3500 BC; Game saved notification. |
| `city-30s` | 8 | Animals have moved again; February 3499 BC; Game saved and Flood will be mediocre notifications. |

The final script waits two seconds after the tutorial checkmark for
`city-entry`, then ten seconds for `city-10s`, then twenty more for
`city-30s` (41.8, 51.8 and 71.8 seconds into the script). These are host
waits, not simulated calendar seconds. It builds no housing; **human
workers/immigrants remain unverified**. Animal movement and date advancement
establish that the city simulation runs.

Copied the final two PPMs byte-for-byte to the task's requested comparison
paths (`build/smoke/city-10s.ppm` and `city-30s.ppm`; copy/assertions exit
**0**), then ran exactly:

```sh
.venv/bin/python kit/tools/recomp/compare_frames.py build/smoke/city-10s.ppm build/smoke/city-30s.ppm
```

Exit **1**, output **`mean 2.139 max 255 outliers 3.15% (> 24) over
640x480`**. This tool tests similarity, so exit 1 means its default
similarity bounds were exceeded; the task expects movement. An additional
Pillow count found **9,919 / 307,200 pixels changed (3.228841%)**. Changes
include notifications/date text as well as the visibly moving animals;
the full-frame fraction is not exclusively a walker metric.

At the eight-round limit, ran the requested file check without extending
the script or starting another host:

```sh
find build/recomp/profile -iname '*.sav' -newer smoke/first-mission.script
```

Exit **0**, exactly **two** results:

- `build/recomp/profile/task-4.1-round-8/Save/pyn/autosave_history.sav`
  (**308,196 bytes**).
- `build/recomp/profile/task-4.1-round-8/Save/pyn/autosave_replay.sav`
  (**308,064 bytes**).

Round 7 also left an older `autosave_replay.sav` in its own profile.
These files and the Game saved notifications prove automatic writes under
the profile. **Menu Save, confirmation, restart/Load and settings changes
remain undone.** No manual-save command was added without testing it.

Final read-only artifact/log checks exited **0**: all eight logs complete,
all repeated final screens match inspected references, the original
`Pharaoh.ini` content and timestamp are unchanged, and there are **zero**
new save/settings files (`.sav`, `.dat`, `.ini`, `.jas`) under
`original/gog/app`. Existing files were preserved. All **163** checked task
artifacts/profile files are ignored. Game and kit whitespace checks and
the staged four-file scope check passed. No portable/native suite was
rerun for this script/documentation-only task; no interactive app,
other-platform run, kit commit or push was performed.

#### 2026-09-14: land Phase 2-3 on kit main (Task 3.3)

Started on clean game main `baad47b`, clean kit `pharaoh`
`2fe5c5dcd967286138820338dd1cb71975aa0314`, and clean landing-checkout
main `31f0f24`. Used the task's corrected test routes instead of
`tools/test.py --native`: native `nogame` tests use the kit's stub game,
while `runtime_tests` uses this game's image and build tree.

Step 1 verification, in order (outputs retained under ignored
`build/task-3.3-*.log`):

| Command | Actual result |
| --- | --- |
| `.venv/bin/python tools/test.py` | Exit **0**; **88 passed, 3 skipped**. |
| `.venv/bin/python -m pytest -q tests` | Exit **0**; **4 passed**. |
| `.venv/bin/python kit/tools/test.py --game-dir /Users/sattam.thakur/Documents/Tests/pharaoh-recomp/kit/games/stub --compile-only` | Exit **0**; configured the stub tree, all test binaries current (`ninja: no work to do`); **0** compiler warnings/errors. |
| `.venv/bin/ctest --test-dir kit/build/cmake/macos -L nogame --output-on-failure` | Exit **0**; **11/11 entries passed**, **0** failures. Per-entry counts below. |
| `.venv/bin/python tools/test.py --compile-only` | Exit **0**; game-tree test binaries built, **6** existing compiler warnings, **0** errors. `profile_tests` is not defined because the translation has no `FN_00500040`. |
| `.venv/bin/ctest --test-dir build/cmake/macos -R runtime_tests --output-on-failure` | Exit **8**; **520 checks, 32 failures**, **0/1** CTest entries passed. Output piped through `tee build/task-3.3-runtime.log` and `tail -40`; pipeline exits **8 / 0 / 0**. |
| From `kit/`: `../.venv/bin/python tools/check_repo.py` | Exit **0**; tracked source boundaries and local documentation links passed. |
| From `kit/`: `../.venv/bin/python tools/check_game_literals.py` | Exit **0**; no findings. |

The `nogame` details were read from CTest's `LastTest.log` and retained in
`build/task-3.3-nogame-detail.log`. Every entry passed:

| Entry | Reported checks/tests |
| --- | --- |
| `platform_tests` | **79 checks, 0 failures** |
| `host_api_header_check` | **1 passed entry**; one existing `#pragma once in main file` warning |
| `dx_tests` | **138,479 checks, 0 failures** |
| `null_host_link` | **1 passed entry**; weak defaults resolved |
| `layout_tests` | **31 checks, 0 failures** |
| `host_boundary_check` | **2 tests, OK** |
| `shader_drift_check` | **1 test, OK** |
| `input_touch_tests` | **1 passed entry**, reports `ok` without a check count |
| `keypad_tests` | **1 passed entry**, reports `ok` without a check count |
| `ui_layer_tests` | **115 checks, 0 failures** |
| `gpu_fake_tests` | **26 checks, 0 failures** |

A read-only Python comparison with `build/task-2.9-green-runtime.log`
exited **0**: the same **32** failure messages remain, with no additions
or removals. They are the known Populous-bound baseline recorded in Task
2.3a, not a passing runtime suite. Other game-labelled, GPU/device, mod,
gameplay and integration suites were **not run**. A read-only byte
comparison also exited **0**: generated `build/recomp/gen/x86.h` matches
`kit/runtime/x86.h`. No regeneration or native source change was needed.

Step 2 landed the existing branch without a merge or rebase:

```sh
cd /Users/sattam.thakur/Documents/Tests/recomp-kit
git -c protocol.file.allow=always pull --ff-only /Users/sattam.thakur/Documents/Tests/pharaoh-recomp/kit pharaoh
git push origin main
cd /Users/sattam.thakur/Documents/Tests/pharaoh-recomp
git -C kit -c protocol.file.allow=always fetch local main
git -C kit checkout -q -B pharaoh local/main
```

All four Git operations exited **0**. The pull fast-forwarded main from
`31f0f24` to `2fe5c5d`; the explicitly authorized push updated only kit
main at its GitHub origin. From the landing checkout,
`git ls-remote --exit-code origin refs/heads/main` exited **0** and returned
**`2fe5c5dcd967286138820338dd1cb71975aa0314`**, matching landing main,
submodule `pharaoh` and `local/main`. No new kit commit was created.
The game already pinned this exact commit, so staging `kit` produces no
gitlink difference; this task records that its existing pin is now on main.

README and CHANGELOG now record the macOS title screen, main menu and
Miles audio status established by Tasks 2.6, 3.1 and 3.2. Smoke verifies
the menu transition and effects; the headless title capture establishes
MP3 output. Smoke has no streaming callbacks, so its play counter does
not establish music output. No new host run, listening test, main-menu
music capture, gameplay or other-platform validation was performed here.
Logs, generated files, binaries, game inputs and saves remain uncommitted;
the game repository was not pushed.

#### 2026-09-14: MP3 streams through Miles (Task 3.2)

Started from game main `c4e846b` and kit `pharaoh` `f4ae821`, both clean.
Kit commit `2fe5c5dcd967286138820338dd1cb71975aa0314` extracts `Mp3Source`
from DirectShow and implements Miles stream open/start/close/status, volume
and loop counts. The stream owns the encoded bytes and a shared audio
channel. It resolves paths through `win32_host_path_op(..., WIN32_FILE_READ)`,
converts the first host play to a stream, retains refused PCM chunks, and
refills while the appended queue has less than one second of audio.
`mss32_frame_pump` is registered beside `qmixer_frame_pump`, services samples
as well as streams, and ignores a null CPU. Decoder EOF does not report
Miles status 2 until submitted audio has played out. Tracked changes are
limited to the audio shims, decoder, tests, build list, documentation and
submodule pin; no runtime, translator, addresses or host implementation changed.

The fixture already exists: `kit/dx/tests/fixtures/tone_mp3.h` contains a
3,179-byte synthetic stereo MP3. The regression writes it under a temporary
`Music/Test.mp3` and opens `music\test.mp3`, using the same `win32_init`
mapping as DirectShow. No private fixture or optional developer-data skip
was needed. Real test helpers are `sc`, `gm_put_str`, and `&g_cpu`.

Verification, in order (full outputs remain in ignored `build/task-3.2-*`):

- Native build command, used before the red run, after extraction, after
  stream implementation and after final formatting:

  ```sh
  .venv/bin/python kit/tools/test.py --game-dir /Users/sattam.thakur/Documents/Tests/pharaoh-recomp/kit/games/stub --compile-only
  ```

  All four completed builds exited **0**. An initial authoring attempt
  exited **1** because the new test supplied a nonexistent mode argument to
  `os_mkdir`; corrected to its actual one-argument signature before the red
  run. This was not the expected regression failure. Final build: **1**
  existing `stalls` unused-variable warning, **0** errors.
- `.venv/bin/ctest --test-dir kit/build/cmake/macos -R dx_tests
  --output-on-failure`: the red run exited **8**, **138,427 checks, 4
  failures**, all in `Miles streams` (open, play, stream conversion and
  playing status). After decoder extraction it again exited **8** with the
  same count and failures; both DirectShow tests stayed **ok**. After stream
  implementation it exited **0**, **1/1** suite passed. After extending
  coverage and formatting, the final run exited **0**, **1/1** suite passed,
  **138,479 checks, 0 failures**. Coverage includes null pumps, queue refusal
  and retry, format and total PCM bytes, decoder EOF versus playback EOF,
  rewind, volume/clamping, two plays, infinite looping, the one-second refill
  threshold, close, and a missing file.
- `.venv/bin/python kit/tools/format.py --write`: **0**, **241** handwritten
  files formatted. The corresponding `kit/tools/format.py` check: **0**,
  **241** files checked. Only scoped files changed.
- `.venv/bin/python -m pytest -q kit/tests/test_game_literals.py
  tests/test_game_config.py`: **0**, **7 passed**.
  `.venv/bin/python kit/tools/check_game_literals.py`: **0**.
  From `kit/`, `../.venv/bin/python tools/check_repo.py` on staged changes:
  **0**, source boundaries and documentation links passed. Kit staged Git
  whitespace check: **0**.
- A read-only Python identity check: **0**; SHA-256
  `b21b7d719491bb45dfb324ba95231a5b0960ab25fea1bf3fb21da65da7eca662`,
  base `0x00400000`, entry `0x00562fea`, all matched.
- After committing the kit, rebuilt **both** hosts in order:

  ```sh
  .venv/bin/python tools/build.py --target smoke --jobs 8
  .venv/bin/python tools/build.py --target headless --jobs 8
  ```

  Both exited **0** and linked. Smoke build: **5** existing C-linkage
  return-type warnings, **0** errors; headless build: **0** warnings,
  **0** errors. Neither `x86.h` nor translation changed, so no regeneration
  was necessary.

Ran the prescribed headless capture with the requested display mode:

```sh
RECOMP_HOST_AUDIO_CAPTURE=build/audio-menu.wav RECOMP_MAX_SECONDS=30 RECOMP_DDRAW_MODES=640x480x16 build/recomp/pop_headless > build/headless-audio.log 2>&1
.venv/bin/python -c "import wave;w=wave.open('build/audio-menu.wav');print(w.getnframes()/w.getframerate(),'s')"
```

Both commands exited **0**. The duration command printed **24.0919375 s**:
**1,156,413 frames**, stereo 48 kHz, 16-bit PCM. A separate read-only Python
waveform measurement exited **0** and found absolute peak **24,632/32,768 =
0.751708984375**, with nonzero sound in every one-second capture block. Its
metrics are in ignored `build/task-3.2-audio-metrics.json`. The host reports
**23.8 s non-silent**, longest unbroken stretch **23.74 s**, **0
discontinuities**, one **330 ms** silence at the beginning with a voice
playing and a **10 ms** short dropout. There are **0** `underrun` or
`stream ran dry` diagnostics and **0** stream-open failures. Thus no failed
path or case-missing file was observed; successful paths were not traced.
This is the title-screen run: headless cannot click through to the menu.
The captured waveform establishes audio output; subjective listening was
not performed.

The duration differs from 30 seconds because the unchanged default frame
cap is **500**: the log explicitly says `frame cap reached, WM_CLOSE posted
(500 frames, 24.1s)`, followed by guest `ExitProcess(0)`. It presents **500**
frames (**50** written), 640x480x16, and releases its one audio channel.
`RECOMP_FRAMES` was not set; it is a directory switch, not a frame count.
No extra run or cap change was made. The known mod-loader, omitted 8-bit
mode, undrawn text and non-client-area diagnostics remain.

Then ran the existing smoke script:

```sh
RECOMP_SCRIPT=$PWD/smoke/main-menu.script RECOMP_HOST_DUMP_DIR=build/smoke RECOMP_DDRAW_MODES=640x480x16 RECOMP_SMOKE_DRAWABLE=1024x768 RECOMP_MAX_SECONDS=40 build/recomp/pop_smoke > build/task-3.2-smoke.log 2>&1
```

Exit **0**, **21.0 s**, **4/4** script steps, **438** presented frames,
**3** dumps, `all expectations met`, no undeliverable calls. Exact audio
line:

```text
audio:              22976 plays, loudest sample 0.782
```

This large count is **not music playback proof**. The smoke host counts
`host_audio_play` calls but has no stream/queue callbacks; its linked
`host_audio_stream` default returns **-1**, which leaves Miles status done
and permits repeated starts. The headless capture above is the streaming
output evidence. No smoke-host fallback or callback implementation was
added in this task. Game-backed `runtime_tests`, other platforms, longer
playback, audible main-menu music and gameplay were not tested. Neither
repository was pushed; landing on kit main remains outside Task 3.2.

#### 2026-09-14: sound effects through Miles (Task 3.1)

Kit `pharaoh` f4ae821: `dx/riff.cpp` parses a PCM RIFF WAVE image in guest
memory; `dx/mss32.cpp` implements `AIL_file_read` (the game passes a
destination of 0 at both call sites, so the shim allocates), `AIL_mem_free_lock`,
the sample handle API (allocate, init, set file, start, end, status, loop count,
volume 0..127 to millibels as `2000*log10(v/127)`, pan 0..127 to -10000..10000)
on the shared `dx_alloc_audio_channel` pool. `dx_tests`: 138,404 checks, 0
failures. The smoke run of `smoke/main-menu.script` (21 s, 4 steps) reports
`audio: 1 plays, loudest sample 0.782`: the click on the title screen. The
smoke host has no `RECOMP_HOST_AUDIO_CAPTURE`; captures are the headless
host's, so music is judged there once streams exist (Task 3.2).

#### 2026-09-14: Task 2.6 resumed; title screen and main menu reached in the smoke host

Resumed at Step 2 on clean game `main` at `7d53c5d` and clean kit
`pharaoh` at `8c8da01a05fe69aa2ba0a68b3bab2ae72a5c8ba2`, already the
game's submodule pin. Used the current smoke binary without rebuilding or
regenerating. No kit changes or submodule re-pin were needed. The existing
pin supplies the 41-entry silent Miles arity table, 19 Bink/Smacker shims
(Bink opens a finished record), 15 Win32 shims, retained-pointer display
writes and window geometry/mode fixes recorded below.

The initial PNG shows Cleopatra's title artwork and **“Click to Start”**.
Changed `smoke/main-menu.script` to wait 15 seconds, dump `title-screen`,
send exactly `click left 320 240`, wait four seconds and dump `main-menu`.
The first run showed menu buttons. Only then added `wait 2000` and
`dump main-menu-settled` and reran. No menu button was clicked in either
run; campaign entry is deliberately outside this resumed task.

Ran this prescribed command twice, first with output redirected to
`build/smoke-13.log`, then as shown with the final three-dump script:

```sh
RECOMP_SCRIPT=$PWD/smoke/main-menu.script RECOMP_HOST_DUMP_DIR=build/smoke \
RECOMP_DDRAW_MODES=640x480x16,800x600x16,1024x768x16 RECOMP_SMOKE_DRAWABLE=1024x768 \
RECOMP_MAX_SECONDS=40 build/recomp/pop_smoke > build/smoke-14.log 2>&1
```

| Run log | Host exit | Elapsed | Script steps | Presented frames | Dumps |
| --- | --- | --- | --- | --- | --- |
| `build/smoke-13.log` | **0** | **19.0 s** | **3/3** | **398**, 3 changed | **2** |
| `build/smoke-14.log` | **0** | **21.0 s** | **4/4** | **438**, 3 changed | **3** |

Read both complete logs. Each reports Metal, **640x480 16bpp**, guest
`ExitProcess(0)`, **0 audio plays**, **no undeliverable calls**, and a
presented non-black fraction of **0.997**. The script finishes before the
40-second cap; the logged stop is the guest exit, not the watchdog. Each
reports three input changes announced and zero input reads in its counter;
the captured screen transition is the evidence that the title click worked.
The logs still contain the mod-loader warning, the offered-mode warning
about omitted 640x480x8, undrawn `TextOutA` and no non-client area in
`AdjustWindowRectEx`. The selected mode is 640x480x16. Neither log reports
an unknown import, guest fault or `Unable to load BINK!`. Neither traces
`sierra.ini` or music-file opens; those paths remain unverified, and no
`RECOMP_LOG=1` run was added.

Converted every dump using the actual smoke-host filenames:

```sh
.venv/bin/python kit/tools/recomp/ppm_to_png.py build/smoke/smoke_title-screen_present.ppm build/smoke/title-screen.png
.venv/bin/python kit/tools/recomp/ppm_to_png.py build/smoke/smoke_main-menu_present.ppm build/smoke/main-menu.png
.venv/bin/python kit/tools/recomp/ppm_to_png.py build/smoke/smoke_main-menu-settled_present.ppm build/smoke/main-menu-settled.png
```

The first two conversions ran after each host run; the third ran after
the final run: **five conversions, all exit 0**, each **640x480**. Final
captures overwrite the first run's two capture names. Visually inspected
all five PNG results:

- **`build/smoke/title-screen.png` (15 s):** Cleopatra's portrait at
  left, gold Pharaoh/Cleopatra title and pyramids at right, “Click to
  Start” at the bottom and the studio logos at lower right.
- **`build/smoke/main-menu.png` (19 s):** an Egyptian throne room with
  decorated columns, two thrones at the back, and five orange menu
  buttons stacked across the upper centre.
- **`build/smoke/main-menu-settled.png` (21 s):** the same throne room
  and five buttons; pixel-identical to the preceding main-menu capture.

Approximate button centres, estimated from both menu images in **640x480
guest pixels** (not the 1024x768 host drawable):

| Button text | Centre (x, y) |
| --- | --- |
| Play Pharaoh/Cleopatra | **(320, 112)** |
| Activision Website | **(320, 152)** |
| Mission Editor | **(320, 192)** |
| Greatest Families | **(320, 232)** |
| Quit | **(320, 272)** |

Read-only `.venv/bin/python`/Pillow assertions exited **0**: each final
PNG matches its PPM pixel-for-pixel, all three are 640x480, timestamps
follow the final run's log creation, the title differs from the menu, and
the two menus are identical. Non-black pixels: **306,350 / 307,200** for
the title and **305,726 / 307,200** for each menu. Log assertions confirm
the steps, frames, dump counts, guest exit, silent audio and lack of
undeliverable calls. The smoke binary's SHA-256 is unchanged
(`62245a8d702f6f886173b8bac69214804b3847eff0ba8cb663fa66b61507dad4`);
the game's executable still matches its pinned SHA-256. `git check-ignore
-q` passed for both run logs and all six PPM/PNG captures.

Both repositories' `git diff --check` and the game's staged whitespace
check exited **0**. Only the script, this run entry, README status and
game changelog changed. No native or portable test suite was rerun for
this script/documentation task; no rebuild, regeneration, kit commit,
landing-checkout change, push or other-platform execution was performed.
Main-menu presentation and the title click are verified; menu-button
selection, gameplay and audio remain unverified. All captures and logs
remain ignored and uncommitted under `build/`.

#### 2026-09-13: Task 2.9 draws the Cleopatra title screen in the smoke host

Started on game `main` at `1371f4e` and kit `pharaoh` at `546f015`.
Kit was clean; the game's unrelated untracked `1/` directory was preserved.
The Task 2.8 changes were already committed and pinned at this point; its
older run record below describes the earlier, uncommitted stopping point.
Task 2.9's kit commit is `8c8da01a05fe69aa2ba0a68b3bab2ae72a5c8ba2`.
No changes were made in the separate kit landing checkout.

Read-only `pefile` and Capstone checks confirmed the pinned executable's
SHA-256, image base and entry point. At `0x00414de0`, the window procedure
subtracts one from the message before indexing the byte table at
`0x004163ac`. Messages 3 and 5 both select index 2 and target `0x00414e8a`
through the pointer table at `0x00416390`. An initial verification lookup
omitted that subtraction and failed; correcting the lookup from the
disassembly passed. The handler checks `DAT_00e38e5c`, then in fullscreen
calls `GetSystemMetrics(1)` and `(0)` and `SetRect` on `DAT_00e39130`.
Its windowed branch calls `GetClientRect` and `ClientToScreen` for both
corners. The imported function names were verified against the PE IAT.

- `kit/runtime/user32.cpp` posts `WM_MOVE` then `WM_SIZE` after successful
  creation, before the host's activation callback. Position and client size
  are packed into 16-bit halves with zero wParam. `SetWindowPos` posts each
  message unless its corresponding `SWP_NOMOVE`/`SWP_NOSIZE` flag is set.
  `Window::shown` limits `ShowWindow`'s size message to its first show;
  creation with `WS_VISIBLE` already delivers creation geometry and marks
  the window shown. `GetSystemMetrics(0/1/16/17)` reads the existing
  `ddraw_display_mode` hook, retaining the 1024x768 fallback and the
  19-pixel caption deduction for index 17.
- `kit/runtime/tests/runtime_tests.cpp` adds nine checks in `test_windows`,
  using its actual 640x480 creation size. These inspect queue order, packed
  geometry, zero wParam, no-op positioning, first show and repeated shows.
  The test restores its original geometry and visibility; callback tests
  drain their creation/show geometry before their existing queue checks.
- `kit/dx/tests/dx_tests.cpp` checks all four screen/fullscreen metrics at
  640x480x16 and their unchanged desktop fallback after a display reset.
  Both changelogs and README record this task's behavior and observed status.

Verification, in task order (full build/test output remains under ignored
`build/task-2.9-*.log`):

| Command | Actual result |
| --- | --- |
| `.venv/bin/python tools/test.py --compile-only` | Baseline, test-first and final builds: exit **0** each; compiler warnings **11 / 6 / 5**, errors **0** each. |
| `.venv/bin/ctest --test-dir build/cmake/macos -R runtime_tests --output-on-failure` | Baseline **511 checks / 32 failures**; test-first **520 / 37**; final **520 / 32**. CTest exit **8** and **0/1** suites passing each time. All five newly failing checks became passing; all nine new checks pass. Exact comparison confirmed the same 32 baseline failure messages. |
| `.venv/bin/python kit/tools/test.py --game-dir "$PWD/kit/games/stub" --compile-only` | Test-first and final builds: exit **0** each, compiler warnings **6 / 5**, errors **0** each. |
| `.venv/bin/ctest --test-dir kit/build/cmake/macos -R dx_tests --output-on-failure` | Test-first: **137,868 checks / 4 failures**, exit **8**, **0/1** suites passed. Failures were the four metrics returning 1024/768/1024/749 instead of 640/480/640/461. Final: **137,868 / 0**, exit **0**, **1/1** passed. |
| `.venv/bin/python kit/tools/format.py --write` | Ran twice, including after updating the metrics comment: exit **0**, **237** handwritten files each; changes confined to task files. |
| `.venv/bin/python tools/build.py --target smoke --jobs 8` | Exit **0**, **0** compiler warnings/errors; rebuilt user32 and linked the smoke host. No translator or `x86.h` change, so no regeneration. |

Build output was retained instead of discarded. The final runtime CTest
pipeline used `tee`, the prescribed geometry/check grep and `tail -8`;
their exits were **8 / 0 / 0 / 0**. The final DX and smoke-build pipelines
used `tee` and the prescribed tails, with all stages exiting **0**. Passing
DX details were copied from CTest's `LastTest.log` into ignored build output.

Ran the prescribed smoke command once:

```sh
RECOMP_SCRIPT=$PWD/smoke/main-menu.script RECOMP_HOST_DUMP_DIR=build/smoke \
RECOMP_DDRAW_MODES=640x480x16,800x600x16,1024x768x16 RECOMP_SMOKE_DRAWABLE=1024x768 \
RECOMP_MAX_SECONDS=30 build/recomp/pop_smoke > build/smoke-12.log 2>&1
grep -E "non-black|presented frames" build/smoke-12.log
.venv/bin/python kit/tools/recomp/ppm_to_png.py build/smoke/smoke_main-menu_present.ppm build/smoke/main-menu.png
```

Host, grep and conversion each exited **0**. The Metal smoke host reports
**15.0 seconds**, **1/1 script steps**, **640x480 16bpp**, **318 presented
frames**, **2** differing from their predecessor, **0 audio plays** and
**no undeliverable calls**. It stopped at guest `ExitProcess(0)`. The
presented non-black fraction is **0.997**; the separate scene figures
remain **0.000**. The full log still includes the mod-loader warning,
the offered-list warning about omitted 640x480x8, undrawn `TextOutA`, and
the no-non-client-area `AdjustWindowRectEx` notice. Its selected mode is
640x480x16; no unknown import, guest fault or Bink-open failure is reported.

**PNG: `build/smoke/main-menu.png`, 640x480, Cleopatra portrait at left,
gold title artwork and pyramids at right, and “Click to skip” along the
bottom.** Visual inspection establishes a title screen, not a menu-button
or gameplay interaction. Pillow counted **306,350 / 307,200 non-black
pixels (0.997233)**. Read-only timestamp assertions confirm the PPM follows
the rebuilt binary and the PNG follows the PPM. The task's title-or-menu
capture expectation passed, so its conditional black-frame peek rerun was
not needed. No additional script or input was sent.

Additional verification:

- `.venv/bin/python -m pytest -q tests`: exit **0**, **4 passed**.
- From `kit/`, `../.venv/bin/python -m pytest -q tests/test_game_literals.py`:
  exit **0**, **3 passed**; `../.venv/bin/python tools/check_game_literals.py`:
  exit **0**, no findings.
- From `kit/`, `../.venv/bin/python tools/check_repo.py` on the staged
  four-file change: exit **0**, source boundaries and local links passed.
- Both repositories' whitespace checks, exact baseline/new-check assertions,
  executable/IAT assertions and image/timestamp assertions exited **0**.
- `git check-ignore -q` passed for all **15** task logs and captures.

Only Task 2.9 was implemented. The script verifies a captured title screen;
main-menu interaction, gameplay, audio and other-platform execution remain
unverified. No push or landing-checkout change was performed. Logs, game
inputs, generated code, binaries and captures stay uncommitted under their
ignored directories.

#### 2026-09-13: Task 2.8 retained-pointer regression passes; smoke remains black

Started on game `main` at `d49d0fa2714c657c90c42374bdbd9fe2d99660ab`
and kit `pharaoh` at `1ced72b50a307cb6e24529efbf6512c6f3d20fb8`.
Kit was clean; the game's unrelated untracked `1/` directory was preserved.
The separate kit landing checkout remained unchanged at main `31f0f24`.

- `kit/dx/com.h` adds `retained_pointer` and `retained_hash`. Every accepted
  writable Lock sets the flag permanently. `kit/dx/ddraw.cpp` hashes every
  byte in the requested guest rectangle (excluding pitch padding), and
  refreshes it before `d3d_read_surface(..., HOST_READ_BLT_SOURCE)` in both
  `Surface_Blt` and `Surface_BltFast`.
- `record_cpu_write_rects` factors the existing `lock_shadow_record` payload,
  coverage, palette lease, frame record and `d3d_cpu_write` sequence so the
  refresh uses the same renderer write path. It then calls
  `ddraw_note_cpu_write_impl` and `surface_pixels_changed`. Normal Unlock
  refreshes the full-surface hash baseline; recorded primary writes update
  it before presentation so their records are not duplicated.
- The present entry point is **`ddraw_present` in `kit/dx/ddraw.cpp`**. It
  calls the helper on the primary's full rectangle before the existing
  flush and `host_present`. If the write notification recursively presents
  the changed primary, the outer call returns without presenting twice.
  `kit/dx/ddraw.h` declares the refresh helper; `ddraw_surface_revision`
  was already declared there. No `host_api.h` or host source edit was needed.
- `test_retained_pointer_writes`, next to `test_blt_and_colorkey`, uses the
  actual `S_Lock`, `S_Unlock`, `S_BltFast`, `S_Blt`, `com_this(...)->id`,
  `call_method`, `sc` and `gm_zero` helpers. It covers retained back-buffer
  writes, an unchanged repeat, a single changed final pixel through Blt,
  a surface only locked read-only, and direct primary presentation. Seven
  additional post-implementation checks inspect the frame-owned CPU record
  and its RGB565 payload/coverage before the blit record.

Verification, in task order:

```sh
.venv/bin/python kit/tools/test.py --game-dir "$PWD/kit/games/stub" --compile-only
.venv/bin/ctest --test-dir kit/build/cmake/macos -R dx_tests --output-on-failure
.venv/bin/python kit/tools/format.py --write
.venv/bin/python kit/tools/test.py --game-dir "$PWD/kit/games/stub" --compile-only
.venv/bin/ctest --test-dir kit/build/cmake/macos -R dx_tests --output-on-failure | tee build/task-2.8-green-dx.log | tail -3
.venv/bin/python tools/build.py --target smoke --jobs 8 2>&1 | tee build/task-2.8-smoke-build.log | tail -2
RECOMP_SCRIPT=$PWD/smoke/main-menu.script RECOMP_HOST_DUMP_DIR=build/smoke \
RECOMP_DDRAW_MODES=640x480x16,800x600x16,1024x768x16 RECOMP_SMOKE_DRAWABLE=1024x768 \
RECOMP_MAX_SECONDS=30 build/recomp/pop_smoke > build/smoke-8.log 2>&1
grep -E "non-black|presented frames" build/smoke-8.log
.venv/bin/python kit/tools/recomp/ppm_to_png.py build/smoke/smoke_main-menu_present.ppm build/smoke/main-menu.png
```

- Test-first stub compile: exit **0**, **1** existing unused-variable warning
  (`stalls`), **0** errors. Red CTest: exit **8**, **137,837 checks / 3
  failures**, **0/1** suites passed. The failures were exactly the back
  revision after BltFast, back revision after Blt, and primary revision
  after direct presentation. Pixel checks already passed in the shim test.
- Formatter ran twice, including after adding the payload assertions: both
  exit **0**, **237** handwritten files, with changes only in task files.
  Final stub compile: exit **0**, **11** compiler warning diagnostics,
  **0** errors. Green CTest: exit **0**, **137,844 checks / 0 failures**,
  **1/1** suites passed, including `retained pointer writes`. Its `tee` and
  `tail` each exited **0**. Build/CTest output is under ignored
  `build/task-2.8-{red,green}-*.log`; passing details are in
  `build/task-2.8-green-dx-detail.log`.
- Smoke build, `tee` and `tail`: each exit **0**, **10** compiler warning
  diagnostics, **0** errors. No translator or `x86.h` change, so no
  regeneration. Read-only executable assertions matched the pinned SHA-256,
  image base `0x00400000` and entry `0x00562fea`, exit **0**.
- Smoke host: exit **0**, **15.0 seconds**, **1/1** script steps,
  **640x480 16bpp**, **314 presented frames**, **1** differing from its
  predecessor. The log says **guest called `ExitProcess`**, guest exit 0,
  zero audio plays and no undeliverable calls. The run records 304 blit
  source reads and 12 lock reads. These counters do not establish a menu.
- The prescribed grep and PNG conversion each exited **0**. Non-black:
  **scene best 0.000, at a dump 0.000, presented 0.000**.
  **PNG: `build/smoke/main-menu.png`, 640x480, uniformly black; no title,
  menu text or buttons.** Visual inspection and Pillow agree: **0 of
  307,200 pixels non-black**. Artifact timestamps confirm the PPM was
  produced after the rebuilt smoke binary and the PNG after the PPM.
- Additional checks: `.venv/bin/python -m pytest -q tests` exited **0**,
  **4 passed**; from `kit/`, `../.venv/bin/python -m pytest -q
  tests/test_game_literals.py` exited **0**, **3 passed**;
  `.venv/bin/python kit/tools/check_game_literals.py` exited **0**, no
  findings. Both repositories' `git diff --check`, pinned-image and
  artifact assertions, and ignored-artifact checks exited **0**.

**Stopped at Step 4's unmet smoke expectation**, following the task's stop
rule. The native regression passes, but the cause of the remaining black
capture is unknown. No further diagnosis, alternate design, rerun, menu
interaction or Step 5 commit was performed. The scoped implementation and
documentation remain uncommitted; the game pin remains `1ced72b`. No
runtime-suite execution, other-platform build or push was performed.

#### 2026-09-13: Task 2.7 returns a finished Bink video record

Started on game main `c81b046` and kit branch `pharaoh` at `17b31a0`,
with both checkouts clean. Before implementation, read
`analysis/decompiled/Pharaoh.exe/functions/00413690.asm` and its `.c`:
the Bink record is loaded from the video object's `+0x10`. The loop reads
record width `+0x00` at `0x00413718` and height `+0x04` at `0x00413725`
to centre it. It reads current frame `+0x14` and frame count `+0x10`
at `0x00413736`/`0x00413739`, compares them unsigned at `0x0041373c`,
and branches to cleanup at `0x00413826` when current >= count. The
bottom-of-loop comparison reads the same counters at
`0x00413816`/`0x00413819`. **No other Bink record fields are read in
either listing.** The object's centring fields `+0x14`/`+0x18` are not
fields in the Bink record. All record bytes except width and height
remain zero, including `+0x08` and both counters; this skips decoding.

The test uses its existing `sc` scratch helper and the included
`guest.h`'s `gm_put_str` (there is no `put_str` helper in `dx_tests.cpp`).
`heap_owns` and `heap_free` are the actual names in `runtime/memory.h`.

- Updated `test_bink_smack_stubs` first, then built against the kit's stub
  game with `.venv/bin/python kit/tools/test.py --game-dir
  "$PWD/kit/games/stub" --compile-only`: exit **0**, **1** existing
  unused-variable compiler warning (`stalls`) and **0** compiler errors.
  `.venv/bin/ctest --test-dir kit/build/cmake/macos -R dx_tests
  --output-on-failure` exited **8**, **137,791 checks / 3 failures**,
  **0/1** suites passing. The first failure is exactly `bink != 0`;
  width and height also failed, reading 0 instead of 640 and 480.
- Implemented `BinkOpen` as a 16-byte-aligned, 256-byte guest heap block,
  zeroed except for 640x480 dimensions, and `BinkClose` using `heap_free`.
  The shim table points to those handlers; decoding, next-frame, service,
  copy and wait remain no-ops returning 0. `BinkGetError` remains
  `"no video decoder"`, and `SmackOpen` still returns 0.
- `.venv/bin/python kit/tools/format.py --write` exited **0**, formatting
  **237** handwritten files with changes confined to the task files.
  Repeated the stub compile command: exit **0**, **0** compiler warnings
  and **0** errors. Repeated CTest with `| tee build/task-2.7-green-dx.log
  | tail -3`: CTest, `tee` and `tail` all exited **0**, **1/1** suites
  passed, **137,791 checks / 0 failures**, including `Bink/Smacker stubs`.
  The detailed passing output is retained from CTest's `LastTest.log` as
  ignored `build/task-2.7-green-dx-detail.log`.
- `.venv/bin/python tools/build.py --target smoke --jobs 8 2>&1
  | tee build/task-2.7-smoke-build.log | tail -2` rebuilt the shim and
  linked the smoke host. Build, `tee` and `tail` exited **0**, with
  **0** compiler warnings/errors. No translator or `x86.h` changed and
  no regeneration was needed. Read-only SHA-256, image-base and
  entry-point assertions matched the pinned executable, exit **0**.
- Ran the prescribed smoke command once:

  ```sh
  RECOMP_SCRIPT=$PWD/smoke/main-menu.script RECOMP_HOST_DUMP_DIR=build/smoke \
  RECOMP_DDRAW_MODES=640x480x16,800x600x16,1024x768x16 RECOMP_SMOKE_DRAWABLE=1024x768 \
  RECOMP_MAX_SECONDS=30 build/recomp/pop_smoke > build/smoke-2.log 2>&1
  ```

  Host exit **0**, **15.0 seconds**, **1/1 script steps**, **640x480
  16bpp**, **315 presented frames** (one differing from the previous),
  **0 audio plays**, **no undeliverable calls**. The stop is still
  **guest called `ExitProcess`**, not the watchdog. The log contains
  **0** occurrences of `Unable to load BINK!`. After the initial surfaces
  and text warning it logs `AdjustWindowRectEx`, two more 640x480x16
  mode/surface setups, then `ExitProcess(0)` and guest exit 0. Bink's
  verbose open message is not enabled by this command; no extra tracing
  run was made, and the reason for the remaining exit is unverified.
- `.venv/bin/python kit/tools/recomp/ppm_to_png.py
  build/smoke/smoke_main-menu_present.ppm build/smoke/main-menu.png`
  exited **0**. **PNG: `build/smoke/main-menu.png`, 640x480, uniformly
  black, with no title, menu or buttons.** Visual inspection and Pillow
  agree: all **307,200 pixels** are RGB `(0, 0, 0)`. Read-only artifact
  assertions exited **0**, confirming both the PPM and PNG were written
  after this run started, not reused from Task 2.6.
- Read all 71 log lines. First distinct warnings/diagnostics, in order:
  mod-loader failure; DirectDraw's offered list omits `640x480x8`;
  `TextOutA` is accepted but undrawn; `AdjustWindowRectEx` models no
  non-client area; `ExitProcess(0)`; guest exit 0. The actual selected mode
  is 640x480x16, so the 8-bpp warning does not establish a mode refusal.
  No unimplemented/unknown-arity import or guest fault is reported.
- `.venv/bin/python -m pytest -q tests`: **4 passed**, exit **0**.
  From `kit/`, `../.venv/bin/python -m pytest -q
  tests/test_game_literals.py`: **3 passed**, exit **0**.
  `.venv/bin/python kit/tools/check_game_literals.py`: no findings, exit
  **0**. Both repositories' `git diff --check` exited **0**. Read-only
  assertions confirmed the last 30 lines below match the log exactly
  and all **10** task logs/artifacts are ignored, exit **0**.
- **Stopped at Step 4's unmet non-uniform capture expectation**, as
  instructed. No further fixes, rerun, campaign click or Step 5 commit;
  kit remains at `17b31a0` and game main at `c81b046`, with the scoped
  working changes retained. README, both changelogs and the smoke script
  comment describe the observed state. No native runtime suite,
  other-platform build or push was performed. Logs and captures remain
  under ignored `build/`; the script's `all expectations met` is not a
  menu assertion.

Last 30 lines of `build/smoke-2.log`:

```text
stopped:            guest called ExitProcess
elapsed:            15.0s
script:             1 of 1 steps
display mode:       640x480 16bpp
presented frames:   315 (1 of them different from the one before)
HD textures:        0 world draws, 0 loads, 0 hits, 0 refused, 0 / 536870912 bytes
terrain detail:     0 world tile draws
Direct3D:           0 draws, 0 textures, 0 write-backs
input:              0 changes announced, 0 reads by the guest
audio:              0 plays, loudest sample 0.000
non-black:          scene best 0.000 (at a dump 0.000), presented 0.000
gameplay: phases: composite=0.5 unique=1 repeats=1771 drops=0 continuous=0/s throughput=0/s scene_reused=0 waits=0 faults=0
access: lock_read=12 lock_write=0 getdc=0 blt_source=305 dstkey_read=0 duplicate=0 texture_load=0 flip=0 clean_reads=317
--- DirectX objects ---
live COM objects (0 of 9 created):
audio channels in use: 0 of 0 allocated
qmixer: waves opened 0 static, 0 streamed, 0 refused (record 0, format 0, data 0, streaming 0, no session 0)
qmixer: plays asked 0, delivered 0, dropped 0 (no session 0, no wave 0, no channel 0, disabled 0, paused 0, session inactive 0, no host voice 0, wave empty 0, stream dry 0)
qmixer: host plays 0, queues 0 accepted 0 refused (a refusal is the host saying no, not a host that was never asked)
qmixer: Pump called 0 times, frame pump 15671089 times, 0 refills, 0 looks that found nothing to do
qmixer: OpenChannel calls 0, EnableChannel 0 on / 0 off, ConfigureChannel 0; stops 0, pauses 0, waves freed 0
qmixer: volume never set; frequency 0, position 0, distance mapping 0, cone 0
-----------------------
guest exit code:    0
undeliverable calls: none

dumps:
    build/smoke/smoke_main-menu_present.ppm

all expectations met
```

#### 2026-09-13: Task 2.6 smoke boot exits after the Bink failure; no menu

Started on game main `554a148` and kit branch `pharaoh` at `17b31a0`,
with both checkouts clean. The kit already includes the Phase 2 Miles
arity table, Bink/Smacker failure stubs and 15 Win32 shims. No kit changes,
submodule re-pin, regeneration or fix-and-rerun rounds were made here.

- Rebuilt all three hosts first, in order, without `--regenerate`:

  ```sh
  .venv/bin/python tools/build.py --jobs 8 2>&1 | tee build/task-2.6-app-build.log | tail -3
  .venv/bin/python tools/build.py --target headless --jobs 8 2>&1 | tee build/task-2.6-headless-build.log | tail -3
  .venv/bin/python tools/build.py --target smoke --jobs 8 2>&1 | tee build/task-2.6-smoke-build.log | tail -3
  ```

  Each build, `tee` and `tail` exited **0**, captured from the shell's
  pipeline statuses. Full logs contain **6 / 0 / 10** compiler warning
  diagnostics respectively, and **0** compiler error diagnostics.
  Read-only SHA-256, image-base and entry-point assertions matched the
  pinned executable and exited **0**.
- Created `smoke/main-menu.script` with `wait 15000` and `dump main-menu`,
  then ran the prescribed command once:

  ```sh
  RECOMP_SCRIPT=$PWD/smoke/main-menu.script RECOMP_HOST_DUMP_DIR=build/smoke \
  RECOMP_DDRAW_MODES=640x480x16,800x600x16,1024x768x16 RECOMP_SMOKE_DRAWABLE=1024x768 \
  RECOMP_MAX_SECONDS=30 build/recomp/pop_smoke > build/smoke-1.log 2>&1
  ```

  The host exited **0**, reporting **15.0 seconds**, **1/1 script steps**,
  **640x480 16bpp**, **308 presented frames** (one differing from the
  previous frame), **0 audio plays** and **no undeliverable calls**.
  The stop was **guest called `ExitProcess`**, not the watchdog. The log
  records `Unable to load BINK!`, then `ExitProcess(0)` and guest exit 0.
  The host's `all expectations met` has no menu assertion behind it:
  this is a dump-only script, and its capture is black.
- The prescribed conversion command
  `.venv/bin/python kit/tools/recomp/ppm_to_png.py
  build/smoke/main-menu.ppm build/smoke/main-menu.png` exited **1** with
  `FileNotFoundError`: the smoke host actually wrote
  `build/smoke/smoke_main-menu_present.ppm`. Converted that existing dump
  with `.venv/bin/python kit/tools/recomp/ppm_to_png.py
  build/smoke/smoke_main-menu_present.ppm build/smoke/main-menu.png`,
  exit **0**. This was artifact inspection, not another host run.
  **The only PNG produced is `build/smoke/main-menu.png`: 640x480,
  uniformly black, with no title, menu or buttons.** Visual inspection
  and a Pillow count agree: all **307,200 pixels** are RGB `(0, 0, 0)`.
- Read the full `build/smoke-1.log` and its last 40 lines. First distinct
  warnings/diagnostics in log order:

  1. `boot: the mod loader reported a failure`.
  2. DirectDraw warns that the offered modes omit `640x480x8` and that a
     front end selecting that mode unchecked would fail. This run actually
     selected **640x480x16**; the warning does not prove a refused call.
  3. `gdi: TextOutA is accepted and not drawn in this runtime`.
  4. `OutputDebugString: Unable to load BINK!`.
  5. `ExitProcess(0)`.
  6. `guest process exited with code 0`.
  7. `stopped: guest called ExitProcess`.
- **Stopped at Step 1's expected menu result.** The observed stop is a
  normal guest exit following the unavailable-video diagnostic. The log
  identifies no unknown-arity or unimplemented import, wrong stdcall
  arity, or missing case/drive-letter file. It does not report a guest
  fault, abort or failed DirectDraw/COM call. Changing video behavior is
  outside the task's permitted fixes, so no further diagnosis or rerun
  was attempted. Step 2's menu coordinates, campaign click and second
  dump remain undone. `sierra.ini` optionality and the drive-letter music
  path remain unverified; no `RECOMP_LOG=1` follow-up was run.
- `.venv/bin/python -m pytest -q tests` exited **0**, **4 passed**.
  Read-only log/artifact assertions, both repositories' whitespace checks,
  and `git check-ignore` for all six new logs/captures exited **0**.
  No native suite was rerun because there is no native change; the
  previously recorded runtime baseline remains **32 failures**, not a
  fresh result. No headless/app execution, other-platform build or push
  was performed. README, changelog and script comments describe the
  observed failure to reach the menu; the kit pin remains `17b31a0`.

#### 2026-09-13: Task 2.5 implements the three gdi32 gaps

Kit commit `17b31a0` implements `GetDeviceCaps`, `GetTextExtentPointA` and
`SetBkColor` with their 2-, 4- and 2-argument stdcall arities. The caps shim
reads the existing `g_mode_w/h/bpp` state through the new
`ddraw_display_mode` accessor; without a linked DX module its weak runtime
definition returns false and leaves the 640x480x8 fallback intact. The
declaration in `runtime/win32.h` lets the runtime suite use the same hook
without linking DX. This follows the kit's existing weak hook pattern;
`GetSystemPaletteEntries` itself is only a no-host-palette stub, and user32
gets display geometry through host-fed window records.

The text extent uses the same named constants as `GetTextMetricsA`:
7 pixels per character and 16 pixels high. Background color lives in the
existing per-DC state, initially white. `TextOutA` still draws nothing;
there is no new font contract or `gdi32.h`.

- `.venv/bin/python tools/test.py --compile-only` exited **0** for the
  baseline, test-first and final builds. Their compiler warning counts were
  **0 / 16 / 5**, with **0** compiler errors. The final five warnings are
  existing volatile-increment warnings in the runtime suite.
- `.venv/bin/ctest --test-dir build/cmake/macos -R runtime_tests
  --output-on-failure` reported **501 checks / 32 failures** at baseline,
  **521 / 51** before implementation, then **511 / 32**. All three exited
  **8**, with **0/1** suites passing. All **10** new check messages now
  report `[ok]`, and all ten new stack-cleanup failures are gone. A read-only
  log comparison confirmed the same 32 baseline failures; the import
  coverage failure now counts **60** unknown arities instead of **63**.
- `.venv/bin/python kit/tools/test.py --game-dir
  /Users/sattam.thakur/Documents/Tests/pharaoh-recomp/kit/games/stub
  --compile-only` exited **0** before and after implementation, with
  **16 / 5** compiler warnings and **0** errors. DirectDraw runs used this
  stub tree, not the game's translation.
- `.venv/bin/ctest --test-dir kit/build/cmake/macos -R dx_tests
  --output-on-failure` first exited **8**, **137,710 checks / 67 failures**;
  finally it exited **0**, **137,774 checks / 0 failures**, **1/1** passing.
  The added mode checks cover the default, 800x600x8, 3840x2160x16 and a
  refused mode leaving the accepted mode and GDI caps unchanged. The
  post-run log assertion initially assumed the red run's check total;
  correcting that assumption to the observed final total passed, exit **0**.
- `.venv/bin/python kit/tools/format.py --write` exited **0**, formatting
  **237** files with changes confined to task files. From `kit/`,
  `../.venv/bin/python -m pytest -q tests/test_game_literals.py` passed
  **3** tests, exit **0**. `.venv/bin/python -m pytest -q tests` passed
  **4** tests, exit **0**. The kit's `tools/check_game_literals.py`,
  staged `tools/check_repo.py`, whitespace checks and ignored-log checks
  all exited **0**.
- Logs remain under ignored `build/task-2.5-*.log`. No game-host run,
  regeneration, other-platform build or push was performed. These checks
  establish shim behavior; menu and gameplay remain unverified.

#### 2026-09-13: Task 2.4 implements the ten user32 gaps

Kit commit `d39439a` registers `GetMenu`, `IsIconic`, `OpenIcon`,
`SetForegroundWindow`, `FindWindowA`, `SetActiveWindow`, `WaitMessage`,
`SystemParametersInfoA`, `GetMessagePos` and `GetMessageTime` with their
stdcall arities. Work-area queries reuse `GetClientRect`'s window record
and fallback dimensions; pointer packing reads `g_cursor_x/y`, as
`GetCursorPos` does; message time uses `host_millis()`, as `GetTickCount`
does. `WaitMessage` calls the existing `sched_checkpoint()`.

- Added all **11** checks immediately after `SetFocus`. The runtime suite
  does not link the input gate, so the position test calls
  `host_set_cursor_pos(200, 100)`, the user32 bridge used by
  `host_input_motion`, and documents the substitution in its comment.
- `.venv/bin/python tools/test.py --compile-only` exited **0** for the
  baseline and test-only builds. The first implementation build exited
  **1** with one undeclared-identifier error for `sched_checkpoint`.
  Adding its local declaration, matching `runtime/imports.cpp`, fixed
  this; the final build exited **0**, with **0** warning/error diagnostics.
  The test-only build had **5** existing volatile-increment warnings.
- `.venv/bin/ctest --test-dir build/cmake/macos -R runtime_tests
  --output-on-failure` ran before the checks, after the checks and after
  implementation: **490 checks / 32 failures**, **509 / 46**, then
  **501 / 32**. All three exited **8**, with **0/1** suites passing.
  Before implementation, `GetMenu` first failed stack cleanup, while
  `SetForegroundWindow` was the first new return-value failure. All 11
  new messages now report `[ok]`, and the eight new ESP failures are gone.
  A read-only Python log comparison exited **0**, confirming the same 32
  baseline failures remain; unknown import arities decreased **73 → 63**.
  The final `tee`, prescribed `grep` and `tail` stages each exited **0**.
- `.venv/bin/python kit/tools/format.py --write` ran twice, each exiting
  **0** and formatting **237** handwritten files; changes stayed within
  the two task files. From `kit/`, `../.venv/bin/python -m pytest -q
  tests/test_game_literals.py` exited **0**, **3 passed**.
  `.venv/bin/python -m pytest -q tests` exited **0**, **4 passed**.
  `.venv/bin/python kit/tools/check_game_literals.py`, the staged kit's
  `.venv/bin/python kit/tools/check_repo.py`, and staged kit whitespace
  checks exited **0**.
- Logs remain under ignored `build/task-2.4-*.log`. No game-host run,
  regeneration, translator or `x86.h` change, other-platform build or push
  was performed. These checks establish shim behavior, not gameplay.

#### 2026-09-13: Task 2.3 implements the two kernel32 gaps

Kit commit `99e8784` implements `GetDiskFreeSpaceA` with 8 sectors per
cluster, 512 bytes per sector, `0x00100000` free clusters and `0x00200000`
total clusters. `GetSystemDirectoryA` writes `C:\WINDOWS\SYSTEM` and returns
17, or returns the required size 18 when the buffer is too small. The shim
table records their 5- and 2-argument stdcall arities.

- Resumed with the four Step 1 checks already uncommitted. Ran
  `.venv/bin/python tools/test.py --compile-only` before and after
  implementation: both exited **0**, with **5** existing volatile-increment
  warnings in `runtime_tests.cpp` each and no compiler errors.
- `.venv/bin/ctest --test-dir build/cmake/macos -R runtime_tests
  --output-on-failure` ran against this game's tree before and after the
  change. Before: **493 checks, 39 failures**. After: **490 checks,
  32 failures**. Both CTest runs exited **8**, with **0/1** suites passing.
  All four task check messages now report `[ok]`; the three ESP failures
  are gone (those conditional failure checks also account for the lower
  check count). A read-only log comparison exited **0**, confirming the
  same 32 baseline failures remain; the import-coverage failure now reports
  **73** unknown arities instead of **75**. This is not a passing suite.
- `.venv/bin/python kit/tools/format.py --write` exited **0**, formatting
  **237** handwritten files with changes confined to the task's two files.
  From `kit/`, `../.venv/bin/python -m pytest -q tests/test_game_literals.py`
  exited **0**: **3 passed**. `.venv/bin/python -m pytest -q tests` exited
  **0**: **4 passed**. `.venv/bin/python kit/tools/check_game_literals.py`,
  `.venv/bin/python kit/tools/check_repo.py` on staged kit changes, and
  `git -C kit diff --cached --check` each exited **0**.
- CTest logs and the post-change build log remain under ignored
  `build/task-2.3-*.log`. No game-host run, regeneration or other-platform
  build was performed; this verifies shim behavior, not gameplay.

#### 2026-09-13: Task 2.3a gates profile_tests; runtime_tests baseline recorded

The kit defines `profile_tests` only when the translation's `funcs.h`
defines `FN_00500040`, allowing this game's native test binaries to build.
Resumed at Step 4 with the gate and kit changelog already edited; the
following verification results were supplied by the preceding run and
were not rerun during this documentation-and-commit step.

- `.venv/bin/python tools/test.py --compile-only`: the game tree compiles.
- `.venv/bin/ctest --test-dir build/cmake/macos -R runtime_tests
  --output-on-failure`: **493 checks, 39 failures**. Of these, **32** are
  the pre-existing Populous-bound baseline: **11** loader expectations,
  **10** `VCONFIG0` file checks, **1** `IsBadCodePtr` bounds check,
  **8** native frame-cap waits, **1** guest-root resolver and **1** import
  coverage check reporting **75 unknown arities**. The other **7** failures
  belong to the uncommitted Task 2.3 checks in
  `kit/runtime/tests/runtime_tests.cpp`; those edits remain untouched and
  excluded from this task's commits. This is not a passing runtime suite.

#### 2026-09-13: Task 2.2 adds Bink and Smacker failure stubs

Kit commit `df96987` registers the 12 Bink and 7 Smacker exports with
their decorated stdcall arities. Both open calls return 0;
`BinkGetError` returns a guest string containing "no video decoder";
`BinkSetSoundSystem` returns 1; the remaining calls return 0.
No decoder is present.

- Added the prescribed `test_bink_smack_stubs` before implementation.
  `.venv/bin/python kit/tools/test.py --game-dir
  /Users/sattam.thakur/Documents/Tests/pharaoh-recomp/kit/games/stub
  --compile-only` exited **0** before and after implementation. The
  builds emitted **1 / 6** compiler warnings, respectively, all in
  existing code, with **0** compiler errors and none from `bink.cpp`.
- `.venv/bin/ctest --test-dir kit/build/cmake/macos -R dx_tests
  --output-on-failure` first exited **8**: **137,650 checks, 7 failures**,
  starting at the first Bink call with `00000000 is not a shim trampoline`.
  After implementation it exited **0**: **1/1** suites passed,
  **137,656 checks, 0 failures**, including `Bink/Smacker stubs`.
  Build and CTest output is retained under ignored `build/task-2.2-*.log`.
- `.venv/bin/python kit/tools/format.py --write` exited **0**, formatting
  **237** handwritten files with no unrelated tracked changes. From
  `kit/`, `../.venv/bin/python -m pytest -q tests/test_game_literals.py`
  exited **0**: **3 passed**. The game-literal checker, staged kit source
  boundary checker and Git whitespace checks also exited **0**.
  `.venv/bin/python -m pytest -q tests` exited **0**: **4 passed** for
  the game configuration with the updated kit.
- No headless run, game host build, regeneration or other-platform build
  was performed. The translator and `x86.h` are unchanged. These native
  checks establish shim behavior; whether the game reaches these calls
  and continues past an unavailable cinematic remains unverified.

#### 2026-09-13: Task 2.1 registers all 41 Miles imports; headless still stalls

Resumed at Step 3 on game main `4e29b23` and kit branch `pharaoh` at
`ddfcb7a`, retaining the existing uncommitted `test_mss32_arities` and
`imports_argc` changes. Steps 1 and 2 and the confirmed red state were
supplied by the preceding run; they were not repeated here. Kit commit
`543daf9` adds the arity table and its registration/build wiring, and
includes those retained tests and the trampoline-arity accessor.

- Read-only `pefile` and SHA-256 assertions exited **0**: the executable
  matches the pinned hash, image base and entry point. Its **41** Miles
  import names and decorated arities exactly match all **41** shim entries
  and all **41** entries in the existing test. Startup returns 1; sample
  and stream handles return 0; all three status calls return 2. Provider
  enumeration returns 0 and opening a 3D provider returns 1, as specified
  by the task's table. These shims do not produce sound.
- `.venv/bin/python kit/tools/format.py --write` exited **0**, formatting
  **236** handwritten files; only the task's files changed.
- `.venv/bin/python kit/tools/test.py --game-dir
  /Users/sattam.thakur/Documents/Tests/pharaoh-recomp/kit/games/stub
  --compile-only` exited **0**. Native suites were built against the kit's
  stub game, without this game's translation. Full output is in ignored
  `build/task-2.1-native-build.log`: **6** compiler warning diagnostics,
  **0** compiler errors, and no warning from `mss32.cpp`.
- `.venv/bin/ctest --test-dir kit/build/cmake/macos -R dx_tests
  --output-on-failure` exited **0**: **1/1** CTest suites passed,
  **137,644 checks, 0 failures**, including `Miles arities`.
- From `kit/`, `../.venv/bin/python -m pytest -q
  tests/test_game_literals.py` exited **0**: **3 passed**.
  `.venv/bin/python kit/tools/check_game_literals.py`, the staged kit's
  `.venv/bin/python kit/tools/check_repo.py` and Git whitespace checks
  also exited **0**.
- `.venv/bin/python tools/build.py --target headless --jobs 8` exited
  **0**, rebuilding and linking `build/recomp/pop_headless` with **0**
  compiler warnings and **0** compiler errors. Full output is in ignored
  `build/task-2.1-headless-build.log`. No translation or `x86.h` changed;
  regeneration was not performed.
- Ran exactly `RECOMP_MAX_SECONDS=10 build/recomp/pop_headless >
  build/headless-3.log 2>&1`. The host exited **4** at **40.1 seconds**:
  the watchdog adds a 30-second grace to the requested cap. The image
  loaded and DirectDraw presented **7 uniform frames**, **1 written**,
  at **640x480 16bpp**. No menu or gameplay is established.
- **No `mss32` or `_AIL_` line appears in this run's log. Actual Miles
  call reachability is unconfirmed:** the requested command enables
  neither verbose import tracing nor import statistics, and the new
  shims return silently. The abnormal-exit import report is conditional
  on `recomp_env("IMPORT_STATS")` in `host/boot.cpp`; no
  `build/recomp/run-report.json` was produced. No extra instrumented run
  was performed.
- First distinct diagnostics, in log order: mod-loader failure;
  `USER32.dll!FindWindowA` unimplemented and unknown-arity warnings;
  the same pair for `GDI32.dll!GetDeviceCaps`,
  `GDI32.dll!GetTextExtentPointA` and `GDI32.dll!SetBkColor`;
  `gdi: TextOutA is accepted and not drawn in this runtime`;
  `watchdog: 40s elapsed with no response`; and the notice that the
  watchdog ended the run before mod teardown. Each unknown-arity warning
  says `not adjusting ESP, the guest stack will drift if it is really
  stdcall`. There are **12** distinct warning/diagnostic lines. Read-only
  log assertions exited **0**. These findings were not fixed or diagnosed
  further. Runtime-suite execution, smoke execution and other-platform
  builds were not performed.

#### 2026-09-13: Task 1.4 compiles; headless boot blocked by the loader

Initial build: game main `324cb37`, kit branch `pharaoh` at `969f027` (the existing
submodule pin). Both checkouts were clean before this task.

- Ran the prescribed build command from the game repository:

  ```sh
  .venv/bin/python tools/build.py --regenerate --jobs 8 2>&1 | tee build/build-1.log | tail -20
  ```

  Captured the shell's pipeline statuses immediately afterward: build,
  `tee` and `tail` each exited **0**. The full output remains in ignored
  `build/build-1.log`.
- Translation closed without a waiver: 6,136 of 6,139 functions, 10,517
  entry points; 839 constant-displacement jump-table sites, 820 decoded,
  34,111 entries, zero entries dispatching nowhere and zero sites decoding
  nothing. The translator still reported one recovery error; this run did
  not investigate or change it.
- All 32 generated C files compiled: `chunk_000.c` through `chunk_030.c`
  plus `table.c`. The generated archive linked, followed by `recomp_app`
  at `build/PharaohRecomp.app/Contents/MacOS/PharaohRecomp`. There were no
  compiler error diagnostics and 21 compiler warning diagnostics about
  C-linkage functions returning C++ user-defined types.
- **Blocker before Step 2:** `build/recomp/pop_headless` and
  `build/recomp/pop_smoke` do not exist. In `kit/tools/build.py`,
  `--target` defaults to `app`, which builds only `recomp_app`;
  `headless` and `smoke` are separate targets. The prescribed Step 1
  command therefore does not produce the executable Step 2 requires.
  Stopped without adding target builds or changing the kit, as instructed
  for a step that cannot be completed as written.
- Verified that `RECOMP_LOG=1` is real: `runtime/memory.cpp` reads
  `recomp_env("LOG")`, and `platform/env.cpp` supplies the `RECOMP_`
  prefix. The headless host reads `recomp_env("FRAMES")` for captures,
  defaulting to `build/recomp/frames`; the prescribed `HOST_DUMP_DIR`
  switch is read by `host/present_pixels.cpp` instead.
- No headless process was launched, so there is **no host exit code or
  exit reason, no first missing import reached, and no runtime warning
  lines to list**. Zero frame files exist in either `build/frames` or
  `build/recomp/frames` (neither directory exists); this is not a measured
  zero-frame boot. `build/headless-1.log` and
  `build/recomp/run-report.json` were not produced. Step 2 and its two
  log-filter commands were not run because the executable is absent.
- Read-only Python artifact/count checks exited 0. No native or portable
  test suites were run: the only tracked change is this run-log entry.

Resumed the same task on game main `c38d1da`, after `517de9a` recorded
the app build and the plan was corrected to build each host explicitly.
Kit remained on `pharaoh` at `969f027`; both checkouts were clean.

- Ran the remaining builds without regenerating the translation:

  ```sh
  .venv/bin/python tools/build.py --target headless --jobs 8 2>&1 | tail -3
  .venv/bin/python tools/build.py --target smoke --jobs 8 2>&1 | tail -3
  find build -name pop_headless -o -name pop_smoke
  ```

  Each build and its `tail` exited **0**, captured from the shell's
  pipeline statuses. Both hosts linked. The smoke build's final output
  included `5 warnings generated.`; the three-line tail does not establish
  a total compiler warning count. `find` exited **0** and returned exactly
  `build/recomp/pop_headless` and `build/recomp/pop_smoke`.
- Rechecked `recomp_env("LOG")` and retained `RECOMP_LOG=1`. A read-only
  Python check of the executable's SHA-256, image base and entry point
  matched the pinned identity above and exited **0**.
- Ran Step 2 using the located headless binary:

  ```sh
  RECOMP_MAX_SECONDS=10 RECOMP_HOST_DUMP_DIR=build/frames RECOMP_LOG=1 \
    build/recomp/pop_headless > build/headless-1.log 2>&1
  ```

  The host exited **2**, before guest execution or the ten-second cap.
  The complete log is one line (63 bytes):

  ```text
  headless: loader_load: image does not fit below the heap arena
  ```

  `kit/runtime/loader.cpp` rejects `image_base + size_image > HEAP_BASE`
  before mapping the image or binding imports. **No first missing import
  was reached**; this run never called `_AIL_startup@0` or set a display
  mode. This loader failure is the blocker; no runtime fix was attempted.
- Ran both prescribed log filters. `grep -c "frame_"
  build/headless-1.log` printed **0** and exited **1** (no match). The
  `grep -iE "trampoline|no shim|missing|fault|abort"` pipeline printed
  nothing; its statuses were **1, 0, 0, 0, 0** for `grep`, `sort`, `uniq`,
  `sort`, `head`. The loader error contains none of those search terms.
- **Frames written: 0.** Read-only Python artifact assertions exited **0**:
  both host binaries exist, the log contains exactly the loader error,
  there are zero `frame_*` files in either `build/frames` (absent) or
  `build/recomp/frames` (created, empty), and
  `build/recomp/run-report.json` is absent. No import-hit report was
  produced. **First 20 distinct runtime warning lines: none (0)**; the
  sole diagnostic is the loader error quoted above.
- `git check-ignore` exited **0** for the log, both binaries and the
  headless frame directory. No smoke execution, native or portable test
  suites, regeneration or kit changes were performed during the resume.

Task 1.5 continued on game main `2cfd174` and kit branch `pharaoh` at
`969f027`, with both checkouts initially clean. The kit now takes the heap
start from optional `[game] heap_base` through the generated header and
CMake fragment into `GUEST_HEAP_BASE`. Its default remains `0x01000000`;
this game's setting is `0x01400000`, above the image end `0x0126d000`.
The loader's rejection diagnostic names both limits and the setting to
raise. The mod heap and higher regions are unchanged.

- Added the two kit config tests first and ran
  `.venv/bin/python tools/test.py 2>&1 | tail -3`: **2 failed, 86 passed,
  3 skipped**, test runner exit **1**. The failures were exactly
  `KeyError: 'heap_base'` and missing `validate_heap_base`.
  After implementation, `.venv/bin/python tools/test.py 2>&1 | tail -2`
  reported **88 passed, 3 skipped**, exit **0**. Both runs also used
  `tee` to retain full output under ignored `build/task-1.5-kit-*.log`;
  `tee` and `tail` each exited **0**.
- `.venv/bin/python kit/tools/format.py --write` exited **0**, formatting
  235 handwritten source files with no unrelated tracked changes. The
  game's `.venv/bin/python -m pytest -q tests` reported **4 passed**,
  exit **0**, including the 20 MB setting and its rendered macro.
- Rebuilt all three hosts in order, without regeneration:

  ```sh
  .venv/bin/python tools/build.py --jobs 8 2>&1 | tail -2
  .venv/bin/python tools/build.py --target headless --jobs 8 2>&1 | tail -2
  .venv/bin/python tools/build.py --target smoke --jobs 8 2>&1 | tail -2
  ```

  Each build exited **0**; each added `tee` and each `tail` exited **0**.
  Full output is in ignored `build/task-1.5-app.log`,
  `build/task-1.5-headless-build.log` and `build/task-1.5-smoke-build.log`.
  The app build recompiled all 32 generated C files; the following builds
  reused that archive and rebuilt their host objects. Compiler warning
  diagnostics numbered **53 / 0 / 20**, respectively, with **0** compiler
  error diagnostics. All three host binaries exist. A read-only Python
  check found the `0x01400000u` heap definition in all **561** generated
  compile commands; both generated config files also contain that value.
- Ran the prescribed boot command:

  ```sh
  RECOMP_MAX_SECONDS=10 RECOMP_HOST_DUMP_DIR=build/frames \
    build/recomp/pop_headless > build/headless-2.log 2>&1
  ```

  **The loader accepted the image:** the log names entry `00562fea` and
  image `00400000..0126d000`. The host exited **4** after **40.0 seconds**:
  `the guest stopped calling into the runtime; stopped by the host watchdog`.
  The headless watchdog adds a 30-second grace to the 10-second cap.
  There was no normal guest exit or reported fault. The log also reports
  a mod-loader failure and that the watchdog stopped before mod teardown;
  neither was investigated in this task.
- **7 frames presented, 1 written**, all uniform, at **640x480 16bpp**,
  through DirectDraw with no Direct3D draws. The capture is
  `build/recomp/frames/frame_0000.ppm` (921,615 bytes), with one distinct
  colour and zero non-background pixels. No menu or gameplay is established.
  Headless uses `recomp_env("FRAMES")`, defaulting to `build/recomp/frames`;
  the prescribed `HOST_DUMP_DIR` is read by `host/present_pixels.cpp` and
  did not redirect this capture. `build/frames` remains absent. Both frame
  directories had zero captures before the run.
- First missing imports reached, in log order: **`USER32.dll!FindWindowA`**,
  `GDI32.dll!GetDeviceCaps`, `GDI32.dll!GetTextExtentPointA`,
  `GDI32.dll!SetBkColor`. Each returned zero and logged an unknown stdcall
  argument count, with possible stack drift. No Miles import is recorded
  as reached. This run does not establish the cause of the stall.
- `grep -c "frame_" build/headless-2.log` printed **1**, exit **0**.
  The prescribed `grep -iE "trampoline|no shim|missing|fault|abort|unknown"`
  pipeline returned four distinct unknown-arity warnings, each once;
  all five pipeline stages exited **0**. Read and retained the final
  15 log lines for the task report. `build/recomp/run-report.json` is absent.
- Read-only build/artifact assertions, `tools/check_game_literals.py`,
  both repositories' `git diff --check`, and `git check-ignore` for the
  logs, captures and binaries all exited **0**. The staged kit passed
  `.venv/bin/python kit/tools/check_repo.py` (source boundaries and local
  documentation links), exit **0**. Native test suites, smoke execution
  and other-platform builds were not run in Task 1.5.

#### 2026-09-13: identify the missing function at 0x004ab2af

The missing function at `0x004ab2af` is `0x004a98b0` (`ENTRY_4AB`),
referenced from the `.data` pointer at `0x005dc3e0` (bytes `b0 98 4a 00`).
The prescribed memory-image scan found this one absolute reference and no
direct `E8 rel32` calls to the entry in RVAs `[0x1000, 0x16e000)`. This is
evidence for entry through a data pointer; the indirect caller's dispatch
instruction was not traced.

- Rechecked the pinned executable's SHA-256, image base `0x00400000` and
  executable entry `0x00562fea`; all matched.
- Linear disassembly from `0x004a985b` exposes ten NOPs at
  `0x004a98a6`-`0x004a98af`, followed by the aligned entry's initial load
  (`a1 f8 56 d0 00`), `sub esp, 0x200` at `0x004a98b5`
  (`81 ec 00 02 00 00`), and saved EBX, ESI and EDI at `0x004a98c0`,
  `0x004a98c6` and `0x004a98cc` (`53`, `56`, `57`).
- A fresh disassembly starting at `0x004a98b0` covers 1,649 contiguous
  instructions / 6,705 bytes through `0x004ab2e1` exclusive, including
  `cmp edi, 0x20` at `0x004ab29e`, the switch at `0x004ab2af`,
  `add esp, 0x200` at `0x004ab2da` and `ret` at `0x004ab2e0`.
  Instruction-boundary, padding and pointer assertions all passed. This
  verification span is not the function's complete extent.
- Both prescribed Python checks and the identity, prologue and contiguous
  disassembly checks exited 0. Local prologue bytes and reference evidence
  are in ignored `analysis/notes/004ab2af.md`. No listings or configuration
  changed; no translation, native build or game run was performed.

#### 2026-09-13: repository created; the translator runs through with one gate waived

Kit main c2b4e93, the submodule pin. `tools/setup.py --link-only` accepts
the extraction, `tools/analyze.py` exports the listings and
`tools/build.py --regenerate` reaches the translator.

- Ghidra (default analyzers, about four minutes): 4,502 functions
  discovered, 4,500 decompiled; two failed with "Flow exceeded maximum
  allowable instructions" (`FUN_004f78a0`, `FUN_0052b6d0`), which only
  affects their pseudocode, not the listing.
- The translator stops at its jump-table gate: "9 table sites decoded
  nothing". All nine are one site, the `jmp dword ptr [eax*4+0x4ab93c]` at
  `0x004ab2af`: a Visual C++ 6 two-level switch (`cmp edi, 0x20; ja`, a byte
  index table at `0x004ab958`, a 7-entry pointer table at `0x004ab93c` whose
  entries `0x004ab2b6`, `0x004ab6ed`, `0x004ab710`, `0x004ab728`,
  `0x004ab74d`, `0x004ab756`, `0x004ab788` are all in range). Ghidra found
  no function between `FUN_004a9730` (ends `0x004a985b`) and `0x004ac000`,
  so the switch's own function is missing from the listing; the translator's
  PE recovery filled the hole with the case bodies as nine functions of its
  own (`fn_004ab2e1` … `fn_004ab6b7`), and none of them, taken as the
  containing function, decodes the table. The fix is either a function entry
  for the real routine in the listings or table decoding that does not
  depend on the containing function; both are kit or export work, not a
  config change.
- With the gate waived (`kit/tools/recomp/translate.py --allow-table-gaps
  <reason>` into a scratch directory, 13.5 s) the translator finishes:
  6,138 of 6,141 functions translated, 10,525 entry points (4,387 alternate,
  1,639 recovered from the PE, of which 1,235 by the data-pointer scan), 888
  constant-displacement jump-table sites of which 848 decoded with 35,010
  entries and none dispatching nowhere, 35 CRT static initialisers from four
  `__initterm` tables, 83 listing gaps, 3 guessed blocks withdrawn, one
  recovery error (`0x00511000`: "unknown operand width 16"), no failures
  and no unsupported mnemonics in the report. Output: 32 C chunks, 67 MB.
  `tools/build.py` does not pass the waiver through, so nothing was
  compiled or run; the next step is the switch above, then a compile.
- Portable checks from this repository: the kit's suites (84 passed, 3
  skipped), `tests/test_game_config.py` (4 passed), `tools/build.py --stub`
  (configures and builds `build/stub/PharaohRecomp.app`).
