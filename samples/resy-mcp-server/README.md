# Resy Model Context Protocol (MCP) Server for Google Cloud Run

A production-ready Model Context Protocol (MCP) Server for Resy restaurant reservations, built with Python, FastMCP, and Server-Sent Events (SSE), ready to deploy on Google Cloud Run.

## Features
- **Restaurant Search**: Search restaurants by name, cuisine, city, or coordinates.
- **Availability Lookup**: Find open reservation time slots, table types (indoor, patio, bar), and party size availability.
- **Slot Details & Policy**: Retrieve exact cancellation policies, deposit amounts, and booking tokens.
- **Safe Booking**: Execute table reservations with built-in `dry_run=True` safety guardrails.
- **User Reservations**: View upcoming reservations for the logged-in Resy user account.
- **Cloud Run Native**: SSE streaming transport, scale-to-zero, and Google Secret Manager integration.

## Quickstart (Local)

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Environment Variables**:
   ```bash
   export RESY_API_KEY="your_resy_api_key"
   export RESY_AUTH_TOKEN="your_resy_auth_token"
   ```

3. **Run the Server**:
   ```bash
   python server.py
   ```

4. **Test with Client**:
   ```bash
   python test_client.py
   ```

## Deploying to Google Cloud Run

```bash
# Set GCP Project
gcloud config set project YOUR_PROJECT_ID

# Create Secrets
echo -n "YOUR_RESY_API_KEY" | gcloud secrets create resy-api-key --data-file=-
echo -n "YOUR_RESY_AUTH_TOKEN" | gcloud secrets create resy-auth-token --data-file=-

# Deploy to Cloud Run
gcloud run deploy resy-mcp-server \
    --source . \
    --region us-central1 \
    --allow-unauthenticated \
    --timeout 3600 \
    --concurrency 80 \
    --set-secrets="RESY_API_KEY=resy-api-key:latest,RESY_AUTH_TOKEN=resy-auth-token:latest"
```

## Connecting with Claude Desktop

Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "resy": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://YOUR_CLOUD_RUN_URL/sse"
      ]
    }
  }
}
```
