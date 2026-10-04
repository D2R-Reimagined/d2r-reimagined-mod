"""Sandswept Tomb Warden, the Dune Serpent: a Claw Viper on the Vampire AI.

The Warden keeps the Claw Viper body. Its own ClawViper AI only charges
(Skill1). It first ran the Dark Lancer's CorruptLancer AI, and a Warden on
that AI cast nothing in game (2026-09-30, tiers 1 and 5): every stock CorruptLancer skill
is a melee attack, and nothing showed that AI casting a projectile from its
slots. It now runs the Vampire AI, which D2R's monai.txt documents as melee
plus three spells switched on by aip5 bit flags (1 = Skill1, 2 = Skill2,
4 = Skill3) and a Skill4, and which the Infernal Warden showed casting live
from a non-SC mode:

    Skill1  flag 1   Sandstorm, slow dust devils fanned toward the target
                     (two, three from tier 5); the signature
    Skill2  flag 2   Burrowing Rush, the viper's own SerpentCharge toward the
                     target (tier 3+; repeats Sandstorm with the bit off below)
    Skill3  flag 4   repeats Sandstorm, bit always off
    Skill4           repeats Sandstorm (every stock Vampire row fills Skill4)

aip1 is the melee chance, aip2 the chance to use a skill, aip3 the active
range and aip4 the spell chance. The Claw Viper swings A1 (action frame 6) and
casts Sandstorm in A2 (frame 7); the charge keeps the viper's own
seq_serpentcharge. The DT-mode death portal sits in Skill8. Holy Shock and the
random Dust Devils proc are gone.
"""
import warden_kits

AI = 'Vampire'
BODY_CODE = 'SD'
CAST = 'A2'
RUSH_MODE = 'seq_serpentcharge'
SANDSTORM_SLOT, RUSH_SLOT, SPARE_SLOT, REPEAT_SLOT, DEATH_SLOT = 1, 2, 3, 4, 8
FLAGS = {SANDSTORM_SLOT: 1, RUSH_SLOT: 2, SPARE_SLOT: 4}

SANDSTORM = 'rmap_sandstorm'
SANDSTORM_DEVIL = 'rmap_sandstorm_devil'
RUSH = 'SerpentCharge'

# Tier: (Rush in the kit, aip2 use-skill chance). Sandstorm fans three devils
# from tier 5 (calc1, level = tier).
TIERS = {
    1: (False, 30), 2: (False, 30),
    3: (True, 35), 4: (True, 35),
    5: (True, 40), 6: (True, 40),
}
DEVILS = '(lvl < 5) ? 2 : 3'
DEVIL_SPEED = 6        # stock 10: slow enough to walk between
DEVIL_FRAMES = 80      # stock 50
MELEE_CHANCE = 80      # aip1
ACTIVE_RANGE = 24      # aip3, the Infernal Warden's
SPELL_CHANCE = 50      # aip4

# Physical damage per devil hit (HitShift 8, whole), level = tier. The stock
# skill is 500-1000 +500/+1000 a level, which the old tier-scaled proc hit hard.
DEVIL_DAMAGE = dict(min=200, max=300, per_level=(40, 60))


def generate(api, plans, kit, monsters):
    lo, hi = DEVIL_DAMAGE['per_level']
    kit.skill('Dust Devils', SANDSTORM, {
        'monanim': CAST, 'skilldesc': '', 'srvmissilea': SANDSTORM_DEVIL, 'cltmissilea': SANDSTORM_DEVIL,
        'calc1': DEVILS, 'Param1': '', 'aitype': '',
        'MinDam': str(DEVIL_DAMAGE['min']), 'MaxDam': str(DEVIL_DAMAGE['max']),
        **{f'MinLevDam{i}': str(lo) for i in range(1, 6)},
        **{f'MaxLevDam{i}': str(hi) for i in range(1, 6)}})
    kit.missile('dust_devils', SANDSTORM_DEVIL, {
        'Skill': SANDSTORM, 'Vel': str(DEVIL_SPEED), 'MaxVel': str(DEVIL_SPEED), 'Range': str(DEVIL_FRAMES)})

    for plan in plans:
        if plan['theme']['key'] != 'desert':
            continue
        tier = plan['tier']
        boss = monsters.find(monsters.col('Id'), f"rmap_{plan['item_code']}_boss")
        assert boss[monsters.col('Code')] == BODY_CODE, boss[monsters.col('Code')]
        rush, use_skill = TIERS[tier]
        sandstorm = (SANDSTORM, CAST, tier)
        slots = {SANDSTORM_SLOT: sandstorm, SPARE_SLOT: sandstorm, REPEAT_SLOT: sandstorm,
                 RUSH_SLOT: (RUSH, RUSH_MODE, tier) if rush else sandstorm,
                 DEATH_SLOT: (warden_kits.death_skill(monsters, boss), 'DT', 1)}
        flags = FLAGS[SANDSTORM_SLOT] | (FLAGS[RUSH_SLOT] if rush else 0)
        warden_kits.layout(api, monsters, boss, AI, slots,
                           (MELEE_CHANCE, use_skill, ACTIVE_RANGE, SPELL_CHANCE, flags, '', '', ''))
