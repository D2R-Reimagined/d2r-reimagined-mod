"""Design data for the Reimagined mapping system.

This module is the single source of truth. `generate_maps.py` reads it and
rewrites the generated blocks in data/global/excel/*.txt. Nothing here is
written by hand into the game files - re-run the generator instead.

The static population, baseline combat MF, drops and recipes work without the
plugin. Rolled effects require the matching plugin and generated header.
"""

# --------------------------------------------------------------------------
# Sentinels
# --------------------------------------------------------------------------
# Every generated row is tagged so the generator can remove its own previous
# output and stay idempotent. Nothing else in the mod uses these prefixes.

ROW_TAG = "RMAP"          # levels.txt / lvlmaze.txt / lvlprest.txt Name column
CUBE_TAG = "rmap"         # cubemain.txt description column
ITEM_TAG = "RMap"         # misc.txt name column
AFFIX_TAG = "rmapaffix"   # magicprefix/magicsuffix name column

# --------------------------------------------------------------------------
# Level id allocation
# --------------------------------------------------------------------------
# The Forsaken Labyrinth occupies 138-165. Maps start immediately after.
# Two level ids per (theme, tier): a body and a boss room.

FIRST_LEVEL_ID = 166

# lvlprest.txt Def ids. The labyrinth presets used 1092-1104.
FIRST_PREST_DEF = 1105

# The native automap save routine uses a fixed 100-entry DWORD directory.
# Layer is an array index, not an extensible level ID. Using 100+ reads past
# that directory and can hang when an area is saved during a transition.
# Both bodies and arenas retain their stock template's layer. Independent
# exploration across tiers needs a separately validated runtime solution.
AUTOMAP_LAYER_COUNT = 100

# --------------------------------------------------------------------------
# Tiers
# --------------------------------------------------------------------------
# Monster health and damage come from monlvl.txt rows 111-116, which the
# generator writes by scaling the existing level 110 cap row. Tier 6 is only
# reachable by corrupting a tier 5 map.

MONLVL_BASE_ROW = 110      # the existing flat cap row we scale from
FIRST_MONLVL_ROW = 111     # tier 1 lands here

TIERS = [
    # tier, hp/dmg multiplier vs the level 110 row, density, unique min/max
    # Elite packs are the whole Hell Worldstone Keep (Levels 1-3: 3 x 6-8 =
    # 18-24), +10% per tier: +10% at tier 1, +60% at tier 6. Every theme of a
    # tier gets the same count; a T1 body is roughly the size of the Keep.
    {"tier": 1, "scale": 1.2, "density": 1100, "umin": 20, "umax": 26},
    {"tier": 2, "scale": 1.4, "density": 1250, "umin": 22, "umax": 29},
    {"tier": 3, "scale": 1.6, "density": 1400, "umin": 23, "umax": 31},
    {"tier": 4, "scale": 1.8, "density": 1550, "umin": 25, "umax": 34},
    {"tier": 5, "scale": 2.0, "density": 1700, "umin": 27, "umax": 36},
    # Corrupted. Deliberately a cliff, not a step.
    {"tier": 6, "scale": 3.0, "density": 2000, "umin": 29, "umax": 38},
]

# Experience is held flat across the tier block so tiers scale difficulty and
# loot without turning into an xp ladder. Set to None to let it scale with
# `scale` instead.
MONLVL_FLAT_XP = True

