import os
import time
import requests
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
OUTPUT_DIR = r"C:\Users\Savio Winson\Desktop\Energy Consumption\dataset\climate_states"
MASTER_FILE = r"C:\Users\Savio Winson\Desktop\Energy Consumption\dataset\master_national_climate.csv"

# Ensure our checkpoint directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

DATE_START = "2023-04-01"
DATE_END   = "2026-03-08"

# ---------------------------------------------------------------------------
# THE NATIONAL LOAD CENTER DICTIONARY (39 Regions matched to GRID-INDIA)
# Weights must sum to 1.0 for each state/entity.
# ---------------------------------------------------------------------------
NATIONAL_LOAD_CENTRES = {
    # === THE GIANTS (4 Nodes) ===
    "Maharashtra": {
        "Mumbai": {"lat": 19.076, "lon": 72.877, "weight": 0.30},
        "Pune": {"lat": 18.520, "lon": 73.857, "weight": 0.25},
        "Nagpur": {"lat": 21.145, "lon": 79.088, "weight": 0.25},
        "Aurangabad": {"lat": 19.877, "lon": 75.343, "weight": 0.20}
    },
    "Gujarat": {
        "Ahmedabad": {"lat": 23.022, "lon": 72.571, "weight": 0.35},
        "Surat": {"lat": 21.170, "lon": 72.831, "weight": 0.35},
        "Rajkot": {"lat": 22.303, "lon": 70.802, "weight": 0.15},
        "Vadodara": {"lat": 22.307, "lon": 73.181, "weight": 0.15}
    },
    "UP": {  # Mapped as "UP" in your CSV
        "Lucknow": {"lat": 26.846, "lon": 80.946, "weight": 0.30},
        "Kanpur": {"lat": 26.449, "lon": 80.331, "weight": 0.30},
        "Noida": {"lat": 28.535, "lon": 77.391, "weight": 0.25},
        "Varanasi": {"lat": 25.317, "lon": 82.973, "weight": 0.15}
    },
    "Rajasthan": {
        "Jaipur": {"lat": 26.912, "lon": 75.787, "weight": 0.35},
        "Jodhpur": {"lat": 26.238, "lon": 73.024, "weight": 0.25},
        "Udaipur": {"lat": 24.585, "lon": 73.712, "weight": 0.20},
        "Bikaner": {"lat": 28.022, "lon": 73.311, "weight": 0.20}
    },

    # === LARGE / MEDIUM STATES (2-3 Nodes) ===
    "Tamil Nadu": {
        "Chennai": {"lat": 13.082, "lon": 80.270, "weight": 0.40},
        "Coimbatore": {"lat": 11.016, "lon": 76.955, "weight": 0.35},
        "Madurai": {"lat": 9.925, "lon": 78.119, "weight": 0.25}
    },
    "Karnataka": {
        "Bengaluru": {"lat": 12.971, "lon": 77.594, "weight": 0.50},
        "Mysuru": {"lat": 12.295, "lon": 76.639, "weight": 0.25},
        "Hubballi": {"lat": 15.364, "lon": 75.123, "weight": 0.25}
    },
    "Andhra Pradesh": {
        "Visakhapatnam": {"lat": 17.686, "lon": 83.218, "weight": 0.45},
        "Vijayawada": {"lat": 16.506, "lon": 80.648, "weight": 0.35},
        "Tirupati": {"lat": 13.628, "lon": 79.419, "weight": 0.20}
    },
    "Telangana": {
        "Hyderabad": {"lat": 17.385, "lon": 78.486, "weight": 0.70},
        "Warangal": {"lat": 17.981, "lon": 79.531, "weight": 0.30}
    },
    "MP": {  # Mapped as "MP" in your CSV
        "Indore": {"lat": 22.719, "lon": 75.857, "weight": 0.40},
        "Bhopal": {"lat": 23.259, "lon": 77.412, "weight": 0.35},
        "Jabalpur": {"lat": 23.181, "lon": 79.986, "weight": 0.25}
    },
    "West Bengal": {
        "Kolkata": {"lat": 22.572, "lon": 88.363, "weight": 0.60},
        "Asansol": {"lat": 23.673, "lon": 86.952, "weight": 0.40}
    },
    "Kerala": {
        "Kochi": {"lat": 9.931, "lon": 76.267, "weight": 0.60},
        "Thiruvananthapuram": {"lat": 8.524, "lon": 76.936, "weight": 0.40}
    },
    "Bihar": {
        "Patna": {"lat": 25.594, "lon": 85.137, "weight": 0.60},
        "Gaya": {"lat": 24.791, "lon": 85.000, "weight": 0.40}
    },
    "Odisha": {
        "Bhubaneswar": {"lat": 20.296, "lon": 85.824, "weight": 0.60},
        "Rourkela": {"lat": 22.260, "lon": 84.853, "weight": 0.40}
    },
    "Punjab": {
        "Ludhiana": {"lat": 30.900, "lon": 75.857, "weight": 0.60},
        "Amritsar": {"lat": 31.634, "lon": 74.872, "weight": 0.40}
    },
    "Haryana": {
        "Gurugram": {"lat": 28.459, "lon": 77.026, "weight": 0.60},
        "Panipat": {"lat": 29.390, "lon": 76.970, "weight": 0.40}
    },
    "Chhattisgarh": {
        "Raipur": {"lat": 21.251, "lon": 81.629, "weight": 0.60},
        "Bhilai": {"lat": 21.193, "lon": 81.350, "weight": 0.40}
    },
    "J&K": {  # Mapped as "J&K" in your CSV
        "Srinagar": {"lat": 34.083, "lon": 74.797, "weight": 0.50},
        "Jammu": {"lat": 32.726, "lon": 74.857, "weight": 0.50}
    },
    "Jharkhand": {
        "Ranchi": {"lat": 23.344, "lon": 85.309, "weight": 0.50},
        "Jamshedpur": {"lat": 22.804, "lon": 86.202, "weight": 0.50}
    },

    # === SMALL STATES / UTs (1 Node) ===
    "Delhi": {"New Delhi": {"lat": 28.613, "lon": 77.209, "weight": 1.0}},
    "Goa": {"Panaji": {"lat": 15.490, "lon": 73.827, "weight": 1.0}},
    "Tripura": {"Agartala": {"lat": 23.831, "lon": 91.286, "weight": 1.0}},
    "Assam": {"Guwahati": {"lat": 26.144, "lon": 91.736, "weight": 1.0}},
    "Sikkim": {"Gangtok": {"lat": 27.338, "lon": 88.606, "weight": 1.0}},
    "Chandigarh": {"Chandigarh": {"lat": 30.733, "lon": 76.779, "weight": 1.0}},
    "Arunachal Pradesh": {"Itanagar": {"lat": 27.084, "lon": 93.605, "weight": 1.0}},
    "Manipur": {"Imphal": {"lat": 24.817, "lon": 93.936, "weight": 1.0}},
    "Meghalaya": {"Shillong": {"lat": 25.578, "lon": 91.893, "weight": 1.0}},
    "Mizoram": {"Aizawl": {"lat": 23.727, "lon": 92.717, "weight": 1.0}},
    "Nagaland": {"Kohima": {"lat": 25.670, "lon": 94.107, "weight": 1.0}},
    "HP": {"Shimla": {"lat": 31.104, "lon": 77.173, "weight": 1.0}}, # Himachal Pradesh
    "Uttarakhand": {"Dehradun": {"lat": 30.316, "lon": 78.032, "weight": 1.0}},
    "Pondy": {"Puducherry": {"lat": 11.941, "lon": 79.808, "weight": 1.0}},

    # === DIRECT GRID CONNECTIONS (Factories & Railways) ===
    # We assign their direct geographical coordinates so the model understands their ambient weather
    "AMNSIL": {"Hazira_Steel_Plant": {"lat": 21.111, "lon": 72.637, "weight": 1.0}},
    "RIL_Jamnagar": {"Reliance_Refinery": {"lat": 22.355, "lon": 69.962, "weight": 1.0}},
    "BALCO": {"Korba_Aluminium": {"lat": 22.348, "lon": 82.698, "weight": 1.0}},
    "DVC": {"Damodar_Valley": {"lat": 23.673, "lon": 86.952, "weight": 1.0}},
    "DNHDDPDCL": {"Silvassa": {"lat": 20.276, "lon": 73.008, "weight": 1.0}},
    "Railways_ER": { # Eastern Railways (Blended Kolkata & Patna proxy)
        "ER_HQ_Kolkata": {"lat": 22.572, "lon": 88.363, "weight": 0.50},
        "ER_Patna": {"lat": 25.594, "lon": 85.137, "weight": 0.50}
    },
    "Railways_NR": { # Northern Railways (Blended Delhi & Lucknow proxy)
        "NR_HQ_Delhi": {"lat": 28.613, "lon": 77.209, "weight": 0.50},
        "NR_Lucknow": {"lat": 26.846, "lon": 80.946, "weight": 0.50}
    }
}

