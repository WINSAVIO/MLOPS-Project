"""
diagnose_page.py
Dumps what Selenium sees on the GRID-India listing page so we can
identify the correct selector for the year dropdown.
Run this, then paste the output back to Claude.
"""

import time
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

LISTING_URL = "https://grid-india.in/en/reports/weekly-report"

chrome_opts = Options()
# Run NON-headless so you can see the browser open
# chrome_opts.add_argument("--headless=new")
chrome_opts.add_argument("--no-sandbox")
chrome_opts.add_argument("--disable-dev-shm-usage")
chrome_opts.add_argument("--ignore-certificate-errors")

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=chrome_opts
)

try:
    print(f"Loading {LISTING_URL} ...")
    driver.get(LISTING_URL)
    time.sleep(5)  # let JS fully render

    print("\n--- PAGE TITLE ---")
    print(driver.title)

    print("\n--- ALL <select> ELEMENTS ---")
    selects = driver.find_elements(By.TAG_NAME, "select")
    print(f"Found {len(selects)} <select> elements")
    for i, sel in enumerate(selects):
        print(f"  select[{i}]: id={sel.get_attribute('id')} class={sel.get_attribute('class')}")
        opts = sel.find_elements(By.TAG_NAME, "option")
        for o in opts:
            print(f"    option: value={repr(o.get_attribute('value'))} text={repr(o.text.strip())}")

    print("\n--- ALL ELEMENTS WITH 'select' IN CLASS OR ID ---")
    results = driver.execute_script("""
        var found = [];
        document.querySelectorAll('*').forEach(function(el) {
            var cls = (el.className || '').toString();
            var id  = (el.id || '').toString();
            if ((cls + id).toLowerCase().includes('select') ||
                (cls + id).toLowerCase().includes('filter') ||
                (cls + id).toLowerCase().includes('year')  ||
                (cls + id).toLowerCase().includes('dropdown')) {
                found.push({
                    tag: el.tagName,
                    id: el.id,
                    cls: cls.substring(0,80),
                    text: (el.innerText||'').substring(0,60)
                });
            }
        });
        return found.slice(0, 30);
    """)
    for r in results:
        print(f"  <{r['tag']}> id={r['id']} class={r['cls']}")
        if r['text'].strip():
            print(f"    text: {r['text'].strip()}")

    print("\n--- PDF LINKS FOUND ---")
    links = driver.find_elements(By.CSS_SELECTOR, "a[href]")
    pdf_links = [a.get_attribute("href") for a in links
                 if a.get_attribute("href") and "weekly" in a.get_attribute("href").lower()
                 and a.get_attribute("href").lower().endswith(".pdf")]
    print(f"PDF links visible: {len(pdf_links)}")
    if pdf_links:
        print(f"  First: {pdf_links[0]}")
        print(f"  Last:  {pdf_links[-1]}")

    print("\n--- CURRENT URL ---")
    print(driver.current_url)

    input("\nBrowser is open — inspect it manually if needed. Press Enter to close...")

finally:
    driver.quit()
    print("Done.")
