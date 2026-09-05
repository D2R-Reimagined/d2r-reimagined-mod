"""Map-only monsters, combat auras, and bank-specific loot progression.

Uses the same table helpers as the layout generator. No Labyrinth row is edited.
"""
from __future__ import annotations

import maps_config as cfg


def generate(api, plans, levels):
    Table, set_cells, EXCEL = api.Table, api.set_cells, api.EXCEL
    skills = Table(EXCEL / "skills.txt")
    states = Table(EXCEL / "states.txt")
    props = Table(EXCEL / "monprop.txt")
    monsters = Table(EXCEL / "monstats.txt")
    for table, key in ((skills, "skill"), (states, "state"),
                       (props, "Id"), (monsters, "Id")):
        table.drop_tagged(table.col(key), "rmap_")

    # Separate states avoid overwriting player equipment auras, curses, and
    # each other. Nearby monsters refresh one state rather than stacking it.
    effects = {
        "sapping": [("damagepercent", "-15")],
        "withering": [("damagepercent", "-30")],
        "unhallowed": [("item_allskills", "-2")],
        "frailty": [(x, "-30") for x in
                    ("fireresist", "coldresist", "lightresist", "poisonresist")],
        "ruin": [(x, "-60") for x in
                 ("fireresist", "coldresist", "lightresist", "poisonresist")],
        "agony": [("damageresist", "-25")],
        "fortune": [("item_magicbonus", "lvl")],
    }
    skill_ids = {}
    for name, stats in effects.items():
        key = "rmap_" + name
        state = states.blank_row()
        set_cells(state, states, {"state": key, "*ID": str(len(states.rows)),
                                 "aura": "1", "*eol": "0"})
        states.append(state)
        # Generic periodic stat aura. Conviction's enemy filter targets the
        # players fighting the carrier; no inventory item or saved stat exists.
        row = skills.blank_row()
        sid = len(skills.rows)
        set_cells(row, skills, {
            "skill": key, "*Id": str(sid), "srvdofunc": "65",
            "aurafilter": "42371", "aurastate": key,
            "auratargetstate": key, "aurarangecalc": "40",
            "auralencalc": "50", "immediate": "1", "range": "none",
            "monanim": "xx", "aura": "1", "perdelay": "25",
            "InGame": "1", "HitShift": "8", "*eol": "0",
        })
        for i, (stat, calc) in enumerate(stats, 1):
            set_cells(row, skills, {f"aurastat{i}": stat, f"aurastatcalc{i}": calc})
        skills.append(row)
        skill_ids[name] = sid

    all_affixes = cfg.AFFIX_PREFIXES + cfg.AFFIX_SUFFIXES
    for affix in all_affixes:
        if affix["kind"] == "aura":
            skill_ids[affix["key"]] = int(skills.find(
                skills.col("skill"), affix["aura_skill"])[skills.col("*Id")])

    def property_row(name, entries):
        row = props.blank_row()
        set_cells(row, props, {"Id": name, "*eol": "0"})
        for diff in ("", " (N)", " (H)"):
            for slot, (skill, level) in enumerate(entries, 1):
                set_cells(row, props, {
                    f"prop{slot}{diff}": "aura", f"chance{slot}{diff}": "100",
                    f"par{slot}{diff}": str(skill), f"min{slot}{diff}": str(level),
                    f"max{slot}{diff}": str(level),
                })
        return row

    # Probe has distinct values in every slot and difficulty. The plugin must
    # verify the complete supported compiled layout before it writes a byte.
    probe_index = len(props.rows)
    probe = property_row("rmap_probe", [(skill_ids["fortune"], i) for i in range(1, 7)])
    for d, diff in enumerate(("", " (N)", " (H)")):
        for i in range(1, 7):
            for field in ("min", "max"):
                probe[props.col(f"{field}{i}{diff}")] = str(11 + d * 6 + i)
    props.append(probe)

    prop_indices = []
    for p in plans:
        idx = len(props.rows)
        prop_indices.append(idx)
        props.append(property_row(f"rmap_{p['item_code']}",
                                  [(skill_ids["fortune"], p["tier"] * cfg.MAP_MF_PER_TIER)]))
        codes = cfg.MAP_MONSTERS[p["theme"]["key"]]
        for i, code in enumerate(codes):
            source = monsters.find(monsters.col("Id"), code)
            row = list(source)
            name = f"rmap_{p['item_code']}_{i}"
            set_cells(row, monsters, {
                "Id": name, "*hcIdx": str(len(monsters.rows)), "NextInClass": "",
                "MonProp": f"rmap_{p['item_code']}", "noAura": "0",
                "noRatio": "0", "boss": "0", "primeevil": "0",
                "MinGrp": "3", "MaxGrp": "5", "enabled": "1",
                "spawn": "", "minion1": "", "minion2": "",
                "TCQuestId": "", "TCQuestCP": "",
            })
            # Native Hell ratios retain the archetype; tiers raise both physical
            # and elemental attacks. Normal/Nightmare copies are defensive only:
            # activation is Hell-only. Use supported area levels 86-91.
            for diff in ("", "(N)", "(H)"):
                row[monsters.col("Level" + diff)] = str(cfg.MAP_AREA_LEVEL + p["tier"] - 1)
                for stem in ("MinHP", "MaxHP", "AC", "Exp", "A1MinD", "A1MaxD",
                             "A1TH", "A2MinD", "A2MaxD", "A2TH", "S1MinD", "S1MaxD",
                             "S1TH", "El1MinD", "El1MaxD", "El2MinD", "El2MaxD",
                             "El3MinD", "El3MaxD"):
                    target = stem + diff
                    if target not in monsters.header:
                        target = target[0].lower() + target[1:]
                    value = int(source[monsters.col(stem + "(H)")] or 0)
                    factor = 1.0 if stem in ("Exp", "AC", "A1TH", "A2TH", "S1TH") else p["spec"]["scale"]
                    if stem in ("MinHP", "MaxHP"):
                        factor *= 1.5
                    row[monsters.col(target)] = str(round(value * factor))
                # Mapping does not require Labyrinth's immunity puzzle. Native
                # single immunities remain, but no blanket six-way immunity.
                for resistance in ("ResDm", "ResMa", "ResFi", "ResLi", "ResCo", "ResPo"):
                    row[monsters.col(resistance + diff)] = source[monsters.col(resistance + "(H)")]
                for kind in ("", "Champ", "Unique", "Quest", "Desecrated",
                             "DesecratedChamp", "DesecratedUnique", "Herald"):
                    reward = "Elite" if kind else "Normal"
                    row[monsters.col("TreasureClass" + kind + diff)] = f"RMap T{p['tier']} {reward}"
            monsters.append(row)
        body = levels.find(levels.col("Id"), str(p["body_id"]))
        for group in ("mon", "nmon", "umon"):
            for i in range(1, 26):
                body[levels.col(f"{group}{i}")] = f"rmap_{p['item_code']}_{i-1}" if i <= len(codes) else ""
        body[levels.col("NumMon")] = str(len(codes))
        for lid in (p["body_id"], p["boss_id"]):
            level = levels.find(levels.col("Id"), str(lid))
            for col in ("MonLvl", "MonLvl(N)", "MonLvl(H)", "MonLvlEx", "MonLvlEx(N)", "MonLvlEx(H)"):
                level[levels.col(col)] = str(cfg.MAP_AREA_LEVEL + p["tier"] - 1)

    metadata = {"prop_indices": prop_indices, "probe_index": probe_index,
                "fortune_skill": skill_ids["fortune"], "skills": skill_ids,
                "prop_count": len(props.rows)}
    # Isolate entry drops by level population rather than shared TC groups:
    # level-85 monsters in earlier acts can upgrade into Act 5 TC groups too.
    entries = {}
    for level in levels.rows:
        if level[levels.col("Id")] not in ("118", "119", "128", "129", "130", "131"):
            continue
        for group in ("nmon", "umon"):
            for i in range(1, 26):
                col = levels.col(f"{group}{i}")
                code = level[col].removeprefix("rmap_e_")
                if not code:
                    continue
                if code not in entries:
                    source = monsters.find(monsters.col("Id"), code)
                    row = list(source)
                    api.set_cells(row, monsters, {"Id": f"rmap_e_{code}",
                        "*hcIdx": str(len(monsters.rows)), "NextInClass": ""})
                    for c, heading in enumerate(monsters.header):
                        if heading.startswith("TreasureClass") and heading.endswith("(H)") and row[c]:
                            name = f"RMap Entry {source[monsters.col('*hcIdx')]} {c}"
                            entries.setdefault(code, []).append((name, row[c]))
                            row[c] = name
                    entries.setdefault(code, [])
                    monsters.append(row)
                level[col] = f"rmap_e_{code}"
    metadata["entry_classes"] = [entry for values in entries.values() for entry in values]
    return [skills, states, props, monsters], metadata


