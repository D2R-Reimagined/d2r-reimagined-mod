"""The soft-mod (standard profile) build: the mod without maps.

The `standard` profile (compatibility/standard) is the mod for plain D2R, with no
D2RLoader. Maps do not work there at all. A player's first map only ever comes from
d2rl-maps.dll: no treasure class, monster or cube recipe outside the maps leads in,
and every maps recipe takes a map or map currency. So that build leaves out what it
can of the maps, and nothing else changes:

  - Every maps cube recipe (rmap activate/upgrade/reroll/infuse/corrupt) is removed.
    They are the last rows of cubemain, so no other row moves, and the activate rows
    point at levels past 255, which a cube output's one-byte level cannot hold.
  - Every string the generator writes ships empty: its compact (standard-mode)
    translation is "" in every locale. Plain D2R crashes once the strings' combined
    size passes its limit (Russian first), and these are never shown without the
    plugin. The keys stay, so no row is left naming a missing string.

The other maps rows stay as dead data. Most cannot leave without moving the mod's own
rows that follow them (Azmodan and Cydaea in levels, skills, monprop, monstats,
monstats2, lvlprest, missiles and monpreset: rows are referenced by position), and the
map treasure classes, states, Wardens and items are still named by those rows.

The cube rules are a Mod Studio rule set, compatibility/standard/maps-soft/cubemain.json;
the compact translations sit on the generator's own entries in source/strings. Both are
rewritten after every generator run, so change them here, not in Studio.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import maps_config as cfg

PROFILE = Path("compatibility") / "standard"
FOLDER = "maps-soft"
GENERATOR = "scripts/maps/generate_maps.py"
REASON = "Soft-mod build (no D2RLoader): maps need d2rl-maps.dll"
CUBE = "global/excel/cubemain.txt"
# Same pattern Mod Studio checks: a compact translation must keep the full text's placeholders.
_PLACEHOLDER = re.compile(r"%%|%(?:\d+\$)?[-+#0 ]*(?:\d+|\*)?(?:\.(?:\d+|\*))?[hlL]*[diuoxXfFeEgGaAcspn]")


def rules(project) -> list[dict]:
    """A remove rule for every maps cube recipe, in row order."""
    header, _ = project.read_table(CUBE)
    desc = header.index("description")
    table = project.table_name(CUBE)
    return [{"table": table, "record": source_id, "reason": REASON, "remove": True}
            for source_id, row in project.read_records(CUBE)
            if row[desc].split()[:1] == [cfg.CUBE_TAG]]


def rule_sets(all_rules: list[dict]) -> dict[str, dict]:
    """File name (relative to the profile folder) -> the rule set for one table."""
    out: dict[str, dict] = {}
    for rule in all_rules:
        out.setdefault(f"{FOLDER}/{rule['table']}.json", {"generator": GENERATOR, "rules": []})["rules"].append(rule)
    return out


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compact_catalogs(project, string_keys: dict[str, set[str]], dumps) -> dict[Path, str]:
    """Catalog file -> its text with every generator-written entry's compact translations set to ""."""
    out: dict[Path, str] = {}
    for name, keys in sorted(string_keys.items()):
        path = project.catalog_file(f"local/lng/strings/{name}")
        doc = json.loads(path.read_text(encoding="utf-8"))
        locales = doc["schema"]["locales"]
        for record in doc["records"]:
            if record["Key"] not in keys:
                continue
            full = record.get("translations", {})
            # A locale whose text has placeholders keeps it: Studio requires the compact text to carry them too.
            empty = [loc for loc in locales if not [m for m in _PLACEHOLDER.findall(full.get(loc) or "") if m != "%%"]]
            record["standardTranslations"] = {loc: "" for loc in empty}
            record["standardReviewedAgainst"] = {loc: _sha256(full.get(loc) or "") for loc in empty}
        out[path] = dumps(doc)
    return out


def write(project, repo: Path, dumps, string_keys: dict[str, set[str]], check: bool = False) -> list[Path]:
    """Write the rule sets, list them in the profile and empty the maps strings; return what is (or would be) changed."""
    profile_dir = repo / PROFILE
    wanted = {name: dumps(rule_set) for name, rule_set in rule_sets(rules(project)).items()}
    changed: list[Path] = []

    def put(path: Path, text: str) -> None:
        if not path.exists() or path.read_bytes().decode("utf-8").replace("\r\n", "\n") != text:
            changed.append(path)
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(text.encode("utf-8"))

    folder = profile_dir / FOLDER
    present = {f"{FOLDER}/{p.name}": p for p in folder.glob("*.json")} if folder.is_dir() else {}
    for name, text in wanted.items():
        put(profile_dir / name, text)
    for name, path in present.items():
        if name not in wanted:
            changed.append(path)
            if not check:
                path.unlink()
    profile_path = profile_dir / "profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8-sig"))
    others = [x for x in profile.get("tableOverrides", []) if not x.startswith(FOLDER + "/")]
    listed = others + sorted(wanted)
    if profile.get("tableOverrides", []) != listed:
        profile["tableOverrides"] = listed
        changed.append(profile_path)
        if not check:
            profile_path.write_bytes(dumps(profile).encode("utf-8"))
    for path, text in compact_catalogs(project, string_keys, dumps).items():
        put(path, text)
    return changed
