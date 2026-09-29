"""Purpose-built Warden arenas: one layout, emitted as a DS1 and its HD scene.

A cloned stock arena brings its own hand-made HD scene. A new room has none,
so both halves are produced here from the same layout and cannot disagree:

* The DS1 carries everything the server and legacy renderer use: floor and
  wall tiles (collision), objects, the return warp and the Warden's spot.
  Tile cells are the values the tileset's own stock rooms use for each piece.
* The HD scene is assembled from entities of the tileset's stock scenes
  (walls, low front walls, pillars, statues, pavement prefabs, stamps, FX),
  cloned verbatim and repositioned. Nothing is invented: every component,
  model and prefab is one the stock rooms already ship.

Grid: one DS1 tile is 10 HD units, tile (x, y) spanning HD x 10x..10x+10 and
z 10y..10y+10; DS1 objects use 5 subtiles per tile. Every offset below was
measured from the stock Tal Rasha's Tomb rooms (tombnsew, tombnse, tombcubes
...) against their DS1s, not tuned by eye.

The floor mesh is a stock flat plane scaled over the room. It must cover its
whole square: a room's own terrain covers only that room's walkable floor
(tombnsew's is a cross), and stretched over an arena it left the corners and
aisles without ground (seen in game, 2026-09-29). Several simple presets use a
plain 10x10-quad grid covering all of 170x170; celSE3's is one. Tomb floors
are textured by the scene's biome (sand) and terrain stamps, not by the mesh's
origin or the legacy floor tiles (act2_tomb_masks.json has no Tomb.dt1 path
masks), so the plane renders as tomb sand.
"""
import copy
import json
import math
import random
import struct
import zlib
from pathlib import Path

import boss_rooms

# --------------------------------------------------------------------------
# Act 2 Tomb tile cells (LevelType 17, Dt1Mask 639). Cell layout: bits 0-7
# flags (0x81 wall, 0xc2 floor), 8-15 sub index, 20-25 main index.
# --------------------------------------------------------------------------
# Back walls (north row, west column) are Tomb.dt1 main 0: full-height, block
# walk and sight. Front walls (south row, east column, both far ends) are
# main 1: the low rubble walls that do not block sight, which is why the HD
# scene draws them as fences.
BACK_WALL_SUBS = (0, 4, 0, 1)          # stock rotation of the plain variants
BACK_CORNER = 0x000181                 # orientation 3, main 0 sub 1
FRONT_WALL = 0x100081                  # orientations 1/2/5/6/7, main 1 sub 0
COLUMN = 0x000081                      # Columns.dt1 orientation 12: 2x2 subtile pillar
FLOOR = 0x0000C2
# Floor pieces the stock rooms lay along walls (sub index per position).
FLOOR_UNDER_TOP = 0x000AC2
FLOOR_UNDER_LEFT = 0x0004C2
FLOOR_UNDER_CORNER = 0x0009C2
FLOOR_EAST_EDGE = 0x0008C2
FLOOR_SOUTH_EDGE = 0x000EC2
FLOOR_SE_EDGE = 0x000DC2
FLOOR_VARIANTS = (0x0, 0x0, 0x0, 0x1, 0x2, 0x3, 0x5, 0x6, 0x9, 0xB, 0xC, 0xF)
# Outside the room: stock rooms fill unused cells with main 30, which Tomb.dt1
# does not define, i.e. no floor.
VOID = 0x1E00042

ORIENT_LEFT, ORIENT_TOP, ORIENT_CORNER = 1, 2, 3
ORIENT_EAST_END, ORIENT_WEST_END, ORIENT_SOUTH_CORNER = 5, 6, 7
ORIENT_WARP, ORIENT_COLUMN = 11, 12

# Act 2 objpreset indices (the DS1 is stamped Act 2; boss_rooms.clone moves
# every object into the Act 5 namespace by class).
OBJ_TORCH_LEFT = 91        # TombWallTorchLeft, on a west wall
OBJ_TORCH_RIGHT = 92       # TombWallTorchRight, on a north wall
OBJ_BRAZIER_TALL = 94      # DesertBrazierTall
OBJ_URNS = (25, 26, 27, 28, 29)
OBJ_SKELETON = 79          # CorpseSkeleton
OBJ_LIGHT = 125            # HellLight3: invisible light source, as in Duriel's lair