def treasure_classes(api, plans, path, runtime):
    t = api.Table(path)
    key = t.col("Treasure Class")
    t.drop_tagged(key, "RMap ")

    def tc(name, picks, drops, nodrop=0):
        row = t.blank_row()
        api.set_cells(row, t, {"Treasure Class": name, "Picks": str(picks),
                              "NoDrop": str(nodrop), "*eol": "0"})
        for i, (item, weight) in enumerate(drops, 1):
            api.set_cells(row, t, {f"Item{i}": item, f"Prob{i}": str(weight)})
        t.append(row)

    for tier in range(1, 6):
        tc(f"RMap Tier {tier}", 1, [(p["item_code"], 1) for p in plans if p["tier"] == tier])
    tc("RMap Currency", 1, [("mor", 5), ("mrl", 4), ("mws", 1)])
    tc("RMap Entry", 1, [("RMap Tier 1", 1)], 249)
    # Remove only the previous generated entry slot, if this is an upgrade
    # from the early shared-TC implementation.
    for row in t.rows:
        name = row[key]
        if not (name.startswith("Act 5 (H) ") and name.endswith((" B", " C"))
                and any(x in name for x in ("H2H", "Cast", "Miss"))):
            continue
        for i in range(1, 11):
            if row[t.col(f"Item{i}")] in ("RMap Entry", "RMap Tier 1"):
                api.set_cells(row, t, {f"Item{i}": "", f"Prob{i}": ""})
    for name, original in runtime["entry_classes"]:
        t.find(key, original)  # bank-specific reference must exist
        tc(name, -2, [(original, 1), ("RMap Entry", 1)])
    for tier in range(1, 7):
        # No group: these rows must never auto-upgrade into another tier's TC.
        tc(f"RMap T{tier} Sustain", 1,
           [(f"RMap Tier {min(tier, 5)}", 8), ("RMap Currency", 5)]
           + ([(f"RMap Tier {tier+1}", 2)] if tier < 5 else []), 985)
        tc(f"RMap T{tier} Loot", 1,
           [("Act 5 (H) Equip C", 25), ("Act 5 (H) Good", 5),
            ("Gold 1x", 8), ("Super Potion", 4)], max(0, 42 - tier * 6))
        # Independent sustain attempt plus tier-scaled loot. Negative picks
        # ensure a map/currency roll cannot consume the equipment reward.
        tc(f"RMap T{tier} Normal", -2,
           [(f"RMap T{tier} Loot", 1), (f"RMap T{tier} Sustain", 1)])
        tc(f"RMap T{tier} Elite", -4,
           [(f"RMap T{tier} Loot", 3), (f"RMap T{tier} Sustain", 1)])
        tc(f"RMap T{tier} Boss", -6,
           [(f"RMap T{tier} Loot", 4), (f"RMap Tier {min(tier, 5)}", 1),
            ("RMap Currency", 1)])
    return t
