from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from model_service import model_service

app = FastAPI(title="Energy Demand Forecasting API (14-Day)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScenarioRequest(BaseModel):
    date_index: int  # 0 to 13
    max_temperature: float
    humidity: float
    cloud_cover: float
    precipitation: float
    evapotranspiration: float
    is_holiday: bool
    current_baseline_mw: float = 5000.0  # Allow frontend to pass its dynamic baseline

@app.get("/")
def health_check():
    return {"status": "ok"}

@app.get("/api/forecast/baseline")
def get_baseline_forecast():
    # Returns the 14-day baseline for the National View and default state views
    return model_service.get_14_day_baseline()

@app.post("/api/predict/scenario")
def predict_scenario(state_name: str, scenario: ScenarioRequest):
    # Runs the iterative feedback loop starting from `scenario.date_index`
    return model_service.predict_scenario_with_feedback(state_name, scenario)
