"""Sunscar Dunes Warden, the Sun Scarab: a lightning Scarab on the Vampire AI.

The Warden keeps the Scarab body. Its Scarab AI only jabs. It first ran the
Dark Lancer's CorruptLancer AI, and a Warden on that AI cast nothing in game
(2026-09-30, tiers 1 and 5): every stock CorruptLancer
skill is a melee attack. It now runs the Vampire AI, which D2R's monai.txt
documents as melee plus three spells switched on by aip5 bit flags
(1 = Skill1, 2 = Skill2, 4 = Skill3) and a Skill4, and which the Infernal
Warden showed casting live from a non-SC mode:

    Skill1  flag 1   Sunfall, a lobbed charged ball that bursts into bolts
                     where the target stood (Catapult Charged Ball, the
                     lightning twin of the Catacombs Miasma lob); the signature
    Skill2  flag 2   Static Spray, a fan of erratic charged bolts (ImpBolt;
                     tier 3+, repeats Sunfall with the bit off below)
    Skill3  flag 4   Scorch Pulse, a lightning nova around it that punishes
                     standing close (Storm Pulse; tier 5+, repeats Sunfall
                     with the bit off below)
    Skill4           repeats Sunfall (every stock Vampire row fills Skill4)

aip1 is the melee chance, aip2 the chance to use a skill, aip3 the active
range and aip4 the spell chance. The Scarab swings A1 (action frame 8) and
casts in A2 (frame 10). The stock catapult bolts set CollideFriend = 1, which
per the D2R data guide lets them hit the caster and its allies; the clone sets
it to 0. Holy Shock and the random Dust Devils proc are gone; the lightning
melee stays. The DT-mode death portal sits in Skill8.
"""
import warden_kits

AI = 'Vampire'
BODY_CODE = 'SC'
CAST = 'A2'
SUNFALL_SLOT, SPRAY_SLOT, PULSE_SLOT, REPEAT_SLOT, DEATH_SLOT = 1, 2, 3, 4, 8
FLAGS = {SUNFALL_SLOT: 1, SPRAY_SLOT: 2, PULSE_SLOT: 4}

SUNFALL = 'rmap_sunfall'
SUNFALL_BALL = 'rmap_sunfall_ball'
SUNFALL_BOLT = 'rmap_sunfall_bolt'
SPRAY = 'rmap_static_spray'
SPRAY_BOLT = 'rmap_static_bolt'
PULSE = 'rmap_scorch_pulse'
PULSE_RING = 'rmap_scorch_ring'

# Tier: (spells in the kit, aip2 use-skill chance).
TIERS = {
    1: ((SUNFALL,), 30), 2: ((SUNFALL,), 30),
    3: ((SUNFALL, SPRAY), 35), 4: ((SUNFALL, SPRAY), 35),
    5: ((SUNFALL, SPRAY, PULSE), 40), 6: ((SUNFALL, SPRAY, PULSE), 40),
}
SLOTS = {SUNFALL: SUNFALL_SLOT, SPRAY: SPRAY_SLOT, PULSE: PULSE_SLOT}
SPRAY_BOLTS = '(lvl < 5) ? 4 : 6'   # calc1, level = tier
MELEE_CHANCE = 80      # aip1
ACTIVE_RANGE = 24      # aip3, the Infernal Warden's
SPELL_CHANCE = 50      # aip4

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
        spells, use_skill = TIERS[tier]
        sunfall = (SUNFALL, CAST, tier)
        slots = {slot: sunfall for slot in (*SLOTS.values(), REPEAT_SLOT)}
        slots.update({SLOTS[s]: (s, CAST, tier) for s in spells})
        slots[DEATH_SLOT] = (warden_kits.death_skill(monsters, boss), 'DT', 1)
        flags = sum(FLAGS[SLOTS[s]] for s in spells)
        warden_kits.layout(api, monsters, boss, AI, slots,
                           (MELEE_CHANCE, use_skill, ACTIVE_RANGE, SPELL_CHANCE, flags, '', '', ''))
