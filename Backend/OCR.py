#!/usr/bin/env python
# coding: utf-8
"""
OCR pipeline for Scammer-Shield: reads rendered email screenshots,
extracts their text with Tesseract, and saves the results as CSV + TXT.

Install dependencies once from the terminal (not in this file):
    pip install pandas pytesseract pillow

Run from anywhere:
    python Backend/OCR.py
"""
import os

# Tesseract uses several CPU threads per image by default. Since we run
# several images in parallel, one thread each is much faster overall.
# This must be set before any OCR call.
os.environ.setdefault("OMP_THREAD_LIMIT", "1")

import glob
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytesseract
from PIL import Image, ImageOps

# --- Settings ---
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
SCREENSHOT_DIR = PROJECT_DIR / "rendered_email_screenshots"
DATA_DIR = PROJECT_DIR / "data"

RAW_CSV = DATA_DIR / "ocr_results.csv"          # also used as a cache between runs
CLEAN_CSV = DATA_DIR / "ocr_results_clean.csv"
TXT_FILE = DATA_DIR / "ocr_results.txt"

IMAGES_PER_FOLDER = None   # images OCR'd per folder; set to None to OCR every image
MIN_WIDTH = 1600         # only upscale images narrower than this
USE_CACHE = True         # reuse text for images already OCR'd in a previous run
WORKERS = os.cpu_count() or 2

# --- TXT file markers (also used to read the file back on the next run) ---
EMAIL_START = "<<<START OF EMAIL>>>"
EMAIL_END = "<<<END OF EMAIL>>>"
RAW_HEADER = "-" * 30 + " RAW TEXT " + "-" * 30
CLEAN_HEADER = "-" * 29 + " CLEAN TEXT " + "-" * 29
HISTORY_TITLE = "RUN HISTORY"
HISTORY_PREFIX = "  RUN | "

# --- OCR ---
def extract_text(image_path):
    with Image.open(image_path) as img:
        img = ImageOps.grayscale(img)                    # simpler colors = better accuracy
        if img.width < MIN_WIDTH:                        # upscale small screenshots only
            scale = MIN_WIDTH / img.width
            img = img.resize((round(img.width * scale), round(img.height * scale)),
                             Image.LANCZOS)
        text = pytesseract.image_to_string(img)
    return text.strip()
 
 
def ocr_one(path):
    """OCR a single image and return its result row."""
    folder = os.path.basename(os.path.dirname(path))     # e.g. "trec06_phishing"
    try:
        text, error = extract_text(path), None
    except Exception as e:                               # one bad image won't stop the run
        text, error = "", str(e)
    return {
        "path": os.path.relpath(path, PROJECT_DIR),
        "file": os.path.basename(path),
        "folder": folder,
        "label": 1 if "phishing" in folder else 0,       # 1 = phishing, 0 = legit
        "text": text,
        "error": error,
        "scanned_at": f"{datetime.now():%Y-%m-%d %H:%M:%S}",
    }
 
 
# --- Metrics (for comparing OCR output against ground truth later) ---
def levenshtein(a, b):
    """Minimum number of edits to turn sequence a into sequence b."""
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        curr = [i]
        for j, y in enumerate(b, 1):
            curr.append(min(prev[j] + 1,              # deletion
                            curr[j - 1] + 1,          # insertion
                            prev[j - 1] + (x != y)))  # substitution
        prev = curr
    return prev[-1]
 
 
def normalize(text):
    return re.sub(r"\s+", " ", str(text)).strip().lower()
 
 
def cer(truth, ocr):
    truth, ocr = normalize(truth), normalize(ocr)
    return levenshtein(truth, ocr) / max(len(truth), 1)
 
 
def wer(truth, ocr):
    t, o = normalize(truth).split(), normalize(ocr).split()
    return levenshtein(t, o) / max(len(t), 1)
 
 
# --- Cleaning ---
def clean_ocr(text):
    text = str(text)
    text = re.sub(r"-\n", "", text)                 # rejoin words split across lines ("veri-\nfy")
    text = re.sub(r"[^\w\s@:/.$%!?'-]", " ", text)  # drop junk symbols, keep email/URL/money characters
    text = re.sub(r"\s+", " ", text)                # collapse whitespace
    return text.strip().lower()
 
 
# --- Helpers ---
def natural_key(path):
    """Sort numerically so email_2 comes before email_10."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", str(path))]
 
 
def select_images(paths, per_folder):
    """Keep the first `per_folder` images of each folder (all if None)."""
    if per_folder is None:
        return paths
    counts, chosen = {}, []
    for p in paths:
        folder = os.path.basename(os.path.dirname(p))
        if counts.get(folder, 0) < per_folder:
            chosen.append(p)
            counts[folder] = counts.get(folder, 0) + 1
    return chosen
 
 
def load_cache():
    """Return {relative path: row} for images that OCR'd successfully before."""
    if not (USE_CACHE and RAW_CSV.exists()):
        return {}
    old = pd.read_csv(RAW_CSV)
    if "path" not in old.columns:                        # CSV from the old notebook version
        return {}
    old["text"] = old["text"].fillna("")
    old = old[old["error"].isna()]
    return {row["path"]: row for row in old.to_dict("records")}
 
 
def is_set(value):
    """True for a real string value (not None/NaN/empty)."""
    return isinstance(value, str) and value != ""
 
 
