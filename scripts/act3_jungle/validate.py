"""Independent check of the written mod files against vanilla."""
import glob, json, os
from ds1lib import Ds1, BASE, collision, components, tileset
from gen_markers import tiles_for

MOD = "C:/dev/d2r/d2r-reimagined-mod/data/"
J = BASE + "/act3/jungle/"
HD = "C:/dev/d2r/base-files/data/data/hd/env/preset/act3/jungle/"

def comps(d, t):
    g, _ = collision(d, t); _, s = components(g)
    return sorted([x for x in s if x > 100], reverse=True)

bad = 0
ds1s = sorted(glob.glob(MOD + "global/tiles/act3/jungle/*.ds1"))
for p in ds1s:
    n = os.path.basename(p)[:-4]
    a, b = Ds1(J + n + ".ds1"), Ds1(p)
    t = tiles_for(n) if n.startswith(("spid", "pyg")) else tileset()
    ca, cb = comps(a, t), comps(b, t)
    same_hdr = (a.version, a.w, a.h, a.act, a.tag, a.files, a.nwalls, a.nfloors) == \
               (b.version, b.w, b.h, b.act, b.tag, b.files, b.nwalls, b.nfloors)
    # tile layers: count changed cells; units: originals preserved in order
    changed = sum(1 for i in range(a.units_off) if a.bytes[i] != b.bytes[i]) // 1
    units_ok = b.units[:len(a.units)] == a.units
    tail_ok = bytes(a.bytes[a.after_units:]) == bytes(b.bytes[b.after_units:])
    ok = same_hdr and units_ok and tail_ok
    if n.startswith("riv"):
        ok &= len(cb) == 1 and len(b.units) == len(a.units)
    else:
        ok &= ca == [c for c in ca] and len(cb) == len(ca) and changed == 0
    bad += not ok
    print("%-9s %s comps %s -> %s  units %d -> %d  tile-bytes-changed %d" %
          (n, "OK " if ok else "BAD", ca, cb, len(a.units), len(b.units), changed))

for p in sorted(glob.glob(MOD + "hd/env/preset/act3/jungle/*.json")):
    n = os.path.basename(p)[:-5]
    a, b = json.load(open(HD + n + ".json")), json.load(open(p))
    ids = [e["id"] for e in b["entities"]] + [b["terrain"]["id"]]
    an = {e["name"] for e in a["entities"]}
    lost = an - {e["name"] for e in b["entities"]}
    deps = {x["path"] for v in b["dependencies"].values() for x in v}
    used = {c.get("filename") for e in b["entities"] for c in e["components"] if c.get("filename")}
    missing = {u for u in used if u not in deps and u.endswith(".model")}
    va = [e["id"] for e in a["entities"]] + [a["terrain"]["id"]]
    ok = len(ids) - len(set(ids)) == len(va) - len(set(va)) and not lost and not missing and b["terrain"] == a["terrain"]
    bad += not ok
    print("%-9s %s entities %d -> %d  missing-deps %s" % (n, "OK " if ok else "BAD", len(a["entities"]), len(b["entities"]), sorted(missing)))
print("files:", len(ds1s), "ds1 +", len(glob.glob(MOD + "hd/env/preset/act3/jungle/*.json")), "json; bad:", bad)
