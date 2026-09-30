"""Infernal Rift Warden, the Forgemaster: a Balrog on the Vampire AI.

The Warden is built on the theme's Balrog (megademon4, WARDENS body) and runs
the Vampire AI, which D2R's monai.txt documents as melee plus three spells
switched on by bit flags in aip5 (1 = Skill1, 2 = Skill2, 4 = Skill3):

    Skill1  "Fireball"   Hellfire Bolt, a slow fireball (tiers 3-6)
    Skill2  "Firewall"   Magma Rift, a firewall through the target (tiers 5-6)
    Skill3  "Meteor"     Brimstone, a meteor with its target circle that leaves
                         burning ground; the signature, from tier 1

aip1 is the melee chance, aip2 the chance to use a skill, aip3 the active range
and aip4 the spell chance. There are no cooldown timers, so aip2 is what paces
Brimstone. Skill4 stays empty and the death portal sits in Skill5, outside the
slots the AI reads. The stock Infernal vampire6 casts all three (aip5 = 7) and
labvampire casts custom SC skills from these slots.

The Balrog body has no SC animation; it casts in S1 (DMS1HTH, action frame 8)
and swings A1. Every Vampire AI row in the game casts in SC, so S1 is the first
thing to confirm in game.
"""
import warden_kits

AI = 'Vampire'
BODY_CODE = 'DM'
CAST = 'S1'
HELLFIRE_SLOT, MAGMA_SLOT, BRIMSTONE_SLOT, DEATH_SLOT = 1, 2, 3, 5
FLAGS = {HELLFIRE_SLOT: 1, MAGMA_SLOT: 2, BRIMSTONE_SLOT: 4}

HELLFIRE = 'rmap_hellfire'
HELLFIRE_BOLT = 'rmap_hellfire_bolt'
MAGMA = 'rmap_magma_rift'
MAGMA_MAKER = 'rmap_magma_maker'
MAGMA_WALL = 'rmap_magma_wall'
BRIMSTONE = 'rmap_brimstone'
BRIMSTONE_CENTER = 'rmap_brimstone_center'
BRIMSTONE_FIRE = 'rmap_brimstone_fire'

# Tier: (spells in the kit, aip2 use-skill chance). Tiers 1-2 teach Brimstone,
# 3-4 add Hellfire Bolt, 5-6 add Magma Rift and cast a little more often.
TIERS = {
    1: ((BRIMSTONE,), 30), 2: ((BRIMSTONE,), 30),
    3: ((BRIMSTONE, HELLFIRE), 35), 4: ((BRIMSTONE, HELLFIRE), 35),
    5: ((BRIMSTONE, HELLFIRE, MAGMA), 40), 6: ((BRIMSTONE, HELLFIRE, MAGMA), 40),
}
SLOTS = {HELLFIRE: HELLFIRE_SLOT, MAGMA: MAGMA_SLOT, BRIMSTONE: BRIMSTONE_SLOT}
MELEE_CHANCE = 80      # aip1
ACTIVE_RANGE = 24      # aip3, stock vampire6 value
SPELL_CHANCE = 50      # aip4

# Fire damage, level = tier. HitShift 8 values are whole life; the ground fire
# (HitShift 3) and the wall (HitShift 2) deal their value / 32 and / 64 every
# frame, about 5-7 a frame (125-175 a second) at tier 1.
BOLT_DAMAGE = dict(min=300, max=450, per_level=(40, 60))        # on the missile
IMPACT_DAMAGE = dict(min=400, max=600, per_level=(60, 90))      # on the skill
GROUND_DAMAGE = dict(min=160, max=224, per_level=(16, 24), shift=3)
WALL_DAMAGE = dict(min=320, max=448, per_level=(32, 48), shift=2)


def _missile_damage(spec, shift='8'):
    lo, hi = spec['per_level']
    return {'EType': 'fire', 'EMin': str(spec['min']), 'EMax': str(spec['max']),
            'HitShift': str(spec.get('shift', shift)),
            **{f'MinELev{i}': str(lo) for i in range(1, 6)},
            **{f'MaxELev{i}': str(hi) for i in range(1, 6)}}


def generate(api, plans, kit, monsters):
    # The Vampire fires a Fireball skill's srvmissile, which carries its damage.
    kit.skill('VampireFireball', HELLFIRE, {'monanim': CAST, 'srvmissile': HELLFIRE_BOLT})
    kit.missile('vampirefireball', HELLFIRE_BOLT, _missile_damage(BOLT_DAMAGE))

    kit.skill('VampireFirewall', MAGMA, {
        'monanim': CAST, 'srvmissilea': MAGMA_MAKER, 'srvmissileb': MAGMA_WALL,
        'cltmissilea': MAGMA_MAKER})
    kit.missile('vampirefirewallmaker', MAGMA_MAKER, {
        'SubMissile1': MAGMA_WALL, 'CltSubMissile1': MAGMA_WALL})
    kit.missile('vampirefirewall', MAGMA_WALL, _missile_damage(WALL_DAMAGE))

    # The target circle lands the meteor (the skill's damage, through the
    # missile's Skill column) and leaves burning ground where it hit.
    lo, hi = IMPACT_DAMAGE['per_level']
    kit.skill('VampireMeteor', BRIMSTONE, {
        'monanim': CAST, 'srvmissilea': BRIMSTONE_CENTER, 'cltmissilea': BRIMSTONE_CENTER,
        'EMin': str(IMPACT_DAMAGE['min']), 'EMax': str(IMPACT_DAMAGE['max']),
        **{f'EMinLev{i}': str(lo) for i in range(1, 6)},
        **{f'EMaxLev{i}': str(hi) for i in range(1, 6)}})
    kit.missile('vampiremeteorcenter', BRIMSTONE_CENTER, {
        'Skill': BRIMSTONE, 'HitSubMissile1': BRIMSTONE_FIRE})
    kit.missile('vampiremeteorfire', BRIMSTONE_FIRE, _missile_damage(GROUND_DAMAGE))

    for plan in plans:
        if plan['theme']['key'] != 'infernal':
            continue
        tier = plan['tier']
        boss = monsters.find(monsters.col('Id'), f"rmap_{plan['item_code']}_boss")
        assert boss[monsters.col('Code')] == BODY_CODE, boss[monsters.col('Code')]
        spells, use_skill = TIERS[tier]
        slots = {SLOTS[s]: (s, CAST, tier) for s in spells}
        slots[DEATH_SLOT] = (warden_kits.death_skill(monsters, boss), 'DT', 1)
        flags = sum(FLAGS[SLOTS[s]] for s in spells)
        warden_kits.layout(api, monsters, boss, AI, slots,
                           (MELEE_CHANCE, use_skill, ACTIVE_RANGE, SPELL_CHANCE, flags, '', '', ''))
