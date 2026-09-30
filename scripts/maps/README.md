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
tileset uses. Every theme has a purpose-built arena (see Custom arenas
below); none clones a Labyrinth room any more.
Every map level is Act 5 regardless of tileset so
the Harrogath portal and town portals stay in one act.

### Where the portal lands

The red portal drops the player in a room that owns a warp tile whose Vis
slot carries a lvlwarp. With the arena stairs as the body's only live warp
that room was the arena doorway. Each theme therefore also names a
`body_entry` warp: the tileset's stairs-up (or trapdoor) piece, whose Vis
points at the body itself so it counts as live without opening a second way
into the arena or leaving a clickable warp with no destination. In game D2R
lands on the special room whose preset the maze routine assigned first (not
the first in the room list, which was wrong twice for the leaf tilesets), so
the entry slot per tileset is that room: the Prev room for
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
the template pins one (the pool rooms said 32x32).

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

Ashen Steppes' ruined bastion (`STEPPES`) stands on the mesa (LevelType 27).
No stock preset level uses the Mesa tiles, so the arena keeps level 165's row
and its slot-0 red portal (lvlwarp 83) and `arenas.LEVEL` switches the
LevelType and ambience; `arenas.PRESET` loads Floor, Brick_Walls and
Surf_Struct (Dt1Mask 265). The walls are the Plains of Despair ruins:
Brick_Walls main 13 with a ruined section (a 10-way model variation) and a
`wall_pillars01` per tile on all four sides, `wall_pillars_corner01` at the
corners, and `pillar02` on Surf_Struct column tiles for the ring. Hell
braziers mark the ring's corners; bonfires, impaled Damned, skull piles, hell
smoke and chained spikes fill the aisles, and the red portal stands in the
south corner.

Infernal Rift's hellforge (`INFERNAL`) is built in the fortress style of the
Infernal Pit / Pit of Acheron / Abaddon rooms (`act4/expansion`). Their walls
are Lava/Intwalls.dt1 main 22, already in level 165's Act 4 Lava tileset, so
the row stays as is apart from `arenas.PRESET` adding Intwalls to its
Dt1Mask (1631). Per tile: `wall01` at (+8.1, +3.2) yaw 180 on a north wall or
(+3.1, +8.2) yaw 270 on a west wall, with `pillar01_staged01` on every other
tile. Intwalls has no corner tile, so the back corner stacks both walls in two
wall layers (`Room.set_wall(..., layer=1)`). The ring's pillars are
`pillar02_blank` on Intwalls column tiles (12, 22, 1); Hell Brazier 4s mark
its corners, the court's floor is shattered and glowing with hell crystals at
its corners and floor braziers flanking the Warden, and skull pillars, wall
spikes, hellfires and debris fill the aisles. The red portal stands in the
south corner, as in the Steppes.

Corrupted Durance's council chamber (`DURANCE`) is built in the Durance of
Hate's tiles (LevelType 22; Travincal Walls.dt1 main 48 on Kurast's floor).
Durance of Hate 3 (102) is the template, so the player arrives by the Durance's
own stairs up (slot 2, lvlwarp 65), the stock Durance 2 -> 3 transition;
Durance stairs on that slot exist only as west-wall warp tiles, so they stand
in the west wall under `door_stairs_up01`. Walls alternate round-pillar tiles
(`round_pillar01` + `pillar_top01`) with wall tiles (`wall01` twice, the second
mirrored with scale z -1 so both faces are finished, plus `square_pillar01` and
wall spikes), with `pillar_top_corner01/02` at the corners, on all four sides.
Round pillars on Floors.dt1 column tiles (12, 46, 0) form the ring; floor
braziers mark its and the court's corners, torches line the back walls,
tortured corpses hang on them, and blood-soaked floors, severed limbs and gore
cover the chamber under Durance fog.

