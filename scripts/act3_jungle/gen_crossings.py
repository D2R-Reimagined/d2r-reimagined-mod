"""Add log crossings to Act 3 jungle river blocks whose land is split by the river.

DS1: stamp the vanilla crossing tiles (rivbank.dt1 main 14) over a canonical
river stamp pair, clearing wall-layer overlap in the footprint.
HD:  copy the vanilla crossing's bridge/log entities (same offset from the
footprint) and drop foliage that sits on the new walkway.
"""
import json, os, sys, zlib
from planner import Ds1, J, BASE, fl, apply, big_comps, tileset, candidates, TPL
from phys import heightgrid
from hdjson import dump

HD_BASE = "C:/dev/d2r/base-files/data/data/hd/env/preset/act3/jungle/"
MOD = "C:/dev/d2r/d2r-reimagined-mod/data/"
SRC = {"H": ("rivns", 18, 17, 4, 2), "V": ("rive2", 9, 14, 2, 4)}
COPY_PREFIX = ("bridge_", "trampled_mud", "grunge_mud_trampled")
DEP_KEYS = ("bridge", "debris", "trampled")
POCKETS = ("rivnw rivnw2 rivnew rivnew2 rivns rivns2 rivns4 rivns5 rivnsw rivnsw2 rivnsew "
           "rivnsew2 rivnsew3 rivewos rivewon rivswoe rivswon rivnwoe rivnwos rivneow rivnewos "
           "rivnsow rivnsoe rivnswoe rivnseow").split()

_hg = {}
def hg(n):
    if n not in _hg: _hg[n] = heightgrid(n)
    return _hg[n]

def hd_diff(kind, name, cx, cy):
    s, sx, sy, w, h = SRC[kind]; a = hg(s); b = hg(name); tot = cnt = 0
    for j in range(-5, (h + 1) * 5):
        for i in range(-5, (w + 1) * 5):
            A = (sy * 5 + j, sx * 5 + i); B = (cy * 5 + j, cx * 5 + i)
            if not all(0 <= v < 165 for v in A + B): continue
            ya, yb = a[A[0]][A[1]], b[B[0]][B[1]]
            if ya is None or yb is None: continue
            tot += abs(ya - yb); cnt += 1
    return tot / max(cnt, 1)

def pockets_of(d):
    g, comp, sizes = big_comps(d, tileset())
    order = sorted(range(len(sizes)), key=lambda c: -sizes[c])
    return g, comp, sizes, order[0], [c for c in order[1:] if sizes[c] > 100]

def joined_area(d, kind, cx, cy):
    """Pocket area (subtiles) that ends up in the main component after the crossing."""
    g, comp, sizes, main, pk = pockets_of(d)
    dd = Ds1.__new__(Ds1); dd.__dict__ = dict(d.__dict__); dd.bytes = bytearray(d.bytes)
    apply(dd, kind, cx, cy)
    _, comp2, _ = big_comps(dd, tileset())
    def rep(c):
        for y, row in enumerate(comp):
            for x, v in enumerate(row):
                if v == c and comp2[y][x] >= 0: return comp2[y][x]
    m = rep(main)
    return sum(sizes[c] for c in pk if rep(c) == m), dd

def plan(name):
    d = Ds1(J + name + ".ds1"); chosen = []
    while True:
        _, _, sizes, main, pk = pockets_of(d)
        if not pk: break
        best = None
        for kind, cx, cy in candidates(d):
            if any(abs(cx - c[1]) < 4 and abs(cy - c[2]) < 4 for c in chosen): continue
            area, dd = joined_area(d, kind, cx, cy)
            if area <= 0: continue
            # rank: join the most area, then the closest HD terrain match
            score = (area, -hd_diff(kind, name, cx, cy))
            if best is None or score > best[0]: best = (score, kind, cx, cy, dd)
        if best is None:
            # no crossing touches main: join pockets to each other first (e.g. rivnswoe west alcove)
            for kind, cx, cy in candidates(d):
                if any(abs(cx - c[1]) < 4 and abs(cy - c[2]) < 4 for c in chosen): continue
                dd = Ds1.__new__(Ds1); dd.__dict__ = dict(d.__dict__); dd.bytes = bytearray(d.bytes)
                apply(dd, kind, cx, cy)
                if len(pockets_of(dd)[4]) < len(pk):
                    best = ((0, -hd_diff(kind, name, cx, cy)), kind, cx, cy, dd); break
        if best is None: break
        _, kind, cx, cy, dd = best
        chosen.append((kind, cx, cy, round(hd_diff(kind, name, cx, cy), 2)))
        d = dd
    left = [sizes for sizes in [pockets_of(d)[2]]][0]
    remaining = [left[c] for c in pockets_of(d)[4]]
    return d, chosen, remaining