TOMB_DT1S = [rf"\d2\data\global\tiles\act2\tomb\{n}.dt1"
             for n in ("tomb", "columns", "things", "stairs")]

# Stock scenes the entity templates are taken from (first match wins).
TOMB_SCENES = ("tombnsew", "tombnse", "tombcubes", "tombs", "tombetalrasha")
# A flat 11x11-vertex grid at y 0 covering exactly 0..170 on both axes.
TERRAIN_SCENE = "act2/palace/celse3"
TERRAIN_SIZE = 170.0

TOMB_PREFABS = "data/hd/env/model/act2/tomb/prefab"
ALCOVES = f"{TOMB_PREFABS}/wall_alcoves_prefabs"
DRESSING = f"{TOMB_PREFABS}/wall_setdressing_prefabs"
# Ritual candle clusters (Act 3 temple set, also used in Duriel's lair) and
# the tomb's ceiling window: a shaft of daylight, dust and a spotlight.
CANDLES = "data/hd/env/model/global/prop/act3/temple/prefabs/ritualistic/pf_candles02.json"
LIGHT_SHAFT = "data/hd/env/light/gobo/prefab/pf_act2_tomb_window01.json"

# The Labyrinth arenas' return warp: an orientation 11 marker whose main
# index is the level's Vis slot, drawn in HD as a red portal. Same art and
# lvlwarp (83) the tested Labyrinth rooms answer to.
RED_PORTAL_PARTICLES = ("data/hd/vfx/particles/objects/vfx_only/town_portal/"
                        "vfx_town_portal_NewStuff_NewRed.particles")


def _yaw(degrees):
    half = math.radians(degrees) / 2
    return {"x": 0.0, "y": round(math.sin(half), 9), "z": 0.0, "w": round(math.cos(half), 9)}


class Kit:
    """Entity templates and dependencies harvested from stock HD scenes."""

    def __init__(self, folder, scenes, terrain_scene):
        self.templates, self.deps = {}, {}
        for name in scenes:
            scene = _load_scene(f"{folder}/{name}")
            self.merge(scene["dependencies"])
            for entity in scene["entities"]:
                key = _template_key(entity)
                if key and key not in self.templates:
                    self.templates[key] = entity
        # Only the terrain is taken from its scene, with its own mesh files.
        self.terrain = _load_scene(terrain_scene)["terrain"]
        for comp in self.terrain["components"]:
            if comp["type"] == "ModelDefinitionComponent":
                self.merge({"models": [{"path": comp["filename"]}]})
            if comp["type"] == "PhysicsBodyDefinitionComponent":
                paths = [f["shapetype"]["filename"] for f in comp["fixturedefs"]]
                self.merge({"physics": [{"path": path} for path in paths]})
                _require_full_plane(paths[0])

    def merge(self, dependencies):
        for kind, entries in dependencies.items():
            bucket = self.deps.setdefault(kind, {})
            for entry in entries:
                bucket.setdefault(entry["path"].lower(), entry)

    def merge_prefab(self, path):
        """Stock scenes list every model their prefabs use among their own
        dependencies, so a placed prefab's are merged in too."""
        source = boss_rooms._stock(Path(path[len("data/"):]))
        self.merge(json.loads(source.read_text(encoding="utf-8-sig"))["dependencies"])

    def prefab(self, path):
        """A placement entity for stock prefab `path`."""
        entity = copy.deepcopy(self.templates["pf_tile_center01.json"])
        for comp in entity["components"]:
            if comp["type"] == "PrefabPlacementDefinitionComponent":
                comp["prefab"] = path
        return entity

    def dependencies(self, extra=()):
        deps = {kind: list(bucket.values()) for kind, bucket in self.deps.items()}
        for kind, path in extra:
            if path.lower() not in self.deps.get(kind, {}):
                deps.setdefault(kind, []).append({"path": path})
        return deps