# --------------------------------------------------------------------------
# Themes
# --------------------------------------------------------------------------
# A theme is a maze body plus a Warden arena, each described by an existing
# level whose rows already run in this mod or in stock D2R. Nothing here
# requires the two to be neighbours anywhere else: the generator links them
# itself and validates the link against the tileset's own warp pieces.
#
#   body_template   maze level (DrlgType 1) whose layout and tileset the body
#                   reuses. lvlmaze.txt must carry a row for it.
#   body_exits      (Vis slot, lvlwarp id) pairs that become the stairs down
#                   into the arena. Maze DRLG only places a warp piece when the
#                   tileset ships one for that slot, so these are taken from a
#                   stock level with the same transition, not invented.
#
#                   The tileset must also place its stairs-down room for ANY
#                   level id. Several maze routines hardcode that by level id:
#                   Act 2 Tomb only for ids 55-58, Durance of Hate only for
#                   ids 100-101, Act 2/3 Sewers only for their stock ids.
#                   A body cloned from those
#                   generates with no way into the arena, whatever Vis/Warp
#                   says. Unconditional: Act 1 Catacombs, Act 2 Maggot Lair,
#                   Act 3 Flayer Dungeon/Swampy Pit, Act 5 Ice Caves, Act 5
#                   Baal Temple.
#   arena_template  preset level (DrlgType 2) whose levels.txt/lvlprest.txt
#                   rows supply LevelType, palette, size, Dt1Mask and flags.
#   arena_ds1       the room to clone. A repo path under data/global/tiles/,
#                   or "stock:<path>" for an unmodified D2R file (see
#                   STOCK_DATA). A list selects one file per tier.
#                   "custom:<name>" is a purpose-built room from arenas.py
#                   (DS1 and HD scene generated together); its level size
#                   comes from the room, the rest of the row from
#                   arena_template.
#   arena_return    (Vis slot, lvlwarp id) the arena DS1's warp tile answers
#                   to. The player arrives on that tile and can leave by it.
#   body_entry      (Vis slot, lvlwarp id) the room the cube portal drops the
#                   player in. Its Vis points at the body itself, so the
#                   stairs are a live warp that goes nowhere.
#
#                   Why a warp at all: the red portal lands on the first room
#                   of the level's room list that owns a warp tile whose Vis
#                   slot has a lvlwarp. A body whose only live warp is the
#                   arena stairs therefore starts the player beside the
#                   Warden's door. In game (2026-09-21) D2R picks the special
#                   room whose preset the maze routine ASSIGNED first, not the
#                   first in the room list, so the entry slot is that room
#                   per maze routine:
#                     Baal Temple / Catacombs  Prev, the origin room at the
#                                              level centre; Next is a leaf.
#                     Maggot Lair              Next (trapdoor), then Prev.
#                     Flayer Dungeon           Prev, then Next.
#                     Ice Caves                Prev, then Next, then Down.
#                   Only the origin-room cases guarantee real distance; the
#                   leaf cases give two random leaves, which body_rooms makes
#                   worth walking between.
#   body_presets    optional {lvlprest Def: Def} applied when a body room is
#                   constructed (plugin hook; the maze routine and campaign
#                   levels are untouched). Used where the tileset's first
#                   assigned room is the wrong piece for an arrival point.
#                   Swapped rows must match in size, door side and flags.
#   body_rooms      optional (normal, nightmare, hell) room counts replacing
#                   the template's lvlmaze Rooms before the per-tier growth.
#   body_rooms_per_tier
#                   optional rooms added per tier above 1 (default 4). Room
#                   footprints differ per tileset (Lair 10x10, Ice 16x16), so
#                   this is how themes are kept to a similar walkable area.
#                   Every body is 200x200 tiles, so even 10x10 rooms have space
#                   for a few hundred.
#
# The arena_ds1 must contain at least one monster record: the Warden replaces
# the monster nearest the room centre, which is a known walkable position.

