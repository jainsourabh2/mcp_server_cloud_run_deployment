# MCP Server Cloud Run Deployment & Technical Guides

This repository contains production blueprints, comprehensive guides, and sample implementations for deploying **Model Context Protocol (MCP)** servers to **Google Cloud Run**, along with enterprise Google Cloud security and architecture best practices.

---

## Repository Structure

```text
.
├── building-resy-mcp-server-cloud-run.md  # Comprehensive guide: Building & Deploying Resy MCP on Cloud Run
├── building-slm-from-scratch-gcp-guide.md  # Complete guide: Building an SLM from Scratch & Deploying on GCP
├── securing-google-cloud-environment.md   # Practical guide: Org Policies, Alerts, Spend Caps & SCC
├── implementation_plan.md                 # Architecture, design & implementation specification
├── walkthrough.md                         # Deliverables, verification summary & execution trace
├── publish_to_medium.py                   # Automation script to publish guides directly to Medium
└── samples/
    ├── resy-mcp-server/                   # Production-ready Python Resy MCP Server
    └── slm-from-scratch/                  # Pure PyTorch Decoder-Only SLM & GCP Cloud Run / Vertex AI artifacts
        ├── data/
        │   └── sample_data.txt            # Training corpus knowledge base
        ├── slm/
        │   ├── tokenizer.py               # Custom character/sub-word tokenizer
        │   ├── model.py                   # Multi-Head Causal Self-Attention & Transformer Blocks
        │   └── dataset.py                 # PyTorch Dataset for next-token prediction
        ├── cloud/
        │   ├── app.py                     # FastAPI serving API
        │   ├── Dockerfile                 # Production container image
        │   ├── cloud_train_vertex.py      # Vertex AI GPU Custom Training launcher
        │   └── deploy_cloud_run.sh        # Cloud Run automated deployment script
        ├── train.py                       # Local model training script
        ├── inference.py                   # Text generation CLI & interactive chat
        └── requirements.txt
```

---

## Featured Implementations & Guides

### 1. [Building an SLM from Scratch & Deploying on Google Cloud](building-slm-from-scratch-gcp-guide.md)
* **Non-Technical AI Demystification**: Tokens, Embeddings, Self-Attention, Loss, and Temperature explained with relatable real-world analogies.
* **SLM vs. LLM Comparison**: Why compact models (100K–3B parameters) are winning in cost, latency, privacy, and edge deployment.
* **Pure PyTorch SLM Implementation**: Building tokenizers, causal attention masks, feed-forward MLPs, and decoder blocks from first principles.
* **Google Cloud Scaling**:
  * Storing datasets and checkpoints on **Google Cloud Storage (GCS)**.
  * Prototyping interactively with **Vertex AI Workbench**.
  * Serverless GPU training with **Vertex AI Custom Training Jobs** (using cost-effective Spot L4/T4 GPUs).
  * High-concurrency, scale-to-zero serverless inference on **Google Cloud Run**.

### 2. [Building & Deploying a Resy MCP Server on Google Cloud Run](building-resy-mcp-server-cloud-run.md)
* **Model Context Protocol (MCP)** architecture over **Server-Sent Events (SSE)**.
* Reverse-engineering Resy REST endpoints (`/4/find`, `/3/details`, `/3/book`, `/3/user/reservations`).
* Exposing 5 core MCP tools for venue search, slot availability, cancellation policies, and booking.
* Google Cloud Run deployment with `--timeout=3600` (SSE stream support) and Google Secret Manager integration.
* Connecting AI clients: **Claude Desktop** (via `npx mcp-remote`), **Cursor IDE**, and Python agents.

### 3. [Securing Your Google Cloud Environment](securing-google-cloud-environment.md)
* **Organization Policies**: Enforcing central guardrails across projects.
* **Cloud Logging & Alerting**: Real-time detection of high-impact resources.
* **Spend Cap Controls**: Budget alerts & automated billing safety nets.
* **Security Command Center (SCC)**: Centralized posture management & threat detection.

---

## Quickstart: Small Language Model (SLM) from Scratch

```bash
cd samples/slm-from-scratch
pip install -r requirements.txt

# 1. Train the model locally
python train.py --epochs 60 --output_dir artifacts

# 2. Run inference
python inference.py --prompt "Q: What is TechGadget X1?\nA:"

# 3. Deploy to Google Cloud Run
chmod +x cloud/deploy_cloud_run.sh
./cloud/deploy_cloud_run.sh
```

---

## Quickstart: Resy MCP Server

### Run Locally:
```bash
cd samples/resy-mcp-server
pip install -r requirements.txt

export RESY_API_KEY="your_resy_api_key"
export RESY_AUTH_TOKEN="your_resy_auth_token"

python server.py
```

### Deploy to Google Cloud Run:
```bash
cd samples/resy-mcp-server

# Create secrets in Secret Manager
echo -n "YOUR_API_KEY" | gcloud secrets create resy-api-key --data-file=-
echo -n "YOUR_AUTH_TOKEN" | gcloud secrets create resy-auth-token --data-file=-

# Deploy service
gcloud run deploy resy-mcp-server \
    --source . \
    --region us-central1 \
    --allow-unauthenticated \
    --timeout 3600 \
    --concurrency 80 \
    --set-secrets="RESY_API_KEY=resy-api-key:latest,RESY_AUTH_TOKEN=resy-auth-token:latest"
```

---

## Publishing Guides to Medium

You can publish any Markdown post in this repository to Medium using the included automation script:

```bash
export MEDIUM_INTEGRATION_TOKEN="your_medium_integration_token"
python publish_to_medium.py $MEDIUM_INTEGRATION_TOKEN draft building-slm-from-scratch-gcp-guide.md
```