def _require_full_plane(physics):
    """The terrain's collision mesh (header: node, vertex and triangle offsets
    and counts; 16-byte vertices; 32-byte triangles led by three indices)
    must be flat and cover all of TERRAIN_SIZE squared, or scaling it leaves
    parts of the room without ground."""
    data = boss_rooms._stock(Path(physics[len("data/"):])).read_bytes()
    _, _, vertices, _, triangles, _, _, nv, nt = struct.unpack_from("<9I", data)
    v = [struct.unpack_from("<3f", data, vertices + 16 * i) for i in range(nv)]
    area = 0.0
    for i in range(nt):
        a, b, c = (v[j] for j in struct.unpack_from("<3I", data, triangles + 32 * i))
        area += abs((b[0] - a[0]) * (c[2] - a[2]) - (c[0] - a[0]) * (b[2] - a[2])) / 2
    if any(abs(p[1]) > 1e-3 for p in v) or abs(area - TERRAIN_SIZE ** 2) > 1:
        raise ValueError(f"{physics} is not a flat plane covering {TERRAIN_SIZE}x{TERRAIN_SIZE}")


def _load_scene(rel):
    path = boss_rooms._stock(Path("hd/env/preset") / f"{rel}.json")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _template_key(entity):
    comps = {c["type"]: c for c in entity["components"]}
    if "TerrainDefinitionComponent" in comps:
        return None
    for kind, field in (("ModelDefinitionComponent", "filename"),
                        ("PrefabPlacementDefinitionComponent", "prefab"),
                        ("VfxDefinitionComponent", "filename"),
                        ("TerrainStampDefinitionComponent", "mask"),
                        ("DecalDefinitionComponent", "diffuseMap")):
        value = comps.get(kind, {}).get(field)
        if value:
            return value.rsplit("/", 1)[-1]
    variants = comps.get("ModelVariationDefinitionComponent", {}).get("variations")
    if variants:
        return variants[0]["filename"].rsplit("/", 1)[-1]
    return None


class Scene:
    """An HD preset scene: repositioned clones of kit entities."""

    def __init__(self, kit, biome, cells_x, cells_y):
        self.kit, self.biome = kit, biome
        self.entities, self.ids = [], set()
        terrain = copy.deepcopy(kit.terrain)
        transform = _transform(terrain)
        transform["scale"] = {"x": cells_x * 10 / TERRAIN_SIZE, "y": 1.0,
                              "z": cells_y * 10 / TERRAIN_SIZE}
        self.terrain = terrain
        self.ids.add(terrain["id"])
        self.entities.append(terrain)
        self.extra_deps = []

    def add(self, key, x, z, yaw=None, y=None, scale=None):
        """Place kit entity `key` at HD (x, z). `yaw` (degrees about +y)
        replaces the template's orientation; None keeps it."""
        return self._place(copy.deepcopy(self.kit.templates[key]), key, x, z, yaw, y, scale)

    def prefab(self, path, x, z, yaw=0):
        """Place the stock prefab at `path` (a data/hd/... path)."""
        return self._place(self.kit.prefab(path), path.rsplit("/", 1)[-1], x, z, yaw, None, None)

    def _place(self, entity, key, x, z, yaw, y, scale):
        name = f"rmap_{key.split('.')[0]}_{len(self.entities):03d}"
        identity = zlib.crc32(name.encode())
        while identity in self.ids:
            identity = (identity + 1) & 0xFFFFFFFF
        self.ids.add(identity)
        entity["name"], entity["id"] = name, identity
        transform = _transform(entity)
        position = transform["position"]
        position["x"], position["z"] = round(x, 4), round(z, 4)
        if y is not None:
            position["y"] = y
        if yaw is not None and "orientation" in transform:
            transform["orientation"] = _yaw(yaw)
        if scale is not None and "scale" in transform:
            transform["scale"] = {"x": scale, "y": scale, "z": scale}
        for comp in entity["components"]:
            if comp["type"] == "WallTransparencyComponent":
                comp["wallTileLocalCoord"] = {"x": -1, "y": -1}
            if comp["type"] == "PrefabPlacementDefinitionComponent":
                self.kit.merge_prefab(comp["prefab"])
        self.entities.append(entity)
        return entity

    def add_raw(self, entity, deps=()):
        entity = copy.deepcopy(entity)
        if entity["id"] in self.ids:
            raise ValueError(f"duplicate HD entity id {entity['id']}")
        self.ids.add(entity["id"])
        self.entities.append(entity)
        self.extra_deps += deps

    def to_bytes(self):
        scene = {
            "dependencies": self.kit.dependencies(self.extra_deps),
            "entities": self.entities,
            "type": "Preset",
            "name": "preset",
            "terrain": self.terrain,
            "biomeFilename": self.biome,
            "perTileBiomeOverrides": [],
            "specialTiles": {},
        }
        return (json.dumps(scene, separators=(",", ":")) + "\n").encode()