THEMES = [
    {
        "key": "desert",
        "name": "Sandswept Tomb",
        # Maggot Lair, LevelType 18. The Tomb tileset (Tal Rasha's Tomb, 66)
        # only places its stairs down for stock ids 55-58, so it left the
        # arena unreachable; the Lair places them for every level.
        "body_template": 62,     # Maggot Lair 1, LevelType 18 maze
        # Lair assigns its Next room first, so that is where the portal
        # lands. Stock, that room holds the trapdoor down and the arena hung
        # off the Prev room's stairs up: players arrived at a way down and
        # left through a way up. body_presets swaps the two rooms' DS1s at
        # construction (both are 10x10 with the same door side and flags),
        # so the first room now carries the stairs up (slot 0) and the other
        # carries the trapdoor (slot 1) down into the arena.
        "body_exits": [(1, 49)], # Act 2 Lair Down: the trapdoor, as Lair 1 -> 2
        "body_entry": (0, 48),   # Act 2 Lair Up: stairs, in the first-assigned room
        # lvlprest Def swaps, Prev W/E/S/N <-> Next W/E/S/N, applied only to
        # this theme's bodies by the plugin's preset-construction hook.
        "body_presets": {497: 501, 498: 502, 499: 503, 500: 504,
                         501: 497, 502: 498, 503: 499, 504: 500},
        # Lair rooms are 10x10 against 16x16 for the Act 5 tilesets, so the
        # stock 18 rooms made a T1 body a third of a Frozen Depths. 80 rooms
        # (+14 per tier) is ~8,000 tiles at T1 and ~15,000 at T6, on par with
        # the Worldstone Keep body at the same tier.
        "body_rooms": (80, 80, 80),
        "body_rooms_per_tier": 14,
        # The Warden's sanctum is purpose-built (arenas.py): a 26x26 tomb hall
        # in the Tomb tileset. Level 138 only supplies the row: LevelType 17,
        # Dt1Mask 639 and the slot-2 red portal (lvlwarp 83) the room keeps.
        "arena_template": 138,
        "arena_ds1": "custom:sandswept",
        "arena_return": (2, 83),
    },
    {
        "key": "kurast",
        "name": "Corrupted Durance",
        # Flayer Dungeon, LevelType 24. Durance of Hate (100) only places its
        # stairs down for stock ids 100-101, same problem as the Tomb.
        "body_template": 88,     # Flayer Dungeon 1, LevelType 24 maze
        # Dungeon assigns its Prev room first, so the portal lands there and
        # the arena keeps the Next trapdoor.
        "body_exits": [(0, 56)], # Act 3 Dungeon Down, slot 0 (as Flayer 1 -> 2)
        "body_entry": (1, 55),   # Act 3 Dungeon Up: the Prev room's stairs
        # Flayer Dungeon 1 is a four-room maze; the Warden was never more than
        # a doorway away. Match the Labyrinth-derived bodies instead.
        "body_rooms": (12, 18, 24),
        # The Warden's council chamber is purpose-built (arenas.py), 20x20 in
        # the Durance of Hate's tiles. Durance of Hate 3 (102) supplies the
        # row: LevelType 22, Dt1Mask 53256 and slot 2 = Mephisto Up (lvlwarp
        # 65), the stock Durance 2 -> 3 stairs, on the room's west wall.
        "arena_template": 102,
        "arena_ds1": "custom:durance",
        "arena_return": (2, 65),
    },
    {
        "key": "catacombs",
        "name": "Forsaken Catacombs",
        "body_template": 157,    # Forsaken Labyrinth 19, LevelType 10 maze
        "body_exits": [(1, 18)], # Act 1 Catacombs Down
        # Catacombs makes the origin room the Prev room: level centre.
        "body_entry": (0, 17),   # Act 1 Catacombs Up (as Catacombs 2 -> 1)
        # The Warden's ossuary chapel is purpose-built (arenas.py), 20x20 in
        # the Catacombs' own tiles. Catacombs 4 (37, Andariel's Lair)
        # supplies the level: LevelType 10, Dt1Mask 57 (base walls, stairs
        # up, floor) and slot 0 = Catacombs Up (lvlwarp 17), the stock
        # Catacombs 3 -> 4 transition the body's stairs down already use.
        "arena_template": 37,
        "arena_ds1": "custom:catacombs",
        "arena_return": (0, 17),
    },
    {
        "key": "frozen",
        "name": "Frozen Depths",
        "body_template": 159,    # Forsaken Labyrinth 21, LevelType 33 maze
        # Ice assigns Prev, then Next, then Down, so the portal lands in the
        # Prev room. Both ways down lead to the arena: left dead, the Next
        # room's stairs looked like the arena entrance and could not be
        # clicked (seen in game, 2026-09-30).
        "body_exits": [(1, 74), (2, 75)],   # Ice Caves Down stairs, Down Floor
        "body_entry": (0, 73),   # Act 5 Ice Caves Up: the Prev room's stairs
        # The Warden's glacier hall is purpose-built (arenas.py), 20x20 in the
        # Ice Caves tileset. Level 160 only supplies the row: LevelType 33,
        # Dt1Mask 1 and the slot-0 Ice Caves Up stairs (lvlwarp 73), which
        # the room carries in its north wall.
        "arena_template": 160,
        "arena_ds1": "custom:frozen",
        "arena_return": (0, 73),
    },
    {
        "key": "worldstone",
        "name": "Worldstone Keep",
        "body_template": 164,    # Forsaken Labyrinth 24, LevelType 34 maze
        "body_exits": [(1, 82)], # Act 5 Baal Temple Down
        # Baal Temple makes the origin room the Prev room: level centre.
        "body_entry": (0, 81),   # Act 5 Baal Temple Up
        # The Warden's throne hall is purpose-built (arenas.py), 20x20 in the
        # Keep's own tiles. The Throne of Destruction row (131) supplies the
        # level: LevelType 34 and slot 0 = Baal Temple Up (lvlwarp 81), the
        # same transition the stock Keep makes from its last maze level.
        # arenas.PRESET widens its Dt1Mask to the Keep's walls and floor.
        "arena_template": 131,
        "arena_ds1": "custom:worldstone",
        "arena_return": (0, 81),
    },
]

# Unmodified D2R files referenced with "stock:". The generator copies each one
# it uses into scripts/maps/stock/ (committed) so a checkout without the
# extracted game data still regenerates. Override with D2R_STOCK_DATA.
STOCK_DATA = r"C:\dev\d2r\base-files\data\data"

# --------------------------------------------------------------------------
# Map items
# --------------------------------------------------------------------------
# One misc.txt item per (theme, tier) because a cube recipe matches on an
# item code and has to resolve to one specific level id. Codes are
# "m" + theme letter + tier digit.

ITEM_CODE_PREFIX = "m"
THEME_CODE_LETTERS = {
    "desert": "d",
    "kurast": "k",
    "catacombs": "c",
    "frozen": "f",
    "worldstone": "w",
    "dunes": "s", "highlands": "h", "travincal": "t", "steppes": "e", "infernal": "i",
}

