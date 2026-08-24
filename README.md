# MCP Server Cloud Run Deployment & Technical Guides

This repository contains production blueprints, comprehensive guides, and sample implementations for deploying **Model Context Protocol (MCP)** servers to **Google Cloud Run**, along with enterprise Google Cloud security and architecture best practices.

---

## Repository Structure

```text
.
├── building-resy-mcp-server-cloud-run.md  # Comprehensive guide: Building & Deploying Resy MCP on Cloud Run
├── securing-google-cloud-environment.md   # Practical guide: Org Policies, Alerts, Spend Caps & SCC
├── publish_to_medium.py                   # Automation script to publish guides directly to Medium
└── samples/
    └── resy-mcp-server/                   # Production-ready Python Resy MCP Server
        ├── resy/
        │   ├── __init__.py
        │   ├── client.py                  # Async Resy REST client with retries
        │   └── models.py                  # Pydantic schemas for MCP tools & responses
        ├── server.py                      # FastMCP Server with SSE transport
        ├── Dockerfile                     # Optimized container image for Cloud Run
        ├── .dockerignore                  # Docker build exclusions
        ├── requirements.txt               # Pinned dependencies
        ├── pyproject.toml                 # Modern Python packaging metadata
        ├── test_client.py                 # Local & remote SSE verification test client
        └── README.md                      # Project setup & deployment quickstart
```

---

## Featured Implementations & Guides

### 1. [Building & Deploying a Resy MCP Server on Google Cloud Run](building-resy-mcp-server-cloud-run.md)
* **Model Context Protocol (MCP)** architecture over **Server-Sent Events (SSE)**.
* Reverse-engineering Resy REST endpoints (`/4/find`, `/3/details`, `/3/book`, `/3/user/reservations`).
* Exposing 5 core MCP tools for venue search, slot availability, cancellation policies, and booking.
* Google Cloud Run deployment with `--timeout=3600` (SSE stream support) and Google Secret Manager integration.
* Connecting AI clients: **Claude Desktop** (via `npx mcp-remote`), **Cursor IDE**, and Python agents.

### 2. [Securing Your Google Cloud Environment](securing-google-cloud-environment.md)
* **Organization Policies**: Enforcing central guardrails across projects.
* **Cloud Logging & Alerting**: Real-time detection of high-impact resources.
* **Spend Cap Controls**: Budget alerts & automated billing safety nets.
* **Security Command Center (SCC)**: Centralized posture management & threat detection.

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
python publish_to_medium.py $MEDIUM_INTEGRATION_TOKEN draft building-resy-mcp-server-cloud-run.md
```