def _transform(entity):
    for comp in entity["components"]:
        if comp["type"] in ("TransformDefinitionComponent", "TransformVariationDefinitionComponent"):
            return comp
    raise ValueError(f"{entity['name']} has no transform")


class Room:
    """A v18 DS1 with one wall layer, one floor layer and no substitutions."""

    def __init__(self, cells_x, cells_y, act, files):
        self.w, self.h, self.act, self.files = cells_x, cells_y, act, files
        self.floor = [VOID] * (cells_x * cells_y)
        self.wall = [0] * (cells_x * cells_y)
        self.orient = [0] * (cells_x * cells_y)
        self.objects = []

    def set_floor(self, x, y, cell):
        self.floor[y * self.w + x] = cell

    def set_wall(self, x, y, orientation, cell):
        at = y * self.w + x
        if self.wall[at]:
            raise ValueError(f"wall cell {x},{y} is already used")
        self.wall[at], self.orient[at] = cell, orientation

    def add_object(self, kind, index, sx, sy):
        if not (0 <= sx < self.w * 5 and 0 <= sy < self.h * 5):
            raise ValueError(f"object {index} at {sx},{sy} is outside the room")
        self.objects.append((kind, index, sx, sy, 0))

    def to_bytes(self):
        out = bytearray(struct.pack("<6I", 18, self.w - 1, self.h - 1, self.act, 0, len(self.files)))
        for name in self.files:
            out += name.encode("latin1") + b"\0"
        out += struct.pack("<2I", 1, 1)
        for layer in (self.wall, self.orient, self.floor, [0] * len(self.floor)):
            out += struct.pack(f"<{len(layer)}I", *layer)
        out += struct.pack("<I", len(self.objects))
        for row in self.objects:
            out += struct.pack("<5I", *row)
        out += struct.pack("<I", 0)  # no NPC paths
        return bytes(out)


# --------------------------------------------------------------------------
# Sandswept Tomb: the Warden's sanctum
# --------------------------------------------------------------------------
# A 20x20 tomb hall (first tested at 26x26: too big). Eight free-standing pillars ring an open, paved central
# court where the Warden waits; the ring's corners are open and marked by tall
# braziers. Torches line the two back walls between pharaoh statues, sand has
# drifted in along every wall, and the player arrives by the red portal in the
# south corner, a diagonal walk from the court.
SANDSWEPT = {
    # Interior tiles, inclusive. The back walls take the row/column before
    # `lo`, the front walls the one after `hi`, which is the DS1's last cell,
    # so the floor mesh ends at the front walls.
    "lo": 3, "hi": 22,
    "ring": (7, 18), "ring_gaps": (10, 15),
    "court": (9, 16),                   # paved square, inclusive
    # Back-wall dressing, tile indices along both back walls (mirrored about
    # the hall's centre line, 12.5). Prefab names: (north, west).
    "torches": (5, 9, 16, 20),
    "statues": (11, 14),                # pharaohs flanking each wall's centre
    "priestesses": (4, 21),
    "alcoves": {7: ("alcove_a10", "alcove_a06"), 18: ("alcove_a11", "alcove_a08")},
    "wall_props": {12: ("scrolls01", "jars01"), 22: ("pots06", "pots01")},
    "warden": (62, 62),                 # subtiles: the court's centre
    "portal": (19, 19),                 # tile of the return warp
    "warp_slot": 2,
    "seed": 1105,
}


