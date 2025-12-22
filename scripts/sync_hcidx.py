#!/usr/bin/env python3
from pathlib import Path
import shutil

MONSTATS = Path("data/global/excel/monstats.txt")
MONSTATS2 = Path("data/global/excel/monstats2.txt")

def split_tsv_line(line: str) -> list[str]:
    # Do NOT use csv — Diablo TSVs are simple tab splits
    return line.rstrip("\n").split("\t")

def join_tsv_line(cols: list[str]) -> str:
    return "\t".join(cols) + "\n"

def main():
    ms_lines = MONSTATS.read_text(encoding="utf-8").splitlines(keepends=True)
    ms2_lines = MONSTATS2.read_text(encoding="utf-8").splitlines(keepends=True)

    ms_header = split_tsv_line(ms_lines[0])
    ms2_header = split_tsv_line(ms2_lines[0])

    ms_id_i = ms_header.index("Id")
    ms_hc_i = ms_header.index("*hcIdx")
    ms2_id_i = ms2_header.index("Id")
    ms2_hc_i = ms2_header.index("*hcIdx")

    # Build Id → *hcIdx map (RAW TEXT)
    id_to_hc = {}
    for line in ms_lines[1:]:
        cols = split_tsv_line(line)
        if cols[ms_id_i]:
            id_to_hc[cols[ms_id_i]] = cols[ms_hc_i]

    updated = 0

    out_lines = [ms2_lines[0]]
    for line in ms2_lines[1:]:
        cols = split_tsv_line(line)

        if cols[ms2_id_i] in id_to_hc:
            old = cols[ms2_hc_i]
            new = id_to_hc[cols[ms2_id_i]]
            if old != new:
                cols[ms2_hc_i] = new
                updated += 1

        out_lines.append(join_tsv_line(cols))

    # Backup
    backup = MONSTATS2.with_suffix(".txt.bak")
    shutil.copy2(MONSTATS2, backup)

    MONSTATS2.write_text("".join(out_lines), encoding="utf-8")

    print(f"Updated rows: {updated}")
    print(f"Backup written: {backup}")

if __name__ == "__main__":
    main()
