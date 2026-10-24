"""Forsaken Highlands Warden, the Fallen Huntress: a fire archer with one
threat for every range.

The Warden is built on the theme's Flesh Archer (cr_archer5, WARDENS body)
and keeps its CorruptArcher AI, which D2R's monai.txt documents as a ranged
kiter: a use-skill roll (aip2), Skill2 and Skill3 with their own chances
(aip6, aip7) and Skill1 otherwise, plus approach (aip1, aip8), run away
(aip4, aip5) and an AI delay (aip3). labcorruptarcher fires custom arrow
skills from all three slots with the bow shot (A1, action frame 5).

    Skill1  default   Ember Volley, a fan of fire arrows (five, seven from
                      tier 5): the long-range threat
    Skill2  aip6 %    Immolation Arrow, an arrow that calls a small meteor
                      where it lands and leaves burning ground: it moves
                      players off their spot
    Skill3  aip7 %    Cinder Rain, fire meteors falling around her for a few
                      seconds (tier 3+; repeats Ember Volley with aip7 = 0
                      below): reaching her through the escort costs something

The first kit (two arrow skills, 2026-09-30) read in game as normal attacks
plus a random multishot (2026-10-12), and the volley drew its source's cold
arrow. Lab bosses threaten at several ranges; this kit follows them.

Ember Volley clones labMonColdArrow (srvstfunc 4, srvdofunc 8: calc1 arrows,
the shoot-missile function Blight Bolt uses). Immolation Arrow clones the
Amazon's (internally Meteoric Arrow), fired like the stock MonFireArrow
(srvstfunc 4 and a srvmissile); its stock burning ground has no HD binding
and a token damage, so the meteor drops the Infernal Brimstone's burn
(vampiremeteorfire) instead, which is drawn and proven in game. Cinder Rain
clones the druid's Armageddon, the fire twin of the Boss_Armageddon that
labdiablo casts: the shared armageddon state's server function spawns the
casting skill's control missile, so the clone needs no state of its own.
Might, the random stomp proc and the stun melee are gone. The DT-mode portal
sits in Skill8.
"""
import warden_kits

AI = 'CorruptArcher'
BODY_CODE = 'CR'
CAST = 'A1'
VOLLEY_SLOT, IMMOLATION_SLOT, RAIN_SLOT, DEATH_SLOT = 1, 2, 3, 8

VOLLEY = 'rmap_ember_volley'
VOLLEY_ARROW = 'rmap_ember_arrow'
IMMOLATION = 'rmap_immolation_arrow'
IMMOLATION_ARROW = 'rmap_immolation_arrow_m'
IMMOLATION_CENTER = 'rmap_immolation_center'
IMMOLATION_FIRE = 'rmap_immolation_fire'
RAIN = 'rmap_cinder_rain'
RAIN_CONTROL = 'rmap_cinder_control'
RAIN_FIRE = 'rmap_cinder_fire'
RAIN_ROCK = 'rmap_cinder_rock'
RAIN_TAIL = 'rmap_cinder_tail'

# Tier: (Cinder Rain in the kit, aip6 Immolation chance, aip7 Rain chance).
TIERS = {
    1: (False, 35, 0), 2: (False, 35, 0),
    3: (True, 35, 25), 4: (True, 35, 25),
    5: (True, 35, 30), 6: (True, 35, 30),
}
VOLLEY_ARROWS = '(lvl < 5) ? 5 : 7'   # calc1, level = tier
RAIN_FRAMES = 150                     # 6 s of meteors (Param1, auralencalc)
RAIN_RADIUS = 10                      # Param3, aurarangecalc (stock 8)
# labcorruptarcher stands its ground (approach 1, skill 99, run away 10,
# delay 6). The first kit approached 60% and ran away 50%, so she stepped in
# and out instead of shooting.
APPROACH = 20          # aip1
USE_SKILL = 90         # aip2; otherwise her plain arrow (75 before 2026-10-14)
AI_DELAY = 6           # aip3, labcorruptarcher's
RUN_AWAY = 10          # aip4, labcorruptarcher's
RUN_RANGE = 15         # aip5
APPROACH_RANGE = 20    # aip8

# Fire damage (whole unless a shift is given), level = tier. Volley arrows also
# carry a share of her own attack damage (SrcDam, 128 = 100%). Burning ground
# deals its value / 32 (shift 3) or / 64 (shift 2) every frame.
VOLLEY_DAMAGE = dict(min=80, max=120, per_level=(15, 25), weapon=64)
IMMOLATION_DAMAGE = dict(min=300, max=450, per_level=(45, 70), weapon=64)
IMMOLATION_BURN = dict(min=160, max=224, per_level=(16, 24), shift=3)
RAIN_DAMAGE = dict(min=250, max=400, per_level=(40, 60))
RAIN_BURN = dict(min=192, max=256, per_level=(16, 24), shift=2)


