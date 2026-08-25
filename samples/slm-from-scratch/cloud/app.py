import os
import sys
import json
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

# Add parent directory to path to import slm package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slm.tokenizer import SimpleTokenizer
from slm.model import SmallLanguageModel, SLMConfig

app = FastAPI(
    title="Custom Small Language Model (SLM) API",
    description="Lightweight inference API for custom-trained SLM on Google Cloud Run",
    version="1.0.0"
)

# Global variables for model and tokenizer
model: Optional[SmallLanguageModel] = None
tokenizer: Optional[SimpleTokenizer] = None
config: Optional[SLMConfig] = None
device: torch.device = torch.device("cpu")

class GenerateRequest(BaseModel):
    prompt: str = Field(..., example="Q: What is TechGadget X1?\nA:")
    max_tokens: int = Field(default=100, ge=1, le=512, description="Maximum tokens to generate")
    temperature: float = Field(default=0.7, ge=0.01, le=2.0, description="Sampling temperature")
    top_k: int = Field(default=10, ge=1, le=50, description="Top-K candidate filter")

class GenerateResponse(BaseModel):
    prompt: str
    generated_text: str
    num_input_tokens: int
    num_generated_tokens: int

class ModelInfoResponse(BaseModel):
    vocab_size: int
    context_length: int
    d_model: int
    num_layers: int
    num_heads: int
    total_parameters: int
    device: str

@app.on_event("startup")
def load_artifacts():
    global model, tokenizer, config, device
    artifacts_dir = os.environ.get("ARTIFACTS_DIR", "artifacts")
    
    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")
    print(f"🔧 Initializing SLM Server on device: {device}")

    # Load Tokenizer
    vocab_path = os.path.join(artifacts_dir, "vocab.json")
    if not os.path.exists(vocab_path):
        print(f"⚠️ Warning: Vocab file not found at {vocab_path}. Server in uninitialized state.")
        return
    tokenizer = SimpleTokenizer.load(vocab_path)

    # Load Config
    config_path = os.path.join(artifacts_dir, "config.json")
    with open(config_path, "r") as f:
        config_dict = json.load(f)
    config = SLMConfig(**config_dict)

    # Load Model Weights
    model = SmallLanguageModel(config).to(device)
    model_path = os.path.join(artifacts_dir, "model.pt")
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval()
    print(f"✅ SLM Loaded successfully! Total params: {model.get_num_params():,}")

@app.get("/health")
def health_check():
    return {
        "status": "healthy" if model is not None else "degraded",
        "model_loaded": model is not None
    }

@app.get("/info", response_model=ModelInfoResponse)
def get_model_info():
    if model is None or config is None or tokenizer is None:
        raise HTTPException(status_code=503, detail="Model is not loaded yet")
    return ModelInfoResponse(
        vocab_size=tokenizer.vocab_size,
        context_length=config.context_length,
        d_model=config.d_model,
        num_layers=config.num_layers,
        num_heads=config.num_heads,
        total_parameters=model.get_num_params(),
        device=str(device)
    )

@app.post("/generate", response_model=GenerateResponse)
def generate_text(req: GenerateRequest):
    if model is None or tokenizer is None:
        raise HTTPException(status_code=503, detail="Model is not loaded yet")

    input_tokens = tokenizer.encode(req.prompt)
    if not input_tokens:
        input_tokens = [tokenizer.bos_token_id]

    input_tensor = torch.tensor([input_tokens], dtype=torch.long, device=device)

    output_tensor = model.generate(
        input_tensor,
        max_new_tokens=req.max_tokens,
        temperature=req.temperature,
        top_k=req.top_k,
        eos_token_id=tokenizer.eos_token_id
    )

    out_token_list = output_tensor[0].tolist()
    full_text = tokenizer.decode(out_token_list)
    generated_tokens_count = len(out_token_list) - len(input_tokens)

    return GenerateResponse(
        prompt=req.prompt,
        generated_text=full_text,
        num_input_tokens=len(input_tokens),
        num_generated_tokens=generated_tokens_count
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
