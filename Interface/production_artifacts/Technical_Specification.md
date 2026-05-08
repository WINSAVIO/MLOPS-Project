# Technical Specification: Energy Demand Forecasting Interface (v2)

## Executive Summary
This document outlines the updated architecture for the Energy Demand Forecasting project. The primary pivot is moving from a static daily forecast to a **7-Day Upcoming Week Forecast**. The application will leverage Open-Meteo's weather forecasting to automatically predict energy consumption for the next week. Users can visualize this on a timeline, drill down into specific states on the map, and simulate complex "What-If" scenarios by altering all underlying model features.

## User Review Required
> [!IMPORTANT]
> Please review the new Weekly Forecasting flow and the manual Predict/Reset logic. If this aligns with your vision, I will begin implementing the changes.

## Requirements

### Functional Requirements
1. **7-Day Weekly Forecast Timeline (New):**
   - The main view will feature a Line Chart displaying the predicted energy consumption for the upcoming 7 days.
   - This chart acts as a controller: clicking a specific day updates the India Map and the Sidebar to reflect that day's specific values.
2. **Comprehensive Feature Sliders:**
   - The sidebar will expose **all** climate features used by the XGBoost model, not just placeholders. 
   - *Sliders:* Temperature, Humidity, Cloud Cover, Precipitation, Evapotranspiration, and the `Is Holiday` toggle.
3. **Manual Simulation Controls (Predict & Reset):**
   - **Initialization:** When a day is selected, sliders automatically populate with the *real forecasted baseline values* (from Open-Meteo/Calendar).
   - **Manual Predict:** Moving a slider will *not* trigger an immediate network request. Instead, a prominent `Predict (Recalculate)` button must be clicked to send the new scenario to the server.
   - **Reset:** A `Reset to Baseline` button will instantly revert all sliders to the real forecasted weather for that day.
4. **Macro to Micro Flow:**
   - The interactive SVG Map of India remains. Clicking a state filters the 7-day timeline and the SHAP explainability chart to that specific region.
5. **Prediction API Updates:**
   - `GET /api/forecast/baseline`: Fetches the pre-computed 7-day baseline forecast for all states based on Open-Meteo's weather API.
   - `POST /api/predict/scenario`: Accepts a modified feature payload, runs XGBoost inference, and returns updated MegaWatts and SHAP values.

### Non-Functional Requirements
1. **Performance:** The baseline 7-day forecast should be cached in memory or fetched instantly so the initial page load is rapid.
2. **Aesthetics & UI/UX:** The dashboard layout will be adapted to comfortably fit the 7-day timeline (top), the interactive map (bottom-left), and the comprehensive sidebar (right).

## Architecture & Tech Stack

### Frontend (Client)
- **Framework:** Next.js (React).
- **Styling:** Vanilla CSS / CSS Modules.
- **Visualizations:** `recharts` for the new 7-Day Line Chart and SHAP Waterfall Plot; `react-simple-maps` for the SVG map.

### Backend (Server)
- **Framework:** FastAPI (Python).
- **Scheduler:** APScheduler/Cron running every 14 days for the MLOps loop, plus a daily cron job to pull the latest 7-day Open-Meteo forecast and cache it.
- **ML Loading:** `xgboost`, `joblib`, and `pandas`.

## State Management & Data Flow
1. **Baseline Load:** On mount, frontend calls `GET /api/forecast/baseline`. Populates the 7-day chart and map.
2. **Selection:** User clicks "Day 3" on the timeline and "Maharashtra" on the map. Sidebar populates with Maharashtra's forecasted weather for Day 3.
3. **Scenario Simulation:** 
   - User increases `Temperature` and clicks `Predict`.
   - `POST /api/predict/scenario` is called with the new payload.
   - FastAPI returns the new prediction and SHAP explainability.
   - Frontend updates the chart (showing a diverging scenario line vs baseline) and updates the SHAP plot.

## Proposed Changes
### Interface Component

#### [MODIFY] `Interface/client/src/app/page.js`
- Restructure layout to include the 7-Day Timeline Chart.
- Add comprehensive sliders mapped to actual model features.
- Add `Predict` and `Reset` buttons.

#### [MODIFY] `Interface/server/main.py`
- Add `GET /forecast/baseline` to serve the 7-day default data.
- Update POST endpoints to handle the expanded scenario feature set.

## Verification Plan
1. Ensure the `Reset to Baseline` button accurately drops scenario state and returns to the API's default values.
2. Ensure the "Predict" button correctly halts any network traffic until explicitly clicked by the user.
