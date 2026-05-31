import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import List, Tuple, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class CrossModalAttention(nn.Module):
    def __init__(self, dim: int, num_heads: int = 8, dropout: float = 0.1):
        super().__init__()
        self.num_heads = num_heads
        self.head_dim = dim // num_heads
        self.scale = self.head_dim ** -0.5
        
        self.q_proj = nn.Linear(dim, dim)
        self.k_proj = nn.Linear(dim, dim)
        self.v_proj = nn.Linear(dim, dim)
        self.out_proj = nn.Linear(dim, dim)
        
        self.dropout = nn.Dropout(dropout)

    def forward(
        self,
        query: torch.Tensor,
        key: torch.Tensor,
        value: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
        return_attention: bool = False
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        batch_size = query.shape[0]
        
        q = self.q_proj(query).view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(key).view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(value).view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)
        
        attn_weights = torch.matmul(q, k.transpose(-2, -1)) * self.scale
        
        if mask is not None:
            attn_weights = attn_weights.masked_fill(mask == 0, float('-inf'))
        
        attn_weights = F.softmax(attn_weights, dim=-1)
        attn_weights = self.dropout(attn_weights)
        
        output = torch.matmul(attn_weights, v)
        output = output.transpose(1, 2).contiguous().view(batch_size, -1, self.num_heads * self.head_dim)
        output = self.out_proj(output)
        
        if return_attention:
            attn_weights_avg = attn_weights.mean(dim=1)
            return output, attn_weights_avg
        
        return output, None


class TransformerEncoderLayer(nn.Module):
    def __init__(self, dim: int, num_heads: int = 8, dim_ff: int = 2048, dropout: float = 0.1):
        super().__init__()
        self.self_attn = CrossModalAttention(dim, num_heads, dropout)
        self.cross_attn_audio = CrossModalAttention(dim, num_heads, dropout)
        self.cross_attn_video = CrossModalAttention(dim, num_heads, dropout)
        self.cross_attn_text = CrossModalAttention(dim, num_heads, dropout)
        
        self.norm1 = nn.LayerNorm(dim)
        self.norm2 = nn.LayerNorm(dim)
        self.norm3 = nn.LayerNorm(dim)
        
        self.ffn = nn.Sequential(
            nn.Linear(dim, dim_ff),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(dim_ff, dim),
            nn.Dropout(dropout)
        )
        
        self.dropout = nn.Dropout(dropout)

    def forward(
        self,
        audio_features: torch.Tensor,
        video_features: torch.Tensor,
        text_features: torch.Tensor,
        return_attention: bool = False
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, Optional[Dict]]:
        audio_norm = self.norm1(audio_features)
        video_norm = self.norm1(video_features)
        text_norm = self.norm1(text_features)
        
        audio_attended, audio_attn_weights = self.self_attn(
            audio_norm, audio_norm, audio_norm, return_attention=return_attention
        )
        video_attended, video_attn_weights = self.self_attn(
            video_norm, video_norm, video_norm, return_attention=return_attention
        )
        text_attended, text_attn_weights = self.self_attn(
            text_norm, text_norm, text_norm, return_attention=return_attention
        )
        
        audio_features = audio_features + self.dropout(audio_attended)
        video_features = video_features + self.dropout(video_attended)
        text_features = text_features + self.dropout(text_attended)
        
        audio_norm2 = self.norm2(audio_features)
        video_norm2 = self.norm2(video_features)
        text_norm2 = self.norm2(text_features)
        
        audio_to_video, av_weights = self.cross_attn_video(
            audio_norm2, video_norm2, video_norm2, return_attention=return_attention
        )
        audio_to_text, at_weights = self.cross_attn_text(
            audio_norm2, text_norm2, text_norm2, return_attention=return_attention
        )
        audio_cross = (audio_to_video + audio_to_text) / 2
        
        video_to_audio, va_weights = self.cross_attn_audio(
            video_norm2, audio_norm2, audio_norm2, return_attention=return_attention
        )
        video_to_text, vt_weights = self.cross_attn_text(
            video_norm2, text_norm2, text_norm2, return_attention=return_attention
        )
        video_cross = (video_to_audio + video_to_text) / 2
        
        text_to_audio, ta_weights = self.cross_attn_audio(
            text_norm2, audio_norm2, audio_norm2, return_attention=return_attention
        )
        text_to_video, tv_weights = self.cross_attn_video(
            text_norm2, video_norm2, video_norm2, return_attention=return_attention
        )
        text_cross = (text_to_audio + text_to_video) / 2
        
        audio_features = audio_features + self.dropout(audio_cross)
        video_features = video_features + self.dropout(video_cross)
        text_features = text_features + self.dropout(text_cross)
        
        audio_ffn = self.ffn(self.norm3(audio_features))
        video_ffn = self.ffn(self.norm3(video_features))
        text_ffn = self.ffn(self.norm3(text_features))
        
        audio_features = audio_features + self.dropout(audio_ffn)
        video_features = video_features + self.dropout(video_ffn)
        text_features = text_features + self.dropout(text_ffn)
        
        attention_weights = None
        if return_attention:
            attention_weights = {
                'self': {
                    'audio': audio_attn_weights.cpu().numpy() if audio_attn_weights is not None else None,
                    'video': video_attn_weights.cpu().numpy() if video_attn_weights is not None else None,
                    'text': text_attn_weights.cpu().numpy() if text_attn_weights is not None else None,
                },
                'cross': {
                    'audio_to_video': av_weights.cpu().numpy() if av_weights is not None else None,
                    'audio_to_text': at_weights.cpu().numpy() if at_weights is not None else None,
                    'video_to_audio': va_weights.cpu().numpy() if va_weights is not None else None,
                    'video_to_text': vt_weights.cpu().numpy() if vt_weights is not None else None,
                    'text_to_audio': ta_weights.cpu().numpy() if ta_weights is not None else None,
                    'text_to_video': tv_weights.cpu().numpy() if tv_weights is not None else None,
                }
            }
        
        return audio_features, video_features, text_features, attention_weights


