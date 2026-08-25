import math
from dataclasses import dataclass
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Tuple

@dataclass
class SLMConfig:
    vocab_size: int = 100
    context_length: int = 128    # Max sequence length (how many tokens the model remembers at once)
    d_model: int = 128           # Embedding dimension (width of the model)
    num_heads: int = 4           # Number of attention heads (perspectives of context)
    num_layers: int = 4          # Number of transformer layers (depth of the model)
    dropout: float = 0.1         # Dropout rate for regularization
    bias: bool = False           # Whether to use bias in linear layers

class MultiHeadSelfAttention(nn.Module):
    """
    Multi-Head Causal Self-Attention mechanism.
    Allows tokens to 'communicate' and weigh the importance of preceding words in context.
    """
    def __init__(self, config: SLMConfig):
        super().__init__()
        assert config.d_model % config.num_heads == 0, "d_model must be divisible by num_heads"
        self.num_heads = config.num_heads
        self.d_model = config.d_model
        self.head_dim = config.d_model // config.num_heads

        # Combined Query, Key, Value linear projections for computational efficiency
        self.qkv_proj = nn.Linear(config.d_model, 3 * config.d_model, bias=config.bias)
        # Output projection
        self.out_proj = nn.Linear(config.d_model, config.d_model, bias=config.bias)
        
        self.attn_dropout = nn.Dropout(config.dropout)
        self.resid_dropout = nn.Dropout(config.dropout)
        
        # Causal mask to ensure attention is only applied to the left in the input sequence
        # (Tokens cannot see future tokens during text generation)
        self.register_buffer(
            "causal_mask",
            torch.tril(torch.ones(config.context_length, config.context_length)).view(
                1, 1, config.context_length, config.context_length
            )
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, T, C = x.size()  # Batch size, Sequence length, Embedding dim

        # Calculate Q, K, V
        qkv = self.qkv_proj(x)  # (B, T, 3 * C)
        q, k, v = qkv.chunk(3, dim=-1)  # Each is (B, T, C)

        # Reshape for multi-head attention: (B, num_heads, T, head_dim)
        q = q.view(B, T, self.num_heads, self.head_dim).transpose(1, 2)
        k = k.view(B, T, self.num_heads, self.head_dim).transpose(1, 2)
        v = v.view(B, T, self.num_heads, self.head_dim).transpose(1, 2)

        # Scaled Dot-Product Attention: Attention(Q, K, V) = softmax(Q @ K^T / sqrt(d_k)) @ V
        scores = (q @ k.transpose(-2, -1)) * (1.0 / math.sqrt(self.head_dim))
        
        # Apply causal mask (fill future positions with -infinity)
        scores = scores.masked_fill(self.causal_mask[:, :, :T, :T] == 0, float("-inf"))
        
        attn_weights = F.softmax(scores, dim=-1)
        attn_weights = self.attn_dropout(attn_weights)
        
        # Weighted sum of values
        out = attn_weights @ v  # (B, num_heads, T, head_dim)
        
        # Re-assemble all head outputs side by side
        out = out.transpose(1, 2).contiguous().view(B, T, C)
        
        # Final linear projection
        out = self.resid_dropout(self.out_proj(out))
        return out

class FeedForward(nn.Module):
    """
    Position-wise Feed-Forward Network (MLP).
    Processes and transforms the extracted contextual representations.
    """
    def __init__(self, config: SLMConfig):
        super().__init__()
        hidden_dim = 4 * config.d_model  # Expansion factor of 4
        self.linear1 = nn.Linear(config.d_model, hidden_dim, bias=config.bias)
        self.act = nn.GELU()             # Smooth Gaussian Error Linear Unit activation
        self.linear2 = nn.Linear(hidden_dim, config.d_model, bias=config.bias)
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.linear1(x)
        x = self.act(x)
        x = self.linear2(x)
        x = self.dropout(x)
        return x

class TransformerBlock(nn.Module):
    """
    A single Transformer Decoder Block consisting of:
    1. Pre-Layer Normalization
    2. Multi-Head Self-Attention with Residual Skip Connection
    3. Pre-Layer Normalization
    4. Feed-Forward MLP with Residual Skip Connection
    """
    def __init__(self, config: SLMConfig):
        super().__init__()
        self.ln1 = nn.LayerNorm(config.d_model)
        self.attn = MultiHeadSelfAttention(config)
        self.ln2 = nn.LayerNorm(config.d_model)
        self.ffn = FeedForward(config)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Pre-LN Transformer architecture (used in modern GPT / Llama models)
        x = x + self.attn(self.ln1(x))
        x = x + self.ffn(self.ln2(x))
        return x

class SmallLanguageModel(nn.Module):
    """
    Complete Small Language Model (SLM) Architecture (Decoder-Only Transformer).
    """
    def __init__(self, config: SLMConfig):
        super().__init__()
        self.config = config

        # Token Embedding Table & Learned Positional Embedding Table
        self.tok_embeddings = nn.Embedding(config.vocab_size, config.d_model)
        self.pos_embeddings = nn.Embedding(config.context_length, config.d_model)
        self.dropout = nn.Dropout(config.dropout)

        # Stack of Transformer Decoder Blocks
        self.blocks = nn.ModuleList([TransformerBlock(config) for _ in range(config.num_layers)])
        
        # Final Layer Normalization
        self.ln_final = nn.LayerNorm(config.d_model)
        
        # Language Modeling Head (Linear projection from d_model to vocab_size)
        self.lm_head = nn.Linear(config.d_model, config.vocab_size, bias=False)
        
        # Weight tying: share weights between token embeddings and output projection
        self.tok_embeddings.weight = self.lm_head.weight

        # Initialize all weights with standard normal distribution
        self.apply(self._init_weights)

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                torch.nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward(self, idx: torch.Tensor, targets: Optional[torch.Tensor] = None) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """
        Forward pass for training and inference.
        idx: (B, T) tensor of integer token indices
        targets: (B, T) tensor of target token indices for calculating cross-entropy loss
        """
        device = idx.device
        B, T = idx.size()
        assert T <= self.config.context_length, f"Sequence length {T} exceeds context length {self.config.context_length}"

        # Position indices: [0, 1, ..., T-1]
        pos = torch.arange(0, T, dtype=torch.long, device=device).unsqueeze(0)

        # Combine token embeddings and positional embeddings
        tok_emb = self.tok_embeddings(idx)  # (B, T, d_model)
        pos_emb = self.pos_embeddings(pos)  # (1, T, d_model)
        x = self.dropout(tok_emb + pos_emb)

        # Pass through all transformer blocks
        for block in self.blocks:
            x = block(x)

        # Apply final LayerNorm and LM projection head
        x = self.ln_final(x)
        logits = self.lm_head(x)  # (B, T, vocab_size)

        loss = None
        if targets is not None:
            # Flatten tensors to compute cross-entropy loss across all sequence tokens
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), targets.view(-1))

        return logits, loss

    def get_num_params(self) -> int:
        """Returns the total number of trainable parameters in the model."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    @torch.no_grad()
    def generate(
        self,
        idx: torch.Tensor,
        max_new_tokens: int = 100,
        temperature: float = 0.8,
        top_k: Optional[int] = 10,
        eos_token_id: Optional[int] = None
    ) -> torch.Tensor:
        """
        Autoregressively generates new tokens one by one.
        
        idx: (B, T) prompt token indices
        max_new_tokens: maximum number of tokens to generate
        temperature: randomness scaling factor (lower = more deterministic/focused, higher = creative)
        top_k: if set, only sample from the top K most likely candidate tokens
        eos_token_id: if set, stops generation when this token is emitted
        """
        self.eval()
        for _ in range(max_new_tokens):
            # Crop the sequence to the maximum context length if it exceeds it
            idx_cond = idx if idx.size(1) <= self.config.context_length else idx[:, -self.config.context_length:]
            
            # Forward pass
            logits, _ = self(idx_cond)
            # Take the logits for the very last token in the sequence
            logits = logits[:, -1, :] / max(temperature, 1e-5)
            
            # Optionally filter by top_k
            if top_k is not None:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = -float("Inf")
                
            # Convert logits to probabilities
            probs = F.softmax(logits, dim=-1)
            
            # Sample next token from the probability distribution
            idx_next = torch.multinomial(probs, num_samples=1)
            
            # Append sampled token to the running sequence
            idx = torch.cat((idx, idx_next), dim=1)
            
            # Early stop if End-Of-Sequence token is hit
            if eos_token_id is not None and (idx_next == eos_token_id).all():
                break

        return idx
