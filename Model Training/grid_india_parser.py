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
# State name matching — handles both English-only and bilingual formats,
# and gracefully skips entities not present in a given PDF (e.g. RIL_Jamnagar
# pre-Dec 2024, Tripura / Railways_ER in very early 2023 PDFs).
# ---------------------------------------------------------------------------

def _strip_devanagari(text):
    if not text:
        return ""
    return re.sub(r"[\u0900-\u097F\u0964\u0965]+", " ", str(text))

def _english_part(text):
    """Strip Devanagari, collapse whitespace, return lowercase English portion."""
    return re.sub(r"\s+", " ", _strip_devanagari(text)).strip().lower()

# Canonical lookup: every recognisable variant -> canonical state name
_STATE_ALIASES = {
    "punjab":              "Punjab",
    "haryana":             "Haryana",
    "rajasthan":           "Rajasthan",
    "delhi":               "Delhi",
    "up":                  "UP",
    "uttar pradesh":       "UP",
    "uttarakhand":         "Uttarakhand",
    "hp":                  "HP",
    "himachal pradesh":    "HP",
    "j&k":                 "J&K",
    "jammu":               "J&K",
    "chandigarh":          "Chandigarh",
    "railways_nr":         "Railways_NR",
    "railways nr":         "Railways_NR",
    "railways_nr ists":    "Railways_NR",
    "chhattisgarh":        "Chhattisgarh",
    "gujarat":             "Gujarat",
    "mp":                  "MP",
    "madhya pradesh":      "MP",
    "maharashtra":         "Maharashtra",
    "goa":                 "Goa",
    "dnhddpdcl":           "DNHDDPDCL",
    "dadra":               "DNHDDPDCL",
    "dnh":                 "DNHDDPDCL",
    "amnsil":              "AMNSIL",
    "arcelormittal":       "AMNSIL",
    "balco":               "BALCO",
    "bharat aluminium":    "BALCO",
    "ril jamnagar":        "RIL_Jamnagar",
    "ril":                 "RIL_Jamnagar",
    "jamnagar":            "RIL_Jamnagar",
    "andhra pradesh":      "Andhra Pradesh",
    "andhra":              "Andhra Pradesh",
    "telangana":           "Telangana",
    "karnataka":           "Karnataka",
    "kerala":              "Kerala",
    "tamil nadu":          "Tamil Nadu",
    "tamilnadu":           "Tamil Nadu",
    "pondy":               "Pondy",
    "pondicherry":         "Pondy",
    "puducherry":          "Pondy",
    "puducheri":           "Pondy",
    "bihar":               "Bihar",
    "dvc":                 "DVC",
    "damodar":             "DVC",
    "jharkhand":           "Jharkhand",
    "odisha":              "Odisha",
    "orissa":              "Odisha",
    "west bengal":         "West Bengal",
    "westbengal":          "West Bengal",
    "sikkim":              "Sikkim",
    "railways_er":         "Railways_ER",
    "railways er":         "Railways_ER",
    "railways_er ists":    "Railways_ER",
    "arunachal pradesh":   "Arunachal Pradesh",
    "arunachal":           "Arunachal Pradesh",
    "assam":               "Assam",
    "manipur":             "Manipur",
    "meghalaya":           "Meghalaya",
    "mizoram":             "Mizoram",
    "nagaland":            "Nagaland",
    "tripura":             "Tripura",
}

# Also try partial matches for longer names (e.g. "Arunachal" inside "Arunachal Pradesh")
_PARTIAL_ALIASES = {
    "arunachal":    "Arunachal Pradesh",
    "andhra":       "Andhra Pradesh",
    "west bengal":  "West Bengal",
    "tamil":        "Tamil Nadu",
    "himachal":     "HP",
    "damodar":      "DVC",
    "ril":          "RIL_Jamnagar",
}

def _identify_state(cell_text):
    """
    Try to identify which canonical state a cell text refers to.
    Returns canonical state name or None.
    """
    eng = _english_part(cell_text)
    if not eng:
        return None
    # Skip ALL_INDIA rows
    if "all india" in eng or "all_india" in eng:
        return None
    # Exact match first
    if eng in _STATE_ALIASES:
        return _STATE_ALIASES[eng]
    # Try stripping trailing footnote markers (e.g. "railways_er ists*")
    eng_clean = eng.rstrip("*").strip()
    if eng_clean in _STATE_ALIASES:
        return _STATE_ALIASES[eng_clean]
    # Partial: check if any alias is a substring of the cell text
    for alias, canonical in _STATE_ALIASES.items():
        if len(alias) > 3 and alias in eng:
            return canonical
    return None


def _build_state_row_map(raw, state_col=1, value_start_col=2):
    """
    Scan all rows of a raw table and build {canonical_state: row} dict.
    Skips header rows, ALL_INDIA rows, and footnote rows.
    state_col  = column index containing the state name
    value_start_col = column where numeric date values begin
    """
    state_map = {}
    for row in raw:
        if not row or len(row) <= state_col:
            continue
        state = _identify_state(row[state_col])
        if state and state not in state_map:
            state_map[state] = row
    return state_map


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
# T1 — Evening Demand Met & Shortage  (MW, 19:00/20:00 hrs)
# Page 2 — dynamic row detection handles old and new format
# ---------------------------------------------------------------------------