class MultimodalFusionTransformer(nn.Module):
    def __init__(
        self,
        audio_dim: int = 768,
        video_dim: int = 512,
        text_dim: int = 768,
        hidden_dim: int = 512,
        num_layers: int = 4,
        num_heads: int = 8,
        dim_ff: int = 2048,
        num_emotions: int = 7,
        max_time_steps: int = 100,
        dropout: float = 0.1,
        modality_dropout: float = 0.2,
        min_modality_weight: float = 0.15,
        weight_regularization: float = 0.01,
        device: str = "cuda" if torch.cuda.is_available() else "cpu"
    ):
        super().__init__()
        self.device = device
        self.hidden_dim = hidden_dim
        self.max_time_steps = max_time_steps
        self.min_modality_weight = min_modality_weight
        self.weight_regularization = weight_regularization
        self.modality_dropout_p = modality_dropout
        
        self.audio_proj = nn.Sequential(
            nn.Linear(audio_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.Dropout(dropout)
        )
        
        self.video_proj = nn.Sequential(
            nn.Linear(video_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.Dropout(dropout)
        )
        
        self.text_proj = nn.Sequential(
            nn.Linear(text_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.Dropout(dropout)
        )
        
        self.modality_embeddings = nn.ParameterDict({
            'audio': nn.Parameter(torch.randn(1, 1, hidden_dim)),
            'video': nn.Parameter(torch.randn(1, 1, hidden_dim)),
            'text': nn.Parameter(torch.randn(1, 1, hidden_dim))
        })
        
        self.time_positional_encoding = nn.Parameter(
            torch.randn(1, max_time_steps, hidden_dim)
        )
        
        self.layers = nn.ModuleList([
            TransformerEncoderLayer(hidden_dim, num_heads, dim_ff, dropout)
            for _ in range(num_layers)
        ])
        
        self.modality_weights = nn.Parameter(torch.ones(3) / 3)
        self.modality_dropout = nn.Dropout(modality_dropout)
        
        self.emotion_classifier = nn.Sequential(
            nn.Linear(hidden_dim * 3, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.LayerNorm(hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, num_emotions)
        )
        
        self.valence_arousal_head = nn.Sequential(
            nn.Linear(hidden_dim * 3, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.LayerNorm(hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 2),
            nn.Tanh()
        )
        
        self.modality_contribution_head = nn.Sequential(
            nn.Linear(hidden_dim * 3, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 3),
            nn.Softmax(dim=-1)
        )
        
        self.apply(self._init_weights)

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            nn.init.xavier_uniform_(module.weight)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.LayerNorm):
            nn.init.ones_(module.weight)
            nn.init.zeros_(module.bias)

    def forward(
        self,
        audio_features: np.ndarray,
        video_features: np.ndarray,
        text_features: np.ndarray,
        return_attention: bool = True
    ) -> Dict:
        audio_seq = torch.tensor(audio_features, dtype=torch.float32, device=self.device)
        video_seq = torch.tensor(video_features, dtype=torch.float32, device=self.device)
        text_tensor = torch.tensor(text_features, dtype=torch.float32, device=self.device)
        
        if len(audio_seq.shape) == 2:
            audio_seq = audio_seq.unsqueeze(0)
        if len(video_seq.shape) == 2:
            video_seq = video_seq.unsqueeze(0)
        if len(text_tensor.shape) == 1:
            text_tensor = text_tensor.unsqueeze(0).unsqueeze(0)
        elif len(text_tensor.shape) == 2:
            text_tensor = text_tensor.unsqueeze(0)
        
        batch_size = audio_seq.shape[0]
        num_time_steps = min(audio_seq.shape[1], video_seq.shape[1], self.max_time_steps)
        
        audio_seq = audio_seq[:, :num_time_steps, :]
        video_seq = video_seq[:, :num_time_steps, :]
        
        audio_emb = self.audio_proj(audio_seq)
        video_emb = self.video_proj(video_seq)
        text_emb = self.text_proj(text_tensor)
        
        if text_emb.shape[1] < num_time_steps:
            text_emb = text_emb.repeat(1, num_time_steps, 1)
        else:
            text_emb = text_emb[:, :num_time_steps, :]
        
        time_encoding = self.time_positional_encoding[:, :num_time_steps, :]
        audio_emb = audio_emb + time_encoding + self.modality_embeddings['audio']
        video_emb = video_emb + time_encoding + self.modality_embeddings['video']
        text_emb = text_emb + time_encoding + self.modality_embeddings['text']
        
        all_attention_weights = []
        for layer in self.layers:
            audio_emb, video_emb, text_emb, attention_weights = layer(
                audio_emb, video_emb, text_emb, return_attention=return_attention
            )
            if attention_weights is not None:
                all_attention_weights.append(attention_weights)
        
        audio_pooled = torch.mean(audio_emb, dim=1)
        video_pooled = torch.mean(video_emb, dim=1)
        text_pooled = torch.mean(text_emb, dim=1)
        
        weights = self._normalize_modality_weights(self.modality_weights)
        
        if self.training:
            weights = self._apply_modality_dropout(weights)
        
        weight_reg_loss = self._compute_weight_regularization(weights)
        self.add_module('weight_reg_loss', weight_reg_loss)
        
        fused_features = torch.cat([
            audio_pooled * weights[0],
            video_pooled * weights[1],
            text_pooled * weights[2]
        ], dim=-1)
        
        emotion_logits = self.emotion_classifier(fused_features)
        emotion_probs = F.softmax(emotion_logits, dim=-1)
        
        va_output = self.valence_arousal_head(fused_features)
        
        modality_contrib = self.modality_contribution_head(fused_features)
        
        time_attention_weights = self._compute_time_attention(
            audio_emb, video_emb, text_emb, num_time_steps
        )
        
        emotions = ['anger', 'joy', 'sadness', 'surprise', 'disgust', 'fear', 'neutral']
        emotion_probs_np = emotion_probs.cpu().numpy()[0]
        emotion_dict = {emotions[i]: float(emotion_probs_np[i]) for i in range(7)}
        
        dominant_idx = int(np.argmax(emotion_probs_np))
        dominant_emotion = emotions[dominant_idx]
        dominant_confidence = float(emotion_probs_np[dominant_idx])
        
        va_np = va_output.cpu().numpy()[0]
        modality_contrib_np = modality_contrib.cpu().numpy()[0]
        
        result = {
            'emotion': {
                'category': dominant_emotion,
                'confidence': dominant_confidence,
                'probabilities': emotion_dict
            },
            'valenceArousal': {
                'valence': float(va_np[0]),
                'arousal': float(va_np[1])
            },
            'modalityContributions': {
                'audio': float(modality_contrib_np[0]),
                'video': float(modality_contrib_np[1]),
                'text': float(modality_contrib_np[2])
            },
            'attentionWeights': {
                'timeSteps': num_time_steps,
                'modalities': ['audio', 'video', 'text'],
                'weights': time_attention_weights
            },
            'layerAttention': all_attention_weights
        }
        
        return result

    def _compute_time_attention(
        self,
        audio_emb: torch.Tensor,
        video_emb: torch.Tensor,
        text_emb: torch.Tensor,
        num_time_steps: int
    ) -> List[List[float]]:
        combined = (audio_emb + video_emb + text_emb) / 3
        cls_token = torch.mean(combined, dim=1, keepdim=True)
        
        attention_map = []
        for t in range(num_time_steps):
            time_features = combined[:, t, :]
            audio_sim = F.cosine_similarity(time_features, audio_emb[:, t, :], dim=-1)
            video_sim = F.cosine_similarity(time_features, video_emb[:, t, :], dim=-1)
            text_sim = F.cosine_similarity(time_features, text_emb[:, t, :], dim=-1)
            
            sims = torch.stack([audio_sim, video_sim, text_sim], dim=-1)
            sims = F.softmax(sims, dim=-1)
            attention_map.append(sims.cpu().numpy()[0].tolist())
        
        return attention_map

    def _normalize_modality_weights(self, weights: torch.Tensor) -> torch.Tensor:
        weights = F.softmax(weights, dim=0)
        
        min_w = self.min_modality_weight
        weights = torch.clamp(weights, min=min_w, max=1.0 - 2 * min_w)
        
        weights = weights / weights.sum()
        
        return weights

    def _apply_modality_dropout(self, weights: torch.Tensor) -> torch.Tensor:
        dropout_mask = torch.ones_like(weights)
        dropout_mask = self.modality_dropout(dropout_mask)
        
        weights = weights * dropout_mask
        
        if weights.sum() > 0:
            weights = weights / weights.sum()
        else:
            weights = torch.ones_like(weights) / 3.0
        
        return weights

    def _compute_weight_regularization(self, weights: torch.Tensor) -> torch.Tensor:
        target_entropy = torch.log(torch.tensor(3.0, device=self.device))
        current_entropy = -torch.sum(weights * torch.log(weights + 1e-10))
        entropy_loss = self.weight_regularization * (target_entropy - current_entropy)
        
        uniform_weights = torch.ones_like(weights) / 3.0
        mse_loss = self.weight_regularization * torch.sum((weights - uniform_weights) ** 2)
        
        max_weight = torch.max(weights)
        min_weight = torch.min(weights)
        spread_penalty = self.weight_regularization * 0.5 * (max_weight - min_weight) ** 2
        
        return entropy_loss + mse_loss + spread_penalty
