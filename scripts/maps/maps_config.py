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
#                   level id. Several maze routines hardcode that by level id
#                   (D2MOO DrlgMaze.cpp): Act 2 Tomb only for ids 55-58
#                   (DRLGMAZE_PlaceAct2TombStuff), Durance of Hate only for
#                   ids 100-101 (DRLGMAZE_PlaceAct3MephistoStuff), Act 2/3
#                   Sewers only for their stock ids. A body cloned from those
#                   generates with no way into the arena, whatever Vis/Warp
#                   says. Unconditional: Act 1 Catacombs, Act 2 Maggot Lair,
#                   Act 3 Flayer Dungeon/Swampy Pit, Act 5 Ice Caves, Act 5
#                   Baal Temple.
#   arena_template  preset level (DrlgType 2) whose levels.txt/lvlprest.txt
#                   rows supply LevelType, palette, size, Dt1Mask and flags.
#   arena_ds1       the room to clone. A repo path under data/global/tiles/,
#                   or "stock:<path>" for an unmodified D2R file (see
#                   STOCK_DATA). A list selects one file per tier.
#   arena_return    (Vis slot, lvlwarp id) the arena DS1's warp tile answers
#                   to. The player arrives on that tile and can leave by it.
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
        "body_exits": [(1, 49)], # Act 2 Lair Down, slot 1 (as Lair 1 -> 2)
        "arena_template": 138,   # Labyrinth 00: Duriel.ds1 with a slot-2 warp
        "arena_ds1": "Labyrinth/Duriel.ds1",
        "arena_return": (2, 83),
    },
    {
        "key": "kurast",
        "name": "Corrupted Durance",
        # Flayer Dungeon, LevelType 24. Durance of Hate (100) only places its
        # stairs down for stock ids 100-101, same problem as the Tomb.
        "body_template": 88,     # Flayer Dungeon 1, LevelType 24 maze
        "body_exits": [(0, 56)], # Act 3 Dungeon Down, slot 0 (as Flayer 1 -> 2)
        "arena_template": 148,   # Labyrinth 10: MephComp.ds1 with a slot-2 warp
        "arena_ds1": "Labyrinth/MephComp.ds1",
        "arena_return": (2, 83),
    },
    {
        "key": "catacombs",
        "name": "Forsaken Catacombs",
        "body_template": 157,    # Forsaken Labyrinth 19, LevelType 10 maze
        "body_exits": [(1, 18)], # Act 1 Catacombs Down
        "arena_template": 158,   # Forsaken Labyrinth 20, Cathy3.ds1
        "arena_ds1": "Labyrinth/Cathy3.ds1",
        "arena_return": (1, 15),
    },
    {
        "key": "frozen",
        "name": "Frozen Depths",
        "body_template": 159,    # Forsaken Labyrinth 21, LevelType 33 maze
        "body_exits": [(2, 75)], # Act 5 Ice Caves Down Floor
        "arena_template": 160,   # Forsaken Labyrinth 21-2, ice pool rooms
        # One stock pool room per tier. Each carries the Ice Caves Up warp
        # the Cellar of Pity family answers to, so no DS1 editing is needed.
        "arena_ds1": [f"stock:expansion/icecave/poolroom0{n}a.ds1" for n in range(1, 7)],
        "arena_return": (0, 73),
    },
    {
        "key": "worldstone",
        "name": "Worldstone Keep",
        "body_template": 164,    # Forsaken Labyrinth 24, LevelType 34 maze
        "body_exits": [(1, 82)], # Act 5 Baal Temple Down
        "arena_template": 165,   # Forsaken Labyrinth 25, Heart.ds1
        "arena_ds1": "Labyrinth/Heart.ds1",
        "arena_return": (0, 83),
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
    "desert": ["clawviper5", "unraveler5", "scarab5", "wraith5"],
    "kurast": ["councilmember3", "vampire4", "blunderbore4", "zealot3"],
    "catacombs": ["mummy5", "sk_archer5"],
    "frozen": ["frozenhorror5", "succubus5", "snowyeti4", "willowisp3"],
    "worldstone": ["hellbovine", "willowisp3"],
}
MAP_AREA_LEVEL = 86

