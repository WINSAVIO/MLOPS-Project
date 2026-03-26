"""
diagnose_network.py
Opens the page NON-headless, captures every network request,
then we change the year filter manually and see what API gets called.
"""

import time, json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from webdriver_manager.chrome import ChromeDriverManager

LISTING_URL = "https://grid-india.in/en/reports/weekly-report"

# Enable performance logging to capture network requests
chrome_opts = Options()
chrome_opts.add_argument("--no-sandbox")
chrome_opts.add_argument("--ignore-certificate-errors")
chrome_opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=chrome_opts
)

try:
    print(f"Loading page...")
    driver.get(LISTING_URL)
    time.sleep(4)

    # Clear existing logs
    driver.get_log("performance")
    print("\nPage loaded. Now MANUALLY click the year dropdown and select '2024-25'.")
    print("Then press Enter here...")
    input()

    time.sleep(2)

    # Capture all network requests made after the year change
    logs = driver.get_log("performance")
    print(f"\nCaptured {len(logs)} log entries. Filtering for XHR/fetch requests...\n")

    api_calls = []
    for entry in logs:
        try:
            msg = json.loads(entry["message"])["message"]
            if msg["method"] in ("Network.requestWillBeSent", "Network.responseReceived"):
                url = (msg.get("params", {})
                          .get("request", msg.get("params", {})
                          .get("response", {}))
                          .get("url", ""))
                if url and "grid-india" in url.lower() and not url.endswith((".js", ".css", ".png", ".ico", ".woff")):
                    api_calls.append(f"  [{msg['method'].split('.')[1][:3]}] {url}")
        except:
            pass

    # Deduplicate preserving order
    seen = set()
    for c in api_calls:
        if c not in seen:
            print(c)
            seen.add(c)

    # Also check current PDF links after the year change
    from selenium.webdriver.common.by import By
    links = driver.find_elements(By.CSS_SELECTOR, "a[href$='.pdf']")
    pdf_links = [a.get_attribute("href") for a in links if a.get_attribute("href")]
    print(f"\nPDF links visible after year change: {len(pdf_links)}")
    if pdf_links:
        print(f"  First: {pdf_links[0]}")
        print(f"  Last:  {pdf_links[-1]}")

    input("\nPress Enter to close...")
finally:
    driver.quit()
    print("Done.")
