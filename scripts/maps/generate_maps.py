#!/usr/bin/env python3
"""Generate the Reimagined mapping system rows into data/global/excel/*.txt.

Idempotent: every row this writes is tagged, and each run removes the previous
tagged rows before appending fresh ones. Run it again after editing
maps_config.py rather than hand-editing the game files.

    python scripts/maps/generate_maps.py            # write
    python scripts/maps/generate_maps.py --check    # validate only, no writes

After a successful run, mirror excel/ into excel/base/ the usual way:

    data/global/excel/a_copy_excel_base.bat
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import maps_config as cfg  # noqa: E402
import endgame
import boss_rooms

REPO = Path(__file__).resolve().parents[2]
EXCEL = REPO / "data" / "global" / "excel"
STRINGS = REPO / "data" / "local" / "lng" / "strings"


# ---------------------------------------------------------------------------
# TSV helpers. These files are CRLF, no BOM, and every row must carry exactly
# the same cell count as the header or D2R drops the table.
# ---------------------------------------------------------------------------

class Table:
    def __init__(self, path: Path):
        self.path = path
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raise SystemExit(f"{path.name}: unexpected BOM")
        text = raw.decode("utf-8")
        lines = text.split("\r\n")
        if lines and lines[-1] == "":
            lines.pop()
        if not lines:
            raise SystemExit(f"{path.name}: empty")
        self.header = lines[0].split("\t")
        self.rows = [ln.split("\t") for ln in lines[1:]]
        self.width = len(self.header)
        for i, r in enumerate(self.rows, start=2):
            if len(r) != self.width:
                raise SystemExit(
                    f"{path.name}: line {i} has {len(r)} cells, header has {self.width}")

    # Column index by exact header name. Several files repeat a header name
    # (cubemain has seven "input" columns); nth picks which one.
    def col(self, name: str, nth: int = 0) -> int:
        found = [i for i, h in enumerate(self.header) if h == name]
        if len(found) <= nth:
            raise SystemExit(f"{self.path.name}: no column {name!r} #{nth}")
        return found[nth]

    def blank_row(self) -> list[str]:
        return [""] * self.width

    def find(self, col: int, value: str) -> list[str]:
        for r in self.rows:
            if r[col] == value:
                return r
        raise SystemExit(f"{self.path.name}: no row with {self.header[col]}={value!r}")

    def drop_tagged(self, col: int, prefix: str) -> int:
        before = len(self.rows)
        self.rows = [r for r in self.rows if not r[col].startswith(prefix)]
        return before - len(self.rows)

    def append(self, row: list[str]) -> None:
        if len(row) != self.width:
            raise SystemExit(
                f"{self.path.name}: attempted to append {len(row)} cells, need {self.width}")
        self.rows.append(row)

    def save(self) -> None:
        self.path.write_bytes(self.to_bytes())

    def to_bytes(self) -> bytes:
        out = [self.header] + self.rows
        text = "\r\n".join("\t".join(r) for r in out) + "\r\n"
        return text.encode("utf-8")


def set_cells(row: list[str], table: Table, values: dict[str, str]) -> None:
    for name, value in values.items():
        row[table.col(name)] = value


# ---------------------------------------------------------------------------
# Layout planning. Level and Def ids are assigned deterministically so a
# re-run produces identical ids and saved characters keep working.
# ---------------------------------------------------------------------------

def plan() -> list[dict]:
    plans = []
    level_id = cfg.FIRST_LEVEL_ID
    prest_def = cfg.FIRST_PREST_DEF
    for theme in cfg.THEMES:
        for spec in cfg.TIERS:
            tier = spec["tier"]
            plans.append({
                "theme": theme,
                "tier": tier,
                "spec": spec,
                "body_id": level_id,
                "boss_id": level_id + 1,
                "prest_def": prest_def,
                "body_key": f"RMap{theme['key'].capitalize()}T{tier}",
                "boss_key": f"RMap{theme['key'].capitalize()}T{tier}Boss",
                "item_code": (cfg.ITEM_CODE_PREFIX
                              + cfg.THEME_CODE_LETTERS[theme["key"]]
                              + str(tier)),
            })
            level_id += 2
            prest_def += 1
    return plans


# ---------------------------------------------------------------------------
# levels.txt
# ---------------------------------------------------------------------------

def gen_levels(plans: list[dict]) -> Table:
    t = Table(EXCEL / "levels.txt")
    c_name, c_id = t.col("Name"), t.col("Id")
    t.drop_tagged(c_name, cfg.ROW_TAG)

    vis = [t.col(f"Vis{i}") for i in range(8)]
    warp = [t.col(f"Warp{i}") for i in range(8)]

    for p in plans:
        theme = p["theme"]
        body_tpl = t.find(c_id, str(theme["body_template"]))
        boss_tpl = t.find(c_id, str(theme["boss_template"]))

        # Establish that the template pair really is connected, and reuse the
        # exact slot and lvlwarp id that already links them.
        fwd = [i for i in range(8) if body_tpl[vis[i]] == str(theme["boss_template"])]
        back = [i for i in range(8) if boss_tpl[vis[i]] == str(theme["body_template"])]
        if not fwd or not back:
            raise SystemExit(
                f"theme {theme['key']}: levels {theme['body_template']} and "
                f"{theme['boss_template']} are not warp-connected; pick an "
                f"adjacent pair from the Forsaken chain")
        fwd_slot, back_slot = fwd[0], back[0]

        body = list(body_tpl)
        boss = list(boss_tpl)
        spec = p["spec"]
        mlvl = str(cfg.FIRST_MONLVL_ROW + spec["tier"] - 1)

        for row, is_boss in ((body, False), (boss, True)):
            # Clear every warp, then re-link only this map's two levels.
            for i in range(8):
                row[vis[i]] = "0"
                row[warp[i]] = "-1"
            for col in ("MonLvl", "MonLvl(N)", "MonLvl(H)",
                        "MonLvlEx", "MonLvlEx(N)", "MonLvlEx(H)"):
                row[t.col(col)] = mlvl
            den = "0" if is_boss else str(spec["density"])
            for col in ("MonDen", "MonDen(N)", "MonDen(H)"):
                row[t.col(col)] = den
            umin = "0" if is_boss else str(spec["umin"])
            umax = "0" if is_boss else str(spec["umax"])
            for col in ("MonUMin", "MonUMin(N)", "MonUMin(H)"):
                row[t.col(col)] = umin
            for col in ("MonUMax", "MonUMax(N)", "MonUMax(H)"):
                row[t.col(col)] = umax
            # Maps are self-contained instances: no waypoint, monsters do not
            # persist, and quest state must not leak in from the template.
            set_cells(row, t, {
                "Waypoint": "255",
                "SaveMonsters": "1",
                "QuestFlag": "",
                "QuestFlagEx": "",
                "Quest": "0",
            })

        set_cells(body, t, {
            "Name": f"{cfg.ROW_TAG} {theme['key']} T{p['tier']}",
            "*StringName": p["body_key"],
            "Id": str(p["body_id"]),
            # LevelName/LevelWarp/LevelEntry are the columns D2R actually
            # reads. Without these the clone keeps the template's keys and
            # every map is announced as "Forsaken Labyrinth Level".
            "LevelName": p["body_key"],
            "LevelWarp": f"RMap{theme['key'].capitalize()}Warp",
            "LevelEntry": f"RMap{theme['key'].capitalize()}Entry",
        })
        body[vis[fwd_slot]] = str(p["boss_id"])
        body[warp[fwd_slot]] = body_tpl[warp[fwd_slot]]

        set_cells(boss, t, {
            "Name": f"{cfg.ROW_TAG} {theme['key']} T{p['tier']} boss",
            "*StringName": p["boss_key"],
            "Id": str(p["boss_id"]),
            "LevelName": p["boss_key"],
            "LevelWarp": f"RMap{theme['key'].capitalize()}WarpBoss",
            "LevelEntry": f"RMap{theme['key'].capitalize()}Entry",
        })
        boss[vis[back_slot]] = str(p["body_id"])
        boss[warp[back_slot]] = boss_tpl[warp[back_slot]]

        t.append(body)
        t.append(boss)
    return t


# ---------------------------------------------------------------------------
# lvlmaze.txt / lvlprest.txt
# ---------------------------------------------------------------------------

def gen_lvlmaze(plans: list[dict]) -> Table:
    t = Table(EXCEL / "lvlmaze.txt")
    c_name, c_level = t.col("Name"), t.col("Level")
    t.drop_tagged(c_name, cfg.ROW_TAG)
    for p in plans:
        tpl = t.find(c_level, str(p["theme"]["body_template"]))
        row = list(tpl)
        set_cells(row, t, {
            "Name": f"{cfg.ROW_TAG} {p['theme']['key']} T{p['tier']}",
            "Level": str(p["body_id"]),
        })
        # Higher tiers are physically larger, which is most of why they take
        # longer and drop more.
        for col in ("Rooms", "Rooms(N)", "Rooms(H)"):
            base = int(tpl[t.col(col)] or 0)
            row[t.col(col)] = str(base + (p["tier"] - 1) * 4)
        t.append(row)
    return t


def gen_lvlprest(plans: list[dict]) -> Table:
    t = Table(EXCEL / "lvlprest.txt")
    c_name, c_level, c_def = t.col("Name"), t.col("LevelId"), t.col("Def")
    t.drop_tagged(c_name, cfg.ROW_TAG)
    for p in plans:
        tpl = t.find(c_level, str(p["theme"]["boss_template"]))
        row = list(tpl)
        set_cells(row, t, {
            "Name": f"{cfg.ROW_TAG} {p['theme']['key']} T{p['tier']} boss",
            "LevelId": str(p["boss_id"]),
            "Def": str(p["prest_def"]),
        })
        t.append(row)
    return t


# ---------------------------------------------------------------------------
# monlvl.txt - the tier scaling block
# ---------------------------------------------------------------------------

SCALED_COLS = ("HP", "HP(N)", "HP(H)", "L-HP", "L-HP(N)", "L-HP(H)",
               "DM", "DM(N)", "DM(H)", "L-DM", "L-DM(N)", "L-DM(H)")
XP_COLS = ("XP", "XP(N)", "XP(H)", "L-XP", "L-XP(N)", "L-XP(H)")


def gen_monlvl() -> Table:
    t = Table(EXCEL / "monlvl.txt")
    c_level = t.col("Level")
    first = cfg.FIRST_MONLVL_ROW
    last = first + len(cfg.TIERS) - 1
    t.rows = [r for r in t.rows
              if not (r[c_level].isdigit() and first <= int(r[c_level]) <= last)]

    base = t.find(c_level, str(cfg.MONLVL_BASE_ROW))
    for i, spec in enumerate(cfg.TIERS):
        row = list(base)
        row[c_level] = str(first + i)
        for col in SCALED_COLS:
            idx = t.col(col)
            value = base[idx]
            if value.strip():
                row[idx] = str(int(round(int(value) * spec["scale"])))
        if not cfg.MONLVL_FLAT_XP:
            for col in XP_COLS:
                idx = t.col(col)
                if base[idx].strip():
                    row[idx] = str(int(round(int(base[idx]) * spec["scale"])))
        t.append(row)
    return t


# ---------------------------------------------------------------------------
# itemtypes.txt / misc.txt
# ---------------------------------------------------------------------------

MAP_ITEM_TYPE = "mapi"
MAP_CURRENCY_TYPE = "mcur"
MAP_UI_CATEGORY = "maps"


def gen_uicategories() -> Table:
    """Give maps their own filter category rather than hiding under Charms.

    D2RLoader's item spawner groups by itemtypes.txt ItemType, and the game's
    own inventory filters group by this table. Both need to be right for maps
    to show up where a player expects them.
    """
    t = Table(EXCEL / "itemuicategories.txt")
    c_name = t.col("Name")
    t.rows = [r for r in t.rows if r[c_name] != MAP_UI_CATEGORY]
    row = t.blank_row()
    set_cells(row, t, {
        "Name": MAP_UI_CATEGORY,
        "isEquipment": "0",
        "ParentCategory": "misc",
        "QualityFilter": "0",
        "NumColumns": "3",
    })
    t.append(row)
    return t


def gen_itemtypes() -> Table:
    t = Table(EXCEL / "itemtypes.txt")
    c_code = t.col("Code")
    # Tagged by Code, not by ItemType: ItemType is the display name the item
    # spawner shows as its category heading, so it has to stay clean.
    owned = {MAP_ITEM_TYPE, MAP_CURRENCY_TYPE}
    t.rows = [r for r in t.rows if r[c_code] not in owned]

    tpl = t.find(c_code, "char")           # charm: 1x1 capable, misc-equivalent
    for code, name in ((MAP_ITEM_TYPE, "Map"), (MAP_CURRENCY_TYPE, "Map Currency")):
        row = list(tpl)
        set_cells(row, t, {
            "ItemType": name,
            "Code": code,
            "Equiv1": "misc",
            # Match rare-capable misc items (rings/amulets): magic minimum,
            # rare allowed, with no normal-only override.
            "Magic": "1" if code == MAP_ITEM_TYPE else "0",
            "Rare": "1" if code == MAP_ITEM_TYPE else "0",
            "Normal": "0" if code == MAP_ITEM_TYPE else "1",
            "Beltable": "0",
            "StaffMods": "",
            "Class": "",
            "UICategory": MAP_UI_CATEGORY,
            # Each map code selects a single tier asset in the HD lookup.
            "VarInvGfx": "0" if code == MAP_ITEM_TYPE else tpl[t.col("VarInvGfx")],
        })
        if code == MAP_ITEM_TYPE:
            for slot in range(1, 7):
                row[t.col(f"InvGfx{slot}")] = ""
        t.append(row)
    return t


def gen_misc(plans: list[dict]) -> Table:
    t = Table(EXCEL / "misc.txt")
    c_name, c_code = t.col("name"), t.col("code")
    t.drop_tagged(c_name, cfg.ITEM_TAG)
    tpl = t.find(c_code, "cm1")            # small charm: 1x1, no side effects

    existing = {r[c_code] for r in t.rows if r[c_code]}

    def make(code: str, name: str, namestr: str, level: int, itype: str) -> None:
        if code in existing:
            raise SystemExit(f"misc.txt: item code {code!r} is already taken")
        row = list(tpl)
        set_cells(row, t, {
            "name": f"{cfg.ITEM_TAG} {name}",
            "code": code,
            "namestr": namestr,
            "normcode": code,
            "ubercode": code,
            "ultracode": code,
            "level": str(level),
            "ShowLevel": "1",
            # Maps and their currency are cube reagents, not equipment: the
            # recipes have no level gate, so neither should the items.
            "levelreq": "0",
            # rarity must be non-zero or the item is invisible to the
            # generation path D2RLoader's spawner uses. spawnable=0 below
            # is what actually keeps maps out of random drops.
            "rarity": "1",
            "spawnable": "0",       # only placed deliberately, via TC or cube
            "cost": "5000",
            "gamble cost": "0",
            "type": itype,
            "type2": "",
            "invwidth": "1",
            "invheight": "1",
            "useable": "0",
            "stackable": "0",
            "unique": "0",
            "auto prefix": "",    # do not inherit the small charm's automagic
            # Match every other misc row rather than blanking these. TMogType
            # is a code field and "xxx" is its no-op sentinel; an empty string
            # is not the same thing and is a candidate for the row being
            # rejected at load.
            "Transmogrify": "0",
            "TMogType": "xxx",
        })
        t.append(row)
        existing.add(code)

    for p in plans:
        make(p["item_code"],
             f"{p['theme']['name']} T{p['tier']}",
             p["item_code"],
             cfg.MAP_ITEM_LEVEL[p["tier"]],
             MAP_ITEM_TYPE)
    for cur in cfg.CURRENCY:
        make(cur["code"], cur["name"], cur["code"], cur["level"], MAP_CURRENCY_TYPE)
    return t


# ---------------------------------------------------------------------------
# magicprefix.txt / magicsuffix.txt
#
# spawnable=0 throughout. D2R never rolls these on its own, so an offline
# game never produces a map that promises an effect it cannot deliver. The
# plugin creates affixed maps explicitly and reads them back by affix id.
# ---------------------------------------------------------------------------

def gen_affixes(kind: str, affixes: list[dict]) -> Table:
    fname = "magicprefix.txt" if kind == "prefix" else "magicsuffix.txt"
    t = Table(EXCEL / fname)
    c_name = t.col("name")
    t.drop_tagged(c_name, cfg.AFFIX_TAG)

    for a in affixes:
        row = t.blank_row()
        set_cells(row, t, {
            "name": f"{cfg.AFFIX_TAG}_{a['key']}",
            "version": "100",
            "spawnable": "0",
            "rare": "0",
            "level": str(min(cfg.MAP_ITEM_LEVEL[x] for x in a["tiers"])),
            "maxlevel": "",
            "levelreq": "0",
            "frequency": "0",
            "group": "",
            "itype1": MAP_ITEM_TYPE,
            "multiply": "0",
            "add": "0",
        })
        for slot, prop in enumerate(a.get("props", [])[:3], start=1):
            code, param, lo, hi = prop
            set_cells(row, t, {
                f"mod{slot}code": code,
                f"mod{slot}param": str(param),
                f"mod{slot}min": str(lo),
                f"mod{slot}max": str(hi),
            })
        t.append(row)
    # Native rare generation needs an eligible affix pool. These map-only
    # quality labels deliberately grant no item stats: combat rolls belong to
    # the plugin's item-seed roll, not to carried-item properties.
    row = t.blank_row()
    set_cells(row, t, {
        "name": f"{cfg.AFFIX_TAG}_quality_{kind}", "version": "100",
        "spawnable": "1", "rare": "1", "level": "1", "levelreq": "0",
        "frequency": "1", "group": "2000" if kind == "prefix" else "2001",
        "itype1": MAP_ITEM_TYPE, "multiply": "0", "add": "0",
    })
    t.append(row)
    return t


# ---------------------------------------------------------------------------
# cubemain.txt
#
# Three recipe families, all plain TXT so they work with no plugin:
#   activate  map                     -> Red Portal to that theme+tier
#   upgrade   map + Horadric Orb      -> the same theme one tier higher
#   corrupt   T5 map + Worldstone Shard -> T6
# ---------------------------------------------------------------------------

def gen_cubemain(plans: list[dict]) -> Table:
    t = Table(EXCEL / "cubemain.txt")
    c_desc = t.col("description")
    t.drop_tagged(c_desc, cfg.CUBE_TAG)

    c_in = [t.col(f"input {n}") for n in range(1, 8)]
    c_out = t.col("output")

    by_theme_tier = {(p["theme"]["key"], p["tier"]): p for p in plans}

    def recipe(desc: str, inputs: list[str], output: str,
               numinputs: int) -> list[str]:
        row = t.blank_row()
        set_cells(row, t, {
            "description": f"{cfg.CUBE_TAG} {desc}",
            "enabled": "1",
            "version": "100",
            "numinputs": str(numinputs),
            "min diff": "2",
        })
        for i, spec in enumerate(inputs):
            row[c_in[i]] = spec
        row[c_out] = output
        # Trailing "*eol" style column in this file is a literal 0.
        row[-1] = "0"
        return row

    for p in plans:
        t.append(recipe(
            f"activate {p['theme']['key']} T{p['tier']}",
            [p["item_code"]],
            f'"Red Portal,lvl={p["body_id"]},qty=1"',
            1,
        ))

    for p in plans:
        higher = by_theme_tier.get((p["theme"]["key"], p["tier"] + 1))
        if higher is None or p["tier"] >= 5:
            continue          # tier 6 is corruption-only, never an upgrade
        t.append(recipe(
            f"upgrade {p['theme']['key']} T{p['tier']}",
            [p["item_code"], "mor"],
            higher["item_code"],
            2,
        ))

    for p in plans:
        t.append(recipe(f"reroll {p['theme']['key']} T{p['tier']}",
                        [p["item_code"], "mrl"], p["item_code"], 2))

    for p in plans:
        if p["tier"] != 5:
            continue
        corrupted = by_theme_tier[(p["theme"]["key"], 6)]
        t.append(recipe(
            f"corrupt {p['theme']['key']}",
            [p["item_code"], "mws"],
            corrupted["item_code"],
            2,
        ))

    if getattr(cfg, "TEST_RECIPES", False):
        first = cfg.THEMES[0]["key"]
        for spec in cfg.TIERS:
            tier = spec["tier"]
            target = by_theme_tier[(first, tier)]
            scrolls = "tsc" if tier == 1 else f"tsc,qty={tier}"
            t.append(recipe(
                f"test tier{tier}",
                [scrolls, "isc"],
                target["item_code"],
                tier + 1,
            ))

        # Rotate through themes at a fixed tier, so testing is not stuck on
        # whichever theme the scroll count happens to hand out.
        for index, theme in enumerate(cfg.THEMES):
            nxt = cfg.THEMES[(index + 1) % len(cfg.THEMES)]
            for spec in cfg.TIERS:
                tier = spec["tier"]
                source = by_theme_tier[(theme["key"], tier)]
                dest = by_theme_tier[(nxt["key"], tier)]
                t.append(recipe(
                    f"test cycle {theme['key']} T{tier}",
                    [source["item_code"], "tsc"],
                    dest["item_code"],
                    2,
                ))
    return t


# ---------------------------------------------------------------------------
# Localisation
# ---------------------------------------------------------------------------

# These files do not all end the same way: levels.json carries a trailing
# blank line and item-names.json does not. Remember each file's tail so a
# 30-entry addition stays a 30-entry diff instead of reformatting 100k lines.
_STRING_TAILS: dict[str, str] = {}


def load_strings(name: str) -> list[dict]:
    raw = (STRINGS / name).read_bytes().decode("utf-8-sig")
    _STRING_TAILS[name] = raw[raw.rindex("]") + 1:]
    return json.loads(raw)


def save_strings(name: str, data: list[dict]) -> None:
    (STRINGS / name).write_bytes(string_bytes(name, data))


def string_bytes(name: str, data: list[dict]) -> bytes:
    # Match the existing files byte for byte: 4-space indent, raw non-ASCII,
    # CRLF throughout, and whatever tail the file already had.
    text = json.dumps(data, indent=4, ensure_ascii=False)
    text = text.replace("\r\n", "\n").replace("\n", "\r\n")
    return (text + _STRING_TAILS[name]).encode("utf-8")


LANGS = ["enUS", "zhTW", "deDE", "esES", "frFR", "itIT", "koKR", "plPL",
         "esMX", "jaJP", "ptBR", "ruRU", "zhCN"]


def string_entry(next_id: int, key: str, text: str) -> dict:
    entry = {"id": next_id, "Key": key}
    for lang in LANGS:
        entry[lang] = text
    return entry


def gen_strings(plans: list[dict]) -> dict[str, list[dict]]:
    out = {}

    levels = load_strings("levels.json")
    levels = [e for e in levels if not str(e.get("Key", "")).startswith("RMap")]  # noqa: E501
    next_id = max((int(e["id"]) for e in levels), default=0) + 1
    join = chr(10) if cfg.LEVEL_NAME_TWO_LINE else " ("
    tail = "" if cfg.LEVEL_NAME_TWO_LINE else ")"
    for p in plans:
        theme = p["theme"]["name"]
        levels.append(string_entry(
            next_id, p["body_key"], f"{theme} Map{join}Tier {p['tier']}{tail}"))
        next_id += 1
        levels.append(string_entry(
            next_id, p["boss_key"], f"{theme} Sanctum{join}Tier {p['tier']}{tail}"))
        next_id += 1

    # Shared per theme: the "To ..." text on a warp and the banner shown on
    # entering. Neither needs the tier, so they are not duplicated per tier.
    for theme in cfg.THEMES:
        stem = f"RMap{theme['key'].capitalize()}"
        for key, text in (
            (f"{stem}Warp", f"To the {theme['name']}"),
            (f"{stem}WarpBoss", f"To the {theme['name']} Sanctum"),
            (f"{stem}Entry", f"Entering the {theme['name']}"),
        ):
            levels.append(string_entry(next_id, key, text))
            next_id += 1
    out["levels.json"] = levels

    items = load_strings("item-names.json")
    known = {p["item_code"] for p in plans} | {c["code"] for c in cfg.CURRENCY}
    quality_names = {f"{cfg.AFFIX_TAG}_quality_prefix": "Charted",
                     f"{cfg.AFFIX_TAG}_quality_suffix": "of Exploration"}
    known.update(quality_names)
    items = [e for e in items if e.get("Key") not in known]
    next_id = max((int(e["id"]) for e in items), default=0) + 1
    for p in plans:
        items.append(string_entry(
            next_id, p["item_code"],
            f"{p['theme']['name']} Map (Tier {p['tier']})"))
        next_id += 1
    for cur in cfg.CURRENCY:
        items.append(string_entry(next_id, cur["code"], cur["name"]))
        next_id += 1
    for key, text in quality_names.items():
        items.append(string_entry(next_id, key, text))
        next_id += 1
    out["item-names.json"] = items
    monsters = load_strings("monsters.json")
    monsters = [e for e in monsters if not str(e.get("Key", "")).startswith("RMapBoss")]
    next_id = max(int(e["id"]) for e in monsters) + 1
    for p in plans:
        monsters.append(string_entry(next_id, f"RMapBoss{p['item_code']}",
                                     f"{p['theme']['name']} Warden"))
        next_id += 1
    out["monsters.json"] = monsters
    return out


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Generated C++ header for the plugin
#
# The plugin needs two things it cannot discover on its own:
#   - which level ids are maps, and what theme/tier/baseline each one is
#   - a calibration set of known MonDen/MonUMin/MonUMax values, used to locate
#     those fields inside D2R's compiled Levels row at runtime
# Emitting both from the same source that writes the TXT means the two can
# never drift apart.
# ---------------------------------------------------------------------------

DEFAULT_PLUGIN_HEADER = (
    REPO.parent / "d2rl-plugins" / "plugins" / "maps" / "src" / "map_tables.gen.h")


def gen_plugin_header(plans: list[dict], path: Path, runtime: dict, write=True) -> str:
    levels = Table(EXCEL / "levels.txt")
    c_id = levels.col("Id")
    # All three difficulty variants, so the plugin can locate each one
    # independently instead of assuming they sit contiguously in the row.
    groups = [["MonDen", "MonDen(N)", "MonDen(H)"],
              ["MonUMin", "MonUMin(N)", "MonUMin(H)"],
              ["MonUMax", "MonUMax(N)", "MonUMax(H)"]]
    cols = [[levels.col(n) for n in g] for g in groups]

    # Map levels are excluded on purpose: the plugin rewrites their density
    # and rarity at runtime, so calibrating against them would break on the
    # next table reload once a roll had been applied.
    map_levels = {p["body_id"] for p in plans} | {p["boss_id"] for p in plans}

    calib = []
    for r in levels.rows:
        raw = r[c_id].strip()
        if not raw.isdigit() or int(raw) in map_levels:
            continue
        vals = [[r[c].strip() for c in group] for group in cols]
        if not all(v.isdigit() for group in vals for v in group):
            continue
        calib.append((int(raw), [[int(v) for v in g] for g in vals]))

    theme_index = {t["key"]: i for i, t in enumerate(cfg.THEMES)}

    out = []
    out.append("// Generated by d2r-reimagined-mod/scripts/maps/generate_maps.py")
    out.append("// Do not edit by hand. Re-run the generator instead.")
    out.append("#pragma once")
    out.append("")
    out.append("#include <cstdint>")
    out.append("")
    out.append("namespace RMap {")
    out.append("")
    out.append("struct MapDef {")
    out.append("\tuint16_t bodyLevel;")
    out.append("\tuint16_t bossLevel;")
    out.append("\tuint8_t  theme;")
    out.append("\tuint8_t  tier;")
    out.append("\tuint16_t baseDensity;")
    out.append("\tuint16_t baseUniqueMin;")
    out.append("\tuint16_t baseUniqueMax;")
    out.append("\tchar     itemCode[5];")
    out.append("};")
    out.append("")
    out.append("// One calibration sample per stock level, used to locate the")
    out.append("// density and rarity fields inside the compiled Levels row.")
    out.append("struct LevelSample {")
    out.append("\tuint16_t levelId;")
    out.append("\tuint16_t density[3];    // normal, nightmare, hell")
    out.append("\tuint16_t uniqueMin[3];")
    out.append("\tuint16_t uniqueMax[3];")
    out.append("};")
    out.append("")

    names = ", ".join(f'"{t["name"]}"' for t in cfg.THEMES)
    out.append(f"inline constexpr const char* ThemeNames[] = {{ {names} }};")
    out.append(f"inline constexpr uint32_t ThemeCount = {len(cfg.THEMES)};")
    out.append(f"inline constexpr uint32_t TierCount = {len(cfg.TIERS)};")
    out.append(f"inline constexpr uint16_t FirstMapLevel = {cfg.FIRST_LEVEL_ID};")
    out.append(f"inline constexpr uint16_t LastMapLevel = {plans[-1]['boss_id']};")
    out.append(f"inline constexpr uint32_t StrengthDensityPerPoint = "
               f"{cfg.STRENGTH_DENSITY_PER_POINT};")
    out.append(f"inline constexpr uint32_t StrengthRarityPerPoint = "
               f"{cfg.STRENGTH_RARITY_PER_POINT};")
    out.append("")
    out.append("inline constexpr MapDef Maps[] = {")
    for p in plans:
        out.append(
            f'\t{{ {p["body_id"]}, {p["boss_id"]}, '
            f'{theme_index[p["theme"]["key"]]}, {p["tier"]}, '
            f'{p["spec"]["density"]}, {p["spec"]["umin"]}, {p["spec"]["umax"]}, '
            f'"{p["item_code"]}" }},')
    out.append("};")
    out.append(f"inline constexpr uint32_t MapCount = {len(plans)};")
    out.append("")
    out.append("inline constexpr LevelSample LevelSamples[] = {")
    for lid, (den, umin, umax) in calib:
        def trio(values: list[int]) -> str:
            return "{ " + ", ".join(str(v) for v in values) + " }"
        out.append(f"\t{{ {lid}, {trio(den)}, {trio(umin)}, {trio(umax)} }},")
    out.append("};")
    out.append(f"inline constexpr uint32_t LevelSampleCount = {len(calib)};")
    out.append(f"inline constexpr uint32_t MonPropProbe = {runtime['probe_index']};")
    out.append(f"inline constexpr uint32_t MonPropCount = {runtime['prop_count']};")
    out.append(f"inline constexpr uint32_t FortuneSkill = {runtime['fortune_skill']};")
    out.append(f"inline constexpr uint32_t MagicFindPerTier = {cfg.MAP_MF_PER_TIER};")
    out.append(f"inline constexpr uint32_t MagicFindPerStrength = {cfg.MAP_MF_PER_STRENGTH};")
    out.append("inline constexpr uint32_t MapMonProps[] = { " +
               ", ".join(map(str, runtime["prop_indices"])) + " };")
    out.append("inline constexpr uint32_t AffixSkills[] = { " + ", ".join(
        str(runtime["skills"].get(a["key"], 0)) for a in cfg.AFFIX_PREFIXES + cfg.AFFIX_SUFFIXES) + " };")
    out.append("inline constexpr uint8_t AffixFamilies[] = { " +
               ", ".join(map(str, cfg.AFFIX_FAMILIES)) + " };")
    out.append("")
    out.append("}")
    out.append("")

    text = "\n".join(out)
    if not write:
        return text
    if path.parent.exists():
        path.write_text(text, encoding="utf-8")
        return f"wrote {path} ({len(calib)} calibration samples)"
    return f"SKIPPED {path} (directory does not exist yet)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="validate and report without writing files")
    ap.add_argument("--plugin-header", type=Path, default=DEFAULT_PLUGIN_HEADER,
                    help="where to emit the generated C++ table for the plugin")
    args = ap.parse_args()

    plans = plan()
    tables = [
        gen_levels(plans),
        gen_lvlmaze(plans),
        gen_lvlprest(plans),
        gen_monlvl(),
        gen_uicategories(),
        gen_itemtypes(),
        gen_misc(plans),
        gen_affixes("prefix", cfg.AFFIX_PREFIXES),
        gen_affixes("suffix", cfg.AFFIX_SUFFIXES),
        gen_cubemain(plans),
    ]
    combat, runtime = endgame.generate(sys.modules[__name__], plans, tables[0])
    places, assets = boss_rooms.generate(sys.modules[__name__], plans, tables[0], tables[2], combat[-1])
    import presentation
    assets.update(presentation.generate(sys.modules[__name__], plans, combat[-1]))
    tables.extend(combat)
    tables.append(places)
    # The two banks have different existing treasure classes. Generate against
    # each independently rather than copying RotW loot over the base bank.
    for path in (EXCEL / "treasureclassex.txt", EXCEL / "base" / "treasureclassex.txt"):
        tables.append(endgame.treasure_classes(sys.modules[__name__], plans, path, runtime))
    strings = gen_strings(plans)

    last = plans[-1]
    print(f"themes      {len(cfg.THEMES)}")
    print(f"tiers       {len(cfg.TIERS)}")
    print(f"maps        {len(plans)}")
    print(f"level ids   {cfg.FIRST_LEVEL_ID}-{last['boss_id']}")
    print(f"prest defs  {cfg.FIRST_PREST_DEF}-{last['prest_def']}")
    print(f"monlvl rows {cfg.FIRST_MONLVL_ROW}-"
          f"{cfg.FIRST_MONLVL_ROW + len(cfg.TIERS) - 1}")
    if last["boss_id"] > 254:
        print("WARNING: level ids pass 254; D2R level id headroom is unverified")

    if args.check:
        expected = {t.path: t.to_bytes() for t in tables}
        expected.update({EXCEL / "base" / t.path.name: t.to_bytes() for t in tables
                         if t.path.parent == EXCEL and t.path.name != "treasureclassex.txt"})
        expected.update({STRINGS / n: string_bytes(n, d) for n, d in strings.items()})
        expected.update(assets)
        stale = [str(p) for p, data in expected.items() if not p.exists() or p.read_bytes() != data]
        header = gen_plugin_header(plans, args.plugin_header, runtime, write=False)
        if not args.plugin_header.exists() or args.plugin_header.read_text(encoding="utf-8") != header:
            stale.append(str(args.plugin_header))
        if stale:
            print("Stale generated outputs:\n" + "\n".join(stale))
            return 1
        print("\n--check: all generated tables, banks, strings, rooms and plugin header match; no files written")
        return 0

    for t in tables:
        t.save()
        if t.path.parent == EXCEL and t.path.name != "treasureclassex.txt":
            (EXCEL / "base" / t.path.name).write_bytes(t.path.read_bytes())
        print(f"wrote {t.path.relative_to(REPO)} ({len(t.rows)} rows)")
    for name, data in strings.items():
        save_strings(name, data)
        print(f"wrote {(STRINGS / name).relative_to(REPO)} ({len(data)} entries)")
    for path, data in assets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    print(gen_plugin_header(plans, args.plugin_header, runtime))

    print("\nGenerated tables mirrored to base; treasure classes generated independently for both banks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
