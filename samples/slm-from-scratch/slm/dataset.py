import torch
from torch.utils.data import Dataset
from typing import List

class TextDataset(Dataset):
    """
    PyTorch Dataset that creates sliding context windows of tokens for next-token prediction.
    Input (x): tokens from position i to i + context_length - 1
    Target (y): tokens from position i + 1 to i + context_length (shifted by 1)
    """
    def __init__(self, token_ids: List[int], context_length: int, stride: int = 1):
        self.context_length = context_length
        self.samples = []

        # If data is shorter than context length, pad it
        if len(token_ids) <= context_length:
            # Repeat or pad
            token_ids = token_ids * ((context_length + 2) // len(token_ids) + 1)

        # Generate overlapping slices
        for i in range(0, len(token_ids) - context_length, stride):
            x = token_ids[i : i + context_length]
            y = token_ids[i + 1 : i + context_length + 1]
            self.samples.append((x, y))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        x, y = self.samples[idx]
        return torch.tensor(x, dtype=torch.long), torch.tensor(y, dtype=torch.long)
