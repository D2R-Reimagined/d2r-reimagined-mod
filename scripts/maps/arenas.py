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
import re
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
        self.templates, self.named, self.scenes, self.deps = {}, {}, {}, {}
        for name in scenes:
            scene = self.scenes[name] = _load_scene(f"{folder}/{name}")
            self.merge(scene["dependencies"])
            for entity in scene["entities"]:
                key = _template_key(entity)
                if key and key not in self.templates:
                    self.templates[key] = entity
                # Stamps that share a mask differ only by layer; their entity
                # names ("icecave_icesheet01_04") tell them apart.
                self.named.setdefault(re.sub(r"_\d+$", "", entity["name"]), entity)
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
        entity = copy.deepcopy(self.templates.get("pf_tile_center01.json") or next(
            t for t in self.templates.values()
            if any(c["type"] == "PrefabPlacementDefinitionComponent" for c in t["components"])))
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

    def add_named(self, name, x, z, yaw=None, y=None):
        """Place the stock entity named `name` (minus its _NN suffix)."""
        return self._place(copy.deepcopy(self.kit.named[name]), name, x, z, yaw, y, None)

    def copy_region(self, scene, keep, dx, dz):
        """Clone every entity of kit scene `scene` for which keep(name, x, z)
        holds, shifted by (dx, dz), keeping its height, rotation and scale."""
        for entity in self.kit.scenes[scene]["entities"]:
            position = _transform(entity)["position"] if _has_transform(entity) else None
            if position and keep(entity["name"], position["x"], position["z"]):
                self._place(copy.deepcopy(entity), re.sub(r"_\d+$", "", entity["name"]),
                            position["x"] + dx, position["z"] + dz, None, None, None)

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
            transform["scale"] = dict(scale) if isinstance(scale, dict) else {"x": scale, "y": scale, "z": scale}
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


def _has_transform(entity):
    return any(c["type"] in ("TransformDefinitionComponent", "TransformVariationDefinitionComponent")
               for c in entity["components"])


def _transform(entity):
    for comp in entity["components"]:
        if comp["type"] in ("TransformDefinitionComponent", "TransformVariationDefinitionComponent"):
            return comp
    raise ValueError(f"{entity['name']} has no transform")


class Room:
    """A v18 DS1 with one or two wall layers, one floor layer and no
    substitutions."""

    def __init__(self, cells_x, cells_y, act, files, void=VOID):
        self.w, self.h, self.act, self.files = cells_x, cells_y, act, files
        self.floor = [void] * (cells_x * cells_y)
        self.walls = [[0] * (cells_x * cells_y)]
        self.orients = [[0] * (cells_x * cells_y)]
        self.objects = []

    def set_floor(self, x, y, cell):
        self.floor[y * self.w + x] = cell

    def set_wall(self, x, y, orientation, cell, layer=0):
        """A second layer holds a second piece on the same tile, e.g. both
        walls of a corner in tilesets that have no corner tile."""
        while len(self.walls) <= layer:
            self.walls.append([0] * (self.w * self.h))
            self.orients.append([0] * (self.w * self.h))
        at = y * self.w + x
        if self.walls[layer][at]:
            raise ValueError(f"wall cell {x},{y} is already used")
        self.walls[layer][at], self.orients[layer][at] = cell, orientation

    def add_object(self, kind, index, sx, sy):
        if not (0 <= sx < self.w * 5 and 0 <= sy < self.h * 5):
            raise ValueError(f"object {index} at {sx},{sy} is outside the room")
        self.objects.append((kind, index, sx, sy, 0))

    def to_bytes(self):
        out = bytearray(struct.pack("<6I", 18, self.w - 1, self.h - 1, self.act, 0, len(self.files)))
        for name in self.files:
            out += name.encode("latin1") + b"\0"
        out += struct.pack("<2I", len(self.walls), 1)
        layers = [grid for pair in zip(self.walls, self.orients) for grid in pair]
        for layer in layers + [self.floor, [0] * len(self.floor)]:
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


# --------------------------------------------------------------------------
# Frozen Depths: the Warden's glacier hall
# --------------------------------------------------------------------------
# Act 5 Ice Caves (LevelType 33, Dt1Mask 1: Interior.dt1 only). Measured from
# the stock ice rooms (icewback01, icee02, iceew03, poolroom01a ...):
#
# * Back-wall pieces are ~20 units long and pivot on the wall line at their
#   east (north wall) or south (west wall) end, yaw 0: the direction is in
#   the model, *01 running along z and *02/*03 along x. Stock rooms overlap
#   them freely; one per tile, as here, keeps the rock face unbroken.
# * Wall runs end in endcaps (endcap04 at a north run's east end);
#   column02/column03 stand at the room's far ends.
# * The floor texture comes from the floor tiles through the ice tile masks
#   (tile_masks.json): main 1 sub 1 is the plain base floor, main 5 tiles
#   paint path shapes. Variation here comes from the stock stamps instead.
# * Stairs up (lvlwarp 73, Vis slot 0) are two orientation 11 main 0 warp
#   tiles in a north wall under one wall_doorway01, pivot at the far tile's
#   east edge, dressed with timber (icewback01).
ICE_FLOOR = 0x1001C2
ICE_BACK_SUBS = (2, 5, 6, 13, 14, 15, 21, 22)   # straight full-edge pieces
ICE_CORNER = 0x000481                           # orientation 3 main 0 sub 4
ICE_FRONT_TOP_SUBS = (2, 4, 5, 6)               # orientation 2 main 1
ICE_FRONT_LEFT_SUBS = (1, 2, 4, 5, 6)           # orientation 1 main 1
ICE_FRONT_END = 0x100181                        # orientations 5/6/7 main 1 sub 1
# Orientation 12 main 2 columns and the model each carries in stock rooms.
ICE_COLUMNS = {0: ("column_small02.model", 2.0, 4.0),
               1: ("column_icechunk01.model", 3.3, 1.4),
               2: ("column_small03.model", 2.3, 2.6)}
ICE_DT1S = [r"\d2\data\global\tiles\expansion\icecave\interior.dt1"]
ICE_SCENES = ("poolroom01a", "icewback01", "icenway", "iceeahead01", "icesew01")

# Act 5 objpreset indices (the room is stamped Act 5 already).
OBJ_ICE_BRAZIER = 75           # IceCaveTorch1
OBJ_ICE_TORCH = 76             # IceCaveTorch2, the stock rooms' wall-side torch
OBJ_ICE_JARS = (67, 68, 69, 70, 71)
OBJ_DEAD_BARBARIAN = 73        # lootable frozen corpse
OBJ_FOG = 5

FROZEN = {
    # Same footprint as the Sandswept sanctum: 20x20, walls outside it.
    "lo": 3, "hi": 22,
    "ring": (7, 18), "ring_gaps": (10, 15),
    "court": (9, 16),                   # the frozen pool, inclusive
    "stairs": 17,                       # stairs up on tiles 17-18 of the north wall
    "torches_north": (5, 10, 14, 21),
    "torches_west": (5, 10, 15, 20),
    "ice_chunks": ((5, 13), (13, 5), (20, 11), (11, 20)),
    "warden": (62, 62),
    "seed": 1123,
}


def build_frozen():
    s = FROZEN
    lo, hi = s["lo"], s["hi"]
    back, front = lo - 1, hi + 1
    cells = front + 1
    rng = random.Random(s["seed"])
    room = Room(cells, cells, 4, ICE_DT1S, void=0)
    kit = Kit("expansion/icecave", ICE_SCENES, TERRAIN_SCENE)
    scene = Scene(kit, "data/hd/env/biome/expansion_icecave.json", cells, cells)
    stairs = (s["stairs"], s["stairs"] + 1)

    # ---- floor and legacy walls ------------------------------------------
    for y in range(back, front):
        for x in range(back, front):
            room.set_floor(x, y, ICE_FLOOR)
    room.set_wall(back, back, ORIENT_CORNER, ICE_CORNER)
    for i, t in enumerate(range(lo, hi + 1)):
        sub = ICE_BACK_SUBS[i % len(ICE_BACK_SUBS)] << 8
        if t in stairs:
            room.set_wall(t, back, ORIENT_WARP, 0x81 | (t - stairs[0]) << 8)
        else:
            room.set_wall(t, back, ORIENT_TOP, 0x81 | sub)
        room.set_wall(back, t, ORIENT_LEFT, 0x81 | sub)
        room.set_wall(t, front, ORIENT_TOP, 0x100081 | ICE_FRONT_TOP_SUBS[i % 4] << 8)
        room.set_wall(front, t, ORIENT_LEFT, 0x100081 | ICE_FRONT_LEFT_SUBS[i % 5] << 8)
    room.set_wall(front, back, ORIENT_EAST_END, ICE_FRONT_END)
    room.set_wall(back, front, ORIENT_WEST_END, ICE_FRONT_END)
    room.set_wall(front, front, ORIENT_SOUTH_CORNER, ICE_FRONT_END)

    # ---- HD walls --------------------------------------------------------
    # All four sides are full rock walls, as the Sandswept sanctum's are.
    along_x = ("wall_ice02.model", "wall_long02.model", "wall_bare03.model")
    along_z = ("wall_ice01.model", "wall_long01.model", "wall_bare01.model")
    for t in range(back, hi + 1):
        if t not in stairs:
            scene.add(rng.choice(along_x), 10 * (t + 1), 10 * back, 0)
        scene.add(rng.choice(along_z), 10 * back, 10 * (t + 1), 0)
        scene.add(rng.choice(along_x), 10 * (t + 1), 10 * front, 0)
        scene.add(rng.choice(along_z), 10 * front, 10 * (t + 1), 0)
    scene.add("corner_wall_ice01.model", 10 * back, 10 * back, 0)
    scene.add("wall_endcap04.model", 10 * front, 10 * back, 0)
    scene.add("column02.model", 10 * front + 1, 10 * back + 1, 0)
    scene.add("column03.model", 10 * back + 2, 10 * front + 2, 0)
    scene.add("column03.model", 10 * front + 2, 10 * front + 2, 0)

    # ---- stairs up (the return warp) -------------------------------------
    door = 10 * (stairs[1] + 1)
    scene.add("wall_endcap04.model", 10 * stairs[0], 10 * back, 0)
    scene.add("wall_doorway01.model", door, 10 * back, 0)
    # icewback01's doorway stands at (120, 10); bring its timber props along.
    scene.copy_region("icewback01", lambda name, x, z: name.startswith("wood_snowy")
                      and 88 <= x <= 132 and 8 <= z <= 36, door - 120, 10 * back - 10)

    # ---- torches along the back walls ------------------------------------
    for t in s["torches_north"]:
        room.add_object(2, OBJ_ICE_TORCH, 5 * t + 2, 5 * back + 2)
    for t in s["torches_west"]:
        room.add_object(2, OBJ_ICE_TORCH, 5 * back + 2, 5 * t + 2)

    # ---- pillar ring and ice chunks --------------------------------------
    a, b = s["ring"]
    g1, g2 = s["ring_gaps"]
    pillars = [(a, g1), (a, g2), (b, g1), (b, g2), (g1, a), (g2, a), (g1, b), (g2, b)]
    for i, (x, y) in enumerate(pillars):
        sub = (0, 2)[i % 2]
        model, dx, dz = ICE_COLUMNS[sub]
        room.set_wall(x, y, ORIENT_COLUMN, 0x200081 | sub << 8)
        scene.add(model, 10 * x + dx, 10 * y + dz, 0)
        scene.add("snow_mound03.model", 10 * x + dx, 10 * y + dz + 2, rng.uniform(0, 360))
    for x, y in s["ice_chunks"]:
        model, dx, dz = ICE_COLUMNS[1]
        room.set_wall(x, y, ORIENT_COLUMN, 0x200181)
        scene.add(model, 10 * x + dx, 10 * y + dz, 0)
    for x, y in ((a, a), (b, a), (a, b), (b, b)):
        room.add_object(2, OBJ_ICE_BRAZIER, 5 * x + 2, 5 * y + 2)

    # ---- the frozen pool -------------------------------------------------
    # Cracked-ice stamps (layer 6) sheet the court; frozen dead lie in it and
    # ice craters ring its edge.
    c0, c1 = s["court"]
    span = 10 * (c1 + 1 - c0)
    for i in range(3):
        for j in range(3):
            scene.add_named("icecave_icesheet01", 10 * c0 + span * (2 * i + 1) / 6,
                            10 * c0 + span * (2 * j + 1) / 6, rng.choice((0, 90, 180, 270)))
    for _ in range(4):
        scene.add_named("icecave_icerough01", rng.uniform(10 * c0, 10 * c1 + 10),
                        rng.uniform(10 * c0, 10 * c1 + 10), rng.uniform(0, 360))
    for model, x, z in (("corpse_frozen01.model", 10 * c0 + 22, 10 * c0 + 30),
                        ("corpse_frozen02.model", 10 * c1 - 12, 10 * c0 + 18),
                        ("corpse_frozen01.model", 10 * c0 + 40, 10 * c1 - 8)):
        scene.add(model, x, z, rng.uniform(0, 360))
    for x, z in ((10 * c0 - 4, 10 * c0 + 34), (10 * c1 + 8, 10 * c0 + 44),
                 (10 * c0 + 30, 10 * c1 + 9), (10 * c0 + 52, 10 * c0 - 5)):
        scene.add("crater01.model", x, z, rng.uniform(0, 360))
    wx, wy = s["warden"]
    for dx, dy in ((-12, 0), (12, 0), (0, -12), (0, 12)):
        room.add_object(2, OBJ_FOG, wx + dx, wy + dy)

    # ---- snow, remains and loot ------------------------------------------
    for t in range(lo, hi + 1, 3):
        scene.add_named("icecave_snow_dusty01", 10 * t + 5, 10 * lo + 4, rng.uniform(0, 360))
        scene.add_named("icecave_snow_dusty01", 10 * lo + 4, 10 * t + 5, rng.uniform(0, 360))
        scene.add_named("icacave_snow_straight03_STAMP", 10 * t + 5, 10 * hi + 6, 0)
        scene.add_named("icacave_snow_straight03_STAMP", 10 * hi + 6, 10 * t + 5, 90)
    for t in range(lo, hi + 1, 2):
        for x, z in ((10 * t + rng.uniform(2, 8), 10 * lo + rng.uniform(0, 3)),
                     (10 * lo + rng.uniform(0, 3), 10 * t + rng.uniform(2, 8))):
            if rng.random() < 0.6 and not (z < 10 * lo + 5 and 10 * stairs[0] - 5 < x < door + 5):
                scene.add("snow_mound03.model", x, z, rng.uniform(0, 360))
    for cx, cz in ((10 * lo + 8, 10 * lo + 8), (10 * hi, 10 * hi), (10 * lo + 6, 10 * hi),
                   (10 * hi, 10 * lo + 8)):
        scene.add_named("icecave_snow01", cx, cz, rng.uniform(0, 360))
    for cx, cz in ((10 * lo + 22, 10 * hi - 12), (10 * hi - 14, 10 * lo + 24),
                   (10 * lo + 40, 10 * lo + 16)):
        scene.add("remains_scattered01.model", cx + rng.uniform(-3, 3), cz + rng.uniform(-3, 3),
                  rng.uniform(0, 360))
    for sx, sy in ((5 * lo + 3, 5 * hi + 2), (5 * lo + 5, 5 * hi + 3), (5 * hi + 2, 5 * lo + 3),
                   (5 * hi + 3, 5 * lo + 6), (5 * lo + 3, 5 * lo + 4)):
        room.add_object(2, rng.choice(OBJ_ICE_JARS), sx, sy)
    room.add_object(2, OBJ_DEAD_BARBARIAN, 5 * lo + 11, 5 * hi - 6)
    room.add_object(2, OBJ_DEAD_BARBARIAN, 5 * hi - 6, 5 * lo + 13)

    # ---- atmosphere ------------------------------------------------------
    for _ in range(8):
        scene.add("FX_Act5Icecave_fog_20x20.particles",
                  rng.uniform(10 * lo, 10 * hi + 10), rng.uniform(10 * lo, 10 * hi + 10))
    for _ in range(5):
        scene.add("FX_Act5Icecave_mist_20x20.particles",
                  rng.uniform(10 * lo, 10 * hi + 10), rng.uniform(10 * lo, 10 * hi + 10))

    # Placeholder monster: boss_rooms.clone replaces it with the Warden.
    room.add_object(1, 0, wx, wy)
    return room.to_bytes(), scene.to_bytes()


