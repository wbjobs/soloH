import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Optional


class ReferenceEncoder(nn.Module):
    def __init__(self, config: dict):
        super().__init__()
        ref_config = config["reference_encoder"]
        
        self.ref_enc_filters = ref_config["ref_enc_filters"]
        self.ref_enc_size = ref_config["ref_enc_size"]
        self.ref_enc_strides = ref_config["ref_enc_strides"]
        self.ref_enc_pad = ref_config["ref_enc_pad"]
        self.ref_enc_gru_size = ref_config["ref_enc_gru_size"]
        self.style_embedding_dim = ref_config["style_embedding_dim"]
        
        self.n_mel_channels = config["audio"]["n_mel_channels"]
        
        K = len(self.ref_enc_filters)
        filters = [1] + self.ref_enc_filters
        
        convs = []
        for i in range(K):
            conv = nn.Conv2d(
                in_channels=filters[i],
                out_channels=filters[i + 1],
                kernel_size=self.ref_enc_size,
                stride=self.ref_enc_strides,
                padding=self.ref_enc_pad,
            )
            convs.append(conv)
            convs.append(nn.BatchNorm2d(filters[i + 1]))
            convs.append(nn.ReLU())
        
        self.convs = nn.Sequential(*convs)
        
        self.channel_proj = nn.Linear(
            self.ref_enc_filters[-1] * self.n_mel_channels // (2 ** K),
            self.ref_enc_gru_size,
        )
        
        self.gru = nn.GRU(
            input_size=self.ref_enc_gru_size,
            hidden_size=self.ref_enc_gru_size,
            batch_first=True,
        )
        
        self.fc = nn.Linear(self.ref_enc_gru_size, self.style_embedding_dim)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        batch_size = inputs.size(0)
        inputs = inputs.unsqueeze(1)
        
        outputs = self.convs(inputs)
        
        outputs = outputs.transpose(1, 2)
        outputs = outputs.contiguous().view(batch_size, outputs.size(1), -1)
        
        outputs = self.channel_proj(outputs)
        
        self.gru.flatten_parameters()
        _, hidden = self.gru(outputs)
        
        style_embedding = self.fc(hidden.squeeze(0))
        
        return style_embedding


class MultiHeadAttention(nn.Module):
    def __init__(self, hidden_dim: int, num_heads: int):
        super().__init__()
        assert hidden_dim % num_heads == 0
        
        self.hidden_dim = hidden_dim
        self.num_heads = num_heads
        self.head_dim = hidden_dim // num_heads
        
        self.q_proj = nn.Linear(hidden_dim, hidden_dim)
        self.k_proj = nn.Linear(hidden_dim, hidden_dim)
        self.v_proj = nn.Linear(hidden_dim, hidden_dim)
        self.o_proj = nn.Linear(hidden_dim, hidden_dim)
        
        self.scale = self.head_dim ** -0.5

    def forward(
        self,
        query: torch.Tensor,
        key: torch.Tensor,
        value: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        batch_size = query.size(0)
        
        q = self.q_proj(query).view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(key).view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(value).view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)
        
        scores = torch.matmul(q, k.transpose(-2, -1)) * self.scale
        
        if mask is not None:
            scores = scores.masked_fill(mask == 0, -1e9)
        
        weights = F.softmax(scores, dim=-1)
        
        output = torch.matmul(weights, v)
        output = output.transpose(1, 2).contiguous().view(batch_size, -1, self.hidden_dim)
        output = self.o_proj(output)
        
        return output, weights


class StyleTokenLayer(nn.Module):
    def __init__(self, num_tokens: int, token_dim: int, num_heads: int):
        super().__init__()
        self.num_tokens = num_tokens
        self.token_dim = token_dim
        
        self.tokens = nn.Parameter(torch.FloatTensor(num_tokens, token_dim))
        nn.init.normal_(self.tokens, mean=0, std=0.5)
        
        self.attention = MultiHeadAttention(token_dim, num_heads)

    def forward(self, style_embedding: torch.Tensor) -> torch.Tensor:
        batch_size = style_embedding.size(0)
        
        tokens = self.tokens.unsqueeze(0).expand(batch_size, -1, -1)
        
        query = style_embedding.unsqueeze(1)
        
        output, weights = self.attention(query, tokens, tokens)
        
        return output.squeeze(1)


class ProsodyEncoder(nn.Module):
    def __init__(self, config: dict):
        super().__init__()
        self.n_mel_channels = config["audio"]["n_mel_channels"]
        self.prosody_dim = config["emotion"]["prosody_dim"]
        
        self.conv1 = nn.Conv1d(self.n_mel_channels, 128, kernel_size=3, padding=1)
        self.conv2 = nn.Conv1d(128, 128, kernel_size=3, padding=1)
        self.pool = nn.MaxPool1d(2)
        
        self.gru = nn.GRU(128, 128, batch_first=True, bidirectional=True)
        
        self.fc_pitch = nn.Linear(256, 1)
        self.fc_energy = nn.Linear(256, 1)
        self.fc_duration = nn.Linear(256, 1)

    def forward(self, mel: torch.Tensor) -> torch.Tensor:
        x = mel.transpose(1, 2)
        
        x = F.relu(self.conv1(x))
        x = self.pool(x)
        x = F.relu(self.conv2(x))
        x = self.pool(x)
        
        x = x.transpose(1, 2)
        
        self.gru.flatten_parameters()
        _, h_n = self.gru(x)
        
        prosody_emb = torch.cat([h_n[0], h_n[1]], dim=-1)
        
        pitch = self.fc_pitch(prosody_emb)
        energy = self.fc_energy(prosody_emb)
        duration = self.fc_duration(prosody_emb)
        
        prosody_features = torch.cat([pitch, energy, duration], dim=-1)
        
        return prosody_features
