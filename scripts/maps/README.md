# Mapping generation and validation

The 0.3.0 expansion generates the affix catalog and 360 population/reward profiles through `expansion.py`. New `x*` item codes share existing map levels while preserving old `m*` rolls. Drops and cube upgrades/rerolls produce the new codes; both versions activate normally. The first seven new concepts exclude Fortified and on-death mechanics. Interactive events and new themes remain pending native runtime work.

Version 0.4.0 adds `treasure.py`: twelve tier-scaled Jewel Hoarder/Amulet Collector rows, isolated MonProp/MonStats2 identities, names, HD bindings, and two six-item treasure classes. The plugin replaces one native ordinary group with one carrier; these rows never enter population, summon, or minion pools. The Collector uses Rare=1024 with normal set/unique opportunities, as requested. Only carrier corpse selection/revival is disabled.

The test default is 100% in `maps_config.py` and the plugin's `maps.toml`; `treasure_chance_percent` is configurable from 0 to 100. Lower the shipped setting and generated fallback default to 8 before release. This is one decision per newly cube-prepared map, including legacy items, without changing any affix rolls. Native placement and drops require in-game acceptance with the matching DLL/data bundle.

After regeneration, run `python scripts/maps/test_maps.py` and `python scripts/maps/generate_maps.py --check`, then rebuild/test the maps plugin with its matching generated header. This validates local data and code; native population selection, combat properties, and drops still need a fresh in-game test.

Edit `maps_config.py`, `endgame.py`, `boss_rooms.py` or `presentation.py`, then run from the mod root:

```
python scripts/maps/generate_maps.py
python scripts/maps/generate_maps.py --check
python -m unittest discover -s scripts/maps -p test_maps.py -v
```

The generator updates both Excel banks, preserving their different treasure
classes, and emits the matching C++ header into the sibling `d2rl-plugins`
checkout. `--check` compares every generated table, bank copy, localization,
boss DS1 and plugin header without writing. Test recipes default to disabled;
set `TEST_RECIPES` locally when needed, then regenerate before release.

## Themes and layouts

Each theme in `maps_config.py` names a maze body template, the Vis slot(s)
and lvlwarp its tileset uses for stairs down, a preset arena template, the
arena DS1 to clone and the warp tile the arena answers to. Bodies and arenas
no longer need to be neighbours in the Forsaken Labyrinth; the generator
links them itself and refuses a slot/warp pair that no stock maze of that
tileset uses. Current themes: Sandswept Tomb (Maggot Lair maze,
purpose-built tomb sanctum), Corrupted Durance (Durance of Hate maze, Mephisto arena),
Forsaken Catacombs (Catacombs maze, purpose-built ossuary chapel), Frozen Depths (ice-cave maze, purpose-built
glacier hall) and Worldstone Keep (Baal Temple maze, purpose-built throne hall). Every map level is Act 5 regardless of tileset so
the Harrogath portal and town portals stay in one act.

### Where the portal lands

The red portal drops the player in the first room of the level's room list
that owns a warp tile whose Vis slot carries a lvlwarp (D2MOO
`DrlgDrlgWarp.cpp`, `sub_6FD788D0`, reached through
`DUNGEON_FindActSpawnLocation`). With the arena stairs as the body's only
live warp that room was the arena doorway. Each theme therefore also names a
`body_entry` warp: the tileset's stairs-up (or trapdoor) piece, whose Vis
points at the body itself so it counts as live without opening a second way
into the arena or leaving a clickable warp with no destination. In-game D2R
lands on the special room whose preset the maze routine assigned first (the
1.10 list order in D2MOO predicted otherwise for the leaf tilesets and was
wrong twice), so the entry slot per tileset is that room: the Prev room for
Baal Temple, Catacombs, Flayer Dungeon and Ice Caves, the Next room for the
Maggot Lair. Stock, the Lair's Next room is a trapdoor down, so players
arrived at a way down and reached the Warden through stairs up. Sandswept
therefore sets `body_presets`: the plugin's preset-construction hook builds
each body's Next room from the Prev DS1 (stairs up, slot 0, the entry) and its
Prev room from the Next DS1 (trapdoor, slot 1, into the arena). The pairs are
validated as identical apart from their files; campaign Lair levels are
untouched. Without the hook the body still works, arriving by the trapdoor.
Baal Temple and Catacombs make Prev the origin room at the level centre, a
real distance from the leaf that holds the arena stairs; the other three give
two random leaves. Corrupted Durance also gets `body_rooms` because the
four-room Flayer Dungeon template could not put any distance between the two.
The self-linked entry stairs are expected to do nothing when clicked.

### Custom arenas