# --------------------------------------------------------------------------
# Wardens
# --------------------------------------------------------------------------
# A Warden is a superunique built on the theme's first MAP_MONSTERS archetype
# with its own combat kit. Everything here is applied through channels that do
# not depend on the archetype's AI: monprop entries (an aura, plus att-skill
# and gethit-skill procs that fire when the Warden attacks or is struck), the
# El1 melee element, and a superuniques.txt escort. The superunique route is
# what places the escort: minion1/minion2 on a monstats row only spawn for
# level-population monsters, and a DS1-preset monster skips that path (stock
# Diablo lists leviathan and never brings one). Bishibosh, Corpsefire, the Cow
# King and this mod's own Skeleton King all spawn their packs this way. A
# skill-slot aura (Duriel's pattern) was tried first and did not activate on
# these AIs, so the aura is a monprop entry like the map affix auras.
#
# The Warden's monprop row keeps slot 1 for the plugin's combat-MF aura and
# slots 2-3 for the map's rolled affix auras; slot 4 is the Warden's aura and
# the procs occupy slots 5-6. With the penalty hook installed a roll carries at
# most three aura affixes (one per family); the third is dropped on the Warden
# alone and its escort still carries it.
#
#   aura       skills.txt name and base level; +WARDEN_AURA_PER_TIER per tier
#   on_attack  (skill, chance %, base level); level +WARDEN_SKILL_PER_TIER
#   on_struck  (skill, chance %, base level)
#   escort     (minion1 archetype, minion2 archetype, min, max) drawn from the
#              theme's MAP_MONSTERS; counts grow by WARDEN_ESCORT_PER_TIER
#   melee      El1 override: (type, hell min, hell max, duration) or None to
#              keep the archetype's own element
#   drain      life drain override, or None

WARDENS = {
    "desert": {
        "aura": ("MonHolyShock", 8),
        "on_attack": ("Dust Devils", 25, 12),
        "on_struck": ("Chain Lightning", 6, 20),
        "escort": ("clawviper5", "unraveler5", 2, 3),
        "melee": ("cold", 110, 185, 150),
        "drain": None,
    },
    "kurast": {
        "aura": ("MonHolyFire", 8),
        "on_attack": ("CountessFirewall", 20, 12),
        "on_struck": ("Lower Resist", 5, 10),
        "escort": ("councilmember3", "councilmember3", 2, 2),
        "melee": ("fire", 90, 160, 0),
        "drain": None,
    },
    "catacombs": {
        "aura": None,
        "on_attack": None,  # Native timed Plague Pulse replaces random procs.
        "on_struck": None,
        "escort": ("mummy5", "sk_archer5", 3, 5),
        "melee": ("pois", 120, 120, 75),
        "drain": 100,
    },
    "frozen": {
        "aura": ("MonHolyFreeze", 8),
        "on_attack": ("MadawcFrozenOrb", 20, 12),
        "on_struck": ("Summoner Frost Nova", 5, 12),
        "escort": ("frozenhorror5", "snowyeti4", 2, 4),
        "melee": ("cold", 90, 160, 150),
        "drain": None,
    },
    "worldstone": {
        "aura": ("Fanaticism", 8),
        "on_attack": ("Siege Beast Stomp", 25, 12),
        "on_struck": ("Baal Nova", 5, 12),
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
# here lands where 12x used to for a mid archetype.
WARDEN_HP_RATIO = (300, 360)
WARDEN_HP_MULTIPLIER = 6
# Regeneration is a share of max health per frame, so it grew with the health
# multiplier. Act bosses run 0; Wardens do too.
WARDEN_DAMAGE_REGEN = 0
WARDEN_UTRANS = 3               # superunique palette shift
WARDEN_AURA_SLOT = 4            # monprop slot for the Warden's own aura
WARDEN_FIRST_PROC_SLOT = 5      # monprop slots 5-6 are never written by the plugin
WARDEN_AURA_PER_TIER = 2
WARDEN_SKILL_PER_TIER = 4
WARDEN_ESCORT_PER_TIER = 1      # applied to both min and max from tier 2 on
WARDEN_TIER6_ESCORT_BONUS = 2   # the corruption cliff, on top of the per-tier step
# Source archetypes carry 99% immunities; a Warden is capped so no build is
# locked out of a theme. Escorts keep their native values.
WARDEN_RESIST_CAP = 75
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
