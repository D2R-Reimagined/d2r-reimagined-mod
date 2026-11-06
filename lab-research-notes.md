# Forsaken Labyrinth: research notes (2026-10-15)

These are investigation notes only; nothing in the repo has been changed.

"Level N" means `Forsaken Labyrinth NN` in `levels.txt`, so level 3 is Id 141 and level 6 is Id 144.

**Sources.** Repo data (levels, lvlprest, lvlwarp, automap, the DS1s in `data/global/tiles/labyrinth`, and the HD presets in `data/hd/env/preset/labyrinth`) plus D2MOO, the 1.10f decompilation.

**Confidence tags.** **[C]** means confirmed in engine source or repo data. **[I]** means inferred; D2R could differ from 1.10.

---

## Update 2026-10-16: level 4 automap still has no exit markers

This update is based on the latest pull: automap rows from 3f4264d5, and `towne1.ds1` reworked in 9092c7fb.

### What's fine

- **The automap rows are correct.** "1 Courtyard" `wre` Style 0 and Style 1, Seq 0 → cel 30. They are inside the Courtyard block, tab-separated, with CRLF line endings.
  - The first-match lookup (`DATATBLS_GetAutomapCellId`) finds them [C].
- **The exit tiles do resolve to real DT1 tiles.** Every room also loads `Act1/Barracks/Warp.dt1`, plus Blank and InvisWal, on top of the `Dt1Mask` files (`DRLGROOMTILE_LoadDT1FilesForRoom`) [C].
  - `Warp.dt1` contains invisible, non-blocking `wre` main0 sub0 and main1 sub0 tiles. So level 4's markers get a real tile.
  - (My earlier worry about "missing tiles" was wrong: courtyard `Dt1Mask 127` doesn't need to cover it.)

### What's different between level 3 and level 4

Level 4's exit markers are **stacked on top of an ordinary wall tile**:

| DS1 | Cell | Layer 0 | Layer 1 |
|---|---|---|---|
| `courtn1.ds1` | (1,22) | outer-wall `wr` (ori2 main4 sub1) | exit marker (ori11 main0) |
| `courtn1.ds1` | (53,22) | outer-wall `wr` (ori2 main4 sub1) | exit marker (ori11 main1) |
| `courtn2.ds1` | (1,22) | outer-wall `wr` | exit marker (mirrored) |
| `courtn2.ds1` | (53,22) | outer-wall `wr` | exit marker (mirrored) |

After the 9092c7fb rework, level 3's markers, (50,12) and (27,28), sit on cells with **no other wall tile**. That's when level 3 started working with the same kind of rows.

Across every lab DS1, every exit on a cell by itself is a stair exit, the kind that shows the marker:

- cathy3
- labyrinth05
- dungrm slot 1
- nihl slot 0
- labyrinth00

Every marker stacked on a wall is one of these:

- level 4
- the dungrm back exits
- harem2 entry
- heart
- mephcomp
- nihl forward
- labyrinth10 slot 2

[I] The mechanism is likely that the client automap keeps one wall cell per tile position, so the layer-0 `wr` wall cell wins and the exit cell is never drawn. The D2Client automap code isn't in D2MOO, so this is inferred from that correlation. Level 4 is the cleanest test, because rows and tiles are both present and only the stacking differs.

### Fix (level 4)

In **both** `courtn1.ds1` and `courtn2.ds1`, make each exit marker the only wall tile in its cell.

- **Recommended:** move the marker from wall layer 1 to wall layer 0 at the same cell, replacing the `wr` outwall piece there.
  - This is the same pattern as vanilla stairs, which replace a wall segment.
  - Keeping the same cell keeps the lvlwarp 15 click box aligned with the HD `stairs01` model.
  - In SD, that one wall piece's art disappears. In HD the json model covers it.
  - There is no floor north of y=22, so losing the wall's collision shouldn't open a path. Test anyway.
- **Alternative:** move the marker one tile into the room, to (1,23) and (53,23), which are floor-only cells.
  - This shifts the click box by one tile relative to the HD stairs.
  - The lvlwarp offsets would then need re-tuning.

**Keep:** the "1 Courtyard" `wre` rows.

**Cleanup:**

- 3f4264d5 also appended a blank, tab-only row to the end of `automap.txt` and `base/automap.txt`. Remove it.
- The "1 Monestary" `wrd` rows from 8353f1b5 are unrelated to the lab and can go.

### Same rule likely affects other marker-only exits

These use lvlwarp 83 and are stacked on walls:

- level 7 / level 9 back exits (dungrm)
- level 10 (both)
- level 14 forward
- level 15 entry
- level 25
- level 00

Several of them also have no matching automap row yet. If those need markers, they need both:

1. Move the marker off the wall onto its own cell.
2. Add a `wre`/`wle` row for the level type, e.g. "3 Dungeon" `wle` Style 0, "5 Temple" `wle` Style 1.

---

## 1. Level 3 (Id 141): no monsters

**Root cause [C].** Population is gated per difficulty:

- Density comes from `MonDen` (Normal), `MonDen(N)` (Nightmare) and `MonDen(H)` (Hell). If it is 0, nothing spawns.
- The spawn list is `mon1..25` on **Normal only**. Nightmare and Hell use `nmon1..25`. `umon` is only used on Normal, to pick champions and uniques.

What 141 looks like now:

- `MonDen=0`, `MonDen(N)=0`, `MonDen(H)=600`.
- `mon*`, `nmon*` and `umon*` are **all empty**. The list was cleared at some point around 33cc3b99 → 22f053f3.

The older attempt could never have worked either. It had `mon1=labcow`, `mon2=chargingbovine`, empty `nmon*`, and density only in `MonDen(H)=800`. So Normal and Nightmare had no density, and Hell had an empty list.

`labcow` and `chargingbovine` are both `isSpawn=1`, so they are not the problem.

**Why wanderers still show up [C/I].** Wandering monsters (`MonWndr=1`) don't use the level list at all. They come from `actinfo.txt` (the Act 5 wandering columns) plus `wanderingmon.txt` (monsor, monbar, …), and only spawn in rooms with no player in them.

**The town DS1 is not the blocker [C].** There is no "town" flag in DS1/DT1. Town-ness is hardcoded to level ids 1, 40, 75, 103 and 109. `lvlprest` row "Labyrinth 03" has `Populate=1`, which is fine.

**Fix**
1. Fix `Position` first (section 2). Once rooms actually populate, every group spawn calls the spawn-location lookup that crashes [I].
2. Fill `nmon1..` with `isSpawn=1` monsters. Also fill `mon1..` and `umon1..` if Normal matters.
3. `NumMon=3` means at most 3 types. Slots are counted up to the first empty one.
4. Keep `MonDen(H)` > 0.
5. Monster level in expansion comes from `MonLvlEx*` (currently 101). `monlvl.txt` goes to 116, so that's fine.

## 2. Debug-teleporting to level 3 crashes

**Root cause [C].** 141 has `Position=1`. With `Position=1`, any arrival that isn't through a warp tile works like this:

- It uses `DUNGEON_FindActSpawnLocation` (`DrlgDrlgWarp.cpp`). That covers debug level-jump, waypoint, town start and link portals.
- That function picks a position-marker tile from the DS1. Markers are special tiles with orientation 10/11 and main index 30–33.
- `towne1.ds1` has **no main-30 marker**, only the two warp tiles (ori11 main0, ori10 main1).
- So the lookup returns (0,0), the room lookup returns NULL, and the game dereferences NULL in `DRLGACTIVATE_InitializeRoomEx`.

Walking in through the warp uses a different path (`DRLGWARP_GetDestinationRoom`), which is why normal play works.

For comparison:

- `duriel.ds1` and `fortress.ds1` have a 10/30/11 marker.
- No other lab level uses `Position=1`.
- Vanilla only uses `Position=1` on towns and fixed-arrival levels (Tristram, Duriel's Lair, Arcane, Harrogath, …).

**Fix:** set `Position=0` on 141. Lab 04 already uses 0.

The alternative is to keep `Position=1` and add ori10, main 30 marker tiles to `TownE1.ds1`:
- sub 0 for the default/waypoint arrival.
- sub 11 for the portal/scripted arrival.

**Side note on `Portal` [C/I].** `Portal=1` gives the level one bit in a 32-bit portal-flag mask.

- 34 levels now have `Portal=1`. 1.10 asserts a maximum of 32, and the bit shift overflows for the last ones (RMAP highlands T6 / T6 boss).
- D2R may have widened this; that is unverified. Worth trimming, since `Portal` does nothing for arrival.

## 3. Automap doesn't mark the exit on level 3 and level 4

**How exits get drawn [C].**

- An exit is a DS1 special tile: orientation 10 = `wle`, 11 = `wre`, with main = the Vis/Warp slot and sub = 0/1.
- The automap looks the tile up in `automap.txt` by (level-type name, TileName, Style = main, Seq = sub).
- Dungeon types map their `wre`/`wle` rows to cels 30–33 (WRE A/B, WLE A/B). That is the stairs/exit glyph you see on other levels.

**Why 141 and 142 have none [C].**

- 141 is LevelType 1 → automap block "1 Town". 142 is LevelType 6 → "1 Courtyard".
- Neither block has any `wre` or `wle` rows, because in vanilla those areas exit through open edges and doors, not warp tiles.
- So the exit tile finds no cell and nothing is drawn.

The 2026-10-13 attempt (8353f1b5) added `wrd` rows to **"1 Monestary"**. That is both the wrong level type and the wrong tile type: `wrd` is a door, not an exit.

**Tiles that need rows**

| Level | DS1 | Tile | Slot |
|---|---|---|---|
| 141 | `towne1.ds1` | ori11 (`wre`) main0 sub0 | back to 140 |
| 141 | `towne1.ds1` | ori10 (`wle`) main1 sub0 | forward to 142 |
| 142 | `courtn1/2.ds1` | ori11 (`wre`) main0 sub0 | — |
| 142 | `courtn1/2.ds1` | ori11 (`wre`) main1 sub0 | — |

**Fix**

1. Add these rows **inside** the existing "1 Town" block. Rows must stay contiguous per LevelName, because the loader keeps one start/end range per type.
   ```
   1 Town	wre	0	0	0	WRE A	30 ...
   1 Town	wle	1	0	0	WLE A	32 ...
   ```
2. Add these rows inside the "1 Courtyard" block:
   ```
   1 Courtyard	wre	0	0	0	WRE A	30 ...
   1 Courtyard	wre	1	0	0	WRE A	30 ...
   ```
3. Widen Start/EndSequence if a DS1 uses sub 1 as well. Mirror the edit into `base/automap.txt`.

[I] We assume D2R still drives the automap from `automap.txt` and only reskins it; no HD JSON for it was found. Test with one row first.

**Related:**

- lvlwarp 83 ("Act 5 Town to Forsaken Labyrinth", used by levels 3, 7, 9, 10, 14, 15, 20, 25, 00) has `LitVersion=0`. Those exits therefore never get the in-world mouse-over highlight either.
- Level 3 and level 4 (and level 20, plus the RMAP catacomb-boss and highlands levels) all share automap `Layer=0`. Layer only controls client-side automap save grouping, so it is not the cause here. But non-contiguous levels sharing a layer can bleed explored automap into each other. Consider giving each lab level its own layer.

## 4. Exit is sometimes up-stairs, sometimes down-stairs

There are two separate causes, both confirmed in data [C].

### 4a. Act 3 Dungeon maze levels (level 6 = 144, level 8 = 146) are wired backwards

Compare to vanilla Act 3 Dungeon (Ids 86–89). There, `Vis0` is the **deeper** level with Warp 56 (Dungeon Down), and `Vis1` is the way **up** with Warp 55 (Dungeon Up).

| Level | Vis0 / Warp0 | Vis1 / Warp1 |
|---|---|---|
| vanilla 86 | 87 (deeper) / **56 Down** | 78 (up) / **55 Up** |
| lab 144 | 143 (**back**) / 56 Down | 145 (**forward**) / 55 Up |
| lab 146 | 145 (back) / 56 Down | 147 (forward) / 55 Up |

How the maze generator places the stairs for a custom id:

- It places the type's hardcoded PREV room (`DExit*U.ds1`, up stairs) and NEXT room (`DExit*D.ds1`, down stairs).
- Which levels.txt slot each room's warp uses is fixed by the main index baked into those vanilla DS1s.
- So in 144 and 146, the down staircase leads back and the up staircase leads forward. That is exactly the "5 exit → 6 entrance → 6 exit should be backwards" report.

**Fix:** mirror vanilla. On 144 and 146 swap the slots:
- `Vis0=<next>`, `Warp0=56`
- `Vis1=<prev>`, `Warp1=55`

[I] Confirm in-game. We could not open the vanilla `DExit*` DS1s to read their main index directly; the claim rests on how vanilla wires 86–89.

Swapping only the Warp ids won't change the art. The art comes from the room DS1/DT1 (SD) and the HD preset/model, not from lvlwarp. lvlwarp only sets the click box, walk-out offset and lit/hover behaviour.

### 4b. Preset treasure rooms reused as levels 7 and 9 (145, 147) only have an *up* staircase

- `dungrm*.ds1` are vanilla Act 3 Dungeon treasure rooms. Vanilla has a single exit, slot 1, which is up stairs.
- In every `dungrm*` file, main1 is the 2-tile staircase. The HD JSON has `wall_stairs01` (up) at that tile.
- The lab uses slot 1 as the **forward** exit (Warp1=55, Act 3 Dungeon Up), so level 7 → 8 and level 9 → 10 are up-stairs.
- Slot 0, the way back, is a bare marker with Warp 83 and has no stair model.

**Fix options**

1. **Swap the slots, then add a down-stair at the main0 spot.**
   - Swap: `Vis1=prev, Warp1=55`; `Vis0=next`, with a down-stair at the main0 spot.
   - Each `dungrm*` DS1 then needs a down-stair tile at main0.
   - Each matching `data/hd/env/preset/labyrinth/dungrm*.json` needs a down-stair model entity at the same spot. HD units are 10 per tile; for example, tile (35,2) is roughly x=360, z=20.
   - Then use Warp 56 for it.
2. Use a different down-capable preset for 7 and 9.

### 4c. What's already correct (for reference)

- **Caves** (1, 2): Vis0 = Up (4), Vis4 = Down (5). Same as vanilla.
- **Jail** (16, 18): prev = 13 Up, next = 14 Down.
- **Catacombs** (17, 19): prev = 16, next = 18 Down.
- **Temple** (11–13): prev = 78 Up, next = 77 Down.
- **Baal** (22, 24): prev = 81 Up, next = 82 Down.
- **Ice** (21, 23): Down. Note that 159 sends its main exit through slot 1 (74), but 162 sends it through slot 2 (75, "Down Floor"). It is inconsistent but still a down warp.
- **Level 5** (`labyrinth05.ds1`): `stairs_up` model at the main0 (back) tile and `stairs_down` at the main4 (forward) tile. Correct.
- **Level 4** (`courtn1/2`): both exits are `stairs01` (the cathedral → catacomb down-stair art) with Warp 15. Visually both look like "down".
- **Level 3** (`towne1`): the back exit is the red town-portal FX. The forward exit has no visual model at all; it is an ori10 main1 tile at DS1 (22,23). Consider adding one.

### 4d. HD vs SD

For **preset** levels, the HD stair you see is a model entity in `data/hd/env/preset/labyrinth/<ds1name>.json`. Changing `Warp*` in levels.txt never changes it.

To "flip" an entrance and exit you have two options:
- Swap the main index (0 ↔ 1 or 4) of the special tiles in the DS1, so the existing art leads the other way.
- Or move/replace the model entities in the JSON *and* the SD tiles in the DS1.

The DS1 swap is the cheaper one, because the art stays put and only the destination changes.

---

## Suggested order of work
1. 141 `Position=0`. This fixes the crash and protects the spawn path.
2. 141: fill `nmon*` (plus `mon*`/`umon*`). Test Hell population.
3. Act 3 Dungeon maze levels 144 and 146: swap the Vis0/Vis1 + Warp slots to vanilla order.
4. `automap.txt`: add `wre`/`wle` rows to the "1 Town" and "1 Courtyard" blocks. Optionally revert the 8353f1b5 "1 Monestary" rows.
5. Levels 145 and 147: fix forward up-stairs (DS1 + HD JSON work).
6. Housekeeping:
   - Unique `Layer` per lab level.
   - `LitVersion=1` for lvlwarp 83 if a hover highlight is wanted.
   - Trim the `Portal=1` count to 32 or fewer.

## Handy one-liners used
- Lab rows with column names: a small Python `csv` dump of `levels.txt` keyed on `Id`.
- DS1 special tiles: parse v18 DS1 wall + orientation layers, and print cells with ori 8–11 (main = bits 20–25, sub = bits 8–13).
