# d2r-reimagined-mod
The source code for the Diablo II Mod Reimagined.

Found on nexus mods here: https://www.nexusmods.com/diablo2resurrected/mods/503

## Our Mission
Our mission is to provide a Diablo II experience that is both familiar and new. We aim to keep the core gameplay of Diablo II intact while adding new features and content to the game. We want to provide a fresh experience for players who have played Diablo II for years, while also providing a fun and engaging experience for new players.

Everything we do, regardless if that is the D2R Files themselves or any of the tooling we build, is open source. We believe that the community should have the ability to see and modify the code that runs the mod. We also believe that the community should have the ability to contribute to the mod and help shape its future.

Want to be apart of this mission? Join our Discord Server https://discord.gg/9zZkYrSA8C for more information on contributing and collaborating.

## Contributing
1) Fork the mod
2) Do your changes in your forked repository
3) Open up a pull request targeting the `next` branch.
4) Reach out to me on discord (collin.h) to discuss your changes.

## JSON source pilot

On this branch, unique items, treasure classes, item ratios, experience, and all eight translation catalogs are authored as individual JSON records under `source/`. Remaining tables and assets stay in `data/`. Standard and D2RLoader outputs are generated from the same source. The D2RLoader profile currently adds its metadata file; no table-value overrides are enabled yet.

Requires Node.js 22 or later, with no dependency installation:

```powershell
node scripts/build.mjs --all
node scripts/diff-builds.mjs
node scripts/check-strings.mjs --profile standard
node --test scripts/tests/*.test.mjs
```

Inspect `source/tables/uniqueitems/records/row-00000-the-gnasher.json` for an editable item. Full mod output is written to `build/standard/mods/Reimagined/` and `build/d2rl/mods/Reimagined/`. **Install from generated output; the repository's `data/` alone is no longer a complete mod.**

See [the source workflow](docs/source-workflow.md) for runtime overrides, compact translations, spreadsheet export/import, migration checks, and the limits of the current string measurements.

## Available Tools
This repository contains a number of tools that can be used to help develop the mod. These tools are located in the `scripts` directory.
The source workflow documents the active tools. Legacy flattened-string mutation scripts are disabled during the JSON pilot to prevent edits to generated data or accidental ID renumbering.

### Launcher
A beta launcher for this mod can be found here [https://github.com/D2R-Reimagined/reimagined-launcher](https://github.com/D2R-Reimagined/reimagined-launcher)
This can make your installation fast and easy and allow you to make your own edits to your Reimagined Playthrough
