"""Clone shipped DS1 rooms and replace their monster population with a map boss.

Only the object block changes; tiles, warps and trailing substitution/NPC
records remain byte-for-byte intact. Source Labyrinth files are never written.
"""
import os
import shutil
import struct
from pathlib import Path

import maps_config as cfg

STOCK_CACHE = Path(__file__).resolve().parent / "stock"


def objects(data):
    version, width, height, act, sub, files = struct.unpack_from("<6I", data)
    if version != 18 or width > 512 or height > 512 or files > 100:
        raise ValueError("Only validated v18 DS1 rooms are supported")
    offset = 24
    for _ in range(files):
        offset = data.index(b"\0", offset) + 1
    walls, floors = struct.unpack_from("<2I", data, offset)
    if not 1 <= walls <= 4 or not 1 <= floors <= 2:
        raise ValueError("Invalid DS1 layer counts")
    offset += 8 + (width + 1) * (height + 1) * (2 * walls + floors + 1 + (sub in (1, 2))) * 4
    count = struct.unpack_from("<I", data, offset)[0]
    if count > 10000 or offset + 4 + count * 20 > len(data):
        raise ValueError("Invalid DS1 object block")
    rows = [struct.unpack_from("<5I", data, offset + 4 + i * 20) for i in range(count)]
    return offset, rows, width, height


OBJECT_TAG = "rmap_object"

# Labyrinth hub furniture that a cloned arena must not keep: a stash has no
# place in a boss room, and a waypoint object in a level without a waypoint
# row is broken.
ARENA_EXCLUDED_OBJECTS = {"Bank", "WaypointAct2"}


class ObjectPresets:
    """objpreset.txt: DS1 object ids are indices into one act's rows. A cloned
    room is stamped Act 5 so its Warden resolves through the Act 5 MonPreset
    namespace, which also moves every object record into the Act 5 object
    namespace: Heart.ds1's Act 4 Hellfire torches became Act 5 Standards and
    its light shafts became Banks, which put stashes in the Worldstone arena.
    Each object is therefore re-pointed at the Act 5 row of the same class,
    appended (and tagged for regeneration) when Act 5 has none."""

    def __init__(self, api):
        self.table = api.Table(api.EXCEL / "objpreset.txt")
        self.api = api
        self.index, self.act, self.cls, self.notes = (
            self.table.col(c) for c in ("Index", "Act", "ObjectClass", "*Notes"))
        self.table.drop_tagged(self.notes, OBJECT_TAG)

    def object_class(self, act, object_id):
        cls = next((r[self.cls] for r in self.table.rows
                    if r[self.act] == str(act) and r[self.index] == str(object_id)), None)
        if cls is None:
            raise ValueError(f"objpreset has no Act {act} object {object_id}")
        return cls

    def remap(self, source_act, object_id):
        """Act 5 index for the object `object_id` of `source_act` (1-based),
        or None when the arena must not keep it."""
        cls = self.object_class(source_act, object_id)
        if cls in ARENA_EXCLUDED_OBJECTS:
            return None
        if source_act == 5:
            return object_id
        rows = self.table.rows
        for r in rows:
            if r[self.act] == "5" and r[self.cls] == cls:
                return int(r[self.index])
        index = 1 + max(int(r[self.index]) for r in rows if r[self.act] == "5")
        row = self.table.blank_row()
        self.api.set_cells(row, self.table, {
            "Index": str(index), "Act": "5", "ObjectClass": cls, "*Notes": OBJECT_TAG, "*eol": "0",
        })
        self.table.append(row)
        return index


def clone(data, preset, presets=None):
    offset, rows, width, height = objects(data)
    points = [(r[2], r[3]) for r in rows if r[0] == 1]
    # Existing monster locations are known walkable positions. NihlS has no
    # monster records; its centre is the original Nihlathak platform.
    x, y = min(points, key=lambda p: (p[0] - width * 2.5)**2 + (p[1] - height * 2.5)**2) if points else (211, 211)
    if not (0 <= x <= width * 5 and 0 <= y <= height * 5):
        raise ValueError("Boss outside DS1")
    source_act = struct.unpack_from("<I", data, 12)[0] + 1
    kept = []
    for r in rows:
        if r[0] == 1:
            continue
        if r[0] == 2 and presets is not None:
            index = presets.remap(source_act, r[1])
            if index is None:
                continue
            r = (2, index, r[2], r[3], r[4])
        kept.append(r)
    kept.append((1, preset, x, y, 0))
    header = bytearray(data[:offset])
    struct.pack_into("<I", header, 12, 4)  # Act 5 MonPreset namespace
    block = struct.pack("<I", len(kept)) + b"".join(struct.pack("<5I", *r) for r in kept)
    return bytes(header) + block + data[offset + 4 + len(rows) * 20:]


