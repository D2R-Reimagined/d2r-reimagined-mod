"""Travincal Warden stopgap until it gets its own kit: no self-heal.

The Warden is a Council Member on the HighPriest AI and inherited the stock
ZakarumHeal (level 4, ~35% life a cast) in Skill2. Skill2 now holds
ZakarumLightning, the skill D2R's monai.txt names for that AI's Skill2, so
the slot never sits empty; the stock Hydra in Skill1 is unchanged. The
DT-mode death portal moves to Skill8, away from the slots the AI reads.
"""
import warden_kits

AI = 'HighPriest'
BODY_CODE = 'HP'
BOLT = 'ZakarumLightning'
BOLT_SLOT, DEATH_SLOT = 2, 8
BOLT_LEVEL = 4          # the level the stock heal had


def generate(api, plans, kit, monsters):
    for plan in plans:
        if plan['theme']['key'] != 'travincal':
            continue
        boss = monsters.find(monsters.col('Id'), f"rmap_{plan['item_code']}_boss")
        assert boss[monsters.col('Code')] == BODY_CODE, boss[monsters.col('Code')]
        slots = {i: (boss[monsters.col(f'Skill{i}')], boss[monsters.col(f'Sk{i}mode')], boss[monsters.col(f'Sk{i}lvl')])
                 for i in range(1, 9) if boss[monsters.col(f'Skill{i}')] and boss[monsters.col(f'Sk{i}mode')] != 'DT'}
        assert slots[BOLT_SLOT][0] == 'ZakarumHeal', slots
        slots[BOLT_SLOT] = (BOLT, slots[BOLT_SLOT][1], BOLT_LEVEL)
        slots[DEATH_SLOT] = (warden_kits.death_skill(monsters, boss), 'DT', 1)
        warden_kits.layout(api, monsters, boss, AI, slots, None)
