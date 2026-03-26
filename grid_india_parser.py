"""
grid_india_parser.py
====================
Reusable extraction functions for GRID-INDIA Weekly PSP PDF reports.
Import this module; do not run it directly.

Public API
----------
parse_pdf(pdf_path)  ->  dict[str, pd.DataFrame]  |  None
    Keys: "t1", "t2", "t3", "t4", "t5", "t6", "t7"
    Each value is a tidy long-format DataFrame.
    Returns None if the PDF is unreadable.
"""

import re
import pdfplumber
import pandas as pd

# ---------------------------------------------------------------------------
# Region / state metadata
# ---------------------------------------------------------------------------

STATES_ORDERED = [
    "Punjab", "Haryana", "Rajasthan", "Delhi", "UP", "Uttarakhand",
    "HP", "J&K", "Chandigarh", "Railways_NR",
    "Chhattisgarh", "Gujarat", "MP", "Maharashtra", "Goa", "DNHDDPDCL",
    "AMNSIL", "BALCO", "RIL_Jamnagar",
    "Andhra Pradesh", "Telangana", "Karnataka", "Kerala", "Tamil Nadu", "Pondy",
    "Bihar", "DVC", "Jharkhand", "Odisha", "West Bengal", "Sikkim", "Railways_ER",
    "Arunachal Pradesh", "Assam", "Manipur", "Meghalaya",
    "Mizoram", "Nagaland", "Tripura",
]

STATE_TO_REGION = {
    s: r for r, states in {
        "NR":  STATES_ORDERED[:10],
        "WR":  STATES_ORDERED[10:19],
        "SR":  STATES_ORDERED[19:25],
        "ER":  STATES_ORDERED[25:32],
        "NER": STATES_ORDERED[32:],
    }.items() for s in states
}

FLOW_DIRECTIONS = [
    "East_to_North", "East_to_West", "East_to_South", "East_to_NorthEast",
    "NorthEast_to_North", "West_to_North", "West_to_South",
]

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _num(val):
    if val is None or str(val).strip() == "":
        return None
    try:
        return float(str(val).replace(",", "").strip())
    except ValueError:
        return None

def _cell(row, idx):
    return _num(row[idx]) if idx < len(row) else None

def _is_date(val):
    return bool(val and re.match(r"\d{2}-\d{2}-\d{4}", str(val).strip()))

def _dates_from_rows(rows, max_scan=5):
    seen, out = set(), []
    for row in rows[:max_scan]:
        for cell in (row or []):
            if cell and re.fullmatch(r"\d{2}-\d{2}-\d{4}", str(cell).strip()):
                d = cell.strip()
                if d not in seen:
                    seen.add(d)
                    out.append(d)
    return out

def _empty(cols):
    return pd.DataFrame(columns=cols)

# ---------------------------------------------------------------------------
# T1
# ---------------------------------------------------------------------------

_T1_COLS = ["Date", "Region", "EveningDemand_MW", "EveningShortage_MW"]
_REGIONS = ["NR", "WR", "SR", "ER", "NER", "ALL"]

def _date_row_groups(raw):
    """
    Collect all date rows from a page-2 merged table and split into 3 groups of 7.
    Old PDFs have an extra units row pushing data down, new ones don't.
    By scanning for actual date rows we handle both layouts automatically.
    """
    date_rows = [row for row in raw if row and row[0] and _is_date(row[0])]
    return date_rows[:7], date_rows[7:14], date_rows[14:21]


def _parse_t1(raw):
    g1, _, _ = _date_row_groups(raw)
    records = []
    for row in g1:
        date = row[0].strip()
        for i, region in enumerate(_REGIONS):
            records.append({"Date": date, "Region": region,
                            "EveningDemand_MW": _cell(row, 1 + i*2),
                            "EveningShortage_MW": _cell(row, 2 + i*2)})
    return pd.DataFrame(records) if records else _empty(_T1_COLS)


def _parse_t2(raw):
    _, g2, _ = _date_row_groups(raw)
    records = []
    for row in g2:
        date = row[0].strip()
        for i, region in enumerate(_REGIONS):
            records.append({"Date": date, "Region": region,
                            "EnergyMet_MU": _cell(row, 1 + i*2),
                            "HydroGen_MU": _cell(row, 2 + i*2)})
    return pd.DataFrame(records) if records else _empty(_T2_COLS)


def _parse_t3(raw):
    _, _, g3 = _date_row_groups(raw)
    records = []
    for row in g3:
        records.append({"Date": row[0].strip(),
                        "Freq_4980_4990_pct":  _cell(row, 1),
                        "Freq_below_4990_pct": _cell(row, 3),
                        "Freq_4990_5005_pct":  _cell(row, 5),
                        "Freq_above_5005_pct": _cell(row, 7),
                        "AvgFreq_Hz":          _cell(row, 9),
                        "FreqVariationIndex":  _cell(row, 11)})
    return pd.DataFrame(records) if records else _empty(_T3_COLS)



def _parse_t4(raw):
    dates = _dates_from_rows(raw)
    records = []
    def _is_num(v):
        try: float(str(v).replace(',','').strip()); return True
        except: return False
    # Skip title/header rows: real data rows have a numeric value in r[2]
    data_rows = [r for r in raw[2:] if r and len(r) > 2 and r[1] and str(r[1]).strip() and _is_num(r[2])]
    for i, row in enumerate(data_rows):
        if i >= len(STATES_ORDERED):
            break
        state = STATES_ORDERED[i]
        region = STATE_TO_REGION.get(state, "")
        for d_idx, date in enumerate(dates):
            records.append({"Date": date, "Region": region, "State": state,
                            "MaxDemand_MW": _cell(row, 2 + d_idx*2),
                            "PeakShortage_MW": _cell(row, 3 + d_idx*2)})
    return pd.DataFrame(records) if records else _empty(_T4_COLS)