`custom:<name>` arenas are built by `arenas.py` instead of cloned: one layout
emits both the DS1 (floor, walls, collision, objects, return warp, Warden
spot) and its HD scene, so the two cannot disagree. The scene is made only of
entities cloned from the tileset's stock HD scenes (walls, low front walls,
pillars, statues, wall-dressing and pavement prefabs, terrain stamps, FX),
repositioned on the DS1 grid: one tile is 10 HD units, tile (x, y) spanning HD
x 10x..10x+10 and z 10y..10y+10. Every placement offset was measured from the
stock rooms against their DS1s. The floor is a stock flat plane (the
10x10-quad grid of Palace `celSE3`, all of 170x170) scaled over the room;
Tomb floors are textured by the biome and stamps, not by the mesh or legacy
floor tiles. A room's own terrain only covers its walkable floor (`tombnsew`'s
is a cross), which left the arena's corners without ground in game, so the
builder rejects any terrain whose mesh is not a full flat square. The level keeps the `arena_template` row
(LevelType, Dt1Mask, return warp) but takes its size from the room.

Sandswept Tomb's sanctum is a 20x20 Tomb hall (DS1 24x24; first tried at 26x26): eight pillars ring
an open, paved court where the Warden waits under a ceiling light shaft,
ritual candles at the court corners and tall braziers at the ring's open
corners. Wall torches, pharaoh and priestess statues, alcoves, pots and a
grave-goods corner line the two back walls; sand drifts, bones, breakable
urns and two lootable skeletons fill the aisles. The player arrives by the
same slot-2 red portal as the Labyrinth rooms (lvlwarp 83) in the south
corner, a diagonal walk from the court. The layout and its seed live in
`SANDSWEPT`. Its south and east walls are full-height rock like the back
walls (low fences left the room open to the void), and plain segments stand
behind the torch and alcove prefabs, which otherwise leave gaps in game.

Frozen Depths' glacier hall (`FROZEN`) has the same 20x20 footprint in the
Ice Caves tileset. Ice wall pieces are ~20 units long, pivot at their
east/south end on the wall line with yaw 0 (direction lives in the model:
`*01` along z, `*02`/`*03` along x) and are placed one per tile with rock
columns at the far corners; all four sides are full walls. Ice pillars on
column tiles ring a frozen pool of cracked-ice stamps where the Warden waits
among frozen dead and ice craters; ice braziers mark the ring's corners,
ice-cave torches line the back walls, and snow drifts, remains, jars and two
lootable frozen barbarians fill the aisles. The player arrives by the Ice
Caves stairs up (two slot-0 warp tiles under `wall_doorway01`, with the stock
timber dressing) in the north wall. The ice floor texture follows the floor
tiles' tile masks, so the room uses the plain base floor and gets its
variation from stamps. A custom arena's `lvlprest` size follows the room when
the template pins one (the pool rooms said 32x32). The remaining themes still
clone Labyrinth rooms.

Worldstone Keep's throne hall (`WORLDSTONE`) uses the Keep's own tiles
(LevelType 34). Its kit is tile-based like the tomb's: back-wall variants
alternate between a `pillar01a` (even) and a `wall01a` panel with a trimmed
pillar (odd), the back corner is `pillar_corner_wtrim`, and all four sides get
the back recipes. The Throne of Destruction row (131) is the template, so the
player arrives by the Baal Temple stairs up (slot 0, lvlwarp 81, `stairs_up01`
over two warp tiles), the same transition the stock Keep makes. `arenas.PRESET`
widens its Dt1Mask to Walls.dt1 + Floor.dt1 and `arenas.LEVEL` keeps automap
layer 78 so the arena does not share the real Throne room's saved map. A ring
of Keep pillars with Baal braziers at its corners surrounds a court where floor
cracks spread from the Warden and Worldstone crystals erupt at the corners;
torches stand on the back-wall pillars, and fallen bodies, rubble and hell
spikes fill the aisles.

Forsaken Catacombs' ossuary chapel (`CATACOMBS`) uses the Catacombs' tiles
(LevelType 10), whose single full wall style walls every side in legacy too.
Wall panels sit 2.5 units in from the wall line (`wall01`/painting/cabinet
turn 90 on a north wall and 180 on a west wall, `wall_plain` 270/0), and
`pillar01` + cap mark corners, run ends and column tiles. Catacombs 4 (37) is
the template: slot 0 = Catacombs Up (lvlwarp 17, `stairs02` + `pf_stairs01`
on the second of two warp tiles), the stock Catacombs 3 -> 4 transition, with
its Dt1Mask (57) already covering walls, stairs and floor; `arenas.LEVEL`
keeps automap layer 0 rather than Andariel's. Instead of a pillar ring, two
rows of pillars form a nave from the stairs west to a bone throne on the west
wall, arranged as in Andariel's lair (throne on the seam, bone banners either
side) and turned to face east; the Warden waits before it among candles,
braziers, a blood bath and gore. Torches stand between the nave pillars,
bubbling blood pools lie in the nave and staked Rogue corpses in the aisles.

`stock:` arena paths refer to unmodified D2R files. The generator copies each
one it uses from the extracted game data (`STOCK_DATA`, or `D2R_STOCK_DATA`)
into `scripts/maps/stock/`, which is committed so regeneration does not need
the extracted data. An arena DS1 must contain a monster record; the Warden
replaces the one nearest the room centre.