# Append only: the first thirty maps retain their IDs, codes and roll themes.
THEMES += [
    dict(key="dunes", name="Sunscar Dunes", body_template=42, exterior=True,
         body_size=(80,80), body_entries=[(0,33),(1,34),(2,35),(3,36)], body_entry=(0,33),
         body_exits=[(7,33)], exit_preset=388, initializer=0x3fbd10,
         arena_template=138, arena_ds1="custom:dunes", arena_return=(2,83)),
    dict(key="highlands", name="Forsaken Highlands", body_template=7, exterior=True,
         body_size=(80,80), body_entries=[(3,0),(4,1),(5,2),(6,3)], body_entry=(3,0),
         body_exits=[(7,0)], exit_preset=24, initializer=0x3fac10,
         # Purpose-built Fallen war camp in the wilderness (arenas.py). Level
         # 158 only supplies the row and its slot-2 red portal; arenas.LEVEL
         # switches it to the Act 1 wilderness tiles.
         arena_template=158, arena_ds1="custom:highlands", arena_return=(2,83)),
    dict(key="travincal", name="Fallen Travincal", body_template=83, exterior=True,
         body_size=(64,64), body_entry=(6,83), body_exits=[(0,64)], initializer=0x3fcbe0,
         # Purpose-built High Council courtyard walled by Travincal's stone
         # terraces (arenas.py). Level 148 supplies the row and its slot-2 red
         # portal; arenas.PRESET adds Kurast's terraces to its Dt1Mask.
         arena_template=148, arena_ds1="custom:travincal", arena_return=(2,83)),
    dict(key="steppes", name="Ashen Steppes", body_template=104, exterior=True,
         body_size=(80,64), body_entry=(1,69), body_exits=[(7,69)], exit_preset=811,
         # Purpose-built ruined bastion on the mesa (arenas.py). Level 165 only
         # supplies the row and its slot-0 red portal; arenas.LEVEL switches it
         # to the Mesa tileset.
         initializer=0x3fdc00, arena_template=165, arena_ds1="custom:steppes", arena_return=(0,83)),
    # Abaddon's own maze routine (LevelType 35) ignores lvlmaze Rooms and
    # always builds three rooms in a line, so bodies generate as LevelType 28
    # instead: River of Flame's lava maze, same Act 4 lava tiles, grown to
    # Rooms by the native basic maze. The engine keeps the maze's bounding
    # box within 200x200 (8x8 rooms of 24x24) wherever it drifts, which always
    # leaves room for both stairs up to 32 rooms. The plugin
    # then adds River of Flame's stairs room (stairs_preset, one doorway,
    # north) twice: the self-linked entry, and the Warden exit as far from it
    # as the maze allows. Both are real DT1 warps, visible and clickable.
    dict(key="infernal", name="Infernal Rift", body_template=125, exterior=True,
         body_level_type=28, body_size=(200,200), body_rooms=(22,22,22), body_rooms_per_tier=2,
         body_entry=(6,70), body_exits=[(7,70)], stairs_preset=852, initializer=0,
         # Purpose-built hellforge in the Infernal Pit's fortress style
         # (arenas.py). Level 165 supplies the row: Act 4 Lava tiles and its
         # slot-0 red portal; arenas.PRESET adds Intwalls to its Dt1Mask.
         arena_template=165, arena_ds1="custom:infernal", arena_return=(0,83)),
]

# Base item level per tier, used for item presentation and the item's own
# required level.
MAP_ITEM_LEVEL = {1: 70, 2: 76, 3: 81, 4: 84, 5: 87, 6: 90}

# Supporting currency. These are plain misc items.
CURRENCY = [
    {"code": "mor", "name": "Horadric Orb",
     "desc": "Upgrades a map to the next tier.", "level": 70},
    {"code": "mws", "name": "Worldstone Shard",
     "desc": "Corrupts a tier 5 map into tier 6.", "level": 87},
    {"code": "mrl", "name": "Arcane Relic",
     "desc": "Rerolls the modifiers on a map.", "level": 70},
]

# --------------------------------------------------------------------------
# Affixes
# --------------------------------------------------------------------------
# These are written into magicprefix.txt / magicsuffix.txt with spawnable=0,
# so D2R never rolls them on its own. Offline, maps stay plain and nothing
# advertises an effect the game cannot deliver. With the plugin loaded, the
# plugin derives the actual roll from the map item seed.
#
#   kind    "world"  applied by rewriting the live Levels row (density,
#                    rarity, aura carrier). No save footprint.
#           "player" hostile aura granted to map monsters by the plugin.
#                    Applies to nearby players; no sigil or saved item.
#   strength  contribution to the map's total modifier strength, which
#             raises density and monster rarity on top of the tier baseline.
#   tiers     which map tiers may roll it.
#
# `mod1code` values are Properties.txt codes. Player affixes carry real
# properties so the line renders natively and reads correctly even offline.

AFFIX_PREFIXES = [
    {
        "key": "teeming", "display": "Teeming",
        "kind": "world", "strength": 2, "tiers": [1, 2, 3, 4, 5, 6],
        "density_bonus": 250, "rarity_bonus": 0,
        "props": [],
    },
    {
        "key": "swarming", "display": "Swarming",
        "kind": "world", "strength": 4, "tiers": [3, 4, 5, 6],
        "density_bonus": 500, "rarity_bonus": 1,
        "props": [],
    },
    {
        "key": "storied", "display": "Storied",
        "kind": "world", "strength": 3, "tiers": [2, 3, 4, 5, 6],
        "density_bonus": 0, "rarity_bonus": 4,
        "props": [],
    },
    {
        "key": "legendary", "display": "Legendary",
        "kind": "world", "strength": 5, "tiers": [4, 5, 6],
        "density_bonus": 100, "rarity_bonus": 8,
        "props": [],
    },
    {
        "key": "sapping", "display": "Sapping",
        "kind": "player", "strength": 3, "tiers": [1, 2, 3, 4, 5, 6],
        "density_bonus": 0, "rarity_bonus": 0,
        # -15 percentage points of physical attack damagepercent, not spell damage
        "props": [("dmg%", 0, -15, -15)],
    },
    {
        "key": "withering", "display": "Withering",
        "kind": "player", "strength": 5, "tiers": [3, 4, 5, 6],
        "props": [("dmg%", 0, -30, -30)],
        "density_bonus": 0, "rarity_bonus": 0,
    },
    {
        "key": "unhallowed", "display": "Unhallowed",
        "kind": "player", "strength": 4, "tiers": [2, 3, 4, 5, 6],
        # -2 to all skills, which is how aura strength is reduced. D2R has no
        # "reduced aura effect" stat; see docs/maps-design.md.
        "props": [("allskills", 0, -2, -2)],
        "density_bonus": 0, "rarity_bonus": 0,
    },
]

