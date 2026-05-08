"""
diagnose.py  —  run this BEFORE build_dataset.py to see exactly what
each table parser returns for a single PDF.

Usage:
    python diagnose.py
"""

import sys
import pdfplumber
import pandas as pd
import re

PDF_PATH = r"C:\Users\Savio Winson\Desktop\Energy Consumption\weekly_pdfs\Weekly%20020326%20to%20080326_253.pdf"

def _num(val):
    if val is None or str(val).strip() == "":
        return None
    try:
        return float(str(val).replace(",", "").strip())
    except ValueError:
        return None

print(f"\n{'='*60}")
print(f"Diagnosing: {PDF_PATH.split(chr(92))[-1]}")
print(f"{'='*60}\n")

try:
    with pdfplumber.open(PDF_PATH) as pdf:
        print(f"Pages: {len(pdf.pages)}")
        for page_idx in range(1, 6):
            print(f"\n--- Page {page_idx+1} ---")
            try:
                tables = pdf.pages[page_idx].extract_tables()
                print(f"  Tables found: {len(tables)}")
                if tables:
                    t = tables[0]
                    print(f"  Rows: {len(t)}")
                    print(f"  Cols in row 0: {len(t[0]) if t else 0}")
                    # Check for date strings
                    dates_found = []
                    for row in t:
                        for cell in (row or []):
                            if cell and re.match(r"\d{2}-\d{2}-\d{4}", str(cell).strip()):
                                if cell.strip() not in dates_found:
                                    dates_found.append(cell.strip())
                    print(f"  Dates found: {dates_found}")
                    print(f"  Row 0 sample: {[str(c)[:30] if c else None for c in t[0][:4]]}")
                    if len(t) > 1:
                        print(f"  Row 1 sample: {[str(c)[:30] if c else None for c in t[1][:4]]}")
            except Exception as e:
                print(f"  ERROR: {type(e).__name__}: {e}")
except Exception as e:
    print(f"FATAL: Could not open PDF: {e}")

print("\n--- Importing grid_india_parser ---")
try:
    import grid_india_parser as p
    print("  Import OK")
    print(f"  Module file: {p.__file__}")

    tables = p.parse_pdf(PDF_PATH)
    if tables is None:
        print("  parse_pdf returned None")
    else:
        print("\n  Table shapes:")
        for key, df in tables.items():
            print(f"    {key}: {df.shape}  cols={list(df.columns)[:5]}")
            if not df.empty:
                print(f"         sample Date values: {df['Date'].unique()[:3].tolist() if 'Date' in df.columns else 'NO DATE COL'}")

except Exception as e:
    import traceback
    print(f"  ERROR: {e}")
    traceback.print_exc()

print("\nDiagnosis complete.\n")
