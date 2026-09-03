# JSON source pilot

This branch converts **uniqueitems**, **treasureclassex**, **itemratio**, **experience**, and **all eight translation catalogs** to editable JSON entries. Both runtime profiles currently generate the same gameplay and translations. No balance values or descriptions have been changed, and no files have been installed into the game.

The remaining TXT tables and game assets stay under `data/` during the pilot. They are copied into each generated mod. There is one editable source for each migrated file: do not recreate its old file under `data/`.

## Build and inspect

Use Node.js 22 or later. There are no npm dependencies and no install step.

```powershell
node scripts/build.mjs --all
node scripts/diff-builds.mjs
node scripts/check-strings.mjs --profile standard
node --test scripts/tests/*.test.mjs
```

The complete mod folders are:

```text
build/standard/mods/Reimagined/
build/d2rl/mods/Reimagined/
```

Each build has `build-manifest.json` and `string-budget.json` outside the install folder. `build/reports/profile-diff.json` lists differing files and the exact override/string rules responsible. Rebuild both profiles after edits before running the comparison; it rejects stale inputs or modified output files. Build folders are replaced on rebuild. Store spreadsheet work under `build/edit/`, which profile builds preserve.

Manual installation uses the generated `mods` folder. Never copy the repository's `data/` directly into the game now: it lacks the migrated files. Replace the previous mod installation rather than merging profiles, so removed files cannot linger; preserve your saves and personal settings separately. The build commands themselves do not install or launch anything.

## Edit a unique item

Open `source/tables/uniqueitems/records/row-00000-the-gnasher.json` for a real example:

```json
{
    "sourceId": "row-00000",
    "order": 0,
    "columnCount": 75,
    "fields": {
        "index": "The Gnasher",
        "*ID": "0",
        "lvl req": "5"
    }
}
```

This abbreviated example omits the item's other fields. Edit named fields in the real file. All TSV cell values are strings. An omitted field means an empty cell, which differs from `"0"`. Empty cells are omitted to keep records readable; the compiler restores all columns and trailing empty cells.

Keep the `sourceId`, `order`, filename prefix and existing `*ID` stable. The filename suffix is a search aid; it need not change when an item is renamed. The compiler preserves physical rows, including separators. Physical row slots are not necessarily the game's item IDs.

`schema.json` defines headers, output encoding, newline style, protected original row identities, and output paths. The original main and `excel/base` unique-item files are identical on this branch; the same records generate both paths. `itemratio` and `experience` also share records across their identical banks.

The two original treasure-class banks are not identical: the main bank has 1,547 rows and `excel/base` has 1,552 rows with a different early row sequence. They are therefore modeled as `source/tables/treasureclassex` and `source/tables/treasureclassex-base`. This preserves each bank exactly instead of incorrectly consolidating them.

The original `*ID` value `1439` appears on both Chaos Onyx Grabber and The Ossuary Almanac. The schema records those exact existing rows as a legacy exception. This migration preserves it; adding a new duplicate fails. The comment-column ID is not a substitute for preserving actual row placement.

For a new item, append the next source row slot and use a new unused `*ID`; do not insert or renumber existing rows. Copying an existing JSON record requires changing its source ID, order, filename prefix, and game ID. Keep the table's structural rules in mind. Deleting original rows or altering protected IDs fails the build. An intentional identity migration requires explicit review of `protectedRows`/`identitySha256`, not simply clearing the guard.

## Author a runtime override

Create a JSON file beneath `compatibility/d2rl/`, then list its relative path in that profile's `tableOverrides`. An example lives at `docs/examples/d2rl-gnasher.json`; it is **not enabled**.

```json
{
    "table": "uniqueitems",
    "record": "row-00000",
    "reason": "Example only: demonstrate a D2RLoader-specific value",
    "changes": {
        "max4": { "expect": "100", "value": "110" }
    }
}
```

An override applies to both output banks by default. Supply `targets` containing exact paths from the table schema to select a single bank. It changes only the named fields. If the shared value changes, its `expect` check fails instead of silently preserving an outdated exception. Competing overrides for the same cell and changes to identity columns fail.

The available table names are `uniqueitems`, `treasureclassex`, `treasureclassex-base`, `itemratio`, and `experience`. Treasure-class overrides affect one bank because the banks have separate source records. Item-ratio and experience overrides affect both identical banks unless a rule supplies a single exact `targets` path.

Disabled examples for the newly migrated tables live under `docs/examples/`. Copy a reviewed rule beneath `compatibility/d2rl/tables/` and add its relative path to `compatibility/d2rl/profile.json` to enable it. The D2RLoader build manifest and profile-diff report will then identify every changed cell and its reason.

