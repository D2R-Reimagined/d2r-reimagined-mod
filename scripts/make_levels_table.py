#!/usr/bin/env python3
"""
Extract specific columns from a tab-separated Diablo II levels file
and output an HTML table.

Columns kept: Name, *StringName, MonLvlEx, MonLvlEx(N), MonLvlEx(H)
"""

import argparse
import csv
import sys
from html import escape
from pathlib import Path

NEEDED_COLS = ["Name", "*StringName", "MonLvlEx", "MonLvlEx(N)", "MonLvlEx(H)"]

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Level Table</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {{
    --bg: #0f1115; --fg: #e6e6e6; --muted: #9aa0a6; --border: #2a2f3a;
  }}
  body {{ background: var(--bg); color: var(--fg); font: 14px/1.5 system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 0; padding: 24px; }}
  h1 {{ font-size: 18px; margin: 0 0 12px; color: var(--fg); }}
  .wrap {{ overflow-x: auto; border: 1px solid var(--border); border-radius: 10px; }}
  table {{ border-collapse: collapse; width: 100%; min-width: 640px; }}
  th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }}
  thead th {{ position: sticky; top: 0; background: #131722; z-index: 1; }}
  tbody tr:nth-child(even) {{ background: #12161f; }}
  .muted {{ color: var(--muted); }}
</style>
</head>
<body>
<h1>Levels (selected columns)</h1>
<div class="wrap">
<table>
<thead>
<tr>{thead}</tr>
</thead>
<tbody>
{tbody}
</tbody>
</table>
</div>
<p class="muted">Generated from: {source}</p>
</body>
</html>
"""

def main():
    ap = argparse.ArgumentParser(description="Make an HTML table from a TSV, keeping selected columns.")
    ap.add_argument("input", help="Path to the tab-separated input file (e.g., Levels.txt)")
    ap.add_argument("-o", "--output", default="levels_selected.html", help="Output HTML file (default: levels_selected.html)")
    args = ap.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"Error: Input file not found: {in_path}", file=sys.stderr)
        sys.exit(1)

    # Read with BOM-safe UTF-8 and tab delimiter
    with in_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")

        # Validate columns
        headers = reader.fieldnames or []
        missing = [c for c in NEEDED_COLS if c not in headers]
        if missing:
            print("Warning: missing expected column(s): " + ", ".join(missing), file=sys.stderr)

        # Build table rows
        rows_html = []
        for row in reader:
            cells = []
            for col in NEEDED_COLS:
                val = row.get(col, "")
                # Convert None to empty string & escape HTML
                cells.append(f"<td>{escape(val if val is not None else '')}</td>")
            rows_html.append("<tr>" + "".join(cells) + "</tr>")

    # Build header row
    thead = "".join(f"<th>{escape(col)}</th>" for col in NEEDED_COLS)

    html = HTML_TEMPLATE.format(
        thead=thead,
        tbody="\n".join(rows_html),
        source=escape(str(in_path))
    )

    out_path = Path(args.output)
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path}")

if __name__ == "__main__":
    main()

# Stick levels.txt in this folder, make a quick and easy html table to import into wiki for area levels with the below console prompt in VSC or Rider
# python make_levels_table.py levels.txt -o levels_selected.html