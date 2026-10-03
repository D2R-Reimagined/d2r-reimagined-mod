"""Ashen Steppes Warden, the Ashen Knight: an Abyss Knight that wards itself.

The Warden is built on the theme's Abyss Knight (doomknight2, WARDENS body)
and keeps its AbyssKnight AI, which D2R's monai.txt documents as melee plus:

    Skill1  missile within aip5, then aip6   Ash Skull, a fire skull (the
            frames of delay                  knight's own srvdofunc 148 shot)
    Skill2  below aip1 % life, aip2 %        Ash Ward, a Bone Armor that
                                             absorbs damage (tier 3+;
                                             repeats Ash Skull with aip2 = 0)

Skill3 is not in the documentation (the stock row holds MonBoneSpirit); it
repeats Ash Skull so it is never empty. The knight casts in S1 (action frame
11) and swings A1 (frame 10).

The stock MonBoneArmor only sets the bonearmor stat (20 + 10 a level, in
256ths) with no absorb event; the player's Bone Armor absorbs through
auraevent1 = absorbdamage, auraeventfunc1 = 22. Ash Ward copies MonBoneArmor
and adds that event with a pool sized for a boss. Holy Fire and the random
Fire Wall proc are gone; the fire melee and Balrog escort stay. The DT-mode
death portal sits in Skill8.
"""
import warden_kits

AI = 'AbyssKnight'
BODY_CODE = 'UM'
CAST = 'S1'
SKULL_SLOT, WARD_SLOT, SPARE_SLOT, DEATH_SLOT = 1, 2, 3, 8

SKULL = 'rmap_ash_skull'
SKULL_MISSILE = 'rmap_ash_skull_m'
WARD = 'rmap_ash_ward'

# Tier: (ward life % threshold or None, aip6 skull delay in frames).
TIERS = {
    1: (None, 100), 2: (None, 100),
    3: (50, 90), 4: (50, 90),
    5: (60, 75), 6: (60, 75),
}
WARD_CHANCE = 5        # aip2, only where the ward is in the kit
MELEE_CHANCE = 80      # aip3
MELEE_DELAY = 5        # aip4, stock
SKULL_RANGE = 20       # aip5 (stock 5 keeps the knight in melee)
APPROACH = 70          # aip7
CIRCLE = 20            # aip8

# Ward pool in life: Param1 + (level - 1) x Param2, level = tier.
WARD_POOL = (1000, 250)
# Fire damage per skull (whole), level = tier, on the missile.
SKULL_DAMAGE = dict(min=250, max=400, per_level=(40, 60))


def generate(api, plans, kit, monsters):
    kit.skill('DoomKnightMissile', SKULL, {'monanim': CAST, 'srvmissilea': SKULL_MISSILE, 'cltmissilea': SKULL_MISSILE})
    lo, hi = SKULL_DAMAGE['per_level']
    kit.missile('undeadmissile2', SKULL_MISSILE, {
        'EMin': str(SKULL_DAMAGE['min']), 'EMax': str(SKULL_DAMAGE['max']),
        **{f'MinELev{i}': str(lo) for i in range(1, 6)},
        **{f'MaxELev{i}': str(hi) for i in range(1, 6)}})
    kit.skill('MonBoneArmor', WARD, {
        'monanim': CAST, 'Param1': str(WARD_POOL[0]), 'Param2': str(WARD_POOL[1]),
        'auraevent1': 'absorbdamage', 'auraeventfunc1': '22'})

    for plan in plans:
        if plan['theme']['key'] != 'steppes':
            continue
        tier = plan['tier']
        boss = monsters.find(monsters.col('Id'), f"rmap_{plan['item_code']}_boss")
        assert boss[monsters.col('Code')] == BODY_CODE and boss[monsters.col('AI')] == AI, boss[0]
        ward, skull_delay = TIERS[tier]
        skull = (SKULL, CAST, tier)
        slots = {SKULL_SLOT: skull, SPARE_SLOT: skull,
                 WARD_SLOT: (WARD, CAST, tier) if ward else skull,
                 DEATH_SLOT: (warden_kits.death_skill(monsters, boss), 'DT', 1)}
        warden_kits.layout(api, monsters, boss, AI, slots, (
            ward or 0, WARD_CHANCE if ward else 0, MELEE_CHANCE, MELEE_DELAY,
            SKULL_RANGE, skull_delay, APPROACH, CIRCLE))
