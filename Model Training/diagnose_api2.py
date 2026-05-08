"""
diagnose_api2.py
Intercepts the actual POST request body sent to webapi.grid-india.in/api/v1/file
when you change the year filter manually.
"""

import time, json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

LISTING_URL = "https://grid-india.in/en/reports/weekly-report"

chrome_opts = Options()
chrome_opts.add_argument("--no-sandbox")
chrome_opts.add_argument("--ignore-certificate-errors")
# Enable full request body capture
chrome_opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=chrome_opts
)

# Inject a fetch/XHR interceptor BEFORE the page loads
driver.execute_cdp_cmd("Network.enable", {})
driver.execute_cdp_cmd("Network.setRequestInterception", {
    "patterns": [{"urlPattern": "*webapi.grid-india.in*"}]
})

captured = []

def intercept(params):
    captured.append(params)
    # Allow request to continue
    driver.execute_cdp_cmd("Network.continueInterceptedRequest", {
        "interceptionId": params.get("interceptionId", "")
    })

try:
    print("Loading page...")
    driver.get(LISTING_URL)
    time.sleep(4)

    # Clear logs
    driver.get_log("performance")
    print("\nPage loaded.")
    print("Now MANUALLY click the year dropdown and select '2024-25'.")
    print("Wait for the list to reload, then press Enter here...")
    input()
    time.sleep(2)

    # Parse performance logs to find the POST request and its body
    logs = driver.get_log("performance")
    print(f"\nAnalyzing {len(logs)} log entries...")

    request_ids = {}
    for entry in logs:
        try:
            msg = json.loads(entry["message"])["message"]
            method = msg.get("method", "")
            params = msg.get("params", {})

            if method == "Network.requestWillBeSent":
                req = params.get("request", {})
                url = req.get("url", "")
                if "webapi.grid-india" in url:
                    rid = params.get("requestId")
                    request_ids[rid] = {
                        "url":     url,
                        "method":  req.get("method"),
                        "headers": req.get("headers", {}),
                        "body":    req.get("postData", "NO BODY CAPTURED"),
                    }
                    print(f"\n>>> REQUEST TO API <<<")
                    print(f"  URL:    {url}")
                    print(f"  Method: {req.get('method')}")
                    print(f"  Body:   {req.get('postData', 'NO BODY')}")
                    print(f"  Headers relevant:")
                    for k, v in req.get("headers", {}).items():
                        if k.lower() in ("content-type", "authorization",
                                         "x-api-key", "cookie", "origin", "referer"):
                            print(f"    {k}: {v}")

            elif method == "Network.loadingFinished":
                rid = params.get("requestId")
                if rid in request_ids:
                    # Try to get the response body
                    try:
                        body = driver.execute_cdp_cmd(
                            "Network.getResponseBody", {"requestId": rid}
                        )
                        print(f"\n>>> RESPONSE BODY <<<")
                        text = body.get("body", "")
                        try:
                            parsed = json.loads(text)
                            if isinstance(parsed, list):
                                print(f"  List of {len(parsed)} items")
                                print(f"  First item: {json.dumps(parsed[0], indent=2)[:400]}")
                            else:
                                print(f"  {json.dumps(parsed, indent=2)[:600]}")
                        except:
                            print(f"  Raw: {text[:500]}")
                    except Exception as e:
                        print(f"  (Could not get response body: {e})")

        except Exception:
            pass

    if not request_ids:
        print("\nNo API calls to webapi.grid-india.in were captured.")
        print("The year filter may be using client-side filtering only.")
        print("\nChecking if ALL links are already in the page source...")
        from selenium.webdriver.common.by import By
        links = driver.find_elements(By.CSS_SELECTOR, "a[href$='.pdf']")
        pdf_links = [a.get_attribute("href") for a in links if a.get_attribute("href")]
        pdf_links = [l for l in pdf_links if "weekly" in l.lower()]
        print(f"Weekly PDF links currently visible: {len(pdf_links)}")
        if pdf_links:
            print(f"  First: {pdf_links[0]}")
            print(f"  Last:  {pdf_links[-1]}")

    input("\nPress Enter to close browser...")

finally:
    driver.quit()
    print("Done.")
