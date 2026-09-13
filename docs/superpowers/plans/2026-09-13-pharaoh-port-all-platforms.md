# Pharaoh Gold Port, All Platforms: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pharaoh Gold (GOG `Pharaoh.exe` 2.1.0.0) boots, plays a mission with sound and saves, and ships as a per-platform app on macOS, iPad, Linux, Windows and Android through recomp-kit.

**Architecture:** The game repository `pharaoh-recomp` holds only config, tests, docs and smoke scripts; every runtime, translator, host and packaging change goes into the kit on a `pharaoh` branch of the `kit/` submodule and is landed on kit `main` afterwards. Work proceeds in the order the kit's design proves things: translation closes on macOS, then the headless and smoke hosts boot the game, then the shims the import table demands (15 win32 gaps, Miles Sound System, Bink/Smacker stubs), then the macOS app plays, then iPad, then Linux and Windows through the existing presets, then Android as new kit packaging.

**Tech Stack:** Python 3.9 tooling, Ghidra 12.1.3 listings, the kit's translator (`kit/tools/recomp/translate.py`), C/C++17 runtime and shims under clang, SDL3 (FetchContent, static), Metal on Apple, Vulkan elsewhere, minimp3 for MP3, CMake presets `macos`, `ios`, `linux`, `windows`, plus a new `android` preset with Gradle and the NDK.

**Spec:** `docs/analysis.md` in this repository (the measured import surface and the first run log) and the kit's design `kit/docs/superpowers/specs/2026-09-13-recomp-kit-design.md` (sections 4.4 to 4.6, 6, 9).

## Global Constraints

