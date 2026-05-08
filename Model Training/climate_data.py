"""
fetch_climate_maharashtra.py
============================
Fetches historical daily weather from Open-Meteo Archive API for Maharashtra
using Load-Centre Averaging across 4 major cities.
Includes advanced grid-specific features (Evapotranspiration, Cloud Cover, Apparent Temp).
"""

import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# CONFIGURATION 
# ---------------------------------------------------------------------------
OUTPUT_PATH = r"C:\Users\Savio Winson\Desktop\Energy Consumption\dataset\climate_maharashtra.csv"

DATE_START = "2023-04-01"   
DATE_END   = "2026-03-08"   

STATE_NAME = "Maharashtra"  

MAX_RETRIES    = 4
RETRY_DELAY_S  = 5
REQUEST_TIMEOUT = 30
SLEEP_BETWEEN  = 0.5        

# ---------------------------------------------------------------------------
# LOAD CENTRES
# ---------------------------------------------------------------------------
LOAD_CENTRES = {
    "Mumbai":      {"lat": 19.076, "lon": 72.877, "weight": 0.30},
    "Pune":        {"lat": 18.520, "lon": 73.857, "weight": 0.25},
    "Nagpur":      {"lat": 21.145, "lon": 79.088, "weight": 0.25},
    "Aurangabad":  {"lat": 19.877, "lon": 75.343, "weight": 0.20},
}

# --- THE 3 NEW ADVANCED FEATURES ARE ADDED HERE ---
DAILY_VARS = [
    "temperature_2m_max",           # Peak daytime temp
    "temperature_2m_min",           # Night minimum
    "temperature_2m_mean",          # Mean temp
    "relative_humidity_2m_mean",    # Humidity
    "precipitation_sum",            # Monsoon indicator
    "shortwave_radiation_sum",      # Solar proxy
    "windspeed_10m_max",            # Wind proxy
    "et0_fao_evapotranspiration",   # Agricultural Pumping indicator (NEW)
    "cloudcover_mean",              # Lighting Load / Solar Masking (NEW)
    "apparent_temperature_max"      # Native "Feels Like" Heat Index (NEW)
]

BASE_URL = "https://archive-api.open-meteo.com/v1/archive"

