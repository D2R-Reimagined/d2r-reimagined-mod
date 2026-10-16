"""Ashen Steppes Warden, the Ashen Knight: a fire knight on the Vampire AI.

The Warden is built on the theme's Abyss Knight (doomknight2, WARDENS body).
Its own AbyssKnight AI casts one missile (Skill1) and a low-life Bone Armor
(Skill2), so the first kit was a fire skull, a ward and his swing: the same
"normal attacks" read the Highlands Warden got in game (2026-10-12). He now
runs the Vampire AI, which D2R's monai.txt documents as melee plus three
spells switched on by aip5 bit flags (1 = Skill1, 2 = Skill2, 4 = Skill3) and
a Skill4, and which the Infernal Warden showed casting live from S1:

    Skill1  flag 1   Ash Skull, a straight fire skull (the knight's own
                     srvdofunc 148 shot): the long-range threat
    Skill2  flag 2   Ash Spirit, a slow homing fire spirit (his stock
                     MonBoneSpirit): it follows players behind cover
    Skill3  flag 4   Ashen Curse, Decrepify: slower, weaker and taking more
                     damage (tier 3+; repeats Ash Skull with the bit off
                     below). laboblivionknight casts it on a knight body.
    Skill4           repeats Ash Skull (every stock Vampire row fills Skill4)

Ember Burst, a fire nova (labFireNova, the Labyrinth fire trap's), goes off
on his swings as an att-skill proc in his monprop proc slot, so standing in
melee with him costs something. WARDENS steppes keeps on_attack None:
endgame.py writes those procs before kit skills exist, so the kit writes this
one (warden_kits.Kit.proc).

aip1 is the melee chance, aip2 the chance to use a skill, aip3 the active
range and aip4 the spell chance. The knight casts in S1 (action frame 11) and
swings A1 (frame 10). The ward (Ash Ward) is gone: on this AI it would be one
random spell in three instead of a low-life reaction. Holy Fire and the
random Fire Wall proc are gone; the fire melee and Balrog escort stay. The
DT-mode death portal sits in Skill8.
"""
import warden_kits

AI = 'Vampire'
BODY_CODE = 'UM'
CAST = 'S1'
SKULL_SLOT, SPIRIT_SLOT, CURSE_SLOT, REPEAT_SLOT, DEATH_SLOT = 1, 2, 3, 4, 8
FLAGS = {SKULL_SLOT: 1, SPIRIT_SLOT: 2, CURSE_SLOT: 4}

SKULL = 'rmap_ash_skull'
SKULL_MISSILE = 'rmap_ash_skull_m'
SPIRIT = 'rmap_ash_spirit'
SPIRIT_MISSILE = 'rmap_ash_spirit_m'
CURSE = 'rmap_ashen_curse'
BURST = 'rmap_ember_burst'
BURST_MISSILE = 'rmap_ember_burst_m'
BURST_RING = 'rmap_ember_burst_ring'

# Tier: (Ashen Curse in the kit, aip2 use-skill chance). Two spells from
# tier 1 and three from tier 3, like every Warden; the Vampire-AI Wardens'
# use-skill chances (aip2/aip4 near 100, see infernal.py).
TIERS = {
    1: (False, 85), 2: (False, 85),
    3: (True, 90), 4: (True, 90),
    5: (True, 95), 6: (True, 95),
}
MELEE_CHANCE = 80      # aip1
ACTIVE_RANGE = 40      # aip3, labvampire's
SPELL_CHANCE = 100     # aip4, labvampire's (was 50)
SPEED = (10, 14)       # Velocity/Run, laboblivionknight's 10/15 (stock 7)
SPIRIT_SPEED = 14      # stock monbonespirit 30: slow enough to outrun
# Ember Burst proc chance on his swings, by tier; level = tier.
BURST_CHANCE = {1: 20, 2: 20, 3: 25, 4: 25, 5: 30, 6: 30}

# Fire damage (whole), level = tier. The Lab trap's nova is a flat 5000.
SKULL_DAMAGE = dict(min=250, max=400, per_level=(40, 60))
SPIRIT_DAMAGE = dict(min=300, max=450, per_level=(45, 70))
BURST_DAMAGE = dict(min=300, max=450, per_level=(50, 75))


def _missile_fire(spec):
    lo, hi = spec['per_level']
    return {'EType': 'fire', 'EMin': str(spec['min']), 'EMax': str(spec['max']),
            **{f'MinELev{i}': str(lo) for i in range(1, 6)},
            **{f'MaxELev{i}': str(hi) for i in range(1, 6)}}


def generate(api, plans, kit, monsters):
    kit.skill('DoomKnightMissile', SKULL, {'monanim': CAST, 'srvmissilea': SKULL_MISSILE, 'cltmissilea': SKULL_MISSILE})
    kit.missile('undeadmissile2', SKULL_MISSILE, _missile_fire(SKULL_DAMAGE))

    kit.skill('MonBoneSpirit', SPIRIT, {
        'monanim': CAST, 'srvmissilea': SPIRIT_MISSILE, 'srvmissileb': SPIRIT_MISSILE,
        'cltmissilea': SPIRIT_MISSILE, 'cltmissileb': SPIRIT_MISSILE})
    kit.missile('monbonespirit', SPIRIT_MISSILE, {
        'Skill': '', 'Vel': str(SPIRIT_SPEED), 'MaxVel': str(SPIRIT_SPEED), **_missile_fire(SPIRIT_DAMAGE)})

    # The curse's effect and duration are the stock skill's (25% slower,
    # weaker and taking more damage; 4 s + 0.6 s a level).
    kit.skill('Decrepify', CURSE, {'monanim': CAST, 'enhanceable': '', 'rightskill': '', 'InTown': ''})

    lo, hi = BURST_DAMAGE['per_level']
    burst = kit.skill('labFireNova', BURST, {
        'srvmissile': BURST_MISSILE, 'cltmissile': BURST_MISSILE,
        'EMin': str(BURST_DAMAGE['min']), 'EMax': str(BURST_DAMAGE['max']),
        **{f'EMinLev{i}': str(lo) for i in range(1, 6)},
        **{f'EMaxLev{i}': str(hi) for i in range(1, 6)}})
    kit.missile('labfirenova', BURST_MISSILE, {
        'Skill': BURST, 'HitSubMissile1': BURST_RING, 'CltHitSubMissile1': BURST_RING})
    kit.missile('labfirenovamiss', BURST_RING, {'Skill': BURST})

    for plan in plans:
        if plan['theme']['key'] != 'steppes':
            continue
        tier = plan['tier']
        boss = monsters.find(monsters.col('Id'), f"rmap_{plan['item_code']}_boss")
        assert boss[monsters.col('Code')] == BODY_CODE, boss[0]
        curse, use_skill = TIERS[tier]
        skull = (SKULL, CAST, tier)
        slots = {SKULL_SLOT: skull, SPIRIT_SLOT: (SPIRIT, CAST, tier),
                 CURSE_SLOT: (CURSE, CAST, tier) if curse else skull, REPEAT_SLOT: skull,
                 DEATH_SLOT: (warden_kits.death_skill(monsters, boss), 'DT', 1)}
        flags = FLAGS[SKULL_SLOT] | FLAGS[SPIRIT_SLOT] | (FLAGS[CURSE_SLOT] if curse else 0)
        warden_kits.layout(api, monsters, boss, AI, slots,
                           (MELEE_CHANCE, use_skill, ACTIVE_RANGE, SPELL_CHANCE, flags, '', '', ''),
                           speed=SPEED)
        kit.proc(boss[monsters.col('Id')], burst, BURST_CHANCE[tier], tier)
