"""
diagnose_api.py
Probes the webapi.grid-india.in/api/v1/file endpoint to find
what parameters control the year filter and report type.
"""

import requests, json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://webapi.grid-india.in/api/v1/file"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":    "https://grid-india.in/en/reports/weekly-report",
    "Origin":     "https://grid-india.in",
}

def try_request(label, method="GET", params=None, json_body=None):
    print(f"\n--- {label} ---")
    try:
        if method == "GET":
            r = requests.get(BASE, headers=HEADERS, params=params,
                             verify=False, timeout=10)
        else:
            r = requests.post(BASE, headers=HEADERS, params=params,
                              json=json_body, verify=False, timeout=10)
        print(f"  Status: {r.status_code}")
        print(f"  URL:    {r.url}")
        text = r.text[:1000]
        try:
            parsed = r.json()
            print(f"  JSON keys: {list(parsed.keys()) if isinstance(parsed, dict) else type(parsed)}")
            if isinstance(parsed, list):
                print(f"  List length: {len(parsed)}")
                print(f"  First item: {json.dumps(parsed[0], indent=2)[:400] if parsed else 'empty'}")
            else:
                print(f"  Body: {json.dumps(parsed, indent=2)[:600]}")
        except:
            print(f"  Raw: {text}")
    except Exception as e:
        print(f"  ERROR: {e}")

# Try plain GET first
try_request("Plain GET")

# Try common parameter patterns for year + report type
try_request("GET year=2024-25",          params={"year": "2024-25"})
try_request("GET fiscalYear=2024-25",    params={"fiscalYear": "2024-25"})
try_request("GET financial_year=2024-25",params={"financial_year": "2024-25"})
try_request("GET type=weekly&year",      params={"type": "weekly", "year": "2024-25"})
try_request("GET category=weekly",       params={"category": "weekly"})
try_request("GET report_type=weekly",    params={"report_type": "weekly", "year": "2024-25"})
try_request("GET slug=weekly-report",    params={"slug": "weekly-report", "year": "2024-25"})
try_request("GET page_slug",             params={"page_slug": "weekly-report", "financial_year": "2024-25"})

# Also try with the full fiscal year values seen in the dropdown
for yr in ["2025-26", "2024-25", "2023-24"]:
    try_request(f"GET multiple param styles yr={yr}",
                params={"financial_year": yr, "report_type": "weekly-report"})
