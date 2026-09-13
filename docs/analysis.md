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
  draw-loop waits by `GetTickCount` return addresses, and whether this
  game's limiter goes through it is a question for the listings.
- **Input** is user32: `GetCursorPos`, `GetAsyncKeyState`, `GetMessagePos`
  and window messages. No DirectInput, so the kit's `mouse_*` hooks (a
  DirectInput device object) will never be real for this game; the touch
  mapper would attach to the message pump, as it does for Majesty.
- **Network**: none. The game has no multiplayer.

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
