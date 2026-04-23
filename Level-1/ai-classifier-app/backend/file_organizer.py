# file_organizer.py — Organize Files by Classification Category
# ================================================================
# Classifies files into persistent category folders under output/.
# No sessions — files accumulate over time with smart dedup logic:
#
# - File not in any category → add to its category folder
# - File in same category, identical content → skip
# - File in same category, content changed → overwrite
# - File in different category → remove old, add to new
#
# Result structure:
#   output/
#     ├── Complaint/
#     │   ├── angry_customer.pdf
#     │   └── broken_product.txt
#     ├── Praise/
#     │   └── great_service.docx
#     └── results.json   (cumulative summary)

import hashlib
import json
import os
import shutil
import zipfile
from io import BytesIO

from models import FileClassificationResponse

# Base directory for organized output
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

VALID_CATEGORIES = {"Complaint", "Suggestion", "Question", "Praise"}


def _file_hash(content: bytes) -> str:
    """Compute SHA-256 hash of file content for dedup comparison."""
    return hashlib.sha256(content).hexdigest()


def _find_existing_file(filename: str) -> tuple[str | None, str | None]:
    """
    Search all category folders for a file with the given name.
    Returns (category, full_path) if found, else (None, None).
    """
    for category in VALID_CATEGORIES:
        path = os.path.join(OUTPUT_DIR, category, filename)
        if os.path.exists(path):
            return category, path
    return None, None


def organize_file(
    filename: str,
    content: bytes,
    category: str,
) -> str:
    """
    Save a file into the appropriate category folder with smart dedup.

    Logic:
    1. File doesn't exist anywhere → add to category folder
    2. File exists in same category, same content → skip (no-op)
    3. File exists in same category, different content → overwrite
    4. File exists in different category → delete old, write to new

    Returns a status string: "added", "unchanged", "updated", "moved"
    """
    if category not in VALID_CATEGORIES:
        category = "Uncategorized"

    # Check if file already exists somewhere
    existing_cat, existing_path = _find_existing_file(filename)

    target_dir = os.path.join(OUTPUT_DIR, category)
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, filename)

    if existing_cat is None:
        # Case 1: New file — just add
        with open(target_path, "wb") as f:
            f.write(content)
        return "added"

    if existing_cat == category:
        # Same category — check content
        with open(existing_path, "rb") as f:  # type: ignore[arg-type]
            old_hash = _file_hash(f.read())
        new_hash = _file_hash(content)

        if old_hash == new_hash:
            # Case 2: Identical content — skip
            return "unchanged"

        # Case 3: Content changed — overwrite
        with open(existing_path, "wb") as f:  # type: ignore[arg-type]
            f.write(content)
        return "updated"

    # Case 4: Different category — move
    os.remove(existing_path)  # type: ignore[arg-type]

    # Clean up empty old category folder
    old_dir = os.path.join(OUTPUT_DIR, existing_cat)
    if os.path.isdir(old_dir) and not os.listdir(old_dir):
        os.rmdir(old_dir)

    with open(target_path, "wb") as f:
        f.write(content)
    return "moved"


def save_results_json(
    results: list[FileClassificationResponse],
) -> None:
    """Save/update the cumulative results.json in the output root."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    summary = []
    for r in results:
        summary.append(
            {
                "filename": r.filename,
                "category": r.classification.category,
                "sentiment": r.classification.sentiment,
                "confidence": r.classification.confidence,
                "summary": r.classification.summary,
            }
        )

    results_path = os.path.join(OUTPUT_DIR, "results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def create_results_zip() -> bytes:
    """
    Package the entire output directory into a ZIP file.
    Returns the ZIP as bytes for HTTP download.
    """
    if not os.path.exists(OUTPUT_DIR):
        raise FileNotFoundError("Output directory not found")

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(OUTPUT_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, OUTPUT_DIR)
                zf.write(file_path, arcname)

    return buf.getvalue()


def get_category_stats() -> dict[str, int]:
    """Return file count per category folder."""
    stats: dict[str, int] = {}
    for category in VALID_CATEGORIES:
        cat_dir = os.path.join(OUTPUT_DIR, category)
        if os.path.isdir(cat_dir):
            count = len(
                [
                    f
                    for f in os.listdir(cat_dir)
                    if os.path.isfile(os.path.join(cat_dir, f))
                ]
            )
            if count > 0:
                stats[category] = count
        else:
            stats[category] = 0
    return stats


def get_all_files() -> list[dict]:
    """List all files across all category folders with metadata."""
    all_files = []
    for category in VALID_CATEGORIES:
        cat_dir = os.path.join(OUTPUT_DIR, category)
        if not os.path.isdir(cat_dir):
            continue
        for filename in os.listdir(cat_dir):
            file_path = os.path.join(cat_dir, filename)
            if os.path.isfile(file_path):
                all_files.append(
                    {
                        "filename": filename,
                        "category": category,
                        "size": os.path.getsize(file_path),
                    }
                )
    return all_files


def delete_file(category: str, filename: str) -> bool:
    """Delete a file from a category folder. Returns True if deleted."""
    if category not in VALID_CATEGORIES:
        return False
    file_path = os.path.join(OUTPUT_DIR, category, filename)
    if not os.path.isfile(file_path):
        return False
    os.remove(file_path)
    # Clean up empty folder
    cat_dir = os.path.join(OUTPUT_DIR, category)
    if os.path.isdir(cat_dir) and not os.listdir(cat_dir):
        os.rmdir(cat_dir)
    return True


def move_file(filename: str, from_category: str, to_category: str) -> bool:
    """Move a file from one category to another. Returns True if moved."""
    if from_category not in VALID_CATEGORIES:
        return False
    if to_category not in VALID_CATEGORIES:
        return False
    if from_category == to_category:
        return False

    src = os.path.join(OUTPUT_DIR, from_category, filename)
    if not os.path.isfile(src):
        return False

    dst_dir = os.path.join(OUTPUT_DIR, to_category)
    os.makedirs(dst_dir, exist_ok=True)
    shutil.move(src, os.path.join(dst_dir, filename))

    # Clean up empty source folder
    src_dir = os.path.join(OUTPUT_DIR, from_category)
    if os.path.isdir(src_dir) and not os.listdir(src_dir):
        os.rmdir(src_dir)
    return True
