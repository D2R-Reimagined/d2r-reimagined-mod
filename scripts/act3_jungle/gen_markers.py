"""Light the approach to Act 3 jungle side-area entrances.

For every Spid*/Pyg* clearing that holds a cave/dungeon warp tile, add DS1 object
units (Act 3 objpreset): a TikiTorch1 pair just inside each opening of the block,
torches every ~5 tiles along the walking route, and a JungleBrazier pair at the
cave mouth. Objects carry their own HD models, so no preset JSON change is needed.
"""
import glob, heapq, math, os, struct, sys
from collections import deque
from ds1lib import Ds1, BASE, collision, components, tileset, decode, dt1_tiles

J = BASE + "/act3/jungle/"
MOD = "C:/dev/d2r/d2r-reimagined-mod/data/global/tiles/act3/jungle/"
TIKI, BRAZIER = 5, 0          # objpreset Act 3 Index: TikiTorch1, JungleBrazier
LT = ["act3/docktown/bridge.dt1", "act3/ground/darkgrass.dt1", "act3/ground/darkmud.dt1",
      "act3/ground/drymud.dt1", "act3/ground/greenmud.dt1", "act3/jungle/trees.dt1",
      "act3/jungle/treegrp.dt1", "act3/river/rivbank.dt1", "act3/docktown/bridge.dt1",
      "act3/jungle/ruin.dt1", "act3/spider/spiderent.dt1", "act3/jungle/dungent.dt1",
      "act3/river/pool.dt1", "act3/jungle/pygmy.dt1"]
MASK = {"spid": 1636, "pyg": 15078}
STEP, GATE_IN, MOUTH_BACK = 30, 6, 8


def tiles_for(name):
    m = MASK["spid" if name.startswith("spid") else "pyg"]
    return tileset([LT[i] for i in range(len(LT)) if m >> i & 1])


def warp_tile(d):
    for i, (w, o) in enumerate(d.walls):
        for y in range(d.h):
            for x in range(d.w):
                if d.orient(i, x, y) == 10 and d.cell(w, x, y) & 255:
                    return x, y
    return None


def walk(g, x, y):
    return 0 <= y < len(g) and 0 <= x < len(g[0]) and not g[y][x] & 9


def wall_dist(g):
    H, W = len(g), len(g[0]); dist = [[0] * W for _ in range(H)]; q = deque()
    for y in range(H):
        for x in range(W):
            if not walk(g, x, y): q.append((x, y))
            else: dist[y][x] = 10 ** 6
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H and dist[ny][nx] > dist[y][x] + 1:
                dist[ny][nx] = dist[y][x] + 1; q.append((nx, ny))
    return dist


def route(g, wd, a, b):
    """Shortest path that keeps away from walls (Dijkstra, cost grows near walls)."""
    best = {a: 0}; prev = {}; pq = [(0, a)]
    while pq:
        c, p = heapq.heappop(pq)
        if p == b: break
        if c > best[p]: continue
        x, y = p
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if not walk(g, *n): continue
            nc = c + 1 + max(0, 4 - wd[n[1]][n[0]]) * 3
            if nc < best.get(n, 1e18): best[n] = nc; prev[n] = p; heapq.heappush(pq, (nc, n))
    if b not in prev and a != b: return None
    path = [b]
    while path[-1] != a: path.append(prev[path[-1]])
    return path[::-1]


