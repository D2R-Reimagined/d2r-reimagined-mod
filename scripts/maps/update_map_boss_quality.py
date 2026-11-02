#!/usr/bin/env python3
"""Update only map boss quality fields in both treasureclassex.txt banks.

Standalone, standard library only. From the mod root:
    python scripts/maps/update_map_boss_quality.py --root .
    python scripts/maps/update_map_boss_quality.py --root . --check

A downloaded copy can be run with --root pointing at the mod directory that
contains data/global/excel. No plugin checkout or stock map assets are needed.
"""
from __future__ import annotations

import argparse
from pathlib import Path


BOSS_SOURCES = {
    1: 'Andarielq (H)',
    2: 'Andarielq (H)',
    3: 'Duriel (H)',
    4: 'Mephisto (H)',
    5: 'Mephisto (H)',
    6: 'Baal (H)',
}
QUALITY_FIELDS = ('Unique', 'Set', 'Rare', 'Magic')
UNIQUE_SET_BY_TIER = {1: 850, 2: 850, 3: 850, 4: 900, 5: 941, 6: 993}


def apply_boss_quality(header: list[str], rows: list[list[str]]) -> int:
    """Set tier-specific Unique/Set; retain act boss Rare/Magic per bank."""
    key = header.index('Treasure Class')
    columns = [header.index(field) for field in QUALITY_FIELDS]
    required = set(BOSS_SOURCES.values()) | {f'RMap T{tier} Boss' for tier in BOSS_SOURCES}
    named = {}
    for row in rows:
        name = row[key]
        if name in required:
            if name in named:
                raise ValueError(f'Duplicate treasure class: {name}')
            named[name] = row
    missing = required - named.keys()
    if missing:
        raise ValueError('Missing treasure classes: ' + ', '.join(sorted(missing)))
    for source in set(BOSS_SOURCES.values()):
        for col in columns:
            if header[col] in ('Unique', 'Set'):
                continue
            value = named[source][col]
            if not value.isdigit() or not 0 <= int(value) <= 1024:
                raise ValueError(f'{source}: invalid {header[col]}={value!r}')
    changed = 0
    for tier, source in BOSS_SOURCES.items():
        boss = named[f'RMap T{tier} Boss']
        for col in columns:
            value = (str(UNIQUE_SET_BY_TIER[tier]) if header[col] in ('Unique', 'Set')
                     else named[source][col])
            changed += boss[col] != value
            boss[col] = value
    return changed


def updated_bytes(path: Path) -> tuple[bytes, int]:
    raw = path.read_bytes()
    text = raw.decode('utf-8')
    if text.startswith('\ufeff'):
        raise ValueError(f'{path}: unexpected UTF-8 BOM')
    newline = '\r\n' if b'\r\n' in raw else '\n'
    trailing = text.endswith(newline)
    lines = text.split(newline)
    if trailing:
        lines.pop()
    records = [line.split('\t') for line in lines]
    header, rows = records[0], records[1:]
    for line, row in enumerate(rows, 2):
        if len(row) != len(header):
            raise ValueError(f'{path}: line {line} has {len(row)} cells; expected {len(header)}')
    changed = apply_boss_quality(header, rows)
    result = newline.join('\t'.join(row) for row in records)
    if trailing:
        result += newline
    return result.encode('utf-8'), changed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, default=Path.cwd(),
                        help='mod directory containing data/global/excel (default: current directory)')
    parser.add_argument('--check', action='store_true', help='report differences without writing')
    args = parser.parse_args(argv)
    excel = args.root / 'data/global/excel'
    # Validate and prepare BOTH banks before writing either file.
    pending = [(path, *updated_bytes(path)) for path in
               (excel / 'treasureclassex.txt', excel / 'base/treasureclassex.txt')]
    for path, data, changed in pending:
        if changed and not args.check:
            path.write_bytes(data)
        status = 'needs update' if args.check and changed else 'updated' if changed else 'matches'
        print(f'{path}: {status} ({changed} quality fields)')
    return int(args.check and any(changed for _, _, changed in pending))


if __name__ == '__main__':
    raise SystemExit(main())
