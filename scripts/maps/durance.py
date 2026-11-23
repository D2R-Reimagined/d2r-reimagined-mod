"""Corrupted Durance Warden, the Pyre Hierarch: a kiting fire caster on the
Oblivion Knight AI.

The Warden keeps the Council Member body and runs the OblivionKnight AI,
which D2R's monai.txt documents as a ranged caster that backs away from
anything inside aip1. The Lab's nakrul2 and belial run this AI with custom
skills in Skill1-3, and nakrul2 blinks with Imp Teleport from Skill3, the
teleport Nihlathak uses to get away from players:

    Skill1  ranged cast, aip5 %, aip6 %   Pyre Bolt, a fireball; the main attack
            else Skill3
    Skill2  (stock Bone Armor; nakrul2    Burning Divide, a firewall through
            casts its meteor here)        the target
    Skill3  aip6 % of the ranged casts    Blink (Imp Teleport)
    Skill4  every aip3 frames             Flame Sentinel, a fire totem (Hydra)
                                          at the target

aip2 is the ranged cast range and aip7/aip8 the approach chance and range;
approach stays off, so the Warden never walks in. Skill5 (a doom knight
sequence) and Skill6 (aip4 %) stay empty, aip4 0. The DT-mode death portal
sits in Skill8.

2026-10-14 report: "boss does no dmg, fire wall on ground does no dmg". The
first kit (HighPriest AI) cloned the Countess firewall, which has no server
damage function (no pSrvDmgFunc, no Collision); the wall now clones the
Vampire firewall, which carries the same columns as the sorceress Fire Wall.
Its Sentinel bolts dealt half damage (HitShift 7) from one 8 s hydra, and the
melee rarely landed on a caster. The report asked for totems and a Warden
that teleports and keeps its distance.

The monster Hydra is the sorceress skill: the summoned hydra casts
HydraMissile, whose missile takes its damage from the Hydra skill. The
Sentinel therefore clones all three so its damage and lifetime are map-owned.
"""
import warden_kits

AI = 'OblivionKnight'
BODY_CODE = 'HP'
CAST = 'S1'
BOLT_SLOT, DIVIDE_SLOT, BLINK_SLOT, SENTINEL_SLOT, DEATH_SLOT = 1, 2, 3, 4, 8

BOLT = 'rmap_pyre_bolt'
BOLT_MISSILE = 'rmap_pyre_bolt_missile'
SENTINEL = 'rmap_flame_sentinel'
SENTINEL_SHOT = 'rmap_sentinel_shot'           # the summoned hydra's skill
SENTINEL_BOLT = 'rmap_sentinel_bolt'           # its missile
DIVIDE = 'rmap_burning_divide'
DIVIDE_MAKER = 'rmap_divide_maker'
DIVIDE_WALL = 'rmap_divide_wall'
BLINK = 'Imp Teleport'

# Tier: frames between Flame Sentinels (aip3). Pace divides it by
# WARDEN_PACE, so 100-70 is about 3-2 s.
TIERS = {
    1: 100, 2: 100,
    3: 85, 4: 85,
    5: 70, 6: 70,
}
# petmax, level = tier: two totems, three from tier 3, four from tier 5.
SENTINEL_MAX = '(lvl < 3) ? 2 : ((lvl < 5) ? 3 : 4)'
SENTINEL_FRAMES = 375                 # 15 s (stock 250; the first kit 200)
DIVIDE_FRAMES = 150                   # 6 s of wall (stock countess wall ~40 s)
BOLT_RANGE = 50                       # frames of flight (vampirefireball 30)

RUN_AWAY_RANGE = 15    # aip1: backs off from anything closer (nakrul2 12)
RANGED_RANGE = 100     # aip2, nakrul2's
SKILL6_CHANCE = 0      # aip4: Skill6 is empty
CAST_CHANCE = 100      # aip5, nakrul2's
BLINK_SHARE = 35       # aip6: Blink on this share of the ranged casts (nakrul2 50)