def arena_source(repo, theme, tier):
    """The on-disk DS1 and HD preset JSON to clone for one map."""
    spec = theme["arena_ds1"]
    if isinstance(spec, (list, tuple)):
        spec = spec[(tier - 1) % len(spec)]
    if spec.startswith("stock:"):
        rel = spec[len("stock:"):]
        ds1 = _stock(Path("global/tiles") / rel)
        hd = _stock(Path("hd/env/preset") / (rel[:-len(".ds1")].lower() + ".json"))
    else:
        ds1 = repo / "data/global/tiles" / spec
        hd = repo / "data/hd/env/preset" / (spec[:-len(".ds1")].lower() + ".json")
    return ds1, hd


def _stock(rel):
    """Return a committed copy of an unmodified D2R file, fetching it from the
    extracted game data the first time it is referenced."""
    cached = STOCK_CACHE / rel
    if not cached.exists():
        source = Path(os.environ.get("D2R_STOCK_DATA", cfg.STOCK_DATA)) / rel
        if not source.exists():
            raise FileNotFoundError(
                f"{rel} is neither cached under {STOCK_CACHE} nor present in the "
                f"extracted game data at {source.parent}; set D2R_STOCK_DATA")
        cached.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, cached)
    return cached


# automap.txt cell drawn for a Warden. D2R draws any monster whose MonStats2
# row carries an automapCel (the Act 5 barricade tower is the stock example),
# so this is the only data needed for a boss marker. 305 is the Compelling Orb
# icon: a plain dot until dedicated skull art is added to the automap sprite.
BOSS_AUTOMAP_CEL = "305"

# Cast by the Warden in death mode (Sk<n>mode = DT), so its corpse opens a town
# portal. This is the stock scroll skill (srvdofunc 113); a monster caster has
# no player portal list, so this must be confirmed live before it is relied on.
BOSS_DEATH_SKILL = "Book of Townportal"


def add_skill(api, monsters, row, skill, mode, level=1):
    """Put `skill` in the first free Skill slot of `row`."""
    for slot in range(1, 9):
        if not row[monsters.col(f"Skill{slot}")]:
            api.set_cells(row, monsters, {
                f"Skill{slot}": skill, f"Sk{slot}mode": mode, f"Sk{slot}lvl": str(level),
            })
            return
    raise ValueError(f"{row[monsters.col('Id')]}: no free skill slot for {skill}")


def add_death_skill(api, monsters, row, skill):
    """Put `skill` in the first free Skill slot of `row`, cast on death."""
    add_skill(api, monsters, row, skill, "DT")


def apply_kit(api, monsters, boss, p):
    """Give a Warden its theme kit from cfg.WARDENS. The aura and procs live
    in the Warden's own monprop row (see endgame.py) and the escort in
    superuniques.txt; this handles everything on the monstats row itself."""
    kit = cfg.WARDENS[p["theme"]["key"]]
    tier, code = p["tier"], p["item_code"]
    step = tier - 1
    api.set_cells(boss, monsters, {"MonProp": f"rmap_{code}_boss",
                                   "DamageRegen": str(cfg.WARDEN_DAMAGE_REGEN)})
    lo, hi = cfg.WARDEN_HP_RATIO
    factor = 1.5 * p["spec"]["scale"] * cfg.WARDEN_HP_MULTIPLIER
    for diff in ("", "(N)", "(H)"):
        for stem, ratio in (("MinHP", lo), ("MaxHP", hi)):
            target = stem + diff
            if target not in monsters.header:
                target = target[0].lower() + target[1:]
            boss[monsters.col(target)] = str(round(ratio * factor))
    if kit["melee"]:
        el_type, lo, hi, dur = kit["melee"]
        cells = {"El1Mode": "A1", "El1Type": el_type}
        for diff in ("", "(N)", "(H)"):
            cells.update({f"El1Pct{diff}": "100", f"El1Dur{diff}": str(dur) if dur else "",
                          f"El1MinD{diff}": str(lo) if lo else "",
                          f"El1MaxD{diff}": str(hi) if hi else ""})
        api.set_cells(boss, monsters, cells)
    if kit["drain"] is not None:
        api.set_cells(boss, monsters, {f"Drain{d}": str(kit["drain"]) for d in ("", "(N)", "(H)")})
    archetypes = cfg.MAP_MONSTERS[p["theme"]["key"]]
    first, second, lo, hi = kit["escort"]
    bonus = cfg.WARDEN_ESCORT_PER_TIER * step + (cfg.WARDEN_TIER6_ESCORT_BONUS if tier == 6 else 0)
    api.set_cells(boss, monsters, {
        "minion1": f"rmap_{code}_{archetypes.index(first)}",
        "minion2": f"rmap_{code}_{archetypes.index(second)}",
        "MinGrp": str(lo + bonus), "MaxGrp": str(hi + bonus),
    })
    for col in monsters.header:
        if col.startswith("Res") and col[3:5] in ("Dm", "Ma", "Fi", "Li", "Co", "Po"):
            value = int(boss[monsters.col(col)] or 0)
            if value > cfg.WARDEN_RESIST_CAP:
                boss[monsters.col(col)] = str(cfg.WARDEN_RESIST_CAP)


