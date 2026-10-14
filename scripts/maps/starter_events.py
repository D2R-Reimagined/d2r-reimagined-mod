"""Map-owned starter encounter monsters, objects, names and native rewards."""
import maps_config as cfg

NAMES = {'RMapEventRaider': 'Treasure Raider', 'RMapEventGuard': 'Raider Guard',
         'RMapEventWave': 'Reliquary Guardian', 'RMapEventKeeper': 'Reliquary Keeper',
         'RMapEventSigil': 'Dark Sigil', 'RMapEventCache': 'Sealed Reliquary',
         'RMapEventMerchant': 'Varic the Wandering Gambler'}

# The Wandering Gambler's own HD unit, built by d2rr-models
# (npcs/wandering_merchant). Until it is installed he wears Gheed's.
MERCHANT_UNIT = 'rmap_merchant'
MERCHANT_UNIT_JSON = 'data/hd/character/npc/rmap_merchant.json'
# Bases the Gambler may offer: armor and weapons in three grades, plus rings
# and amulets. Grade 3 is jewelry, offered at every tier.
MERCHANT_JEWELRY = ('rin', 'amu')


def native_rows(table):
    # Expansion separators occupy a TXT line but never a compiled record.
    return [r for r in table.rows if not any(c.strip() == 'Expansion' for c in r)]

