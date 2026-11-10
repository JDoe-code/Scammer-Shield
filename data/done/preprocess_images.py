import os
import html
import pandas as pd
from playwright.sync_api import sync_playwright

# 1. Load the cleaned dataset, change as needed to which file needs image rendering
df = pd.read_csv('data/done/assassin_phishing_cleaned.csv')

# 2. Create output directory for screenshots
output_dir = 'rendered_email_screenshots/assassin_phishing'
os.makedirs(output_dir, exist_ok=True)

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

# 3. Run Playwright to render and capture screenshots
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    
    # Process a subset (e.g., first 50) as a test, or remove the slice [:50] for all rows
    limit = 50 
    print(f"Starting rendering for {min(limit, len(df))} emails...")
    
    for idx, row in df.head(limit).iterrows():
        html_content = wrap_email_to_html(
            subject=row['subject'], 
            body=row['body'], 
            sender=row['sender']
        )
        
        # Load HTML content directly into the headless browser page
        page.set_content(html_content, wait_until="load")
        
        # Optional: target the email card specifically for a cleaner bounding box
        card_element = page.locator(".email-card")
        
        screenshot_path = os.path.join(output_dir, f"assassin_phishing_email_{idx}.png")
        card_element.screenshot(path=screenshot_path)
        
        if (idx + 1) % 10 == 0:
            print(f"Captured {idx + 1} screenshots...")
            
    browser.close()

print(f"Done! Screenshots successfully saved to '{output_dir}/'")