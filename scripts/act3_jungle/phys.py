import struct, sys
def load(path):
    b = open(path,"rb").read()
    hdr, _, voff, _, toff, _, nbvh, nv, nt = struct.unpack_from("<IIIIIIIII", b, 0)
    verts = [struct.unpack_from("<fff", b, voff+i*16) for i in range(nv)]
    tris = [struct.unpack_from("<8I", b, toff+i*32) for i in range(nt)]
    return verts, tris, (hdr, voff, toff, nbvh, nv, nt)
if __name__=="__main__":
    v,t,h = load(sys.argv[1]); print(h)
    xs=[a[0] for a in v]; ys=[a[1] for a in v]; zs=[a[2] for a in v]
    print("x",min(xs),max(xs),"y",min(ys),max(ys),"z",min(zs),max(zs))
    print(v[:3]); print(t[:4])

import os, math
PRE = "C:/dev/d2r/base-files/data/data/hd/env/preset/act3/jungle/"
def heightgrid(name, n=33, res=5):
    """height at subtile centres: grid[sy][sx], HD coords 2*s+1"""
    d = [f for f in os.listdir(PRE) if f.lower()==name.lower() and os.path.isdir(PRE+f)][0]
    v,t,_ = load(PRE+d+"/terrain.physics")
    N = n*res; step = 10.0/res
    g = [[None]*N for _ in range(N)]
    for tri in t:
        a,b,c = (v[tri[0]],v[tri[1]],v[tri[2]])
        minx=min(a[0],b[0],c[0]); maxx=max(a[0],b[0],c[0]); minz=min(a[2],b[2],c[2]); maxz=max(a[2],b[2],c[2])
        det = (b[2]-c[2])*(a[0]-c[0]) + (c[0]-b[0])*(a[2]-c[2])
        if abs(det) < 1e-9: continue
        for sx in range(max(0,int(minx/step)-1), min(N, int(maxx/step)+2)):
            px = sx*step+step/2
            if px<minx-1e-6 or px>maxx+1e-6: continue
            for sz in range(max(0,int(minz/step)-1), min(N,int(maxz/step)+2)):
                pz = sz*step+step/2
                l1 = ((b[2]-c[2])*(px-c[0]) + (c[0]-b[0])*(pz-c[2]))/det
                l2 = ((c[2]-a[2])*(px-c[0]) + (a[0]-c[0])*(pz-c[2]))/det
                l3 = 1-l1-l2
                if l1>=-1e-6 and l2>=-1e-6 and l3>=-1e-6:
                    y = l1*a[1]+l2*b[1]+l3*c[1]
                    if g[sz][sx] is None or y > g[sz][sx]: g[sz][sx]=y
    return g
