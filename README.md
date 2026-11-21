# d2r-reimagined-mod

> [!IMPORTANT]
> **Tables and strings are now edited with [Reimagined D2R Mod Studio](https://github.com/D2R-Reimagined/reimagined-d2r-mod-studio).**
> The excel tables (`data/global/excel/*.txt`) and string catalogs (`data/local/lng/strings/*.json`) are no longer kept as game files. They live in `source/tables` and `source/strings` as Mod Studio source, and Mod Studio builds the game files from them.
>
> - Open this repository's folder in Mod Studio to edit tables and strings, and to build or deploy the mod.
> - Don't add `.txt` tables or string `.json` files under `data/`: they are not part of the source any more, and a build ignores them.
> - Have a branch or pull request from before the change? Bring it over with `scripts/studio/sync_from_txt.py` (see [Merging a branch that still has TXT files](scripts/studio/README.md#day-to-day)), or ask on Discord and we'll convert it for you.

The source code for the Diablo II Mod Reimagined.

Found on nexus mods here: https://www.nexusmods.com/diablo2resurrected/mods/503

## Our Mission
Our mission is to provide a Diablo II experience that is both familiar and new. We aim to keep the core gameplay of Diablo II intact while adding new features and content to the game. We want to provide a fresh experience for players who have played Diablo II for years, while also providing a fun and engaging experience for new players.

Everything we do, regardless if that is the D2R Files themselves or any of the tooling we build, is open source. We believe that the community should have the ability to see and modify the code that runs the mod. We also believe that the community should have the ability to contribute to the mod and help shape its future.

Want to be apart of this mission? Join our Discord Server https://discord.gg/9zZkYrSA8C for more information on contributing and collaborating.

## Contributing
1) Fork the mod
2) Do your changes in your forked repository. Edit tables and strings with [Mod Studio](https://github.com/D2R-Reimagined/reimagined-d2r-mod-studio), not as `.txt`/`.json` files (see the note at the top).
3) Open up a pull request targeting the `next` branch.
4) Reach out to me on discord (collin.h) to discuss your changes.

## Available Tools
This repository contains a number of tools that can be used to help develop the mod. These tools are located in the `scripts` directory.
These tools include the ability to compare key entries for strings between two files, copying english names to other languages.

### Mod Studio project and the two builds
The tables and strings are a [Mod Studio](https://github.com/D2R-Reimagined/reimagined-d2r-mod-studio) project (`source/`), built into two deployments from one source: the D2RLoader build (`mods/Reimagined`) and a soft mod for plain D2R (`mods/ReimaginedSoft`). `scripts/studio/deploy.ps1` builds and installs either one. See [scripts/studio/README.md](scripts/studio/README.md).

### Launcher
A beta launcher for this mod can be found here [https://github.com/D2R-Reimagined/reimagined-launcher](https://github.com/D2R-Reimagined/reimagined-launcher)
This can make your installation fast and easy and allow you to make your own edits to your Reimagined Playthrough