def pos(e):
    for c in e["components"]:
        if c["type"] == "TransformDefinitionComponent": return c["position"]

TALL = ("tree", "bush", "sapling", "palm", "banyan", "cypress", "treewall", "canopy")

def has_visual(e):
    """Tall foliage that would stand on the new walkway. Riverbank prefabs carry the
    bank-lip geometry and stay, as they do under vanilla crossings."""
    for c in e["components"]:
        path = (c.get("filename") or c.get("prefab") or "").lower().split("/")[-1]
        if c["type"] in ("ModelDefinitionComponent", "PrefabPlacementDefinitionComponent") and \
                "riverbank" not in path and any(k in path for k in TALL):
            return True
    return False

def hd_edit(name, chosen, report):
    j = json.load(open(HD_BASE + name + ".json"))
    ids = {e["id"] for e in j["entities"]} | {j["terrain"]["id"]}
    names = {e["name"] for e in j["entities"]}
    removed, added = [], []
    for kind, cx, cy, _ in chosen:
        s, sx, sy, w, h = SRC[kind]
        src = json.load(open(HD_BASE + s + ".json"))
        # walkway footprint in HD units
        X0, Z0, X1, Z1 = cx * 10, cy * 10, (cx + w) * 10, (cy + h) * 10
        keep = []
        for e in j["entities"]:
            p = pos(e)
            if p and has_visual(e) and not e["name"].startswith("bridge_") and X0 <= p["x"] <= X1 and Z0 <= p["z"] <= Z1:
                removed.append(e["name"]); continue
            keep.append(e)
        j["entities"] = keep
        M = 1.5
        for e in src["entities"]:
            p = pos(e)
            if not p or not e["name"].startswith(COPY_PREFIX): continue
            if not ((sx - M) * 10 <= p["x"] <= (sx + w + M) * 10 and (sy - M) * 10 <= p["z"] <= (sy + h + M) * 10): continue
            ne = json.loads(json.dumps(e))
            base = "rx_" + e["name"]; nm = base; k = 1
            while nm in names: k += 1; nm = "%s_%d" % (base, k)
            names.add(nm); ne["name"] = nm
            nid = zlib.crc32(("%s:%s:%d:%d:%s" % (name, kind, cx, cy, e["name"])).encode())
            while nid in ids or nid == 0: nid = (nid * 1103515245 + 12345) & 0xFFFFFFFF
            ids.add(nid); ne["id"] = nid
            for c in ne["components"]:
                if c["type"] == "TransformDefinitionComponent":
                    c["position"]["x"] = round(p["x"] - sx * 10 + cx * 10, 4)
                    c["position"]["z"] = round(p["z"] - sy * 10 + cy * 10, 4)
            j["entities"].append(ne); added.append(nm)
        # dependencies
        for key, lst in src["dependencies"].items():
            have = {x["path"] for x in j["dependencies"].setdefault(key, [])}
            for x in lst:
                if any(k in x["path"].lower() for k in DEP_KEYS) and x["path"] not in have:
                    j["dependencies"][key].append({"path": x["path"]}); have.add(x["path"])
    report.append("    HD: +%d entities, -%d (%s)" % (len(added), len(removed), ", ".join(removed)))
    return j

def main(write):
    report = []
    for name in POCKETS:
        d, chosen, remaining = plan(name)
        report.append("%-9s crossings %s remaining %s" % (name, chosen, remaining or "none"))
        j = hd_edit(name, chosen, report)
        if write and chosen:
            os.makedirs(MOD + "global/tiles/act3/jungle", exist_ok=True)
            os.makedirs(MOD + "hd/env/preset/act3/jungle", exist_ok=True)
            open(MOD + "global/tiles/act3/jungle/" + name + ".ds1", "wb").write(bytes(d.bytes))
            open(MOD + "hd/env/preset/act3/jungle/" + name + ".json", "w", newline="").write(dump(j))
    print("\n".join(report))

if __name__ == "__main__":
    main("--write" in sys.argv)
