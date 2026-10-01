"""Sunscar Dunes Warden, the Sun Scarab: a lightning Scarab on the CorruptLancer AI.

The Warden keeps the Scarab body. Its Scarab AI only jabs, so it runs the
Dark Lancer's CorruptLancer AI, which D2R's monai.txt documents as melee plus
three skills with their own chances (aip6-8) behind one use-skill roll (aip2)
and an AI delay (aip3); Sandswept uses it too.

    Skill1  aip6 %   Sunfall, a lobbed charged ball that bursts into bolts
                     where the target stood (Catapult Charged Ball, the
                     lightning twin of the Catacombs Miasma lob); the signature
    Skill2  aip7 %   Static Spray, a fan of erratic charged bolts (ImpBolt;
                     tier 3+, repeats Sunfall with aip7 = 0 below)
    Skill3  aip8 %   Scorch Pulse, a lightning nova around it that punishes
                     standing close (Storm Pulse; tier 5+, repeats Sunfall
                     with aip8 = 0 below)

The Scarab swings A1 (action frame 8) and casts in A2 (frame 10). The stock
catapult bolts set CollideFriend = 1, which per the D2R data guide lets them
hit the caster and its allies; the clone sets it to 0. Holy Shock and the
random Dust Devils proc are gone; the lightning melee stays. The DT-mode death
portal sits in Skill8.
"""
import warden_kits

AI = 'CorruptLancer'
BODY_CODE = 'SC'
CAST = 'A2'
SUNFALL_SLOT, SPRAY_SLOT, PULSE_SLOT, DEATH_SLOT = 1, 2, 3, 8

SUNFALL = 'rmap_sunfall'
SUNFALL_BALL = 'rmap_sunfall_ball'
SUNFALL_BOLT = 'rmap_sunfall_bolt'
SPRAY = 'rmap_static_spray'
SPRAY_BOLT = 'rmap_static_bolt'
PULSE = 'rmap_scorch_pulse'
PULSE_RING = 'rmap_scorch_ring'

# Tier: (spells in the kit, aip7 spray chance, aip8 pulse chance).
TIERS = {
    1: ((SUNFALL,), 0, 0), 2: ((SUNFALL,), 0, 0),
    3: ((SUNFALL, SPRAY), 30, 0), 4: ((SUNFALL, SPRAY), 30, 0),
    5: ((SUNFALL, SPRAY, PULSE), 30, 25), 6: ((SUNFALL, SPRAY, PULSE), 30, 25),
}
SLOTS = {SUNFALL: SUNFALL_SLOT, SPRAY: SPRAY_SLOT, PULSE: PULSE_SLOT}
SPRAY_BOLTS = '(lvl < 5) ? 4 : 6'   # calc1, level = tier
APPROACH = 80          # aip1
USE_SKILL = 20         # aip2
AI_DELAY = 10          # aip3
RUN = 60               # aip4
RUN_RANGE = 10         # aip5
SUNFALL_CHANCE = 35    # aip6

# Lightning damage per hit (HitShift 8, whole), level = tier.
SUNFALL_DAMAGE = dict(min=120, max=220, per_level=(20, 35))
SPRAY_DAMAGE = dict(min=100, max=200, per_level=(15, 30))
PULSE_DAMAGE = dict(min=300, max=450, per_level=(50, 70))


def _lightning(spec):
    lo, hi = spec['per_level']
    return {'EType': 'ltng', 'HitShift': '8', 'EMin': str(spec['min']), 'EMax': str(spec['max']),
            'EDmgSymPerCalc': '',
            **{f'EMinLev{i}': str(lo) for i in range(1, 6)},
            **{f'EMaxLev{i}': str(hi) for i in range(1, 6)}}


def generate(api, plans, kit, monsters):
    kit.skill('Catapult Charged Ball', SUNFALL, {
        'monanim': CAST, 'srvmissilea': SUNFALL_BALL, 'cltmissilea': SUNFALL_BALL, **_lightning(SUNFALL_DAMAGE)})
    kit.missile('catapultchargedball', SUNFALL_BALL, {
        'HitSubMissile1': SUNFALL_BOLT, 'CltHitSubMissile1': SUNFALL_BOLT})
    kit.missile('catapultchargedballbolt', SUNFALL_BOLT, {'Skill': SUNFALL, 'CollideFriend': '0'})

    kit.skill('ImpBolt', SPRAY, {
        'monanim': CAST, 'srvmissilea': SPRAY_BOLT, 'cltmissilea': SPRAY_BOLT,
        'calc1': SPRAY_BOLTS, **_lightning(SPRAY_DAMAGE)})
    kit.missile('imp charged bolt', SPRAY_BOLT, {'Skill': SPRAY})

    kit.skill('Storm Pulse', PULSE, {
        'monanim': CAST, 'skilldesc': '', 'srvmissilea': PULSE_RING, 'srvmissileb': PULSE_RING,
        'srvmissilec': PULSE_RING, 'cltmissilea': PULSE_RING, **_lightning(PULSE_DAMAGE)})
    kit.missile('storm_pulse', PULSE_RING, {'Skill': PULSE})

    for plan in plans:
        if plan['theme']['key'] != 'dunes':
            continue
        tier = plan['tier']
        boss = monsters.find(monsters.col('Id'), f"rmap_{plan['item_code']}_boss")
        assert boss[monsters.col('Code')] == BODY_CODE, boss[monsters.col('Code')]
        spells, spray_chance, pulse_chance = TIERS[tier]
        sunfall = (SUNFALL, CAST, tier)
        slots = {slot: sunfall for slot in SLOTS.values()}
        slots.update({SLOTS[s]: (s, CAST, tier) for s in spells})
        slots[DEATH_SLOT] = (warden_kits.death_skill(monsters, boss), 'DT', 1)
        warden_kits.layout(api, monsters, boss, AI, slots, (
            APPROACH, USE_SKILL, AI_DELAY, RUN, RUN_RANGE, SUNFALL_CHANCE, spray_chance, pulse_chance))
