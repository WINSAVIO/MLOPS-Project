import os
import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

OUTPUT_DIR = r"C:\Users\Savio Winson\Desktop\Energy Consumption\dataset\forecast_states"
MASTER_FILE = r"C:\Users\Savio Winson\Desktop\Energy Consumption\dataset\master_national_forecast.csv"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Using a subset of states for quick feasibility testing, including one Giant, one Medium, one Small
NATIONAL_LOAD_CENTRES = {
    "Maharashtra": {
        "Mumbai": {"lat": 19.076, "lon": 72.877, "weight": 0.30},
        "Pune": {"lat": 18.520, "lon": 73.857, "weight": 0.25},
        "Nagpur": {"lat": 21.145, "lon": 79.088, "weight": 0.25},
        "Aurangabad": {"lat": 19.877, "lon": 75.343, "weight": 0.20}
    },
    "Tamil Nadu": {
        "Chennai": {"lat": 13.082, "lon": 80.270, "weight": 0.40},
        "Coimbatore": {"lat": 11.016, "lon": 76.955, "weight": 0.35},
        "Madurai": {"lat": 9.925, "lon": 78.119, "weight": 0.25}
    },
    "Delhi": {"New Delhi": {"lat": 28.613, "lon": 77.209, "weight": 1.0}}
}

# In the Forecast API, 'cloudcover_mean' might not be available, trying 'precipitation_sum', etc.
# We will use what is commonly available in the free Open-Meteo Forecast API
DAILY_VARS = [
    "temperature_2m_max", "temperature_2m_min", "temperature_2m_mean", 
    "apparent_temperature_max", "precipitation_sum", 
    "et0_fao_evapotranspiration", "windspeed_10m_max", "shortwave_radiation_sum"
]

BASE_URL = "https://api.open-meteo.com/v1/forecast"

def fetch_city_forecast(city_name, lat, lon):
    params = {
        "latitude": lat, 
        "longitude": lon, 
        "daily": ",".join(DAILY_VARS), 
        "timezone": "Asia/Kolkata",
        "forecast_days": 14
    }
    resp = requests.get(BASE_URL, params=params, timeout=10)
    
    # If a variable is not found in the forecast API, Open-Meteo returns a 400 with details.
    if resp.status_code != 200:
        print(f"Error fetching {city_name}: {resp.text}")
        return pd.DataFrame()
        
    df = pd.DataFrame(resp.json()["daily"])
    df["date"] = pd.to_datetime(df["time"])
    return df.drop(columns=["time"]).set_index("date")

def process_state_forecast(state_name, load_centers):
    city_frames = {}
    for city, cfg in load_centers.items():
        df = fetch_city_forecast(city, cfg["lat"], cfg["lon"])
        if not df.empty:
            city_frames[city] = (df, cfg["weight"])
        time.sleep(0.5)

    if not city_frames:
        return None

    ref_index = list(city_frames.values())[0][0].index
    state_daily = pd.DataFrame(index=ref_index)

    for var in DAILY_VARS:
        state_daily[var] = sum(frame[var] * weight for frame, weight in city_frames.values() if var in frame.columns)
    
    # Simple feature engineering for the forecast data
    T = state_daily["temperature_2m_mean"]
    state_daily["CDD_18"] = (T - 18).clip(lower=0)
    state_daily["Is_Extreme_Heat_Day"] = (state_daily["temperature_2m_max"] >= 38).astype(int)

    out = state_daily.reset_index()
    out.rename(columns={"date": "Date"}, inplace=True)
    # Output date format like the user asked: 07/05/2026\nThursday
    # For CSV we'll just keep the standard datetime or string, and format in the UI. 
    # But to test exactly what they asked, we can format it here.
    out["Date_Display"] = out["Date"].dt.strftime("%d/%m/%Y\n%A")
    out.insert(1, "State", state_name)
    
    return out

def main():
    print("Testing Feasibility: 14-Day Forecast Data Extraction...")
    all_states_data = []

    for state, load_centers in NATIONAL_LOAD_CENTRES.items():
        print(f"Fetching 14-day forecast for {state}...")
        df = process_state_forecast(state, load_centers)
        
        if df is not None and not df.empty:
            all_states_data.append(df)
            print(f"   Success for {state}. Rows: {len(df)}")
            print(df[["Date_Display", "temperature_2m_max", "precipitation_sum"]].head(3))

    if all_states_data:
        master_df = pd.concat(all_states_data, ignore_index=True)
        master_df.to_csv(MASTER_FILE, index=False)
        print(f"\nFEASIBILITY PROVEN! 14-Day Forecast dataset saved to {MASTER_FILE}")
        print(f"   Total Rows: {len(master_df)}")

if __name__ == "__main__":
    main()
