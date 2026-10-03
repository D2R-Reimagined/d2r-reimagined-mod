"""Fallen Travincal Warden, the High Inquisitor: a lightning Council commander.

The Warden keeps the Council Member body and HighPriest AI (the Durance
Warden's too). Where the Durance Hierarch controls the room with fire, the
Inquisitor uses the AI's own lightning slot and drives its Zealots: it keeps
the Fanaticism aura, the one Warden aura that buffs the escort rather than
dealing passive damage. D2R's monai.txt documents the AI as melee plus

    Skill1  aip4 %                 Heaven's Wrath, a strike on the target that
                                   radiates a ring of slow holy bolts (tier 3+;
                                   repeats Judgment with aip4 = 0 below)
    Skill2  aip2 % (aip5 at range, Judgment, a chain lightning; the signature
            aip7 in melee)

with aip3 the delay between skills, aip6 the chance to back away in melee and
aip8 the approach range. Council members cast from these slots in S1 (action
frame 3). Judgment clones Chain Lightning (the willowisps' monster skill).
Heaven's Wrath clones Star of Bethlehem, which the mod's monpal casts as a
monster; the stock radiating bolts set CollideFriend = 1 and the clone clears
it. The stock Hydra (cap 18), the inherited heal, the firewall proc and the
healing Heirophant escort are gone; Zealots and Temple Guards escort it, and
its melee is lightning. The DT-mode death portal sits in Skill8.
"""
import warden_kits

AI = 'HighPriest'
BODY_CODE = 'HP'
CAST = 'S1'
WRATH_SLOT, JUDGMENT_SLOT, DEATH_SLOT = 1, 2, 8

JUDGMENT = 'rmap_judgment'
JUDGMENT_BOLT = 'rmap_judgment_bolt'
WRATH = 'rmap_heavens_wrath'
WRATH_STRIKE = 'rmap_wrath_strike'
WRATH_BOLT = 'rmap_wrath_bolt'

# Tier: (Heaven's Wrath in the kit, aip4 Wrath chance, skill delay aip3 in frames).
TIERS = {
    1: (False, 0, 100), 2: (False, 0, 100),
    3: (True, 30, 90), 4: (True, 30, 90),
    5: (True, 35, 75), 6: (True, 35, 75),
}
JUMPS = '(lvl < 5) ? 3 : 5'   # Judgment chain hits, level = tier
WRATH_DELAY = 20              # frames before the strike lands (stock 10)
MELEE_CHANCE = 60      # aip1
JUDGMENT_CHANCE = 35   # aip2
RANGED_SKILL = 60      # aip5
RUN_AWAY = 10          # aip6
MELEE_SKILL = 30       # aip7
APPROACH_RANGE = 30    # aip8

# Lightning damage (whole), level = tier.
JUDGMENT_DAMAGE = dict(min=150, max=350, per_level=(25, 50))
STRIKE_DAMAGE = dict(min=400, max=600, per_level=(60, 90))
WRATH_BOLT_DAMAGE = dict(min=150, max=250, per_level=(20, 35))


def _skill_damage(spec):
    lo, hi = spec['per_level']
    return {'EType': 'ltng', 'HitShift': '8', 'EMin': str(spec['min']), 'EMax': str(spec['max']),
            'EDmgSymPerCalc': '',
            **{f'EMinLev{i}': str(lo) for i in range(1, 6)},
            **{f'EMaxLev{i}': str(hi) for i in range(1, 6)}}


def _missile_damage(spec):
    lo, hi = spec['per_level']
    return {'EType': 'ltng', 'HitShift': '8', 'EMin': str(spec['min']), 'EMax': str(spec['max']),
            **{f'MinELev{i}': str(lo) for i in range(1, 6)},
            **{f'MaxELev{i}': str(hi) for i in range(1, 6)}}


def generate(api, plans, kit, monsters):
    kit.skill('Chain Lightning', JUDGMENT, {
        'monanim': CAST, 'srvmissilea': JUDGMENT_BOLT, 'srvmissileb': JUDGMENT_BOLT,
        'srvmissilec': JUDGMENT_BOLT, 'cltmissilea': JUDGMENT_BOLT, 'calc1': JUMPS,
        **_skill_damage(JUDGMENT_DAMAGE)})
    kit.missile('chainlightning', JUDGMENT_BOLT, {'Skill': JUDGMENT})

    kit.skill('Star of Bethlehem', WRATH, {
        'monanim': CAST, 'srvmissilea': WRATH_STRIKE, 'cltmissilea': WRATH_STRIKE,
        **_skill_damage(STRIKE_DAMAGE)})
    kit.missile('starofbeth_initial', WRATH_STRIKE, {
        'Skill': WRATH, 'Range': str(WRATH_DELAY), 'HitSubMissile1': WRATH_BOLT})
    kit.missile('starofbeth_bolts', WRATH_BOLT, {'CollideFriend': '0', **_missile_damage(WRATH_BOLT_DAMAGE)})

    for plan in plans:
        if plan['theme']['key'] != 'travincal':
            continue
        tier = plan['tier']
        boss = monsters.find(monsters.col('Id'), f"rmap_{plan['item_code']}_boss")
        assert boss[monsters.col('Code')] == BODY_CODE, boss[monsters.col('Code')]
        wrath, wrath_chance, delay = TIERS[tier]
        judgment = (JUDGMENT, CAST, tier)
        slots = {WRATH_SLOT: (WRATH, CAST, tier) if wrath else judgment, JUDGMENT_SLOT: judgment,
                 DEATH_SLOT: (warden_kits.death_skill(monsters, boss), 'DT', 1)}
        warden_kits.layout(api, monsters, boss, AI, slots, (
            MELEE_CHANCE, JUDGMENT_CHANCE, delay, wrath_chance,
            RANGED_SKILL, RUN_AWAY, MELEE_SKILL, APPROACH_RANGE))
