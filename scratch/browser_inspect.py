import os
from playwright.sync_api import sync_playwright

ws_url = os.environ.get("AGY_BROWSER_WS_URL")
print(f"Connecting to browser over CDP via: {ws_url}...")

with sync_playwright() as p:
    try:
        browser = p.chromium.connect_over_cdp(ws_url)
        print("Connected successfully!")
        
        for context in browser.contexts:
            pages = context.pages
            print(f"Number of open pages: {len(pages)}")
            for idx, page in enumerate(pages, 1):
                try:
                    title_val = page.title
                    if callable(title_val):
                        title_val = title_val()
                    url_val = page.url
                    if callable(url_val):
                        url_val = url_val()
                    print(f"Page {idx}: {title_val} ({url_val})")
                except Exception as ex:
                    print(f"Page {idx} error: {ex}")
        browser.close()
    except Exception as e:
        print("CDP connection failed:", e)