def generate(api, plans, monsters, props, stats2, uniques, runtime):
    objects = api.Table(api.EXCEL / 'objects.txt')
    objects.drop_tagged(objects.col('Name'), 'RMapEvent')
    object_ids = []
    for key, source in [('RMapEventSigil', 17), ('RMapEventCache', 5)]:
        row = list(objects.rows[source])
        # Overlay=1 is the golden glow vanilla puts on quest chests (Horadric
        # Cube, Khalim, Staff of Kings). It makes the event object stand out so
        # it cannot be walked past. Draw stays 1 so the base sprite still shows.
        api.set_cells(row, objects, {'Name': key, 'InitFn': '0', 'OperateFn': '6',
            'Lockable': '0', 'Restore': '0', 'RestoreVirgins': '0', 'Overlay': '1',
            'SizeX': '1', 'SizeY': '1', 'ClientFn': '0', 'SubClass': '0', 'Selectable2': '1'})
        object_ids.append(len(native_rows(objects))); objects.append(row)
    models = runtime['expansion_models']
    records = []
    def monster(name, source_name, tier, label, reward='', health=1):
        source = monsters.find(monsters.col('Id'), source_name)
        row = list(source)
        prop = props.blank_row(); api.set_cells(prop, props, {'Id': name, '*eol': '0'})
        prop_id = len(props.rows); props.append(prop)
        marker = list(stats2.find(stats2.col('Id'), source[monsters.col('MonStatsEx')]))
        api.set_cells(marker, stats2, {'Id': name, 'revive': '0', 'corpseSel': '0',
            'ResurrectMode': '', 'ResurrectSkill': '', 'SpawnUniqueMod': ''})
        stats2.append(marker)
        api.set_cells(row, monsters, {'Id': name, '*hcIdx': str(len(api.monster_indices(monsters))),
            'NextInClass': '', 'MonStatsEx': name, 'MonProp': name, 'NameStr': label,
            'minion1': '', 'minion2': '', 'MinGrp': '1', 'MaxGrp': '1', 'Rarity': '0',
            'PartyMin': '0', 'PartyMax': '0', 'spawn': '', 'placespawn': '0',
            'SetBoss': '0', 'BossXfer': '0', 'deathDmg': '0', 'DamageRegen': '0',
            'boss': '0', 'primeevil': '0', 'noRatio': '0',
            'CannotDesecrate': '1', 'CannotHerald': '1', 'TCQuestId': '', 'TCQuestCP': ''})
        for diff in ('', '(N)', '(H)'):
            row[monsters.col('Level'+diff)] = str(cfg.MAP_AREA_LEVEL+tier-1)
            for col in ('MinHP', 'MaxHP'):
                dest=col+diff
                if dest not in monsters.header: dest=dest[0].lower()+dest[1:]
                row[monsters.col(dest)] = str(round(int(source[monsters.col(col+'(H)')] or 0)*health))
            # These are independent events, not additional copies of the map's Warden kit.
            for col in monsters.header:
                if col.startswith('TreasureClass'): row[monsters.col(col)] = reward
        models[name] = models.get(source_name, source_name)
        index=len(api.monster_indices(monsters)); monsters.append(row)
        records.append((index, prop_id)); return index
    raiders=[]; guards=[]; waves=[]; keepers=[]; challengers=[]; super_ids=[]
    for tier in range(1,7):
        raiders.append(monster(f'rmap_event_raider_{tier}', 'fallen5',tier,'RMapEventRaider',f'RMap Event Raiders {tier}',4))
        guards.append(monster(f'rmap_event_guard_{tier}', 'fallen5',tier,'RMapEventGuard','',1.5))
    # The Wandering Gambler stands still among the map's monsters like Izual's
    # ghost (NpcStationary, ally, not killable). interact is off: the native
    # talk menu has nothing to show; the plugin opens his window by proximity.
    merchant=monster('rmap_event_merchant','gheed',1,'RMapEventMerchant')
    api.set_cells(monsters.rows[-1],monsters,{'AI':'NpcStationary','Velocity':'0','Run':'0','npc':'1',
        'interact':'','inventory':'','inTown':'','isSpawn':'','killable':'','Align':'1'})
    # Town NPCs leave hit points blank; a unit with none is not a valid monster.
    for col in ('minHP','maxHP','MinHP(N)','MaxHP(N)','MinHP(H)','MaxHP(H)'):
        monsters.rows[-1][monsters.col(col)]='5000'
    if (api.REPO / MERCHANT_UNIT_JSON).exists():
        runtime.setdefault('hd_units',{})['rmap_event_merchant']=MERCHANT_UNIT
    next_hc = 1 + max(int(r[uniques.col('hcIdx')] or 0) for r in uniques.rows)
    for p in plans:
        tier=p['tier']; source=f"rmap_{p['item_code']}_0"
        waves.append(monster(f"rmap_event_wave_{p['item_code']}",source,tier,'RMapEventWave','',0.7))
        group=[]
        for reward in ('Crafting','Equipment','Maps'):
            group.append(monster(f"rmap_event_keeper_{p['item_code']}_{reward.lower()}",source,tier,'RMapEventKeeper',f'RMap Event {reward} {tier}',4))
        keepers.append(group)
        label=f"RMapEventChallenger{p['item_code']}";NAMES[label]=p['theme']['name']+' Challenger'
        name=f"rmap_event_challenger_{p['item_code']}"
        challengers.append(monster(name,source,tier,label,f'RMap Event Challenger {tier}',5))
        row=uniques.blank_row();super_ids.append(len(native_rows(uniques)))
        api.set_cells(row,uniques,{'Superunique':name,'Name':label,'Class':name,'hcIdx':str(next_hc),
            'Mod1':'0','Mod2':'0','Mod3':'0','MinGrp':'0','MaxGrp':'0','AutoPos':'0','Stacks':'0','*eol':'0'})
        for col in uniques.header:
            if col.startswith('TC'):row[uniques.col(col)]=f'RMap Event Challenger {tier}'
        uniques.append(row)
        next_hc += 1
    runtime['events'] = dict(object_count=len(native_rows(objects)), objects=object_ids, records=records, raiders=raiders,guards=guards,
        waves=waves,keepers=keepers,challengers=challengers,super_ids=super_ids,merchant=merchant,
        gamble_vendor=api.monster_indices(monsters)['gheed'],merchant_bases=merchant_bases(api),
        gamble_chances=gamble_chances(api))
    runtime['monster_count']=len(api.monster_indices(monsters));runtime['prop_count']=len(props.rows)
    return objects

def gamble_chances(api):
    """The vendor gamble quality chances the Gambler uses, per difficulty."""
    t=api.Table(api.EXCEL/'difficultylevels.txt')
    return [tuple(int(r[t.col(c)] or 0) for c in ('GambleUnique','GambleSet','GambleRare')) for r in t.rows[:3]]

