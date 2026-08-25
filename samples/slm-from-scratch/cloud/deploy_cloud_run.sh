#!/usr/bin/env bash
# ==============================================================================
# Deploy Custom SLM Server to Google Cloud Run
# ==============================================================================
set -euo pipefail

# Configuration
SERVICE_NAME="slm-service"
REGION="${GCP_REGION:-us-central1}"
PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project)}"
IMAGE_TAG="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"

echo "============================================================"
echo "🚀 Deploying Small Language Model (SLM) to Google Cloud Run"
echo "Project ID: ${PROJECT_ID}"
echo "Region:     ${REGION}"
echo "Service:    ${SERVICE_NAME}"
echo "============================================================"

# Step 1: Ensure model artifacts exist locally
if [ ! -f "artifacts/model.pt" ] || [ ! -f "artifacts/vocab.json" ]; then
    echo "⚠️ Local model artifacts missing. Training model first..."
    python train.py --epochs 60 --output_dir artifacts
fi

# Step 2: Build container image using Google Cloud Build
echo "📦 Building container image via Google Cloud Build..."
gcloud builds submit --tag "${IMAGE_TAG}" -f cloud/Dockerfile .

# Step 3: Deploy service to Google Cloud Run
echo "🚀 Deploying to Google Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
    --image "${IMAGE_TAG}" \
    --platform managed \
    --region "${REGION}" \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --concurrency 80 \
    --min-instances 0 \
    --max-instances 5 \
    --timeout 300 \
    --set-env-vars "ARTIFACTS_DIR=/app/artifacts"

# Step 4: Display Service URL
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --platform managed --region "${REGION}" --format="value(status.url)")
echo "============================================================"
echo "🎉 SLM API is live!"
echo "Service URL: ${SERVICE_URL}"
echo "Test endpoint: curl -X POST ${SERVICE_URL}/generate -H 'Content-Type: application/json' -d '{\"prompt\": \"Q: What is TechGadget X1?\\nA:\"}'"
echo "============================================================"
