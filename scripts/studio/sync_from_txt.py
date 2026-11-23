#!/usr/bin/env python3
"""Bring native TXT / string-JSON changes into the Mod Studio source.

  python scripts/studio/sync_from_txt.py --merge origin/next [--check]
      Three-way merge of a branch that still keeps data/global/excel/*.txt and
      data/local/lng/strings/*.json (not yet converted to Mod Studio). For each such file
      the branch changed since the merge base, its changes are merged into the Studio
      table or catalog with `git merge-file` (tables line by line, catalogs entry by
      entry), so changes made here survive. Files that conflict are written with
      conflict markers to .studio/merge-conflicts/ and left unapplied.

      Typical use while merging an unconverted branch:
          git merge --no-commit origin/next        # TXT files conflict as modify/delete
          python scripts/studio/sync_from_txt.py --merge origin/next
          git rm --cached -r -q data/global/excel data/local/lng/strings   # keep them deleted
          (also delete those files from the working tree), review, commit

  python scripts/studio/sync_from_txt.py --tree <data-root> [--check]
      Overwrite tables/catalogs from a native data tree (<data-root>/global/excel/...,
      <data-root>/local/lng/strings/...), e.g. after editing TXT in an external tool.
      Unchanged rows keep their Studio ids.

Exit code: 0 applied/clean, 1 conflicts or (with --check) changes pending, 2 usage error.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from studio_tables import StudioProject  # noqa: E402

EXCEL = 'data/global/excel/'
STRINGS = 'data/local/lng/strings/'


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(['git', '-C', str(repo), *args], capture_output=True, check=check)


def parse_tsv(data: bytes) -> tuple[list[str], list[list[str]]]:
    text = data.decode('utf-8').replace('\r\n', '\n')
    lines = text.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    return lines[0].split('\t'), [line.split('\t') for line in lines[1:]]


def tsv_lines(header: list[str], rows: list[list[str]]) -> str:
    return '\n'.join('\t'.join(r) for r in [header] + rows) + '\n'


def catalog_lines(entries: list[dict]) -> str:
    # One entry per line, so merge-file merges whole entries.
    return ''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in entries)


def parse_catalog_lines(text: str) -> list[dict]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def merge3(ours: str, base: str, theirs: str) -> tuple[str, bool]:
    with tempfile.TemporaryDirectory() as d:
        paths = []
        for name, text in (('ours', ours), ('base', base), ('theirs', theirs)):
            p = Path(d) / name
            p.write_text(text, encoding='utf-8', newline='\n')
            paths.append(str(p))
        r = subprocess.run(['git', 'merge-file', '-p', '-L', 'studio', '-L', 'base', '-L', 'theirs', *paths],
                           capture_output=True)
        if r.returncode < 0 or r.returncode > 127:
            raise RuntimeError(r.stderr.decode())
        return r.stdout.decode('utf-8'), r.returncode > 0


def changed_paths(repo: Path, base: str, ref: str) -> list[str]:
    out = git(repo, 'diff', '--name-only', '--no-renames', base, ref, '--', EXCEL, STRINGS).stdout.decode()
    return [p for p in out.splitlines() if p.lower().endswith(('.txt', '.json'))]


def blob(repo: Path, rev: str, path: str) -> bytes | None:
    r = git(repo, 'show', f'{rev}:{path}', check=False)
    return r.stdout if r.returncode == 0 else None


def do_merge(repo: Path, project: StudioProject, ref: str, check: bool) -> int:
    base = git(repo, 'merge-base', 'HEAD', ref).stdout.decode().strip()
    conflicts_dir = repo / '.studio' / 'merge-conflicts'
    applied, conflicts, skipped = [], [], []
    for path in changed_paths(repo, base, ref):
        target = path[len('data/'):]
        theirs_b, base_b = blob(repo, ref, path), blob(repo, base, path)
        is_table = path.lower().endswith('.txt')
        known = project.has_table(target) if is_table else project.has_catalog(target)
        if not known:
            skipped.append(f'{path}: not in the Studio project (new file? import it in Mod Studio)')
            continue
        if theirs_b is None:
            skipped.append(f'{path}: deleted on {ref}; delete or keep the Studio table by hand')
            continue
        if is_table:
            header, rows = project.read_table(target)
            ours = tsv_lines(header, rows)
            th_header, th_rows = parse_tsv(theirs_b)
            theirs = tsv_lines(th_header, th_rows)
            base_t = tsv_lines(*parse_tsv(base_b)) if base_b is not None else ''
        else:
            ours = catalog_lines(project.read_strings(target))
            theirs = catalog_lines(json.loads(theirs_b.decode('utf-8-sig')))
            base_t = catalog_lines(json.loads(base_b.decode('utf-8-sig'))) if base_b is not None else ''
        merged, conflicted = merge3(ours, base_t, theirs)
        if conflicted:
            out = conflicts_dir / path
            if not check:
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(merged, encoding='utf-8', newline='\n')
            conflicts.append(f'{path} -> {out}')
            continue
        if merged == ours:
            continue
        if is_table:
            m_header, m_rows = parse_tsv(merged.encode('utf-8'))
            if m_header != project.read_table(target)[0]:
                skipped.append(f'{path}: columns changed on {ref}; add them in Mod Studio first, then rerun')
                continue
            project.write_table(target, m_header, m_rows)
        else:
            project.write_strings(target, parse_catalog_lines(merged))
        applied.append(path)
    return report(project, check, applied, conflicts, skipped)


def do_tree(project: StudioProject, root: Path, check: bool) -> int:
    applied, skipped = [], []
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel.lower().startswith('global/excel/') and rel.lower().endswith('.txt'):
            if not project.has_table(rel):
                skipped.append(f'{rel}: not in the Studio project'); continue
            header, rows = parse_tsv(path.read_bytes())
            if (header, rows) != project.read_table(rel):
                project.write_table(rel, header, rows); applied.append(rel)
        elif rel.lower().startswith('local/lng/strings/') and rel.lower().endswith('.json'):
            if not project.has_catalog(rel):
                skipped.append(f'{rel}: not in the Studio project'); continue
            entries = json.loads(path.read_bytes().decode('utf-8-sig'))
            if entries != project.read_strings(rel):
                project.write_strings(rel, entries); applied.append(rel)
    return report(project, check, applied, [], skipped)


def report(project: StudioProject, check: bool, applied, conflicts, skipped) -> int:
    for line in skipped:
        print('skipped   ' + line)
    for line in conflicts:
        print('CONFLICT  ' + line)
    if check:
        for path in project.check():
            print('would write ' + str(path))
        for p in applied:
            print('changes   ' + p)
        return 1 if (applied or conflicts) else 0
    written = project.flush()
    for p in applied:
        print('merged    ' + p)
    print(f'{len(written)} Studio file(s) written, {len(conflicts)} conflict(s).')
    if conflicts:
        print('Resolve the conflict files, then apply them with --tree on a copy, or edit in Mod Studio.')
    return 1 if conflicts else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--merge', metavar='REF', help='git ref of an unconverted branch to merge from')
    mode.add_argument('--tree', type=Path, metavar='DATA_ROOT', help='native data tree to apply')
    ap.add_argument('--check', action='store_true', help='report without writing')
    args = ap.parse_args(argv)
    project = StudioProject(args.repo)
    if args.merge:
        return do_merge(args.repo, project, args.merge, args.check)
    return do_tree(project, args.tree, args.check)


if __name__ == '__main__':
    raise SystemExit(main())
