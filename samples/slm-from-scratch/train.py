import os
import argparse
import json
import torch
from torch.utils.data import DataLoader
from slm.tokenizer import SimpleTokenizer
from slm.model import SmallLanguageModel, SLMConfig
from slm.dataset import TextDataset

def train(
    data_path: str = "data/sample_data.txt",
    output_dir: str = "artifacts",
    epochs: int = 50,
    batch_size: int = 16,
    lr: float = 1e-3,
    context_length: int = 64,
    d_model: int = 128,
    num_heads: int = 4,
    num_layers: int = 4,
    device: str = "auto"
):
    os.makedirs(output_dir, exist_ok=True)

    # Determine compute device
    if device == "auto":
        if torch.cuda.is_available():
            dev = torch.device("cuda")
        elif torch.backends.mps.is_available():
            dev = torch.device("mps")
        else:
            dev = torch.device("cpu")
    else:
        dev = torch.device(device)
    print(f"🚀 Using compute device: {dev}")

    # 1. Load raw text dataset
    print(f"📖 Reading dataset from: {data_path}")
    with open(data_path, "r", encoding="utf-8") as f:
        text = f.read()

    print(f"📊 Total characters in dataset: {len(text):,}")

    # 2. Build Tokenizer
    tokenizer = SimpleTokenizer()
    tokenizer.build_vocab(text)
    vocab_file = os.path.join(output_dir, "vocab.json")
    tokenizer.save(vocab_file)
    print(f"🔤 Vocabulary Size: {tokenizer.vocab_size} tokens (Saved to {vocab_file})")

    # 3. Encode data and create DataLoader
    token_ids = tokenizer.encode(text)
    split_idx = int(len(token_ids) * 0.9)
    train_ids = token_ids[:split_idx]
    val_ids = token_ids[split_idx:]

    train_dataset = TextDataset(train_ids, context_length=context_length, stride=2)
    val_dataset = TextDataset(val_ids, context_length=context_length, stride=4)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    print(f"📦 Training samples: {len(train_dataset):,} | Validation samples: {len(val_dataset):,}")

    # 4. Initialize Model
    config = SLMConfig(
        vocab_size=tokenizer.vocab_size,
        context_length=context_length,
        d_model=d_model,
        num_heads=num_heads,
        num_layers=num_layers,
        dropout=0.1
    )
    model = SmallLanguageModel(config).to(dev)
    print(f"🧠 SLM Architecture: {config.num_layers} layers, {config.num_heads} heads, {config.d_model} d_model")
    print(f"⚙️ Total Trainable Parameters: {model.get_num_params():,}")

    # 5. Optimizer & Learning Rate
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)

    # 6. Training Loop
    print("\n--- Starting Model Training ---")
    best_val_loss = float("inf")

    for epoch in range(1, epochs + 1):
        model.train()
        total_train_loss = 0.0
        for x_batch, y_batch in train_loader:
            x_batch, y_batch = x_batch.to(dev), y_batch.to(dev)
            
            optimizer.zero_grad()
            _, loss = model(x_batch, y_batch)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            
            total_train_loss += loss.item()

        avg_train_loss = total_train_loss / max(len(train_loader), 1)

        # Validation
        model.eval()
        total_val_loss = 0.0
        with torch.no_grad():
            for x_val, y_val in val_loader:
                x_val, y_val = x_val.to(dev), y_val.to(dev)
                _, v_loss = model(x_val, y_val)
                total_val_loss += v_loss.item()
        avg_val_loss = total_val_loss / max(len(val_loader), 1)

        # Print progress
        if epoch % 10 == 0 or epoch == 1 or epoch == epochs:
            print(f"Epoch [{epoch:03d}/{epochs:03d}] | Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f}")
            
            # Generate a short sample snippet
            prompt = "Q: How do I reset"
            input_tokens = torch.tensor([tokenizer.encode(prompt)], dtype=torch.long, device=dev)
            gen_tokens = model.generate(input_tokens, max_new_tokens=60, temperature=0.7)
            generated_text = tokenizer.decode(gen_tokens[0].tolist())
            print(f"   Sample Generation: {repr(generated_text[:100])}")

        # Save best model
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            model_path = os.path.join(output_dir, "model.pt")
            torch.save(model.state_dict(), model_path)
            
            # Save config
            config_path = os.path.join(output_dir, "config.json")
            with open(config_path, "w") as f:
                json.dump(config.__dict__, f, indent=2)

    print("\n✅ Training Complete!")
    print(f"💾 Best Model saved to: {os.path.join(output_dir, 'model.pt')}")
    print(f"💾 Model Config saved to: {os.path.join(output_dir, 'config.json')}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train a Small Language Model (SLM) from scratch")
    parser.add_argument("--data_path", type=str, default="data/sample_data.txt", help="Path to raw training text")
    parser.add_argument("--output_dir", type=str, default="artifacts", help="Directory to save model weights & vocab")
    parser.add_argument("--epochs", type=int, default=60, help="Number of training epochs")
    parser.add_argument("--batch_size", type=int, default=16, help="Batch size")
    parser.add_argument("--lr", type=float, default=2e-3, help="Learning rate")
    parser.add_argument("--context_length", type=int, default=64, help="Context window length")
    parser.add_argument("--d_model", type=int, default=128, help="Embedding dimension")
    parser.add_argument("--num_heads", type=int, default=4, help="Attention heads")
    parser.add_argument("--num_layers", type=int, default=4, help="Transformer layers")
    parser.add_argument("--device", type=str, default="auto", help="Compute device (cpu, cuda, mps, auto)")
    
    args = parser.parse_args()
    train(
        data_path=args.data_path,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        context_length=args.context_length,
        d_model=args.d_model,
        num_heads=args.num_heads,
        num_layers=args.num_layers,
        device=args.device
    )