## Edit translations

Each file under `source/strings/<catalog>/records/` holds its existing numeric `id`, exact `Key`, output order, and all 13 locale values under `translations`. Keep these identities stable. Original keys are case-sensitive. The catalog schema determines its output JSON filename.

Add only the compact locale values needed for Standard:

```json
"standardTranslations": {
    "enUS": "An authored shorter description."
}
```

Standard inherits the full value for any locale without an alternative. D2RLoader uses the full values. Neither profile removes keys or renumbers IDs.

After reviewing the compact wording and its formatting, record the review:

```powershell
node scripts/review-strings.mjs --file source/strings/item-names/records/<filename>.json
```

The command records hashes of the reviewed full values and checks placeholders. A later edit to a full value makes its compact alternative require review again. Placeholder checks cannot prove equivalent meaning or correct color/grammar controls; those still require human review. Build validates compact alternatives even when building D2RLoader, so broken source cannot hide in the other profile.

No compact alternatives have been applied to current content. Choose those after reviewing the generated measurements.

## Spreadsheet editing

```powershell
node scripts/export-tsv.mjs --table treasureclassex --out build/edit/treasureclassex.txt
# Edit the TXT using a TSV editor; keep its .source.json snapshot alongside it.
node scripts/import-tsv.mjs --file build/edit/uniques.txt
```

Export operates on shared source, before runtime overrides. Import compares exported values, edited values, and current source. Independent newer changes are preserved. A competing edit reports a conflict before any source file is changed. It does not infer row additions, deletions, or reordering; those are rejected. Existing export files are never overwritten by the exporter.

## Assets specific to a runtime

`assetOverrides` in a profile contains entries like:

```json
{
    "scope": "data",
    "source": "assets/example.json",
    "target": "global/ui/layouts/example.json",
    "expectSha256": null,
    "reason": "Explain why this runtime needs the asset"
}
```

Paths in `source` are relative to the profile directory. `target` is relative to the generated `data/` directory. `null` expects an absent target; replacing an existing asset requires its current SHA-256 hash. Asset replacements cannot bypass generated table/string rules.

For D2RLoader-specific metadata/plugin/patch assets, use `"scope": "mod"` and a target such as `d2rloader/patches/example.json`. These files go beside `Reimagined.mpq`, not inside its data directory. This scope is accepted only by the D2RLoader profile and rejects runtime `config/` and `logs/` directories. No loader DLLs or patches are included in this pilot.

The active D2RLoader profile demonstrates this with `compatibility/d2rl/assets/d2rloader/metadata.json`. It uses the exact JSON value `"${mod.version}"`; the build substitutes the root `modinfo.json` version and validates the emitted metadata shape. This prevents release version drift while leaving the required D2RLoader version explicit in the compatibility source. JSON templates accept only known, complete-string values rather than arbitrary expression evaluation.

## What the measurements establish

The report counts selected mod records, key bytes, and per-locale UTF-8/UTF-16LE text bytes including terminators, plus the largest text entries. The encoding calculations are alternatives, not allocations to add together.

Runtime capacity, usage percentage, and remaining headroom are deliberately `null`. Base-game/loader strings, resource fallback, duplicate allocation, and native pool capacities have not been calibrated. The pilot does not certify stock-runtime safety or automatically prune features/keys. Reference-aware feature removal, calibrated budget gates, and release publishing can follow once this source workflow is accepted.

## Migration verification

`source/migration.json` records the original checkout's byte and semantic hashes. The original tables regenerate byte-for-byte; every string record, ID, key, order, and locale value is preserved. Some string JSON files are reformatted with consistent property ordering/indentation.

```powershell
node scripts/build.mjs --all --verify-migration
```

This audit command checks the initial conversion and is expected to stop matching after intentional content edits. Checkout line-ending conversion can also affect byte hashes. Regular builds/tests do not require the original content hashes to stay fixed.

`migrate-source.mjs` is the original one-time importer used to start this pilot. It refuses to overwrite `source/` and is retained for provenance; it is not a generic converter for the remaining tables. Each later conversion is validated against hashes in `source/migration.json` before its old `data/` copy is removed.

The old ID-renumbering and flattened-string mutation utilities now stop with an explanation. Edit source entries directly. `copy-files.bat` builds the chosen profile and prints its output path instead of copying an incomplete source tree. The bundled lint configuration targets the generated Standard tables; build Standard before using it.
