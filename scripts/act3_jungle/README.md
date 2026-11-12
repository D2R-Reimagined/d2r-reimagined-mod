# Act 3 jungle: river crossings and entrance markers

These scripts produce the loose overrides in `data/global/tiles/act3/jungle/` and
`data/hd/env/preset/act3/jungle/`. They read vanilla files from
`C:/dev/d2r/base-files/data/data` and write into this repo's `data/`.

```
python gen_crossings.py           # dry run: lists crossings per block
python gen_crossings.py --write
python gen_markers.py --write
python validate.py                # re-checks every written file against vanilla
```

## Crossings (`gen_crossings.py`)

Jungle levels (Spider Forest, Great Marsh, Flayer Jungle) are built from 32x32
`Riv*.ds1` blocks. In 25 of them the river cuts off a land pocket on its
north/west side. That pocket only connects through a neighbouring block, so you
walk into it, hit the river and have to go back to find a log.

Every vanilla crossing uses one of two templates over the same river stamps
(`rivbank.dt1`):

- **H** (4x2 tiles, main 14 subs 0-3/12-15): crosses a north-south river, laid over
  the stamp pair `11:0-15 | 11:47-62`. The source is `rivns.ds1` at (18,17).
- **V** (2x4 tiles, main 14 subs 16-19/28-31): crosses an east-west river, laid over
  `12:16-31 / 10:1-16`. The source is `rive2.ds1` at (9,14).

For each pocket block the planner tries every spot where the crossing's 8
original cells match and simulates DT1 collision. It keeps the crossing that
joins the most pocket area to the main path, breaking ties by the HD terrain
match (heights sampled from `terrain.physics`, compared with the source
crossing's surroundings). Some blocks need two crossings. Afterwards every block
is one connected area.

HD: the source crossing's `bridge_*` and trampled-mud entities are copied at the
same offset and get new ids. The missing bridge/debris dependencies are added.
Trees or bushes standing on the walkway would be removed, but none are. Riverbank
prefabs stay, as they do under vanilla crossings.

## Entrance markers (`gen_markers.py`)

The Spider Cave and Arachnid Lair entrances are in `Spid*` variants 1-2, and the
Swampy Pit and Flayer Dungeon entrances are in `Pyg*` variants 1-2: 40 blocks in
all. Each gets new DS1 object units (Act 3 `objpreset` Index):

- a `TikiTorch1` (5) pair 6 subtiles inside every opening of the block;
- a `TikiTorch1` every ~6 tiles along the wall-avoiding route to the mouth. Later
  routes stop where they join an earlier lit one;
- a `JungleBrazier` (0) pair beside the cave mouth.

Both objects start lit (Mode0=1, light radius 19) and bring their own HD models,
so no preset JSON changes are needed. The script asserts that every route stays
walkable with the new object collision.