def build_sandswept():
    s = SANDSWEPT
    lo, hi = s["lo"], s["hi"]
    back, front = lo - 1, hi + 1
    cells = front + 1
    rng = random.Random(s["seed"])
    room = Room(cells, cells, 1, TOMB_DT1S)
    kit = Kit("act2/tomb", TOMB_SCENES, TERRAIN_SCENE)
    scene = Scene(kit, "data/hd/env/biome/act2_tomb.json", cells, cells)

    # ---- floor -----------------------------------------------------------
    for y in range(lo, hi + 1):
        for x in range(lo, hi + 1):
            cell = FLOOR | rng.choice(FLOOR_VARIANTS) << 8
            if x == hi and y == hi:
                cell = FLOOR_SE_EDGE
            elif x == hi:
                cell = FLOOR_EAST_EDGE
            elif y == hi:
                cell = FLOOR_SOUTH_EDGE
            room.set_floor(x, y, cell)

    # ---- walls -----------------------------------------------------------
    # Back walls sit on the north edge of row `back` / west edge of column
    # `back`; only that edge's subtiles block, so the rest of those tiles is
    # floor. Front walls block the south/east ends of the room and nothing
    # lies beyond them.
    room.set_wall(back, back, ORIENT_CORNER, BACK_CORNER)
    room.set_floor(back, back, FLOOR_UNDER_CORNER)
    scene.add("pillar01.model", 10 * back + 1, 10 * back + 1, 0)
    torch_tiles = set(s["torches"])
    for i, t in enumerate(range(lo, hi + 1)):
        sub = BACK_WALL_SUBS[i % len(BACK_WALL_SUBS)] << 8
        room.set_wall(t, back, ORIENT_TOP, 0x81 | sub)
        room.set_floor(t, back, FLOOR_UNDER_TOP)
        room.set_wall(back, t, ORIENT_LEFT, 0x81 | sub)
        room.set_floor(back, t, FLOOR_UNDER_LEFT)
    # HD back walls: one 10-unit segment per tile, the corner tile included.
    # A torch replaces its tile's segment with the stock torch prefab, which
    # carries the same wall piece plus the torch mount and scorch decal; an
    # alcove replaces it with a niche piece standing 3.7 units proud of the
    # wall line, as in Duriel's lair. Both left a gap in the wall in game, so
    # a plain segment also stands behind each (placed by hand on tier 1,
    # 2026-09-29, then adopted here). Those are picked without the RNG so the
    # rest of the room's random dressing stays as tested.
    styles = ("wall_a01.model", "wall_b01.model", "wall_a01_clean.model", "wall_b01_clean.model")
    alcoves = s["alcoves"]
    for t in range(back, hi + 1):
        if t in torch_tiles:
            room.add_object(2, OBJ_TORCH_RIGHT, 5 * t + 2, 5 * back)
            scene.add("pf_wall_torch_right.json", 10 * t + 6, 10 * back + 2, 0)
            room.add_object(2, OBJ_TORCH_LEFT, 5 * back, 5 * t + 2)
            scene.add("pf_wall_torch_left.json", 10 * back + 2, 10 * t + 6, 0)
        elif t in alcoves:
            north, west = alcoves[t]
            scene.prefab(f"{ALCOVES}/{north}.json", 10 * t + 11, 10 * back + 3.7, 0)
            scene.prefab(f"{ALCOVES}/{west}.json", 10 * back + 3.7, 10 * t + 0.8, 90)
        else:
            scene.add(rng.choice(styles), 10 * t + 11, 10 * back - 0.4, 0)
            scene.add(rng.choice(styles), 10 * back, 10 * t + 0.9, 90)
            continue
        scene.add(styles[t % len(styles)], 10 * t + 11.13, 10 * back - 0.4, 0)
        scene.add(styles[(t + 1) % len(styles)], 10 * back, 10 * t + 0.77, 90)
    # More wall dressing from the tomb's own prefab sets: pots, scrolls and
    # jars along a tile's wall foot at the wall segment's own pivot; the
    # grave-goods corner piece in the back corner.
    for t, (north, west) in s["wall_props"].items():
        scene.prefab(f"{DRESSING}/{north}.json", 10 * t + 11, 10 * back - 0.4, 0)
        scene.prefab(f"{DRESSING}/{west}.json", 10 * back, 10 * t + 0.9, 90)
    scene.prefab(f"{DRESSING}/corner01.json", 10 * back + 1, 10 * back + 1, 0)

    room.set_wall(front, back, ORIENT_EAST_END, FRONT_WALL)
    scene.add("pf_pillar_right.json", 10 * front + 2, 10 * back, 0)
    room.set_wall(back, front, ORIENT_WEST_END, FRONT_WALL)
    scene.add("pf_pillar_left.json", 10 * back, 10 * front + 2, 0)
    room.set_wall(front, front, ORIENT_SOUTH_CORNER, FRONT_WALL)
    for t in range(lo, hi + 1):
        room.set_wall(t, front, ORIENT_TOP, FRONT_WALL)
        room.set_wall(front, t, ORIENT_LEFT, FRONT_WALL)
    # HD front walls: full-height segments end to end (10.13 units, one model
    # length apart) along the south row and east column, not the stock low
    # fences, which left the room open to the void on those sides. Laid out
    # by hand on tier 1 (2026-09-29) and adopted here.
    for k in range(front - back):
        scene.add("wall_b01_clean.model", 10 * back + 10.13 * (k + 1), 10 * front + 1.03, 0)
        scene.add("wall_b01_clean.model", 10 * front + 1.89, 10 * back - 1.68 + 10.13 * k, 90)

    # ---- statues ---------------------------------------------------------
    # Pharaohs stand against the back walls facing into the hall (stock:
    # x+1.5/z+4.5 on a north wall tile, mirrored on a west wall).
    for t in s["statues"]:
        scene.add("pharoah01.model", 10 * t + 1.5, 10 * back + 4.5, 0)
        scene.add("pharoah01.model", 10 * back + 4.5, 10 * t + 1.5, 90)
    # Priestesses close each wall's row of statues (stock: x+8.6/z+3.5 on a
    # north wall tile, x+3.5/z+3.5 on a west one).
    for t in s["priestesses"]:
        scene.add("priestess01.model", 10 * t + 8.6, 10 * back + 3.5, 0)
        scene.add("priestess01.model", 10 * back + 3.5, 10 * t + 3.5, 90)

    # ---- pillar ring -----------------------------------------------------
    a, b = s["ring"]
    g1, g2 = s["ring_gaps"]
    pillars = [(a, g1), (a, g2), (b, g1), (b, g2), (g1, a), (g2, a), (g1, b), (g2, b)]
    for x, y in pillars:
        room.set_wall(x, y, ORIENT_COLUMN, COLUMN)
        scene.add("pillar01.model", 10 * x + 3.5, 10 * y + 3.2, 0)
        scene.add("sand_pile07.model", 10 * x + 3.5, 10 * y + 3.2, rng.uniform(0, 360))
    for x, y in ((a, a), (b, a), (a, b), (b, b)):
        room.add_object(2, OBJ_BRAZIER_TALL, 5 * x + 2, 5 * y + 2)

    # ---- the court -------------------------------------------------------
    c0, c1 = s["court"]
    for y in range(c0, c1 + 1):
        for x in range(c0, c1 + 1):
            cx, cz = 10 * x + 5, 10 * y + 5
            exposed = [d for d, edge in ((0, x == c1), (90, y == c0), (180, x == c0), (270, y == c1)) if edge]
            if exposed:
                piece = rng.choice(("pf_tile_edge01.json", "pf_tile_edge02.json", "pf_tile_edge03.json"))
                scene.add(piece, cx, cz, rng.choice(exposed))
            else:
                piece = rng.choice(("pf_tile_center01.json", "pf_tile_center02.json"))
                scene.add(piece, cx, cz, rng.choice((0, 90, 180, 270)))
    # Worn, sand-choked paving: drifts and loose slabs over the court.
    for _ in range(6):
        x, z = rng.uniform(10 * c0 + 5, 10 * c1 + 5), rng.uniform(10 * c0 + 5, 10 * c1 + 5)
        scene.add("sand_tile_pile01.model", x, z, rng.uniform(0, 360))
        scene.add("act2_tomb_sand_blend01_ALB.texture", x + 0.3, z + 0.5, rng.uniform(0, 360))
    for _ in range(7):
        x, z = rng.uniform(10 * c0, 10 * c1 + 10), rng.uniform(10 * c0, 10 * c1 + 10)
        scene.add(rng.choice(("tile_rubble01.model", "tile_small01.model", "tile_large01.model")), x, z)
    # Ritual candles at the court's corners and a shaft of daylight from a
    # ceiling window onto the Warden; two more shafts break up the aisles.
    for x, y, yaw in ((c0, c0, 0), (c1, c0, 90), (c1, c1, 180), (c0, c1, 270)):
        scene.prefab(CANDLES, 10 * x + 5, 10 * y + 5, yaw)
    wx, wy = s["warden"]
    scene.prefab(LIGHT_SHAFT, 2 * wx, 2 * wy + 4)
    scene.prefab(LIGHT_SHAFT, 10 * lo + 30, 10 * hi - 30)
    scene.prefab(LIGHT_SHAFT, 10 * hi - 30, 10 * lo + 30)
    # Invisible light sources around the court (legacy light radius; the
    # braziers and torches carry the HD light).
    mid = 5 * (c0 + c1 + 1) // 2
    for dx, dy in ((-20, 0), (20, 0), (0, -20), (0, 20)):
        room.add_object(2, OBJ_LIGHT, mid + dx, mid + dy)

    # ---- the path in -----------------------------------------------------
    # A worn path from the portal to the court's south corner, along the
    # diagonal the player walks.
    px, py = s["portal"]
    start, end = (10 * px + 5, 10 * py + 5), (10 * c1 + 8, 10 * c1 + 8)
    steps = 4
    for i in range(steps + 1):
        x = start[0] + (end[0] - start[0]) * i / steps
        z = start[1] + (end[1] - start[1]) * i / steps
        scene.add("act2_tomb_path_straight01_STAMP.texture", x, z, 45)

    # ---- sand, bones and grave goods -------------------------------------
    # Drifts along the walls, heaviest in the back corner.
    for t in range(lo, hi + 1, 2):
        if rng.random() < 0.7:
            scene.add(rng.choice(("sand_pile01.model", "sand_pile06.model", "sand_pile08.model")),
                      10 * t + rng.uniform(2, 8), 10 * lo + rng.uniform(-1, 2), rng.uniform(0, 360))
        if rng.random() < 0.7:
            scene.add(rng.choice(("sand_pile01.model", "sand_pile06.model", "sand_pile08.model")),
                      10 * lo + rng.uniform(-1, 2), 10 * t + rng.uniform(2, 8), rng.uniform(0, 360))
        if rng.random() < 0.5:
            scene.add("sand_pile04.model", 10 * t + rng.uniform(2, 8), 10 * front - rng.uniform(1, 3),
                      rng.uniform(0, 360))
            scene.add("sand_pile04.model", 10 * front - rng.uniform(1, 3), 10 * t + rng.uniform(2, 8),
                      rng.uniform(0, 360))
    for dx, dz in ((3, 8), (8, 3), (6, 6), (12, 4), (4, 12)):
        scene.add(rng.choice(("sand_pile01.model", "sand_pile06.model", "sand_pile08.model")),
                  10 * lo + dx, 10 * lo + dz, rng.uniform(0, 360))
    for _ in range(16):
        x, z = rng.uniform(10 * lo + 5, 10 * hi + 5), rng.uniform(10 * lo + 5, 10 * hi + 5)
        if 10 * c0 - 5 < x < 10 * c1 + 15 and 10 * c0 - 5 < z < 10 * c1 + 15:
            continue
        scene.add("sand_tile_pile01.model", x, z, rng.uniform(0, 360))
        scene.add("act2_tomb_sand_blend01_ALB.texture", x + 0.3, z + 0.5, rng.uniform(0, 360))
    # Hard-packed sand and noise stamps so the floor is not one flat sheet.
    for _ in range(9):
        scene.add(rng.choice(("act2_outdoor_noise02_STAMP.texture", "act2_town_noise04_STAMP.texture")),
                  rng.uniform(10 * lo, 10 * hi + 10), rng.uniform(10 * lo, 10 * hi + 10), rng.uniform(0, 360))
    # Remains of those who came before, strewn between the ring and the walls.
    bones = ("bone02.model", "bone03.model", "rib02.model", "skull02.model", "skull_fragment02.model")
    for cx, cz in ((10 * lo + 22, 10 * hi - 12), (10 * hi - 14, 10 * lo + 24),
                   (10 * lo + 40, 10 * lo + 16)):
        for _ in range(5):
            scene.add(rng.choice(bones), cx + rng.uniform(-5, 5), cz + rng.uniform(-5, 5), rng.uniform(0, 360))
    # Grave goods heaped at the statues' feet.
    goods = ("canopic_jar01.model", "canopic_jar02.model", "canopic_jar_broken01.model",
             "vase_blue01.model", "vase_brown01.model", "tablet01.model")
    for t in s["statues"]:
        for _ in range(3):
            scene.add(rng.choice(goods), 10 * t + rng.uniform(-3, 6), 10 * lo + rng.uniform(1, 4),
                      rng.uniform(0, 360), y=0.0)
            scene.add(rng.choice(goods), 10 * lo + rng.uniform(1, 4), 10 * t + rng.uniform(-3, 6),
                      rng.uniform(0, 360), y=0.0)
    # Cobweb strung across the west wall by the back corner (stock: x+1.1 on
    # a west wall tile, the template keeps its tilt and height).
    scene.add("cobweb04.model", 10 * back + 1.1, 10 * lo + 5.7)

    # Breakable urns and a looted corpse (real objects, legacy and HD).
    for sx, sy in ((5 * lo + 3, 5 * hi + 2), (5 * lo + 5, 5 * hi + 3), (5 * hi + 2, 5 * lo + 3),
                   (5 * hi + 3, 5 * lo + 5), (5 * lo + 12, 5 * lo + 2), (5 * lo + 2, 5 * lo + 12)):
        room.add_object(2, rng.choice(OBJ_URNS), sx, sy)
    room.add_object(2, OBJ_SKELETON, 5 * lo + 11, 5 * hi - 6)
    room.add_object(2, OBJ_SKELETON, 5 * hi - 6, 5 * lo + 11)

    # ---- atmosphere ------------------------------------------------------
    for _ in range(8):
        scene.add("FX_Act2Tomb_fog_20x20.particles",
                  rng.uniform(10 * lo, 10 * hi + 10), rng.uniform(10 * lo, 10 * hi + 10))
    for _ in range(8):
        scene.add("FX_Act2Tomb_motes_30x30.particles",
                  rng.uniform(10 * lo, 10 * hi + 10), rng.uniform(10 * lo, 10 * hi + 10))
    for _ in range(5):
        scene.add("FX_Act2Tomb_sand_10x10.particles",
                  rng.uniform(10 * lo, 10 * hi + 10), rng.uniform(10 * lo, 10 * hi + 10))

    # ---- return warp and the Warden --------------------------------------
    room.set_wall(px, py, ORIENT_WARP, 0x81 | s["warp_slot"] << 20)
    portal = {
        "type": "Entity", "name": "FX_TownPortal_Red_01", "id": 4123456789,
        "components": [
            {"type": "TransformDefinitionComponent", "name": "FX_TownPortal_Red_01_Transform",
             "position": {"x": 10 * px + 5.22, "y": 0, "z": 10 * py + 5},
             "scale": {"x": 1, "y": 1, "z": 1}, "orientation": {"x": 0, "y": 0, "z": 0, "w": 1},
             "inheritOnlyPosition": False},
            {"type": "VfxDefinitionComponent", "name": "FX_TownPortal_Red_01_Vfx",
             "filename": RED_PORTAL_PARTICLES, "hardKillOnDestroy": False},
        ],
    }
    scene.add_raw(portal, [("particles", RED_PORTAL_PARTICLES)])
    # Placeholder monster: boss_rooms.clone replaces it with the Warden.
    room.add_object(1, 0, *s["warden"])
    return room.to_bytes(), scene.to_bytes()


BUILDERS = {"sandswept": build_sandswept}
_cache = {}


def build(name):
    """(ds1 bytes, HD scene bytes) for the custom arena `name`."""
    if name not in _cache:
        _cache[name] = BUILDERS[name]()
    return _cache[name]
