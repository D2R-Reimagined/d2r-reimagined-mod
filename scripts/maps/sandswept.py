"""Sandswept Tomb Warden, the Dune Serpent: a Claw Viper on the CorruptLancer AI.

The Warden keeps the Claw Viper body. Its own ClawViper AI only charges
(Skill1), so it runs the Dark Lancer's CorruptLancer AI, which D2R's monai.txt
documents as melee plus three skills, each with its own chance, behind one
"use a skill" roll and an AI delay:

    Skill1  aip6 %   Sandstorm, slow dust devils fanned toward the target
                     (two, three from tier 5); the signature
    Skill2  aip7 %   Burrowing Rush, the viper's own SerpentCharge toward the
                     target (tier 3+; repeats Sandstorm with aip7 = 0 below)
    Skill3  aip8 %   repeats Sandstorm with aip8 = 0, so the slot is never empty

aip1 is the approach chance, aip2 the use-skill roll, aip3 the AI delay, aip4
run-else-walk and aip5 the always-run range. The stock Dark Lancer casts both a
sequence skill (Jab) and a missile skill (MonIceSpear, A1) from these slots.
The Claw Viper swings A1 (action frame 6) and casts Sandstorm in A2 (frame 7);
the charge keeps the viper's own seq_serpentcharge. The DT-mode death portal
sits in Skill8. Holy Shock and the random Dust Devils proc are gone.
"""
import warden_kits

AI = 'CorruptLancer'
BODY_CODE = 'SD'
CAST = 'A2'
RUSH_MODE = 'seq_serpentcharge'
SANDSTORM_SLOT, RUSH_SLOT, SPARE_SLOT, DEATH_SLOT = 1, 2, 3, 8

SANDSTORM = 'rmap_sandstorm'
SANDSTORM_DEVIL = 'rmap_sandstorm_devil'
RUSH = 'SerpentCharge'

# Tier: (Rush in the kit, aip7 Rush chance). Sandstorm fans three devils from
# tier 5 (calc1, level = tier).
TIERS = {
    1: (False, 0), 2: (False, 0),
    3: (True, 35), 4: (True, 35),
    5: (True, 45), 6: (True, 45),
}
DEVILS = '(lvl < 5) ? 2 : 3'
DEVIL_SPEED = 6        # stock 10: slow enough to walk between
DEVIL_FRAMES = 80      # stock 50
APPROACH = 80          # aip1
USE_SKILL = 20         # aip2
AI_DELAY = 10          # aip3 (stock Dark Lancer 6)
RUN = 60               # aip4
RUN_RANGE = 10         # aip5
SANDSTORM_CHANCE = 35  # aip6

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
        rush, rush_chance = TIERS[tier]
        sandstorm = (SANDSTORM, CAST, tier)
        slots = {SANDSTORM_SLOT: sandstorm, SPARE_SLOT: sandstorm,
                 RUSH_SLOT: (RUSH, RUSH_MODE, tier) if rush else sandstorm,
                 DEATH_SLOT: (warden_kits.death_skill(monsters, boss), 'DT', 1)}
        warden_kits.layout(api, monsters, boss, AI, slots, (
            APPROACH, USE_SKILL, AI_DELAY, RUN, RUN_RANGE, SANDSTORM_CHANCE, rush_chance, 0))