# Fire damage, level = tier, all whole-life (HitShift 8) except the wall
# (HitShift 2), which deals its value / 64 every frame, about 5-7 at tier 1.
BOLT_DAMAGE = dict(min=300, max=450, per_level=(40, 60))
SENTINEL_DAMAGE = dict(min=180, max=260, per_level=(30, 40))
WALL_DAMAGE = dict(min=320, max=448, per_level=(32, 48))


def _missile_damage(spec, shift):
    lo, hi = spec['per_level']
    return {'EType': 'fire', 'EMin': str(spec['min']), 'EMax': str(spec['max']),
            'HitShift': str(shift),
            **{f'MinELev{i}': str(lo) for i in range(1, 6)},
            **{f'MaxELev{i}': str(hi) for i in range(1, 6)}}


def generate(api, plans, kit, monsters):
    kit.skill('VampireFireball', BOLT, {'monanim': CAST, 'srvmissile': BOLT_MISSILE,
                                        'cltmissile': BOLT_MISSILE})
    kit.missile('vampirefireball', BOLT_MISSILE, {'Range': str(BOLT_RANGE), **_missile_damage(BOLT_DAMAGE, 8)})

    lo, hi = SENTINEL_DAMAGE['per_level']
    kit.skill('Hydra', SENTINEL, {
        'monanim': CAST, 'skilldesc': '', 'sumskill1': SENTINEL_SHOT, 'sumsk1calc': 'lvl',
        **{f'sumskill{i}': '' for i in (2, 3)}, **{f'sumsk{i}calc': '' for i in (2, 3)},
        **{f'passivestat{i}': '' for i in (1, 2, 3)}, **{f'passivecalc{i}': '' for i in (1, 2, 3)},
        'petmax': SENTINEL_MAX, 'Param1': str(SENTINEL_FRAMES), 'Param2': '0', 'Param3': '', 'Param8': '',
        'HitShift': '8', 'EDmgSymPerCalc': '',
        'EMin': str(SENTINEL_DAMAGE['min']), 'EMax': str(SENTINEL_DAMAGE['max']),
        **{f'EMinLev{i}': str(lo) for i in range(1, 6)},
        **{f'EMaxLev{i}': str(hi) for i in range(1, 6)}})
    kit.skill('HydraMissile', SENTINEL_SHOT, {'srvmissile': SENTINEL_BOLT, 'cltmissile': SENTINEL_BOLT})
    kit.missile('hydra', SENTINEL_BOLT, {'Skill': SENTINEL})

    # The Vampire firewall's wall damages through pSrvDmgFunc 3 and Collision,
    # like the sorceress Fire Wall; the Countess wall the first kit used has
    # neither and burned nobody.
    kit.skill('VampireFirewall', DIVIDE, {
        'monanim': CAST, 'srvmissilea': DIVIDE_MAKER, 'srvmissileb': DIVIDE_WALL,
        'cltmissilea': DIVIDE_MAKER})
    kit.missile('vampirefirewallmaker', DIVIDE_MAKER, {
        'SubMissile1': DIVIDE_WALL, 'CltSubMissile1': DIVIDE_WALL})
    kit.missile('vampirefirewall', DIVIDE_WALL, {
        'Range': str(DIVIDE_FRAMES), **_missile_damage(WALL_DAMAGE, 2)})

    for plan in plans:
        if plan['theme']['key'] != 'kurast':
            continue
        tier = plan['tier']
        boss = monsters.find(monsters.col('Id'), f"rmap_{plan['item_code']}_boss")
        assert boss[monsters.col('Code')] == BODY_CODE, boss[monsters.col('Code')]
        slots = {BOLT_SLOT: (BOLT, CAST, tier), DIVIDE_SLOT: (DIVIDE, CAST, tier),
                 BLINK_SLOT: (BLINK, CAST, 1), SENTINEL_SLOT: (SENTINEL, CAST, tier),
                 DEATH_SLOT: (warden_kits.death_skill(monsters, boss), 'DT', 1)}
        warden_kits.layout(api, monsters, boss, AI, slots, (
            RUN_AWAY_RANGE, RANGED_RANGE, TIERS[tier], SKILL6_CHANCE,
            CAST_CHANCE, BLINK_SHARE, 0, ''))
