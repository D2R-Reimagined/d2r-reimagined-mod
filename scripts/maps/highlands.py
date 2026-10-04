"""Forsaken Highlands Warden, the Fallen Huntress: a corrupted rogue archer.

The Warden is built on the theme's Flesh Archer (cr_archer5, WARDENS body)
and keeps its CorruptArcher AI, which D2R's monai.txt documents as a ranged
kiter: a use-skill roll (aip2), Skill2 and Skill3 with their own chances
(aip6, aip7) and Skill1 otherwise, plus approach (aip1, aip8), run away
(aip4, aip5) and an AI delay (aip3). labcorruptarcher fires custom arrow
skills from all three slots with the bow shot (A1, action frame 5).

    Skill1  default   Ember Volley, a fan of fire arrows (three, five from
                      tier 5); the signature
    Skill2  aip6 %    Cinder Shot, an exploding fire arrow (tier 3+;
                      repeats Ember Volley with aip6 = 0 below)
    Skill3  aip7 = 0  repeats Ember Volley so the slot is never empty

Both skills clone labMonColdArrow (srvstfunc 4, srvdofunc 8: calc1 arrows,
the same shoot-missile function as Blight Bolt) and only swap the arrow and
its damage. Between skills she shoots her normal arrow (MissA1). The fight is
reaching her through the escort while she backs away. Might, the random
stomp proc and the stun melee are gone. The DT-mode portal sits in Skill8.
"""
import warden_kits

AI = 'CorruptArcher'
BODY_CODE = 'CR'
CAST = 'A1'
VOLLEY_SLOT, CINDER_SLOT, SPARE_SLOT, DEATH_SLOT = 1, 2, 3, 8

VOLLEY = 'rmap_ember_volley'
VOLLEY_ARROW = 'rmap_ember_arrow'
CINDER = 'rmap_cinder_shot'
CINDER_ARROW = 'rmap_cinder_arrow'

# Tier: (Cinder Shot in the kit, aip6 Cinder chance).
TIERS = {
    1: (False, 0), 2: (False, 0),
    3: (True, 30), 4: (True, 30),
    5: (True, 35), 6: (True, 35),
}
VOLLEY_ARROWS = '(lvl < 5) ? 3 : 5'   # calc1, level = tier
APPROACH = 60          # aip1
USE_SKILL = 35         # aip2; otherwise her plain arrow
AI_DELAY = 10          # aip3
RUN_AWAY = 50          # aip4
RUN_RANGE = 15         # aip5
APPROACH_RANGE = 20    # aip8

# Fire damage per arrow (whole), level = tier, plus a share of her own attack
# damage (SrcDam, 128 = 100%).
VOLLEY_DAMAGE = dict(min=80, max=120, per_level=(15, 25), weapon=64)
CINDER_DAMAGE = dict(min=250, max=400, per_level=(40, 60), weapon=128)


def _arrow(spec, count):
    lo, hi = spec['per_level']
    return {'monanim': CAST, 'calc1': count, 'SrcDam': str(spec['weapon']),
            'EType': 'fire', 'HitShift': '8', 'ELen': '',
            'EMin': str(spec['min']), 'EMax': str(spec['max']),
            **{f'EMinLev{i}': str(lo) for i in range(1, 6)},
            **{f'EMaxLev{i}': str(hi) for i in range(1, 6)}}


def generate(api, plans, kit, monsters):
    kit.skill('labMonColdArrow', VOLLEY, {
        'srvmissilea': VOLLEY_ARROW, 'srvmissileb': VOLLEY_ARROW, **_arrow(VOLLEY_DAMAGE, VOLLEY_ARROWS)})
    kit.missile('firearrow', VOLLEY_ARROW, {'Skill': VOLLEY})

    kit.skill('labMonColdArrow', CINDER, {
        'srvmissilea': CINDER_ARROW, 'srvmissileb': CINDER_ARROW, **_arrow(CINDER_DAMAGE, '1')})
    kit.missile('explodingarrow', CINDER_ARROW, {'Skill': CINDER})

    for plan in plans:
        if plan['theme']['key'] != 'highlands':
            continue
        tier = plan['tier']
        boss = monsters.find(monsters.col('Id'), f"rmap_{plan['item_code']}_boss")
        assert boss[monsters.col('Code')] == BODY_CODE and boss[monsters.col('AI')] == AI, boss[0]
        cinder, cinder_chance = TIERS[tier]
        volley = (VOLLEY, CAST, tier)
        slots = {VOLLEY_SLOT: volley, SPARE_SLOT: volley,
                 CINDER_SLOT: (CINDER, CAST, tier) if cinder else volley,
                 DEATH_SLOT: (warden_kits.death_skill(monsters, boss), 'DT', 1)}
        warden_kits.layout(api, monsters, boss, AI, slots, (
            APPROACH, USE_SKILL, AI_DELAY, RUN_AWAY, RUN_RANGE, cinder_chance, 0, APPROACH_RANGE))