# --- TXT file ---
def format_entry(row):
    """One email's block in the TXT file, ending with the EMAIL_END delimiter."""
    label = "phishing" if row["label"] == 1 else "legit"
    lines = [
        "=" * 80,
        EMAIL_START,
        f"PATH:    {row['path']}",
        f"FILE:    {row['file']}",
        f"FOLDER:  {row['folder']}",
        f"LABEL:   {row['label']} ({label})",
        f"SCANNED: {row['scanned_at'] if is_set(row.get('scanned_at')) else 'unknown'}",
    ]
    if is_set(row.get("error")):
        lines.append(f"ERROR:   {row['error']}")
    lines += [
        RAW_HEADER,
        row["text"] or "(no text found)",
        CLEAN_HEADER,
        row["clean_text"] or "(no text found)",
        EMAIL_END,
    ]
    return "\n".join(lines)
 
 
def read_existing_txt(path):
    """Read the run history and email blocks from a previous run's TXT file."""
    if not path.exists():
        return [], {}
    content = path.read_text(encoding="utf-8")
 
    header = content.split(EMAIL_START, 1)[0]
    history = [line for line in header.splitlines() if line.startswith(HISTORY_PREFIX)]
 
    entries = {}
    for chunk in content.split(EMAIL_END):
        start = chunk.find(EMAIL_START)
        if start == -1:
            continue
        block = chunk[start:].strip()
        match = re.search(r"^PATH:\s+(.+)$", block, re.MULTILINE)
        if match:
            entries[match.group(1).strip()] = "=" * 80 + "\n" + block + "\n" + EMAIL_END
    return history, entries
 
 
def update_txt(df, out_path, run_summary):
    """Add/refresh this run's emails in the TXT file and keep everything else."""
    history, entries = read_existing_txt(out_path)
    before = set(entries)
 
    for row in df.to_dict("records"):
        entries[row["path"]] = format_entry(row)
    history.append(HISTORY_PREFIX + run_summary)
 
    # Totals across every email in the file, not just this run
    folder_counts, errors = {}, 0
    for block in entries.values():
        meta = block.split(RAW_HEADER, 1)[0]
        m = re.search(r"^FOLDER:\s+(.+)$", meta, re.MULTILINE)
        if m:
            folder = m.group(1).strip()
            folder_counts[folder] = folder_counts.get(folder, 0) + 1
        if re.search(r"^ERROR:", meta, re.MULTILINE):
            errors += 1
 
    out = [
        "SCAMMER-SHIELD OCR RESULTS",
        f"Last updated: {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"Emails in file: {len(entries)}  |  With errors: {errors}",
    ]
    out += [f"  {folder}: {n}" for folder, n in sorted(folder_counts.items())]
    out += ["", HISTORY_TITLE] + history + [""]
    out += [entries[p] + "\n" for p in sorted(entries, key=natural_key)]
 
    # Write to a temp file first so an interrupted run can't corrupt the TXT
    tmp = out_path.with_suffix(".txt.tmp")
    tmp.write_text("\n".join(out), encoding="utf-8")
    os.replace(tmp, out_path)
 
    added = len(set(entries) - before)
    return added, len(df) - added
 
 
def main():
    start = time.time()
    print("Tesseract version:", pytesseract.get_tesseract_version())
 
    all_paths = sorted(
        glob.glob(str(SCREENSHOT_DIR / "**" / "*.png"), recursive=True),
        key=natural_key,
    )
    image_paths = select_images(all_paths, IMAGES_PER_FOLDER)
    print(f"Found {len(all_paths)} images, processing {len(image_paths)}")
    if not image_paths:
        print("No images found, check SCREENSHOT_DIR.")
        return
 
    cache = load_cache()
    results, todo = [], []
    for p in image_paths:
        rel = os.path.relpath(p, PROJECT_DIR)
        if rel in cache:
            results.append(cache[rel])
        else:
            todo.append(p)
    cached = len(results)
    if cache:
        print(f"Reused {cached} cached results, {len(todo)} left to OCR")
 
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(ocr_one, p) for p in todo]
        for i, fut in enumerate(as_completed(futures), 1):
            results.append(fut.result())
            if i % 10 == 0 or i == len(todo):
                print(f"{i}/{len(todo)} images read")
 
    DATA_DIR.mkdir(exist_ok=True)
 
    results.sort(key=lambda r: natural_key(r["path"]))   # keep email_2 before email_10
    ocr_df = pd.DataFrame(results)
    ocr_df["text"] = ocr_df["text"].fillna("")
    ocr_df["clean_text"] = ocr_df["text"].apply(clean_ocr)
 
    ocr_df.drop(columns="clean_text").to_csv(RAW_CSV, index=False)
    ocr_df.to_csv(CLEAN_CSV, index=False)
 
    n_errors = int(ocr_df["error"].notna().sum())
    n_empty = int((ocr_df["text"].str.len() < 20).sum())
    run_summary = (f"{datetime.now():%Y-%m-%d %H:%M:%S} | processed {len(ocr_df)} "
                   f"(newly scanned {len(todo)}, cached {cached}) | "
                   f"errors {n_errors} | empty {n_empty}")
    added, refreshed = update_txt(ocr_df, TXT_FILE, run_summary)
 
    print("Images read:", len(ocr_df))
    print("Errors:", n_errors)
    print("Empty/near-empty results:", n_empty)
    print(ocr_df.groupby("folder").size())
    print(f"Saved {RAW_CSV.name} and {CLEAN_CSV.name} to data/")
    print(f"Updated {TXT_FILE.name}: {added} emails added, {refreshed} refreshed")
    print(f"Done in {time.time() - start:.1f}s")
 
 
if __name__ == "__main__":
    main()
