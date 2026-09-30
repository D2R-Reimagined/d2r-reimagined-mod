"""Corrupted Durance Warden, the Pyre Hierarch: zone control on the Council AI.

The Warden keeps the Council Member body and its HighPriest AI, which D2R's
monai.txt documents as melee plus two skills, with aip3 a delay between
skill uses. Stock council members cast Hydra from Skill1 in S1 (action frame
3), so the slots are proven; only their contents change:

    Skill1  aip4 %                 Flame Sentinel, a capped short-lived Hydra
                                   (tier 3+; repeats Burning Divide below)
    Skill2  aip2 % (aip5 at range, Burning Divide, a firewall through the
            aip7 in melee)         target; the signature

aip1 is the melee chance, aip6 the chance to back away in melee and aip8 the
approach range. The stock kit healed (ZakarumHeal, ~35% a cast) and allowed 18
Hydras, and the escort was two more healing Council Members; the heal, Holy
Fire aura and firewall proc are gone and the escort is Zealots and Maulers.
The DT-mode death portal sits in Skill8.

The monster Hydra is the sorceress skill: the summoned hydra casts
HydraMissile, whose missile takes its damage from the Hydra skill. The
Sentinel therefore clones all three so its damage and lifetime are map-owned.
"""
import warden_kits

AI = 'HighPriest'
BODY_CODE = 'HP'
CAST = 'S1'
SENTINEL_SLOT, DIVIDE_SLOT, DEATH_SLOT = 1, 2, 8

SENTINEL = 'rmap_flame_sentinel'
SENTINEL_SHOT = 'rmap_sentinel_shot'           # the summoned hydra's skill
SENTINEL_BOLT = 'rmap_sentinel_bolt'           # its missile
DIVIDE = 'rmap_burning_divide'
DIVIDE_MAKER = 'rmap_divide_maker'
DIVIDE_WALL = 'rmap_divide_wall'

# Tier: (Flame Sentinel in the kit, skill delay aip3 in frames).
TIERS = {
    1: (False, 100), 2: (False, 100),
    3: (True, 90), 4: (True, 90),
    5: (True, 75), 6: (True, 75),
}
SENTINEL_MAX = '(lvl < 5) ? 1 : 2'    # petmax, level = tier: one Sentinel, two from tier 5
SENTINEL_FRAMES = 200                 # 8 s (stock 250)
DIVIDE_FRAMES = 150                   # 6 s of wall (stock countess wall ~40 s)
MELEE_CHANCE = 60      # aip1
DIVIDE_CHANCE = 40     # aip2
SENTINEL_CHANCE = 35   # aip4
RANGED_SKILL = 60      # aip5
RUN_AWAY = 20          # aip6
MELEE_SKILL = 30       # aip7
APPROACH_RANGE = 30    # aip8, stock

# Fire damage, level = tier. Sentinel bolts use HitShift 7 (half); the wall
# (HitShift 2) deals its value / 64 every frame, about 5-7 at tier 1.
SENTINEL_DAMAGE = dict(min=200, max=260, per_level=(30, 40))
WALL_DAMAGE = dict(min=320, max=448, per_level=(32, 48))


def generate(api, plans, kit, monsters):
    lo, hi = SENTINEL_DAMAGE['per_level']
    kit.skill('Hydra', SENTINEL, {
        'monanim': CAST, 'skilldesc': '', 'sumskill1': SENTINEL_SHOT, 'sumsk1calc': 'lvl',
        **{f'sumskill{i}': '' for i in (2, 3)}, **{f'sumsk{i}calc': '' for i in (2, 3)},
        **{f'passivestat{i}': '' for i in (1, 2, 3)}, **{f'passivecalc{i}': '' for i in (1, 2, 3)},
        'petmax': SENTINEL_MAX, 'Param1': str(SENTINEL_FRAMES), 'Param2': '0', 'Param3': '', 'Param8': '',
        'EDmgSymPerCalc': '', 'EMin': str(SENTINEL_DAMAGE['min']), 'EMax': str(SENTINEL_DAMAGE['max']),
        **{f'EMinLev{i}': str(lo) for i in range(1, 6)},
        **{f'EMaxLev{i}': str(hi) for i in range(1, 6)}})
    kit.skill('HydraMissile', SENTINEL_SHOT, {'srvmissile': SENTINEL_BOLT, 'cltmissile': SENTINEL_BOLT})
    kit.missile('hydra', SENTINEL_BOLT, {'Skill': SENTINEL})

    lo, hi = WALL_DAMAGE['per_level']
    kit.skill('CountessFirewall', DIVIDE, {
        'monanim': CAST, 'srvmissilea': DIVIDE_MAKER, 'srvmissileb': DIVIDE_WALL,
        'cltmissilea': DIVIDE_MAKER})
    kit.missile('countessfirewallmaker', DIVIDE_MAKER, {'SubMissile1': DIVIDE_WALL})
    kit.missile('countessfirewall', DIVIDE_WALL, {
        'Range': str(DIVIDE_FRAMES), 'HitShift': '2',
        'EMin': str(WALL_DAMAGE['min']), 'EMax': str(WALL_DAMAGE['max']),
        **{f'MinELev{i}': str(lo) for i in range(1, 6)},
        **{f'MaxELev{i}': str(hi) for i in range(1, 6)}})

    for plan in plans:
        if plan['theme']['key'] != 'kurast':
            continue
        tier = plan['tier']
        boss = monsters.find(monsters.col('Id'), f"rmap_{plan['item_code']}_boss")
        assert boss[monsters.col('Code')] == BODY_CODE, boss[monsters.col('Code')]
        sentinel, delay = TIERS[tier]
        slots = {SENTINEL_SLOT: ((SENTINEL if sentinel else DIVIDE), CAST, tier),
                 DIVIDE_SLOT: (DIVIDE, CAST, tier),
                 DEATH_SLOT: (warden_kits.death_skill(monsters, boss), 'DT', 1)}
        warden_kits.layout(api, monsters, boss, AI, slots, (
            MELEE_CHANCE, DIVIDE_CHANCE, delay, SENTINEL_CHANCE,
            RANGED_SKILL, RUN_AWAY, MELEE_SKILL, APPROACH_RANGE))