AFFIX_SUFFIXES = [
    {
        "key": "conviction", "display": "of Conviction",
        "kind": "aura", "strength": 6, "tiers": [3, 4, 5, 6],
        "aura_skill": "Conviction", "aura_level": 10,
        "density_bonus": 0, "rarity_bonus": 2,
        "props": [],
    },
    {
        "key": "might", "display": "of Might",
        "kind": "aura", "strength": 4, "tiers": [2, 3, 4, 5, 6],
        "aura_skill": "Might", "aura_level": 12,
        "density_bonus": 0, "rarity_bonus": 1,
        "props": [],
    },
    {
        "key": "fanaticism", "display": "of Fanaticism",
        "kind": "aura", "strength": 6, "tiers": [4, 5, 6],
        "aura_skill": "Fanaticism", "aura_level": 10,
        "density_bonus": 0, "rarity_bonus": 2,
        "props": [],
    },
    {
        "key": "frailty", "display": "of Frailty",
        "kind": "player", "strength": 4, "tiers": [1, 2, 3, 4, 5, 6],
        # -30 to all resistances
        "props": [("res-all", 0, -30, -30)],
        "density_bonus": 0, "rarity_bonus": 0,
    },
    {
        "key": "ruin", "display": "of Ruin",
        "kind": "player", "strength": 6, "tiers": [4, 5, 6],
        "props": [("res-all", 0, -60, -60)],
        "density_bonus": 0, "rarity_bonus": 0,
    },
    {
        "key": "agony", "display": "of Agony",
        "kind": "player", "strength": 5, "tiers": [3, 4, 5, 6],
        # D2R has no "increased damage taken" property. Negative physical
        # damage reduction is the equivalent. See docs/maps-design.md for the
        # clamping caveat - itemstatcost lists damageresist with a 0 floor,
        # so this needs confirming in game before it is trusted.
        "props": [("red-dmg%", 0, -25, -25)],
        "density_bonus": 0, "rarity_bonus": 0,
    },
]

# Stock Conviction, Might and Fanaticism use one state as both aurastate and
# auratargetstate, and a unit holds one stat list per state. A player's own
# copy of the aura (Infinity, a paladin, a merc) therefore replaces the map
# monster's list on that state and the monster aura silently stops working.
# Map monsters carry clones on their own states instead. endgame.py builds the
# clones from the stock rows; affix and Warden auras name the stock skill and
# go through monster_aura().
MONSTER_AURA_CLONES = {
    "Conviction": "rmap_conviction",
    "Might": "rmap_might",
    "Fanaticism": "rmap_fanaticism",
}


def monster_aura(skill):
    """skills.txt name a map monster actually carries for `skill`."""
    return MONSTER_AURA_CLONES.get(skill, skill)


# Every point of total affix strength adds this much on top of the tier's
# baseline. The plugin applies these; offline they are simply not present.
STRENGTH_DENSITY_PER_POINT = 40
STRENGTH_RARITY_PER_POINT = 1


# --------------------------------------------------------------------------
# Testing shortcuts
# --------------------------------------------------------------------------
# Cube recipes that hand you map items directly, for testing without the item
# spawner. Set to False (and re-run the generator) to strip them for release.
#
#   N town portal scrolls + 1 identify scroll  ->  tier N map, first theme
#   any map + 1 town portal scroll             ->  same tier, next theme
#
# The identify scroll is not decoration: "1 town portal scroll" on its own is
# already the mod's `lab enter` recipe, and 2-6 identify scrolls are lab5
# through lab25. Adding one isc makes every tier a distinct input set, so the
# count still equals the tier and nothing existing is shadowed.
TEST_RECIPES = False