# --------------------------------------------------------------------------
# Worldstone Keep: the Warden's throne hall
# --------------------------------------------------------------------------
# Act 5 Baal Temple tiles (LevelType 34: Walls.dt1 + Floor.dt1). The Keep's
# kit is tile-based like the tomb's; per tile variant the stock rooms
# (baalnsew01, baalnewup01 ...) carry a fixed recipe:
#
# * Back walls alternate variants 0-3: even variants carry a pillar01a at
#   (+1.8, +1.5); odd ones a wall01a panel at (+0.3, +1.1) and a trimmed
#   pillar02_wtrims_a, yaw 270 on a north wall, 0 on a west wall.
# * The back corner is a pillar_corner_wtrim at (+1.8, +2.0).
# * Stairs up (lvlwarp 81, Vis slot 0) are two orientation 11 main 0 warp
#   tiles in a north wall under one stairs_up01 at (+12, +0.1) of the first
#   tile, with pillars on the tiles either side.
# * Floors are plain marble (biome layer 0, no tile masks).
PRESET = {"worldstone": {"Dt1Mask": "3"},      # Walls.dt1 + Floor.dt1
          "steppes": {"Dt1Mask": "265"},       # Mesa Floor + Brick_Walls + Surf_Struct
          "infernal": {"Dt1Mask": "1631"},     # level 165's Lava files + Intwalls
          "travincal": {"Dt1Mask": "53512"},   # level 148's files + Kurast Terraces
          "dunes": {"Dt1Mask": "50397185"},    # Desert Town/Ground, Ruin/Ground + Column, Village
          "highlands": {"Dt1Mask": "65541"}}   # Wilderness Town/Floor, stonewall, Fallen
# The Throne of Destruction's automap layer (98) would share the real Throne
# room's saved map; keep the layer this arena has always used.
LEVEL = {"worldstone": {"Layer": "78"},
         # Andariel's layer (24) would share her lair's saved map; keep 0.
         "catacombs": {"Layer": "0"},
         # Level 165's row with the Mesa's tiles and wind instead of lava's.
         "steppes": {"LevelType": "27", "SoundEnv": "32"},
         # An open courtyard: Travincal's outdoor ambience, not the Durance's.
         "travincal": {"SoundEnv": "25"},
         # Level 138's row (slot-2 red portal) with the desert's tiles and wind.
         "dunes": {"LevelType": "16", "SoundEnv": "13"},
         # Level 158's row (slot-2 red portal) with the wilderness tiles and ambience.
         "highlands": {"LevelType": "2", "SoundEnv": "2"}}

KEEP_DT1S = [r"\d2\data\global\tiles\expansion\baallair\walls.dt1",
             r"\d2\data\global\tiles\expansion\baallair\floor.dt1"]
KEEP_SCENES = ("baalnewup01", "baalnsew01", "baale02", "baaledown01")
KEEP_PREFABS = "data/hd/env/model/expansion/baallair"
KEEP_FLOOR = 0x0000C2
KEEP_CORNER = 0x000081              # orientation 3 main 0 sub 0
KEEP_COLUMN = 0x000081              # orientation 12 main 0 sub 0: pillar01a

OBJ_BAAL_TORCH = 94                 # BaalTorch1, on a back-wall pillar
OBJ_BAAL_BRAZIER = 95               # BaalTorch2, freestanding

WORLDSTONE = {
    # Same footprint as the other sanctums: 20x20, walls outside it.
    "lo": 3, "hi": 22,
    "ring": (7, 18), "ring_gaps": (10, 15),
    "court": (9, 16),
    "stairs": 16,                   # stairs up on tiles 16-17 of the north wall
    "torches_north": (5, 9, 13, 21),
    "torches_west": (5, 9, 15, 19),
    "warden": (62, 62),
    "seed": 1159,
}


def _keep_wall(scene, t, line, north):
    """HD recipe of back-wall tile t on a wall line (north: a row at z=10*line,
    else a column at x=10*line); even tiles of the run are pillars."""
    x, z = (10 * t, 10 * line) if north else (10 * line, 10 * t)
    if t % 2 == 0:
        scene.add("pillar01a.model", x + 1.8, z + 1.5, 0)
    elif north:
        scene.add("wall01a.model", x + 0.3, z + 1.1, 270)
        scene.add("pillar02_wtrims_a.model", x + 1.1, z + 2.4, 270)
    else:
        scene.add("wall01a.model", x + 0.3, z + 1.1, 0)
        scene.add("pillar02_wtrims_a.model", x + 2.3, z + 1.0, 0)


