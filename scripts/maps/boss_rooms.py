"""Clone shipped DS1 rooms and replace their monster population with a map boss.

Only the object block changes; tiles, warps and trailing substitution/NPC
records remain byte-for-byte intact. Source Labyrinth files are never written.
"""
import struct


def objects(data):
    version, width, height, act, sub, files = struct.unpack_from("<6I", data)
    if version != 18 or width > 512 or height > 512 or files > 100:
        raise ValueError("Only validated v18 DS1 rooms are supported")
    offset = 24
    for _ in range(files):
        offset = data.index(b"\0", offset) + 1
    walls, floors = struct.unpack_from("<2I", data, offset)
    if not 1 <= walls <= 4 or not 1 <= floors <= 2:
        raise ValueError("Invalid DS1 layer counts")
    offset += 8 + (width + 1) * (height + 1) * (2 * walls + floors + 1 + (sub in (1, 2))) * 4
    count = struct.unpack_from("<I", data, offset)[0]
    if count > 10000 or offset + 4 + count * 20 > len(data):
        raise ValueError("Invalid DS1 object block")
    rows = [struct.unpack_from("<5I", data, offset + 4 + i * 20) for i in range(count)]
    return offset, rows, width, height


def clone(data, preset):
    offset, rows, width, height = objects(data)
    points = [(r[2], r[3]) for r in rows if r[0] == 1]
    # Existing monster locations are known walkable positions. NihlS has no
    # monster records; its centre is the original Nihlathak platform.
    x, y = min(points, key=lambda p: (p[0] - width * 2.5)**2 + (p[1] - height * 2.5)**2) if points else (211, 211)
    if not (0 <= x <= width * 5 and 0 <= y <= height * 5):
        raise ValueError("Boss outside DS1")
    kept = [r for r in rows if r[0] != 1]
    kept.append((1, preset, x, y, 0))
    header = bytearray(data[:offset])
    struct.pack_into("<I", header, 12, 4)  # Act 5 MonPreset namespace
    block = struct.pack("<I", len(kept)) + b"".join(struct.pack("<5I", *r) for r in kept)
    return bytes(header) + block + data[offset + 4 + len(rows) * 20:]


def generate(api, plans, levels, presets, monsters):
    places = api.Table(api.EXCEL / "monpreset.txt")
    places.drop_tagged(places.col("Place"), "rmap_")
    next_slot = sum(r[places.col("Act")] == "5" for r in places.rows)
    assets = {}
    for p in plans:
        code = p["item_code"]
        boss = list(monsters.find(monsters.col("Id"), f"rmap_{code}_0"))
        api.set_cells(boss, monsters, {
            "Id": f"rmap_{code}_boss", "*hcIdx": str(len(monsters.rows)),
            "MinGrp": "1", "MaxGrp": "1", "boss": "1", "primeevil": "0",
            "NameStr": f"RMapBoss{code}",
        })
        for col in monsters.header:
            if col.lower().startswith(("minhp", "maxhp")):
                boss[monsters.col(col)] = str(int(boss[monsters.col(col)] or 0) * 12)
            if col.startswith("TreasureClass"):
                boss[monsters.col(col)] = f"RMap T{p['tier']} Boss"
        monsters.append(boss)
        row = places.blank_row()
        api.set_cells(row, places, {"Act": "5", "Place": f"rmap_{code}_boss", "* DS1 ID#": str(next_slot)})
        places.append(row)

        preset = presets.find(presets.col("LevelId"), str(p["boss_id"]))
        level = levels.find(levels.col("Id"), str(p["boss_id"]))
        # The stock ice pool DS1s are not shipped in this repo and have no
        # guaranteed boss. Use the shipped NihlS arena until ice arenas can be
        # authored, keeping the Frozen Depths body and its own monster roster.
        if p["theme"]["key"] == "frozen":
            template = levels.find(levels.col("Id"), "152")
            source_preset = presets.find(presets.col("LevelId"), "152")
            for col in ("Pal", "DrlgType", "LevelType", "SizeX", "SizeY", "SizeX(N)", "SizeY(N)", "SizeX(H)", "SizeY(H)"):
                level[levels.col(col)] = template[levels.col(col)]
            for i in range(8):
                level[levels.col(f"Vis{i}")] = str(p["body_id"]) if template[levels.col(f"Vis{i}")] == "151" else "0"
                level[levels.col(f"Warp{i}")] = template[levels.col(f"Warp{i}")] if template[levels.col(f"Vis{i}")] == "151" else "-1"
            for col in ("Outdoors", "Animate", "KillEdge", "FillBlanks", "SizeX", "SizeY", "Dt1Mask"):
                preset[presets.col(col)] = source_preset[presets.col(col)]
            source = "Labyrinth/NihlS.ds1"
        else:
            source = preset[presets.col("File1")]
        data = (api.REPO / "data/global/tiles" / source).read_bytes()
        target = f"Maps/{code}_boss.ds1"
        assets[api.REPO / "data/global/tiles" / target] = clone(data, next_slot)
        next_slot += 1
        api.set_cells(preset, presets, {"Populate": "0", "Files": "1", "File1": target,
                                       **{f"File{i}": "0" for i in range(2, 7)}})
        for group in ("mon", "nmon", "umon"):
            for i in range(1, 26):
                level[levels.col(f"{group}{i}")] = ""
        level[levels.col("NumMon")] = "0"
    if next_slot > 256:
        raise ValueError("Act 5 preset slots exceed 8-bit range")
    return places, assets
