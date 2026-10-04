"""Catacombs Warden, the Plague Abbot: a poison caster on the Summoner AI.

The Warden keeps the greater mummy body (GYSCHTH has an action frame, so SC
casts release) and swaps GreaterMummy AI for Summoner, which D2R's monai.txt
documents as five cast slots, two of them on their own timers:

    Skill1  missile within aip8            Blight Bolt, an aimed poison bolt
                                           (a fan of three from tier 4)
    Skill2  "nova" every aip4 frames,      Plague Pulse, a short poison nova
            only within aip7
    Skill3  "firewall" every aip5 frames   Miasma, a lobbed plague ball that
                                           leaves poison clouds where it lands
    Skill5  curse, aip2 % of casts         Lower Resist (tiers 5-6)

aip1 is the chance to cast at all (else it walks closer) and aip6 the chance
to back away from an adjacent target. The AI has no melee attack. Skill4 stays
empty so slot selection is predictable, and the death portal moves to Skill6,
outside the slots the AI reads. `labsummoner` casts SC skills from these slots
in the Labyrinth and `labfiretrap1` runs this AI on a non-Summoner body.
Live-tested 2026-09-30. Clones and HD bindings go through warden_kits.py.
"""
import warden_kits

AI = 'Summoner'
BODY = 'unraveler1'
CAST = 'SC'
BOLT_SLOT, NOVA_SLOT, MIASMA_SLOT, CURSE_SLOT, DEATH_SLOT = 1, 2, 3, 5, 6

NOVA = 'rmap_plague_nova'
BOLT = 'rmap_blight_bolt'
MIASMA = 'rmap_miasma'
MIASMA_BALL = 'rmap_miasma_ball'
MIASMA_CLOUD = 'rmap_miasma_cloud'
CURSE = 'Lower Resist'

# Tier: (Plague Pulse interval, Miasma interval or None, curse level or None).
# Intervals are frames (25 per second). Tiers 1-2 teach the pulse and bolt,
# 3-4 add Miasma, 5-6 add the curse and trim both cooldowns by about 15%.
TIERS = {
    1: (300, None, None), 2: (300, None, None),
    3: (250, 225, None), 4: (250, 225, None),
    5: (215, 190, 1), 6: (215, 190, 2),
}
BOLT_FAN_TIER = 4      # Blight Bolt fires three bolts from this tier (level = tier)
CAST_CHANCE = 70       # aip1
CURSE_CHANCE = 10      # aip2, only where the curse slot is filled
PREFER_COLD = 50       # aip3; every skill here is poison, so it only orders slots
RUN_AWAY_CHANCE = 15   # aip6
NOVA_RANGE = 10        # aip7; the pulse only reaches about 7 subtiles
MISSILE_RANGE = 40     # aip8, stock Summoner value

# Poison is dealt per frame: with HitShift 4 each point is 1/16 life a frame,
# so the pulse is 300-375 over 3 s at tier 1 and ~490-560 at tier 6.
POISON = {
    NOVA: dict(min=64, max=80, per_level=8, frames=75),
    BOLT: dict(min=48, max=64, per_level=6, frames=50),
    MIASMA: dict(min=32, max=40, per_level=4, frames=50),
}


def _poison(skill):
    p = POISON[skill]
    return {'EType': 'pois', 'HitShift': '4', 'EMin': str(p['min']), 'EMax': str(p['max']),
            'ELen': str(p['frames']), 'EDmgSymPerCalc': '',
            **{f'E{kind}Lev{i}': str(p['per_level']) for kind in ('Min', 'Max') for i in range(1, 6)},
            **{f'ELevLen{i}': '' for i in range(1, 4)}}


def generate(api, plans, kit, monsters):
    kit.skill('Poison Nova', NOVA, {
        'monanim': CAST, 'srvmissilea': NOVA, 'cltmissilea': NOVA, **_poison(NOVA)})
    kit.missile('poisonnova', NOVA, {'Skill': NOVA, 'Range': '18'})

    # The Summoner's own slot-1 missile skill (shoot missile, srvdofunc 8), so
    # the server path is the one the Lab already exercises on this AI.
    # calc1 is the projectile count: one bolt, a fan of three from tier 4.
    kit.skill('Summoner Glacial Spike', BOLT, {
        'monanim': CAST, 'srvmissilea': BOLT, 'cltmissilea': BOLT, 'cltmissileb': BOLT,
        'castoverlay': '', 'stsound': 'necromancer_poison_cast',
        'calc1': f'(lvl < {BOLT_FAN_TIER}) ? 1 : 3', '*calc1 desc': '# of Projectiles',
        'auralencalc': '', 'aurarangecalc': '',
        **{f'Param{i}': '' for i in range(1, 9)},
        **{f'*Param{i} Description': '' for i in (1, 2, 3, 4, 7)}, **_poison(BOLT)})
    kit.missile('andypoisonbolt', BOLT, {'Skill': BOLT})

    # The plague catapult's lob (srvdofunc 28, like labmeteor on the Vampire AI):
    # the ball lands where the target stood and bursts into a ring of clouds.
    # Only the clouds carry the skill's damage.
    kit.skill('CatapultPlague', MIASMA, {
        'monanim': CAST, 'srvmissilea': MIASMA_BALL, 'cltmissilea': MIASMA_BALL,
        'stsound': 'necromancer_poison_cast', **_poison(MIASMA)})
    kit.missile('catapult plague ball', MIASMA_BALL, {
        'HitSubMissile1': MIASMA_CLOUD, 'CltHitSubMissile1': MIASMA_CLOUD})
    kit.missile('catapult plague cloud', MIASMA_CLOUD, {'Skill': MIASMA})

    for plan in plans:
        if plan['theme']['key'] != 'catacombs':
            continue
        tier = plan['tier']
        boss = monsters.find(monsters.col('Id'), f"rmap_{plan['item_code']}_boss")
        assert boss[monsters.col('BaseId')] == BODY, boss[monsters.col('BaseId')]
        nova_interval, miasma_interval, curse_level = TIERS[tier]
        slots = {BOLT_SLOT: (BOLT, CAST, tier), NOVA_SLOT: (NOVA, CAST, tier),
                 DEATH_SLOT: (warden_kits.death_skill(monsters, boss), 'DT', 1)}
        if miasma_interval:
            slots[MIASMA_SLOT] = (MIASMA, CAST, tier)
        if curse_level:
            slots[CURSE_SLOT] = (CURSE, CAST, curse_level)
        warden_kits.layout(api, monsters, boss, AI, slots, (
            CAST_CHANCE, CURSE_CHANCE if curse_level else 0, PREFER_COLD, nova_interval,
            miasma_interval or 0, RUN_AWAY_CHANCE, NOVA_RANGE, MISSILE_RANGE))
