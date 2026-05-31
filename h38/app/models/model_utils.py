import os
import torch
import torch.nn as nn
import numpy as np
from typing import List, Tuple, Optional
from app.models.crispr_model import CRISPRModel, CRISPRPredictor
from app.data_processing.sequence_encoder import encode_batch
from app.config import get_settings
from app.constants import TOTAL_SEQUENCE_LENGTH


def load_model(
    model_path: Optional[str] = None,
    device: Optional[str] = None,
) -> CRISPRPredictor:
    settings = get_settings()

    if model_path is None:
        model_path = settings.MODEL_PATH

    if device is None:
        device = settings.MODEL_DEVICE

    model = CRISPRModel()
    predictor = CRISPRPredictor(model=model, model_path=model_path, device=device)

    return predictor


def save_model(
    predictor: CRISPRPredictor,
    save_path: str,
    optimizer: Optional[torch.optim.Optimizer] = None,
    epoch: Optional[int] = None,
    loss: Optional[float] = None,
):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    save_dict = {
        "model_state_dict": predictor.model.state_dict(),
    }

    if optimizer is not None:
        save_dict["optimizer_state_dict"] = optimizer.state_dict()

    if epoch is not None:
        save_dict["epoch"] = epoch

    if loss is not None:
        save_dict["loss"] = loss

    torch.save(save_dict, save_path)


def predict_batch(
    predictor: CRISPRPredictor,
    pairs: List[Tuple[str, str]],
    batch_size: int = 32,
) -> np.ndarray:
    all_scores = []

    for i in range(0, len(pairs), batch_size):
        batch_pairs = pairs[i : i + batch_size]
        encoded_batch = encode_batch(
            batch_pairs,
            max_length=TOTAL_SEQUENCE_LENGTH,
            device=str(predictor.device),
        )
        scores = predictor.predict(encoded_batch)
        all_scores.extend(scores.cpu().numpy())

    return np.array(all_scores)


def calculate_offtarget_score(
    raw_score: float,
    transitions: int = 0,
    transversions: int = 0,
    insertions: int = 0,
    deletions: int = 0,
) -> float:
    penalty = 1.0

    transition_penalty = 0.10
    transversion_penalty = 0.20
    insertion_penalty = 0.25
    deletion_penalty = 0.30

    penalty -= transitions * transition_penalty
    penalty -= transversions * transversion_penalty
    penalty -= insertions * insertion_penalty
    penalty -= deletions * deletion_penalty

    total_mismatches = transitions + transversions
    if total_mismatches <= 1:
        bonus = 0.1
        penalty += bonus
    elif total_mismatches <= 3:
        bonus = 0.05
        penalty += bonus

    final_score = raw_score * max(0.0, penalty)

    return max(0.0, min(1.0, final_score))


def create_dummy_training_data(
    num_samples: int = 1000,
    seq_length: int = TOTAL_SEQUENCE_LENGTH,
) -> Tuple[torch.Tensor, torch.Tensor]:
    bases = ["A", "T", "C", "G"]
    pairs = []
    labels = []

    for _ in range(num_samples):
        sgrna = "".join(np.random.choice(bases) for _ in range(seq_length))
        target = list(sgrna)

        num_mismatches = np.random.poisson(2)
        positions = np.random.choice(seq_length, num_mismatches, replace=False)
        for pos in positions:
            original = target[pos]
            new_base = np.random.choice([b for b in bases if b != original])
            target[pos] = new_base

        target = "".join(target)

        pairs.append((sgrna, target))
        label = 1.0 if num_mismatches <= 2 else max(0.0, 1.0 - num_mismatches * 0.1)
        labels.append(label)

    encoded = encode_batch(pairs, max_length=seq_length)
    labels = torch.tensor(labels, dtype=torch.float32)

    return encoded, labels


def train_model(
    model: CRISPRModel,
    train_data: Tuple[torch.Tensor, torch.Tensor],
    val_data: Optional[Tuple[torch.Tensor, torch.Tensor]] = None,
    epochs: int = 50,
    batch_size: int = 32,
    learning_rate: float = 1e-3,
    device: str = "cpu",
) -> CRISPRModel:
    device = torch.device(device if torch.cuda.is_available() else "cpu")
    model = model.to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=5
    )
    criterion = nn.BCEWithLogitsLoss()

    X_train, y_train = train_data
    dataset = torch.utils.data.TensorDataset(X_train, y_train)
    dataloader = torch.utils.data.DataLoader(
        dataset, batch_size=batch_size, shuffle=True
    )

    for epoch in range(epochs):
        model.train()
        total_loss = 0.0

        for batch_X, batch_y in dataloader:
            batch_X = batch_X.to(device)
            batch_y = batch_y.to(device)

            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()

            total_loss += loss.item()

        avg_loss = total_loss / len(dataloader)

        if val_data is not None:
            model.eval()
            X_val, y_val = val_data
            with torch.no_grad():
                val_outputs = model(X_val.to(device))
                val_loss = criterion(val_outputs, y_val.to(device))

            scheduler.step(val_loss)
            print(
                f"Epoch {epoch + 1}/{epochs}, Train Loss: {avg_loss:.4f}, Val Loss: {val_loss:.4f}"
            )
        else:
            scheduler.step(avg_loss)
            print(f"Epoch {epoch + 1}/{epochs}, Train Loss: {avg_loss:.4f}")

    return model
