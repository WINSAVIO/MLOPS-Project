"""
GRID-INDIA Weekly PSP Report Downloader
Requirements: pip install requests undetected-chromedriver
"""

import os, re, time, requests, urllib3
from pathlib import Path

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
SSL_VERIFY = False

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

OUTPUT_DIR              = r"C:\Users\Savio Winson\Desktop\Energy Consumption\weekly_pdfs"
YEARS_TO_DOWNLOAD       = ["2026-27", "2025-26", "2024-25", "2023-24"]
SLEEP_BETWEEN_DOWNLOADS = 1.5
SLEEP_AFTER_YEAR_SELECT = 4.0
LISTING_URL             = "https://grid-india.in/en/reports/weekly-report"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
}

# ---------------------------------------------------------------------------
# Import undetected-chromedriver at module level so errors are visible
# ---------------------------------------------------------------------------

import traceback as _tb

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.keys import Keys
    UC_OK = True
    print("  [OK] undetected_chromedriver imported successfully")
except Exception as _e:
    UC_OK = False
    print(f"  [FAIL] Could not import undetected_chromedriver: {_e}")
    _tb.print_exc()

# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

def _scrape_links(driver) -> dict:
    links = {}
    for a in driver.find_elements(By.CSS_SELECTOR, "a[href]"):
        href = a.get_attribute("href") or ""
        if "weekly" in href.lower() and href.lower().endswith(".pdf"):
            links[href] = href.split("/")[-1]
    return links


def fetch_all_links() -> list[dict]:
    if not UC_OK:
        raise RuntimeError("undetected_chromedriver failed to import — see error above.")

    print("  Launching undetected Chrome...")

    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--headless=new")

    driver = uc.Chrome(options=options, version_main=147)
    wait   = WebDriverWait(driver, 20)
    all_links = {}

    try:
        driver.get(LISTING_URL)
        time.sleep(5)
        print(f"  Page title: {driver.title}")

        # Read year options from react-select
        available_years = []
        try:
            control = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".my-select__control"))
            )
            control.click()
            time.sleep(2)
            option_els = driver.find_elements(By.CSS_SELECTOR, ".my-select__option")
            available_years = [o.text.strip() for o in option_els
                               if re.match(r"\d{4}-\d{2}", o.text.strip())]
            print(f"  Years found: {available_years}")
            # Close menu by clicking the body — more reliable than Escape in headless
            driver.execute_script("document.body.click()")
            time.sleep(0.5)
        except Exception as e:
            print(f"  WARNING: Could not read dropdown ({e})")
            # available_years keeps whatever was read before the error

        years_to_scrape = ([y for y in available_years if y in YEARS_TO_DOWNLOAD]
                           if available_years else [])
        print(f"  Years to scrape: {years_to_scrape}")

        if not years_to_scrape:
            all_links.update(_scrape_links(driver))
        else:
            for year_label in years_to_scrape:
                try:
                    control = wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, ".my-select__control"))
                    )
                    control.click()
                    time.sleep(2)
                    for opt in driver.find_elements(By.CSS_SELECTOR, ".my-select__option"):
                        if opt.text.strip() == year_label:
                            driver.execute_script("arguments[0].scrollIntoView(true);", opt)
                            opt.click()
                            break
                    time.sleep(SLEEP_AFTER_YEAR_SELECT)
                    links = _scrape_links(driver)
                    print(f"    {year_label}: {len(links)} links")
                    all_links.update(links)
                except Exception as e:
                    print(f"  WARNING: Failed on {year_label}: {e}")

    finally:
        driver.quit()

    return [{"url": u, "filename": f} for u, f in all_links.items()]


# ---------------------------------------------------------------------------
# Downloader
# ---------------------------------------------------------------------------

def download_pdfs(links, output_dir):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    total = len(links)
    done = skipped = failed = 0
    print(f"\n  Downloading {total} PDFs -> {output_dir}\n")
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # Read processed logs (output_dir is in root/weekly_pdfs, so dirname is root)
    log_path = os.path.join(os.path.dirname(output_dir), "processed_files.log")
    processed_files = set()
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            for line in f:
                if line.strip() and not line.startswith("LAST_RUN") and not line.startswith("#"):
                    processed_files.add(line.strip())

    newly_downloaded = 0
    for i, item in enumerate(links, 1):
        url, filename = item["url"], item["filename"]
        out_path = os.path.join(output_dir, filename)
        if filename in processed_files:
            print(f"  [{i:>3}/{total}] SKIP (In Log)  {filename}")
            skipped += 1
            continue
        try:
            resp = session.get(url, timeout=30, stream=True, verify=SSL_VERIFY)
            resp.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"  [{i:>3}/{total}] OK    {filename}  ({os.path.getsize(out_path)//1024} KB)")
            done += 1
            newly_downloaded += 1
        except Exception as e:
            print(f"  [{i:>3}/{total}] FAIL  {filename}  {e}")
            failed += 1
        time.sleep(SLEEP_BETWEEN_DOWNLOADS)

    print(f"\n  Done — {done} downloaded, {skipped} skipped, {failed} failed.\n")
    return newly_downloaded


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("\n  Fetching PDF links from GRID-INDIA...\n")
    try:
        links = fetch_all_links()
    except Exception as e:
        print(f"\n  Fatal error: {e}\n")
        _tb.print_exc()
        return 0
    if not links:
        print("\n  No links found.\n")
        return 0
    print(f"\n  Total unique PDFs found: {len(links)}")
    return download_pdfs(links, OUTPUT_DIR)

if __name__ == "__main__":
    main()