# Mapping has its own combat population; Labyrinth monsters depend on its
# resistance-breaking mechanics and deliberately do not carry normal loot.
#
# Every listed type spawns in every body (NumMon = list length). The native
# monster region holds at most 13 types, so keep lists to 10 or fewer; the
# first entry is the Warden's archetype, the Warden escort must be listed, and
# the last entry is the one population affixes replace. Picks come from each
# theme's source areas in levels.txt, preferring types no other theme uses.
MAP_MONSTERS = {
    # Tal Rasha's tombs, Claw Viper Temple and the Maggot Lair.
    "desert": ["clawviper5", "unraveler5", "sandmaggot5", "swarm4", "scarab5",
               "mummy4", "skmage_pois5", "batdemon5", "wraith5"],
    # Durance of Hate, Flayer Dungeon and the Kurast sewers.
    "kurast": ["councilmember3", "vampire4", "blunderbore4", "bonefetish5",
               "fetishshaman5", "frogdemon3", "thornhulk4", "zealot3"],
    # The greater mummy leads so the Warden gets its body, whose SC cast has an
    # action frame; catacombs.py then runs it on the Summoner AI. The Mummy AI
    # never uses its skill slots, so a mummy5 Warden cannot cast anything.
    "catacombs": ["unraveler5", "mummy5", "sk_archer5", "vampire5", "bighead4",
                  "skmage_fire4", "zombie5", "arach4", "corruptrogue4"],
    "frozen": ["frozenhorror5", "succubus5", "snowyeti4", "skmage_cold5",
               "succubuswitch6", "bloodlord3", "wraith6", "cr_lancer7", "willowisp3"],
    "worldstone": ["hellbovine", "willowisp3", "minion11", "bloodlord5", "vampire7",
                   "dkmag2", "skmage_ltng6", "cr_lancer8", "wraith8"],
    "dunes": ["scarab5", "sandleaper5", "vulture4", "pantherwoman5", "slinger5",
              "sandmaggot4", "brute4", "sandraider5"],
    "highlands": ["goatman5", "corruptrogue5", "cr_archer5", "cr_lancer5", "fallen5",
                  "fallenshaman5", "skmage_fire6", "brute5", "quillrat5"],
    "travincal": ["councilmember3", "zealot3", "cantor3", "baboon5", "fetish5",
                  "fetishblow5", "arach5", "mosquito3", "vampire4"],
    "steppes": ["megademon1", "vilemother1", "fingermage1", "doomknight1", "doomknight2",
                "bighead5", "batdemon4", "regurgitator1"],
    "infernal": ["minion1", "succubus4", "overseer1", "megademon4", "blunderbore6",
                 "vampire6", "bonefetish6", "skmage_ltng5", "imp5"],
}
# Sand maggots lay eggs that hatch into larvae; that is the Maggot Lair. Their
# native spawn column is kept (eggs/larvae are stock rows with no map loot).
# Every other map row clears spawn so no new offspring mechanic appears.
MAP_KEEP_SPAWN = {"sandmaggot4", "sandmaggot5"}
# The monster region the native population routine fills has 13 entries.
MAP_MONSTER_LIMIT = 10
MAP_AREA_LEVEL = 100  # Tiers 1-6: 100-105, for bodies and Warden arenas.

# --------------------------------------------------------------------------
# Wardens
# --------------------------------------------------------------------------
# A Warden is a superunique built on one of the theme's MAP_MONSTERS archetypes
# (the first, unless the kit names a `body`) with its own combat kit. Most kits
# are applied through channels that do not depend on the archetype's AI:
# monprop entries (an aura, plus an att-skill proc that fires when the Warden
# attacks), the El1 melee element, and a superuniques.txt escort. Themes in
# warden_kits.KITS go further and move the Warden onto a stock caster AI with a
# per-tier skill kit. The superunique route is
# what places the escort: minion1/minion2 on a monstats row only spawn for
# level-population monsters, and a DS1-preset monster skips that path (stock
# Diablo lists leviathan and never brings one). Bishibosh, Corpsefire, the Cow
# King and this mod's own Skeleton King all spawn their packs this way. A
# skill-slot aura (Duriel's pattern) was tried first and did not activate on
# these AIs, so the aura is a monprop entry like the map affix auras.
#
# The Warden's monprop row keeps slot 1 for the plugin's combat-MF aura and
# slots 2-3 for the map's rolled affix auras; slot 4 is the Warden's aura, slot
# 5 its attack proc and slot 6 the Warden haste aura. The plugin fills any
# slot left empty with rolled affix auras, and every Warden keeps at least two.
# The random when-struck procs were removed on 2026-09-30 to make room for the
# haste aura; bosses get deliberate casts instead (warden_kits.py).
#
#   aura         skills.txt name and base level; +WARDEN_AURA_PER_TIER per tier.
#                Names in MONSTER_AURA_CLONES are swapped for their clone.
#   on_attack    (skill, chance %, base level); level +WARDEN_SKILL_PER_TIER
#   escort       (minion1 archetype, minion2 archetype, min, max) drawn from the
#                theme's MAP_MONSTERS; counts grow by WARDEN_ESCORT_PER_TIER
#   melee        El1 override: (type, hell min, hell max, duration) or None to
#                keep the archetype's own element
#   drain        life drain override, or None
#   body         optional MAP_MONSTERS archetype to build the Warden on
#   model_scale  optional HD model scale instead of WARDEN_MODEL_SCALE