# ---------------------------------------------------------------------------
# STEP 1 — Fetch daily data 
# ---------------------------------------------------------------------------
def fetch_city(city_name: str, lat: float, lon: float) -> pd.DataFrame:
    params = {
        "latitude":   lat,
        "longitude":  lon,
        "start_date": DATE_START,
        "end_date":   DATE_END,
        "daily":      ",".join(DAILY_VARS),
        "timezone":   "Asia/Kolkata",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            if "daily" not in data:
                raise ValueError(f"Unexpected API response: {list(data.keys())}")

            df = pd.DataFrame(data["daily"])
            df["date"] = pd.to_datetime(df["time"])
            df = df.drop(columns=["time"]).set_index("date")
            df.columns = [f"{col}" for col in df.columns]
            print(f"    OK  {city_name:<14} {len(df)} days")
            return df

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else "?"
            print(f"    Attempt {attempt}/{MAX_RETRIES} — HTTP {status}: {e}")
        except requests.exceptions.ConnectionError:
            print(f"    Attempt {attempt}/{MAX_RETRIES} — Connection error")
        except Exception as e:
            print(f"    Attempt {attempt}/{MAX_RETRIES} — {type(e).__name__}: {e}")

        if attempt < MAX_RETRIES:
            wait = RETRY_DELAY_S * (2 ** (attempt - 1))   
            print(f"    Waiting {wait}s before retry...")
            time.sleep(wait)

    raise RuntimeError(f"Failed to fetch {city_name} after {MAX_RETRIES} attempts")

# ---------------------------------------------------------------------------
# STEP 2 — Fetch all cities and compute weighted geographic average
# ---------------------------------------------------------------------------
def fetch_all_cities() -> pd.DataFrame:
    city_frames = {}
    total_weight = sum(v["weight"] for v in LOAD_CENTRES.values())

    for city, cfg in LOAD_CENTRES.items():
        print(f"  Fetching {city}...")
        df = fetch_city(city, cfg["lat"], cfg["lon"])
        city_frames[city] = (df, cfg["weight"] / total_weight)
        time.sleep(SLEEP_BETWEEN)

    reference_index = list(city_frames.values())[0][0].index
    state_daily = pd.DataFrame(index=reference_index)

    for var in DAILY_VARS:
        weighted_col = sum(
            frame[var] * weight
            for frame, weight in city_frames.values()
            if var in frame.columns
        )
        state_daily[var] = weighted_col

    print(f"\n  Load-centre weighted average complete: {len(state_daily)} days")
    return state_daily

# ---------------------------------------------------------------------------
# STEP 3 — Feature engineering (daily level)
# ---------------------------------------------------------------------------
def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    T    = df["temperature_2m_mean"]
    Tmax = df["temperature_2m_max"]
    Tmin = df["temperature_2m_min"]
    RH   = df["relative_humidity_2m_mean"]

    df["Heat_Stress_Index"] = Tmax * (1 + (RH / 100))
    df["CDD_18"] = (T - 18).clip(lower=0)
    df["HDD_15"] = (15 - T).clip(lower=0)

    steadman = (
        -8.78469 + 1.61139411 * T + 2.33854883 * RH
        - 0.14611605 * T * RH - 0.01230809 * T**2
        - 0.01642482 * RH**2
    )
    df["Heat_Index_Steadman"] = np.where(T >= 27, steadman, T)
    df["Is_Monsoon_Day"] = (df["precipitation_sum"] >= 5).astype(int)

    max_solar_mj = 30.0 
    df["Solar_Availability"] = (df["shortwave_radiation_sum"] / max_solar_mj).clip(0, 1)
    df["Temp_Range"] = Tmax - Tmin
    df["Is_Extreme_Heat_Day"] = (Tmax >= 38).astype(int)

    return df

# ---------------------------------------------------------------------------
# STEP 4 — Rolling weekly aggregations 
# ---------------------------------------------------------------------------
def add_rolling_weekly_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["Roll7_AvgMaxTemp"]    = df["temperature_2m_max"].shift(1).rolling(7, min_periods=1).mean()
    df["Roll7_AvgHeatStress"] = df["Heat_Stress_Index"].shift(1).rolling(7, min_periods=1).mean()
    df["Roll7_TotalPrecip"]   = df["precipitation_sum"].shift(1).rolling(7, min_periods=1).sum()
    df["Roll7_AvgCDD"]        = df["CDD_18"].shift(1).rolling(7, min_periods=1).mean()
    df["Days_Above_38C_Week"] = df["Is_Extreme_Heat_Day"].shift(1).rolling(7, min_periods=1).sum().fillna(0).astype(int)

    # --- AGGREGATING THE NEW FEATURES ---
    # Total Evapotranspiration over the last 7 days (Sum)
    df["Roll7_TotalEvapo"] = df["et0_fao_evapotranspiration"].shift(1).rolling(7, min_periods=1).sum()
    
    # Average Cloud Cover over the last 7 days (Mean)
    df["Roll7_AvgCloudCover"] = df["cloudcover_mean"].shift(1).rolling(7, min_periods=1).mean()
    
    # Average "Feels Like" Max Temp over the last 7 days (Mean)
    df["Roll7_AvgApparentTemp"] = df["apparent_temperature_max"].shift(1).rolling(7, min_periods=1).mean()

    return df

# ---------------------------------------------------------------------------
# STEP 5 — Format for join
# ---------------------------------------------------------------------------
def format_for_join(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.index.name = "date"
    out = out.reset_index()
    out["Date"]  = out["date"].dt.strftime("%d-%m-%Y")
    out["State"] = STATE_NAME
    out = out.drop(columns=["date"])

    cols = ["Date", "State"] + [c for c in out.columns if c not in ("Date", "State")]
    return out[cols]

# ---------------------------------------------------------------------------
# WEEKLY SUMMARY TABLE 
# ---------------------------------------------------------------------------
def build_weekly_summary(daily_df: pd.DataFrame) -> pd.DataFrame:
    tmp = daily_df.copy()
    tmp.index = pd.to_datetime(tmp["Date"], format="%d-%m-%Y")
    tmp = tmp.drop(columns=["Date", "State"])

    weekly = pd.DataFrame()
    weekly["Week_End_Sun"]        = tmp.resample("W-SUN").last().index
    weekly["Avg_MaxTemp_C"]       = tmp["temperature_2m_max"].resample("W-SUN").mean().values
    weekly["Avg_ApparentTemp_C"]  = tmp["apparent_temperature_max"].resample("W-SUN").mean().values # NEW
    weekly["Avg_Humidity_pct"]    = tmp["relative_humidity_2m_mean"].resample("W-SUN").mean().values
    weekly["Avg_CloudCover_pct"]  = tmp["cloudcover_mean"].resample("W-SUN").mean().values # NEW
    weekly["Avg_HeatStressIndex"] = tmp["Heat_Stress_Index"].resample("W-SUN").mean().values
    weekly["Avg_CDD_18"]          = tmp["CDD_18"].resample("W-SUN").mean().values
    weekly["Total_Precip_mm"]     = tmp["precipitation_sum"].resample("W-SUN").sum().values
    weekly["Total_Evapo_mm"]      = tmp["et0_fao_evapotranspiration"].resample("W-SUN").sum().values # NEW
    weekly["Days_Above_38C"]      = tmp["Is_Extreme_Heat_Day"].resample("W-SUN").sum().astype(int).values
    weekly["Avg_SolarAvail"]      = tmp["Solar_Availability"].resample("W-SUN").mean().values

    return weekly.reset_index(drop=True)

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("Maharashtra Climate Data Fetcher — Open-Meteo Archive API")
    print("=" * 60)
    print(f"Period : {DATE_START} → {DATE_END}")
    print(f"Cities : {', '.join(LOAD_CENTRES.keys())}")
    print()

    state_daily = fetch_all_cities()
    state_daily = engineer_features(state_daily)
    state_daily = add_rolling_weekly_features(state_daily)
    output = format_for_join(state_daily)

    output.to_csv(OUTPUT_PATH, index=False)
    
    weekly_path = OUTPUT_PATH.replace("climate_maharashtra.csv", "climate_maharashtra_weekly_summary.csv")
    weekly = build_weekly_summary(output)
    weekly.to_csv(weekly_path, index=False)

    print("\n" + "=" * 60)
    print("DONE: Added Evapotranspiration, Cloud Cover, and Apparent Temp!")

if __name__ == "__main__":
    main()