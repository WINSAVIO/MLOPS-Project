"""
build_dataset.py
================
Processes all GRID-INDIA weekly PDFs and produces two master CSV files:

    master_state_daily.csv     one row per (Date, State)
    master_national_daily.csv  one row per Date

Edit the CONFIG block below, then run:
    python build_dataset.py
"""

import os
import glob
import traceback
import pandas as pd
from grid_india_parser import parse_pdf, FLOW_DIRECTIONS

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

PDF_DIR    = r"C:\Users\Savio Winson\Desktop\Energy Consumption\weekly_pdfs"
OUTPUT_DIR = r"C:\Users\Savio Winson\Desktop\Energy Consumption\dataset"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_merge(left, right, on, how="left"):
    """Merge that skips gracefully if right is empty or missing the join key."""
    if right is None or right.empty:
        return left
    keys = [on] if isinstance(on, str) else on
    if not all(k in right.columns for k in keys):
        return left
    if not all(k in left.columns for k in keys):
        return left
    return pd.merge(left, right, on=on, how=how)


def _pivot_t7(t7):
    """Long (Date, FlowDirection, Exchange_MU) -> wide one-row-per-date."""
    if t7 is None or t7.empty or "Date" not in t7.columns:
        return pd.DataFrame(columns=["Date"])
    wide = (t7.pivot_table(index="Date", columns="FlowDirection", values="Exchange_MU")
              .reset_index()
              .rename(columns=lambda c: f"Flow_{c}" if c != "Date" else c))
    return wide


# ---------------------------------------------------------------------------
# State-level join  (one row per Date × State)
# ---------------------------------------------------------------------------

def _build_state_rows(tables):
    t5 = tables["t5"]
    t4 = tables["t4"]
    t1 = tables["t1"]
    t2 = tables["t2"]
    t3 = tables["t3"]
    t6 = tables["t6"]

    # T5 is the spine — without it there's nothing to build on
    t5_data = t5[t5["State"] != "ALL_INDIA"] if not t5.empty else t5
    if t5_data.empty:
        raise ValueError("T5 (energy consumption) is empty")

    # Bolt T4 onto the spine
    t4_slim = (t4[["Date", "State", "MaxDemand_MW", "PeakShortage_MW"]]
               if not t4.empty else pd.DataFrame(columns=["Date", "State"]))
    base = _safe_merge(t5_data, t4_slim, on=["Date", "State"])

    # Region features: rename T1 & T2 columns then join on (Date, Region)
    if not t1.empty:
        t1_r = t1[t1["Region"] != "AllIndia"].rename(columns={
            "EveningDemand_MW":   "Reg_EveningDemand_MW",
            "EveningShortage_MW": "Reg_EveningShortage_MW"})
    else:
        t1_r = pd.DataFrame(columns=["Date", "Region",
                                      "Reg_EveningDemand_MW", "Reg_EveningShortage_MW"])

    if not t2.empty:
        t2_r = t2[t2["Region"] != "AllIndia"].rename(columns={
            "EnergyMet_MU": "Reg_EnergyMet_MU",
            "HydroGen_MU":  "Reg_HydroGen_MU"})
    else:
        t2_r = pd.DataFrame(columns=["Date", "Region",
                                      "Reg_EnergyMet_MU", "Reg_HydroGen_MU"])

    region_feat = _safe_merge(t1_r, t2_r, on=["Date", "Region"], how="outer")
    base = _safe_merge(base, region_feat, on=["Date", "Region"])

    # All-India energy from T2
    if not t2.empty and "Region" in t2.columns:
        t2_all = (t2[t2["Region"] == "AllIndia"][["Date", "EnergyMet_MU", "HydroGen_MU"]]
                  .rename(columns={"EnergyMet_MU": "Grid_EnergyMet_MU",
                                   "HydroGen_MU":  "Grid_HydroGen_MU"}))
    else:
        t2_all = pd.DataFrame(columns=["Date", "Grid_EnergyMet_MU", "Grid_HydroGen_MU"])

    # Grid frequency from T3
    if not t3.empty and "AvgFreq_Hz" in t3.columns:
        t3_slim = t3[["Date", "AvgFreq_Hz", "FreqVariationIndex", "Freq_4990_5005_pct"]].rename(
            columns={"AvgFreq_Hz":         "Grid_AvgFreq_Hz",
                     "FreqVariationIndex": "Grid_FreqVariationIndex",
                     "Freq_4990_5005_pct": "Grid_NormalBand_pct"})
    else:
        t3_slim = pd.DataFrame(columns=["Date", "Grid_AvgFreq_Hz",
                                         "Grid_FreqVariationIndex", "Grid_NormalBand_pct"])

    # International exchange from T6
    t6_keep = [c for c in ["Date", "Bhutan_Exchange_MU", "Bhutan_DayPeak_MW",
                            "Nepal_Exchange_MU", "Nepal_DayPeak_MW",
                            "Bangladesh_Exchange_MU", "Bangladesh_DayPeak_MW"]
               if t6 is not None and c in t6.columns]
    t6_slim = t6[t6_keep] if t6_keep and not t6.empty else pd.DataFrame(columns=["Date"])

    # Final join
    df = (base
          .pipe(_safe_merge, t2_all,  on="Date")
          .pipe(_safe_merge, t3_slim, on="Date")
          .pipe(_safe_merge, t6_slim, on="Date"))

    first = ["Date", "State", "Region",
             "Energy_Consumption_MU", "MaxDemand_MW", "PeakShortage_MW"]
    rest  = [c for c in df.columns if c not in first]
    return df[first + rest]


