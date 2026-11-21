"""How much string text a build hands the game, per language, against plain D2R's limit.

Plain D2R crashes once the combined text of all its string catalogs passes a fixed size;
Russian reaches it first (Cyrillic is two bytes per character in UTF-8, so ruRU is the
largest language by bytes). D2RLoader lifts the limit, so this matters for the soft-mod
(standard) build only.

The game loads every catalog in local/lng/strings; a mod's catalog replaces the game's
file of the same name. So the total is the plain game's catalogs with the build's
catalogs swapped in. This script adds that up per locale, in UTF-8 bytes and characters.

  python scripts/studio/string_budget.py                     # standard build, from source/strings
  python scripts/studio/string_budget.py --mode full         # what the d2rl build ships
  python scripts/studio/string_budget.py --output <dir>      # a built strings folder instead
  python scripts/studio/string_budget.py --max-bytes 845000  # fail above a limit

The plain game's catalogs come from --game-strings, $D2R_GAME_STRINGS, or
../base-files/data/data/local/lng/strings next to the repo (an extract of the game data).
The limit is scripts/studio/string_budget.json "maxBytes" (for "locale"); until it has been
measured in game it is null and the script only reports.

Exit codes: 0 within the limit (or no limit set), 1 over it, 2 bad input.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONFIG = Path(__file__).with_name('string_budget.json')


def _load(path: Path):
    return json.loads(path.read_bytes().decode('utf-8-sig'))


def game_catalogs(folder: Path) -> dict[str, list[dict]]:
    """The plain game's catalogs by file name (entries in the game's own shape)."""
    return {p.name: _load(p) for p in sorted(folder.glob('*.json'))}


def built_catalogs(folder: Path) -> dict[str, list[dict]]:
    return game_catalogs(folder)


def source_catalogs(repo: Path, mode: str) -> dict[str, list[dict]]:
    """The catalogs a Mod Studio build writes from source/strings, in standard or full string mode."""
    out: dict[str, list[dict]] = {}
    for path in sorted((repo / 'source' / 'strings').glob('*.json')):
        doc = _load(path)
        locales = doc['schema']['locales']
        entries = []
        for r in doc['records']:
            full = r.get('translations', {})
            compact = r.get('standardTranslations', {}) if mode == 'standard' else {}
            nulls = set(r.get('nullTranslations', []))
            e = {'id': r['id'], 'Key': r['Key']}
            for loc in locales:
                e[loc] = compact[loc] if loc in compact else (None if loc in nulls else full.get(loc, ''))
            entries.append(e)
        out[doc['schema']['target'].rsplit('/', 1)[1]] = entries
    return out


def totals(catalogs: dict[str, list[dict]]) -> dict[str, dict[str, int]]:
    """locale -> {'bytes': UTF-8 bytes, 'chars': characters} over every entry of every catalog."""
    out: dict[str, dict[str, int]] = {}
    for entries in catalogs.values():
        for e in entries:
            for key, value in e.items():
                if key in ('id', 'Key') or not isinstance(value, str):
                    continue
                t = out.setdefault(key, {'bytes': 0, 'chars': 0})
                t['bytes'] += len(value.encode('utf-8'))
                t['chars'] += len(value)
    return out


def loaded(game: dict[str, list[dict]], mod: dict[str, list[dict]]) -> dict[str, list[dict]]:
    files = dict(game)
    files.update(mod)
    return files


def default_game_strings() -> Path | None:
    env = os.environ.get('D2R_GAME_STRINGS')
    if env:
        return Path(env)
    guess = REPO.parent / 'base-files' / 'data' / 'data' / 'local' / 'lng' / 'strings'
    return guess if guess.is_dir() else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--repo', type=Path, default=REPO)
    ap.add_argument('--mode', choices=('standard', 'full'), default='standard',
                    help='string mode to build source/strings in (standard = the soft-mod build)')
    ap.add_argument('--output', type=Path, help="a built local/lng/strings folder to measure instead of source/strings")
    ap.add_argument('--game-strings', type=Path, default=None, help="the plain game's local/lng/strings folder")
    ap.add_argument('--max-bytes', type=int, default=None, help='limit for the watched locale (default: string_budget.json)')
    ap.add_argument('--locale', default=None, help='locale the limit applies to (default: string_budget.json, ruRU)')
    args = ap.parse_args(argv)

    config = _load(CONFIG) if CONFIG.exists() else {}
    locale = args.locale or config.get('locale', 'ruRU')
    limit = args.max_bytes if args.max_bytes is not None else config.get('maxBytes')
    game_dir = args.game_strings or default_game_strings()
    if game_dir is None or not game_dir.is_dir():
        print("The plain game's string catalogs were not found. Pass --game-strings <data>/local/lng/strings "
              "or set D2R_GAME_STRINGS.", file=sys.stderr)
        return 2
    game = game_catalogs(game_dir)
    if args.output:
        if not args.output.is_dir():
            print(f'{args.output} is not a folder', file=sys.stderr)
            return 2
        mod, what = built_catalogs(args.output), str(args.output)
    else:
        mod, what = source_catalogs(args.repo, args.mode), f'source/strings ({args.mode} string mode)'

    plain, build = totals(game), totals(loaded(game, mod))
    print(f'String text the game loads: {what}, over the plain game in {game_dir}')
    print(f"{'locale':8}{'build bytes':>14}{'plain game':>14}{'added':>11}{'build chars':>14}")
    for loc in sorted(build, key=lambda l: -build[l]['bytes']):
        b, p = build[loc], plain.get(loc, {'bytes': 0})
        mark = '  <- limit applies' if loc == locale else ''
        print(f"{loc:8}{b['bytes']:>14,}{p['bytes']:>14,}{b['bytes'] - p['bytes']:>+11,}{b['chars']:>14,}{mark}")
    watched = build.get(locale, {'bytes': 0})['bytes']
    biggest = max(build, key=lambda l: build[l]['bytes'])
    if biggest != locale:
        print(f'note: {biggest} is larger than {locale} by bytes in this build')
    if limit is None:
        print(f'{locale}: {watched:,} bytes; no limit set (string_budget.json maxBytes is null until it is measured in game)')
        return 0
    if watched > limit:
        print(f'{locale}: {watched:,} bytes is {watched - limit:,} over the limit of {limit:,}: plain D2R would crash')
        return 1
    print(f'{locale}: {watched:,} bytes, {limit - watched:,} under the limit of {limit:,}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
