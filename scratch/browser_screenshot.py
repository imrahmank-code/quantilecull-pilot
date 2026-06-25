import os
import time
from playwright.sync_api import sync_playwright

ws_url = os.environ.get("AGY_BROWSER_WS_URL")
print(f"Connecting to browser over CDP via: {ws_url}...")

with sync_playwright() as p:
    try:
        browser = p.chromium.connect_over_cdp(ws_url)
        print("Connected successfully!")
        
        # Open a new tab
        context = browser.contexts[0]
        page = context.new_page()
        
        url = "https://dashboard.render.com"
        print(f"Navigating to {url}...")
        page.goto(url, wait_until="load", timeout=30000)
        
        # Wait extra time for JS to render and session cookies to apply
        print("Waiting for page load...")
        time.sleep(8)
        
        # Print info
        title = page.title()
        curr_url = page.url
        if callable(curr_url):
            curr_url = curr_url()
        print(f"Loaded Page Title: {title}")
        print(f"Loaded Page URL:   {curr_url}")
        
        # Take screenshot and save to artifacts folder
        screenshot_path = r"C:\Users\Admin\.gemini\antigravity\brain\42e33fe9-fea8-4b44-ac5a-532ffeb3ed39\render_dashboard.png"
        page.screenshot(path=screenshot_path)
        print(f"Screenshot successfully saved to {screenshot_path}")
        
        # Close the page
        page.close()
        browser.close()
    except Exception as e:
        print("CDP browser task failed:", e)
