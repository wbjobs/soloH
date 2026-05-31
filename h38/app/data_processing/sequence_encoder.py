import numpy as np
import torch
from typing import List, Tuple
from app.constants import BASE_TO_INDEX, TOTAL_SEQUENCE_LENGTH, SGRNA_LENGTH


def encode_sequence(sequence: str, max_length: int = TOTAL_SEQUENCE_LENGTH) -> np.ndarray:
    sequence = sequence.upper()
    encoded = np.zeros(max_length, dtype=np.int64)

    for i, base in enumerate(sequence[:max_length]):
        encoded[i] = BASE_TO_INDEX.get(base, 4)

    return encoded


def one_hot_encode(sequence: str, max_length: int = TOTAL_SEQUENCE_LENGTH) -> np.ndarray:
    sequence = sequence.upper()
    num_bases = len(BASE_TO_INDEX)
    encoded = np.zeros((max_length, num_bases), dtype=np.float32)

    for i, base in enumerate(sequence[:max_length]):
        idx = BASE_TO_INDEX.get(base, 4)
        encoded[i, idx] = 1.0

    return encoded


def encode_sgrna_pair(
    sgrna: str,
    target: str,
    max_length: int = TOTAL_SEQUENCE_LENGTH,
    include_mismatch_features: bool = True,
) -> np.ndarray:
    sgrna = sgrna.upper()
    target = target.upper()

    sgrna_encoded = one_hot_encode(sgrna, max_length)
    target_encoded = one_hot_encode(target, max_length)

    combined = np.concatenate([sgrna_encoded, target_encoded], axis=1)

    if include_mismatch_features:
        mismatch_features = np.zeros((max_length, 2), dtype=np.float32)
        for i in range(min(len(sgrna), len(target), max_length)):
            if sgrna[i] != target[i]:
                mismatch_features[i, 0] = 1.0
            if sgrna[i] == "-" or target[i] == "-":
                mismatch_features[i, 1] = 1.0
        combined = np.concatenate([combined, mismatch_features], axis=1)

    return combined


def encode_batch(
    pairs: List[Tuple[str, str]],
    max_length: int = TOTAL_SEQUENCE_LENGTH,
    device: str = "cpu",
) -> torch.Tensor:
    encoded_list = []
    for sgrna, target in pairs:
        encoded = encode_sgrna_pair(sgrna, target, max_length)
        encoded_list.append(encoded)

    batch = np.stack(encoded_list, axis=0)
    batch = np.transpose(batch, (0, 2, 1))

    return torch.tensor(batch, dtype=torch.float32, device=device)


def create_position_encoding(max_length: int = TOTAL_SEQUENCE_LENGTH, d_model: int = 128) -> np.ndarray:
    position_enc = np.zeros((max_length, d_model), dtype=np.float32)
    position = np.arange(max_length)[:, np.newaxis]
    div_term = np.exp(np.arange(0, d_model, 2) * (-np.log(10000.0) / d_model))

    position_enc[:, 0::2] = np.sin(position * div_term)
    position_enc[:, 1::2] = np.cos(position * div_term)

    return position_enc
