#!/usr/bin/env python3
"""
DeepL Translator for item-names.json

This script identifies missing translations in the item-names.json file and uses the DeepL API
to translate them. A translation is considered "missing" if the text for a language is identical
to the English text.

Requirements:
- Python 3.6+
- requests library
- DeepL API key (free or pro)

Usage:
    python translate_items.py [options]

Examples:
    # Run in dry-run mode (no actual translations)
    python translate_items.py --dry-run

    # Translate using API key from environment variable
    python translate_items.py

    # Translate using API key from command line
    python translate_items.py --api-key YOUR_API_KEY

    # Translate only the first 10 items (for testing)
    python translate_items.py --limit 10

    # Specify custom input and output files
    python translate_items.py --input path/to/input.json --output path/to/output.json

    # Overwrite the input file with translations
    python translate_items.py --overwrite

    # Adjust delay between API requests
    python translate_items.py --delay 0.5

    # List all available language codes
    python translate_items.py --list-languages

    # Translate only specific languages
    python translate_items.py --languages deDE,frFR,esES

    # Skip items that don't need translation (only process items with missing translations)
    python translate_items.py --skip-translated

    # Translate only the first 10 items that need translation
    python translate_items.py --skip-translated --limit 10

    # Skip items with ID below 22485 (default behavior)
    python translate_items.py

    # Process all items regardless of ID
    python translate_items.py --min-id 0
"""

import json
import time
import os
import requests
import argparse
import sys
from typing import Dict, List, Any

# Try to import tqdm for progress bar, use a simple alternative if not available
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

# DeepL API configuration
# You can set your DeepL API key as an environment variable or pass it as a command-line argument
# DeepL API URLs - will be selected based on the API key format
DEEPL_API_FREE_URL = "https://api-free.deepl.com/v2/translate"  # Free API URL
DEEPL_API_PRO_URL = "https://api.deepl.com/v2/translate"  # Pro API URL

# Language mapping from item-names.json to DeepL API
LANGUAGE_MAPPING = {
    "zhTW": "ZH",  # Chinese (traditional)
    "deDE": "DE",  # German
    "esES": "ES",  # Spanish (Spain)
    "frFR": "FR",  # French
    "itIT": "IT",  # Italian
    "koKR": "KO",  # Korean
    "plPL": "PL",  # Polish
    "esMX": "ES",  # Spanish (Mexico) - Using standard ES code for compatibility
    "jaJP": "JA",  # Japanese
    "ptBR": "PT-BR",  # Portuguese (Brazil)
    "ruRU": "RU",  # Russian
    "zhCN": "ZH",  # Chinese (simplified)
}

def translate_text(text: str, target_lang: str, api_key: str) -> str:
    """
    Translate text using DeepL API

    Args:
        text: Text to translate
        target_lang: Target language code
        api_key: DeepL API key

    Returns:
        Translated text
    """
    if not api_key:
        raise ValueError("DeepL API key not provided.")

    # Determine which API URL to use based on the API key format
    # Free tier API keys end with ":fx"
    if api_key.endswith(":fx"):
        api_url = DEEPL_API_FREE_URL
    else:
        api_url = DEEPL_API_PRO_URL

    params = {
        "auth_key": api_key,
        "text": text,
        "target_lang": target_lang,
    }

    try:
        response = requests.post(api_url, data=params)
        response.raise_for_status()  # Raise exception for HTTP errors

        result = response.json()
        if "translations" in result and len(result["translations"]) > 0:
            return result["translations"][0]["text"]
        else:
            print(f"Warning: No translation returned for '{text}' to {target_lang}")
            return text

    except requests.exceptions.RequestException as e:
        print(f"Error translating '{text}' to {target_lang}: {e}")
        # Return original text on error
        return text

def process_item(item: Dict[str, Any], api_key: str, dry_run: bool = False, delay: float = 1.0, languages: List[str] = None) -> tuple[Dict[str, Any], bool]:
    """
    Process a single item, translating any missing translations

    Args:
        item: Item dictionary from the JSON file
        api_key: DeepL API key
        dry_run: If True, don't actually translate, just identify what would be translated
        delay: Delay in seconds between API requests to avoid rate limiting
        languages: List of language codes to translate. If None, all languages will be translated.

    Returns:
        Tuple of (updated item dictionary, whether item would be updated)
    """
    english_text = item.get("enUS", "")
    if not english_text:
        return item, False  # Skip items without English text

    updated_item = item.copy()
    would_update = False

    for lang_code, deepl_code in LANGUAGE_MAPPING.items():
        # Skip languages not in the specified list
        if languages and lang_code not in languages:
            continue

        # Check if translation is missing (same as English)
        if lang_code in item and item[lang_code] == english_text:
            would_update = True
            if dry_run:
                print(f"Would translate '{english_text}' to {lang_code} ({deepl_code})")
            else:
                print(f"Translating '{english_text}' to {lang_code} ({deepl_code})...")
                translated_text = translate_text(english_text, deepl_code, api_key)
                updated_item[lang_code] = translated_text
                # Sleep to avoid hitting API rate limits
                time.sleep(delay)

    return updated_item, would_update

