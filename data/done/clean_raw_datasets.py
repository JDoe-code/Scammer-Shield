#!/usr/bin/env python3
"""Normalize the raw email CSV datasets into data/done/*_cleaned.csv.

The output schema is body, subject, urls, sender, label, source. Labels use
0 for legitimate and 1 for phishing. Missing message bodies and duplicate
body/subject pairs are removed.
"""

import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "not_done"
OUT = ROOT / "data" / "done"
FIELDS = ["body", "subject", "urls", "sender", "label", "source"]
csv.field_size_limit(100_000_000)


def get(row, *names):
    lowered = {str(key).strip().lower(): value for key, value in row.items() if key is not None}
    for name in names:
        value = lowered.get(name.lower())
        if value is not None:
            return value
    return ""


def normalize_label(value):
    value = str(value or "").strip().lower()
    if value in {"0", "0.0", "legitimate", "legit", "safe", "safe email", "ham"}:
        return "0"
    if value in {"1", "1.0", "phishing", "phishing email", "spam"}:
        return "1"
    return None


def transform(row, source):
    source_lower = source.lower()
    body = get(row, "body", "email text", "email_body", "text_combined", "text")
    subject = get(row, "subject")
    sender = get(row, "sender", "sender_email", "from")
    urls = get(row, "urls", "url_domain")
    label = normalize_label(get(row, "label", "email type", "class", "category"))

    # The V2 source has a stable reduced feature set used by its existing notebook.
    if source_lower == "phishing_emaildetectionv2":
        body = get(row, "email_body")
        urls = get(row, "url_domain")
        sender = get(row, "sender_email")
        label = normalize_label(get(row, "label"))
    body = body.strip() if isinstance(body, str) else ""
    subject = subject.strip() if isinstance(subject, str) else ""
    sender = sender.strip() if isinstance(sender, str) else ""
    urls = urls.strip() if isinstance(urls, str) else str(urls or "")
    if not body or label is None:
        return None
    return {"body": body, "subject": subject, "urls": urls, "sender": sender,
            "label": label, "source": source}


def clean_file(path):
    source = re.sub(r"[^A-Za-z0-9]+", "_", path.stem).strip("_").lower()
    if path.parent.name == "archive":
        source = f"archive_{source}"
    target = OUT / f"{source}_cleaned.csv"
    seen = set()
    kept = dropped = duplicates = 0
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as stream:
        reader = csv.DictReader(stream)
        with target.open("w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=FIELDS)
            writer.writeheader()
            for row in reader:
                item = transform(row, source)
                if item is None:
                    dropped += 1
                    continue
                key = (item["body"], item["subject"])
                if key in seen:
                    duplicates += 1
                    continue
                seen.add(key)
                writer.writerow(item)
                kept += 1
    print(f"{path.relative_to(ROOT)} -> {target.name}: {kept} kept, {dropped} missing/unknown, {duplicates} duplicates")


def main():
    sources = sorted(RAW.glob("*.csv")) + sorted((RAW / "raw" / "archive").glob("*.csv"))
    for path in sources:
        clean_file(path)


if __name__ == "__main__":
    main()
