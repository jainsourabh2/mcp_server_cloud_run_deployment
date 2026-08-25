import os
import argparse
import json
import torch
from slm.tokenizer import SimpleTokenizer
from slm.model import SmallLanguageModel, SLMConfig

class SLMPredictor:
    """
    Inference helper to load an SLM model and generate text completions.
    """
    def __init__(self, artifacts_dir: str = "artifacts", device: str = "auto"):
        if device == "auto":
            if torch.cuda.is_available():
                self.device = torch.device("cuda")
            elif torch.backends.mps.is_available():
                self.device = torch.device("mps")
            else:
                self.device = torch.device("cpu")
        else:
            self.device = torch.device(device)

        # 1. Load Tokenizer
        vocab_path = os.path.join(artifacts_dir, "vocab.json")
        if not os.path.exists(vocab_path):
            raise FileNotFoundError(f"Vocabulary not found at {vocab_path}. Please train the model first.")
        self.tokenizer = SimpleTokenizer.load(vocab_path)

        # 2. Load Config
        config_path = os.path.join(artifacts_dir, "config.json")
        with open(config_path, "r") as f:
            config_dict = json.load(f)
        self.config = SLMConfig(**config_dict)

        # 3. Load Model Weights
        self.model = SmallLanguageModel(self.config).to(self.device)
        model_path = os.path.join(artifacts_dir, "model.pt")
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.eval()

    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 120,
        temperature: float = 0.7,
        top_k: int = 8
    ) -> str:
        """Generates text completion given an input prompt."""
        token_ids = self.tokenizer.encode(prompt)
        if len(token_ids) == 0:
            token_ids = [self.tokenizer.bos_token_id]

        input_tensor = torch.tensor([token_ids], dtype=torch.long, device=self.device)
        
        output_tokens = self.model.generate(
            input_tensor,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_k=top_k,
            eos_token_id=self.tokenizer.eos_token_id
        )
        
        generated_token_list = output_tokens[0].tolist()
        return self.tokenizer.decode(generated_token_list)

def interactive_loop(predictor: SLMPredictor):
    print("\n" + "="*50)
    print("🤖 Small Language Model (SLM) Interactive Console")
    print("Type your question or prompt below (or 'exit' to quit):")
    print("="*50 + "\n")
    
    while True:
        try:
            prompt = input("You: ").strip()
            if not prompt:
                continue
            if prompt.lower() in ["exit", "quit", "q"]:
                print("Goodbye!")
                break
            
            # Format prompt if user didn't prefix with Q:
            formatted_prompt = prompt if prompt.startswith("Q:") else f"Q: {prompt}\nA:"
            response = predictor.generate(formatted_prompt, max_new_tokens=150, temperature=0.6, top_k=5)
            print(f"\nSLM:\n{response}\n" + "-"*40)
        except KeyboardInterrupt:
            print("\nExiting...")
            break

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate text using trained SLM")
    parser.add_argument("--artifacts_dir", type=str, default="artifacts", help="Path to saved model artifacts")
    parser.add_argument("--prompt", type=str, default=None, help="Prompt text to complete")
    parser.add_argument("--max_tokens", type=int, default=120, help="Max tokens to generate")
    parser.add_argument("--temperature", type=float, default=0.7, help="Sampling temperature")
    parser.add_argument("--top_k", type=int, default=8, help="Top-K sampling constraint")
    
    args = parser.parse_args()
    
    predictor = SLMPredictor(artifacts_dir=args.artifacts_dir)
    
    if args.prompt:
        raw_prompt = args.prompt.replace("\\n", "\n")
        output = predictor.generate(
            prompt=raw_prompt,
            max_new_tokens=args.max_tokens,
            temperature=args.temperature,
            top_k=args.top_k
        )
        print("Generated Output:\n")
        print(output)
    else:
        interactive_loop(predictor)
