import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Optional, Tuple
from . import utils


class TDNNLayer(nn.Module):
    def __init__(self, in_channels: int, out_channels: int,
                 kernel_size: int, dilation: int = 1):
        super().__init__()
        self.conv = nn.Conv1d(in_channels, out_channels, kernel_size, dilation=dilation)
        self.activation = nn.ReLU()
        self.bn = nn.BatchNorm1d(out_channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.conv(x)
        x = self.activation(x)
        x = self.bn(x)
        return x


class StatsPooling(nn.Module):
    def __init__(self):
        super().__init__()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        mean = torch.mean(x, dim=2)
        std = torch.std(x, dim=2)
        return torch.cat([mean, std], dim=1)


class XVector(nn.Module):
    def __init__(self, input_dim: int = 80, embedding_dim: int = 512):
        super().__init__()
        self.input_dim = input_dim
        self.embedding_dim = embedding_dim

        self.tdnn1 = TDNNLayer(input_dim, 512, kernel_size=5, dilation=1)
        self.tdnn2 = TDNNLayer(512, 512, kernel_size=3, dilation=2)
        self.tdnn3 = TDNNLayer(512, 512, kernel_size=3, dilation=3)
        self.tdnn4 = TDNNLayer(512, 512, kernel_size=1, dilation=1)
        self.tdnn5 = TDNNLayer(512, 1500, kernel_size=1, dilation=1)

        self.stats_pooling = StatsPooling()

        self.fc1 = nn.Linear(3000, embedding_dim)
        self.fc2 = nn.Linear(embedding_dim, embedding_dim)
        self.bn1 = nn.BatchNorm1d(embedding_dim)
        self.bn2 = nn.BatchNorm1d(embedding_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.tdnn1(x)
        x = self.tdnn2(x)
        x = self.tdnn3(x)
        x = self.tdnn4(x)
        x = self.tdnn5(x)

        x = self.stats_pooling(x)

        x = self.fc1(x)
        x = F.relu(x)
        x = self.bn1(x)
        x = self.fc2(x)
        x = self.bn2(x)

        return F.normalize(x, p=2, dim=1)


class SEBlock(nn.Module):
    def __init__(self, channels: int, reduction: int = 16):
        super().__init__()
        self.avg_pool = nn.AdaptiveAvgPool1d(1)
        self.fc = nn.Sequential(
            nn.Linear(channels, channels // reduction, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(channels // reduction, channels, bias=False),
            nn.Sigmoid()
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, c, _ = x.size()
        y = self.avg_pool(x).view(b, c)
        y = self.fc(y).view(b, c, 1)
        return x * y.expand_as(x)


class ECAPA_TDNN_Block(nn.Module):
    def __init__(self, channels: int, kernel_size: int = 3, dilation: int = 1):
        super().__init__()
        self.conv1 = nn.Conv1d(channels, channels, kernel_size, padding=dilation, dilation=dilation)
        self.bn1 = nn.BatchNorm1d(channels)
        self.relu = nn.ReLU()
        self.conv2 = nn.Conv1d(channels, channels, kernel_size, padding=dilation, dilation=dilation)
        self.bn2 = nn.BatchNorm1d(channels)
        self.se = SEBlock(channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.conv2(x)
        x = self.bn2(x)
        x = self.se(x)
        return x + residual


class AttentiveStatsPooling(nn.Module):
    def __init__(self, in_dim: int, hidden_dim: int = 128):
        super().__init__()
        self.attention = nn.Sequential(
            nn.Conv1d(in_dim * 3, hidden_dim, kernel_size=1),
            nn.ReLU(),
            nn.BatchNorm1d(hidden_dim),
            nn.Conv1d(hidden_dim, in_dim, kernel_size=1),
            nn.Softmax(dim=2)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        mean = torch.mean(x, dim=2, keepdim=True)
        std = torch.std(x, dim=2, keepdim=True)
        mean = mean.expand_as(x)
        std = std.expand_as(x)

        stats = torch.cat([x, mean, std], dim=1)
        weights = self.attention(stats)

        weighted_mean = torch.sum(x * weights, dim=2)
        weighted_var = torch.sum((x ** 2) * weights, dim=2) - weighted_mean ** 2
        weighted_std = torch.sqrt(weighted_var + 1e-8)

        return torch.cat([weighted_mean, weighted_std], dim=1)


class ECAPA_TDNN(nn.Module):
    def __init__(self, input_dim: int = 80, embedding_dim: int = 192, channels: int = 512):
        super().__init__()
        self.input_dim = input_dim
        self.embedding_dim = embedding_dim
        self.channels = channels

        self.layer1 = nn.Sequential(
            nn.Conv1d(input_dim, channels, kernel_size=5, padding=2),
            nn.BatchNorm1d(channels),
            nn.ReLU()
        )

        self.block1 = ECAPA_TDNN_Block(channels, kernel_size=3, dilation=2)
        self.block2 = ECAPA_TDNN_Block(channels, kernel_size=3, dilation=3)
        self.block3 = ECAPA_TDNN_Block(channels, kernel_size=3, dilation=4)

        self.layer2 = nn.Sequential(
            nn.Conv1d(channels * 3, channels * 3, kernel_size=1),
            nn.BatchNorm1d(channels * 3),
            nn.ReLU()
        )

        self.asp = AttentiveStatsPooling(channels * 3)

        self.fc1 = nn.Linear(channels * 6, embedding_dim)
        self.bn1 = nn.BatchNorm1d(embedding_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.layer1(x)

        b1 = self.block1(x)
        b2 = self.block2(b1)
        b3 = self.block3(b2)

        concat = torch.cat([b1, b2, b3], dim=1)
        x = self.layer2(concat)

        x = self.asp(x)

        x = self.fc1(x)
        x = self.bn1(x)

        return F.normalize(x, p=2, dim=1)


class SpeakerEmbeddingExtractor:
    def __init__(self, model_type: str = 'ecapa', embedding_dim: int = 192,
                 sample_rate: int = 16000, device: str = 'cpu'):
        self.model_type = model_type.lower()
        self.embedding_dim = embedding_dim
        self.sample_rate = sample_rate
        self.device = device

        if self.model_type == 'xvector':
            self.model = XVector(input_dim=80, embedding_dim=embedding_dim)
        elif self.model_type == 'ecapa':
            self.model = ECAPA_TDNN(input_dim=80, embedding_dim=embedding_dim)
        else:
            raise ValueError(f"不支持的模型类型: {model_type}")

        self.model.to(device)
        self.model.eval()

    def extract_embedding(self, audio: np.ndarray) -> np.ndarray:
        mel_spec = utils.compute_mel_spectrogram(
            audio, sample_rate=self.sample_rate,
            n_fft=512, hop_length=160, n_mels=80
        )
        
        mel_tensor = torch.tensor(mel_spec, dtype=torch.float32, device=self.device)
        mel_tensor = mel_tensor.unsqueeze(0)

        with torch.no_grad():
            embedding = self.model(mel_tensor)

        return utils.to_numpy(embedding.squeeze(0))

    def extract_embeddings_batch(self, audios: list) -> np.ndarray:
        embeddings = []
        for audio in audios:
            emb = self.extract_embedding(audio)
            embeddings.append(emb)
        return np.array(embeddings)

    def enroll_speaker(self, audio_samples: list) -> np.ndarray:
        embeddings = self.extract_embeddings_batch(audio_samples)
        mean_embedding = np.mean(embeddings, axis=0)
        return mean_embedding / (np.linalg.norm(mean_embedding) + 1e-8)