def build_worldstone():
    s = WORLDSTONE
    lo, hi = s["lo"], s["hi"]
    back, front = lo - 1, hi + 1
    cells = front + 1
    rng = random.Random(s["seed"])
    room = Room(cells, cells, 4, KEEP_DT1S, void=0)
    kit = Kit("expansion/baallair", KEEP_SCENES, TERRAIN_SCENE)
    scene = Scene(kit, "data/hd/env/biome/expansion_baallair.json", cells, cells)
    stairs = (s["stairs"], s["stairs"] + 1)

    # ---- floor and legacy walls ------------------------------------------
    # Variants follow the tile's parity so the legacy art matches the HD
    # recipe: 0/2 pillar pieces on even tiles, 1/3 wall panels on odd ones.
    for y in range(back, front):
        for x in range(back, front):
            room.set_floor(x, y, KEEP_FLOOR)
    room.set_wall(back, back, ORIENT_CORNER, KEEP_CORNER)
    for t in range(lo, hi + 1):
        sub = (t % 4) << 8
        if t in stairs:
            room.set_wall(t, back, ORIENT_WARP, 0x81 | (t - stairs[0]) << 8)
        else:
            room.set_wall(t, back, ORIENT_TOP, 0x81 | sub)
        room.set_wall(back, t, ORIENT_LEFT, 0x81 | sub)
        room.set_wall(t, front, ORIENT_TOP, 0x100081 | (1 + t % 2) << 8)
        room.set_wall(front, t, ORIENT_LEFT, 0x100081 | (1 + t % 2) << 8)
    # The stock rooms end runs with front-wall variant 5 pieces.
    room.set_wall(front, back, ORIENT_LEFT, 0x100581)
    room.set_wall(back, front, ORIENT_TOP, 0x100581)
    room.set_wall(front, front, ORIENT_SOUTH_CORNER, 0x100081)

    # ---- HD walls: back recipes on all four sides --------------------------
    scene.add("pillar_corner_wtrim.model", 10 * back + 1.8, 10 * back + 2.0, 0)
    for t in range(lo, hi + 1):
        if t not in stairs:
            _keep_wall(scene, t, back, True)
        _keep_wall(scene, t, back, False)
        _keep_wall(scene, t, front, True)
        _keep_wall(scene, t, front, False)
    for x, y in ((front, back), (back, front)):
        scene.add("pillar01a.model", 10 * x + 1.8, 10 * y + 1.5, 0)
    scene.add("pillar_corner_wtrim.model", 10 * front + 1.8, 10 * front + 2.0, 0)

    # ---- stairs up (the return warp) -------------------------------------
    scene.add("stairs_up01.model", 10 * stairs[0] + 12, 10 * back + 0.1, 0)
    # Pillars flank the stairs: the first stairs tile's own (its wall recipe
    # is skipped) and the next tile's, unless its recipe is a pillar anyway.
    scene.add("pillar01a.model", 10 * stairs[0] + 1.8, 10 * back + 1.5, 0)
    if (stairs[1] + 1) % 2:
        scene.add("pillar01a.model", 10 * (stairs[1] + 1) + 1.8, 10 * back + 1.5, 0)

    # ---- torches on the back-wall pillars ----------------------------------
    for t in s["torches_north"]:
        room.add_object(2, OBJ_BAAL_TORCH, 5 * t, 5 * back + 3)
    for t in s["torches_west"]:
        room.add_object(2, OBJ_BAAL_TORCH, 5 * back + 3, 5 * t)

    # ---- pillar ring -----------------------------------------------------
    a, b = s["ring"]
    g1, g2 = s["ring_gaps"]
    for x, y in ((a, g1), (a, g2), (b, g1), (b, g2), (g1, a), (g2, a), (g1, b), (g2, b)):
        room.set_wall(x, y, ORIENT_COLUMN, KEEP_COLUMN)
        scene.add("pillar01a.model", 10 * x + 1.8, 10 * y + 1.5, 0)
    for x, y in ((a, a), (b, a), (a, b), (b, b)):
        room.add_object(2, OBJ_BAAL_BRAZIER, 5 * x + 2, 5 * y + 2)

    # ---- the court: the Worldstone's corruption breaks through -----------
    # Floor cracks spread from the Warden's feet (tile-aligned as in the
    # Worldstone Chamber: +6.6/+6.7), worldstone crystals erupt at the
    # court's corners and ritual candles burn between them.
    c0, c1 = s["court"]
    cracks = f"{KEEP_PREFABS}/Prefabs/floorTile_dam"
    for i, (x, y) in enumerate(((c0 + 2, c0 + 2), (c0 + 4, c0 + 2), (c0 + 2, c0 + 4), (c0 + 4, c0 + 4),
                                (c0 + 1, c0 + 5), (c0 + 5, c0 + 1), (c1 - 1, c1 - 1), (c0 + 3, c1))):
        scene.prefab(f"{cracks}/pf_floor_cracks0{i % 4 + 1}.json", 10 * x + 6.6, 10 * y + 6.7,
                     rng.choice((0, 90, 180, 270)))
    for x, y in ((c0 - 1, c0 + 3), (c1 + 1, c0 + 5), (c0 + 5, c1 + 1), (c0 + 3, c0 - 1)):
        scene.prefab(f"{cracks}/pf_floorTile_dam05.json", 10 * x + 6.6, 10 * y + 6.7, 0)
    crystals = f"{KEEP_PREFABS}/Prefabs/crystals"
    for i, (x, y) in enumerate(((c0, c0), (c1, c0), (c0, c1), (c1, c1))):
        scene.prefab(f"{crystals}/pf_crystals0{i + 1}.json", 10 * x + 5, 10 * y + 5, rng.uniform(0, 360))
    candles = f"{KEEP_PREFABS}/Prefabs/candles"
    for x, y in ((c0 + 3, c0), (c0, c0 + 4), (c1, c0 + 3), (c0 + 4, c1)):
        scene.prefab(f"{candles}/pf_candles0{rng.choice((1, 2))}.json", 10 * x + 5, 10 * y + 5,
                     rng.uniform(0, 360))

    # ---- the aisles: the fallen, rubble and hell spikes ------------------
    bodies = f"{KEEP_PREFABS}/Prefabs/bodies"
    for name, x, z in (("pf_body01", 10 * lo + 22, 10 * hi - 12), ("pf_body03", 10 * hi - 14, 10 * lo + 24),
                       ("pf_arm01", 10 * lo + 40, 10 * lo + 16), ("pf_leg01_arm02", 10 * hi - 30, 10 * hi - 4),
                       ("pf_body02", 10 * lo + 8, 10 * lo + 58)):
        scene.prefab(f"{bodies}/{name}.json", x, z, rng.uniform(0, 360))
    rubble = f"{KEEP_PREFABS}/expansion_baallair_rubble/prefab"
    for i, (x, z) in enumerate(((10 * lo + 4, 10 * hi + 2), (10 * hi + 2, 10 * lo + 4),
                                (10 * hi, 10 * hi), (10 * lo + 6, 10 * lo + 6))):
        scene.prefab(f"{rubble}/pf_rubble_pile0{i + 1}.json", x, z, rng.uniform(0, 360))
    spikes = f"{KEEP_PREFABS}/Prefabs/Spikes"
    for i, (x, z) in enumerate(((10 * lo + 14, 10 * lo + 36), (10 * lo + 36, 10 * lo + 14),
                                (10 * hi - 4, 10 * lo + 46), (10 * lo + 46, 10 * hi - 4))):
        scene.prefab(f"{spikes}/pf_spikes0{(2, 4, 6, 3)[i]}.json", x, z, rng.uniform(0, 360))
    # Corner rubble at the feet of back-wall pillars (stock: in the pillar's
    # corner, turned away from the wall).
    for t in range(lo + 1, hi + 1, 4):
        if t not in stairs and t + 1 not in stairs:
            scene.add("rubble_dirt01_cnr_conc01.model", 10 * t + 1.8, 10 * back + 2.0, 180)
        scene.add("rubble_dirt01_cnr_conc01.model", 10 * back + 2.0, 10 * t + 1.8, 90)

    # ---- atmosphere ------------------------------------------------------
    for _ in range(8):
        scene.add("FX_Act5BaalLair_fog_20x20.particles",
                  rng.uniform(10 * lo, 10 * hi + 10), rng.uniform(10 * lo, 10 * hi + 10))
    for _ in range(6):
        scene.add("FX_Act5BaalLair_mist_20x20.particles",
                  rng.uniform(10 * lo, 10 * hi + 10), rng.uniform(10 * lo, 10 * hi + 10))

    # Placeholder monster: boss_rooms.clone replaces it with the Warden.
    room.add_object(1, 0, *s["warden"])
    return room.to_bytes(), scene.to_bytes()


# --------------------------------------------------------------------------
# Forsaken Catacombs: the Warden's ossuary chapel
# --------------------------------------------------------------------------
# Act 1 Catacombs tiles (LevelType 10). One full wall style (Basewalls main
# 0) serves every side, so the legacy room is walled all round too. Per tile
# the stock rooms (catewup, catnsew3, andy3 ...) carry:
#
# * A wall panel 2.5 units in from the wall line: (+7.5, +2.5) on a north
#   wall, (+2.5, +7.5) on a west wall. Yaw depends on the model: the
#   wall01/painting/cabinet family turns 90 (north) / 180 (west), wall_plain
#   270 / 0.
# * pillar01 + pillar_cap01 at (+2.5, +2.5) on corners, run ends and column
#   tiles; the back corner adds corner_column01 at (+4, +4).
# * Stairs up (lvlwarp 17, Vis slot 0): two orientation 11 main 0 warp tiles
#   in a north wall, stairs02 + pf_stairs01 at (+2.5, +2.5) of the second.
# * Andariel's Lair seats a bone throne on a north wall tile seam, 5 units
#   out, with pf_bonebanner01/02 at 11 and 8 units either side.
CAT_DT1S = [rf"\d2\data\global\tiles\act1\catacomb\{n}.dt1" for n in ("basewalls", "upstr", "floor")]
CAT_SCENES = ("catewup", "andy3", "catnsew3", "catnsup", "catewup4")
CAT_WALL = 0x000081                 # orientations 1/2/3/5/6/7/12, main 0 sub 0
CAT_FLOOR = 0x0000C2
# (model, north-wall yaw, west-wall yaw)
CAT_PANELS = (("wall01.model", 90, 180), ("wall_plain.model", 270, 0))
CAT_DRESSED = (("wall_painting01.model", 90, 180), ("wall_painting03.model", 90, 180),
               ("wall_cabient03.model", 90, 180))
CAT_PROPS = "data/hd/env/model/act1/catacomb/act1_catacomb_props"

# Act 1 objpreset indices (the room is stamped Act 1; boss_rooms.clone moves
# them into the Act 5 namespace by class).
OBJ_CAT_TORCH = 1                   # TikiTorch1
OBJ_CAT_BRAZIER = 17                # Brazier
OBJ_CAT_CANDLES = (19, 20)          # Candles1, Candles2
OBJ_BLOOD_POOL = 28                 # BubblingBloodPool
OBJ_STAKED_ROGUES = (70, 71)        # RogueStakedCorpse1/2

CATACOMBS = {
    # Same footprint as the other sanctums: 20x20, walls outside it.
    "lo": 3, "hi": 22,
    # A nave runs from the stairs' side west to the throne between two rows
    # of pillars; aisles lie north and south of it.
    "pillar_rows": (7, 18), "pillar_cols": (8, 12, 16, 20),
    "stairs": 17,                   # stairs up on tiles 17-18 of the north wall
    "throne_seam": 13,              # the throne sits on the west wall at z = 10 * seam
    "dressed_north": (5, 9, 13, 21),
    "dressed_west": (5, 8, 17, 20),
    "warden": (22, 64),             # subtiles: before the throne
    "seed": 1117,
}


def _cat_panel(scene, choice, t, line, north):
    model, north_yaw, west_yaw = choice
    if north:
        scene.add(model, 10 * t + 7.5, 10 * line + 2.5, north_yaw)
    else:
        scene.add(model, 10 * line + 2.5, 10 * t + 7.5, west_yaw)


def _cat_pillar(scene, x, y):
    scene.add("pillar01.model", 10 * x + 2.5, 10 * y + 2.5, 0)
    scene.add("pillar_cap01.model", 10 * x + 2.5, 10 * y + 2.5, 0)


