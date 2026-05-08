import pandas as pd
import holidays
import os

# 1. Configuration 
DATASET_DIR = r"C:\Users\Savio Winson\Desktop\Energy Consumption\dataset"
ENERGY_FILE = os.path.join(DATASET_DIR, "master_state_daily.csv")
CLIMATE_FILE = os.path.join(DATASET_DIR, "master_national_climate.csv")
FINAL_OUTPUT_FILE = os.path.join(DATASET_DIR, "final_mlops_dataset.csv")

# 2. Load the Datasets
print("📥 Loading datasets...")
energy_df = pd.read_csv(ENERGY_FILE)
climate_df = pd.read_csv(CLIMATE_FILE)

# Ensure Dates are strings in the exact same format (DD-MM-YYYY)
energy_df['Date'] = pd.to_datetime(energy_df['Date'], format='%d-%m-%Y').dt.strftime('%d-%m-%Y')
climate_df['Date'] = pd.to_datetime(climate_df['Date'], format='%d-%m-%Y').dt.strftime('%d-%m-%Y')

# 3. The Grand Merge
print("🔗 Merging Energy and Climate data...")
merged_df = pd.merge(energy_df, climate_df, on=['Date', 'State'], how='inner')

# 4. The Holiday Engine
print("🎉 Injecting Indian Public Holidays...")
in_holidays = holidays.India(years=[2023, 2024, 2025, 2026])

merged_df['Is_Holiday'] = pd.to_datetime(merged_df['Date'], format='%d-%m-%Y').apply(lambda x: 1 if x in in_holidays else 0)
merged_df['Day_Of_Week'] = pd.to_datetime(merged_df['Date'], format='%d-%m-%Y').dt.dayofweek
merged_df['Is_Weekend'] = merged_df['Day_Of_Week'].apply(lambda x: 1 if x >= 5 else 0)

# 5. THE FIX: Surgical Drop
print("🧹 Cleaning up initial null values (Surgical Drop)...")
# We ONLY drop the rows where our specific 7-day rolling climate features are NaN
merged_df = merged_df.dropna(subset=['Roll7_AvgMaxTemp'])

# 6. Save the Final MLOps Dataset
merged_df.to_csv(FINAL_OUTPUT_FILE, index=False)

print("✅ DONE!")
print(f"Final Dataset Shape: {merged_df.shape} (Should be ~38,000+ rows now!)")