"""Read and write Mod Studio source tables as the native TXT/JSON shapes scripts expect.

Mod Studio keeps the mod's excel tables in source/tables/<name>.json and the string
catalogs in source/strings/<name>.json. Scripts written for the native files (the maps
generator, its tests) address them by their game path, e.g. "global/excel/levels.txt" or
"local/lng/strings/levels.json". This module maps those paths onto the Studio files.

Tables
  read_table(target)          -> (header, rows)     rows are lists of cells, game order
  write_table(target, header, rows)                 staged until flush()
  native_bytes(target)        -> the TXT bytes Studio's build will emit

  Row identity: every Studio record has a sourceId (profile overrides refer to rows by it).
  A written row that equals a row already in the file keeps that row's sourceId, so hand
  rows and unchanged generated rows keep their ids across regenerations. Only new or changed
  rows get a fresh id, derived from the row's content so the same run gives the same ids.

  Banks: base/ and top-level copies of a table share one Studio file while their content is
  identical. flush() regroups the targets of a table after writes, splitting them into
  "<stem>" (holds the top-level target) and "<stem>-base" when they diverge, and merging
  them back when they converge.

Catalogs
  read_strings(target)        -> list of {"id", "Key", locale...} dicts, like the game file
  write_strings(target, entries)                    staged until flush()

flush() writes every staged change. check() reports, without writing, which Studio files
the staged changes would alter. Files are written the way Mod Studio writes them
(4-space indent, relaxed escaping) with LF line endings, which is what git stores for
source/**/*.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from pathlib import Path

__all__ = ["StudioProject", "dumps"]


# --------------------------------------------------------------------------- json
def _escape(s: str) -> str:
    out = []
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == '\\':
            out.append('\\\\')
        elif ch == '\n':
            out.append('\\n')
        elif ch == '\r':
            out.append('\\r')
        elif ch == '\t':
            out.append('\\t')
        elif ch == '\b':
            out.append('\\b')
        elif ch == '\f':
            out.append('\\f')
        elif o > 0xFFFF:
            o -= 0x10000
            out.append('\\u%04X\\u%04X' % (0xD800 + (o >> 10), 0xDC00 + (o & 0x3FF)))
        elif o == 0x7F or (o != 0x20 and unicodedata.category(ch) in _ESCAPED_CATEGORIES):
            out.append('\\u%04X' % o)
        else:
            out.append(ch)
    return '"' + ''.join(out) + '"'


# System.Text.Json's relaxed encoder (Mod Studio's) escapes controls, surrogates, private
# use, unassigned code points and every separator but the plain space. Format characters
# (U+200C in the zhCN item names) stay raw. Checked against every Studio file of the mod.
_ESCAPED_CATEGORIES = {'Cc', 'Cs', 'Co', 'Cn', 'Zs', 'Zl', 'Zp'}


def _dump(node, indent: int, out: list) -> None:
    pad = ' ' * indent
    if isinstance(node, dict):
        if not node:
            out.append('{}')
            return
        out.append('{\n')
        items = list(node.items())
        for i, (k, v) in enumerate(items):
            out.append(pad + '    ' + _escape(k) + ': ')
            _dump(v, indent + 4, out)
            out.append(',\n' if i < len(items) - 1 else '\n')
        out.append(pad + '}')
    elif isinstance(node, list):
        if not node:
            out.append('[]')
            return
        out.append('[\n')
        for i, v in enumerate(node):
            out.append(pad + '    ')
            _dump(v, indent + 4, out)
            out.append(',\n' if i < len(node) - 1 else '\n')
        out.append(pad + ']')
    elif isinstance(node, str):
        out.append(_escape(node))
    elif node is True:
        out.append('true')
    elif node is False:
        out.append('false')
    elif node is None:
        out.append('null')
    elif isinstance(node, int):
        out.append(str(node))
    else:
        raise TypeError(f'unsupported JSON value {node!r}')


def dumps(node) -> str:
    """Mod Studio's file format: indented JSON, LF, final newline."""
    out: list = []
    _dump(node, 0, out)
    return ''.join(out) + '\n'


def _load(path: Path):
    return json.loads(path.read_bytes().decode('utf-8-sig'))


# --------------------------------------------------------------------------- tables
_ORIGINAL = re.compile(r'^row-[0-9]{5}$')


