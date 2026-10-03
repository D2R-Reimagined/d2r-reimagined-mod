# UnHoarder alert sounds

Filter01–Filter16 and their FLAC assets come from MindH1ve's official
[UnHoarder 1.1.0 release](https://github.com/Lukaszpg/d2rl-unhoarder/releases/tag/v1.1.0).
The upstream GPL-3.0 license is preserved here.

The 16 rows were appended to Reimagined's sounds.txt at indices 11992–12007.
All earlier rows are unchanged. The DLL is installed separately in
`mods/Reimagined/d2rloader/plugins/unhoarder.dll`; this directory documents the
mod data integration, not a bundled plugin release.

Official asset SHA-256:

- `unhoarder.dll`: `0f20fa8ff1080f349447a6cab16ddfaceca8f991381b34d63674f819f0e0c307`
- `unhoarder-1.1.0-data.zip`: `7f2e734f8bf005dbd9cb8b3178fbd2c4068368310d087cc0d58dc546e260d905`

The website's unlisted `/loot-filter` builder downloads schema-v3 filter.json.
Place that file beside the DLL. The plugin reloads saved changes; Ctrl+Shift+F9
also reloads manually. Actual ground labels, pickup filtering, automap icons and
sound playback still require in-game testing.
