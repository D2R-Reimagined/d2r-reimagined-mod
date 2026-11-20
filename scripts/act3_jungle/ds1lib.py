"""Minimal DS1 v16-18 reader + DT1 collision for Act 3 jungle analysis."""
import struct, os
from collections import deque

BASE = r"C:/dev/d2r/base-files/data/data/global/tiles"
JUNGLE_DT1 = ["act3/docktown/bridge.dt1", "act3/ground/darkgrass.dt1", "act3/ground/darkmud.dt1",
              "act3/ground/drymud.dt1", "act3/ground/greenmud.dt1", "act3/jungle/trees.dt1",
              "act3/jungle/treegrp.dt1", "act3/river/rivbank.dt1"]


class Ds1:
    def __init__(self, path):
        self.path = path
        b = self.bytes = bytearray(open(path, "rb").read())
        o = 0
        def i32():
            nonlocal o
            v = struct.unpack_from("<i", b, o)[0]; o += 4; return v
        self.version = i32(); self.w = i32() + 1; self.h = i32() + 1; self.act = i32() + 1
        self.tag = i32(); n = i32(); self.files = []
        for _ in range(n):
            e = b.index(0, o); self.files.append(b[o:e].decode()); o = e + 1
        self.nwalls = i32(); self.nfloors = i32()
        cells = self.w * self.h; size = cells * 4
        self.walls = []  # (offset, orient offset)
        for _ in range(self.nwalls):
            self.walls.append((o, o + size)); o += 2 * size
        self.floors = []
        for _ in range(self.nfloors):
            self.floors.append(o); o += size
        self.shadow = o; o += size
        self.tagoff = None
        if self.tag in (1, 2):
            self.tagoff = o; o += size
        self.units_off = o
        cnt = i32(); self.units = []
        for _ in range(cnt):
            t, i, x, y, f = struct.unpack_from("<iiiii", b, o); self.units.append((t, i, x, y, f)); o += 20
        self.after_units = o

    def cell(self, off, x, y):
        return struct.unpack_from("<I", self.bytes, off + (y * self.w + x) * 4)[0]

    def set_cell(self, off, x, y, v):
        struct.pack_into("<I", self.bytes, off + (y * self.w + x) * 4, v)

    def orient(self, l, x, y):
        return self.cell(self.walls[l][1], x, y) & 255


def dt1_tiles(path):
    b = open(path, "rb").read()
    assert struct.unpack_from("<ii", b, 0) == (7, 6), path
    count, start = struct.unpack_from("<ii", b, 268)
    out = {}
    for i in range(count):
        h = start + i * 96
        orient, main, sub = struct.unpack_from("<iii", b, h + 20)
        flags = [0] * 25
        for y in range(5):
            for x in range(5):
                flags[y * 5 + x] = b[h + 40 + (4 - y) * 5 + x]
        out.setdefault((orient, main, sub), []).append(flags)
    return out


_cache = {}
def tileset(files=JUNGLE_DT1):
    key = tuple(files)
    if key not in _cache:
        t = {}
        for f in files:
            for k, v in dt1_tiles(os.path.join(BASE, f)).items():
                t.setdefault(k, []).extend(v)
        _cache[key] = t
    return _cache[key]


def decode(v):
    return (v & 255, (v >> 20) & 63, (v >> 8) & 255)  # prop1, main, sub


def collision(d, tiles=None):
    """Return subtile grid [y][x] of flags (bit0 walk-block). Missing floor = blocked(1)."""
    tiles = tiles or tileset()
    W, H = d.w * 5, d.h * 5
    g = [[0] * W for _ in range(H)]
    unknown = set()
    for ty in range(d.h):
        for tx in range(d.w):
            fl = [0] * 25
            has_floor = any(d.cell(f, tx, ty) & 255 for f in d.floors)
            forced = any(d.cell(f, tx, ty) & 0x20000 for f in d.floors) or any(d.cell(w, tx, ty) & 0x20000 for w, _ in d.walls)
            if not has_floor or forced:
                fl = [1] * 25
            layers = [(f, 0) for f in d.floors] + [(w, d.orient(i, tx, ty)) for i, (w, _) in enumerate(d.walls)]
            for off, orient in layers:
                v = d.cell(off, tx, ty)
                if v & 255 == 0:
                    continue
                _, main, sub = decode(v)
                keys = [(orient, main, sub)]
                if orient == 3:
                    keys.append((4, main, sub))
                for k in keys:
                    vs = tiles.get(k)
                    if vs is None and orient in (18, 19):
                        alt = 19 if orient == 18 else 18
                        vs = tiles.get((alt, main, sub)) or tiles.get((alt, main, 0))
                    if vs is None:
                        if k == keys[0]:
                            unknown.add(k)
                        continue
                    for var in vs:
                        for i in range(25):
                            fl[i] |= var[i]
            for sy in range(5):
                for sx in range(5):
                    g[ty * 5 + sy][tx * 5 + sx] = fl[sy * 5 + sx]
    return g, unknown


def components(g, mask=9):
    H, W = len(g), len(g[0])
    comp = [[-1] * W for _ in range(H)]
    n = 0; sizes = []
    for y in range(H):
        for x in range(W):
            if g[y][x] & mask or comp[y][x] >= 0:
                continue
            q = deque([(x, y)]); comp[y][x] = n; s = 0
            while q:
                cx, cy = q.popleft(); s += 1
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < W and 0 <= ny < H and comp[ny][nx] < 0 and not g[ny][nx] & mask:
                        comp[ny][nx] = n; q.append((nx, ny))
            sizes.append(s); n += 1
    return comp, sizes