def _digest(*parts: str) -> str:
    h = hashlib.sha1()
    for p in parts:
        h.update(p.encode('utf-8'))
        h.update(b'\0')
    return h.hexdigest()[:8]


class _TableFile:
    def __init__(self, path: Path):
        self.path = path
        self.doc = _load(path)
        self.schema = self.doc['schema']
        self.keys = [c['key'] for c in self.schema['columns']]
        self.header = [c['header'] for c in self.schema['columns']]

    @property
    def name(self) -> str:
        return self.schema['name']

    @property
    def targets(self) -> list[str]:
        return list(self.schema['targets'])

    def rows(self) -> list[list[str]]:
        """Fresh lists each call (callers edit them); decoded once per loaded file."""
        if not hasattr(self, '_rows'):
            keys = self.keys
            self._rows = []
            for r in self.doc['records']:
                f = r['fields']
                n = r.get('columnCount', len(keys))
                self._rows.append(tuple(f.get(k, '') for k in keys[:n]))
        return [list(r) for r in self._rows]


class StudioProject:
    def __init__(self, root: os.PathLike | str):
        self.root = Path(root)
        self.tables_dir = self.root / 'source' / 'tables'
        self.strings_dir = self.root / 'source' / 'strings'
        if not self.tables_dir.is_dir():
            raise FileNotFoundError(f'{self.root} has no source/tables (not a Mod Studio project)')
        self._tables: dict[str, _TableFile] = {}       # target (lower) -> table file
        for path in sorted(self.tables_dir.glob('*.json')):
            t = _TableFile(path)
            for target in t.targets:
                key = target.lower()
                if key in self._tables:
                    raise ValueError(f'{target} is claimed by {self._tables[key].path.name} and {path.name}')
                self._tables[key] = t
        self._catalogs: dict[str, Path] = {}
        if self.strings_dir.is_dir():
            for path in sorted(self.strings_dir.glob('*.json')):
                self._catalogs[_load(path)['schema']['target'].lower()] = path
        self._staged_tables: dict[str, tuple[list[str], list[list[str]]]] = {}
        self._staged_strings: dict[str, list[dict]] = {}

    # -- paths -----------------------------------------------------------------
    @staticmethod
    def target_of(path: os.PathLike | str) -> str:
        """'C:/mod/data/global/excel/base/levels.txt' -> 'global/excel/base/levels.txt'."""
        p = str(path).replace('\\', '/')
        for anchor in ('global/excel/', 'local/lng/strings/'):
            i = p.lower().rfind('/' + anchor)
            if i >= 0:
                return p[i + 1:]
            if p.lower().startswith(anchor):
                return p
        raise ValueError(f'{path} is not a table or string catalog path')

    def has_table(self, target: str) -> bool:
        return target.lower() in self._tables

    def table_targets(self) -> list[str]:
        return sorted({t for f in self._tables.values() for t in f.targets})

    def has_catalog(self, target: str) -> bool:
        return target.lower() in self._catalogs

    def catalog_targets(self) -> list[str]:
        return sorted(_load(p)['schema']['target'] for p in self._catalogs.values())

    def catalog_file(self, target: str) -> Path:
        """The source/strings file holding this catalog."""
        return self._catalogs[target.lower()]

    # -- tables ----------------------------------------------------------------
    def read_table(self, target: str) -> tuple[list[str], list[list[str]]]:
        key = target.lower()
        if key in self._staged_tables:
            header, rows = self._staged_tables[key]
            return list(header), [list(r) for r in rows]
        t = self._tables[key]
        return list(t.header), t.rows()

    def table_name(self, target: str) -> str:
        """The Studio table holding this target (profile override rules name it)."""
        return self._tables[target.lower()].name

    def read_records(self, target: str) -> list[tuple[str, list[str]]]:
        """(sourceId, cells) per row as saved; staged writes are not included."""
        t = self._tables[target.lower()]
        return [(r['sourceId'], cells) for r, cells in zip(t.doc['records'], t.rows())]

    def write_table(self, target: str, header: list[str], rows: list[list[str]]) -> None:
        key = target.lower()
        t = self._tables[key]
        if list(header) != t.header:
            raise ValueError(f'{target}: the header changed; change columns in Mod Studio')
        for i, r in enumerate(rows):
            if len(r) > len(header):
                raise ValueError(f'{target}: row {i} has {len(r)} cells, header has {len(header)}')
            for c in r:
                if '\t' in c or '\r' in c or '\n' in c:
                    raise ValueError(f'{target}: row {i} has a tab or newline in a cell')
        self._staged_tables[key] = (list(header), [list(r) for r in rows])

    def native_bytes(self, target: str) -> bytes:
        """The TXT bytes Mod Studio's build emits for this target (current or staged)."""
        key = target.lower()
        t = self._tables[key]
        header, rows = self.read_table(target)
        nl = t.schema.get('newline', '\n')
        lines = ['\t'.join(header)] + ['\t'.join(r) for r in rows]
        text = ('\ufeff' if t.schema.get('bom') else '') + nl.join(lines) + (nl if t.schema.get('finalNewline') else '')
        enc = 'utf-8' if t.schema.get('encoding', 'utf-8') in ('utf-8', 'utf8') else t.schema['encoding']
        return text.encode(enc)

    # -- strings ---------------------------------------------------------------
    def read_strings(self, target: str) -> list[dict]:
        key = target.lower()
        if key in self._staged_strings:
            return json.loads(json.dumps(self._staged_strings[key]))
        doc = _load(self._catalogs[key])
        locales = doc['schema']['locales']
        out = []
        for r in doc['records']:
            entry = {'id': r['id'], 'Key': r['Key']}
            nulls = set(r.get('nullTranslations', []))
            tr = r.get('translations', {})
            for loc in locales:
                if loc in nulls:
                    entry[loc] = None
                elif loc in tr:
                    entry[loc] = tr[loc]
            out.append(entry)
        return out

    def write_strings(self, target: str, entries: list[dict]) -> None:
        key = target.lower()
        locales = _load(self._catalogs[key])['schema']['locales']
        for i, e in enumerate(entries):
            if not isinstance(e.get('id'), int) or not isinstance(e.get('Key'), str):
                raise ValueError(f'{target}: entry {i} needs an integer id and a Key')
            extra = [k for k in e if k not in ('id', 'Key') and k not in locales]
            if extra:
                raise ValueError(f'{target}: entry {i} has locales the catalog lacks: {extra}')
        self._staged_strings[key] = json.loads(json.dumps(entries))

    # -- writing ---------------------------------------------------------------
    def _planned(self) -> tuple[dict[Path, str], list[Path]]:
        """Studio files to write (path -> text) and to delete."""
        writes: dict[Path, str] = {}
        deletes: list[Path] = []
        files = {id(t): t for t in self._tables.values()}
        touched = {id(self._tables[k]) for k in self._staged_tables}
        # Gather every bank of each touched stem, so split/merge sees them all.
        stems: dict[str, list[_TableFile]] = {}
        for t in files.values():
            stems.setdefault(_stem(t.name), []).append(t)
        for stem, group in stems.items():
            if not any(id(t) in touched for t in group):
                continue
            # content per target, old records available for id reuse
            content: dict[str, tuple[list[str], list[list[str]]]] = {}
            old_records: list[dict] = []
            schema = None
            for t in group:
                old_records.extend(t.doc['records'])
                schema = schema or t.schema
                for target in t.targets:
                    content[target] = self.read_table(target)
            # regroup targets by identical content; the group with a top-level target is <stem>
            buckets: dict[str, list[str]] = {}
            for target, (header, rows) in content.items():
                sig = _digest('\n'.join('\t'.join(r) for r in [header] + rows))
                buckets.setdefault(sig, []).append(target)
            new_files: dict[str, tuple[list[str], tuple]] = {}
            for targets in buckets.values():
                targets = sorted(targets, key=lambda s: (s.lower().count('/'), s.lower()), reverse=True)
                top = any('/base/' not in s.lower() for s in targets)
                name = stem if top else stem + '-base'
                if name in new_files:
                    raise ValueError(f'{stem}: two diverging top-level banks')
                new_files[name] = (targets, content[targets[0]])
            existing = {t.path.name: t for t in group}
            for name, (targets, (header, rows)) in new_files.items():
                path = self.tables_dir / (name + '.json')
                base_file = existing.get(path.name) or group[0]
                # Reuse ids from the file this one continues first, so each bank keeps its own ids.
                own = [t for t in group if t is base_file] + [t for t in group if t is not base_file]
                candidates = [r for t in own for r in t.doc['records']]
                doc = _rebuild_table(base_file, name, _order_targets(base_file, targets), rows, candidates)
                text = dumps(doc)
                if not path.exists() or path.read_bytes().decode('utf-8-sig').replace('\r\n', '\n') != text:
                    writes[path] = text
            for t in group:
                if t.path.stem not in new_files:
                    deletes.append(t.path)
        for key, entries in self._staged_strings.items():
            path = self._catalogs[key]
            text = dumps(_rebuild_catalog(_load(path), entries))
            if path.read_bytes().decode('utf-8-sig').replace('\r\n', '\n') != text:
                writes[path] = text
        return writes, deletes

    def check(self) -> list[Path]:
        """Studio files the staged changes would write or delete (nothing is written)."""
        writes, deletes = self._planned()
        return sorted(list(writes) + deletes)

    def flush(self) -> list[Path]:
        writes, deletes = self._planned()
        for path, text in writes.items():
            tmp = path.with_suffix('.json.tmp')
            tmp.write_bytes(text.encode('utf-8'))
            os.replace(tmp, path)
        for path in deletes:
            path.unlink()
        changed = sorted(list(writes) + deletes)
        # reload so later reads see the written state
        staged_s = self._staged_strings
        self.__init__(self.root)
        del staged_s
        return changed


