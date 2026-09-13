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
