"""Frozen Depths Warden, the Rime Matron: a Dominus on the ZakarumPriest AI.

The Warden is built on the theme's Dominus (succubuswitch6, WARDENS body) and
runs the Heirophant's ZakarumPriest AI, which D2R's monai.txt documents as
melee plus four slots:

    Skill1  heal an ally within aip6       Glacial Mend, heals her Horrors
                                           (tiers 5-6; empty below)
    Skill2  bolt, aip3 %                   Glacial Orb, a slow frozen orb that
                                           sprays ice bolts; the signature
    Skill3  teleport every aip5 frames     Blink
    Skill4  Blizzard, aip2 %               Blizzard over the target (tier 3+;
                                           repeats Glacial Orb below)

aip1 is the melee chance and aip4 the Skill4/Skill2 split. labheirophant runs
this AI with all four slots filled. Skill4 always holds a real spell (the
Infernal Warden died at full life with its Skill4 empty) and the DT-mode death
portal sits in Skill8. Skill1 stays empty below tier 5 so she cannot heal
herself there; whether ZakarumHeal can target its caster is still unproven.

The Dominus casts in S2 (0CS2HTH, action frame 5) and swings A1 (frame 5).
Glacial Mend and Blink are the stock skills. The orb and Blizzard are clones
whose damage-carrying missiles are map-owned; their client visuals stay stock.
"""
import warden_kits

AI = 'ZakarumPriest'
BODY_CODE = '0C'
CAST = 'S2'
MEND_SLOT, ORB_SLOT, BLINK_SLOT, BLIZZARD_SLOT, DEATH_SLOT = 1, 2, 3, 4, 8

ORB = 'rmap_glacial_orb'
ORB_BALL = 'rmap_glacial_orb_ball'
ORB_BOLT = 'rmap_glacial_orb_bolt'
ORB_NOVA = 'rmap_glacial_orb_nova'
BLIZZARD = 'rmap_blizzard'
BLIZZARD_CENTER = 'rmap_blizzard_center'
BLIZZARD_SHARD = 'rmap_blizzard_shard'
MEND = 'ZakarumHeal'
BLINK = 'MonTeleport'

# Tier: (Blizzard from this tier, Blink interval in frames, Mend).
# Blink runs at every tier (it only moves her); it comes round faster higher up.
TIERS = {
    1: (False, 375, False), 2: (False, 375, False),
    3: (True, 250, False), 4: (True, 250, False),
    5: (True, 175, True), 6: (True, 175, True),
}
MELEE_CHANCE = 60      # aip1
BLIZZARD_CHANCE = 25   # aip2
ORB_CHANCE = 35        # aip3
SPLIT = 50             # aip4, Skill4 vs Skill2
MEND_RANGE = 15        # aip6 where Mend is in the kit (stock Heirophant 40)
MEND_LEVEL = 1         # ZakarumHeal restores 15 + 5 x level

# Cold damage, level = tier. The orb's bolts and nova use HitShift 7 (half);
# each Blizzard shard is whole. Both chill for 3 s.
ORB_DAMAGE = dict(min=240, max=300, per_level=(40, 50), shift=7)
SHARD_DAMAGE = dict(min=120, max=180, per_level=(20, 30))
CHILL = 75


def generate(api, plans, kit, monsters):
    lo, hi = ORB_DAMAGE['per_level']
    kit.skill('MadawcFrozenOrb', ORB, {
        'monanim': CAST, 'srvmissile': ORB_BALL, 'srvmissilea': ORB_BALL, 'cltmissilea': ORB_BALL,
        'HitShift': str(ORB_DAMAGE['shift']), 'EMin': str(ORB_DAMAGE['min']), 'EMax': str(ORB_DAMAGE['max']),
        'ELen': str(CHILL), **{f'ELevLen{i}': '' for i in range(1, 4)},
        **{f'EMinLev{i}': str(lo) for i in range(1, 6)},
        **{f'EMaxLev{i}': str(hi) for i in range(1, 6)}})
    kit.missile('madawc_frozenorb', ORB_BALL, {'SubMissile1': ORB_BOLT, 'HitSubMissile1': ORB_NOVA})
    kit.missile('madawc_frozenorbbolt', ORB_BOLT, {'Skill': ORB})
    kit.missile('madawc_frozenorbnova', ORB_NOVA, {'Skill': ORB})

    # The center rains server shards that carry the damage; the falling-ice
    # visuals are the center's own client missiles and stay stock.
    lo, hi = SHARD_DAMAGE['per_level']
    kit.skill('MonBlizzard', BLIZZARD, {
        'monanim': CAST, 'srvmissilea': BLIZZARD_CENTER, 'cltmissilea': BLIZZARD_CENTER})
    kit.missile('monblizcenter', BLIZZARD_CENTER, {'SubMissile1': BLIZZARD_SHARD})
    kit.missile('monbliz1', BLIZZARD_SHARD, {
        'EMin': str(SHARD_DAMAGE['min']), 'EMax': str(SHARD_DAMAGE['max']), 'ELen': str(CHILL),
        **{f'MinELev{i}': str(lo) for i in range(1, 6)},
        **{f'MaxELev{i}': str(hi) for i in range(1, 6)}})

    for plan in plans:
        if plan['theme']['key'] != 'frozen':
            continue
        tier = plan['tier']
        boss = monsters.find(monsters.col('Id'), f"rmap_{plan['item_code']}_boss")
        assert boss[monsters.col('Code')] == BODY_CODE, boss[monsters.col('Code')]
        blizzard, blink_interval, mend = TIERS[tier]
        slots = {ORB_SLOT: (ORB, CAST, tier), BLINK_SLOT: (BLINK, CAST, 1),
                 BLIZZARD_SLOT: ((BLIZZARD, CAST, tier) if blizzard else (ORB, CAST, tier)),
                 DEATH_SLOT: (warden_kits.death_skill(monsters, boss), 'DT', 1)}
        if mend:
            slots[MEND_SLOT] = (MEND, CAST, MEND_LEVEL)
        warden_kits.layout(api, monsters, boss, AI, slots, (
            MELEE_CHANCE, BLIZZARD_CHANCE, ORB_CHANCE, SPLIT, blink_interval,
            MEND_RANGE if mend else 0, '', ''))
