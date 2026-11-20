import os, copy, sys
from ds1lib import *
J = BASE + "/act3/jungle/"
def fl(d,x,y):
    if not (0<=x<d.w and 0<=y<d.h): return None
    p,m,s = decode(d.cell(d.floors[0],x,y)); return (m,s) if p else None
# templates: raw floor values + wall cells from canonical sources
def grab(name, x0, y0, w, h):
    d = Ds1(J+name+".ds1")
    return [[d.cell(d.floors[0],x0+i,y0+j) for i in range(w)] for j in range(h)]
TPL = {"H": (grab("rivns",18,17,4,2), 4, 2), "V": (grab("rive2",9,14,2,4), 2, 4)}
def stamp_ok(d,X,Y,main,subs):
    k=0
    for j in range(4):
        for i in range(4):
            if fl(d,X+i,Y+j) != (main,subs[k]): return False
            k+=1
    return True
S11a=list(range(0,16)); S11b=list(range(47,63)); S12=list(range(16,32)); S10=list(range(1,17))
# original (pre-crossing) cells under each template footprint
FOOT = {"H": [[(11,6),(11,7),(11,51),(11,52)],[(11,10),(11,11),(11,55),(11,56)]],
        "V": [[(12,25),(12,26)],[(12,29),(12,30)],[(10,2),(10,3)],[(10,6),(10,7)]]}
def foot_ok(d,kind,cx,cy):
    f=FOOT[kind]
    return all(fl(d,cx+i,cy+j)==f[j][i] for j in range(len(f)) for i in range(len(f[0])))
def candidates(d):
    return [(k,x,y) for k in ("H","V") for y in range(d.h) for x in range(d.w) if foot_ok(d,k,x,y)]
def apply(d,kind,cx,cy,clear_walls=True):
    raw,w,h = TPL[kind]
    for j in range(h):
        for i in range(w):
            d.set_cell(d.floors[0],cx+i,cy+j,raw[j][i])
            if clear_walls:
                for wo,oo in d.walls:
                    d.set_cell(wo,cx+i,cy+j,0); d.set_cell(oo,cx+i,cy+j,0)
def big_comps(d, tiles):
    g,_ = collision(d, tiles); comp,sizes = components(g)
    return g, comp, sizes
def analyse(name, verbose=True):
    tiles = tileset()
    d = Ds1(J+name+".ds1")
    g, comp, sizes = big_comps(d, tiles)
    order = sorted(range(len(sizes)), key=lambda c:-sizes[c])
    main = order[0]; pockets = [c for c in order[1:] if sizes[c]>100]
    res=[]
    for kind,cx,cy in candidates(d):
        # skip if already a crossing
        if fl(d,cx,cy)[0]==14: continue
        dd = Ds1(J+name+".ds1"); apply(dd,kind,cx,cy)
        g2, comp2, sizes2 = big_comps(dd, tiles)
        # which original components are now joined with main?
        def rep(c):
            for y in range(len(comp)):
                for x in range(len(comp[0])):
                    if comp[y][x]==c and comp2[y][x]>=0: return comp2[y][x]
        m2 = rep(main)
        joined = [c for c in pockets if rep(c)==m2]
        res.append((kind,cx,cy,[sizes[c] for c in joined]))
    if verbose:
        print(name, "main", sizes[main], "pockets", [sizes[c] for c in pockets])
        for r in res: print("   ", r)
    return res
if __name__ == "__main__":
    for n in sys.argv[1:]: analyse(n)
