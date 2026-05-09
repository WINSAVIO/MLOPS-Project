import os
from fastapi import FastAPI, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from model_service import model_service

# Initialize Rate Limiter
limiter = Limiter(key_func=get_remote_address)

# Disable Swagger/ReDoc in production to prevent schema leakage
SHOW_DOCS = os.getenv("ENVIRONMENT") == "development"

app = FastAPI(
    title="GridSight API (14-Day Forecast)",
    docs_url="/docs" if SHOW_DOCS else None,
    redoc_url="/redoc" if SHOW_DOCS else None,
    openapi_url="/openapi.json" if SHOW_DOCS else None
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Secure CORS Policy
# During local dev, fallback to localhost. In production, provide the Vercel domain.
ALLOWED_ORIGIN = os.getenv("FRONTEND_URL", "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
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
@limiter.limit("60/minute")
def get_baseline_forecast(request: Request):
    # Returns the 14-day baseline for the National View and default state views
    return model_service.get_14_day_baseline()

@app.post("/api/predict/scenario")
@limiter.limit("60/minute")
def predict_scenario(request: Request, state_name: str, scenario: ScenarioRequest):
    # Runs the iterative feedback loop starting from `scenario.date_index`
    return model_service.predict_scenario_with_feedback(state_name, scenario)