- Game repository: `~/Documents/Tests/pharaoh-recomp`. Kit checkout used for landing: `~/Documents/Tests/recomp-kit` (main is `31f0f24`; the submodule's current pin `c2b4e93` is no longer on main).
- Kit code under `runtime/`, `dx/`, `host/`, `platform/` may not name a game; `kit/tests/test_game_literals.py` enforces it. Write "the game" or "a Miles game", never "Pharaoh".
- Every environment switch is `RECOMP_<NAME>` read through `recomp_env("<NAME>")`; no other prefix and no aliases.
- Addresses live in `game.toml` `[hooks]`/`[translate]` and `globals.toml`, never in kit code. A sentinel is replaced only by an address verified in the listings; `tests/test_game_config.py` keeps sentinels in `0x0126ce00`-`0x0126cfff`.
- Native code builds only through `tools/build.py` and `tools/test.py`. Kit sources are formatted with `.venv/bin/python kit/tools/format.py --write`.
- Nothing generated, no game file, no run log and no save is committed. `original/`, `analysis/`, `build/` are ignored.
- Executable identity is fixed: `Pharaoh.exe`, SHA-256 `b21b7d719491bb45dfb324ba95231a5b0960ab25fea1bf3fb21da65da7eca662`, image base `0x00400000`, entry `0x00562fea`.
- Kit-side tests: `runtime/tests/runtime_tests.cpp` uses `check(cond, "message %u", ...)` and `call_import(c, "DLL.dll", "Name", {args})`; `dx/tests/dx_tests.cpp` uses `CHECK`, `CHECK_EQ`, `tramp("DLL.dll", "Name")`, `call_shim(t, {args})` and a `tests[]` table in `main`. Run them with `.venv/bin/python tools/test.py --native` from the game repository or `ctest --test-dir build/cmake/macos -R <name>`.
- Commit messages: imperative subject, a body that says what changed and why. Kit commits go on branch `pharaoh` in `kit/`; game commits go on `main` of the game repository and re-pin the submodule.
- Minimum platforms (kit decision): iOS 17, Android 10 with Vulkan 1.1, macOS 14, current Linux and Windows releases SDL3 supports.

---

## Phase 0: the repository is ready to carry kit work

### Task 0.1: Re-pin the kit submodule to main and open the `pharaoh` branch

**Files:**
- Modify: `.gitmodules` (no change expected; verify URL)
- Modify: submodule pointer `kit`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Produces: `kit/` on branch `pharaoh` based on kit main `31f0f24`, with remote `local` pointing at the sibling kit checkout.

- [ ] **Step 1: Add the sibling kit checkout as a remote of the submodule and fetch it**

```bash
cd ~/Documents/Tests/pharaoh-recomp
git -C kit remote add local ~/Documents/Tests/recomp-kit || true
git -C kit -c protocol.file.allow=always fetch local main
git -C kit log --oneline -1 local/main
```

Expected: `31f0f24 Touch on a tablet: taps that land, edges a finger or a mouse can reach`

- [ ] **Step 2: Create the `pharaoh` branch on the fetched main**

```bash
git -C kit checkout -q -b pharaoh local/main
git -C kit log --oneline -1
```

Expected: `31f0f24 ...`

- [ ] **Step 3: Run the portable checks against the new pin**

```bash
.venv/bin/python -m pytest -q tests
.venv/bin/python tools/test.py
```

Expected: `4 passed` and `84 passed, 3 skipped` (counts may grow with the kit; no failures).

- [ ] **Step 4: Record the pin in the changelog**

Add under `## Unreleased` in `CHANGELOG.md`:

```markdown
- The kit submodule moves to kit main `31f0f24` (the previous pin `c2b4e93`
  was rewritten away); kit work for this game happens on the submodule's
  `pharaoh` branch and lands on main.
```

- [ ] **Step 5: Commit**

```bash
git add kit CHANGELOG.md
git commit -m "Re-pin the kit to main 31f0f24

c2b4e93 is no longer on kit main. The submodule now tracks the pharaoh
branch, based on main, for the kit changes this port needs."
```

### Task 0.2: `tools/build.py` passes `--allow-table-gaps` through to the translator

**Files:**
- Modify: `kit/tools/build.py:179-182` (`run_translator`), `kit/tools/build.py:198-215` (`parse_args`)
- Test: `kit/tools/tests/test_build.py` (add a case beside the existing `parse_args` tests; create the file if the directory has no build test)

**Interfaces:**
- Produces: `tools/build.py --regenerate --allow-table-gaps "<reason>"` runs `translate.py --allow-table-gaps "<reason>"`; without the flag behaviour is unchanged.

- [ ] **Step 1: Write the failing test**

Find the existing tests for `build.py`:

```bash
grep -rln "parse_args" kit/tools/tests kit/tools/recomp/tests | head
```

Add to that file (or to a new `kit/tools/tests/test_build.py` importing `build` the way its neighbours import kit tools):

```python
def test_allow_table_gaps_reaches_the_translator(tmp_path):
    calls = []
    build.subprocess.run = lambda cmd, **kw: calls.append(cmd)
    build.run_translator(tmp_path / "stage", tmp_path, tmp_path / "build", allow_table_gaps="switch 004ab2af")
    assert "--allow-table-gaps" in calls[0]
    assert calls[0][calls[0].index("--allow-table-gaps") + 1] == "switch 004ab2af"


def test_no_table_gap_flag_by_default(tmp_path):
    calls = []
    build.subprocess.run = lambda cmd, **kw: calls.append(cmd)
    build.run_translator(tmp_path / "stage", tmp_path, tmp_path / "build")
    assert "--allow-table-gaps" not in calls[0]
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd kit && ../.venv/bin/python -m pytest -q tools/tests/test_build.py -k table_gaps
```

Expected: FAIL with `TypeError: run_translator() got an unexpected keyword argument 'allow_table_gaps'`

- [ ] **Step 3: Implement**

In `kit/tools/build.py` replace `run_translator`:

```python
def run_translator(stage, game_dir, build_root, allow_table_gaps=None):
    command = [sys.executable, str(ROOT / "tools/recomp/translate.py"), "--out", str(stage),
               "--game", str(game_dir),
               "--report", str(Path(build_root) / "recomp/translate-report.json")]
    if allow_table_gaps:
        command += ["--allow-table-gaps", allow_table_gaps]
    subprocess.run(command, cwd=ROOT, check=True)
```

In `parse_args` add after the `--regenerate` argument:

```python
    parser.add_argument("--allow-table-gaps", metavar="REASON", default=None,
                        help="Accept jump-table sites the translator cannot decode (passed to translate.py)")
```

In `main` change the `publish_generated` call to:

```python
                publish_generated(args.build_root,
                                  lambda stage: run_translator(stage, args.game_dir, args.build_root,
                                                               args.allow_table_gaps))
```

- [ ] **Step 4: Run the tests**

```bash
cd kit && ../.venv/bin/python -m pytest -q tools/tests/test_build.py
```

Expected: PASS

- [ ] **Step 5: Commit in the kit**

```bash
cd kit && git add tools/build.py tools/tests/test_build.py && git commit -m "build.py: pass --allow-table-gaps through to the translator

A game whose listing lacks one switch's function can be compiled and run
while the listing gap is worked on, with the reason recorded in the report."
```

---

## Phase 1: the translation closes and the game boots headless on macOS

### Task 1.1: Find the function Ghidra missed around `0x004ab2af`

**Files:**
- Create: `analysis/notes/004ab2af.md` (ignored directory; working notes only)
- Modify: `docs/analysis.md` (run log)

**Interfaces:**
- Produces: the entry address `ENTRY_4AB` of the routine containing the switch at `0x004ab2af`, verified by a disassembly that starts at a prologue and reaches `0x004ab29e`.

- [ ] **Step 1: Disassemble the hole linearly from the end of `FUN_004a9730`**

```bash
.venv/bin/python - <<'EOF'
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
pe = pefile.PE("original/gog/app/Pharaoh.exe")
rd = lambda va, n: pe.get_data(va - 0x400000, n)
md = Cs(CS_ARCH_X86, CS_MODE_32)
start = 0x4a985b            # end of FUN_004a9730 (299 bytes from 0x4a9730)
code = rd(start, 0x4ab2b6 - start)
last_ret = None
for ins in md.disasm(code, start):
    if ins.mnemonic in ("ret", "int3") and last_ret is None or ins.mnemonic == "ret":
        last_ret = ins.address
    if ins.address >= 0x4ab280 or ins.mnemonic in ("ret", "int3") or "esp, 0x200" in ins.op_str:
        print("%08x %s %s" % (ins.address, ins.mnemonic, ins.op_str))
EOF
```

Expected: a run of `int3` or `nop` padding, then a prologue (`push ebx`/`push esi`/`push edi` and `sub esp, 0x200`, matching the `add esp, 0x200; ret` at `0x004ab2da`) at an aligned address before `0x004ab29e`. Record that address as `ENTRY_4AB`.

- [ ] **Step 2: Confirm the candidate is reached from the switch and from a caller**

```bash
.venv/bin/python - <<'EOF'
import pefile, struct
pe = pefile.PE("original/gog/app/Pharaoh.exe")
data = pe.get_memory_mapped_image()
ENTRY = int(open("analysis/notes/entry.txt").read(), 16) if False else 0  # set the value found in step 1
target = struct.pack("<I", ENTRY)
hits = [0x400000 + i for i in range(len(data) - 4) if data[i:i+4] == target]
print("absolute references:", ["%08x" % h for h in hits])
# relative calls: E8 rel32
for i in range(0x1000, 0x16e000):
    if data[i] == 0xE8:
        rel = struct.unpack("<i", data[i+1:i+5])[0]
        if 0x400000 + i + 5 + rel == ENTRY:
            print("call from %08x" % (0x400000 + i))
EOF
```

Expected: at least one `call from` or one absolute reference (a vtable or a data pointer). Ghidra missed the routine because it is reached only through that pointer.

- [ ] **Step 3: Write the note and the run log entry**

`analysis/notes/004ab2af.md`: the entry, its callers, the prologue bytes. In `docs/analysis.md` under the run log add a dated entry "the missing function at 0x004ab2af is `ENTRY_4AB`, reached from ...".

- [ ] **Step 4: Commit the doc**

```bash
git add docs/analysis.md && git commit -m "analysis: the function behind the 004ab2af switch"
```

### Task 1.2: Translator reads `[translate] entry_points` from `game.toml` as function seeds

**Files:**
- Modify: `kit/tools/recomp/translate.py:45-60` (`configure`), the discovery seeding beside the `__initterm` seeds (find with `grep -n "initterm" kit/tools/recomp/translate.py`)
- Modify: `kit/games/stub/game.toml` (`[translate] entry_points = []`)
- Test: `kit/tools/recomp/tests/test_translate_config.py` (create if absent)
- Modify: `game.toml`, `tests/test_game_config.py`

**Interfaces:**
- Consumes: `ENTRY_4AB` from Task 1.1.
- Produces: `cfg["translate"]["entry_points"]` (list of ints) accepted by `configure`, exposed as module constant `EXTRA_ENTRY_POINTS` (frozenset of int), and every address in it becomes a discovered function entry named `FUN_<addr>` with provenance `"config"` in the report.

- [ ] **Step 1: Write the failing tests**

`kit/tools/recomp/tests/test_translate_config.py` already exists and loads
`game_config` and `translate` at module level; `configure()` needs a fully
loaded config (`listings_path`, `developer_exe_path`), so build it from the
stub game. Add to the existing test class:

```python
    def test_entry_points_default_empty(self):
        cfg = game_config.load(ROOT / "games/stub")
        translate.configure(cfg)
        self.assertEqual(translate.EXTRA_ENTRY_POINTS, frozenset())

    def test_entry_points_read(self):
        cfg = game_config.load(ROOT / "games/stub")
        cfg["translate"]["entry_points"] = [0x4ab000, 0x4ac000]
        translate.configure(cfg)
        self.assertEqual(translate.EXTRA_ENTRY_POINTS, frozenset({0x4ab000, 0x4ac000}))
```

- [ ] **Step 2: Run to verify failure**

```bash
cd kit && ../.venv/bin/python -m pytest -q tools/recomp/tests/test_translate_config.py
```

Expected: FAIL, `AttributeError: module 'translate' has no attribute 'EXTRA_ENTRY_POINTS'`

- [ ] **Step 3: Implement the config read**

In `translate.py` `configure(cfg)` after `VISUAL_ANIMATION_READS = ...` add:

```python
    global EXTRA_ENTRY_POINTS
    EXTRA_ENTRY_POINTS = frozenset(int(a) for a in cfg["translate"].get("entry_points", ()))
```

and declare `EXTRA_ENTRY_POINTS = frozenset()` with the other module-level configured constants.

- [ ] **Step 4: Seed discovery**

Locate where the `__initterm` entries are queued:

```bash
grep -n "initterm_entries\|initterm_tables\|provenance\[" kit/tools/recomp/translate.py | head
```

Immediately after the initterm seeds are added (the same call the initterm loop makes to register an entry, with its provenance string), add:

```python
        for addr in sorted(EXTRA_ENTRY_POINTS):
            if not self.image.contains_code(addr):
                raise TranslateError("[translate] entry_points: %08x is not in a code section" % addr)
            self.add_entry(addr, provenance="config")   # the same registration the initterm seeds use
```

Use the actual registration method name found in the grep (the plan names it `add_entry`; the initterm loop shows the real one). Add `"config"` to the `provenance` counter in the report where `"initterm"` is counted.

- [ ] **Step 5: Run the kit tests**

```bash
.venv/bin/python tools/test.py      # from the game repository: it sets RECOMP_GAME_DIR/RECOMP_BUILD_ROOT for the kit's suites
```

Expected: PASS, two more tests than before (86 passed, 3 skipped).

- [ ] **Step 6: Point the game config at the found entry and extend the config test**

`game.toml` `[translate]`:

```toml
# Function entries the Ghidra listing lacks. 0x004ab... (ENTRY_4AB) is the
# routine holding the two-level switch at 0x004ab2af, reached only through a
# pointer; see docs/analysis.md.
entry_points = [ENTRY_4AB]
```

`tests/test_game_config.py`, in `test_identity`:

```python
        self.assertEqual(self.cfg["translate"]["entry_points"], [ENTRY_4AB])
        for address in self.cfg["translate"]["entry_points"]:
            self.assertTrue(0x00401000 <= address < 0x0056e24d, hex(address))  # inside .text
```

- [ ] **Step 7: Regenerate without the waiver**

```bash
.venv/bin/python tools/build.py --regenerate --target gen --jobs 8 2>&1 | tail -5
```

Expected: no `TranslateError`; the summary line reports `0 sites decoded nothing` and `build/recomp/translate-report.json` has `"table_sites_undecoded": []` and `"provenance": {... "config": 1 ...}`.

- [ ] **Step 8: Commit kit and game**

```bash
cd kit && git add tools/recomp/translate.py tools/recomp/tests/test_translate_config.py games/stub/game.toml && git commit -m "translate.py: [translate] entry_points seeds functions the listing lacks

A routine reached only through a pointer can be absent from a Ghidra
listing; naming its entry in game.toml puts it back without hand-editing
the export. Provenance \"config\" in the report."
cd .. && git add kit game.toml tests/test_game_config.py && git commit -m "The 004ab2af switch's function is a configured entry point; the translation closes"
```

### Task 1.3: Exclude jump-table slots from the data-pointer function scan

> **Not needed (2026-09-13).** `Image.code_pointers` already takes
> `exclude=tr.table_ranges` and skips both pointers stored in decoded table
> storage and candidates pointing at it. The nine case bodies were accepted
> only because their table's function was missing; with Task 1.2's seed they
> are `kind: block, provenance: table` in `symbols.json`. Skipped; the steps
> below are kept for the record.


**Files:**
- Modify: `kit/tools/recomp/translate.py` (the data-pointer scan; find with `grep -n "data-pointer\|discovered_by_scan" kit/tools/recomp/translate.py`)
- Test: `kit/tools/recomp/tests/test_translate_tables.py` (extend or create next to existing table tests)

**Interfaces:**
- Produces: an address that lies inside a decoded `table_ranges` entry is never accepted as a function entry by the data-pointer scan.

- [ ] **Step 1: Write the failing test**

Find how existing tests build a small image for the translator (`grep -rn "def make_image\|class FakeImage" kit/tools/recomp/tests | head`) and add:

```python
    def test_table_slot_is_not_a_function_entry(self):
        t = self.make_translator_with_table(dword_base=0x4ab93c, entries=[0x4ab2b6, 0x4ab74d])
        t.scan_data_pointers()
        self.assertNotIn(0x4ab2b6, t.entries_from_data)
```

using the helper names found in the neighbouring test file.

- [ ] **Step 2: Run to verify failure**

```bash
cd kit && ../.venv/bin/python -m pytest -q tools/recomp/tests -k table_slot
```

Expected: FAIL (the slot is accepted).

- [ ] **Step 3: Implement**

In the data-pointer scan, before accepting a candidate `t` read from `.rdata`/`.data`, add:

```python
            if any(lo <= at < hi for lo, hi in self.table_ranges):
                self.stats["_data_scan_table_slot_skipped"] += 1
                continue
```

where `at` is the address of the pointer slot being read (not its target).

- [ ] **Step 4: Run the tests and the game translation**

```bash
cd kit && ../.venv/bin/python -m pytest -q tools/recomp/tests
cd .. && .venv/bin/python tools/build.py --regenerate --target gen --jobs 8 2>&1 | tail -3
```

Expected: PASS; the report's `functions_total` drops by the nine former `fn_004ab2e1`... case bodies (they are blocks of the configured function now).

- [ ] **Step 5: Commit**

```bash
cd kit && git add tools/recomp && git commit -m "translate.py: a jump-table slot is not a data pointer to a function"
```

### Task 1.4: Compile the translation and boot the headless host

**Files:**
- Modify: `docs/analysis.md` (run log)

**Interfaces:**
- Produces: `build/recomp/pop_headless` runs the game to its first frames or to a recorded fault; `build/recomp/run-report.json` lists the imports hit.

- [ ] **Step 1: Build**

```bash
.venv/bin/python tools/build.py --regenerate --jobs 8 2>&1 | tee build/build-1.log | tail -20
.venv/bin/python tools/build.py --target headless --jobs 8 2>&1 | tail -3
.venv/bin/python tools/build.py --target smoke --jobs 8 2>&1 | tail -3
```

Expected: the 32 chunks compile; `recomp_app` links, then `pop_headless` and `pop_smoke` (each `--target` builds one host; find the binaries with `find build -name pop_headless -o -name pop_smoke`). A compile error in a chunk is a translator bug: record the chunk and instruction in the run log and fix it in `translate.py` with a unit test in `kit/tools/recomp/tests` before continuing.

- [ ] **Step 2: Run headless for ten seconds**

```bash
RECOMP_MAX_SECONDS=10 RECOMP_HOST_DUMP_DIR=build/frames RECOMP_LOG=1 \
  build/recomp/pop_headless > build/headless-1.log 2>&1; echo "exit $?"
grep -c "frame_" build/headless-1.log; grep -iE "trampoline|no shim|missing|fault|abort" build/headless-1.log | sort | uniq -c | sort -rn | head -30
```

Expected outcomes, in order of likelihood: (a) the game exits early because `_AIL_startup@0` returns 0 through a logging trampoline and the stack drifts (Phase 2 fixes this); (b) the game reaches DirectDraw `SetDisplayMode` and presents frames. Either way the report names the imports it hit.

- [ ] **Step 3: Record the run**

Append to the run log in `docs/analysis.md`: the exit reason, the first missing import reached, the frame count. Commit:

```bash
git add docs/analysis.md && git commit -m "analysis: first headless boot"
```

---

## Phase 2: the import gaps close; the game reaches its main menu in the smoke host

### Task 2.1: Miles Sound System arity table (silent, stack-safe)

**Files:**
- Create: `kit/dx/mss32.cpp`
- Modify: `kit/dx/dx.h` (declare `void mss32_register();` with the other per-module registrations), `kit/dx/dx.cpp:563-580` (`dx_register_shims` calls it), `kit/dx/CMakeLists.txt:1-3` (add `mss32.cpp` to `POP_DX_SOURCES`)
- Test: `kit/dx/tests/dx_tests.cpp` (new `test_mss32_arities`, added to `tests[]`)

**Interfaces:**
- Produces: every `mss32.dll` import the game names resolves to a shim with the right stdcall arity. Until Task 3.x gives them behaviour, `AIL_startup` returns 1, handle allocators return 0, status calls return `SMP_DONE` (2), everything else returns 0.

- [ ] **Step 1: Write the failing test**

In `dx_tests.cpp`:

```cpp
// Miles Sound System: every import has the arity its decorated name states,
// so a call through it leaves ESP where the caller expects.
static void test_mss32_arities() {
    cpu_reset();
    struct { const char *name; uint32_t argc; } expected[] = {
        {"_AIL_startup@0", 0}, {"_AIL_shutdown@0", 0}, {"_AIL_set_preference@8", 2},
        {"_AIL_waveOutOpen@16", 4}, {"_AIL_allocate_sample_handle@4", 1},
        {"_AIL_set_sample_reverb@16", 4}, {"_AIL_set_3D_orientation@28", 7},
        {"_AIL_open_stream@12", 3}, {"_AIL_enumerate_3D_providers@12", 3},
    };
    for (auto &e : expected) {
        uint32_t t = tramp("mss32.dll", e.name);
        CHECK(t != 0);
        CHECK_EQ(imports_argc(t), e.argc);
    }
    CHECK_EQ(call_shim(tramp("mss32.dll", "_AIL_startup@0"), {}), 1u);
    CHECK_EQ(call_shim(tramp("mss32.dll", "_AIL_enumerate_3D_providers@12"), {0, 0, 0}), 0u);
}
```

If `imports_argc` does not exist, add `uint8_t imports_argc(uint32_t trampoline);` to `kit/runtime/imports.h` returning `tramps()[idx].argc` (0 for an unallocated trampoline).

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/python tools/build.py --target fixture --jobs 8 >/dev/null 2>&1; ctest --test-dir build/cmake/macos -R dx_tests --output-on-failure | tail -5
```

Expected: FAIL at `tramp("mss32.dll", "_AIL_startup@0") != 0`.

- [ ] **Step 3: Implement the table**

`kit/dx/mss32.cpp`:

```cpp
// mss32.cpp - Miles Sound System 6 (mss32.dll) as a game imports it: 41
// stdcall exports whose decorated names carry their arity (_AIL_name@bytes).
// This file starts as an arity table so a call through any of them leaves
// the guest stack intact; samples and streams gain behaviour in the sound
// tasks, and the 3D provider API always reports "no providers", which puts a
// game on its plain 2D path.
#include "com.h"
#include "dx.h"
#include "host_api.h"
#include "../runtime/imports.h"
#include "../runtime/memory.h"
#include "../runtime/win32.h"
#include "../platform/os.h"

#include <string.h>
#include <vector>

namespace {

const uint32_t SMP_FREE = 1, SMP_DONE = 2, SMP_PLAYING = 4, SMP_STOPPED = 8;

void ret0(X86 *c) { set_eax(c, 0); }
void ret1(X86 *c) { set_eax(c, 1); }
void ret_done(X86 *c) { set_eax(c, SMP_DONE); }

#define AIL(name, bytes, fn) {"mss32.dll", "_AIL_" #name "@" #bytes, (bytes) / 4, fn}

const ImportShim g_mss32_shims[] = {
    AIL(startup, 0, ret1), AIL(shutdown, 0, ret0), AIL(set_preference, 8, ret0),
    AIL(waveOutOpen, 16, ret0), AIL(mem_free_lock, 4, ret0), AIL(file_read, 8, ret0),
    AIL(allocate_sample_handle, 4, ret0), AIL(release_sample_handle, 4, ret0),
    AIL(init_sample, 4, ret0), AIL(set_sample_file, 12, ret0), AIL(start_sample, 4, ret0),
    AIL(end_sample, 4, ret0), AIL(sample_status, 4, ret_done), AIL(set_sample_volume, 8, ret0),
    AIL(set_sample_pan, 8, ret0), AIL(set_sample_loop_count, 8, ret0),
    AIL(sample_loop_count, 4, ret0), AIL(set_sample_reverb, 16, ret0),
    AIL(open_stream, 12, ret0), AIL(start_stream, 4, ret0), AIL(close_stream, 4, ret0),
    AIL(stream_status, 4, ret_done), AIL(set_stream_volume, 8, ret0), AIL(stream_volume, 4, ret0),
    AIL(set_stream_loop_count, 8, ret0),
    AIL(enumerate_3D_providers, 12, ret0), AIL(open_3D_provider, 4, ret1),
    AIL(close_3D_provider, 4, ret0), AIL(set_3D_provider_preference, 12, ret0),
    AIL(3D_provider_attribute, 12, ret0), AIL(allocate_3D_sample_handle, 4, ret0),
    AIL(release_3D_sample_handle, 4, ret0), AIL(set_3D_sample_file, 8, ret0),
    AIL(start_3D_sample, 4, ret0), AIL(end_3D_sample, 4, ret0), AIL(3D_sample_status, 4, ret_done),
    AIL(set_3D_sample_volume, 8, ret0), AIL(set_3D_sample_loop_count, 8, ret0),
    AIL(set_3D_position, 16, ret0), AIL(set_3D_orientation, 28, ret0),
    AIL(3D_update_position, 8, ret0),
};

} // namespace

void mss32_register() {
    static bool done = false;
    if (done)
        return;
    done = true;
    imports_register(g_mss32_shims, std::size(g_mss32_shims));
}
```

Check the 41 names against `docs/analysis.md` (the `mss32` row) and the import list from `pefile`; the test must include every name that is in the game's import table, so extend `expected[]` with all 41.

- [ ] **Step 4: Register and build**

`dx.h`: add `void mss32_register();` beside `qmixer_register`. `dx.cpp` `dx_register_shims`: add `mss32_register();` after `qmixer_register();`. `dx/CMakeLists.txt`: add `mss32.cpp` to `POP_DX_SOURCES`.

```bash
.venv/bin/python kit/tools/format.py --write
.venv/bin/python tools/build.py --target fixture --jobs 8 >/dev/null; ctest --test-dir build/cmake/macos -R dx_tests --output-on-failure | tail -3
cd kit && ../.venv/bin/python -m pytest -q tests/test_game_literals.py
```

Expected: `dx_tests` passes; the literal check passes.

- [ ] **Step 5: Commit**

```bash
cd kit && git add dx/mss32.cpp dx/dx.h dx/dx.cpp dx/CMakeLists.txt dx/tests/dx_tests.cpp runtime/imports.h runtime/imports.cpp && git commit -m "mss32: Miles Sound System arity table

41 stdcall exports with the arity their decorated names carry; startup
succeeds, handles are refused, the 3D provider enumeration is empty. A
game linked against Miles now runs silent instead of drifting its stack."
```

### Task 2.2: Bink and Smacker stubs that fail cleanly

**Files:**
- Create: `kit/dx/bink.cpp`
- Modify: `kit/dx/dx.h`, `kit/dx/dx.cpp`, `kit/dx/CMakeLists.txt`
- Test: `kit/dx/tests/dx_tests.cpp` (`test_bink_smack_stubs`)

**Interfaces:**
- Produces: `_BinkOpen@8` and `_SmackOpen@12` return 0; `_BinkGetError@0` returns a guest string "no video decoder"; `_BinkSetSoundSystem@8` returns 1; `_BinkDDSurfaceType@4` returns 0; all others return 0 with correct arity.

- [ ] **Step 1: Write the failing test**

```cpp
static void test_bink_smack_stubs() {
    cpu_reset();
    CHECK_EQ(call_shim(tramp("binkw32.dll", "_BinkOpen@8"), {0, 0}), 0u);
    uint32_t err = call_shim(tramp("binkw32.dll", "_BinkGetError@0"), {});
    CHECK(err != 0);
    CHECK_EQ(strcmp(gm_str(err).c_str(), "no video decoder"), 0);
    CHECK_EQ(call_shim(tramp("smackw32.dll", "_SmackOpen@12"), {0, 0, 0}), 0u);
    CHECK_EQ(imports_argc(tramp("binkw32.dll", "_BinkCopyToBuffer@28")), 7u);
    CHECK_EQ(imports_argc(tramp("smackw32.dll", "_SmackToBuffer@28")), 7u);
}
```

- [ ] **Step 2: Run to verify failure**

```bash
ctest --test-dir build/cmake/macos -R dx_tests --output-on-failure | tail -3
```

Expected: FAIL at the first `tramp`.

- [ ] **Step 3: Implement**

`kit/dx/bink.cpp`:

```cpp
// bink.cpp - RAD Game Tools' Bink (binkw32.dll) and Smacker (smackw32.dll)
// video as a game imports them. No decoder: BinkOpen and SmackOpen refuse, so
// a game takes its own "video unavailable" path and skips the cinematic. The
// arities come from the decorated names.
#include "dx.h"
#include "../runtime/imports.h"
#include "../runtime/memory.h"
#include "../runtime/win32.h"

#include <string.h>

namespace {

uint32_t g_error_string = 0;

void ret0(X86 *c) { set_eax(c, 0); }
void ret1(X86 *c) { set_eax(c, 1); }

void BinkGetError(X86 *c) {
    if (!g_error_string) {
        static const char text[] = "no video decoder";
        g_error_string = heap_alloc(sizeof text, true, 16);
        memcpy(g_mem + g_error_string, text, sizeof text);
    }
    set_eax(c, g_error_string);
}

#define BINK(name, bytes, fn) {"binkw32.dll", "_Bink" #name "@" #bytes, (bytes) / 4, fn}
#define SMACK(name, bytes, fn) {"smackw32.dll", "_Smack" #name "@" #bytes, (bytes) / 4, fn}

const ImportShim g_video_shims[] = {
    BINK(Open, 8, ret0), BINK(OpenMiles, 4, ret0), BINK(SetSoundSystem, 8, ret1),
    BINK(DDSurfaceType, 4, ret0), BINK(DoFrame, 4, ret0), BINK(NextFrame, 4, ret0),
    BINK(Wait, 4, ret0), BINK(CopyToBuffer, 28, ret0), BINK(Service, 4, ret0),
    BINK(GetError, 0, BinkGetError), BINK(Close, 4, ret0), BINK(BufferClose, 4, ret0),
    SMACK(Open, 12, ret0), SMACK(SoundUseMSS, 4, ret0), SMACK(DoFrame, 4, ret0),
    SMACK(NextFrame, 4, ret0), SMACK(Wait, 4, ret0), SMACK(ToBuffer, 28, ret0),
    SMACK(Close, 4, ret0),
};

} // namespace

void bink_register() {
    static bool done = false;
    if (done)
        return;
    done = true;
    imports_register(g_video_shims, std::size(g_video_shims));
}
```

Register `bink_register()` in `dx_register_shims`, declare in `dx.h`, add `bink.cpp` to `POP_DX_SOURCES`.

- [ ] **Step 4: Build and test**

```bash
.venv/bin/python kit/tools/format.py --write && .venv/bin/python tools/build.py --target fixture --jobs 8 >/dev/null; ctest --test-dir build/cmake/macos -R dx_tests --output-on-failure | tail -3
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd kit && git add dx/bink.cpp dx/dx.h dx/dx.cpp dx/CMakeLists.txt dx/tests/dx_tests.cpp && git commit -m "bink/smack: video stubs that refuse to open

BinkOpen and SmackOpen return 0 with a readable BinkGetError, so a game
skips its cinematics instead of calling into a decoder that is not there."
```

### Task 2.3: kernel32 gaps: `GetDiskFreeSpaceA`, `GetSystemDirectoryA`

**Files:**
- Modify: `kit/runtime/kernel32.cpp` (shims beside `k_GetVolumeInformationA` at `:1493`; table `g_kernel32_shims` near `:4116`)
- Test: `kit/runtime/tests/runtime_tests.cpp`

**Interfaces:**
- Produces: `GetDiskFreeSpaceA(root, &spc, &bps, &free, &total)` writes 8, 512, 0x00100000, 0x00200000 (4 GB free of 8 GB) and returns 1; `GetSystemDirectoryA(buf, n)` writes `C:\WINDOWS\SYSTEM` and returns its length (17), or the needed size when `n` is too small.

- [ ] **Step 1: Write the failing test**

In `runtime_tests.cpp`, inside the kernel32 test function that already exercises `GetVolumeInformationA` (find it with `grep -n GetVolumeInformationA runtime/tests/runtime_tests.cpp`):

```cpp
    uint32_t spc = scratch_block(4), bps = scratch_block(4), fr = scratch_block(4), tot = scratch_block(4);
    uint32_t root = scratch_string("C:\\");
    check(call_import(c, "KERNEL32.dll", "GetDiskFreeSpaceA", {root, spc, bps, fr, tot}) == 1,
          "GetDiskFreeSpaceA succeeds");
    check(rd32(spc) == 8 && rd32(bps) == 512 && rd32(fr) == 0x00100000 && rd32(tot) == 0x00200000,
          "GetDiskFreeSpaceA reports 4 GB free of 8 GB");
    uint32_t sysdir = scratch_block(64);
    check(call_import(c, "KERNEL32.dll", "GetSystemDirectoryA", {sysdir, 64}) == 17 &&
              gm_str(sysdir) == "C:\\WINDOWS\\SYSTEM",
          "GetSystemDirectoryA");
    check(call_import(c, "KERNEL32.dll", "GetSystemDirectoryA", {sysdir, 4}) == 18,
          "GetSystemDirectoryA reports the size needed when the buffer is short");
```

(`scratch_string` exists if another test writes a guest string; otherwise write the bytes with `wr8` from a loop.)

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/python tools/build.py --target fixture --jobs 8 >/dev/null; ctest --test-dir build/cmake/macos -R runtime_tests --output-on-failure | tail -5
```

Expected: FAIL on `GetDiskFreeSpaceA succeeds` (the logging stub returns 0).

- [ ] **Step 3: Implement**

```cpp
// The one drive the runtime presents: 4 GB free of 8 GB, in 512-byte sectors,
// 8 per cluster. A game checks this before writing a save.
void k_GetDiskFreeSpaceA(X86 *c) {
    uint32_t spc = arg(c, 1), bps = arg(c, 2), fr = arg(c, 3), tot = arg(c, 4);
    if (spc) wr32(spc, 8);
    if (bps) wr32(bps, 512);
    if (fr) wr32(fr, 0x00100000);
    if (tot) wr32(tot, 0x00200000);
    set_eax(c, 1);
}

void k_GetSystemDirectoryA(X86 *c) {
    static const char dir[] = "C:\\WINDOWS\\SYSTEM";
    uint32_t buf = arg(c, 0), size = arg(c, 1);
    uint32_t len = sizeof dir - 1;
    if (size <= len) {
        set_eax(c, len + 1);
        return;
    }
    memcpy(g_mem + buf, dir, len + 1);
    set_eax(c, len);
}
```

Table entries: `{"KERNEL32.dll", "GetDiskFreeSpaceA", 5, k_GetDiskFreeSpaceA}`, `{"KERNEL32.dll", "GetSystemDirectoryA", 2, k_GetSystemDirectoryA}`.

- [ ] **Step 4: Run tests, commit**

```bash
.venv/bin/python kit/tools/format.py --write && .venv/bin/python tools/build.py --target fixture --jobs 8 >/dev/null; ctest --test-dir build/cmake/macos -R runtime_tests --output-on-failure | tail -3
cd kit && git add runtime/kernel32.cpp runtime/tests/runtime_tests.cpp && git commit -m "kernel32: GetDiskFreeSpaceA and GetSystemDirectoryA"
```

### Task 2.4: user32 gaps: ten window-state and message functions

**Files:**
- Modify: `kit/runtime/user32.cpp` (shims and `g_user32_shims` table)
- Test: `kit/runtime/tests/runtime_tests.cpp` (extend the window test that checks `GetActiveWindow`)

**Interfaces:**
- Produces: `GetMenu(hwnd)` = 0; `WaitMessage()` yields once (calls `sched_checkpoint()` and returns 1); `FindWindowA(cls, title)` = 0 (a single-instance check finds nothing); `OpenIcon(hwnd)` = 1; `SystemParametersInfoA(action, ...)` = 0 with `SPI_GETWORKAREA` (48) writing the main window's client rect and returning 1; `GetMessagePos()` = packed last pointer position (`y << 16 | x`) as user32 records it; `GetMessageTime()` = the runtime's tick count; `SetForegroundWindow(hwnd)` = 1; `SetActiveWindow(hwnd)` = previous active (the main window handle); `IsIconic(hwnd)` = 0.

- [ ] **Step 1: Write the failing test**

After the `SetFocus` check in the window test:

```cpp
    check(call_import(c, "USER32.dll", "GetMenu", {hwnd}) == 0, "GetMenu: no menu");
    check(call_import(c, "USER32.dll", "IsIconic", {hwnd}) == 0, "IsIconic: never minimised");
    check(call_import(c, "USER32.dll", "SetForegroundWindow", {hwnd}) == 1, "SetForegroundWindow");
    check(call_import(c, "USER32.dll", "SetActiveWindow", {hwnd}) == hwnd, "SetActiveWindow returns the previous");
    check(call_import(c, "USER32.dll", "OpenIcon", {hwnd}) == 1, "OpenIcon");
    check(call_import(c, "USER32.dll", "FindWindowA", {0, 0}) == 0, "FindWindowA finds no other instance");
    check(call_import(c, "USER32.dll", "WaitMessage", {}) == 1, "WaitMessage returns");
    uint32_t work = scratch_block(16);
    check(call_import(c, "USER32.dll", "SystemParametersInfoA", {48, 0, work, 0}) == 1 &&
              rd32(work + 8) == 640 && rd32(work + 12) == 480,
          "SPI_GETWORKAREA is the window's client area");
    check(call_import(c, "USER32.dll", "SystemParametersInfoA", {0x2000, 0, 0, 0}) == 0,
          "unknown SPI actions fail");
    // The pointer the gate last delivered is what GetMessagePos packs.
    host_gate_pointer_event(200, 100, 0);   // the same call the input tests use
    check(call_import(c, "USER32.dll", "GetMessagePos", {}) == ((100u << 16) | 200u), "GetMessagePos packs y:x");
    check(call_import(c, "USER32.dll", "GetMessageTime", {}) <= call_import(c, "KERNEL32.dll", "GetTickCount", {}),
          "GetMessageTime is on the tick clock");
```

Adjust `host_gate_pointer_event`'s signature to the one in `kit/host/input_gate.h` (grep it); if the runtime test cannot reach the gate, set the recorded position through the user32 function that `WM_MOUSEMOVE` posting uses (grep `last_pointer` or `g_cursor` in `user32.cpp`) and note the substitution in the test comment.

- [ ] **Step 2: Run to verify failure**

Expected: FAIL at `GetMenu` (logging stub returns 0 already, so the first failing check is `SetForegroundWindow`); every check must be present regardless.

- [ ] **Step 3: Implement**

In `user32.cpp`:

```cpp
void u_GetMenu(X86 *c) { set_eax(c, 0); }
void u_IsIconic(X86 *c) { set_eax(c, 0); }
void u_OpenIcon(X86 *c) { set_eax(c, 1); }
void u_SetForegroundWindow(X86 *c) { set_eax(c, 1); }
void u_FindWindowA(X86 *c) { set_eax(c, 0); }

void u_SetActiveWindow(X86 *c) {
    // Single-window runtime: the main window is always the active one.
    set_eax(c, host_main_window());
}

void u_WaitMessage(X86 *c) {
    // A blocking wait in the original; here a scheduling checkpoint so the
    // service threads run, then return as if a message arrived.
    sched_checkpoint();
    set_eax(c, 1);
}

void u_SystemParametersInfoA(X86 *c) {
    const uint32_t SPI_GETWORKAREA = 48;
    uint32_t action = arg(c, 0), param = arg(c, 2);
    if (action == SPI_GETWORKAREA && param) {
        uint32_t w = 0, h = 0;
        host_client_size(&w, &h);          // the helper GetClientRect uses; grep u_GetClientRect
        wr32(param + 0, 0);
        wr32(param + 4, 0);
        wr32(param + 8, w);
        wr32(param + 12, h);
        set_eax(c, 1);
        return;
    }
    log_once(("spi:" + std::to_string(action)).c_str(), "SystemParametersInfoA(%u) unsupported", action);
    set_eax(c, 0);
}

void u_GetMessagePos(X86 *c) {
    int32_t x = 0, y = 0;
    cursor_position(&x, &y);               // the helper GetCursorPos uses; grep u_GetCursorPos
    set_eax(c, ((uint32_t)(uint16_t)y << 16) | (uint16_t)x);
}

void u_GetMessageTime(X86 *c) { set_eax(c, tick_count_ms()); }  // the helper k_GetTickCount uses
```

Replace `host_client_size`, `cursor_position`, `tick_count_ms` with the real helper names found in the neighbouring shims (`u_GetClientRect`, `u_GetCursorPos`, `k_GetTickCount`). Table entries with arities: `GetMenu 1`, `IsIconic 1`, `OpenIcon 1`, `SetForegroundWindow 1`, `FindWindowA 2`, `SetActiveWindow 1`, `WaitMessage 0`, `SystemParametersInfoA 4`, `GetMessagePos 0`, `GetMessageTime 0`.

- [ ] **Step 4: Test and commit**

```bash
.venv/bin/python kit/tools/format.py --write && .venv/bin/python tools/build.py --target fixture --jobs 8 >/dev/null; ctest --test-dir build/cmake/macos -R runtime_tests --output-on-failure | tail -3
cd kit && git add runtime/user32.cpp runtime/tests/runtime_tests.cpp && git commit -m "user32: window state and message-position shims a 2000-era game polls"
```

### Task 2.5: gdi32 gaps: `GetDeviceCaps`, `GetTextExtentPointA`, `SetBkColor`

**Files:**
- Modify: `kit/runtime/gdi32.cpp` (shims; table `g_gdi32_shims` at `:478`)
- Test: `kit/runtime/tests/runtime_tests.cpp` (the gdi32 test that exercises `TextOutA`)

**Interfaces:**
- Produces: `GetDeviceCaps(hdc, index)`: `HORZRES` (8) and `VERTRES` (10) = the current display mode, `BITSPIXEL` (12) = its depth, `PLANES` (14) = 1, `RASTERCAPS` (38) = `RC_PALETTE` (0x100) only when depth is 8, `SIZEPALETTE` (104) = 256 when depth is 8 else 0, `NUMCOLORS` (24) = 256 when depth 8 else -1, other indices 0. `GetTextExtentPointA(hdc, str, n, &size)`: size = (n * glyph_w, glyph_h) from the font the kit's `TextOutA` draws with, returns 1. `SetBkColor(hdc, color)` stores the colour for `TextOutA`'s opaque background and returns the previous value (`CLR_INVALID` 0xffffffff the first time is wrong; the default is white 0x00ffffff).

- [ ] **Step 1: Write the failing test**

```cpp
    check(call_import(c, "GDI32.dll", "GetDeviceCaps", {hdc, 8}) == 640 &&
              call_import(c, "GDI32.dll", "GetDeviceCaps", {hdc, 10}) == 480,
          "GetDeviceCaps HORZRES/VERTRES are the mode");
    check(call_import(c, "GDI32.dll", "GetDeviceCaps", {hdc, 12}) == 16, "BITSPIXEL");
    check(call_import(c, "GDI32.dll", "GetDeviceCaps", {hdc, 14}) == 1, "PLANES");
    check(call_import(c, "GDI32.dll", "GetDeviceCaps", {hdc, 38}) == 0, "RASTERCAPS has no palette at 16 bpp");
    uint32_t sz = scratch_block(8), text = scratch_string("Pharaoh");  // any 7-character string
    check(call_import(c, "GDI32.dll", "GetTextExtentPointA", {hdc, text, 7, sz}) == 1 &&
              rd32(sz) == 7 * gdi_glyph_width() && rd32(sz + 4) == gdi_glyph_height(),
          "GetTextExtentPointA measures with TextOutA's font");
    check(call_import(c, "GDI32.dll", "SetBkColor", {hdc, 0x00ff0000}) == 0x00ffffff, "SetBkColor returns white first");
    check(call_import(c, "GDI32.dll", "SetBkColor", {hdc, 0}) == 0x00ff0000, "then the previous colour");
```

`gdi_glyph_width()`/`gdi_glyph_height()`: expose the constants `TextOutA` uses (grep `TextOutA` in `gdi32.cpp` for the glyph cell) through `gdi32.h` for the test. The test string must not name a game in kit code; use `"ABCDEFG"`.

- [ ] **Step 2: Run to verify failure**, **Step 3: Implement** following the interface above (a `static uint32_t g_bk_color = 0x00ffffff;` per DC is enough; the kit has one DC), **Step 4: Test, format, commit**:

```bash
cd kit && git add runtime/gdi32.cpp runtime/gdi32.h runtime/tests/runtime_tests.cpp && git commit -m "gdi32: GetDeviceCaps, GetTextExtentPointA, SetBkColor"
```

### Task 2.6: Boot to the main menu in the smoke host; first smoke script

**Files:**
- Create: `smoke/main-menu.script`
- Modify: `docs/analysis.md` (run log), `README.md` (status), `CHANGELOG.md`
- Modify: submodule pointer `kit`

**Interfaces:**
- Produces: `smoke/main-menu.script` drives the game from boot to a frame dump of the main menu; the dump `build/smoke/main-menu.ppm` shows the menu.

- [ ] **Step 1: Rebuild with the Phase 2 kit and run the smoke host with a dump-only script**

```bash
.venv/bin/python tools/build.py --jobs 8 2>&1 | tail -3
cat > smoke/main-menu.script <<'EOF'
# Boot to the main menu and dump it. Coordinates are guest pixels at 1024x768
# (the GOG default); RECOMP_DDRAW_MODES lists what the display offers.
wait 15000
dump main-menu
EOF
RECOMP_SCRIPT=$PWD/smoke/main-menu.script RECOMP_HOST_DUMP_DIR=build/smoke \
RECOMP_DDRAW_MODES=640x480x16,800x600x16,1024x768x16 RECOMP_SMOKE_DRAWABLE=1024x768 \
RECOMP_MAX_SECONDS=30 build/recomp/pop_smoke > build/smoke-1.log 2>&1; echo "exit $?"
.venv/bin/python kit/tools/recomp/ppm_to_png.py build/smoke/main-menu.ppm build/smoke/main-menu.png
```

Expected: a PNG of the game's title/main menu. If the game exits first, `build/smoke-1.log` names the shim or fault; fix in the kit with a test (the pattern of Tasks 2.3 to 2.5) and repeat. Known likely stops: the game's `sierra.ini` read (answer: the file is optional; verify the game continues), `Pharaoh.ini` `CDDrive=G` (the kit strips drive letters, so `G:\audio\music\` resolves under the guest root; verify with `RECOMP_LOG=1` that `AUDIO\Music\...` opens).

- [ ] **Step 2: Read the menu layout and script a click into the campaign**

Open `build/smoke/main-menu.png`, note the button positions, and extend the script:

```
wait 15000
dump main-menu
click left <x> <y>          # the first menu button (new family / campaign)
wait 5000
dump after-first-click
```

Run again; expected: the second dump shows the next screen.

- [ ] **Step 3: Record and commit**

Run log entry in `docs/analysis.md` ("main menu reached in the smoke host": the shims added, what the game logged, the mode it set). README status line: "boots to the main menu in the smoke host on macOS; silent". Changelog line per kit change (mss32 arity table, video stubs, the 15 win32 shims).

```bash
git add smoke/main-menu.script docs/analysis.md README.md CHANGELOG.md kit
git commit -m "The game boots to its main menu in the smoke host

Kit pharaoh branch: Miles arity table, Bink/Smacker stubs, the kernel32,
user32 and gdi32 shims the import table lacked."
```

---

## Phase 3: sound through Miles

### Task 3.1: `AIL_file_read` / `AIL_mem_free_lock` and the sample path (WAV effects)

**Files:**
- Modify: `kit/dx/mss32.cpp`
- Create: `kit/dx/riff.h`, `kit/dx/riff.cpp` (a RIFF WAVE parser over guest memory)
- Modify: `kit/dx/CMakeLists.txt` (`riff.cpp`)
- Test: `kit/dx/tests/dx_tests.cpp` (`test_riff_parse`, `test_mss32_sample`)

**Interfaces:**
- Produces:
  - `bool riff_parse_wave(uint32_t guest_ptr, uint32_t bytes, RiffWave *out)` with `struct RiffWave { uint32_t pcm; uint32_t pcm_bytes; uint32_t rate; uint16_t channels; uint16_t bits; }`.
  - `AIL_file_read(filename, dest)`: reads the guest-visible file through the runtime's file seam (`gm_open`/the helper `k_CreateFileA` uses), allocates `size` bytes of guest heap when `dest == 0xffffffff` (`FILE_READ_WITH_SIZE`), returns the guest pointer or 0. `AIL_mem_free_lock(ptr)` frees it.
  - Sample handles: `AIL_allocate_sample_handle(driver)` returns a non-zero handle (1..64), `AIL_init_sample` resets it, `AIL_set_sample_file(h, image, block)` parses the WAV at `image` (returns 1, or 0 when it is not PCM WAVE), `AIL_start_sample` calls `host_audio_play` on a channel taken from the same channel pool `dsound.cpp` uses (grep `next_channel`/`channel_alloc` there), `AIL_end_sample` stops it, `AIL_sample_status` returns `SMP_PLAYING` (4) while `host_audio_is_playing`, `SMP_DONE` (2) after, `SMP_FREE` (1) for an unallocated handle. Volume 0..127 maps to the host scale as `dsound.cpp` maps DirectSound volume (read its conversion and reuse the helper); pan 0..127 (64 centre) likewise; loop count 0 = forever, n = n plays.

- [ ] **Step 1: Write the failing tests**

```cpp
static void test_riff_parse() {
    cpu_reset();
    uint32_t wav = sc(0x100);
    // A 44-byte canonical header + 8 bytes of 8-bit mono PCM at 22050 Hz.
    static const uint8_t header[44] = {
        'R','I','F','F', 44 + 8 - 8, 0, 0, 0, 'W','A','V','E', 'f','m','t',' ', 16, 0, 0, 0,
        1, 0, 1, 0, 0x22, 0x56, 0, 0, 0x22, 0x56, 0, 0, 1, 0, 8, 0, 'd','a','t','a', 8, 0, 0, 0};
    for (uint32_t i = 0; i < 44; ++i) wr8(wav + i, header[i]);
    for (uint32_t i = 0; i < 8; ++i) wr8(wav + 44 + i, (uint8_t)(0x80 + i));
    RiffWave w{};
    CHECK(riff_parse_wave(wav, 52, &w));
    CHECK_EQ(w.pcm, wav + 44);
    CHECK_EQ(w.pcm_bytes, 8u);
    CHECK_EQ(w.rate, 22050u);
    CHECK_EQ(w.channels, 1u);
    CHECK_EQ(w.bits, 8u);
    wr8(wav + 20, 2); // format tag 2 (ADPCM) is refused
    CHECK(!riff_parse_wave(wav, 52, &w));
}

static void test_mss32_sample() {
    cpu_reset();
    g_plays.clear();
    uint32_t wav = build_test_wave();   // the same bytes as test_riff_parse, factored out
    uint32_t h = call_shim(tramp("mss32.dll", "_AIL_allocate_sample_handle@4"), {1});
    CHECK(h != 0);
    call_shim(tramp("mss32.dll", "_AIL_init_sample@4"), {h});
    CHECK_EQ(call_shim(tramp("mss32.dll", "_AIL_set_sample_file@12"), {h, wav, 0}), 1u);
    call_shim(tramp("mss32.dll", "_AIL_set_sample_volume@8"), {h, 127});
    call_shim(tramp("mss32.dll", "_AIL_start_sample@4"), {h});
    CHECK_EQ(g_plays.size(), 1u);
    CHECK_EQ(g_plays[0].rate, 22050u);
    CHECK_EQ(g_plays[0].bytes, 8u);
    CHECK_EQ(call_shim(tramp("mss32.dll", "_AIL_sample_status@4"), {h}), 4u);
    call_shim(tramp("mss32.dll", "_AIL_end_sample@4"), {h});
    CHECK_EQ(call_shim(tramp("mss32.dll", "_AIL_sample_status@4"), {h}), 2u);
    call_shim(tramp("mss32.dll", "_AIL_release_sample_handle@4"), {h});
    CHECK_EQ(call_shim(tramp("mss32.dll", "_AIL_sample_status@4"), {h}), 1u);
}
```

`g_plays` is the test's record of `host_audio_play` calls, already used by `test_qmixer`.

- [ ] **Step 2: Run to verify failure** (`riff_parse_wave` undefined).

- [ ] **Step 3: Implement `riff.cpp`**

```cpp
// riff.cpp - RIFF WAVE in guest memory: the header a game hands a sound
// library after reading a .wav itself. PCM (format tag 1) only.
#include "riff.h"
#include "../runtime/memory.h"

bool riff_parse_wave(uint32_t p, uint32_t bytes, RiffWave *out) {
    if (bytes < 12 || rd32(p) != 0x46464952 /* RIFF */ || rd32(p + 8) != 0x45564157 /* WAVE */)
        return false;
    uint32_t at = p + 12, end = p + bytes;
    bool have_fmt = false;
    while (at + 8 <= end) {
        uint32_t id = rd32(at), size = rd32(at + 4);
        if (id == 0x20746d66 /* fmt  */ && size >= 16) {
            if (rd16(at + 8) != 1)
                return false;
            out->channels = rd16(at + 10);
            out->rate = rd32(at + 12);
            out->bits = rd16(at + 22);
            have_fmt = true;
        } else if (id == 0x61746164 /* data */ && have_fmt) {
            out->pcm = at + 8;
            out->pcm_bytes = size > end - (at + 8) ? end - (at + 8) : size;
            return out->pcm_bytes > 0;
        }
        at += 8 + ((size + 1) & ~1u);
    }
    return false;
}
```

- [ ] **Step 4: Implement the sample path in `mss32.cpp`**

Add a `Sample` struct (`handle, alive, channel, wave, volume=127, pan=64, loops=1, playing`), a `std::vector<Sample>` of 64, replace the `ret0` entries for the sample functions with real shims per the interface, and implement `AIL_file_read`/`AIL_mem_free_lock` on the runtime's file seam and `heap_alloc`/`heap_free`. `host_audio_play` takes a `HostAudioPlay` record: fill it the way `dsound.cpp`'s `Play` does (grep `HostAudioPlay p{}` there) with `pcm = g_mem + wave.pcm`.

- [ ] **Step 5: Build, test, format, commit**

```bash
.venv/bin/python kit/tools/format.py --write && .venv/bin/python tools/build.py --target fixture --jobs 8 >/dev/null; ctest --test-dir build/cmake/macos -R dx_tests --output-on-failure | tail -3
cd kit && git add dx/riff.h dx/riff.cpp dx/mss32.cpp dx/CMakeLists.txt dx/tests/dx_tests.cpp && git commit -m "mss32: sample handles play RIFF WAVE images through the host mixer

AIL_file_read loads the file into guest memory, AIL_set_sample_file parses
the WAVE, start/end/status map onto a host channel; volume and pan use the
DirectSound conversions."
```

### Task 3.2: Streams: MP3 music through `AIL_open_stream`

**Files:**
- Modify: `kit/dx/dshow.cpp:159-260` (extract the MP3 `Source` decoder into a reusable unit), create `kit/dx/mp3_source.h`, `kit/dx/mp3_source.cpp`
- Modify: `kit/dx/mss32.cpp`, `kit/dx/CMakeLists.txt`
- Test: `kit/dx/tests/dx_tests.cpp` (`test_mss32_stream` using a tiny MP3 fixture the dshow tests already carry; grep `mp3` in `dx/tests`)

**Interfaces:**
- Produces: `struct Mp3Source` with `bool open(const std::vector<uint8_t> &bytes)`, `bool decode_next(std::vector<int16_t> &out)`, `uint32_t rate()`, `uint32_t channels()`, `void seek_frames(uint64_t)`, `bool drained()`. `dshow.cpp` uses it unchanged in behaviour. `AIL_open_stream(driver, filename, mem)` opens the file through the runtime file seam, decodes with `Mp3Source`, converts the channel to a stream with `host_audio_stream`, and refills from the frame pump (`mss32_frame_pump`, registered beside `qmixer_frame_pump` in `dx_register_shims`) using `host_audio_queue` while `host_audio_queued_bytes` is under one second. `AIL_start_stream`, `AIL_close_stream`, `AIL_stream_status` (4 while playing, 2 when drained), `AIL_set_stream_volume`, `AIL_stream_volume`, `AIL_set_stream_loop_count` (0 = loop: `seek_frames(0)` when drained).

- [ ] **Step 1: Write the failing test** (a stream opened on the fixture MP3 converts channel to a stream and queues bytes after one pump):

```cpp
static void test_mss32_stream() {
    cpu_reset();
    g_plays.clear();
    uint32_t name = scratch_c_string("music\\test.mp3");   // a fixture file the test environment maps
    uint32_t s = call_shim(tramp("mss32.dll", "_AIL_open_stream@12"), {1, name, 0});
    CHECK(s != 0);
    call_shim(tramp("mss32.dll", "_AIL_start_stream@4"), {s});
    mss32_frame_pump(cpu());
    CHECK_EQ(g_plays.size(), 1u);
    CHECK(host_audio_queued_bytes(g_plays[0].channel) > 0);
    CHECK_EQ(call_shim(tramp("mss32.dll", "_AIL_stream_status@4"), {s}), 4u);
    call_shim(tramp("mss32.dll", "_AIL_close_stream@4"), {s});
    CHECK_EQ(call_shim(tramp("mss32.dll", "_AIL_stream_status@4"), {s}), 2u);
}
```

Use the same fixture mapping the dshow test uses for its MP3 (grep `test_dshow` in `dx_tests.cpp`).

- [ ] **Step 2: Run to verify failure.** **Step 3: Extract `Mp3Source` from `dshow.cpp`** keeping `dshow` tests green (`ctest -R dx_tests`). **Step 4: Implement the stream path.** **Step 5: Verify audibly in the headless host:**

```bash
RECOMP_HOST_AUDIO_CAPTURE=build/audio-menu.wav RECOMP_MAX_SECONDS=30 build/recomp/pop_headless > build/headless-audio.log 2>&1
.venv/bin/python -c "import wave;w=wave.open('build/audio-menu.wav');print(w.getnframes()/w.getframerate(),'s')"
```

Expected: the capture holds most of 30 s of sound (menu music), no underrun lines in the log.

- [ ] **Step 6: Format, commit**

```bash
cd kit && git add dx/mp3_source.h dx/mp3_source.cpp dx/dshow.cpp dx/mss32.cpp dx/dx.cpp dx/dx.h dx/CMakeLists.txt dx/tests/dx_tests.cpp && git commit -m "mss32: streams decode MP3 through the shared minimp3 source

The DirectShow music path's decoder becomes Mp3Source and serves Miles
streams too; refills run from the frame pump against host_audio_queued_bytes."
```

### Task 3.3: Re-pin, record, and land Phase 2-3 kit work on kit main

**Files:**
- Modify: submodule pointer `kit`, `CHANGELOG.md`, `docs/analysis.md`, `README.md`

- [ ] **Step 1: Run every suite**

```bash
.venv/bin/python tools/test.py && .venv/bin/python -m pytest -q tests && .venv/bin/python tools/test.py --native 2>&1 | tail -5
cd kit && ../.venv/bin/python tools/check_repo.py && ../.venv/bin/python tools/check_game_literals.py && cd ..
```

Expected: all pass; the game-labelled Populous-bound suites are reported as skipped or not run, per `docs/testing.md`.

- [ ] **Step 2: Land on kit main**

```bash
cd ~/Documents/Tests/recomp-kit
git -c protocol.file.allow=always pull --ff-only ~/Documents/Tests/pharaoh-recomp/kit pharaoh
git push origin main
cd ~/Documents/Tests/pharaoh-recomp && git -C kit -c protocol.file.allow=always fetch local main && git -C kit checkout -q local/main && git -C kit checkout -q -B pharaoh
```

- [ ] **Step 3: Commit the pin with the run log and changelog**

```bash
git add kit CHANGELOG.md docs/analysis.md README.md
git commit -m "Sound: effects and music play through the Miles shims; kit pinned to main"
```

---

## Phase 4: the macOS app plays a mission

### Task 4.1: Campaign entry, saves and settings in the smoke host

**Files:**
- Create: `smoke/first-mission.script`
- Modify: `docs/analysis.md`, `README.md`, `CHANGELOG.md`

**Interfaces:**
- Produces: a script from the main menu into the first Predynastic mission (Nubt/"Begin Family History"), with dumps at 10 s and 30 s of play, and a save written through the game's own menu.

- [ ] **Step 1: Script the path** (coordinates from dumps as in Task 2.6): main menu → Begin Family History → name entry (`key` events for a name, `key RETURN down/up`) → mission briefing → the city view. Dump `city-10s`, `city-30s`.

- [ ] **Step 2: Verify the city runs** (the two dumps differ: walkers move; compare with `kit/tools/recomp/compare_frames.py`):

```bash
.venv/bin/python kit/tools/recomp/compare_frames.py build/smoke/city-10s.ppm build/smoke/city-30s.ppm
```

Expected: a non-trivial changed fraction (workers walking, the date advancing).

- [ ] **Step 3: Save and reload.** Extend the script: open the game menu (`key ESCAPE`), Save, confirm; after a restart `Load` the save. Verify the save exists in the profile:

```bash
find build/recomp/profile -iname '*.sav' -newer smoke/first-mission.script
```

Expected: the `.sav` under the profile's `save\` directory, not under `original/gog/app`.

- [ ] **Step 4: Record, commit**

```bash
git add smoke/first-mission.script docs/analysis.md README.md CHANGELOG.md && git commit -m "Smoke: the first mission runs and saves in the profile"
```

### Task 4.2: The macOS app plays by hand; resolution and cursor

**Files:**
- Modify: `game.toml` (`[hooks]` if a frame clock site is identified), `docs/analysis.md`

- [ ] **Step 1: Run the app**

```bash
.venv/bin/python tools/build.py --jobs 8 && open build/PharaohRecomp.app
```

Play five minutes: menu, mission start, build a few houses, right-click information panels, scroll with the mouse at the edges and the arrow keys, open the in-game options. Note every misbehaviour (cursor offset, missing sound, wrong colours, frame rate) in the run log.

- [ ] **Step 2: Frame pacing.** If the game runs unthrottled or too slowly, find its limiter:

```bash
grep -l "timeGetTime\|GetTickCount" analysis/decompiled/Pharaoh.exe/functions/*.asm | head
```

If the main loop waits on `GetTickCount`, record the return addresses of those calls as `frame_clock_*` in `game.toml` (replacing sentinels) and adjust `tests/test_game_config.py`'s sentinel test to allow the identified ones; if it waits on `timeGetTime`, keep the sentinels and note it, as Majesty did.

- [ ] **Step 3: Commit**

```bash
git add game.toml tests/test_game_config.py docs/analysis.md && git commit -m "The macOS app plays the first mission by hand; pacing measured"
```

---

## Phase 5: iPad

### Task 5.1: iOS bundle and first boot

**Files:**
- Modify: `game.toml` `[bundle]` and `[touch]`, `README.md` ("Play on an iPad"), `docs/analysis.md`

- [ ] **Step 1: Check the staged size**

```bash
.venv/bin/python - <<'EOF'
import importlib.util, pathlib
spec = importlib.util.spec_from_file_location("s", "kit/tools/stage_game_files.py"); s = importlib.util.module_from_spec(spec); spec.loader.exec_module(spec and s)
import tomllib
cfg = tomllib.load(open("game.toml","rb"))
root = pathlib.Path("original/gog/app"); total = 0
for p in root.rglob("*"):
    if p.is_file() and not s.excluded(p.relative_to(root), cfg["bundle"]["exclude"]): total += p.stat().st_size
print(total // 2**20, "MB staged")
EOF
```

Expected: about 760 MB. Decide whether `BINKS/` (140 MB, unplayable until a decoder exists) joins the exclusions; if so add `"BINKS"` and update `test_bundle_exclusions_and_setup`.

- [ ] **Step 2: Build, install, launch**

```bash
.venv/bin/python tools/build.py --target ios --team <TEAM_ID> --device <DEVICE_ID> --console 2>&1 | tee build/ios-1.log | tail -30
```

Expected: the app seeds the game into Documents on first launch, sets a display mode, reaches the main menu with music. If the seeding's stamp or a path fails, the console names it.

- [ ] **Step 3: Touch play.** Tap through Begin Family History, enter a name with the keypad, reach the city; hold a finger at each screen edge to scroll; long-press a building for its right-click panel. Record what works in the run log ("playing on the iPad by hand"). Kit touch fixes, if any, go on the `pharaoh` branch with `input_touch_tests` cases as the Majesty session did.

- [ ] **Step 4: Commit**

```bash
git add game.toml tests/test_game_config.py README.md docs/analysis.md CHANGELOG.md kit && git commit -m "The iPad app boots to the menu and plays by touch"
```

---

## Phase 6: Linux and Windows

### Task 6.1: Lift the macOS-only gate for the desktop hosts

**Files:**
- Modify: `kit/tools/build.py:37-38` (`MACOS_ONLY`), `:226-228`
- Test: `kit/tools/tests/test_build.py`

**Interfaces:**
- Produces: `MACOS_ONLY = {"ios"}`; `tools/build.py --target app` on Linux and Windows configures the `linux`/`windows` preset and builds `recomp_app`; `--regenerate` runs the translator there too (it is pure Python).

- [ ] **Step 1: Write the failing test**

```python
def test_app_target_allowed_on_linux(tmp_path):
    (tmp_path / "game.toml").write_text("")
    args, _ = build.parse_args(["--target", "app", "--game-dir", str(tmp_path)], system="Linux")
    assert args.preset == "linux"


def test_ios_target_still_needs_macos(tmp_path):
    (tmp_path / "game.toml").write_text("")
    with pytest.raises(SystemExit):
        build.parse_args(["--target", "ios", "--stub", "--game-dir", str(tmp_path)], system="Linux")
```

- [ ] **Step 2: Run to verify failure**, **Step 3: Implement** (`MACOS_ONLY = {"ios"}`, error text "The iOS packager runs on macOS"), **Step 4: Test and commit**:

```bash
cd kit && git add tools/build.py tools/tests/test_build.py && git commit -m "build.py: the desktop hosts build on Linux and Windows

CI has linked recomp_app on both since M0; only the iOS packager needs macOS."
```

### Task 6.2: Desktop packaging: a Linux directory and tarball, a Windows folder

**Files:**
- Create: `kit/tools/package_desktop.py`
- Modify: `kit/tools/build.py` (after a successful `app` build on Linux/Windows, call the packager)
- Test: `kit/tools/tests/test_package_desktop.py`

**Interfaces:**
- Produces: `package_desktop.stage(app_binary: Path, cfg: dict, out_dir: Path) -> Path` creates `out_dir/<app_name>/` with the binary, a `README.txt` naming the game directory the app expects (`RECOMP_DATA=<path to your game>` or a `game/` directory beside the binary, which `host/game_path.cpp` already searches; confirm with `grep -n "game/" kit/host/game_path.cpp`) and `LICENSE`/`NOTICE` from the kit. On Linux it also writes `<app_name>-linux-x86_64.tar.gz` (or `aarch64`). No game file is ever copied.

- [ ] **Step 1: Write the failing test**

```python
def test_stage_layout(tmp_path):
    exe = tmp_path / "recomp_app"; exe.write_bytes(b"\x7fELF")
    cfg = {"game": {"app_name": "StubRecomp", "name": "Stub Game", "executable": "STUB.EXE"}}
    out = package_desktop.stage(exe, cfg, tmp_path / "out", system="Linux")
    assert (out / "StubRecomp").is_file()
    assert "STUB.EXE" in (out / "README.txt").read_text()
    assert (out / "LICENSE").is_file()
    assert (tmp_path / "out" / "StubRecomp-linux-x86_64.tar.gz").is_file()
```

- [ ] **Step 2: Run to verify failure**, **Step 3: Implement** with `shutil.copy2`, `tarfile`, `platform.machine()`; **Step 4: Hook into `build.py`** after `build(...)` when `args.target == "app"` and the system is Linux or Windows; **Step 5: Test, commit**:

```bash
cd kit && git add tools/package_desktop.py tools/build.py tools/tests/test_package_desktop.py && git commit -m "Desktop packaging: a folder with the app and its notices, a tarball on Linux"
```

### Task 6.3: Run the game on Linux and Windows

**Files:**
- Modify: `docs/analysis.md`, `README.md` ("Build on Linux", "Build on Windows"), `.github/workflows/checks.yml`

- [ ] **Step 1: Linux.** On a Linux machine (or a VM) with the game copied to `original/gog/app`:

```bash
sudo apt-get install -y clang lld libasound2-dev libpulse-dev libx11-dev libxext-dev libxrandr-dev libxcursor-dev libxi-dev libxkbcommon-dev libwayland-dev libdecor-0-dev libgl1-mesa-dev libegl1-mesa-dev libdrm-dev libgbm-dev libdbus-1-dev libudev-dev mesa-vulkan-drivers
python3 -m venv .venv && .venv/bin/python -m pip install -r kit/requirements-dev.txt
.venv/bin/python tools/setup.py --install original/gog/app --link-only
.venv/bin/python tools/analyze.py --ghidra-home /path/to/ghidra_12.1.3_PUBLIC
.venv/bin/python tools/build.py --regenerate --jobs 8
RECOMP_SCRIPT=$PWD/smoke/first-mission.script RECOMP_HOST_DUMP_DIR=build/smoke build/recomp/pop_smoke
build/linux/PharaohRecomp/PharaohRecomp
```

Expected: the smoke dumps match the macOS ones (compare with `compare_frames.py`, expect a small difference from timing only); the app opens a window through Vulkan and plays. Record GPU driver and any Vulkan validation output (`RECOMP_GPU_VALIDATE=1`).

- [ ] **Step 2: Windows.** In a Visual Studio developer shell with clang and lld on `PATH`:

```powershell
py -3 -m venv .venv; .venv\Scripts\python -m pip install -r kit\requirements-dev.txt
.venv\Scripts\python tools\setup.py --install original\gog\app --link-only
.venv\Scripts\python tools\analyze.py --ghidra-home C:\path\to\ghidra_12.1.3_PUBLIC
.venv\Scripts\python tools\build.py --regenerate --jobs 8
build\windows\PharaohRecomp\PharaohRecomp.exe
```

Expected: the same. Path handling differences (`\` in guest paths against the host's own separator) surface here; fix in `kit/platform/os_win32.cpp` with a `platform_tests` case.

- [ ] **Step 3: CI.** Add to this repository's `.github/workflows/checks.yml` matrix a `windows-2025` job running the same portable tests and `tools/build.py --stub` (clang from `ilammy/msvc-dev-cmd@v1` as the kit's CI does).

- [ ] **Step 4: Document and commit**

```bash
git add README.md docs/analysis.md CHANGELOG.md .github/workflows/checks.yml kit && git commit -m "Linux and Windows: the app builds, packages and plays the first mission"
```

---

## Phase 7: Android

The kit has no Android target today (design spec M4). These tasks add it to the kit; the game repository only gains a `[bundle]` note and README section.

### Task 7.1: `android` CMake preset and the NDK toolchain

**Files:**
- Modify: `kit/CMakePresets.json` (presets `android`, `android-stub`), `kit/CMakeLists.txt` (`if(ANDROID)` branches where `IOS` is special-cased at `:32-40`, `:80-103`), `kit/host/gpu/CMakeLists.txt` (Vulkan backend on Android links `vulkan` from the NDK), `kit/platform/CMakeLists.txt` (`log` library on Android)
- Test: kit CI job `android-stub` (configure + build `recomp_app` as a shared library)

**Interfaces:**
- Produces: `cmake --preset android-stub` with `ANDROID_NDK_HOME` set configures for `arm64-v8a`, API 29, and builds `librecomp_app.so` (the host as a shared library, `add_library(recomp_app SHARED ...)` when `ANDROID`), linking SDL3 static and the NDK's `vulkan` and `log`.

- [ ] **Step 1: Add the presets**

```json
{
  "name": "android",
  "inherits": "base",
  "binaryDir": "${sourceDir}/build/cmake/android",
  "toolchainFile": "$env{ANDROID_NDK_HOME}/build/cmake/android.toolchain.cmake",
  "cacheVariables": {
    "ANDROID_ABI": "arm64-v8a",
    "ANDROID_PLATFORM": "android-29",
    "ANDROID_STL": "c++_static",
    "POP_TRANSLATE": "ON"
  }
},
{
  "name": "android-stub",
  "inherits": "android",
  "binaryDir": "${sourceDir}/build/cmake/android-stub",
  "cacheVariables": { "POP_TRANSLATE": "STUB" }
}
```

- [ ] **Step 2: Gate the tree.** Wherever `CMakeLists.txt` writes `if(IOS)` to skip desktop-only tests and to build the app as a bundle, treat `ANDROID` the same for tests and build the app as `SHARED` named `recomp_app` (SDL3's Android glue loads `libmain.so` by default; set `OUTPUT_NAME main`).

- [ ] **Step 3: Configure and build the stub**

```bash
export ANDROID_NDK_HOME=$HOME/Library/Android/sdk/ndk/27.2.12479018
cd kit && cmake --preset android-stub && cmake --build --preset android-stub --target recomp_app
ls build/cmake/android-stub/host/libmain.so
```

Expected: the shared library links. Compile errors from `platform/os_posix.cpp` (e.g. `dlopen` of Vulkan: use `libvulkan.so`) are fixed inline with a `platform_tests` case where testable.

- [ ] **Step 4: Commit**

```bash
git add CMakePresets.json CMakeLists.txt host/CMakeLists.txt host/gpu/CMakeLists.txt platform/CMakeLists.txt platform/os_posix.cpp && git commit -m "Android: an NDK preset builds the host as libmain.so against static SDL3"
```

### Task 7.2: Gradle project template and `tools/build.py --target android`

**Files:**
- Create: `kit/platform/android/build.gradle.kts`, `kit/platform/android/settings.gradle.kts`, `kit/platform/android/app/build.gradle.kts.in`, `kit/platform/android/app/src/main/AndroidManifest.xml.in`, `kit/platform/android/app/src/main/java/dev/recompkit/RecompActivity.java`
- Modify: `kit/tools/build.py` (`TARGETS["android"] = ["recomp_app"]`, a `android_project()` step that renders the templates with `app_name`, `bundle_id` and the game's `id`, runs `gradlew assembleDebug`, and `adb install -r` + `adb shell am start` + `adb logcat` with `--console`)
- Test: `kit/tools/tests/test_build.py` (`test_android_templates_render`)

**Interfaces:**
- Produces: `tools/build.py --target android --console` from a game repository produces `build/android/app/build/outputs/apk/debug/app-debug.apk`, installs and launches it. `RecompActivity extends org.libsdl.app.SDLActivity` and overrides `getLibraries()` to return `{"main"}`; the manifest declares `android.hardware.vulkan.version` `0x401000` (1.1) required, `screenOrientation="landscape"`, and `requestLegacyExternalStorage="false"`.

- [ ] **Step 1: Write the failing test** (`android_project(tmp_path, cfg)` renders `applicationId "dev.recompkit.pharaoh"`-style values from the stub config):

```python
def test_android_templates_render(tmp_path):
    cfg = {"game": {"app_name": "StubRecomp", "bundle_id": "dev.recompkit.stub", "id": "stub"}}
    out = build.android_project(tmp_path, cfg, gen_dir=tmp_path / "gen")
    manifest = (out / "app/src/main/AndroidManifest.xml").read_text()
    assert 'package="dev.recompkit.stub"' in manifest
    assert "StubRecomp" in (out / "app/build.gradle.kts").read_text()
```

- [ ] **Step 2: Run to verify failure**, **Step 3: Write the templates** (SDL3's `android-project` layout: the SDL Java sources come from the FetchContent checkout at `build/_deps/sdl3-src/android-project/app/src/main/java/org/libsdl/app`; `settings.gradle.kts` includes them as a source directory), **Step 4: Build on the Mac**

```bash
.venv/bin/python tools/build.py --target android --stub 2>&1 | tail -5
```

Expected: an APK with `libmain.so` and the SDL activity. **Step 5: Commit**

```bash
cd kit && git add platform/android tools/build.py tools/tests/test_build.py && git commit -m "Android: a Gradle project around SDLActivity, built and installed by build.py"
```

### Task 7.3: Game data on the device, lifecycle, and the first Android boot

**Files:**
- Modify: `kit/host/sdl/main.cpp` (Android: `SDL_GetAndroidExternalStoragePath()` as the data root; on first launch with no `game/` there, show the kit's page overlay with the `adb push` instruction and the expected path), `kit/host/sdl/platform_ui_desktop.cpp` (or a new `platform_ui_android.cpp`: `platform_ui_process_exit` finishes the activity), `kit/host/game_path.cpp` (search `<external files>/game`)
- Modify: `kit/tools/build.py` (`--push-game` pushes `original/gog/app` minus `[bundle].exclude` with `adb push` to `/sdcard/Android/data/<bundle_id>/files/game`)
- Modify: game `README.md` ("Play on an Android tablet"), `docs/analysis.md`

- [ ] **Step 1: Implement the data path and the exit** (guard with `#ifdef __ANDROID__`; the host boundary test forbids Android APIs outside `platform/` and `host/sdl/`, so keep them there).

- [ ] **Step 2: Push the game and launch**

```bash
.venv/bin/python tools/build.py --target android --push-game --console 2>&1 | tee build/android-1.log | tail -30
```

Expected: `logcat` shows the seeding stamp check, the display mode, the main menu; music plays through SDL's audio (AAudio). Touch uses the same mapper as iOS (`input_touch.cpp` is SDL-generic); the keypad appears.

- [ ] **Step 3: Play** the first mission by touch; record frame rate (`RECOMP_FRAME_TIMINGS` via a `switches.txt` in the external files directory, mirroring the iOS mechanism, if `recomp_env_apply_file` is pointed there) and issues in the run log.

- [ ] **Step 4: Commit and land**

```bash
git -C kit add host tools && git -C kit commit -m "Android: game data from external storage, activity exit, first boot"
git add README.md docs/analysis.md CHANGELOG.md kit && git commit -m "The Android app boots and plays the first mission by touch"
```

Then land `pharaoh` on kit main as in Task 3.3 and re-pin.

---

## Phase 8: release state

### Task 8.1: Cinematics decision, exclusions, and the status page

**Files:**
- Modify: `README.md`, `docs/analysis.md`, `game.toml` `[bundle]`, `CHANGELOG.md`

- [ ] **Step 1: Decide the cinematics.** The stubs skip them. Record in `docs/analysis.md` the options (a Bink decoder is not available under a permissive licence; FFmpeg's `binkvideo` is LGPL and 140 MB of assets), and either exclude `BINKS/` from every bundle (saves 140 MB on iPad and Android) or keep it for a future decoder. Update `[bundle].exclude` and `test_bundle_exclusions_and_setup` accordingly.

- [ ] **Step 2: Per-platform status table in `README.md`**: macOS, iPad, Linux, Windows, Android, each with "plays the first mission", the build command, and the known issues from the run log.

- [ ] **Step 3: Final checks and commit**

```bash
.venv/bin/python tools/test.py && .venv/bin/python -m pytest -q tests && .venv/bin/python tools/build.py --stub && .venv/bin/python tools/build.py --stub --target ios
git add -A && git commit -m "Status: the port plays on every supported platform; cinematics skipped"
```

---

## Self-review notes

- **Spec coverage:** import gaps (Tasks 2.1 to 2.5), Miles sound (3.1, 3.2), Bink/Smacker (2.2), DirectDraw path (verified in 2.6, no kit change expected), translation gate (1.1 to 1.3), macOS (1.4, 2.6, 4.x), iOS (5.1), Linux and Windows (6.x, spec M4 packagers), Android (7.x, spec M4 and 4.6), save/profile (4.1), frame clock hook (4.2). Multiplayer: none in this game. Drive-letter music path: verified in Task 2.6 Step 1.
- **Names used across tasks:** `EXTRA_ENTRY_POINTS` (1.2), `imports_argc` (2.1, 2.2), `riff_parse_wave`/`RiffWave` (3.1), `Mp3Source` (3.2), `mss32_register`/`bink_register`/`mss32_frame_pump` (2.1, 2.2, 3.2), `package_desktop.stage` (6.2), `android_project` (7.2). Helper names marked "grep for the real one" (`add_entry`, `host_client_size`, `cursor_position`, `tick_count_ms`, `scratch_string`) are anchored to the neighbouring shim the executor copies from.
- **Unknowns that stop a task rather than being guessed:** the entry `ENTRY_4AB` (found in 1.1 before 1.2 uses it), menu coordinates (read from dumps in 2.6 before scripting), the Android NDK path and a Linux/Windows machine with the game (6.3, 7.x).