WARDENS = {
    "dunes": dict(aura=("MonHolyShock",8), on_attack=("Dust Devils",20,12),
                  escort=("scarab5","sandraider5",3,4), melee=("ltng",80,180,0), drain=None),
    "highlands": dict(aura=("Might",8), on_attack=("Siege Beast Stomp",20,12),
                      escort=("goatman5","cr_archer5",3,5), melee=("stun",0,0,20), drain=None),
    "travincal": dict(aura=("Fanaticism",6), on_attack=("CountessFirewall",20,12),
                      escort=("zealot3","cantor3",3,5), melee=("fire",90,160,0), drain=None),
    "steppes": dict(aura=("MonHolyFire",8), on_attack=("Fire Wall",20,12),
                    escort=("megademon1","fingermage1",3,4), melee=("fire",100,180,0), drain=None),
    # The Forgemaster: infernal.py runs a Balrog on the Vampire AI (melee plus
    # Brimstone, Hellfire Bolt and Magma Rift by tier). Its fire melee stays;
    # the Might aura and random procs are gone. Imps teleport in beside it.
    "infernal": dict(aura=None, on_attack=None, escort=("minion1","imp5",4,6),
                     melee=("fire",120,190,0), drain=None, body="megademon4", model_scale=1.4),
    "desert": {
        "aura": ("MonHolyShock", 8),
        "on_attack": ("Dust Devils", 25, 12),
        "escort": ("clawviper5", "unraveler5", 2, 3),
        "melee": ("cold", 110, 185, 150),
        "drain": None,
    },
    "kurast": {
        "aura": ("MonHolyFire", 8),
        "on_attack": ("CountessFirewall", 20, 12),
        "escort": ("councilmember3", "councilmember3", 2, 2),
        "melee": ("fire", 90, 160, 0),
        "drain": None,
    },
    "catacombs": {
        "aura": None,
        # The Plague Abbot: catacombs.py gives it the Summoner AI and a cast
        # kit (Blight Bolt, Plague Pulse, Miasma, Lower Resist). That AI never
        # melees, so there is no melee element, drain, aura or proc. Greater
        # mummy escorts revive the fallen mummies around it.
        "on_attack": None,
        "escort": ("unraveler5", "mummy5", 3, 5),
        "melee": None,
        "drain": None,
    },
    "frozen": {
        # The Rime Matron: frozen.py runs a Dominus on the ZakarumPriest AI
        # (Glacial Orb, Blink, Blizzard, Glacial Mend by tier). The permanent
        # Holy Freeze and the random Frozen Orb proc are gone; the cold melee
        # chills for 3 s instead of 6.
        "aura": None,
        "on_attack": None,
        "escort": ("frozenhorror5", "snowyeti4", 2, 4),
        "melee": ("cold", 90, 160, 75),
        "drain": None,
        "body": "succubuswitch6",
    },
    "worldstone": {
        "aura": ("Fanaticism", 8),
        "on_attack": ("Siege Beast Stomp", 25, 12),
        "escort": ("hellbovine", "willowisp3", 4, 6),
        "melee": ("stun", 0, 0, 30),
        "drain": None,
    },
}
# Warden health is a per-tier ratio independent of the archetype: Hell Bovine
# carries three times the base health of the other archetypes, which made the
# Worldstone Warden a 3x outlier under the old 12x-archetype rule. The ratio
# goes through the same 1.5 x tier scale as the population, then this
# multiplier. Hell uniques receive a further +100% (monumod constant 9), so 6
# here lands where 12x used to for a mid archetype; raised 50% to 9 after
# feedback that Wardens were too easy.
WARDEN_HP_RATIO = (300, 360)
WARDEN_HP_MULTIPLIER = 9
# Applied on top of the archetype's tier-scaled physical and elemental attacks,
# including the WARDENS melee override. Proc and aura skills are unaffected.
WARDEN_DAMAGE_MULTIPLIER = 1.2
# Attack rating (A1TH/A2TH/S1TH) multiplier: +20% at tier 1 and +10% more per
# tier (x1.2 ... x1.7), after reports that Wardens rarely hit high-defence
# characters.
WARDEN_ACCURACY_BASE = 1.2
WARDEN_ACCURACY_PER_TIER = 0.1
# Wardens swing and cast this much faster: a self aura (radius 1) raising
# attackrate and other_animrate, the two stats monster Frenzy speeds up and Holy
# Freeze slows down. The item IAS/FCR stats are player breakpoint stats.
WARDEN_HASTE_PERCENT = 20
WARDEN_HASTE_SKILL = "rmap_warden_haste"
WARDEN_HASTE_SLOT = 6
# Regeneration is a share of max health per frame, so it grew with the health
# multiplier. Act bosses run 0; Wardens do too.
WARDEN_DAMAGE_REGEN = 0
WARDEN_UTRANS = 3               # superunique palette shift
# HD model scale, relative to the archetype's own model, so a Warden stands out
# from its escort and the population. presentation.py writes a scaled copy of
# the archetype's model for the Warden; hit box and pathing are unchanged.
WARDEN_MODEL_SCALE = 2.0
WARDEN_AURA_SLOT = 4            # monprop slot for the Warden's own aura
WARDEN_PROC_SLOT = 5            # monprop slot for the Warden's attack proc
WARDEN_AURA_PER_TIER = 2
WARDEN_SKILL_PER_TIER = 4
WARDEN_ESCORT_PER_TIER = 1      # applied to both min and max from tier 2 on
WARDEN_TIER6_ESCORT_BONUS = 2   # the corruption cliff, on top of the per-tier step
# Source archetypes carry 99% immunities; a Warden is capped so no build is
# locked out of a theme. Escorts keep their native values.
WARDEN_RESIST_CAP = 75