Fallen Travincal's High Council courtyard (`TRAVINCAL`) is a sunken stone court
walled by the terraces Travincal is built on: Kurast Terraces.dt1 main 31
(walk-blocking, not sight-blocking), added to level 148's Dt1Mask (53512) by
`arenas.PRESET`. Across the stock Kurast and Travincal presets the terrace
tiles carry `wall_elevation_stone01` + `wall_stone_buttress01` at (+7.5, +4.5)
/ (+7.5, +4.0) yaw 90 on a north edge, (+4.5, +7.5) / (+4.0, +7.5) yaw 180 on a
west edge, and `wall_stone_buttress_corner01` at the corners. Spiked stone
pillars crown the back terraces and ring the court on Travincal column tiles;
floor and jungle braziers, the Council's idols and offering bowls on gold
ornaments, stone trims, blood and footprints, and jungle growth under
Travincal fog, leaves and motes finish it. The arena keeps level 148's
slot-2 red portal (encoded as the old Mephisto-chamber arena did, a hidden
orientation 11 warp tile) in the south corner, and `arenas.LEVEL` gives it
Travincal's outdoor ambience (SoundEnv 25).

Sunscar Dunes' sun-scorched ruin (`DUNES`) is an open-air courtyard of the
Lost City in the Act 2 desert tiles (LevelType 16). It keeps level 138's row
and slot-2 red portal (lvlwarp 83) in the south corner; `arenas.LEVEL`
switches the LevelType and the desert ambience (SoundEnv 13), and
`arenas.PRESET` loads Town/Ground, Ruin/Ground, Ruin/Column and Village
(Dt1Mask 50397185). The walls are the ruins' sandstone: Village.dt1 main 48
(variants 15/16) carrying `wall01` (`act2_ruin_stone_walls`) at (+6.3, +2.4)
yaw 0 on a north wall and (+2.6, +6.7) yaw 90 on a west wall, on all four
sides. Village has no end pieces, so a model-less wall tile past the east wall
seals the south-east corner. Two `statue01` colossi stand mid-way along the
back walls on the Column.dt1 pieces the stock ruins lay under them (ruin2 and
ruin10 for the yaw 90 one, ruin9 for the yaw 3 one). Sandstone pillars
(`pillar_base01/mid01/top01`) on Column tiles (12, 36, 0) ring Tal Rasha's
seal (the Canyon of the Magi dais) under the Warden, with two Horadric tablets
on their own Column tiles. Tall braziers mark the ring's corners and tiki
torches line the back walls; dunes, palms, fallen columns, desert scrub,
bones, urns and jugs fill the aisles under sand ribbons and motes.

Forsaken Highlands' war camp (`HIGHLANDS`) is a hollow in the Act 1
wilderness (LevelType 2) where corrupted Rogues and the Fallen have made
camp. It keeps level 158's row, but returns by its slot-2 red portal
(lvlwarp 83) in the south corner instead of the Cathedral stairs the old
Labyrinth room used; `arenas.LEVEL` switches the LevelType and ambience
(SoundEnv 2) and `arenas.PRESET` loads Town/Floor, stonewall and Fallen
(Dt1Mask 65541). The walls are the wilderness borders' dry stone:
stonewall.dt1 main 2 sub 0 carrying the `act1_outdoors_stonewalls`
`r_wall01` at (+3.0, +4.5) on a north wall and `l_wall01` at (+4.0, +3.5) on a
west wall, on all four sides, with one more model past each run's end to
close the corners. The Stony Field cliffs share those basenames, so the kit
reads `bivouac` first. Fallen.dt1 main 14 supplies the camp exactly as the
stock `fallcmp*` rooms lay it out: skull totems ring the clearing, two tents
stand in the aisles (a prefab over three west-wall pieces), each with a
campfire. Gibbets mark the ring's corners, Fallen torches light the clearing
and the walls, and staked Rogues hang along the walls. Rogue corpses, the
Fallen's loot piles, corrupted spears, dead trees, boulders and highland
scrub fill the rest under ground fog.

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