def merchant_bases(api):
    """(code, grade) for every spawnable armor/weapon base, and ring/amulet,
    that an enabled unique or set item uses. Grade 0/1/2 is normal/exceptional/
    elite by the row's own normcode/ubercode/ultracode; 3 is jewelry. The plugin
    reads the live unique and set rows for the odds; this only says which bases
    are worth offering."""
    used=set()
    for name,code_col in (('uniqueitems.txt','code'),('setitems.txt','item')):
        t=api.Table(api.EXCEL/name)
        for r in t.rows:
            if (r[t.col('disabled')] or '0')!='1' and (r[t.col('spawnable')] or '0')=='1':
                used.add(r[t.col(code_col)].strip())
    bases=[]
    for name in ('armor.txt','weapons.txt'):
        t=api.Table(api.EXCEL/name)
        for r in t.rows:
            code=r[t.col('code')].strip()
            if not code or code not in used or r[t.col('spawnable')]!='1' or r[t.col('quest')] not in ('','0'):continue
            grade=[r[t.col(c)].strip() for c in ('normcode','ubercode','ultracode')]
            if code in grade:bases.append((code,grade.index(code)))
    bases+=[(code,3) for code in MERCHANT_JEWELRY if code in used]
    return bases

def classes(api,t):
    def add(name,picks,items):
        row=t.blank_row();api.set_cells(row,t,{'Treasure Class':name,'Picks':str(picks),'NoDrop':'0','*eol':'0'})
        for i,(item,weight) in enumerate(items,1):api.set_cells(row,t,{f'Item{i}':item,f'Prob{i}':str(weight)})
        t.append(row)
    # Every nested row here is generated by endgame.treasure_classes before
    # this call; D2 resolves a treasure-class item only if that row was parsed
    # earlier in the file.
    for tier in range(1,7):
        # Bearer: four tier-loot attempts, one map/currency sustain roll, one
        # guaranteed currency and one guaranteed jewel.
        add(f'RMap Event Raiders {tier}',-7,[(f'RMap T{tier} Loot',4),(f'RMap T{tier} Sustain',1),('RMap Currency',1),('jew',1)])
        add(f'RMap Event Challenger {tier}',-6,[(f'RMap T{tier} Loot',4),(f'RMap T{tier} Sustain',1),('RMap Currency',1)])
        add(f'RMap Event Crafting {tier}',-6,[('Gem',4),('jew',1),('mor',1)])
        add(f'RMap Event Equipment {tier}',-6,[(f'RMap T{tier} Loot',6)])
        add(f'RMap Event Maps {tier}',-3,[(f'RMap Tier {min(tier,5)}',1),('RMap Currency',2)])

def header(out,runtime):
    e=runtime['events']
    for key,name in [('objects','EventObjectIds'),('raiders','EventRaiderIds'),('guards','EventGuardIds'),
                     ('waves','EventWaveIds'),('challengers','EventChallengerIds'),('super_ids','EventSuperUniqueIds')]:
        out.append('inline constexpr uint16_t '+name+'[] = { '+', '.join(map(str,e[key]))+' };')
    for name,values in [('EventMonsterIds',[x[0] for x in e['records']]),('EventMonProps',[x[1] for x in e['records']])]:
        out.append('inline constexpr uint16_t '+name+'[] = { '+', '.join(map(str,values))+' };')
    out.append('inline constexpr uint16_t EventKeeperIds[][3] = { '+', '.join('{'+','.join(map(str,x))+'}' for x in e['keepers'])+' };')
    out.append('inline constexpr uint16_t EventObjectCount = '+str(e['object_count'])+';')
    out.append('inline constexpr uint16_t EventMerchantId = '+str(e['merchant'])+';')
    out.append('// Gheed: the vendor whose gamble prices the Wandering Gambler charges.')
    out.append('inline constexpr uint16_t EventGambleVendorId = '+str(e['gamble_vendor'])+';')
    out.append('// Gamble bases: four-character code (little-endian, space padded) and grade')
    out.append('// (0 normal, 1 exceptional, 2 elite, 3 ring/amulet).')
    out.append('struct MerchantBase { uint32_t code; uint8_t grade; };')
    out.append('// difficultylevels.txt GambleUnique, GambleSet, GambleRare per difficulty (of 100000).')
    out.append('struct MerchantChance { uint32_t unique, set, rare; };')
    out.append('inline constexpr MerchantChance MerchantGambleChances[] = { '+', '.join(
        '{%d,%d,%d}'%c for c in e['gamble_chances'])+' };')
    def fourcc(code): return int.from_bytes(code.ljust(4).encode('ascii'),'little')
    out.append('inline constexpr MerchantBase MerchantBases[] = { '+', '.join(
        '{0x%08X,%d}'%(fourcc(code),grade) for code,grade in e['merchant_bases'])+' };')
