import os
import sys
import time
from playwright.sync_api import sync_playwright

def run():
    print("==========================================================")
    print("             QuantileCull Cloud Deploy Monitor             ")
    print("==========================================================")
    print("Launching Google Chrome on your desktop...")
    
    with sync_playwright() as p:
        # Launch using the host's installed Google Chrome
        # We use a custom user data dir to avoid profile conflicts but let you log in
        profile_dir = os.path.join(os.getcwd(), "scratch", "chrome_profile")
        os.makedirs(profile_dir, exist_ok=True)
        
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=False,
                channel="chrome",
                args=["--start-maximized"]
            )
        except Exception as e:
            print("Failed to launch Chrome with persistent context. Trying standard launch...", e)
            browser = p.chromium.launch(headless=False, channel="chrome")
            context = browser.new_context()
            
        page = context.pages[0] if context.pages else context.new_page()
        
        print("\n--> Action Required:")
        print("1. A Google Chrome window has opened on your desktop.")
        print("2. Please log into your Render account in that window.")
        print("3. Once logged in, navigate to the service dashboard (either create the service, or click on it).")
        print("4. The script will monitor your navigation and audit the deployment automatically.")
        
        page.goto("https://dashboard.render.com")
        
        print("\nMonitoring browser navigation...")
        try:
            last_url = ""
            start_time = time.time()
            # Keep monitoring for up to 10 minutes
            while time.time() - start_time < 600:
                try:
                    curr_url = page.url
                    if curr_url != last_url:
                        print(f"Active URL: {curr_url}")
                        last_url = curr_url
                        
                        # Take screenshots of settings pages to report progress
                        if "render.com/web/srv-" in curr_url or "render.com/databases/dpg-" in curr_url:
                            print("--> Service detected! Capturing service status...")
                            time.sleep(2)
                            screenshot_path = r"C:\Users\Admin\.gemini\antigravity\brain\42e33fe9-fea8-4b44-ac5a-532ffeb3ed39\active_service_status.png"
                            page.screenshot(path=screenshot_path)
                            print(f"Saved status screenshot to {screenshot_path}")
                            
                            # Let's read the logs or settings if possible
                            content = page.content()
                            if "Build failed" in content or "Deployment failed" in content:
                                print("--> [ERROR] Build/deployment failures detected on page!")
                            elif "Live" in content:
                                print("--> [SUCCESS] Service is reported as Live!")
                                
                    time.sleep(2)
                except Exception as ex:
                    print(f"Monitoring tick error (browser might have closed): {ex}")
                    break
        finally:
            context.close()

if __name__ == "__main__":
    run()
