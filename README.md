# GridSight: AI-Powered Energy Forecasting

## 🌍 Project Overview
This project is an end-to-end MLOps pipeline designed to forecast short-term electricity consumption for Indian states. Moving beyond static, sanitized datasets, this system dynamically extracts multi-modal data (Energy, Climate, Calendar), engineers domain-specific features, and trains a Highly Generalized Explainable AI (XAI) model capable of predicting grid fluctuations.

## 🛠️ Steps & Implementation
Our architecture uses an **Exogenous-Driven Pipeline** to bypass the reactive nature of pure time-series modeling.

### 1. Data Engineering Pipeline
* **Automated Data Ingestion:** A custom data pipeline utilizes `cloudscraper` and aggressive Regex to bypass government Web Application Firewalls (WAFs) and dynamically download Weekly Performance Reports (PDFs) from GRID-INDIA.
* **Tabular Extraction:** Utilizing `pdfplumber` to safely parse complex, merged-cell PDF tables into clean Pandas DataFrames.
* **Multi-Modal Feature Engineering:** Integrating historical energy lags with live Open-Meteo climate data (Temperature, Humidity, Cloud Cover, Evapotranspiration) and regional public holiday calendars. 
* **Target Normalization:** To eliminate the massive scale differences between states (e.g., Maharashtra vs. Goa), we engineered a new target predicting the **Logarithmic Change** (Log Returns) of energy consumption based on a 7-day rolling baseline. This neutralizes state sizes and forces the model to learn pure climate/behavioral patterns.

### 2. Modeling & Explainable AI (SHAP)
The optimized XGBoost Regressor predicts Log Change, achieving enterprise-grade accuracy ($R^2$: 0.9957). We use SHAP (SHapley Additive exPlanations) to extract the underlying decision logic:
* **Calendar is King:** `Day_Of_Week` and `Is_Holiday` are the strongest drivers, correctly identifying that the most violent grid drops occur when factories and offices close.
* **Physics over Geography:** Climate features like `Cooling Degree Days (CDD_18)` and `Precipitation` dominate predictions. Heavy rainfall cools the environment and drastically reduces grid demand, effectively creating a fully generalized model independent of geographical bounds.

### 3. Full-Stack Dashboard
* **The Backend (FastAPI):** A live inference API that receives raw weather forecasts from the client, generates the Log Change prediction via the exported XGBoost model, and applies the state baselines to return real MegaWatt (MW) predictions.
* **The Frontend (Next.js):** An interactive geographical dashboard using React Simple Maps. Users can click on specific states to initiate a 14-day forecast and manipulate "What-If" scenario sliders (Max Temperature, Cloud Cover, Holidays) to dynamically see grid impacts in real-time.

---

## 🚀 Setup & Run Guide

### 1. Repository Setup
First, clone the repository and navigate into the root directory.
```bash
git clone <your-repo-url>
cd "Energy Consumption"
```

### 2. Install Python Dependencies (Backend & ML)
We use a single `requirements.txt` file located in the root to power both the ML training notebooks and the FastAPI server.
```bash
# Create and activate a virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\Activate.ps1
# On Linux/Mac:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run the FastAPI Backend
Navigate to the server directory and start Uvicorn.
```bash
cd Interface/server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
*The backend will now listen for API requests on `http://localhost:8000`.*

### 4. Run the Next.js Frontend
Open a **new terminal window**, navigate to the client directory, and install the Node dependencies before starting the development server.
```bash
cd Interface/client
npm install
npm run dev
```
*The interactive dashboard is now live at `http://localhost:3000`!*