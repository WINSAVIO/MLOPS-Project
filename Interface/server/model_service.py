import datetime
import random
import xgboost as xgb
import joblib
import pandas as pd
import shap
import numpy as np
import os

import traceback

class ModelService:
    def __init__(self):
        try:
            now = datetime.datetime.now().isoformat()
            print(f"[{now}] Loading XGBoost Model Artifacts...")
            # Robust path discovery for Model Weights (Local vs Docker)
            possible_paths = [
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "Model Weights"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "Model Weights"),
                os.path.join(os.getcwd(), "Model Weights")
            ]
            base_path = next((p for p in possible_paths if os.path.exists(p)), possible_paths[0])
            print(f"[{now}] Using base_path: {base_path}")
            
            model_path = os.path.join(base_path, "generalized_xgboost_model.json")
            print(f"[{now}] Attempting to load booster from {model_path}...")
            self.booster = xgb.Booster()
            self.booster.load_model(model_path)
            print(f"[{now}] Booster loaded successfully.")
            
            features_path = os.path.join(base_path, "model_features.pkl")
            print(f"[{now}] Loading features from {features_path}...")
            self.features = joblib.load(features_path)
            
            baselines_path = os.path.join(base_path, "state_baselines.pkl")
            print(f"[{now}] Loading baselines from {baselines_path}...")
            self.state_baselines = joblib.load(baselines_path)
            
            try:
                print(f"[{now}] Initializing SHAP TreeExplainer...")
                self.explainer = shap.TreeExplainer(self.booster)
                print(f"[{now}] SHAP Explainer Loaded Successfully!")
            except Exception as se:
                print(f"[{now}] Warning: SHAP failed to load. Error: {se}")
                self.explainer = None
                
            print(f"[{now}] Model Service Initialization Complete!")
        except Exception as e:
            now = datetime.datetime.now().isoformat()
            print(f"[{now}] CRITICAL ERROR: Could not load model artifacts: {e}")
            self.booster = None
        
    def get_14_day_baseline(self):
        return {"status": "success", "message": "14-day baseline returned"}
        
    def predict_scenario_with_feedback(self, state_name: str, scenario):
        if self.booster is None:
            return {"error": "Model not loaded. Check server logs for file path issues."}

        # 1. Get Baseline - Favor the Frontend UI value for visual consistency
        # This prevents the "25k dip" when the UI is using scaled mock data (~60k) 
        # but the artifact might have a different historical value (~27k).
        ui_baseline = getattr(scenario, "current_baseline_mw", 0)
        
        artifact_baseline_mu = 0
        if hasattr(self, 'state_baselines') and isinstance(self.state_baselines, dict):
            artifact_baseline_mu = self.state_baselines.get(state_name, 0)
            
        artifact_baseline = (artifact_baseline_mu * 1000) / 24 if artifact_baseline_mu > 0 else 0
        
        # Use UI baseline first, then Artifact, then hard default
        baseline = ui_baseline if ui_baseline > 0 else (artifact_baseline if artifact_baseline > 0 else 5000)
        
        # 2. Incorporate Model's Expected Value (Internal SHAP Baseline)
        # TreeExplainer.expected_value is the average prediction in log-space.
        model_expected_val = 0
        if self.explainer is not None:
            # expected_value can be a list or a single float
            ev = self.explainer.expected_value
            model_expected_val = ev[0] if isinstance(ev, (list, np.ndarray)) else ev

        # The "True Scenario Baseline" for the UI is the starting point from the chart.
        true_scenario_baseline = baseline

        # Human-readable feature name mapping
        FEATURE_MAP = {
            "temperature_2m_max": "Max Temp",
            "relative_humidity_2m_mean": "Humidity",
            "cloudcover_mean": "Cloud Cover",
            "precipitation_sum": "Rainfall",
            "et0_fao_evapotranspiration": "Evaporation",
            "Is_Holiday": "Public Holiday",
            "is_weekend": "Weekend",
            "hour": "Hour of Day"
        }

        df_dict = {col: [0.0] for col in self.features}
        df = pd.DataFrame(df_dict)
        
        # Broad feature mapping to ensure sensitivity
        for col in df.columns:
            c = col.lower()
            if any(k in c for k in ['temperature', 'maxtemp', 'cdd', 'apparent']):
                df[col] = scenario.max_temperature
            if 'humidity' in c:
                df[col] = scenario.humidity
            if 'cloudcover' in c or 'radiation' in c:
                df[col] = scenario.cloud_cover
            if 'precipitation' in c:
                df[col] = scenario.precipitation
            if 'et0' in c or 'evapo' in c:
                df[col] = scenario.evapotranspiration
            if 'holiday' in c:
                df[col] = 1 if scenario.is_holiday else 0
                
        dmatrix = xgb.DMatrix(df[self.features])
        prediction = self.booster.predict(dmatrix)[0]
        
        multiplier = np.exp(prediction)
        multiplier = np.clip(multiplier, 0.7, 1.4) 
        final_mw = baseline * multiplier

        # SHAP calculation with percentage impacts
        top_shap = {}
        if self.explainer is not None:
            try:
                shap_vals = self.explainer.shap_values(df[self.features])[0]
                top_indices = np.argsort(np.abs(shap_vals))[-10:][::-1]
                
                for i in top_indices:
                    raw_name = self.features[i]
                    nice_name = FEATURE_MAP.get(raw_name, raw_name.replace("_", " ").title())
                    val = shap_vals[i]
                    
                    if abs(val) < 1e-4: continue 
                    
                    # Impact is relative to the internal model state
                    mw_impact = final_mw - (baseline * np.exp(prediction - val))
                    percent_impact = (np.exp(val) - 1) * 100
                    
                    sign = "+" if mw_impact >= 0 else ""
                    top_shap[nice_name] = f"{sign}{mw_impact:,.0f} MW ({sign}{percent_impact:+.1f}%)"
                    
            except Exception as e:
                print(f"Runtime SHAP error: {e}")
                top_shap = {"SHAP Error": str(e)}
        else:
            top_shap = {"Status": "SHAP Disabled in Cloud Run container."}
        
        return {
            "baseline_mw": float(true_scenario_baseline),
            "predicted_mw": float(final_mw),
            "shap_values": top_shap
        }

model_service = ModelService()
