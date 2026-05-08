# GridSight — Production Deployment Walkthrough
## GCP Cloud Run (Backend) + Vercel (Frontend) | Region: asia-south1 (Mumbai)

This document provides the exact configuration and commands used to deploy the production-ready GridSight pipeline.

---

## Infrastructure Overview

| Component | Provider | Region | URL |
|-----------|----------|--------|-----|
| **Backend API** | GCP Cloud Run | `asia-south1` | [Backend Link](https://gridsight-backend-585052320054.asia-south1.run.app) |
| **Dashboard** | Vercel | `Production` | [Dashboard Link](https://gridsight-blush.vercel.app) |
| **Artifacts** | Artifact Registry | `asia-south1` | `gridsight` repository |

---

## PART 1 — Backend Maintenance (GCP)

### 1.1 — Preparing Model Weights
If you retrain the model using the `mlops_worker.py` or the notebook, you MUST run the cleaning script before deploying to ensure SHAP compatibility:

```bash
python patch_json.py
```
*This removes brackets from scientific notation strings in the JSON model that would otherwise crash the SHAP explainer in the Linux container.*

### 1.2 — Building and Deploying
Run these from the project root (`Energy Consumption/`):

```bash
# 1. Build the Docker image in GCP
gcloud builds submit --tag asia-south1-docker.pkg.dev/gridsight-prod/gridsight/backend:latest .

# 2. Deploy to Cloud Run
gcloud run deploy gridsight-backend \
  --image asia-south1-docker.pkg.dev/gridsight-prod/gridsight/backend:latest \
  --region asia-south1 \
  --platform managed \
  --memory 2Gi \
  --update-env-vars FRONTEND_URL=https://gridsight-blush.vercel.app
```

---

## PART 2 — Frontend Maintenance (Vercel)

### 2.1 — Environment Variables
The frontend is configured with `NEXT_PUBLIC_API_URL` pointing to the Cloud Run service.

To update locally:
```bash
# Inside Interface/client
vercel env pull .env.local
```

To redeploy manually:
```bash
vercel --prod
```

### 2.2 — Peer Dependency Handling
Because this project uses React 19, the `.npmrc` file is configured with `legacy-peer-deps=true` to allow `react-simple-maps` to install correctly.

---

## PART 3 — Troubleshooting & Logs

### 3.1 — Backend Logs
If predictions fail or show "fallback" values, check the Cloud Run logs:
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gridsight-backend" --limit 50
```

### 3.2 — Common Errors
- **"could not convert string to float"**: Usually means `patch_json.py` was skipped after a retrain.
- **CORS Error**: Check that `FRONTEND_URL` on Cloud Run matches the current Vercel deployment URL.

---

## Post-Deployment Verification
The dashboard was verified on May 8, 2026.
- **Baseline Load**: Success (14-day forecast)
- **Scenario Predict**: Success (Real-time XGBoost + SHAP)
- **Map Interaction**: Success (Maharashtra region selection)