def escort_count(p):
    """Superunique MinGrp/MaxGrp for a Warden: the theme's escort plus the
    per-tier step and the tier 6 cliff."""
    _, _, lo, hi = cfg.WARDENS[p["theme"]["key"]]["escort"]
    bonus = cfg.WARDEN_ESCORT_PER_TIER * (p["tier"] - 1)
    if p["tier"] == 6:
        bonus += cfg.WARDEN_TIER6_ESCORT_BONUS
    return lo + bonus, hi + bonus


def generate(api, plans, levels, presets, monsters):
    places = api.Table(api.EXCEL / "monpreset.txt")
    places.drop_tagged(places.col("Place"), "rmap_")
    next_slot = sum(r[places.col("Act")] == "5" for r in places.rows)
    # The Warden is placed as a superunique so its escort spawns with it.
    uniques = api.Table(api.EXCEL / "superuniques.txt")
    uniques.drop_tagged(uniques.col("Superunique"), "rmap_")
    next_hc = 1 + max(int(r[uniques.col("hcIdx")] or 0) for r in uniques.rows)
    # Map monsters share their source monster's MonStats2 row. A Warden gets
    # its own copy so the automap marker is not inherited by every monster
    # of that archetype in the rest of the game.
    stats2 = api.Table(api.EXCEL / "monstats2.txt")
    stats2.drop_tagged(stats2.col("Id"), "rmap_")
    object_presets = ObjectPresets(api)
    assets = {}
    for p in plans:
        code = p["item_code"]
        boss = list(monsters.find(monsters.col("Id"), f"rmap_{code}_0"))
        marker = list(stats2.find(stats2.col("Id"), boss[monsters.col("MonStatsEx")]))
        api.set_cells(marker, stats2, {"Id": f"rmap_{code}_boss", "automapCel": BOSS_AUTOMAP_CEL})
        stats2.append(marker)
        api.set_cells(boss, monsters, {
            "Id": f"rmap_{code}_boss", "*hcIdx": str(len(monsters.rows)),
            "MonStatsEx": f"rmap_{code}_boss",
            "MinGrp": "1", "MaxGrp": "1", "boss": "1", "primeevil": "0",
            "NameStr": f"RMapBoss{code}",
        })
        add_death_skill(api, monsters, boss, BOSS_DEATH_SKILL)
        apply_kit(api, monsters, boss, p)
        for col in monsters.header:
            if col.startswith("TreasureClass"):
                boss[monsters.col(col)] = f"RMap T{p['tier']} Boss"
        monsters.append(boss)
        unique = uniques.blank_row()
        lo, hi = escort_count(p)
        api.set_cells(unique, uniques, {
            "Superunique": f"rmap_{code}_warden", "Name": f"RMapBoss{code}",
            "Class": f"rmap_{code}_boss", "hcIdx": str(next_hc),
            "Mod1": "0", "Mod2": "0", "Mod3": "0",
            "MinGrp": str(lo), "MaxGrp": str(hi), "AutoPos": "0", "Stacks": "0",
            "Utrans": str(cfg.WARDEN_UTRANS), "Utrans(N)": str(cfg.WARDEN_UTRANS),
            "Utrans(H)": str(cfg.WARDEN_UTRANS),
            **{col: f"RMap T{p['tier']} Boss" for col in uniques.header if col.startswith("TC")},
            "*eol": "0",
        })
        uniques.append(unique)
        next_hc += 1
        row = places.blank_row()
        api.set_cells(row, places, {"Act": "5", "Place": f"rmap_{code}_warden", "* DS1 ID#": str(next_slot)})
        places.append(row)

        preset = presets.find(presets.col("LevelId"), str(p["boss_id"]))
        level = levels.find(levels.col("Id"), str(p["boss_id"]))
        ds1, hd = arena_source(api.REPO, p["theme"], p["tier"])
        target = f"Maps/{code}_boss.ds1"
        assets[api.REPO / "data/global/tiles" / target] = clone(ds1.read_bytes(), next_slot, object_presets)
        # D2R resolves the HD scene by the DS1 path, so a cloned room needs its
        # own hd/env/preset entry or it renders without HD geometry. The JSON
        # only references stock terrain assets by absolute path; a verbatim
        # copy is the correct scene for the copied tiles.
        assets[api.REPO / "data/hd/env/preset/maps" / f"{code}_boss.json"] = hd.read_bytes()
        next_slot += 1
        api.set_cells(preset, presets, {"Populate": "0", "Files": "1", "File1": target,
                                       **{f"File{i}": "0" for i in range(2, 7)}})
        for group in ("mon", "nmon", "umon"):
            for i in range(1, 26):
                level[levels.col(f"{group}{i}")] = ""
        level[levels.col("NumMon")] = "0"
    if next_slot > 256:
        raise ValueError("Act 5 preset slots exceed 8-bit range")
    return [places, stats2, uniques, object_presets.table], assets