_T1_COLS = ["Date", "Region", "EveningDemand_MW", "EveningShortage_MW"]
_REGIONS  = ["NR", "WR", "SR", "ER", "NER", "ALL"]


def _date_row_groups(raw):
    """
    Collect all date rows from a page-2 merged table and split into 3 groups.
    Old PDFs have an extra units row pushing data down, new ones don't.
    Scanning for actual date rows handles both layouts automatically.
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


# ---------------------------------------------------------------------------
# T2 — Energy Met & Hydro Generation  (MU)
# ---------------------------------------------------------------------------

_T2_COLS = ["Date", "Region", "EnergyMet_MU", "HydroGen_MU"]

def _parse_t2(raw):
    _, g2, _ = _date_row_groups(raw)
    records = []
    for row in g2:
        date = row[0].strip()
        for i, region in enumerate(_REGIONS):
            records.append({"Date": date, "Region": region,
                            "EnergyMet_MU": _cell(row, 1 + i*2),
                            "HydroGen_MU":  _cell(row, 2 + i*2)})
    return pd.DataFrame(records) if records else _empty(_T2_COLS)


# ---------------------------------------------------------------------------
# T3 — All-India Grid Frequency
# ---------------------------------------------------------------------------

_T3_COLS = ["Date", "Freq_4980_4990_pct", "Freq_below_4990_pct",
            "Freq_4990_5005_pct", "Freq_above_5005_pct", "AvgFreq_Hz", "FreqVariationIndex"]

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


# ---------------------------------------------------------------------------
# T4 — State-wise Max Demand Met & Peak Hour Shortage  (MW)
# Page 3 — NAME-BASED matching avoids ALL_INDIA bleed and missing-state bugs
# ---------------------------------------------------------------------------

_T4_COLS = ["Date", "Region", "State", "MaxDemand_MW", "PeakShortage_MW"]

def _parse_t4(raw):
    # In T4, dates run across the TOP (row 1 in both old/new),
    # state names are in col1, values start at col2
    dates = _dates_from_rows(raw)
    state_map = _build_state_row_map(raw, state_col=1, value_start_col=2)

    records = []
    for state in STATES_ORDERED:
        row = state_map.get(state)
        if row is None:
            continue
        region = STATE_TO_REGION.get(state, "")
        for d_idx, date in enumerate(dates):
            records.append({"Date": date, "Region": region, "State": state,
                            "MaxDemand_MW":    _cell(row, 2 + d_idx*2),
                            "PeakShortage_MW": _cell(row, 3 + d_idx*2)})
    return pd.DataFrame(records) if records else _empty(_T4_COLS)


# ---------------------------------------------------------------------------
# T5 — State-wise Energy Consumption  (MU)
# Page 4 — NAME-BASED matching (same fix)
# ---------------------------------------------------------------------------

_T5_COLS = ["Date", "Region", "State", "Energy_Consumption_MU"]

def _parse_t5(raw):
    dates = _dates_from_rows(raw)
    state_map = _build_state_row_map(raw, state_col=1, value_start_col=2)

    records = []
    for state in STATES_ORDERED:
        row = state_map.get(state)
        if row is None:
            continue
        region = STATE_TO_REGION.get(state, "")
        for d_idx, date in enumerate(dates):
            records.append({"Date": date, "Region": region, "State": state,
                            "Energy_Consumption_MU": _cell(row, 2 + d_idx)})

    # ALL_INDIA total — find the row explicitly by looking for "all india" text in col0
    all_india_row = None
    for row in raw:
        if row and row[0] and "all india" in _english_part(row[0]).lower():
            all_india_row = row
            break
    if all_india_row is not None:
        for d_idx, date in enumerate(dates):
            records.append({"Date": date, "Region": "ALL", "State": "ALL_INDIA",
                            "Energy_Consumption_MU": _cell(all_india_row, 2 + d_idx)})

    return pd.DataFrame(records) if records else _empty(_T5_COLS)


# ---------------------------------------------------------------------------
# T6 — International Power Exchange  (MU / MW)
# ---------------------------------------------------------------------------

_T6_COLS = [
    "Date",
    "Bhutan_Exchange_MU", "Bhutan_DayPeak_MW", "Bhutan_DayAvg_MW",
    "Nepal_Exchange_MU",  "Nepal_DayPeak_MW",  "Nepal_DayAvg_MW",
    "Bangladesh_Exchange_MU", "Bangladesh_DayPeak_MW", "Bangladesh_DayAvg_MW",
]
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
# T7 — Inter-regional Exchange  (MU)
# Page 6 — COLUMN-ORIENTED: dates across top, flow directions down side
# Scans for the date header row (handles extra title rows in old PDFs)
# ---------------------------------------------------------------------------

_T7_COLS = ["Date", "FlowDirection", "Exchange_MU"]

def _parse_t7(raw):
    if not raw or len(raw) < 3:
        return _empty(_T7_COLS)
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
    for i, flow in enumerate(FLOW_DIRECTIONS):
        data_idx = header_idx + 1 + i
        if data_idx >= len(raw):
            break
        row = raw[data_idx]
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
    State assignment in T4/T5 uses name-based matching (not positional),
    so missing entities (e.g. RIL_Jamnagar pre-Dec 2024) are simply absent
    rather than corrupting neighbouring states.
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