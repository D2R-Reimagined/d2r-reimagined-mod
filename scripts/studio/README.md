# Mod Studio project: layout, builds and scripts

The mod is a [Reimagined D2R Mod Studio](https://github.com/D2R-Reimagined/reimagined-d2r-mod-studio) project. The
game's excel tables and string catalogs are not kept as `.txt`/`.json` game files any more:

| Path | Holds |
|---|---|
| `source/tables/<name>.json` | one file per excel table. `base/` and top-level copies share one file while they are identical (`treasureclassex` has two, the banks differ). |
| `source/strings/<name>.json` | the `local/lng/strings` catalogs |
| `data/` | every other game file, at its game path (HD json, DS1, sprites, UI layouts...) |
| `compatibility/<profile>/` | what differs per build (see below) |
| `mod-project.json`, `modinfo.json` | project identity, the mod's modinfo |

Rows keep their order and every cell exactly; Mod Studio writes the same TXT bytes the
game has always read. Each row has a `sourceId` that profile rules refer to.

## Two builds from one source

| Profile | For | Deploys to | Differences |
|---|---|---|---|
| `d2rl` | D2RLoader (ladder, plugins) | `mods/Reimagined` | adds the mod's D2RLoader memory patches (`compatibility/d2rl/d2rloader/patches`) |
| `standard` | plain D2R, no loader | `mods/ReimaginedSoft` | own name and savepath (`ReimaginedSoft/`); exterior map themes switched off (`compatibility/standard/maps-soft/`: one rule set per table, written by the maps generator; Studio will not edit the cells they own) |

The D2RLoader build's plugins, `d2rloader/config/*`, `metadata.json` and the ladder's
`.DISABLE_DEBUG` marker still come from d2rl-plugins (`scripts/package-ladder-bundle.ps1`)
and the launcher, as before. Plain D2R lacks everything the loader and plugins add (game
rules in d2rloader.toml, the memory patches, every plugin fix), so the soft mod plays
like the mod without them.

## Day to day

- **Edit** tables and strings in Mod Studio (or its External editor), or with scripts.
- **Deploy** (replaces `scripts/copy-files.bat`):
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\studio\deploy.ps1                    # d2rl -> mods\Reimagined
  powershell -ExecutionPolicy Bypass -File scripts\studio\deploy.ps1 -Profile standard  # -> mods\ReimaginedSoft
  ```
  It runs the Mod Studio CLI build (`MOD_STUDIO_CLI`, or `..\d2r-mod-studio\src\ModStudio.Cli\bin\Release\net10.0\ModStudio.Cli.exe`).
- **Maps**: `python scripts/maps/generate_maps.py` writes the Studio tables directly (both
  banks) and refreshes the soft-mod rules; `--check` validates. Tests:
  `python -m unittest discover -p "test_*.py"` in `scripts/maps` and in `scripts/studio`.
- **Merging a branch that still has TXT files** (e.g. `next` before it is converted):
  ```powershell
  git merge --no-commit origin/next
  python scripts/studio/sync_from_txt.py --merge origin/next
  ```
  then keep the TXT/strings files deleted (`git rm` them), review and commit. Conflicting
  tables are written with conflict markers to `.studio/merge-conflicts/` and left alone.
  `--tree <data-root>` applies a whole native tree instead.

## Scripts

- `studio_tables.py`: read/write Studio tables and catalogs by game path, in native shapes
  (keeps row ids, splits/merges banks, writes Studio's exact JSON format).
- `deploy.ps1`, `sync_from_txt.py`: above.
- `test_studio_tables.py`, `test_sync_from_txt.py`: their tests.