DAILY_VARS = [
    "temperature_2m_max", "temperature_2m_min", "temperature_2m_mean", 
    "relative_humidity_2m_mean", "precipitation_sum", "shortwave_radiation_sum", 
    "windspeed_10m_max", "et0_fao_evapotranspiration", "cloudcover_mean", "apparent_temperature_max"
]

BASE_URL = "https://archive-api.open-meteo.com/v1/archive"

# ---------------------------------------------------------------------------
# CORE FUNCTIONS (Reused from previous logic)
# ---------------------------------------------------------------------------
def fetch_city(city_name, lat, lon):
    params = {
        "latitude": lat, "longitude": lon, "start_date": DATE_START,
        "end_date": DATE_END, "daily": ",".join(DAILY_VARS), "timezone": "Asia/Kolkata"
    }
    for attempt in range(1, 4):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
            df = pd.DataFrame(resp.json()["daily"])
            df["date"] = pd.to_datetime(df["time"])
            return df.drop(columns=["time"]).set_index("date")
        except Exception as e:
            time.sleep(2 ** attempt)
    return pd.DataFrame()

def process_state(state_name, load_centers):
    city_frames = {}
    for city, cfg in load_centers.items():
        df = fetch_city(city, cfg["lat"], cfg["lon"])
        if not df.empty:
            city_frames[city] = (df, cfg["weight"])
        time.sleep(1) # API Rate limit protection

    if not city_frames:
        return None

    ref_index = list(city_frames.values())[0][0].index
    state_daily = pd.DataFrame(index=ref_index)

    for var in DAILY_VARS:
        state_daily[var] = sum(frame[var] * weight for frame, weight in city_frames.values() if var in frame.columns)
    
    # Feature Engineering
    T = state_daily["temperature_2m_mean"]
    state_daily["Heat_Stress_Index"] = state_daily["temperature_2m_max"] * (1 + (state_daily["relative_humidity_2m_mean"] / 100))
    state_daily["CDD_18"] = (T - 18).clip(lower=0)
    state_daily["Is_Extreme_Heat_Day"] = (state_daily["temperature_2m_max"] >= 38).astype(int)

    # Rolling Weekly Features
    cols_to_roll = {
        "temperature_2m_max": "Roll7_AvgMaxTemp",
        "Heat_Stress_Index": "Roll7_AvgHeatStress",
        "CDD_18": "Roll7_AvgCDD",
        "cloudcover_mean": "Roll7_AvgCloudCover",
        "apparent_temperature_max": "Roll7_AvgApparentTemp"
    }
    for src, dst in cols_to_roll.items():
        state_daily[dst] = state_daily[src].shift(1).rolling(7, min_periods=1).mean()
        
    state_daily["Roll7_TotalPrecip"] = state_daily["precipitation_sum"].shift(1).rolling(7, min_periods=1).sum()
    state_daily["Roll7_TotalEvapo"] = state_daily["et0_fao_evapotranspiration"].shift(1).rolling(7, min_periods=1).sum()
    state_daily["Days_Above_38C_Week"] = state_daily["Is_Extreme_Heat_Day"].shift(1).rolling(7, min_periods=1).sum().fillna(0).astype(int)

    # Format
    out = state_daily.reset_index()
    out.rename(columns={"date": "Date"}, inplace=True)
    out["Date"] = out["Date"].dt.strftime("%d-%m-%Y")
    out.insert(1, "State", state_name)
    
    return out

