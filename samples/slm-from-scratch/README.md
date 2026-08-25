# Small Language Model (SLM) from Scratch & Google Cloud Deployment

A complete, pedagogical implementation of a **Decoder-Only Transformer Small Language Model (SLM)** built in PyTorch from first principles, trained on custom sample data, and deployable to **Google Cloud (Vertex AI & Cloud Run)**.

---

## Architecture Overview

* **Tokenizer**: Character and sub-word tokenization with special tokens (`<PAD>`, `<UNK>`, `<BOS>`, `<EOS>`).
* **Embeddings**: Learned Token Embeddings + Learned Positional Embeddings.
* **Transformer Core**: Multi-Head Causal Self-Attention + Pre-Layer Normalization + GELU Feed-Forward Network + Residual Connections.
* **Serving**: High-performance FastAPI server containerized with Docker for scale-to-zero serverless hosting on Google Cloud Run.
* **GCP Training**: Automated GPU training scripts for Google Cloud Vertex AI Custom Jobs.

---

## Quickstart: Local Training & Testing

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Train the SLM Locally
```bash
python train.py --epochs 60 --output_dir artifacts
```

### 3. Generate Text Interactively
```bash
python inference.py --artifacts_dir artifacts
```

Or run a single prompt:
```bash
python inference.py --prompt "Q: How do I reset my TechGadget X1?\nA:"
```

---

## Deploying to Google Cloud Run

To containerize and deploy your trained SLM as a serverless API on Cloud Run:

```bash
chmod +x cloud/deploy_cloud_run.sh
./cloud/deploy_cloud_run.sh
```

### Querying your Live Cloud Run API:
```bash
curl -X POST "https://slm-service-<hash>-uc.a.run.app/generate" \
     -H "Content-Type: application/json" \
     -d '{"prompt": "Q: What is TechGadget X1?\nA:", "max_tokens": 100, "temperature": 0.7}'
```