def openings(g):
    """Middle subtile of each walkable run on the block border (row/col 0..W-1)."""
    H, W = len(g), len(g[0]); out = []
    for edge in ("N", "S", "W", "E"):
        cells = {"N": [(x, 0) for x in range(W)], "S": [(x, H - 1) for x in range(W)],
                 "W": [(0, y) for y in range(H)], "E": [(W - 1, y) for y in range(H)]}[edge]
        run = []
        for c in cells + [None]:
            if c and walk(g, *c): run.append(c); continue
            if len(run) >= 5: out.append((edge, run[len(run) // 2]))
            run = []
    return out


def connected(g, a, b):
    seen = {a}; q = deque([a])
    while q:
        p = q.popleft()
        if p == b: return True
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (p[0] + dx, p[1] + dy)
            if n not in seen and walk(g, *n): seen.add(n); q.append(n)
    return False


def plan(name):
    d = Ds1(J + name + ".ds1"); wt = warp_tile(d)
    if not wt: return d, None, []
    g, _ = collision(d, tiles_for(name)); wd = wall_dist(g)
    cx, cy = wt[0] * 5 + 2, wt[1] * 5 + 2
    cand = [(abs(x - cx) + abs(y - cy), (x, y)) for y in range(len(g)) for x in range(len(g[0])) if walk(g, x, y)]
    mouth = min(cand)[1]
    taken = [(u[2], u[3]) for u in d.units]
    placed = []; blocked = set(); pathcells = set(); paths = []
    for edge, e in openings(g):
        p = route(g, wd, e, mouth)
        if p: paths.append((edge, p)); pathcells.update(p)

    def spot(path, i, side):
        a = path[max(0, i - 4)]; b = path[min(len(path) - 1, i + 4)]
        dx, dy = b[0] - a[0], b[1] - a[1]; n = math.hypot(dx, dy) or 1
        px, py = -dy / n * side, dx / n * side
        x0, y0 = path[i]
        for off in (3, 4, 5, 2, 6):
            x, y = round(x0 + px * off), round(y0 + py * off)
            if not walk(g, x, y) or (x, y) in blocked: continue
            if min(abs(x - qx) + abs(y - qy) for qx, qy in pathcells) < 2: continue
            if any(abs(x - tx) + abs(y - ty) < 4 for tx, ty in taken): continue
            return x, y
        return None

    def put(obj, s, why):
        if not s: return
        blocked.add(s); taken.append(s); placed.append((obj, s[0], s[1], why))

    lit = set()   # cells of routes already lined; later routes stop where they join one
    for edge, p in sorted(paths, key=lambda t: -len(t[1])):
        L = len(p)
        if L < GATE_IN + MOUTH_BACK + 4: continue
        i = GATE_IN
        put(TIKI, spot(p, i, 1), "gate %s" % edge); put(TIKI, spot(p, i, -1), "gate %s" % edge)
        side = 1; i += STEP
        while i < L - MOUTH_BACK - 10:
            x, y = p[i]
            if any((x + dx, y + dy) in lit for dx in range(-3, 4) for dy in range(-3, 4)): break
            put(TIKI, spot(p, i, side), "route %s" % edge); side = -side; i += STEP
        lit.update(p)
    # brazier pair at the mouth, on the longest route's approach
    if paths:
        p = max(paths, key=lambda t: len(t[1]))[1]
        i = max(0, len(p) - 1 - MOUTH_BACK)
        put(BRAZIER, spot(p, i, 1), "mouth"); put(BRAZIER, spot(p, i, -1), "mouth")

    # walkability must survive the new collision
    g2 = [row[:] for row in g]
    for _, x, y, _ in placed: g2[y][x] |= 1
    for edge, p in paths:
        assert connected(g2, p[0], mouth), (name, edge)
    return d, (wt, mouth), placed


def write_units(d, placed):
    b = d.bytes; o = d.units_off
    cnt = struct.unpack_from("<i", b, o)[0]
    recs = b"".join(struct.pack("<iiiii", 2, obj, x, y, 0) for obj, x, y, _ in placed)
    end = d.after_units
    return bytes(b[:o]) + struct.pack("<i", cnt + len(placed)) + bytes(b[o + 4:end]) + recs + bytes(b[end:])


def main(write):
    files = sorted(os.path.basename(p)[:-4] for p in glob.glob(J + "spid*.ds1") + glob.glob(J + "pyg*.ds1"))
    total = 0
    for n in files:
        d, info, placed = plan(n)
        if not info: continue
        total += len(placed)
        kinds = {}
        for obj, x, y, why in placed: kinds[why.split()[0]] = kinds.get(why.split()[0], 0) + 1
        print("%-8s warp %s mouth %s  %s" % (n, info[0], info[1], kinds))
        if write and placed:
            os.makedirs(MOD, exist_ok=True)
            data = write_units(d, placed)
            chk = Ds1.__new__(Ds1)
            open(MOD + n + ".ds1", "wb").write(data)
            r = Ds1(MOD + n + ".ds1")
            assert r.units[:len(d.units)] == d.units and len(r.units) == len(d.units) + len(placed)
            assert bytes(r.bytes[r.after_units:]) == bytes(d.bytes[d.after_units:])
    print("objects placed:", total)


if __name__ == "__main__":
    main("--write" in sys.argv)