# ---------------------------------------------------------------------------
# MAIN EXECUTION LOOP (With Checkpoints)
# ---------------------------------------------------------------------------
def main():
    print("🚀 Starting National Climate Data Extraction...")
    all_states_data = []

    for state, load_centers in NATIONAL_LOAD_CENTRES.items():
        save_path = os.path.join(OUTPUT_DIR, f"climate_{state.replace(' ', '_')}.csv")
        
        # 1. Checkpoint Logic
        if os.path.exists(save_path):
            print(f"⏭️ Skipping {state}... File already exists.")
            df = pd.read_csv(save_path)
            all_states_data.append(df)
            continue
            
        print(f"📥 Fetching data for {state} ({len(load_centers)} Load Centers)...")
        df = process_state(state, load_centers)
        
        if df is not None:
            df.to_csv(save_path, index=False)
            all_states_data.append(df)
            print(f"   ✅ Saved {state}")
        
        # 2. Rate Limiting Logic
        time.sleep(2) # Rest between states so Open-Meteo doesn't block us

    # 3. Create the Master Dataset
    print("\n🔗 Compiling National Master Dataset...")
    master_df = pd.concat(all_states_data, ignore_index=True)
    master_df.to_csv(MASTER_FILE, index=False)
    print(f"🎉 DONE! National dataset saved to {MASTER_FILE}")
    print(f"   Total Rows: {len(master_df)}")

if __name__ == "__main__":
    main()