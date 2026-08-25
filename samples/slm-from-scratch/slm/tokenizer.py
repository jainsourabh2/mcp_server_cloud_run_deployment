import json
from typing import List, Dict

class SimpleTokenizer:
    """
    A lightweight, understandable character-level and word-piece style tokenizer.
    Translates human readable text into numerical token IDs and vice versa.
    """
    def __init__(self):
        self.pad_token = "<PAD>"
        self.unk_token = "<UNK>"
        self.bos_token = "<BOS>"
        self.eos_token = "<EOS>"
        
        self.special_tokens = [self.pad_token, self.unk_token, self.bos_token, self.eos_token]
        self.token_to_id: Dict[str, int] = {}
        self.id_to_token: Dict[int, str] = {}
        
        # Initialize special tokens
        for idx, token in enumerate(self.special_tokens):
            self.token_to_id[token] = idx
            self.id_to_token[idx] = token
            
        self.pad_token_id = self.token_to_id[self.pad_token]
        self.unk_token_id = self.token_to_id[self.unk_token]
        self.bos_token_id = self.token_to_id[self.bos_token]
        self.eos_token_id = self.token_to_id[self.eos_token]

    def build_vocab(self, text: str):
        """Builds the vocabulary mapping from a corpus of text."""
        # Character-level vocabulary ensures zero out-of-vocabulary words
        unique_chars = sorted(list(set(text)))
        next_id = len(self.special_tokens)
        
        for char in unique_chars:
            if char not in self.token_to_id:
                self.token_to_id[char] = next_id
                self.id_to_token[next_id] = char
                next_id += 1

    @property
    def vocab_size(self) -> int:
        return len(self.token_to_id)

    def encode(self, text: str, add_special_tokens: bool = False) -> List[int]:
        """Converts a string of text into a list of integer token IDs."""
        tokens = []
        if add_special_tokens:
            tokens.append(self.bos_token_id)
            
        for char in text:
            tokens.append(self.token_to_id.get(char, self.unk_token_id))
            
        if add_special_tokens:
            tokens.append(self.eos_token_id)
            
        return tokens

    def decode(self, token_ids: List[int], skip_special_tokens: bool = True) -> str:
        """Converts a list of integer token IDs back into human readable text."""
        chars = []
        for token_id in token_ids:
            if token_id in self.id_to_token:
                token = self.id_to_token[token_id]
                if skip_special_tokens and token in self.special_tokens:
                    continue
                chars.append(token)
            else:
                chars.append(self.unk_token)
        return "".join(chars)

    def save(self, filepath: str):
        """Saves vocabulary mapping to a JSON file."""
        data = {
            "token_to_id": self.token_to_id,
            "special_tokens": self.special_tokens
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, filepath: str) -> "SimpleTokenizer":
        """Loads a tokenizer from a saved JSON vocabulary file."""
        tokenizer = cls()
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        tokenizer.token_to_id = data["token_to_id"]
        tokenizer.id_to_token = {int(v): k for k, v in tokenizer.token_to_id.items()}
        tokenizer.special_tokens = data.get("special_tokens", tokenizer.special_tokens)
        return tokenizer