def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description="Translate missing entries in item-names.json using DeepL API")

    parser.add_argument("--input", "-i", 
                        default="data/local/lng/strings/item-names.json",
                        help="Path to the input JSON file (default: data/local/lng/strings/item-names.json)")

    parser.add_argument("--output", "-o", 
                        default="data/local/lng/strings/item-names-translated.json",
                        help="Path to the output JSON file (default: data/local/lng/strings/item-names-translated.json)")

    parser.add_argument("--api-key", "-k",
                        default=os.environ.get("DEEPL_API_KEY"),
                        help="DeepL API key (default: value of DEEPL_API_KEY environment variable)")

    parser.add_argument("--dry-run", "-d",
                        action="store_true",
                        help="Run in dry-run mode (don't actually translate)")

    parser.add_argument("--limit", "-l",
                        type=int,
                        help="Limit the number of items to process (for testing)")

    parser.add_argument("--delay", 
                        type=float,
                        default=0.1,
                        help="Delay in seconds between API requests (default: 0.1)")

    parser.add_argument("--overwrite", 
                        action="store_true",
                        help="Overwrite the input file instead of creating a new output file")

    parser.add_argument("--languages", 
                        default=None,
                        help="Comma-separated list of language codes to translate (e.g., 'deDE,frFR,esES'). If not specified, all languages will be translated.")

    parser.add_argument("--list-languages", 
                        action="store_true",
                        help="List all available language codes and exit")

    parser.add_argument("--skip-translated", "-s",
                        action="store_true",
                        help="Skip items that don't need translation (only process items with missing translations)")

    parser.add_argument("--min-id",
                        type=int,
                        default=22485,
                        help="Skip items with ID below this value (default: 22485)")

    return parser.parse_args()

def main():
    """Main function to process the item-names.json file"""
    # Parse command-line arguments
    args = parse_arguments()

    # If --list-languages is specified, print available languages and exit
    if args.list_languages:
        print("Available language codes:")
        for lang_code, deepl_code in LANGUAGE_MAPPING.items():
            print(f"  {lang_code}: {deepl_code}")
        return

    # Parse languages if specified
    languages = None
    if args.languages:
        languages = [lang.strip() for lang in args.languages.split(',')]
        # Validate languages
        invalid_langs = [lang for lang in languages if lang not in LANGUAGE_MAPPING]
        if invalid_langs:
            print(f"Error: Invalid language code(s): {', '.join(invalid_langs)}")
            print("Use --list-languages to see available language codes.")
            return
        print(f"Translating only the following languages: {', '.join(languages)}")

    # Set file paths
    input_file = args.input
    output_file = args.input if args.overwrite else args.output

    # Check if API key is set
    if not args.api_key and not args.dry_run:
        print("Warning: DeepL API key not provided. Please set the DEEPL_API_KEY environment variable or use --api-key.")
        print("Continuing in dry-run mode (no actual translations will be made).")
        dry_run = True
    else:
        dry_run = args.dry_run

    # Read the JSON file
    print(f"Reading {input_file}...")
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            items = json.load(f)
    except Exception as e:
        print(f"Error reading {input_file}: {e}")
        return

    print(f"Found {len(items)} items in the file.")

    # Process items
    total_translations = 0

    # Create a map of item IDs to their indices in the original list
    # This will help us update items in-place
    item_indices = {item.get("id"): i for i, item in enumerate(items) if "id" in item}

    # Filter items based on ID and translation status
    needs_translation = []
    for item in items:
        # Skip items with ID below the minimum
        if "id" in item and item["id"] < args.min_id:
            continue

        english_text = item.get("enUS", "")
        if not english_text:
            continue

        # If skip-translated is enabled, only include items that need translation
        if args.skip_translated:
            for lang_code in LANGUAGE_MAPPING:
                if lang_code in item and item[lang_code] == english_text:
                    needs_translation.append(item)
                    break
        else:
            needs_translation.append(item)

    print(f"Found {len(needs_translation)} items with ID > {args.min_id}" +
          (" that need translation" if args.skip_translated else "") + ".")

    # Apply limit if specified
    items_to_process = needs_translation[:args.limit] if args.limit else needs_translation

    total_items = len(items_to_process)

    # Create progress bar
    if TQDM_AVAILABLE:
        # Use tqdm if available
        progress_bar = tqdm(total=total_items, desc="Processing items", unit="item")

        for item in items_to_process:
            updated_item, would_update = process_item(item, args.api_key, dry_run, args.delay, languages)

            # Update the item in-place in the original list
            if not dry_run and would_update and "id" in item and item["id"] in item_indices:
                items[item_indices[item["id"]]] = updated_item

            # Count translations
            if would_update:
                total_translations += 1

            progress_bar.update(1)

        progress_bar.close()
    else:
        # Simple progress indicator as fallback
        print(f"Processing {total_items} items...")
        for i, item in enumerate(items_to_process):
            if i % 100 == 0 or i == total_items - 1:
                progress = (i + 1) / total_items * 100
                sys.stdout.write(f"\rProgress: {progress:.1f}% ({i+1}/{total_items})")
                sys.stdout.flush()

            updated_item, would_update = process_item(item, args.api_key, dry_run, args.delay, languages)

            # Update the item in-place in the original list
            if not dry_run and would_update and "id" in item and item["id"] in item_indices:
                items[item_indices[item["id"]]] = updated_item

            # Count translations
            if would_update:
                total_translations += 1

        print()  # New line after progress indicator

    # Write the updated JSON file
    if not dry_run and total_translations > 0:
        print(f"Writing {total_translations} updated translations to {output_file}...")
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(items, f, ensure_ascii=False, indent=4)
            print(f"Successfully wrote {output_file}")
        except Exception as e:
            print(f"Error writing {output_file}: {e}")
    else:
        print(f"Dry run completed. Would have updated {total_translations} items.")

if __name__ == "__main__":
    main()