def warden_body(theme_key):
    """MAP_MONSTERS archetype a theme's Warden is built on."""
    return WARDENS[theme_key].get("body", MAP_MONSTERS[theme_key][0])
MAP_MF_PER_TIER = 25
MAP_MF_PER_STRENGTH = 5
# Same affix family cannot occur twice; this also prevents two penalties
# targeting the same aura state from competing.
AFFIX_FAMILIES = [0, 0, 1, 1, 2, 2, 3, 4, 5, 6, 7, 7, 8]

# Version 2 uses distinct item codes so saved legacy maps keep their exact
# deterministic rolls. Existing layouts and their level IDs remain shared.
EXPANSION_ITEM_PREFIX = "x"
LEGACY_AFFIX_COUNT = 13
EXPANSION_AFFIXES = [
    dict(key="bovine", display="Bovine Incursion", kind="population", strength=2,
         tiers=[1, 2, 3, 4, 5, 6], family=9, population=1, weight=10,
         description="Bovine Incursion: some native packs replaced by Hell Bovines"),
    dict(key="coven", display="Witch Coven", kind="population", strength=3,
         tiers=[2, 3, 4, 5, 6], family=9, population=2, weight=10,
         description="Witch Coven: some native packs replaced by Succubi"),
    dict(key="legion", display="Restless Legion", kind="population", strength=2,
         tiers=[1, 2, 3, 4, 5, 6], family=9, population=3, weight=10,
         description="Restless Legion: some native packs replaced by skeletal archers"),
    dict(key="frenzy", display="Blood Frenzy", kind="monster", strength=3,
         tiers=[2, 3, 4, 5, 6], family=10, weight=8,
         monster_props=[("move2", 0, 15, 15), ("swing2", 0, 15, 15)],
         description="Blood Frenzy: body monsters gain 15% movement and attack speed"),
    dict(key="fire_pact", display="Flame Pact", kind="monster", strength=3,
         tiers=[1, 2, 3, 4, 5, 6], family=11, weight=4,
         monster_props=[("dmg-fire", 0, 20, 40)], scale_with_tier=True,
         description="Flame Pact: body monsters add 20-40 fire attack damage per tier"),
    dict(key="cold_pact", display="Frost Pact", kind="monster", strength=3,
         tiers=[1, 2, 3, 4, 5, 6], family=11, weight=4,
         monster_props=[("dmg-cold", 25, 15, 30)], scale_with_tier=True,
         description="Frost Pact: body monsters add 15-30 cold attack damage per tier"),
    dict(key="light_pact", display="Storm Pact", kind="monster", strength=3,
         tiers=[1, 2, 3, 4, 5, 6], family=11, weight=4,
         monster_props=[("dmg-ltng", 0, 5, 60)], scale_with_tier=True,
         description="Storm Pact: body monsters add 5-60 lightning attack damage per tier"),
    dict(key="gilded", display="Gilded", kind="reward", strength=0,
         tiers=[1, 2, 3, 4, 5, 6], family=12, reward=1, weight=8,
         description="Gilded: elite bonus drop chance for gold, gems and mapping currency"),
    dict(key="artificer", display="Artificer's", kind="reward", strength=0,
         tiers=[1, 2, 3, 4, 5, 6], family=12, reward=2, weight=8,
         description="Artificer's: elite bonus drop chance for gems, jewels and equipment"),
]

# Each profile preserves the native number of population slots and substitutes
# only the final slot. No resurrection, on-death spawning, or death damage.
EXPANSION_POPULATIONS = [None, "hellbovine", "succubus5", "sk_archer5"]
EXPANSION_REWARDS = [None, "Gilded", "Artificer"]

# One native group is replaced by a single treasure carrier. The plugin owns
# occurrence; these monsters must never enter a random population or summon pool.
TREASURE_MONSTERS = [
    dict(key="jewel", name="Jewel Hoarder", source="goatman5", palette=8,
         item="jew", rare=0),
    dict(key="amulet", name="Amulet Collector", source="corruptrogue5", palette=12,
         item="amu", rare=1024),
]
TREASURE_DROPS = 6
TREASURE_DEFAULT_CHANCE = 8  # Combined encounter chance: one per 12.5 maps on average.
TREASURE_RELEASE_CHANCE = 8


def all_affixes():
    return AFFIX_PREFIXES + AFFIX_SUFFIXES + EXPANSION_AFFIXES


def expansion_code(code):
    return EXPANSION_ITEM_PREFIX + code[1:]


# --------------------------------------------------------------------------
# Level name presentation
# --------------------------------------------------------------------------
# The in-game area name is driven by the levels.txt LevelName column, which
# points at a levels.json key. Note that *StringName (column 2) is a COMMENT
# column - the leading asterisk makes D2R ignore it entirely - so setting it
# does nothing for what the player sees.
#
# True  -> "Forgotten Dungeon Map\nTier 3"   (two lines, as designed)
# False -> "Forgotten Dungeon Map (Tier 3)"  (single line fallback)
#
# ui.json and item-names.json both use \n freely, but levels.json has no
# existing multi-line entry, so whether the area-name widget honours one is
# unproven. If the newline renders literally, flip this to False and re-run.
LEVEL_NAME_TWO_LINE = True
