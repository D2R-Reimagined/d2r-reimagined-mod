"""Byte-faithful D2R preset JSON writer (minified, upper-case float exponents)."""
import json, re, glob, sys

_STR = re.compile(r'("(?:[^"\\]|\\.)*")')
_EXP = re.compile(r'(?<=[0-9])e(?=[-+]?[0-9])')


def dump(j):
    s = json.dumps(j, separators=(",", ":"))
    parts = _STR.split(s)
    return "".join(p if k % 2 else _EXP.sub("E", p) for k, p in enumerate(parts))


if __name__ == "__main__":
    bad = 0
    files = glob.glob("C:/dev/d2r/base-files/data/data/hd/env/preset/act3/jungle/*.json")
    for p in files:
        raw = open(p, "rb").read().decode()
        if dump(json.loads(raw)) != raw:
            bad += 1
            print("diff", p)
    print("checked", len(files), "bad", bad)
