#python convert_txt_encoding.py "C:\path\to\folder" --recursive --backup

from pathlib import Path
import argparse
import shutil
import sys


UTF8_BOM = b"\xef\xbb\xbf"
UTF16_LE_BOM = b"\xff\xfe"
UTF16_BE_BOM = b"\xfe\xff"


def decode_text(raw: bytes, path: Path) -> str:
    """
    Safely decode common .txt encodings.

    Important:
    - Only decode as UTF-16 if a UTF-16 BOM is actually present.
    - Do NOT blindly try utf-16 first, because normal ASCII/UTF-8 files
      can be misread as Chinese-looking mojibake.
    """

    if raw.startswith(UTF16_LE_BOM):
        return raw[len(UTF16_LE_BOM):].decode("utf-16-le")

    if raw.startswith(UTF16_BE_BOM):
        return raw[len(UTF16_BE_BOM):].decode("utf-16-be")

    if raw.startswith(UTF8_BOM):
        return raw[len(UTF8_BOM):].decode("utf-8")

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass

    # Windows fallback for older ANSI-ish text files.
    try:
        return raw.decode("cp1252")
    except UnicodeDecodeError as e:
        raise UnicodeDecodeError(
            "unknown",
            raw,
            0,
            len(raw),
            f"Could not decode {path}: {e}"
        )


def normalize_to_crlf(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\r\n".join(text.split("\n"))


def convert_file(path: Path, backup: bool = False, dry_run: bool = False) -> bool:
    raw = path.read_bytes()

    try:
        text = decode_text(raw, path)
    except UnicodeDecodeError as e:
        print(f"ERROR: {path}: {e}")
        return False

    text = normalize_to_crlf(text)

    # UTF-8 without BOM.
    output = text.encode("utf-8")

    if dry_run:
        print(f"DRY RUN: Would convert {path}")
        return True

    if backup:
        backup_path = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup_path)
        print(f"BACKUP: {backup_path}")

    path.write_bytes(output)
    print(f"CONVERTED: {path}")
    return True


def collect_txt_files(target: Path, recursive: bool) -> list[Path]:
    if target.is_file():
        return [target] if target.suffix.lower() == ".txt" else []

    if target.is_dir():
        pattern = "**/*.txt" if recursive else "*.txt"
        return sorted(target.glob(pattern))

    return []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert .txt files to UTF-8 no BOM with CRLF line endings."
    )

    parser.add_argument("path", help="A .txt file or folder containing .txt files.")

    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Search folders recursively."
    )

    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create .bak backup files before overwriting."
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be converted without modifying files."
    )

    args = parser.parse_args()

    target = Path(args.path)
    files = collect_txt_files(target, args.recursive)

    if not files:
        print("No .txt files found.")
        return 1

    converted = 0

    for file_path in files:
        if convert_file(file_path, backup=args.backup, dry_run=args.dry_run):
            converted += 1

    print()
    print(f"Done. Converted {converted} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())