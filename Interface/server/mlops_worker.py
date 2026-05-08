import os
import sys
import glob
import datetime
import subprocess

# Ensure we can import from Model Training
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_TRAINING_DIR = os.path.join(ROOT_DIR, "Model Training")
if MODEL_TRAINING_DIR not in sys.path:
    sys.path.insert(0, MODEL_TRAINING_DIR)

import download_grid_india
import build_dataset
import fetch_climate_national

PDF_DIR = os.path.join(ROOT_DIR, "weekly_pdfs")
LOG_FILE = os.path.join(ROOT_DIR, "processed_files.log")

def get_last_run_date():
    if not os.path.exists(LOG_FILE):
        return None
    with open(LOG_FILE, "r") as f:
        for line in f:
            if line.startswith("LAST_RUN:"):
                date_str = line.split("LAST_RUN:")[1].strip()
                try:
                    return datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                except:
                    pass
    return None

def update_last_run():
    lines = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            lines = [line for line in f if not line.startswith("LAST_RUN:")]
    
    with open(LOG_FILE, "w") as f:
        f.write(f"LAST_RUN: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.writelines(lines)

def delete_processed_pdfs():
    print("🧹 Cleaning up stateless PDF storage...")
    pdfs = glob.glob(os.path.join(PDF_DIR, "*.pdf"))
    count = 0
    for pdf in pdfs:
        try:
            os.remove(pdf)
            count += 1
        except Exception as e:
            print(f"Failed to delete {pdf}: {e}")
    print(f"✅ Deleted {count} temporary PDFs.")

def sliding_window_retraining_loop():
    print(f"\n🚀 [{datetime.datetime.now()}] Starting MLOps Retraining Loop...\n")
    
    last_run = get_last_run_date()
    if last_run:
        days_passed = (datetime.datetime.now() - last_run).days
        if days_passed < 14:
            print(f"⏳ Only {days_passed} days have passed since last run. Skipping retraining to save compute.")
            return
            
    print("📥 STEP 1: Scraping new GRID-INDIA reports...")
    newly_downloaded = download_grid_india.main()
    
    if newly_downloaded < 2:
        print(f"⚠️ Only {newly_downloaded} new PDFs found. Waiting for at least 2 weeks of data before retraining.")
        # If we downloaded 1 PDF, we can delete it or keep it for next week. Let's delete to stay stateless.
        delete_processed_pdfs()
        return
        
    print(f"✅ Downloaded {newly_downloaded} new weekly reports.")
    
    print("\n⚙️ STEP 2: Extracting Tables from PDFs...")
    build_dataset.main()
    
    print("\n🌤️ STEP 3: Fetching Open-Meteo Climate Data...")
    fetch_climate_national.main()
    
    print("\n🔗 STEP 4: Merging Datasets & Injecting Holidays...")
    subprocess.run([sys.executable, os.path.join(ROOT_DIR, "Model Training", "dataset_merger.py")], check=True)
    
    print("\n🧠 STEP 5: Retraining XGBoost Model (Headless)...")
    notebook_path = os.path.join(ROOT_DIR, "Model Training", "Energy_Consumption_Model_Training.ipynb")
    subprocess.run([
        sys.executable, "-m", "jupyter", "nbconvert",
        "--to", "notebook",
        "--execute",
        "--inplace",
        "--ExecutePreprocessor.timeout=600",
        "--TagRemovePreprocessor.enabled=True",
        "--TagRemovePreprocessor.remove_cell_tags=skip-execution",
        notebook_path
    ], check=True)
    
    print("\n🧹 STEP 6: Deleting Ephemeral PDFs...")
    # Append the newly downloaded PDFs to the log before deleting them
    with open(LOG_FILE, "a") as f:
        for pdf in glob.glob(os.path.join(PDF_DIR, "*.pdf")):
            f.write(f"{os.path.basename(pdf)}\n")
            
    delete_processed_pdfs()
    
    print("\n🕒 STEP 7: Updating Schedule Log...")
    update_last_run()
    
    print(f"\n🎉 [{datetime.datetime.now()}] MLOps Pipeline Complete! New Model deployed to production.")

if __name__ == "__main__":
    sliding_window_retraining_loop()
