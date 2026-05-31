import torch
import torch.nn as nn
import numpy as np
from typing import Tuple, List, Dict, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class AttentionResult:
    target_i: int
    target_j: int
    target_probability: float
    importance_map: np.ndarray
    top_residues: List[Tuple[int, float]]
    attention_score: float

    def to_dict(self):
        return {
            "target_i": self.target_i,
            "target_j": self.target_j,
            "target_probability": float(self.target_probability),
            "importance_map": self.importance_map.tolist(),
            "top_residues": [(int(i), float(s)) for i, s in self.top_residues],
            "attention_score": float(self.attention_score)
        }


class GradCAMAttention:
    def __init__(self, model: nn.Module):
        self.model = model
        self.model.eval()
        self.gradients = None
        self.activations = None
        self.hooks = []

    def _register_hooks(self):
        def forward_hook(module, input, output):
            self.activations = output.detach()

        def backward_hook(module, grad_input, grad_output):
            self.gradients = grad_output[0].detach()

        last_layer = None
        for module in self.model.modules():
            if isinstance(module, nn.Conv2d) and module.out_channels == 1:
                last_layer = module
                break

        if last_layer is None:
            for name, module in list(self.model.named_modules())[::-1]:
                if isinstance(module, nn.Conv2d):
                    last_layer = module
                    break

        if last_layer is not None:
            self.hooks.append(last_layer.register_forward_hook(forward_hook))
            self.hooks.append(last_layer.register_full_backward_hook(backward_hook))

    def _remove_hooks(self):
        for hook in self.hooks:
            hook.remove()
        self.hooks = []

    def compute_attention(
        self,
        input_tensor: torch.Tensor,
        target_i: int,
        target_j: int,
        device: Optional[str] = None
    ) -> AttentionResult:
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"

        self.model = self.model.to(device)
        input_tensor = input_tensor.to(device)
        input_tensor.requires_grad_(True)

        self._register_hooks()

        try:
            output = self.model(input_tensor)

            target_prob = output[0, target_i, target_j]

            self.model.zero_grad()
            target_prob.backward(retain_graph=True)

            if self.gradients is None or self.activations is None:
                raise RuntimeError("Failed to capture gradients or activations")

            pooled_gradients = torch.mean(self.gradients, dim=[0, 2, 3])

            for i in range(self.activations.shape[1]):
                self.activations[:, i, :, :] *= pooled_gradients[i]

            heatmap = torch.mean(self.activations, dim=1).squeeze()
            heatmap = torch.clamp(heatmap, min=0)

            if heatmap.numel() > 0:
                max_val = torch.max(heatmap)
                if max_val > 0:
                    heatmap = heatmap / max_val

            heatmap_np = heatmap.cpu().numpy()
            heatmap_np = (heatmap_np + heatmap_np.T) / 2

            row_importance = np.mean(heatmap_np, axis=1)
            col_importance = np.mean(heatmap_np, axis=0)
            residue_importance = (row_importance + col_importance) / 2

            top_indices = np.argsort(-residue_importance)[:10]
            top_residues = [(int(i), float(residue_importance[i])) for i in top_indices]

            attention_score = float(
                (heatmap_np[target_i, :].mean() + heatmap_np[:, target_j].mean()) / 2
            )

            return AttentionResult(
                target_i=target_i,
                target_j=target_j,
                target_probability=float(target_prob.item()),
                importance_map=heatmap_np,
                top_residues=top_residues,
                attention_score=attention_score
            )

        finally:
            self._remove_hooks()
            input_tensor.requires_grad_(False)


def compute_attention_map(
    model: nn.Module,
    input_tensor: torch.Tensor,
    contact_map: np.ndarray,
    top_k: int = 5,
    device: Optional[str] = None
) -> Dict[str, List[Dict]]:
    seq_len = contact_map.shape[0]

    triu_indices = np.triu_indices(seq_len, k=6)
    scores = contact_map[triu_indices]
    top_idx = np.argsort(-scores)[:top_k]

    attention_results = []
    explainer = GradCAMAttention(model)

    for idx in top_idx:
        i = int(triu_indices[0][idx])
        j = int(triu_indices[1][idx])

        try:
            result = explainer.compute_attention(
                input_tensor.clone(),
                target_i=i,
                target_j=j,
                device=device
            )
            attention_results.append(result.to_dict())
        except Exception as e:
            logger.warning(f"Failed to compute attention for ({i},{j}): {e}")

    per_residue_importance = compute_residue_importance(contact_map)

    return {
        "attention_results": attention_results,
        "per_residue_importance": per_residue_importance,
        "analyzed_contacts": top_k
    }


def compute_residue_importance(contact_map: np.ndarray) -> List[Dict]:
    seq_len = contact_map.shape[0]

    row_sums = np.sum(contact_map, axis=1)
    col_sums = np.sum(contact_map, axis=0)
    total_importance = (row_sums + col_sums) / 2

    high_prob_contacts = np.zeros(seq_len)
    for i in range(seq_len):
        for j in range(i + 6, seq_len):
            if contact_map[i, j] > 0.8:
                high_prob_contacts[i] += 1
                high_prob_contacts[j] += 1

    importance_scores = []
    for i in range(seq_len):
        importance_scores.append({
            "residue_index": i,
            "total_contact_probability": float(total_importance[i]),
            "high_prob_contact_count": int(high_prob_contacts[i]),
            "normalized_score": float(total_importance[i] / np.max(total_importance) if np.max(total_importance) > 0 else 0)
        })

    importance_scores.sort(key=lambda x: x["normalized_score"], reverse=True)
    return importance_scores


def get_contact_explanation(
    model: nn.Module,
    input_tensor: torch.Tensor,
    contact_map: np.ndarray,
    residue_i: int,
    residue_j: int,
    device: Optional[str] = None
) -> Optional[Dict]:
    seq_len = contact_map.shape[0]

    if residue_i < 0 or residue_i >= seq_len or residue_j < 0 or residue_j >= seq_len:
        raise ValueError(f"Residue indices out of range (0-{seq_len-1})")

    if abs(residue_i - residue_j) < 6:
        raise ValueError("Contact prediction only valid for residues separated by >= 6 positions")

    explainer = GradCAMAttention(model)

    try:
        result = explainer.compute_attention(
            input_tensor.clone(),
            target_i=residue_i,
            target_j=residue_j,
            device=device
        )
        return result.to_dict()
    except Exception as e:
        logger.error(f"Failed to get contact explanation: {e}")
        return None
