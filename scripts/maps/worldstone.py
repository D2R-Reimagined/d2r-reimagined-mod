"""Worldstone Keep Warden, the Worldbreaker: a Hell Bovine on the PinHead AI.

The Warden keeps the Hell Bovine body. Its Skeleton AI reads no skill slots,
so it runs the Mauler's PinHead AI, which D2R's monai.txt documents as melee
plus Skill1 and Skill2, each with its own chance (aip5, aip6) behind one
act roll (aip1), with an attack delay (aip2) and an AI delay (aip4):

    Skill1  aip5 %   Seismic Slam, a Siege Beast Stomp around the Warden;
                     the signature
    Skill2  aip6 %   Rift Wave, a slow fan of shockwaves toward the target
                     with open sectors beside and between them

Seismic Slam was the Warden's att-skill proc, so the stomp is known to work
from this body; it keeps the stock A2 cast (action frame 8). Rift Wave is a
clone of Dsum_Shockwave, a monster skill on the shoot-missile function
(srvdofunc 8, the one Blight Bolt uses) that fans calc1 shockwave missiles;
it casts in A1 (action frame 9). The druid's own Shock Wave was passed over:
its start function (srvstfunc 39) is the one Berserk and Stun share.

Fanaticism, the random stomp proc and the stun melee are gone. The DT-mode
death portal sits in Skill8.
"""
import warden_kits

AI = 'PinHead'
BODY_CODE = 'EC'
SLAM_MODE = 'A2'
WAVE_MODE = 'A1'
SLAM_SLOT, WAVE_SLOT, DEATH_SLOT = 1, 2, 8

SLAM = 'rmap_seismic_slam'
WAVE = 'rmap_rift_wave'
WAVE_MISSILE = 'rmap_rift_wave_m'

# Tier: (Rift Wave in the kit, aip5 slam chance, aip6 wave chance). Raised to
# 45-50/35-45 on 2026-10-14: at 20-30 the Hell Bovine mostly tried to swing
# and stood behind its own escort. Rift
# Wave from tier 1: a one-spell Warden reads as "normal attacks" in game.
TIERS = {
    1: (True, 45, 35), 2: (True, 45, 35),
    3: (True, 45, 40), 4: (True, 45, 40),
    5: (True, 50, 45), 6: (True, 50, 45),
}
WAVES = '(lvl < 5) ? 5 : 7'   # calc1, level = tier: five waves, seven from tier 5
WAVE_SPEED = 12               # stock 20: slow enough to step between
WAVE_FRAMES = 30              # stock 8: rolls out across the arena
ACT = 90                      # aip1
ATTACK_DELAY = 7              # aip2, stock Blunderbore (was 10)
APPROACH = 100                # aip3
AI_DELAY = 5                  # aip4, stock Blunderbore (was 8)
# Speed comes from the population row (AI_PROFILES Skeleton, labcow's 12).

# Physical damage (whole), level = tier.
SLAM_DAMAGE = dict(min=400, max=600, per_level=(60, 90))
WAVE_DAMAGE = dict(min=250, max=350, per_level=(40, 60))


def _physical(spec):
    lo, hi = spec['per_level']
    return {'MinDam': str(spec['min']), 'MaxDam': str(spec['max']),
            **{f'MinLevDam{i}': str(lo) for i in range(1, 6)},
            **{f'MaxLevDam{i}': str(hi) for i in range(1, 6)}}


def generate(api, plans, kit, monsters):
    kit.skill('Siege Beast Stomp', SLAM, {'monanim': SLAM_MODE, **_physical(SLAM_DAMAGE)})
    kit.skill('Dsum_Shockwave', WAVE, {
        'monanim': WAVE_MODE, 'srvmissilea': WAVE_MISSILE, 'srvmissileb': WAVE_MISSILE,
        # The client must draw the slowed clone, not the stock wave (speed 20,
        # 8 frames) that would run ahead of the damage.
        'cltmissilea': WAVE_MISSILE, 'cltmissileb': WAVE_MISSILE,
        'calc1': WAVES, **_physical(WAVE_DAMAGE)})
    kit.missile('dsum_shockwave_m', WAVE_MISSILE, {
        'Skill': WAVE, 'Vel': str(WAVE_SPEED), 'MaxVel': str(WAVE_SPEED), 'Range': str(WAVE_FRAMES)})

    for plan in plans:
        if plan['theme']['key'] != 'worldstone':
            continue
        tier = plan['tier']
        boss = monsters.find(monsters.col('Id'), f"rmap_{plan['item_code']}_boss")
        assert boss[monsters.col('Code')] == BODY_CODE, boss[monsters.col('Code')]
        wave, slam_chance, wave_chance = TIERS[tier]
        slam = (SLAM, SLAM_MODE, tier)
        slots = {SLAM_SLOT: slam, WAVE_SLOT: (WAVE, WAVE_MODE, tier) if wave else slam,
                 DEATH_SLOT: (warden_kits.death_skill(monsters, boss), 'DT', 1)}
        warden_kits.layout(api, monsters, boss, AI, slots, (
            ACT, ATTACK_DELAY, APPROACH, AI_DELAY, slam_chance, wave_chance, '', ''))
