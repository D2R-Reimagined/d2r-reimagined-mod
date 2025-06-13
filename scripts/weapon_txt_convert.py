# Converts weapons.txt into wiki useable html table in case we ever add/change bases again.

import os
import csv

input_file = "data/global/excel/weapons.txt"
output_file = "scripts/output_wep.html"

type_display_map = {
    "axe": "Axe",
    "wand": "Wand",
    "club": "Club",
    "scep": "Scepter",
    "mace": "Mace",
    "hamm": "Hammer",
    "swor": "Sword",
    "knif": "Dagger",
    "tkni": "Throwing Dagger",
    "taxe": "Throwing Axe",
    "jave": "Javelin",
    "spea": "Spear",
    "pole": "Polearm",
    "staf": "Staff",
    "bow": "Bow",
    "xbow": "Crossbow",
    "tpot": "Throwing Potion",
    "h2h": "Claw",
    "h2h2": "Claw (Mods)",
    "orb": "Sorceress Orb",
    "abow": "Amazon Bow",
    "aspe": "Amazon Spear",
    "ajav": "Amazon Javelin"
}

fields = [
    "name", "type", "type2",
    ("mindam", "maxdam"),
    ("2handmindam", "2handmaxdam"),
    ("minmisdam", "maxmisdam"),
    "speed", "reqstr", "reqdex", "levelreq", "gemsockets"
]

headers = [
    "Name", "Type", "Type2", "Dmg", "2H Dmg", "Msl Dmg",
    "Speed", "R.Str", "R.Dex", "Lvl Req", "Max Sockets"
]

type_groups = [
    (["axe"], "Axes"),
    (["swor"], "Swords"),
    (["club", "mace"], "Maces"),
    (["scep"], "Scepters"),
    (["hamm"], "Hammers"),
    (["knif"], "Daggers"),
    (["wand"], "Wands"),
    (["h2h", "h2h2"], "Claws"),
    (["orb"], "Orbs"),
    (["tkni", "taxe"], "Throwing Weapons"),
    (["jave", "ajav"], "Javelins"),
    (["spea", "aspe"], "Spears"),
    (["pole"], "Polearms"),
    (["staf"], "Staves"),
    (["bow", "xbow", "abow"], "Bows"),
]

def merge_fields(row, pair):
    a, b = pair
    av = row.get(a, "")
    bv = row.get(b, "")
    if (not av or av.strip() == "0") and (not bv or bv.strip() == "0"):
        return ""
    if not av or av.strip() == "0":
        return bv if bv and bv.strip() != "0" else ""
    if not bv or bv.strip() == "0":
        return av if av and av.strip() != "0" else ""
    return f"{av}-{bv}"

def process_type2(val):
    if "1wep" in val:
        return ""
    elif "slam" in val:
        return "Slam"
    else:
        return val

def get_type_display(type_code):
    return type_display_map.get(type_code, type_code)

def blank_if_zero(val):
    return "" if not val or val.strip() == "0" else val

def filter_rows(rows, type_codes):
    return [row for row in rows if row.get("type") in type_codes]

def get_sort_key(row, type_codes):
    try:
        return type_codes.index(row.get("type"))
    except ValueError:
        return len(type_codes)

with open(input_file, encoding="utf-8") as f:
    reader = csv.DictReader(f, delimiter="\t")
    names_to_ignore = {
        "Khalim's Will",
        "Khalim's Flail",
        "Staff of Kings",
        "Horadric Staff",
        "Horadric Malus",
        "Hellforge Hammer",
        "Wirt's Leg",
        "Decoy Gidbinn",
        "The Gidbinn"
    }
    all_rows = [
        row for row in reader
        if row["name"].strip()
        and row["name"].strip().lower() != "expansion"
        and row.get("type") != "tpot"
        and row["name"].strip() not in names_to_ignore
    ]

# Find all handled type codes
handled_type_codes = []
for group in type_groups:
    handled_type_codes.extend(group[0])

def partition_by_code(rows):
    norm, exc, elite, other = [], [], [], []
    for row in rows:
        if row.get("code") == row.get("normcode"):
            norm.append(row)
        elif row.get("code") == row.get("ubercode"):
            exc.append(row)
        elif row.get("code") == row.get("ultracode"):
            elite.append(row)
        else:
            other.append(row)
    return norm, exc, elite, other

def get_active_columns(data):
    # Scan all rows and find which columns are not empty for this data set
    active = []
    for idx, field in enumerate(fields):
        found = False
        for row in data:
            if isinstance(field, tuple):
                val = merge_fields(row, field)
            elif field == "type2":
                val = process_type2(row.get("type2", ""))
            elif field == "type":
                val = get_type_display(row.get("type", ""))
            else:
                val = blank_if_zero(row.get(field, ""))
            if val != "":
                found = True
                break
        if found:
            active.append(idx)
    return active

def build_table(title, data, type_codes):
    if not data:
        return ""
    data.sort(key=lambda row: get_sort_key(row, type_codes))
    active_columns = get_active_columns(data)
    html = []
    html.append(f"<h3>{title}</h3>")
    html.append('<figure class="table">\n  <table>')
    # Header row
    html.append("    <thead>\n      <tr>")
    for idx in active_columns:
        html.append(f'        <th><mark class="pen-green">{headers[idx]}</mark></th>')
    html.append("      </tr>\n    </thead>")
    # Table body
    html.append("    <tbody>")
    for row in data:
        html.append("      <tr>")
        for idx in active_columns:
            field = fields[idx]
            if isinstance(field, tuple):
                cell = merge_fields(row, field)
            elif field == "type2":
                cell = process_type2(row.get("type2", ""))
            elif field == "type":
                cell = get_type_display(row.get("type", ""))
            else:
                cell = blank_if_zero(row.get(field, ""))
            # Use <th> for first column (name), <td> otherwise
            tag = "th" if idx == 0 else "td"
            html.append(f"        <{tag}>{cell if cell else '&nbsp;'}</{tag}>")
        html.append("      </tr>")
    html.append("    </tbody>")
    html.append("  </table>\n</figure>")
    return "\n".join(html)

full_html = [
    "<html><head><meta charset='utf-8'><title>D2 Items Table</title></head><body>"
]

for type_codes, group_title in type_groups:
    group_rows = filter_rows(all_rows, type_codes)
    n, e, l, o = partition_by_code(group_rows)
    full_html.append(f"<h2>{group_title}</h2>")
    full_html.append(build_table("Normal Base", n, type_codes))
    full_html.append(build_table("Exceptional Base", e, type_codes))
    full_html.append(build_table("Elite Base", l, type_codes))
    full_html.append(build_table("Other Items", o, type_codes))

# Anything not handled is "Other Types"
other_rows = [row for row in all_rows if row.get("type") not in handled_type_codes]
if other_rows:
    n, e, l, o = partition_by_code(other_rows)
    full_html.append("<h2>Other Types</h2>")
    full_html.append(build_table("Normal Base", n, []))
    full_html.append(build_table("Exceptional Base", e, []))
    full_html.append(build_table("Elite Base", l, []))
    full_html.append(build_table("Other Items", o, []))

full_html.append("</body></html>")

with open(output_file, "w", encoding="utf-8") as f:
    f.write("\n".join(full_html))

print(f"Done. Output saved to: {os.path.abspath(output_file)}")
