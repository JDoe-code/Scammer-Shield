#!/usr/bin/env python
# coding: utf-8
"""
Batch preprocessing script for Scammer-Shield: renders clean email screenshots
using Playwright for all four core datasets without hardcoding paths.
"""
import os
import html
import pandas as pd
from pathlib import Path
from playwright.sync_api import sync_playwright

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "done" 
if not DATA_DIR.exists():
    DATA_DIR = BASE_DIR  # fallback if CSVs are in the same folder as the script

DATASETS = [
    {"name": "assassin_legit", "file": "assassin_legit_cleaned.csv", "label": 0},
    {"name": "assassin_phishing", "file": "assassin_phishing_cleaned.csv", "label": 1},
    {"name": "trec06_legit", "file": "trec06_legit_cleaned.csv", "label": 0},
    {"name": "trec06_phishing", "file": "trec06_phishing_cleaned.csv", "label": 1},
]

LIMIT_PER_DATASET = 500  # Set to None to process all rows, or an integer for a test subset

def wrap_email_to_html(subject, body, sender):
    """Wraps plain text email headers and body into a clean webmail HTML template."""
    safe_subject = html.escape(str(subject))
    safe_sender = html.escape(str(sender))
    safe_body = html.escape(str(body)).replace('\n', '<br>')
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                background-color: #f3f4f6;
                margin: 0;
                padding: 40px;
                color: #1f2937;
            }}
            .email-card {{
                background: #ffffff;
                max-width: 700px;
                margin: 0 auto;
                padding: 32px;
                border-radius: 12px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
            }}
            .email-header {{
                border-bottom: 1px solid #e5e7eb;
                padding-bottom: 20px;
                margin-bottom: 24px;
            }}
            .subject {{
                font-size: 20px;
                font-weight: 700;
                color: #111827;
                margin-bottom: 12px;
            }}
            .meta-row {{
                font-size: 14px;
                color: #4b5563;
                margin-bottom: 4px;
            }}
            .meta-row strong {{
                color: #374151;
            }}
            .email-body {{
                font-size: 14px;
                line-height: 1.6;
                white-space: pre-wrap;
                word-break: break-word;
                color: #374151;
            }}
        </style>
    </head>
    <body>
        <div class="email-card">
            <div class="email-header">
                <div class="subject">{safe_subject}</div>
                <div class="meta-row"><strong>From:</strong> {safe_sender}</div>
            </div>
            <div class="email-body">{safe_body}</div>
        </div>
    </body>
    </html>
    """

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        
        for ds in DATASETS:
            csv_path = DATA_DIR / ds["file"]
            if not csv_path.exists():
                print(f"[-] Warning: {csv_path} not found. Skipping {ds['name']}.")
                continue
                
            df = pd.read_csv(csv_path)
            output_dir = BASE_DIR / "rendered_email_screenshots" / ds["name"]
            output_dir.mkdir(parents=True, exist_ok=True)
            
            subset = df.head(LIMIT_PER_DATASET) if LIMIT_PER_DATASET else df
            print(f"[+] Rendering {len(subset)} emails for {ds['name']} into {output_dir.relative_to(BASE_DIR)}...")
            
            for idx, row in subset.iterrows():
                html_content = wrap_email_to_html(
                    subject=row.get('subject', ''), 
                    body=row.get('body', ''), 
                    sender=row.get('sender', '')
                )
                page.set_content(html_content, wait_until="load")
                
                card_element = page.locator(".email-card")
                screenshot_path = output_dir / f"{ds['name']}_email_{idx}.png"
                card_element.screenshot(path=screenshot_path)
                
                if (idx + 1) % 10 == 0 or (idx + 1) == len(subset):
                    print(f"    -> Captured {idx + 1}/{len(subset)} screenshots...")
                    
        browser.close()
    print("[+] All dataset renderings complete!")

if __name__ == "__main__":
    main()