# ---------------------------------------------------------------------------
# T5
# ---------------------------------------------------------------------------

_T5_COLS = ["Date", "Region", "State", "Energy_Consumption_MU"]

def _parse_t5(raw):
    dates = _dates_from_rows(raw)
    records = []
    data_rows = raw[2:-1]
    for i, row in enumerate(data_rows):
        if i >= len(STATES_ORDERED):
            break
        state = STATES_ORDERED[i]
        region = STATE_TO_REGION.get(state, "")
        for d_idx, date in enumerate(dates):
            records.append({"Date": date, "Region": region, "State": state,
                            "Energy_Consumption_MU": _cell(row, 2 + d_idx)})
    if raw:
        last = raw[-1]
        for d_idx, date in enumerate(dates):
            records.append({"Date": date, "Region": "ALL", "State": "ALL_INDIA",
                            "Energy_Consumption_MU": _cell(last, 2 + d_idx)})
    return pd.DataFrame(records) if records else _empty(_T5_COLS)

# ---------------------------------------------------------------------------
# T6
# ---------------------------------------------------------------------------

_T6_COLS = ["Date",
            "Bhutan_Exchange_MU", "Bhutan_DayPeak_MW", "Bhutan_DayAvg_MW",
            "Nepal_Exchange_MU",  "Nepal_DayPeak_MW",  "Nepal_DayAvg_MW",
            "Bangladesh_Exchange_MU", "Bangladesh_DayPeak_MW", "Bangladesh_DayAvg_MW"]
_COUNTRIES = ["Bhutan", "Nepal", "Bangladesh"]

def _parse_t6(raw):
    records = []
    for row in raw:
        if not row or not _is_date(row[0]):
            continue
        rec = {"Date": row[0].strip()}
        for i, c in enumerate(_COUNTRIES):
            rec[f"{c}_Exchange_MU"] = _cell(row, 1 + i*3)
            rec[f"{c}_DayPeak_MW"]  = _cell(row, 2 + i*3)
            rec[f"{c}_DayAvg_MW"]   = _cell(row, 3 + i*3)
        records.append(rec)
    return pd.DataFrame(records) if records else _empty(_T6_COLS)

# ---------------------------------------------------------------------------
# T7  — COLUMN-ORIENTED: dates are column headers, flow directions are rows
#
# Page 6 layout:
#   raw[0] : title row
#   raw[1] : [date_label, 02-03-2026, 03-03-2026, ..., 08-03-2026]
#   raw[2] : [East_to_North (Hindi\nEnglish), -67.7, -60.2, ...]
#   raw[3] : [East_to_West ..., ...]
#   ...
# ---------------------------------------------------------------------------

_T7_COLS = ["Date", "FlowDirection", "Exchange_MU"]

def _parse_t7(raw):
    """
    T7 is column-oriented: dates run across the top, flow directions down the side.
    Old PDFs have 1-2 extra title rows before the date header row.
    We scan every row to find the one whose columns 1+ are dates.
    """
    if not raw or len(raw) < 3:
        return _empty(_T7_COLS)

    # Find the header row — the one where column 1 is a date
    header_idx = None
    for i, row in enumerate(raw):
        if row and len(row) > 1 and _is_date(row[1]):
            header_idx = i
            break

    if header_idx is None:
        return _empty(_T7_COLS)

    dates = [str(c).strip() for c in raw[header_idx][1:] if _is_date(c)]
    if not dates:
        return _empty(_T7_COLS)

    records = []
    data_rows = raw[header_idx + 1:]
    for i, flow in enumerate(FLOW_DIRECTIONS):
        if i >= len(data_rows):
            break
        row = data_rows[i]
        for d_idx, date in enumerate(dates):
            records.append({"Date": date, "FlowDirection": flow,
                            "Exchange_MU": _cell(row, 1 + d_idx)})

    return pd.DataFrame(records) if records else _empty(_T7_COLS)

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_pdf(pdf_path):
    """
    Parse a single GRID-INDIA weekly PDF.
    Returns dict with keys t1..t7, or None if the file cannot be opened.
    Every returned DataFrame is guaranteed to have a Date column.
    """

    def _safe_extract(page, label):
        try:
            tables = page.extract_tables()
            return tables[0] if tables else []
        except BaseException as e:
            print(f"    [PAGE ERROR] {label}: {type(e).__name__}: {e}")
            return []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            if len(pdf.pages) < 6:
                raise ValueError(f"Expected >=6 pages, got {len(pdf.pages)}")
            p2 = _safe_extract(pdf.pages[1], "p2->t1/t2/t3")
            p3 = _safe_extract(pdf.pages[2], "p3->t4")
            p4 = _safe_extract(pdf.pages[3], "p4->t5")
            p5 = _safe_extract(pdf.pages[4], "p5->t6")
            p6 = _safe_extract(pdf.pages[5], "p6->t7")
    except BaseException as e:
        print(f"  [PARSE ERROR] {pdf_path}: {type(e).__name__}: {e}")
        return None

    return {
        "t1": _parse_t1(p2),
        "t2": _parse_t2(p2),
        "t3": _parse_t3(p2),
        "t4": _parse_t4(p3),
        "t5": _parse_t5(p4),
        "t6": _parse_t6(p5),
        "t7": _parse_t7(p6),
    }