The generator emits `data/hd/env/preset/maps/<code>_boss.json` next to every
cloned `Maps/<code>_boss.ds1`. D2R resolves the HD scene by DS1 path, and the
scene JSON only references stock terrain assets by absolute path, so the
source arena's JSON is copied verbatim. The deploy script ships these.

Wardens are superuniques (`rmap_<code>_warden`, the monpreset Place the arena
DS1 points at) whose class is the `rmap_<code>_boss` monstats row. They take
their combat kit from `WARDENS` in `maps_config.py`: an `aura` entry in slot 4
and `att-skill`/`gethit-skill` procs in slots 5-6 of a dedicated
`rmap_<code>_boss` monprop row (slot 1 is the plugin's combat-MF aura, slots
2-3 are left free for its rolled affix auras), an `El1` melee element, an
escort from the theme's `MAP_MONSTERS` sized by the superunique's
MinGrp/MaxGrp, per-tier health from `WARDEN_HP_RATIO`, zero regeneration and
a 75 resistance cap. Levels and escort counts scale per tier. The generated
header exports `WardenMonProps[]` beside `MapMonProps[]`; the plugin must be
rebuilt with it. Two things were confirmed live and drove this shape: a
monstats `minion1/minion2` pair never spawns for a DS1-preset monster, and a
skill-slot aura in mode `NU` does not activate on these AIs.

`presentation.py` also generates the HD monster lookup entries for every map-owned monster ID, including Wardens and late-Hell drop variants. Wardens bind to `rmap_warden_<model>.json`, a copy of their archetype's stock HD model scaled by `WARDEN_MODEL_SCALE` at the root. The lookup is included in `--check` and the deployment script.

Approved folded-parchment sprites use Roman numerals I–VI at the bottom right. Sources and exact image-generation prompts are in `art/v4/`; `preview.html` displays converted art at inventory sizes. Rebuild using `python scripts/maps/build_sprites.py --source scripts/maps/art/v4 --neutral-matte`. The explicit matte option converts the generated neutral preview background into alpha; transparent inputs need no option. Both 98px and 49px RGBA-v31 sprites are generated. `presentation.py` binds all 30 map codes and supplies a shipped charm ground-model fallback. The deploy script includes these 19 HD artifacts. Legacy inventory artwork remains inherited from the small charm.

The mapping implementation and engine limitations are documented in
`d2rl-plugins/plugins/maps/README.md`. Labyrinth monsters, skills, property rows,
treasure classes and source DS1s are preserved. Six late-Act-5 level populations
use separate entry-drop monster variants; their non-Hell treasure classes stay
unchanged. Mapping combat populations and Wardens have independent rows.

## September 5 test build

- Generator output equality check passed for both banks and all 30 boss rooms.
- Six Python contract tests passed.
- C++ suite passed: 60,000 rolls, all affixes, family exclusions, compiled-layout
  and revision rejection, effect application/restoration, consumed-map and
  town/warden state, visited-level protection, and 128 tooltip capacities.
- Release MSVC DLL build passed without compiler warnings.
- Original monster, skill, state, property, treasure-class and preset rows were
  compared against Git HEAD and preserved in both banks. Original level rows
  were preserved apart from the six intended entry-population substitutions.
- 66 mapping artifacts installed and hash-verified in the local D2R Reimagined
  installation using `d2rl-plugins/scripts/deploy-maps-test.ps1 -Apply`.
- Original installation files, Trangsgender save files and shared stashes are
  backed up under `d2rl-plugins/build/maps-test-backup/20260905-095737`.

**Live testing is incomplete.** Computer-use launch approval timed out, and no
gameplay was performed. The existing loader settings have `monsterNoDamage` and
`manaCheat` enabled; those must be off for a meaningful difficulty benchmark.
The character selected by the user is stored as `Trangsgender.d2s` in the
`ReimaginedThree` save directory. No character data was changed by this task.

Prioritize runtime calibration, penalty/MF state application and expiration,
native auras, Warden placement/drop bundles, and all body/warden return warps.
Treat the installed files as a test build until these checks pass.

Rare-capable map quality now matches rings and amulets: Magic=1, Rare=1, Normal=0 in both banks. The former Normal=1 setting was incorrect, and subsequently clearing Magic as well also diverged from working misc items. The regression compares these flags against both ring and amulet rows. Generated maps have no inherited charm automagic. Native spawn tests use the observed letter option typ=r, not numeric typ=6. Live creation still needs confirmation.

Map tiers 1-6 use area levels 100, 101, 102, 103, 104 and 105 in both map bodies and Warden arenas. Base populations, affix variants, Wardens and treasure carriers use matching tier levels in both data banks. Existing tier multipliers remain; the higher monster levels also use the existing higher-level MonLvl stats. Shared MonLvl rows and Labyrinth levels are unchanged.
