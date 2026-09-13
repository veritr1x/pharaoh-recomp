# Changelog

## Unreleased

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
