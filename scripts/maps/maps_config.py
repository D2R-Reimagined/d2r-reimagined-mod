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
    {"tier": 1, "scale": 1.2, "density": 1100, "umin": 2,  "umax": 4},
    {"tier": 2, "scale": 1.4, "density": 1250, "umin": 3,  "umax": 6},
    {"tier": 3, "scale": 1.6, "density": 1400, "umin": 5,  "umax": 8},
    {"tier": 4, "scale": 1.8, "density": 1550, "umin": 7,  "umax": 11},
    {"tier": 5, "scale": 2.0, "density": 1700, "umin": 9,  "umax": 14},
    # Corrupted. Deliberately a cliff, not a step.
    {"tier": 6, "scale": 3.0, "density": 2000, "umin": 12, "umax": 18},
]

# Experience is held flat across the tier block so tiers scale difficulty and
# loot without turning into an xp ladder. Set to None to let it scale with
# `scale` instead.
MONLVL_FLAT_XP = True

# --------------------------------------------------------------------------
# Themes
# --------------------------------------------------------------------------
# Each theme clones an ADJACENT PAIR of existing Forsaken Labyrinth levels:
# a maze body and the preset room it already warps into. Cloning a working
# pair means the tileset, the warp ids, the preset .ds1 files and the Act 5
# monpreset wiring are all combinations the mod already ships and runs.
#
#   body_template  maze level whose layout and tileset the map body reuses
#   boss_template  preset level whose .ds1 (and therefore its boss) is reused
#
# The generator asserts that body_template warps to boss_template, so a bad
# pairing fails loudly instead of producing a map with no exit.

THEMES = [
    {
        "key": "dungeon",
        "name": "Forgotten Dungeon",
        "body_template": 146,   # Forsaken Labyrinth 08, LevelType 24 maze
        "boss_template": 147,   # Forsaken Labyrinth 09, LevelType 24 presets
    },
    {
        "key": "anguish",
        "name": "Halls of Anguish",
        "body_template": 151,   # Forsaken Labyrinth 13, LevelType 32 maze
        "boss_template": 152,   # Forsaken Labyrinth 14, NihlS.ds1
    },
    {
        "key": "catacombs",
        "name": "Forsaken Catacombs",
        "body_template": 157,   # Forsaken Labyrinth 19, LevelType 10 maze
        "boss_template": 158,   # Forsaken Labyrinth 20, Cathy3.ds1
    },
    {
        "key": "frozen",
        "name": "Frozen Depths",
        "body_template": 159,   # Forsaken Labyrinth 21, LevelType 33 maze
        "boss_template": 160,   # Forsaken Labyrinth 21-2, icecave poolrooms
    },
    {
        "key": "worldstone",
        "name": "Worldstone Keep",
        "body_template": 164,   # Forsaken Labyrinth 24, LevelType 34 maze
        "boss_template": 165,   # Forsaken Labyrinth 25, Heart.ds1
    },
]

# --------------------------------------------------------------------------
# Map items
# --------------------------------------------------------------------------
# One misc.txt item per (theme, tier) because a cube recipe matches on an
# item code and has to resolve to one specific level id. Codes are
# "m" + theme letter + tier digit.

ITEM_CODE_PREFIX = "m"
THEME_CODE_LETTERS = {
    "dungeon": "d",
    "anguish": "a",
    "catacombs": "c",
    "frozen": "f",
    "worldstone": "w",
}

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
MAP_MONSTERS = {
    "dungeon": ["vampire5", "unraveler5", "councilmember3"],
    "anguish": ["slinger6", "pantherwoman4", "sandraider5"],
    "catacombs": ["mummy5", "sk_archer5"],
    "frozen": ["frozenhorror5", "succubus5", "snowyeti4", "willowisp3"],
    "worldstone": ["hellbovine", "willowisp3"],
}
MAP_AREA_LEVEL = 86
MAP_MF_PER_TIER = 25
MAP_MF_PER_STRENGTH = 5
# Same affix family cannot occur twice; this also prevents two penalties
# targeting the same aura state from competing.
AFFIX_FAMILIES = [0, 0, 1, 1, 2, 2, 3, 4, 5, 6, 7, 7, 8]


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
