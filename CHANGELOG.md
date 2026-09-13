# Changelog

## Unreleased

- Land the Phase 2-3 kit work on kit main `2fe5c5d` and retain that exact
  submodule pin. Record the full verification: 88 portable tests passed,
  3 skipped, 4 game config tests passed, all 11 native `nogame` entries
  passed, and runtime_tests retained its 32 known failures in 520 checks.
  Update macOS status: title screen, main menu and effects in smoke; MP3
  output in headless. Smoke streaming, gameplay and other platforms remain
  unverified.
- Re-pin the kit to `pharaoh` 2fe5c5d: Miles MP3 streams share DirectShow's
  decoder and refill through the frame pump, with volume, loop counts and
  playback completion. The macOS headless title run captures 24.092 seconds
  (23.8 seconds non-silent), peak 0.752, with no logged underrun. The default
  500-frame cap ends the run before 30 seconds. The smoke script passes,
  but its host has no streaming callbacks and does not validate music.
- Sound effects play: the kit's Miles Sound System shims (kit `pharaoh`
  f4ae821) load WAV files into guest memory, parse them and play sample
  handles through the host mixer with Miles volume and pan; the smoke run of
  `smoke/main-menu.script` reports one play at peak 0.78 (the menu click).
  Music streams are next.
- Complete Task 2.6's smoke script: capture the Cleopatra title screen,
  click its centre, then capture the five-button main menu after four
  seconds and again two seconds later. Both 640x480 menu images match;
  the macOS smoke run exits 0 after 21 seconds, silently. No menu button
  is selected. The existing kit pin `8c8da01` is unchanged.
- Task 2.9: re-pin the kit with creation, first-show and repositioning
  geometry messages, and screen metrics that follow the DirectDraw mode.
  The macOS smoke capture now shows the 640x480 Cleopatra title screen
  with “Click to skip”: 318 presented frames, presented non-black 0.997,
  exit 0. All nine new runtime checks pass with the same 32 baseline
  failures; DirectDraw passes 137,868 checks. Menu interaction and gameplay
  remain unverified. This pin also includes the committed Task 2.8 changes.
- Task 2.8 working changes detect DirectDraw writes through pointers retained
  after `Unlock`, sharing the written-lock CPU recording path before blits
  and primary presentation. The native regression passes (137,844 checks,
  zero failures), but the rebuilt macOS smoke host still captures uniform
  black: 314 presented frames and non-black 0.000. Stopped at Step 4's unmet
  menu expectation; no Task 2.8 commits or re-pin, so kit stays `1ced72b`.
- Task 2.7 working changes: Bink returns a finished 640x480 video record
  with zero frame counters and frees it on close. Native checks pass;
  the macOS smoke log no longer says `Unable to load BINK!`, but still
  exits with code 0 and captures uniform black. Stopped at that unmet
  expectation without further fixes or commits; kit pin stays `17b31a0`.
- Add the first dump-only smoke script and record its macOS boot result:
  640x480 at 16 bpp, a uniform black capture, and `ExitProcess(0)` after
  `Unable to load BINK!`. The main menu was not reached. The kit remains
  pinned at `17b31a0`; no additional shim fix or campaign click was made.
- Re-pin the kit with `GetDeviceCaps` reading the DirectDraw mode,
  `GetTextExtentPointA` sharing the fixed text metrics, and `SetBkColor`
  returning the previous per-DC color (initially white). All 10 new runtime
  checks pass with the same 32 known failures; DirectDraw checks pass.
- Re-pin the kit with ten user32 window-state and message shims, including
  client-area work bounds, recorded pointer position, tick-clock message time
  and a scheduler checkpoint for `WaitMessage`. All 11 new runtime checks
  pass; the suite retains its 32 known failures tied to the other game.
- Re-pin the kit with `GetDiskFreeSpaceA` reporting 4 GB free of 8 GB and
  `GetSystemDirectoryA` returning `C:\WINDOWS\SYSTEM` or the required buffer
  size. Both imports preserve the guest stack; all four new runtime checks
  pass, leaving the 32 known failures tied to the suite's other game.
- Re-pin the kit with 19 Bink and Smacker video stubs: opening a video
  returns 0, BinkGetError returns "no video decoder", and each export has
  its decorated stdcall arity. Native checks pass; cinematic skipping in
  the game remains unverified.
- Re-pin the kit with silent, stack-safe shims for all 41 Miles Sound System
  imports: startup succeeds, handles are refused and status calls report done.
  Native arity checks pass; the headless probe still stops at its watchdog
  after seven uniform frames, with Miles call reachability unconfirmed.
- Start the heap arena at 20 MB (`[game] heap_base = 0x01400000`) and
  re-pin the kit with per-game heap configuration. The loader now accepts
  the image ending at `0x0126d000`; headless presents seven uniform frames
  (one captured) before the watchdog stops it. The menu remains unverified.
- Re-pin the kit with `tools/build.py --regenerate --allow-table-gaps
  "<reason>"` support, forwarding the waiver and its reason to the translator.
  Builds without the flag keep the existing jump-table gap checks.
- The kit submodule moves to kit main `31f0f24` (the previous pin `c2b4e93`
  was rewritten away); kit work for this game happens on the submodule's
  `pharaoh` branch and lands on main.
- First run of the pipeline: Ghidra exports 4,502 functions, and the kit's
  translator converts 6,138 of 6,141 functions once its jump-table gate is
  waived for one switch at `0x004ab2af` whose function the listing lacks
  (`docs/analysis.md`, run log). Nothing compiled or run yet.
- New game repository for Pharaoh Gold (GOG offline installer 2.1.0.15) in
  the shape of majesty-recomp and populous-recomp: the kit as the submodule
  `kit/` (pinned at kit main c2b4e93), `game.toml` and `globals.toml`, thin
  `tools/*.py` wrappers, config tests and CI.
- The pinned executable is the installer's only one, `Pharaoh.exe`
  (2.1.0.0, SHA-256 `b21b7d71…a662`), a Visual C++ 6 DirectDraw build.
- `game.toml` carries the measured identity of the executable (image base
  `0x00400000`, entry point `0x00562fea`, guest root, required data
  directories, iOS bundle exclusions). The Populous-shaped hooks and globals
  the kit compiles against are sentinels in the executable's unused section
  padding until the bring-up identifies them; `tests/test_game_config.py`
  enforces that and that the exclusion list keeps the executable and the
  game's `.txt` model files.
- `tools/analyze.py`: listing export with Ghidra's own analyzers, because the
  kit's setup expects a curated annotation set this game does not have.
- `docs/analysis.md`: the executable's import surface (197 imports, 122 of
  them shimmed by the kit), its DirectDraw, Miles Sound System, Bink and
  Smacker paths, the kit work each needs, and the run log of the pipeline
  against it.
