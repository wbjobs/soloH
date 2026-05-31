import numpy as np
import torch
from typing import Optional

from app.utils.fasta_parser import AMINO_ACID_ORDER, AMINO_ACID_TO_IDX

NUM_AMINO_ACIDS = len(AMINO_ACID_ORDER)


def one_hot_encode(sequence: str, as_tensor: bool = True) -> np.ndarray:
    seq_len = len(sequence)
    one_hot = np.zeros((seq_len, NUM_AMINO_ACIDS), dtype=np.float32)

    for i, aa in enumerate(sequence):
        if aa in AMINO_ACID_TO_IDX:
            one_hot[i, AMINO_ACID_TO_IDX[aa]] = 1.0

    if as_tensor:
        return torch.from_numpy(one_hot)

    return one_hot


def get_sequence_features(sequence: str, pssm: Optional[np.ndarray] = None) -> torch.Tensor:
    one_hot = one_hot_encode(sequence, as_tensor=False)

    if pssm is not None:
        if pssm.shape != (len(sequence), NUM_AMINO_ACIDS):
            raise ValueError(f"PSSM shape {pssm.shape} does not match sequence length {len(sequence)}")
        features = np.concatenate([one_hot, pssm], axis=1)
    else:
        features = one_hot

    return torch.from_numpy(features).float()


def build_input_tensor(features: torch.Tensor) -> torch.Tensor:
    seq_len = features.shape[0]
    feat_dim = features.shape[1]

    feat_i = features.unsqueeze(1).expand(seq_len, seq_len, feat_dim)
    feat_j = features.unsqueeze(0).expand(seq_len, seq_len, feat_dim)

    pairwise_feat = torch.cat([feat_i, feat_j], dim=2)
    pairwise_feat = pairwise_feat.permute(2, 0, 1).unsqueeze(0)

    return pairwise_feat
