"""Mod Studio profile rules that keep maps working in the soft-mod build.

The `standard` profile (compatibility/standard) is the mod for plain D2R, with no
D2RLoader. Interior map themes work there as baseline maps. Exterior themes do not:
only d2rl-maps.dll reroutes outdoor level generation, and their Red Portal levels
pass 255, which the engine's one-byte cube output level cannot hold.

So for that profile only, and without moving or deleting any row (rows are
referenced by position):
  - every cube recipe of an exterior theme is disabled (enabled 1 -> 0)
  - every treasure class entry that drops an exterior map drops the paired
    interior map of the same tier instead, same weight, so totals are unchanged

Each rule is one file under compatibility/standard/maps-soft/, the format Mod
Studio applies at build time (one record per file, cells with expect/value). They
name rows by Studio sourceId, so they are regenerated after every generator run.
"""
from __future__ import annotations

from pathlib import Path

import maps_config as cfg

PROFILE = Path("compatibility") / "standard"
FOLDER = "maps-soft"
REASON = ("Soft-mod build (no D2RLoader): exterior map themes need d2rl-maps.dll; "
          "written by scripts/maps/generate_maps.py")
CUBE = "global/excel/cubemain.txt"
TREASURE = ("global/excel/treasureclassex.txt", "global/excel/base/treasureclassex.txt")


def exterior_keys() -> list[str]:
    return [t["key"] for t in cfg.THEMES if t.get("exterior")]


def interior_partners(plans: list[dict]) -> dict[str, str]:
    """Exterior map code -> interior map code of the paired theme, same tier."""
    interior = [t["key"] for t in cfg.THEMES if not t.get("exterior")]
    by_key_tier = {(p["theme"]["key"], p["tier"]): p for p in plans}
    out = {}
    for i, key in enumerate(exterior_keys()):
        partner = interior[i % len(interior)]
        for p in plans:
            if p["theme"]["key"] != key:
                continue
            q = by_key_tier[(partner, p["tier"])]
            out[p["item_code"]] = q["item_code"]
            out[cfg.expansion_code(p["item_code"])] = cfg.expansion_code(q["item_code"])
    return out


def rules(project, plans: list[dict]) -> dict[str, dict]:
    """File name (relative to the profile folder) -> rule, from the saved Studio tables."""
    out: dict[str, dict] = {}

    def add(table: str, source_id: str, changes: dict) -> None:
        out[f"{FOLDER}/{table}-{source_id}.json"] = {
            "table": table, "record": source_id, "reason": REASON, "changes": changes}

    header, _ = project.read_table(CUBE)
    desc, enabled = header.index("description"), header.index("enabled")
    keys = set(exterior_keys())
    for source_id, row in project.read_records(CUBE):
        words = row[desc].split()
        if len(words) >= 3 and words[0] == cfg.CUBE_TAG and words[2] in keys:
            if row[enabled] != "0":
                add(project.table_name(CUBE), source_id, {"enabled": {"expect": row[enabled], "value": "0"}})

    partners = interior_partners(plans)
    for target in TREASURE:
        header, _ = project.read_table(target)
        items = [(f"Item{i}", header.index(f"Item{i}")) for i in range(1, 11)]
        for source_id, row in project.read_records(target):
            changes = {name: {"expect": row[c], "value": partners[row[c]]}
                       for name, c in items if c < len(row) and row[c] in partners}
            if changes:
                add(project.table_name(target), source_id, changes)
    return out


def write(project, repo: Path, plans: list[dict], dumps, check: bool = False) -> list[Path]:
    """Write the rule files and list them in the profile; return what is (or would be) changed."""
    profile_dir = repo / PROFILE
    wanted = {name: dumps(rule) for name, rule in rules(project, plans).items()}
    changed: list[Path] = []
    folder = profile_dir / FOLDER
    present = {f"{FOLDER}/{p.name}": p for p in folder.glob("*.json")} if folder.is_dir() else {}
    for name, text in wanted.items():
        path = profile_dir / name
        if not path.exists() or path.read_bytes().decode("utf-8").replace("\r\n", "\n") != text:
            changed.append(path)
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(text.encode("utf-8"))
    for name, path in present.items():
        if name not in wanted:
            changed.append(path)
            if not check:
                path.unlink()
    profile_path = profile_dir / "profile.json"
    import json
    profile = json.loads(profile_path.read_text(encoding="utf-8-sig"))
    others = [x for x in profile.get("tableOverrides", []) if not x.startswith(FOLDER + "/")]
    listed = others + sorted(wanted)
    if profile.get("tableOverrides", []) != listed:
        profile["tableOverrides"] = listed
        changed.append(profile_path)
        if not check:
            profile_path.write_bytes(dumps(profile).encode("utf-8"))
    return changed