def _skill_fire(spec):
    lo, hi = spec['per_level']
    return {'EType': 'fire', 'HitShift': '8', 'ELen': '', 'EDmgSymPerCalc': '',
            'EMin': str(spec['min']), 'EMax': str(spec['max']),
            **{f'EMinLev{i}': str(lo) for i in range(1, 6)},
            **{f'EMaxLev{i}': str(hi) for i in range(1, 6)}}


def _missile_fire(spec):
    lo, hi = spec['per_level']
    return {'EType': 'fire', 'HitShift': str(spec['shift']), 'EDmgSymPerCalc': '',
            'EMin': str(spec['min']), 'EMax': str(spec['max']),
            **{f'MinELev{i}': str(lo) for i in range(1, 6)},
            **{f'MaxELev{i}': str(hi) for i in range(1, 6)}}


def generate(api, plans, kit, monsters):
    # The client draws cltmissilea/b. Left on the source's coldarrow, the
    # fire volley rendered as an ice multishot in game (2026-10-12).
    kit.skill('labMonColdArrow', VOLLEY, {
        'monanim': CAST, 'calc1': VOLLEY_ARROWS, 'SrcDam': str(VOLLEY_DAMAGE['weapon']),
        'srvmissilea': VOLLEY_ARROW, 'srvmissileb': VOLLEY_ARROW,
        'cltmissilea': VOLLEY_ARROW, 'cltmissileb': VOLLEY_ARROW, **_skill_fire(VOLLEY_DAMAGE)})
    kit.missile('firearrow', VOLLEY_ARROW, {'Skill': VOLLEY})

    # The arrow's hit drops the meteor center, whose explosion deals the
    # skill's damage and leaves the burn.
    kit.skill('Meteoric Arrow', IMMOLATION, {
        'monanim': CAST, 'srvmissile': IMMOLATION_ARROW, 'cltmissile': IMMOLATION_ARROW,
        'SrcDam': str(IMMOLATION_DAMAGE['weapon']), 'aurarangecalc': '',
        'enhanceable': '', 'leftskill': '', 'rightskill': '', 'InTown': '', **_skill_fire(IMMOLATION_DAMAGE)})
    kit.missile('meteoricarrow', IMMOLATION_ARROW, {
        'Skill': IMMOLATION, 'HitSubMissile1': IMMOLATION_CENTER, 'CltHitSubMissile1': IMMOLATION_CENTER})
    kit.missile('immo_meteorcenter', IMMOLATION_CENTER, {
        'Skill': IMMOLATION, 'HitSubMissile1': IMMOLATION_FIRE})
    kit.missile('vampiremeteorfire', IMMOLATION_FIRE, {'Range': '75', **_missile_fire(IMMOLATION_BURN)})

    # Meteors land around her while the armageddon state lasts; each control
    # missile deals the skill's damage where it lands and leaves a short burn.
    kit.skill('Armageddon', RAIN, {
        'monanim': CAST, 'srvmissilea': RAIN_CONTROL, 'srvmissileb': RAIN_CONTROL,
        'srvmissilec': RAIN_CONTROL, 'cltmissilea': RAIN_TAIL, 'cltmissileb': RAIN_ROCK,
        'auralencalc': 'par1', 'aurarangecalc': 'par3',
        'Param1': str(RAIN_FRAMES), 'Param3': str(RAIN_RADIUS), 'Param5': '', 'Param7': '', 'Param8': '',
        'MinDam': '', 'MaxDam': '', 'DmgSymPerCalc': '',
        **{f'{kind}LevDam{i}': '' for kind in ('Min', 'Max') for i in range(1, 6)},
        'restrict': '', 'enhanceable': '', 'rightskill': '', 'InTown': '', **_skill_fire(RAIN_DAMAGE)})
    kit.missile('armageddoncontrol', RAIN_CONTROL, {'Skill': RAIN, 'HitSubMissile1': RAIN_FIRE})
    kit.missile('armageddonfire', RAIN_FIRE, {'Range': '50', **_missile_fire(RAIN_BURN)})
    kit.missile('armageddonrock', RAIN_ROCK, {})
    kit.missile('armageddontail', RAIN_TAIL, {})

    for plan in plans:
        if plan['theme']['key'] != 'highlands':
            continue
        tier = plan['tier']
        boss = monsters.find(monsters.col('Id'), f"rmap_{plan['item_code']}_boss")
        assert boss[monsters.col('Code')] == BODY_CODE and boss[monsters.col('AI')] == AI, boss[0]
        rain, immolation_chance, rain_chance = TIERS[tier]
        volley = (VOLLEY, CAST, tier)
        slots = {VOLLEY_SLOT: volley, IMMOLATION_SLOT: (IMMOLATION, CAST, tier),
                 RAIN_SLOT: (RAIN, CAST, tier) if rain else volley,
                 DEATH_SLOT: (warden_kits.death_skill(monsters, boss), 'DT', 1)}
        warden_kits.layout(api, monsters, boss, AI, slots, (
            APPROACH, USE_SKILL, AI_DELAY, RUN_AWAY, RUN_RANGE, immolation_chance, rain_chance,
            APPROACH_RANGE))