# ---------------------------------------------------------------------------
# National-level join  (one row per Date)
# ---------------------------------------------------------------------------

def _build_national_rows(tables):
    t2 = tables["t2"]
    t3 = tables["t3"]
    t6 = tables["t6"]
    t7 = tables["t7"]

    if not t2.empty and "Region" in t2.columns:
        t2_all = (t2[t2["Region"] == "AllIndia"][["Date", "EnergyMet_MU", "HydroGen_MU"]]
                  .rename(columns={"EnergyMet_MU": "AllIndia_EnergyMet_MU",
                                   "HydroGen_MU":  "AllIndia_HydroGen_MU"}))
    else:
        t2_all = pd.DataFrame(columns=["Date", "AllIndia_EnergyMet_MU", "AllIndia_HydroGen_MU"])

    t3_keep = ["Date", "AvgFreq_Hz", "FreqVariationIndex",
               "Freq_4990_5005_pct", "Freq_below_4990_pct"]
    t3_slim = (t3[[c for c in t3_keep if c in t3.columns]]
               if not t3.empty else pd.DataFrame(columns=t3_keep))

    t7_wide = _pivot_t7(t7)

    # Build from whichever frames have data
    frames = [f for f in [t2_all, t3_slim, t6, t7_wide]
              if f is not None and not f.empty and "Date" in f.columns]
    if not frames:
        return pd.DataFrame(columns=["Date"])

    df = frames[0]
    for other in frames[1:]:
        df = _safe_merge(df, other, on="Date", how="outer")
    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    pdf_files = sorted(glob.glob(os.path.join(PDF_DIR, "*.pdf")))
    print(f"\n  Found {len(pdf_files)} PDFs in {PDF_DIR}\n")

    state_chunks, national_chunks, failed = [], [], []

    for i, path in enumerate(pdf_files, 1):
        name = os.path.basename(path)
        print(f"  [{i:>2}/{len(pdf_files)}] {name}")

        tables = parse_pdf(path)
        if tables is None:
            failed.append(name)
            continue

        # Show per-table row counts for transparency
        shapes = {k: len(v) for k, v in tables.items()}
        print(f"         rows -> {shapes}")

        try:
            state_chunks.append(_build_state_rows(tables))
            national_chunks.append(_build_national_rows(tables))
        except Exception as e:
            print(f"    [JOIN ERROR] {name}: {e}")
            traceback.print_exc()
            failed.append(name)

    if not state_chunks:
        print("\n  No data assembled — all PDFs failed.\n")
        return

    print("\n  Assembling master CSVs...")

    master_state = (pd.concat(state_chunks, ignore_index=True)
                      .drop_duplicates(subset=["Date", "State"]))
    master_state["_sort"] = pd.to_datetime(master_state["Date"], format="%d-%m-%Y", errors="coerce")
    master_state = master_state.sort_values(["_sort", "Region", "State"]).drop(columns="_sort")

    master_nat = (pd.concat(national_chunks, ignore_index=True)
                    .drop_duplicates(subset=["Date"]))
    if "Date" in master_nat.columns:
        master_nat["_sort"] = pd.to_datetime(master_nat["Date"], format="%d-%m-%Y", errors="coerce")
        master_nat = master_nat.sort_values("_sort").drop(columns="_sort")

    sp = os.path.join(OUTPUT_DIR, "master_state_daily.csv")
    np_ = os.path.join(OUTPUT_DIR, "master_national_daily.csv")
    master_state.to_csv(sp,  index=False)
    master_nat.to_csv(np_,   index=False)

    print(f"\n  master_state_daily.csv    {len(master_state):>6,} rows x {len(master_state.columns)} cols")
    print(f"  master_national_daily.csv {len(master_nat):>6,} rows x {len(master_nat.columns)} cols")
    _dt = pd.to_datetime(master_state["Date"], format="%d-%m-%Y", errors="coerce")
    print(f"  Date range  : {_dt.min().strftime('%d-%m-%Y')}  ->  {_dt.max().strftime('%d-%m-%Y')}")
    print(f"  States      : {master_state['State'].nunique()} unique")
    print(f"  Saved to    : {OUTPUT_DIR}")
    if failed:
        print(f"\n  Failed ({len(failed)}): {failed}")
    print()

if __name__ == "__main__":
    main()