def _stem(name: str) -> str:
    return name[:-5] if name.endswith('-base') else name


def _order_targets(base_file: _TableFile, targets: list[str]) -> list[str]:
    """The file's own order when its targets are unchanged, otherwise ordinal order (as Studio's import lists them)."""
    if sorted(base_file.targets) == sorted(targets):
        return base_file.targets
    return sorted(targets)


def _rebuild_table(template: _TableFile, name: str, targets: list[str], rows: list[list[str]], old_records: list[dict]) -> dict:
    keys = template.keys
    by_cells: dict[tuple, list[str]] = {}
    for r in old_records:
        n = r.get('columnCount', len(keys))
        cells = tuple(r['fields'].get(k, '') for k in keys[:n])
        by_cells.setdefault(cells, [])
        if r['sourceId'] not in by_cells[cells]:
            by_cells[cells].append(r['sourceId'])
    used: set[str] = set()
    records = []
    occurrences: dict[tuple, int] = {}
    for i, row in enumerate(rows):
        cells = tuple(row)
        sid = next((s for s in by_cells.get(cells, []) if s not in used), None)
        if sid is None:
            k = occurrences.get(cells, 0)
            occurrences[cells] = k + 1
            sid = 'gen-' + _digest(name, '\t'.join(row), str(k))
            while sid in used:
                k += 1
                sid = 'gen-' + _digest(name, '\t'.join(row), str(k))
        used.add(sid)
        fields = {k: v for k, v in zip(keys, row) if v != ''}
        records.append({'sourceId': sid, 'columnCount': len(row), 'fields': fields})
    schema = dict(template.schema)
    schema['name'] = name
    schema['targets'] = targets
    doc = dict(template.doc)
    doc['schema'] = schema
    doc['records'] = records
    return doc