def build_catacombs():
    s = CATACOMBS
    lo, hi = s["lo"], s["hi"]
    back, front = lo - 1, hi + 1
    cells = front + 1
    rng = random.Random(s["seed"])
    room = Room(cells, cells, 0, CAT_DT1S, void=0)
    kit = Kit("act1/catacomb", CAT_SCENES, TERRAIN_SCENE)
    scene = Scene(kit, "data/hd/env/biome/act1_catacombs.json", cells, cells)
    stairs = (s["stairs"], s["stairs"] + 1)

    # ---- floor and legacy walls ------------------------------------------
    for y in range(back, front):
        for x in range(back, front):
            room.set_floor(x, y, CAT_FLOOR)
    room.set_wall(back, back, ORIENT_CORNER, CAT_WALL)
    room.set_wall(front, back, ORIENT_EAST_END, CAT_WALL)
    room.set_wall(back, front, ORIENT_WEST_END, CAT_WALL)
    room.set_wall(front, front, ORIENT_SOUTH_CORNER, CAT_WALL)
    for t in range(lo, hi + 1):
        if t in stairs:
            room.set_wall(t, back, ORIENT_WARP, 0x81 | (t - stairs[0]) << 8)
        else:
            room.set_wall(t, back, ORIENT_TOP, CAT_WALL)
        room.set_wall(back, t, ORIENT_LEFT, CAT_WALL)
        room.set_wall(t, front, ORIENT_TOP, CAT_WALL)
        room.set_wall(front, t, ORIENT_LEFT, CAT_WALL)

    # ---- HD walls: all four sides full, the back ones dressed -------------
    _cat_pillar(scene, back, back)
    scene.add("corner_column01.model", 10 * back + 4, 10 * back + 4, 0)
    _cat_panel(scene, CAT_PANELS[0], back, back, True)
    _cat_panel(scene, CAT_PANELS[0], back, back, False)
    for t in range(lo, hi + 1):
        if t not in stairs:
            dressed = t in s["dressed_north"]
            _cat_panel(scene, rng.choice(CAT_DRESSED if dressed else CAT_PANELS), t, back, True)
        dressed = t in s["dressed_west"]
        _cat_panel(scene, rng.choice(CAT_DRESSED if dressed else CAT_PANELS), t, back, False)
        _cat_panel(scene, rng.choice(CAT_PANELS), t, front, True)
        _cat_panel(scene, rng.choice(CAT_PANELS), t, front, False)
    for x, y in ((front, back), (back, front), (front, front)):
        _cat_pillar(scene, x, y)
    _cat_panel(scene, CAT_PANELS[1], back, front, True)      # south wall's first tile
    _cat_panel(scene, CAT_PANELS[0], back, front, False)     # east wall's first tile

    # ---- stairs up (the return warp) -------------------------------------
    sx, sz = 10 * stairs[1] + 2.5, 10 * back + 2.5
    scene.add("stairs02.model", sx, sz, 0)
    scene.add("pf_stairs01.json", sx, sz, 0)

    # ---- the throne ------------------------------------------------------
    # Andariel's arrangement turned to face east from the west wall: throne
    # 5 units out on the seam, banners 11 units north and 8 south of it.
    tz = 10 * s["throne_seam"]
    scene.add("bonethrone01.model", 10 * back + 5, tz, 90)
    scene.add("pf_bonebanner01.json", 10 * back + 3, tz + 11, 90)
    scene.add("pf_bonebanner02.json", 10 * back + 3, tz - 8, 90)
    for dz in (-16, 16):
        room.add_object(2, rng.choice(OBJ_CAT_CANDLES), 5 * back + 4, (tz + dz) // 2)
    for dz in (-26, 26):
        room.add_object(2, OBJ_CAT_BRAZIER, 5 * lo + 3, (tz + dz) // 2)
    scene.add("bloodbath01.model", 10 * lo + 22, tz, 90)
    for _ in range(5):
        scene.add(rng.choice(("gore01.model", "gore02.model", "gore03.model")),
                  10 * lo + rng.uniform(4, 30), tz + rng.uniform(-22, 22), rng.uniform(0, 360))

    # ---- the nave --------------------------------------------------------
    for y in s["pillar_rows"]:
        for x in s["pillar_cols"]:
            room.set_wall(x, y, ORIENT_COLUMN, CAT_WALL)
            _cat_pillar(scene, x, y)
    cols = s["pillar_cols"]
    for x in cols[1:]:
        for y in s["pillar_rows"]:
            room.add_object(2, OBJ_CAT_TORCH, 5 * x - 8, 5 * y + 2)
    for x, y in ((cols[1] + 2, s["throne_seam"]), (cols[3] - 2, s["throne_seam"] - 1)):
        room.add_object(2, OBJ_BLOOD_POOL, 5 * x + 3, 5 * y + 3)

    # ---- aisles: the Rogues who came before ------------------------------
    rows = s["pillar_rows"]
    for i, (x, y) in enumerate(((cols[0] + 2, lo + 1), (cols[2] + 1, lo + 2), (cols[1] + 1, rows[1] + 2),
                                (cols[3] - 1, rows[1] + 3))):
        room.add_object(2, OBJ_STAKED_ROGUES[i % 2], 5 * x + 2, 5 * y + 2)
    for _ in range(6):
        x = rng.uniform(10 * cols[0], 10 * hi + 5)
        z = rng.choice((rng.uniform(10 * lo + 5, 10 * rows[0] - 5), rng.uniform(10 * rows[1] + 15, 10 * hi + 5)))
        scene.add(rng.choice(("gore01.model", "gore02.model", "gore03.model", "gore04.model")),
                  x, z, rng.uniform(0, 360))
    for x, y in ((front - 1, front - 1), (front - 1, lo), (lo + 1, front - 1)):
        room.add_object(2, OBJ_CAT_BRAZIER, 5 * x + 2, 5 * y + 2)

    # ---- atmosphere ------------------------------------------------------
    for _ in range(6):
        scene.add("FX_Catacombs_FloorHaze_40x40.particles",
                  rng.uniform(10 * lo, 10 * hi + 10), rng.uniform(10 * lo, 10 * hi + 10))
    for _ in range(8):
        scene.add("FX_Catacombs_DustMotes_20x20.particles",
                  rng.uniform(10 * lo, 10 * hi + 10), rng.uniform(10 * lo, 10 * hi + 10))

    # Placeholder monster: boss_rooms.clone replaces it with the Warden.
    room.add_object(1, 0, *s["warden"])
    return room.to_bytes(), scene.to_bytes()


# --------------------------------------------------------------------------
# Ashen Steppes: the Warden's ruined bastion
# --------------------------------------------------------------------------
# Act 4 Mesa tiles (LevelType 27). No stock preset level uses them, so the
# arena keeps level 165's row (its slot-0 red portal, lvlwarp 83, is what the
# body links to) and arenas.LEVEL switches the tileset. The walls are the
# Plains of Despair ruins (the "chaos" presets): Brick_Walls main 13, one
# recipe per tile:
#
# * a ruined wall section, (+7.0, +2.5) yaw 0 on a north wall, (+1.7, +7.5)
#   yaw 90 on a west wall, with a wall_pillars01 at (+2.4, +3.8) yaw 270 /
#   (+2.8, +2.7) yaw 0;
# * wall_pillars_corner01 at (+2.5, +3.0) on corners;
# * Surf_Struct column tiles (orientation 12 main 11 sub 6) carry pillar02
#   at (+2.5, +3.0).
# Mesa floors are textured through the tile masks: main 10 sub 0 is the
# ruins' plain ground.
MESA_DT1S = [rf"\d2\data\global\tiles\act4\mesa\{n}.dt1" for n in ("floor", "brick_walls", "surf_struct")]
MESA_SCENES = ("chaos24x24_1", "chaos08x08_0", "chaos16x16_0", "border5a", "outer08x08_4")
MESA_FLOOR = 0xA000C2
MESA_TOP, MESA_LEFT = 0xD00081, 0xD00081       # orientations 2 / 1, main 13 sub 0
MESA_CORNER = 0xD00081                          # orientation 3, main 13 sub 0
MESA_EAST_END = 0xD00081                        # orientation 5, main 13 sub 0
MESA_WEST_END = 0xD00081                        # orientation 6, main 13 sub 0
MESA_SOUTH_CORNER = 0xD00481                    # orientation 7, main 13 sub 4
MESA_COLUMN = 0xB00681                          # orientation 12, main 11 sub 6
ORIENT_WARP_WEST = 10

# Act 4 objpreset indices (the room is stamped Act 4; boss_rooms.clone moves
# them into the Act 5 namespace by class).
OBJ_HELLFIRES = (8, 9, 10)          # Hellfire1-3: bonfires
OBJ_HELL_BRAZIERS = (17, 18, 56)    # HellBrazier1-3
OBJ_HELL_LIGHT = 16                 # HellLight3
OBJ_HELL_SMOKE = 55
OBJ_DAMNED = (58, 59)               # DamnedV1/V2: impaled souls
OBJ_SKULL_PILE = 34

STEPPES = {
    # Same footprint as the other sanctums: 20x20, walls outside it.
    "lo": 3, "hi": 22,
    "ring": (7, 18), "ring_gaps": (10, 15),
    "court": (9, 16),
    "warden": (62, 62),
    "portal": (19, 19),             # red portal in the south corner
    "warp_slot": 0,
    "seed": 1147,
}


def _mesa_wall(scene, rng, walls, t, line, north):
    """Ruin wall recipe of tile t on a wall line (a row at z=10*line when
    north, else a column at x=10*line)."""
    model = rng.choice(walls)
    if north:
        scene.add(model, 10 * t + 7.0, 10 * line + 2.5, 0)
        scene.add("wall_pillars01.model", 10 * t + 2.4, 10 * line + 3.8, 270)
    else:
        scene.add(model, 10 * line + 1.7, 10 * t + 7.5, 90)
        scene.add("wall_pillars01.model", 10 * line + 2.8, 10 * t + 2.7, 0)


def build_steppes():
    s = STEPPES
    lo, hi = s["lo"], s["hi"]
    back, front = lo - 1, hi + 1
    cells = front + 1
    rng = random.Random(s["seed"])
    room = Room(cells, cells, 3, MESA_DT1S, void=0)
    kit = Kit("act4/mesa", MESA_SCENES, TERRAIN_SCENE)
    scene = Scene(kit, "data/hd/env/biome/act4_mesa.json", cells, cells)
    walls = sorted(k for k in kit.templates
                   if re.fullmatch(r"ruin_walls_(large|medium)_staged\d\d\.model", k))

    # ---- floor and legacy walls ------------------------------------------
    for y in range(back, front):
        for x in range(back, front):
            room.set_floor(x, y, MESA_FLOOR)
    room.set_wall(back, back, ORIENT_CORNER, MESA_CORNER)
    room.set_wall(front, back, ORIENT_EAST_END, MESA_EAST_END)
    room.set_wall(back, front, ORIENT_WEST_END, MESA_WEST_END)
    room.set_wall(front, front, ORIENT_SOUTH_CORNER, MESA_SOUTH_CORNER)
    for t in range(lo, hi + 1):
        room.set_wall(t, back, ORIENT_TOP, MESA_TOP)
        room.set_wall(back, t, ORIENT_LEFT, MESA_LEFT)
        room.set_wall(t, front, ORIENT_TOP, MESA_TOP)
        room.set_wall(front, t, ORIENT_LEFT, MESA_LEFT)

    # ---- HD walls: ruins on all four sides -------------------------------
    for t in range(lo, hi + 1):
        for line, north in ((back, True), (back, False), (front, True), (front, False)):
            _mesa_wall(scene, rng, walls, t, line, north)
    for x, y in ((back, back), (front, back), (back, front), (front, front)):
        scene.add("wall_pillars_corner01.model", 10 * x + 2.5, 10 * y + 3.0, 0)

    # ---- pillar ring and hell braziers -----------------------------------
    a, b = s["ring"]
    g1, g2 = s["ring_gaps"]
    for x, y in ((a, g1), (a, g2), (b, g1), (b, g2), (g1, a), (g2, a), (g1, b), (g2, b)):
        room.set_wall(x, y, ORIENT_COLUMN, MESA_COLUMN)
        scene.add("pillar02.model", 10 * x + 2.5, 10 * y + 3.0, 0)
    for x, y in ((a, a), (b, a), (a, b), (b, b)):
        room.add_object(2, rng.choice(OBJ_HELL_BRAZIERS), 5 * x + 2, 5 * y + 2)

    # ---- the court: a scorched killing floor -----------------------------
    c0, c1 = s["court"]
    wx, wy = s["warden"]
    for dx, dy in ((-14, 0), (14, 0), (0, -14), (0, 14)):
        room.add_object(2, OBJ_HELL_LIGHT, wx + dx, wy + dy)
    for x, z in ((10 * c0 + 4, 10 * c0 + 30), (10 * c1 + 4, 10 * c0 + 46), (10 * c0 + 34, 10 * c1 + 6)):
        scene.add("skeleton_pile02.model", x, z, rng.uniform(0, 360))
    for _ in range(6):
        scene.add(rng.choice(("rubble_pile01.model", "rubble_pile02.model", "rubble_pile03.model")),
                  rng.uniform(10 * c0, 10 * c1 + 10), rng.uniform(10 * c0, 10 * c1 + 10), rng.uniform(0, 360))

    # ---- the aisles: bonfires, the impaled and the chained ----------------
    for x, y in ((lo + 1, lo + 1), (hi - 1, lo + 1), (lo + 1, hi - 1), (c0 + 3, lo + 1), (lo + 1, c0 + 3)):
        room.add_object(2, rng.choice(OBJ_HELLFIRES), 5 * x + 2, 5 * y + 2)
    for i, (x, y) in enumerate(((c0 + 1, lo + 2), (lo + 2, c1 - 1), (hi - 1, c0 + 2), (c1, hi - 1))):
        room.add_object(2, OBJ_DAMNED[i % 2], 5 * x + 2, 5 * y + 2)
    for x, y in ((lo + 2, lo + 4), (hi - 3, hi - 1)):
        room.add_object(2, OBJ_SKULL_PILE, 5 * x + 2, 5 * y + 2)
    for x, y in ((lo, c1), (c1, lo)):
        room.add_object(2, OBJ_HELL_SMOKE, 5 * x + 3, 5 * y + 3)
    for t in range(lo + 2, hi, 4):
        scene.add(rng.choice(("spike_chain_small01.model", "spike_chain_medium01.model")),
                  10 * t + rng.uniform(2, 8), 10 * lo + rng.uniform(2, 5), rng.uniform(0, 360))
        scene.add(rng.choice(("spike_chain_small01.model", "spike_chain_medium01.model")),
                  10 * lo + rng.uniform(2, 5), 10 * t + rng.uniform(2, 8), rng.uniform(0, 360))
    for _ in range(10):
        x, z = rng.uniform(10 * lo, 10 * hi + 10), rng.uniform(10 * lo, 10 * hi + 10)
        if 10 * c0 - 5 < x < 10 * c1 + 15 and 10 * c0 - 5 < z < 10 * c1 + 15:
            continue
        scene.add(rng.choice(("rubble_pile03.model", "rubble_pile06.model", "grounding_pile01.model")),
                  x, z, rng.uniform(0, 360))

    # ---- atmosphere ------------------------------------------------------
    for _ in range(8):
        scene.add("FX_Act4Mesa_Wind_Small_10x10.particles",
                  rng.uniform(10 * lo, 10 * hi + 10), rng.uniform(10 * lo, 10 * hi + 10))
    for _ in range(3):
        scene.add("FX_Act4Mesa_Wind_Huge_40x40.particles",
                  rng.uniform(10 * lo, 10 * hi + 10), rng.uniform(10 * lo, 10 * hi + 10))

    # ---- return warp and the Warden --------------------------------------
    # The red portal the Labyrinth's Heart room used on slot 0: an
    # orientation 10 warp tile, drawn in HD by the town portal effect.
    px, py = s["portal"]
    room.set_wall(px, py, ORIENT_WARP_WEST, 0x81 | s["warp_slot"] << 20)
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
    room.add_object(1, 0, wx, wy)
    return room.to_bytes(), scene.to_bytes()


# --------------------------------------------------------------------------
# Infernal Rift: the Warden's hellforge
# --------------------------------------------------------------------------
# The Infernal Pit / Pit of Acheron / Abaddon fortress rooms (act4/expansion,
# lavae ... lavaw2). Their walls are Lava/Intwalls.dt1 main 22, which the
# Act 4 Lava tileset (LevelType 28) of level 165's row already lists, and per
# tile they carry:
#
# * wall01 at (+8.1, +3.2) yaw 180 on a north wall, (+3.1, +8.2) yaw 270 on a
#   west wall; variants 9/11/13 are plain,
# * variants 8/10/12 add pillar01_staged01 at (+5.9, +6.2) yaw 0 on a north
#   wall, (+5.9, +5.2) yaw 90 on a west wall.
# Intwalls has no corner tiles, so the back corner stacks a north and a west
# piece in two wall layers. Intwalls' column tile (12, 22, 1) blocks a 3x3
# subtile patch under a pillar02_blank at (+3.7, +7.0). Floors are Lava
# main 20, variants 0-7.
LAVA_DT1S = [rf"\d2\data\global\tiles\act4\lava\{n}.dt1" for n in ("floor", "intwalls")]
# Infernal Pit rooms first: their wall01 is the one these offsets belong to
# (the River of Flame rooms have another model of that name).
LAVA_SCENES = ("expansion/lavae", "expansion/lavaew", "expansion/lavans",
               "lava/lavaew", "lava/lavanew", "lava/lavae2")
LAVA_FLOOR = 0x14000C2              # main 20, | variant << 8
LAVA_WALL = 0x1600081               # orientations 1/2, main 22, | variant << 8
LAVA_COLUMN = 0x1600181             # orientation 12, main 22 sub 1

# Act 4 objpreset indices (the room is stamped Act 4; boss_rooms.clone moves
# them into the Act 5 namespace by class).
OBJ_LAVA_FIRES = (8, 9, 10)         # Hellfire1-3
OBJ_HELL_BRAZIER4 = 62
OBJ_FLOOR_BRAZIER = 63

INFERNAL = {
    # Same footprint as the other sanctums: 20x20, walls outside it.
    "lo": 3, "hi": 22,
    "ring": (7, 18), "ring_gaps": (10, 15),
    "court": (9, 16),
    "warden": (62, 62),
    "portal": (19, 19),             # red portal in the south corner
    "warp_slot": 0,
    "seed": 1163,
}


def _lava_wall(room, scene, t, line, north, legacy=True):
    """Legacy tile and HD recipe of wall tile t on a wall line; even tiles
    carry a pillar."""
    pillar = t % 2 == 0
    if north:
        if legacy:
            room.set_wall(t, line, ORIENT_TOP, LAVA_WALL | (10 if pillar else 9) << 8)
        scene.add("wall01.model", 10 * t + 8.1, 10 * line + 3.2, 180)
        if pillar:
            scene.add("pillar01_staged01.model", 10 * t + 5.9, 10 * line + 6.2, 0)
    else:
        if legacy:
            room.set_wall(line, t, ORIENT_LEFT, LAVA_WALL | (10 if pillar else 9) << 8)
        scene.add("wall01.model", 10 * line + 3.1, 10 * t + 8.2, 270)
        if pillar:
            scene.add("pillar01_staged01.model", 10 * line + 5.9, 10 * t + 5.2, 90)


def build_infernal():
    s = INFERNAL
    lo, hi = s["lo"], s["hi"]
    back, front = lo - 1, hi + 1
    cells = front + 1
    rng = random.Random(s["seed"])
    room = Room(cells, cells, 3, LAVA_DT1S, void=0)
    kit = Kit("act4", LAVA_SCENES, TERRAIN_SCENE)
    scene = Scene(kit, "data/hd/env/biome/act4_lava.json", cells, cells)

    # ---- floor -----------------------------------------------------------
    for y in range(back, front):
        for x in range(back, front):
            room.set_floor(x, y, LAVA_FLOOR | rng.randrange(8) << 8)

    # ---- walls: all four sides; the back corner takes both pieces --------
    _lava_wall(room, scene, back, back, True)
    room.set_wall(back, back, ORIENT_LEFT, LAVA_WALL | 10 << 8, layer=1)
    scene.add("wall01.model", 10 * back + 3.1, 10 * back + 8.2, 270)
    for t in range(lo, hi + 1):
        _lava_wall(room, scene, t, back, True)
        _lava_wall(room, scene, t, back, False)
    # The south wall runs under both far corners; the east wall reaches up to
    # the north wall's row.
    for t in range(back, front + 1):
        _lava_wall(room, scene, t, front, True)
    for t in range(back, hi + 1):
        _lava_wall(room, scene, t, front, False)

    # ---- pillar ring and hell braziers -----------------------------------
    a, b = s["ring"]
    g1, g2 = s["ring_gaps"]
    for x, y in ((a, g1), (a, g2), (b, g1), (b, g2), (g1, a), (g2, a), (g1, b), (g2, b)):
        room.set_wall(x, y, ORIENT_COLUMN, LAVA_COLUMN)
        scene.add("pillar02_blank.model", 10 * x + 3.7, 10 * y + 7.0, 0)
    for x, y in ((a, a), (b, a), (a, b), (b, b)):
        room.add_object(2, OBJ_HELL_BRAZIER4, 5 * x + 2, 5 * y + 2)

    # ---- the court: the rift glows through a shattered floor -------------
    c0, c1 = s["court"]
    wx, wy = s["warden"]
    for x, y in ((c0 + 2, c0 + 2), (c1 - 3, c0 + 3), (c0 + 3, c1 - 3), (c1 - 2, c1 - 2)):
        scene.add("tile_floor_3x3_damage.model", 10 * x + 5, 10 * y + 5, rng.choice((0, 90, 180, 270)))
    for _ in range(3):
        scene.add("FX_Act4Expansion_lavaglow_30x30.particles",
                  rng.uniform(10 * c0 + 10, 10 * c1), rng.uniform(10 * c0 + 10, 10 * c1))
    for i, (x, y) in enumerate(((c0, c0), (c1, c0), (c0, c1), (c1, c1))):
        scene.add(("crystal_cluster_large01.model", "crystal_spike_cluster01.model")[i % 2],
                  10 * x + 5, 10 * y + 5, rng.uniform(0, 360))
    for dx, dy in ((-10, 0), (10, 0)):
        room.add_object(2, OBJ_FLOOR_BRAZIER, wx + dx, wy + dy)

    # ---- the aisles: skull pillars, spikes, fires ------------------------
    for x, y in ((lo + 1, lo + 1), (hi - 1, lo + 1), (lo + 1, hi - 1), (hi - 1, hi - 1)):
        scene.add("skull_pillar01.model", 10 * x + 5, 10 * y + 5, rng.uniform(0, 360))
    for x, y in ((c0 + 3, lo + 1), (lo + 1, c0 + 3), (hi - 1, c1 - 3), (c1 - 3, hi - 1), (c1, lo + 2)):
        room.add_object(2, rng.choice(OBJ_LAVA_FIRES), 5 * x + 2, 5 * y + 2)
    for t in range(lo + 1, hi, 3):
        scene.add(rng.choice(("wall_spikes01.model", "wall_spikes02.model")),
                  10 * t + 5, 10 * lo + 1, 0)
        scene.add(rng.choice(("wall_spikes01.model", "wall_spikes02.model")),
                  10 * lo + 1, 10 * t + 5, 90)
    for _ in range(10):
        x, z = rng.uniform(10 * lo, 10 * hi + 10), rng.uniform(10 * lo, 10 * hi + 10)
        if 10 * c0 - 5 < x < 10 * c1 + 15 and 10 * c0 - 5 < z < 10 * c1 + 15:
            continue
        scene.add(rng.choice(("debris01.model", "debris02.model", "rock_spikes01.model")),
                  x, z, rng.uniform(0, 360))
    for _ in range(4):
        scene.add("FX_Act4Expansion_lavasplash.particles",
                  rng.uniform(10 * lo, 10 * hi + 10), rng.uniform(10 * lo, 10 * hi + 10))

    # ---- return warp and the Warden --------------------------------------
    px, py = s["portal"]
    room.set_wall(px, py, ORIENT_WARP_WEST, 0x81 | s["warp_slot"] << 20)
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
    room.add_object(1, 0, wx, wy)
    return room.to_bytes(), scene.to_bytes()


# --------------------------------------------------------------------------
# Corrupted Durance: the Warden's council chamber
# --------------------------------------------------------------------------
# Durance of Hate tiles (LevelType 22: Travincal Walls.dt1 main 48). Per tile
# the stock Durance rooms (mephns, mephnwarpu ...) carry, on a north wall /
# a west wall:
#
# * round-pillar tiles: round_pillar01 + pillar_top01 at (+2.0, +3.0) yaw 270
#   / (+3.0, +2.0) yaw 0;
# * wall tiles: wall01 at (+2.0, +3.5) / (+3.5, +2.0), twice, the second
#   mirrored (scale z -1) so both faces are finished, with square_pillar01 at
#   (+2.0, +5.0) / (+5.0, +2.0) and spikes01 on the wall;
# * pillar_top_corner01 over a round pillar at the back corner (+3, +3),
#   pillar_top_corner02 over one at the far ends and the front corner.
# Stairs up (lvlwarp 65, Vis slot 2 as in the Durance's last level) exist
# only as west-wall warp tiles (orientation 10, main 2): door_stairs_up01 at
# (+6, +4) of the first, yaw 270.
DURANCE_DT1S = [r"\d2\data\global\tiles\act3\kurast\floors.dt1",
                r"\d2\data\global\tiles\act3\travincal\floors.dt1",
                r"\d2\data\global\tiles\act3\travincal\walls.dt1"]
DURANCE_SCENES = ("mephns", "mephnwarpu", "mephnsew", "mephe", "mephnw")
DURANCE_PROPS = "data/hd/env/model/global/prop/act3/travincal/prefabs"
DURANCE_FLOOR = 0x14000C2           # Kurast Floors.dt1 main 20 sub 0
DURANCE_WALL = 0x3000081            # orientations 1/2/3/5/6/7, main 48, | variant << 8
DURANCE_COLUMN = 0x2E00081          # orientation 12, Floors.dt1 main 46 sub 0: 3x3 subtiles
MIRROR = {"x": 1.0, "y": 1.0, "z": -1.0}

# Act 3 objpreset indices (the room is stamped Act 3; boss_rooms.clone moves
# them into the Act 5 namespace by class).
OBJ_DURANCE_BRAZIER = 4             # FloorBrazier
OBJ_DURANCE_TORCH = 99              # TorchAct2

DURANCE = {
    # Same footprint as the other sanctums: 20x20, walls outside it.
    "lo": 3, "hi": 22,
    "ring": (7, 18), "ring_gaps": (10, 15),
    "court": (9, 16),
    "stairs": 17,                   # stairs up on tiles 17-18 of the west wall
    "torches": (5, 9, 13),          # along both back walls
    "warden": (62, 62),
    "warp_slot": 2,
    "seed": 1181,
}


def _durance_wall(scene, t, line, north):
    """HD recipe of wall tile t on a wall line (a row at z=10*line when
    north, else a column at x=10*line); even tiles are round pillars."""
    x, z = (10 * t, 10 * line) if north else (10 * line, 10 * t)
    yaw = 270 if north else 0
    if t % 2 == 0:
        dx, dz = (2.0, 3.0) if north else (3.0, 2.0)
        scene.add("round_pillar01.model", x + dx, z + dz, yaw)
        scene.add("pillar_top01.model", x + dx, z + dz, yaw)
        return
    dx, dz = (2.0, 3.5) if north else (3.5, 2.0)
    scene.add("wall01.model", x + dx, z + dz, yaw)
    scene.add("wall01.model", x + dx, z + dz, yaw, scale=MIRROR)
    scene.add("spikes01.model", x + dx, z + dz, yaw)
    px, pz = (2.0, 5.0) if north else (5.0, 2.0)
    scene.add("square_pillar01.model", x + px, z + pz, yaw)


def _durance_corner(scene, x, y, cap, cap_yaw, pillar_yaw, dx, dz):
    scene.add(cap, 10 * x + dx, 10 * y + dz, cap_yaw)
    scene.add("round_pillar01.model", 10 * x + dx, 10 * y + dz, pillar_yaw)


def build_durance():
    s = DURANCE
    lo, hi = s["lo"], s["hi"]
    back, front = lo - 1, hi + 1
    cells = front + 1
    rng = random.Random(s["seed"])
    room = Room(cells, cells, 2, DURANCE_DT1S, void=0)
    kit = Kit("act3/travincal", DURANCE_SCENES, TERRAIN_SCENE)
    scene = Scene(kit, "data/hd/env/biome/act3_travincal.json", cells, cells)
    stairs = (s["stairs"], s["stairs"] + 1)

    # ---- floor and legacy walls: full walls on every side -----------------
    for y in range(back, front):
        for x in range(back, front):
            room.set_floor(x, y, DURANCE_FLOOR)
    room.set_wall(back, back, ORIENT_CORNER, DURANCE_WALL)
    room.set_wall(front, back, ORIENT_EAST_END, DURANCE_WALL)
    room.set_wall(back, front, ORIENT_WEST_END, DURANCE_WALL)
    room.set_wall(front, front, ORIENT_SOUTH_CORNER, DURANCE_WALL)
    for t in range(lo, hi + 1):
        top, left = (2, 3) if t % 2 == 0 else (3, 2)   # round pillar / wall variants
        room.set_wall(t, back, ORIENT_TOP, DURANCE_WALL | top << 8)
        if t in stairs:
            room.set_wall(back, t, ORIENT_WARP_WEST, 0x81 | s["warp_slot"] << 20 | (t == stairs[0]) << 8)
        else:
            room.set_wall(back, t, ORIENT_LEFT, DURANCE_WALL | left << 8)
        room.set_wall(t, front, ORIENT_TOP, DURANCE_WALL | top << 8)
        room.set_wall(front, t, ORIENT_LEFT, DURANCE_WALL | left << 8)

    # ---- HD walls --------------------------------------------------------
    for t in range(lo, hi + 1):
        _durance_wall(scene, t, back, True)
        if t not in stairs:
            _durance_wall(scene, t, back, False)
        _durance_wall(scene, t, front, True)
        _durance_wall(scene, t, front, False)
    _durance_corner(scene, back, back, "pillar_top_corner01.model", 0, 315, 3.0, 3.0)
    scene.add("wall01.model", 10 * back + 2.0, 10 * back + 3.5, 270)
    _durance_corner(scene, front, back, "pillar_top_corner02.model", 90, 45, 3.0, 2.5)
    _durance_corner(scene, back, front, "pillar_top_corner02.model", 270, 45, 2.5, 3.0)
    _durance_corner(scene, front, front, "pillar_top_corner02.model", 0, 315, 2.0, 2.0)

    # ---- stairs up (the return warp) -------------------------------------
    scene.add("door_stairs_up01.model", 10 * back + 6, 10 * stairs[0] + 4, 270)
    for t in (stairs[0], stairs[1] + 1):
        if t % 2:
            scene.add("round_pillar01.model", 10 * back + 3.0, 10 * t + 2.0, 0)
            scene.add("pillar_top01.model", 10 * back + 3.0, 10 * t + 2.0, 0)

    # ---- torches, and the dead the Durance keeps on its walls -------------
    for t in s["torches"]:
        room.add_object(2, OBJ_DURANCE_TORCH, 5 * t + 2, 5 * back + 2)
        room.add_object(2, OBJ_DURANCE_TORCH, 5 * back + 2, 5 * t + 2)
    corpses = f"{DURANCE_PROPS}/torturedcorpses"
    for i, t in enumerate((6, 11, 16, 21)):
        scene.prefab(f"{corpses}/pf_torturedcorpse0{(1, 3, 5, 8)[i]}.json", 10 * t + 5, 10 * lo + 2, 0)
    for i, t in enumerate((7, 12)):
        scene.prefab(f"{corpses}/pf_torturedcorpse0{(2, 6)[i]}.json", 10 * lo + 2, 10 * t + 5, 90)

    # ---- pillar ring and braziers ----------------------------------------
    a, b = s["ring"]
    g1, g2 = s["ring_gaps"]
    for x, y in ((a, g1), (a, g2), (b, g1), (b, g2), (g1, a), (g2, a), (g1, b), (g2, b)):
        room.set_wall(x, y, ORIENT_COLUMN, DURANCE_COLUMN)
        scene.add("round_pillar01.model", 10 * x + 3.0, 10 * y + 3.0, 0)
        scene.add("pillar_top01.model", 10 * x + 3.0, 10 * y + 3.0, 0)
    for x, y in ((a, a), (b, a), (a, b), (b, b)):
        room.add_object(2, OBJ_DURANCE_BRAZIER, 5 * x + 2, 5 * y + 2)

    # ---- the court: a blood-soaked council floor --------------------------
    c0, c1 = s["court"]
    floors = f"{DURANCE_PROPS}/floorsetdressed"
    for i, (x, y) in enumerate(((c0 + 1, c0 + 2), (c1 - 2, c0 + 1), (c0 + 2, c1 - 2), (c1 - 1, c1 - 1),
                                (c0 + 4, c0 + 4))):
        scene.prefab(f"{floors}/pf_bloodyfloor{(1, 5, 8, 12, 16)[i]:02d}.json", 10 * x + 5, 10 * y + 5,
                     rng.uniform(0, 360))
    for x, y in ((c0, c0), (c1, c0), (c0, c1), (c1, c1)):
        room.add_object(2, OBJ_DURANCE_BRAZIER, 5 * x + 2, 5 * y + 2)
    limbs = f"{DURANCE_PROPS}/torturedcorpses"
    for x, z in ((10 * lo + 24, 10 * hi - 10), (10 * hi - 12, 10 * lo + 26), (10 * hi - 28, 10 * hi - 4)):
        scene.prefab(f"{limbs}/pf_corpselimbs0{rng.choice((1, 2))}.json", x, z, rng.uniform(0, 360))
    for _ in range(12):
        x, z = rng.uniform(10 * lo, 10 * hi + 10), rng.uniform(10 * lo, 10 * hi + 10)
        scene.add(rng.choice(("gore01.model", "gore02.model", "gore03.model", "gore04.model", "gore05.model")),
                  x, z, rng.uniform(0, 360))

    # ---- atmosphere ------------------------------------------------------
    for _ in range(8):
        scene.add("FX_Act3Travincal_Fog_20x20.particles",
                  rng.uniform(10 * lo, 10 * hi + 10), rng.uniform(10 * lo, 10 * hi + 10))
    for _ in range(4):
        scene.add("FX_Act3Travincal_FlatFog_30x30.particles",
                  rng.uniform(10 * lo, 10 * hi + 10), rng.uniform(10 * lo, 10 * hi + 10))

    # Placeholder monster: boss_rooms.clone replaces it with the Warden.
    room.add_object(1, 0, *s["warden"])
    return room.to_bytes(), scene.to_bytes()


# --------------------------------------------------------------------------
# Fallen Travincal: the High Council's courtyard
# --------------------------------------------------------------------------
# Travincal / Kurast tiles (LevelType 22). The courtyard is walled by the
# stone terraces Travincal and Kurast are built on: Kurast Terraces.dt1 main
# 31 (blocks walking, not sight). Across the stock Kurast and Travincal
# presets the terrace tiles carry, on a north / west edge:
#
# * wall_elevation_stone01 at (+7.5, +4.5) yaw 90 / (+4.5, +7.5) yaw 180,
# * wall_stone_buttress01 at (+7.5, +4.0) yaw 90 / (+4.0, +7.5) yaw 180,
# * the back corner a wall_stone_buttress_corner01 at (+4, +4) yaw 180.
# Spiked stone pillars (round_pillar_stone01 + pillar_top_stone01 +
# spikes_stone01) crown the terraces here and there, as in travs.
TRAV_DT1S = [r"\d2\data\global\tiles\act3\kurast\floors.dt1",
             r"\d2\data\global\tiles\act3\kurast\terraces.dt1",
             r"\d2\data\global\tiles\act3\travincal\floors.dt1"]
TRAV_SCENES = ("travs", "travn", "travnw")
TRAV_FLOOR = 0x14000C2              # Kurast Floors.dt1 main 20 sub 0: the plaza stone
TRAV_TERRACE = 0x1F00081            # orientations 1/2/3/5/6/7, main 31 sub 0
TRAV_COLUMN = 0x2E00081             # orientation 12, Travincal Floors.dt1 main 46 sub 0

# Act 3 objpreset indices.
OBJ_JUNGLE_BRAZIER = 0

TRAVINCAL = {
    # Same footprint as the other sanctums: 20x20, walls outside it.
    "lo": 3, "hi": 22,
    "ring": (7, 18), "ring_gaps": (10, 15),
    "court": (9, 16),
    "spiked": (4, 8, 12, 16, 20),   # spiked stone pillars along both back terraces
    "warden": (62, 62),
    "portal": (19, 19),             # red portal in the south corner
    # The Mephisto chamber's slot-2 red portal as the old arena encoded it:
    # a hidden orientation 11 warp tile.
    "portal_cell": 0x80200081,
    "seed": 1191,
}


def _terrace(scene, t, line, north):
    if north:
        scene.add("wall_elevation_stone01.model", 10 * t + 7.5, 10 * line + 4.5, 90)
        scene.add("wall_stone_buttress01.model", 10 * t + 7.5, 10 * line + 4.0, 90)
    else:
        scene.add("wall_elevation_stone01.model", 10 * line + 4.5, 10 * t + 7.5, 180)
        scene.add("wall_stone_buttress01.model", 10 * line + 4.0, 10 * t + 7.5, 180)


def _stone_pillar(scene, x, z, spikes=True):
    scene.add("round_pillar_stone01.model", x, z, 0)
    scene.add("pillar_top_stone01.model", x, z, 0)
    if spikes:
        scene.add("spikes_stone01.model", x + 0.5, z - 0.5, 0)


def build_travincal():
    s = TRAVINCAL
    lo, hi = s["lo"], s["hi"]
    back, front = lo - 1, hi + 1
    cells = front + 1
    rng = random.Random(s["seed"])
    room = Room(cells, cells, 2, TRAV_DT1S, void=0)
    kit = Kit("act3/travincal", TRAV_SCENES, TERRAIN_SCENE)
    scene = Scene(kit, "data/hd/env/biome/act3_travincal_outdoors.json", cells, cells)

    # ---- floor and legacy terraces ---------------------------------------
    for y in range(back, front):
        for x in range(back, front):
            room.set_floor(x, y, TRAV_FLOOR)
    room.set_wall(back, back, ORIENT_CORNER, TRAV_TERRACE)
    room.set_wall(front, back, ORIENT_EAST_END, TRAV_TERRACE)
    room.set_wall(back, front, ORIENT_WEST_END, TRAV_TERRACE)
    room.set_wall(front, front, ORIENT_SOUTH_CORNER, TRAV_TERRACE)
    for t in range(lo, hi + 1):
        room.set_wall(t, back, ORIENT_TOP, TRAV_TERRACE)
        room.set_wall(back, t, ORIENT_LEFT, TRAV_TERRACE)
        room.set_wall(t, front, ORIENT_TOP, TRAV_TERRACE)
        room.set_wall(front, t, ORIENT_LEFT, TRAV_TERRACE)

    # ---- HD terraces on all four sides -----------------------------------
    scene.add("wall_elevation_stone01.model", 10 * back + 7.5, 10 * back + 4.5, 90)
    scene.add("wall_stone_buttress_corner01.model", 10 * back + 4.0, 10 * back + 4.0, 180)
    for t in range(lo, hi + 1):
        for line, north in ((back, True), (back, False), (front, True), (front, False)):
            _terrace(scene, t, line, north)
    for x, y in ((front, back), (back, front), (front, front)):
        scene.add("wall_stone_buttress_corner01.model", 10 * x + 4.0, 10 * y + 4.0, 180)
    for t in s["spiked"]:
        _stone_pillar(scene, 10 * t + 5, 10 * back + 3.5)
        _stone_pillar(scene, 10 * back + 3.5, 10 * t + 5)
    for t in (lo + 1, hi - 1):
        room.add_object(2, OBJ_JUNGLE_BRAZIER, 5 * t + 2, 5 * lo + 2)
        room.add_object(2, OBJ_JUNGLE_BRAZIER, 5 * lo + 2, 5 * t + 2)

    # ---- pillar ring and floor braziers ----------------------------------
    a, b = s["ring"]
    g1, g2 = s["ring_gaps"]
    for x, y in ((a, g1), (a, g2), (b, g1), (b, g2), (g1, a), (g2, a), (g1, b), (g2, b)):
        room.set_wall(x, y, ORIENT_COLUMN, TRAV_COLUMN)
        _stone_pillar(scene, 10 * x + 3.0, 10 * y + 3.0)
    for x, y in ((a, a), (b, a), (a, b), (b, b)):
        room.add_object(2, OBJ_DURANCE_BRAZIER, 5 * x + 2, 5 * y + 2)

    # ---- the court: the Council's offerings and sacrifices ----------------
    c0, c1 = s["court"]
    for x, y in ((c0, c0), (c1, c0), (c0, c1), (c1, c1)):
        cx, cz = 10 * x + 5, 10 * y + 5
        scene.add(rng.choice(("idol02.model", "idol03.model")), cx, cz, rng.uniform(0, 360))
        scene.add("bowl04.model", cx + rng.uniform(-3, 3), cz + rng.uniform(-3, 3), rng.uniform(0, 360))
        scene.add("kurast_gold_ornate01.model", cx, cz + 3, rng.choice((0, 90)))
    for _ in range(6):
        scene.add(rng.choice(("grunge_blood_splatter03_150.model", "grunge_blood_footsteps01_100.model")),
                  rng.uniform(10 * c0, 10 * c1 + 10), rng.uniform(10 * c0, 10 * c1 + 10), rng.uniform(0, 360))
    for t in range(c0, c1 + 1, 2):
        for x, z, yaw in ((10 * t + 5, 10 * c0 - 2, 0), (10 * t + 5, 10 * c1 + 12, 0),
                          (10 * c0 - 2, 10 * t + 5, 90), (10 * c1 + 12, 10 * t + 5, 90)):
            scene.add("trim_stone_a.model", x, z, yaw)

    # ---- the jungle creeping back in -------------------------------------
    plants = ("cinchona02.model", "act3_clover01.model", "act3_epiphyte01.model", "act3_roots_ground01.model")
    for t in range(lo, hi + 1, 2):
        for x, z in ((10 * t + rng.uniform(1, 9), 10 * lo + rng.uniform(1, 5)),
                     (10 * lo + rng.uniform(1, 5), 10 * t + rng.uniform(1, 9))):
            if rng.random() < 0.6:
                scene.add(rng.choice(plants), x, z, rng.uniform(0, 360))
    for t in range(lo + 1, hi, 5):
        scene.add("act3_ivy_climbing02.model", 10 * t + 5, 10 * lo + 1, 0)
        scene.add("act3_ivy_climbing02.model", 10 * lo + 1, 10 * t + 5, 90)

    # ---- atmosphere ------------------------------------------------------
    for fx, count in (("FX_Act3Travincal_Fog_20x20.particles", 6), ("FX_Act3Travincal_Leaves_30x30.particles", 3),
                      ("FX_Act3Travincal_Motes_30x30.particles", 4)):
        for _ in range(count):
            scene.add(fx, rng.uniform(10 * lo, 10 * hi + 10), rng.uniform(10 * lo, 10 * hi + 10))

    # ---- return warp and the Warden --------------------------------------
    px, py = s["portal"]
    room.set_wall(px, py, ORIENT_WARP, s["portal_cell"])
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
    room.add_object(1, 0, *s["warden"])
    return room.to_bytes(), scene.to_bytes()


# --------------------------------------------------------------------------
# Sunscar Dunes: the Warden's sun-scorched ruin
# --------------------------------------------------------------------------
# An open-air courtyard of the Lost City, half buried in sand: sandstone
# walls on all four sides, two colossi in the middle of the back walls, a
# ring of sandstone pillars around Tal Rasha's seal and two Horadric tablets.
# Act 2 desert tiles (LevelType 16). Level 138's row keeps its slot-2 red
# portal; LEVEL switches it to the desert. The walls are the desert's
# ruined sandstone (Village.dt1 main 48, variants 15/16); across the stock
# ruins (Act2/Outdoors/ruin*, Act2/Ruin/ruin*) a straight tile carries a
# wall01 (act2_ruin_stone_walls) at a median (+6.3, +2.4) yaw 0 on a north
# wall, (+2.6, +6.7) yaw 90 on a west wall; the corner tile carries both.
# Ruin/Column.dt1 column tiles hold the sandstone pillars (base, mid, top at
# (+3.5, +2.0/+1.1/+0.9), the top turned 29 degrees) and the Horadric tablets.
DUNES_DT1S = [rf"\d2\data\global\tiles\act2\{n}.dt1"
              for n in ("town\\ground", "ruin\\ground", "ruin\\column", "outdoors\\village")]
DUNES_SCENES = ("outdoors/ruin3", "outdoors/ruin2", "outdoors/tombent2", "ruin/ruin5", "outdoors/desert4",
                "outdoors/kingwarp", "ruin/ruin9")
DUNES_FLOOR = 0x0001C2              # main 0 sub 1: the ruins' packed sand
DUNES_WALL = 0x3000081              # orientations 1/2/3, main 48, | variant << 8
DUNES_PILLAR = 0x2400081            # orientation 12, Ruin/Column.dt1 main 36 sub 0
DUNES_TABLETS = ((0x2400381, "tablet02.model", 4.1, 6.3), (0x2400481, "tablet01.model", 2.5, 5.9))

# Act 2 objpreset indices (as in the Sandswept sanctum).
OBJ_DESERT_TORCH = 1                # TikiTorch1
OBJ_DESERT_POTS = (28, 29, 30, 31)  # Urn4, Urn5, JugOutdoor1/2

DUNES = {
    # Same footprint as the other sanctums: 20x20, walls outside it.
    "lo": 3, "hi": 22,
    "ring": (7, 18), "ring_gaps": (10, 15),
    "court": (9, 16),
    # Colossi at the middle of the north and west walls (anchor tiles, see
    # _colossus): each spans about 23 units along its wall.
    "colossi": ((13, 3), (4, 14)),
    "warden": (62, 62),
    "portal": (19, 19),             # red portal in the south corner
    "warp_slot": 2,                # level 138's red portal, as in the Sandswept sanctum
    "seed": 1135,
}


def _ruin_wall(room, scene, t, line, north, variant):
    if north:
        room.set_wall(t, line, ORIENT_TOP, DUNES_WALL | variant << 8)
        scene.add("wall01.model", 10 * t + 6.3, 10 * line + 2.4, 0)
    else:
        room.set_wall(line, t, ORIENT_LEFT, DUNES_WALL | variant << 8)
        scene.add("wall01.model", 10 * line + 2.6, 10 * t + 6.7, 90)


def _sandstone_pillar(scene, x, y):
    scene.add("pillar_base01.model", 10 * x + 3.5, 10 * y + 2.0, 0)
    scene.add("pillar_mid01.model", 10 * x + 3.5, 10 * y + 1.1, 0)
    scene.add("pillar_top01.model", 10 * x + 3.5, 10 * y + 0.9, 29)


def _colossus(room, scene, x, y, yaw):
    """A statue01 colossus on tile (x, y) with the Column.dt1 pieces the stock
    ruins lay under it: turned 90 (ruin2, ruin10) it lies along the row below;
    turned 3 (ruin9's left statue) along its own column and the tile west."""
    if yaw == 90:
        scene.add("statue01.model", 10 * x + 2.5, 10 * y + 1.5, 90)
        pieces = ((x - 2, y + 1, ORIENT_WEST_END, 0x2400181), (x - 1, y + 1, ORIENT_TOP, 0x2400481),
                  (x, y + 1, ORIENT_TOP, 0x2400581))
    else:
        scene.add("statue01.model", 10 * x + 7.5, 10 * y + 3.2, 3)
        pieces = ((x, y - 2, ORIENT_LEFT, 0x2400081), (x, y - 1, ORIENT_LEFT, 0x2400181),
                  (x - 1, y, ORIENT_TOP, 0x2400081), (x, y, ORIENT_SOUTH_CORNER, 0x2400081))
    for px, py, orientation, cell in pieces:
        room.set_wall(px, py, orientation, cell)


def build_dunes():
    s = DUNES
    lo, hi = s["lo"], s["hi"]
    back, front = lo - 1, hi + 1
    cells = front + 1
    rng = random.Random(s["seed"])
    room = Room(cells, cells, 1, DUNES_DT1S, void=0)
    kit = Kit("act2", DUNES_SCENES, TERRAIN_SCENE)
    scene = Scene(kit, "data/hd/env/biome/act2_outdoors.json", cells, cells)

    # ---- floor -----------------------------------------------------------
    for y in range(back, front):
        for x in range(back, front):
            room.set_floor(x, y, DUNES_FLOOR)

    # ---- ruined sandstone walls on all four sides ------------------------
    # Village.dt1 has no end pieces, so the south wall runs under both far
    # corners and the east wall reaches the north wall's row. The south
    # wall's last piece, past the east wall, only seals the corner: no model.
    room.set_wall(back, back, ORIENT_CORNER, DUNES_WALL | 15 << 8)
    scene.add("wall01.model", 10 * back + 6.8, 10 * back + 2.4, 0)
    scene.add("wall01.model", 10 * back + 2.2, 10 * back + 6.9, 90)
    for t in range(lo, hi + 1):
        _ruin_wall(room, scene, t, back, True, 15 + t % 2)
        _ruin_wall(room, scene, t, back, False, 15 + t % 2)
    for t in range(back, hi + 1):
        _ruin_wall(room, scene, t, front, True, 15 + t % 2)
    room.set_wall(front, front, ORIENT_TOP, DUNES_WALL | 15 << 8)
    for t in range(back, hi + 1):
        _ruin_wall(room, scene, t, front, False, 15 + t % 2)
    for t in (lo + 2, hi - 2):
        room.add_object(2, OBJ_DESERT_TORCH, 5 * t + 2, 5 * lo + 2)
        room.add_object(2, OBJ_DESERT_TORCH, 5 * lo + 2, 5 * t + 2)

    # ---- sandstone pillar ring and braziers ------------------------------
    a, b = s["ring"]
    g1, g2 = s["ring_gaps"]
    for x, y in ((a, g1), (a, g2), (b, g1), (b, g2), (g1, a), (g2, a), (g1, b), (g2, b)):
        room.set_wall(x, y, ORIENT_COLUMN, DUNES_PILLAR)
        _sandstone_pillar(scene, x, y)
    for x, y in ((a, a), (b, a), (a, b), (b, b)):
        room.add_object(2, OBJ_BRAZIER_TALL, 5 * x + 2, 5 * y + 2)

    # ---- colossi against both back walls ---------------------------------
    _colossus(room, scene, *s["colossi"][0], 90)
    _colossus(room, scene, *s["colossi"][1], 3)

    # ---- the court: Tal Rasha's seal and the Horadric tablets -------------
    # The seal is the Canyon of the Magi's floor dais, laid flat under the
    # Warden; the tablets mark the court's north and south corners.
    c0, c1 = s["court"]
    wx, wy = s["warden"]
    scene.add("talrasha_altar.model", 2 * wx + 1, 2 * wy + 1, 0)
    for i, (x, y) in enumerate(((c0, c0), (c1, c1))):
        cell, model, dx, dz = DUNES_TABLETS[i]
        room.set_wall(x, y, ORIENT_COLUMN, cell)
        scene.add(model, 10 * x + dx, 10 * y + dz, 0)
    for _ in range(3):
        scene.add("act2_outdoors_dune_pattern01_STAMP.texture", rng.uniform(10 * c0, 10 * c1 + 10),
                  rng.uniform(10 * c0, 10 * c1 + 10), rng.uniform(0, 360))

    # ---- the aisles: fallen columns, drifting dunes, the desert's dead ----
    for model, x, z in (("column_fallen01.model", 10 * lo + 20, 10 * hi - 8),
                        ("column_half_fallen01.model", 10 * hi - 10, 10 * lo + 22),
                        ("column_base01.model", 10 * lo + 44, 10 * lo + 12),
                        ("column_half_fallen01.model", 10 * hi - 38, 10 * hi - 2)):
        scene.add(model, x, z, rng.uniform(0, 360))
    for t in range(lo, hi + 1, 3):
        if abs(t - 12.5) < 2:           # the colossi
            continue
        if rng.random() < 0.7:
            scene.add(rng.choice(("dune_long01.model", "dune_circular01.model")),
                      10 * t + rng.uniform(2, 8), 10 * lo + rng.uniform(1, 4), rng.uniform(-20, 20))
        if rng.random() < 0.7:
            scene.add(rng.choice(("dune_long01.model", "dune_circular01.model")),
                      10 * lo + rng.uniform(1, 4), 10 * t + rng.uniform(2, 8), rng.uniform(70, 110))
    for x, z in ((10 * lo + 6, 10 * lo + 6), (10 * hi, 10 * lo + 6)):
        scene.add("act2_tree_palm01.model", x, z, rng.uniform(0, 360))
    for _ in range(12):
        x, z = rng.uniform(10 * lo, 10 * hi + 10), rng.uniform(10 * lo, 10 * hi + 10)
        if 10 * c0 - 5 < x < 10 * c1 + 15 and 10 * c0 - 5 < z < 10 * c1 + 15:
            continue
        scene.add(rng.choice(("act2_bush04.model", "act2_grass_clump02.model", "act2_cacti_small01.model",
                              "skull01.model", "rock_skirt_spread01.model", "vase09.model")),
                  x, z, rng.uniform(0, 360))
    for sx, sy in ((5 * lo + 3, 5 * hi + 2), (5 * lo + 5, 5 * hi + 3), (5 * hi + 2, 5 * lo + 3),
                   (5 * hi + 3, 5 * lo + 5)):
        room.add_object(2, rng.choice(OBJ_DESERT_POTS), sx, sy)

    # ---- atmosphere ------------------------------------------------------
    for fx, count in (("FX_SandRibbons_Outdoors.particles", 4),
                      ("FX_Act2Outdoors_SandMotes_30x30.particles", 6)):
        for _ in range(count):
            scene.add(fx, rng.uniform(10 * lo, 10 * hi + 10), rng.uniform(10 * lo, 10 * hi + 10))

    # ---- return warp and the Warden --------------------------------------
    px, py = s["portal"]
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
    room.add_object(1, 0, *s["warden"])
    return room.to_bytes(), scene.to_bytes()


# --------------------------------------------------------------------------
# Forsaken Highlands: the Warden's war camp
# --------------------------------------------------------------------------
# A hollow in the highlands where corrupted Rogues and the Fallen have made
# camp: dry-stone border walls on all four sides, a ring of Fallen skull
# totems with gibbets at its corners around a trampled clearing where the
# Warden waits, Fallen tents and campfires in the aisles, staked Rogues along
# the walls and the red portal in the south corner.
#
# Act 1 wilderness tiles (LevelType 2). Level 158's row keeps its slot-2 red
# portal; LEVEL switches it to the wilderness. The walls are the wilderness
# borders: stonewall.dt1 main 2 sub 0, which across the stock borders
# (Act1/Outdoors/bord*, wild*) carries an act1_outdoors_stonewalls r_wall01
# at (+3.0, +4.5) on a north wall and an l_wall01 at (+4.0, +3.5) on a west
# wall, both yaw 0 (each a model variation with ivy-grown alternatives); the
# corner (3, 2, 0) carries both. Each model reaches ~8 units back into the
# previous tile, so a run gets one more model on the tile past its end to
# close the corner. (The Stony Field cliffs, act1_outdoors_cliffs, share the
# basenames; the kit reads bivouac first to get the stone walls.) Fallen.dt1
# main 14 holds the Fallen camp
# pieces, each with its stock model and offset (fallcmp*): skull totems,
# campfires and tents (a prefab on tile (x, y) over three west-wall pieces
# down the column to its west).
HIGHLANDS_DT1S = [rf"\d2\data\global\tiles\act1\{n}.dt1"
                  for n in ("town\\floor", "outdoors\\stonewall", "outdoors\\fallen")]
HIGHLANDS_SCENES = ("outdoors/bivouac", "outdoors/fallcmp", "outdoors/fallcmp3", "outdoors/tome",
                    "outdoors/fallcmp2", "outdoors/stnclf2")
HIGHLANDS_FLOOR = 0x0000C2           # Town/Floor.dt1 main 0 sub 0: the wilderness grass
HIGHLANDS_WALL = 0x200081            # orientations 1/2/3, stonewall.dt1 main 2 sub 0
# (orientation, cell, model, dx, dz) per Fallen totem, as in fallcmp*.
FALLEN_TOTEMS = ((ORIENT_TOP, 0xE00081, "marker02.model", 8, 4),
                 (ORIENT_TOP, 0xE00281, "pf_marker04.json", 8, 4),
                 (ORIENT_TOP, 0xE00181, "marker03.model", 6, 4),
                 (ORIENT_LEFT, 0xE00181, "marker05.model", 2, 6))
FALLEN_CAMPFIRE = 0xE00081           # orientation 12, Fallen.dt1 main 14 sub 0
FALLEN_TENT = (0xE00481, 0xE00381, 0xE00281)   # orientation 1, top to bottom

# Act 1 objpreset indices.
OBJ_FALLEN_TORCH = 1                 # TikiTorch1
OBJ_GIBBET = 26
OBJ_ROGUE_CORPSES = (67, 68)         # RogueCorpse1/2
OBJ_STAKED_ROGUES_A1 = (70, 71)      # RogueStakedCorpse1/2

HIGHLANDS = {
    # Same footprint as the other sanctums: 20x20, walls outside it.
    "lo": 3, "hi": 22,
    "ring": (7, 18), "ring_gaps": (10, 15),
    "court": (9, 16),
    "tents": ((20, 4), (5, 18)),     # prefab tiles; their campfires two tiles south
    "warden": (62, 62),
    "portal": (19, 19),              # red portal in the south corner
    "warp_slot": 2,                  # level 158's red portal (lvlwarp 83)
    "seed": 1141,
}


def _stone_wall(room, scene, t, line, north):
    if north:
        room.set_wall(t, line, ORIENT_TOP, HIGHLANDS_WALL)
    else:
        room.set_wall(line, t, ORIENT_LEFT, HIGHLANDS_WALL)
    _stone_wall_model(scene, t, line, north)


def _stone_wall_model(scene, t, line, north):
    if north:
        scene.add("r_wall01.model", 10 * t + 3.0, 10 * line + 4.5, 0)
    else:
        scene.add("l_wall01.model", 10 * line + 4.0, 10 * t + 3.5, 0)


def _fallen_tent(room, scene, x, y):
    for i, cell in enumerate(FALLEN_TENT):
        room.set_wall(x - 1, y + i, ORIENT_LEFT, cell)
    scene.add("pf_act1_outdoors_markers_tent01.json", 10 * x, 10 * y + 6, 0)
    room.set_wall(x, y + 2, ORIENT_COLUMN, FALLEN_CAMPFIRE)
    scene.add("campfire01.model", 10 * x + 8, 10 * y + 28, 0)


def build_highlands():
    s = HIGHLANDS
    lo, hi = s["lo"], s["hi"]
    back, front = lo - 1, hi + 1
    cells = front + 1
    rng = random.Random(s["seed"])
    room = Room(cells, cells, 0, HIGHLANDS_DT1S, void=0)
    kit = Kit("act1", HIGHLANDS_SCENES, TERRAIN_SCENE)
    scene = Scene(kit, "data/hd/env/biome/act1_outdoors.json", cells, cells)

    # ---- floor -----------------------------------------------------------
    for y in range(back, front):
        for x in range(back, front):
            room.set_floor(x, y, HIGHLANDS_FLOOR)

    # ---- stone walls on all four sides -----------------------------------
    # Legacy walls as in the Sunscar ruin (no end pieces: the south wall's
    # last piece seals the south-east corner).
    room.set_wall(back, back, ORIENT_CORNER, HIGHLANDS_WALL)
    for north in (True, False):
        _stone_wall_model(scene, back, back, north)
    for t in range(lo, hi + 1):
        _stone_wall(room, scene, t, back, True)
        _stone_wall(room, scene, t, back, False)
    for t in range(back, hi + 1):
        _stone_wall(room, scene, t, front, True)
        _stone_wall(room, scene, t, front, False)
    room.set_wall(front, front, ORIENT_TOP, HIGHLANDS_WALL)
    # The models past each run's end, closing the corners.
    for line in (back, front):
        for north in (True, False):
            _stone_wall_model(scene, front, line, north)
    for t in (lo + 3, hi - 3):
        room.add_object(2, OBJ_FALLEN_TORCH, 5 * t + 2, 5 * lo + 4)
        room.add_object(2, OBJ_FALLEN_TORCH, 5 * lo + 4, 5 * t + 2)
    for t in (lo + 6, hi - 6):
        room.add_object(2, OBJ_STAKED_ROGUES_A1[0], 5 * t + 2, 5 * lo + 4)
        room.add_object(2, OBJ_STAKED_ROGUES_A1[1], 5 * lo + 4, 5 * t + 2)

    # ---- Fallen totem ring and gibbets -----------------------------------
    a, b = s["ring"]
    g1, g2 = s["ring_gaps"]
    ring = ((a, g1), (g1, a), (b, g1), (g2, a), (a, g2), (g1, b), (b, g2), (g2, b))
    for i, (x, y) in enumerate(ring):
        orientation, cell, model, dx, dz = FALLEN_TOTEMS[i % len(FALLEN_TOTEMS)]
        room.set_wall(x, y, orientation, cell)
        scene.add(model, 10 * x + dx, 10 * y + dz, 0)
    for x, y in ((a, a), (b, a), (a, b), (b, b)):
        room.add_object(2, OBJ_GIBBET, 5 * x + 2, 5 * y + 2)

    # ---- the clearing: the Fallen's spoils and the Rogues' dead ----------
    c0, c1 = s["court"]
    mid = 10 * (c0 + c1 + 1) / 2
    for dx, dz, yaw in ((0, 0, 0), (-18, 14, 70), (16, -15, 150)):
        scene.add("act1_outdoors_dirt_clearing01_STAMP.texture", mid + dx, mid + dz, yaw)
    for x, y in ((c0, c0), (c1, c0), (c0, c1), (c1, c1)):
        room.add_object(2, OBJ_FALLEN_TORCH, 5 * x + 2, 5 * y + 2)
    spoils = ("pile01.model", "pile02.model", "pile05.model", "pile07.model", "pile08.model", "stick_pile01.model",
              "corpse01.model", "corpse02.model", "torso.model", "sword_rusty01.model", "spear_corrupted01.model",
              "skull_stick02.model")
    for _ in range(14):
        x, z = rng.uniform(10 * c0, 10 * c1 + 10), rng.uniform(10 * c0, 10 * c1 + 10)
        if abs(x - mid) < 12 and abs(z - mid) < 12:     # the Warden's spot
            continue
        scene.add(rng.choice(spoils), x, z, rng.uniform(0, 360))
    for sx, sy in ((5 * c0 + 3, 5 * c1 + 1), (5 * c1 + 1, 5 * c0 + 3)):
        room.add_object(2, rng.choice(OBJ_ROGUE_CORPSES), sx, sy)

    # ---- the aisles: tents, dead trees, boulders, highland scrub ----------
    for x, y in s["tents"]:
        _fallen_tent(room, scene, x, y)
        for model, dx, dz in (("pile02.model", -6, 14), ("pile01.model", 14, 12), ("marker01.model", 13, 30)):
            scene.add(model, 10 * x + dx, 10 * y + dz, rng.uniform(0, 360))
    for model, x, z in (("act1_tree_dead01.model", 10 * lo + 12, 10 * lo + 24),
                        ("act1_tree_dead02.model", 10 * hi - 14, 10 * hi - 26),
                        ("act1_tree_deadstump01.model", 10 * lo + 44, 10 * hi + 2)):
        scene.add(model, x, z, rng.uniform(0, 360))
    for t in range(lo, hi + 1, 2):
        for x, z in ((10 * t + rng.uniform(1, 9), 10 * lo + rng.uniform(4, 8)),
                     (10 * lo + rng.uniform(4, 8), 10 * t + rng.uniform(1, 9))):
            if rng.random() < 0.4:
                scene.add(rng.choice(("boulder05.model", "boulder07.model")), x, z, rng.uniform(0, 360))
    scrub = ("act1_grass_clump01.model", "act1_grass_clump02.model", "act1_shrub02.model",
             "act1_bush_hawthorn05.model", "act1_weeds03.model")
    for _ in range(26):
        x, z = rng.uniform(10 * lo, 10 * hi + 10), rng.uniform(10 * lo, 10 * hi + 10)
        if 10 * c0 - 5 < x < 10 * c1 + 15 and 10 * c0 - 5 < z < 10 * c1 + 15:
            continue
        scene.add(rng.choice(scrub), x, z, rng.uniform(0, 360))

    # ---- atmosphere ------------------------------------------------------
    for fx, count in (("FX_Act1Outdoors_fog_20x20.particles", 6), ("FX_FogGround.particles", 3)):
        for _ in range(count):
            scene.add(fx, rng.uniform(10 * lo, 10 * hi + 10), rng.uniform(10 * lo, 10 * hi + 10))
    scene.add("FX_Flies_Heavy.particles", mid - 20, mid + 25)

    # ---- return warp and the Warden --------------------------------------
    px, py = s["portal"]
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
    room.add_object(1, 0, *s["warden"])
    return room.to_bytes(), scene.to_bytes()


BUILDERS = {"sandswept": build_sandswept, "frozen": build_frozen, "worldstone": build_worldstone,
            "catacombs": build_catacombs, "steppes": build_steppes, "infernal": build_infernal,
            "durance": build_durance, "travincal": build_travincal, "dunes": build_dunes,
            "highlands": build_highlands}
_cache = {}


def build(name):
    """(ds1 bytes, HD scene bytes) for the custom arena `name`."""
    if name not in _cache:
        _cache[name] = BUILDERS[name]()
    return _cache[name]