def _rebuild_catalog(doc: dict, entries: list[dict]) -> dict:
    locales = doc['schema']['locales']
    old: dict[tuple, list[dict]] = {}
    for r in doc['records']:
        old.setdefault((r['id'], r['Key']), []).append(r)
    records = []
    for e in entries:
        prev_list = old.get((e['id'], e['Key']))
        prev = prev_list.pop(0) if prev_list else None
        translations = {}
        nulls = []
        for loc in locales:
            if loc not in e:
                continue
            if e[loc] is None:
                nulls.append(loc)
            else:
                translations[loc] = e[loc]
        rec: dict = {}
        if prev is not None and 'sourceId' in prev:
            rec['sourceId'] = prev['sourceId']
        elif prev is None:
            rec['sourceId'] = 'str-' + _digest(doc['schema']['target'], str(e['id']), e['Key'])
        rec['id'] = e['id']
        rec['Key'] = e['Key']
        rec['translations'] = translations
        if nulls:
            rec['nullTranslations'] = nulls
        # compact (standard-mode) translations only survive while the full text is unchanged
        if prev is not None:
            for extra in ('standardTranslations', 'standardReviewedAgainst'):
                if extra in prev and all(prev.get('translations', {}).get(l) == translations.get(l) for l in prev[extra]):
                    rec[extra] = prev[extra]
        records.append(rec)
    out = dict(doc)
    out['records'] = records
    return out
