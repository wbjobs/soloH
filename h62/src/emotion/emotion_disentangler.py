import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Dict, List, Tuple, Optional, Union


class ContentEncoder(nn.Module):
    def __init__(self, config: dict):
        super().__init__()
        model_config = config["model"]
        self.encoder_embedding_dim = model_config["encoder_embedding_dim"]
        self.n_mel_channels = config["audio"]["n_mel_channels"]
        
        self.convolutions = nn.ModuleList()
        for i in range(3):
            in_channels = self.n_mel_channels if i == 0 else self.encoder_embedding_dim
            self.convolutions.append(
                nn.Sequential(
                    nn.Conv1d(
                        in_channels,
                        self.encoder_embedding_dim,
                        kernel_size=5,
                        padding=2,
                    ),
                    nn.BatchNorm1d(self.encoder_embedding_dim),
                    nn.ReLU(),
                    nn.Dropout(0.1),
                )
            )
        
        self.lstm = nn.LSTM(
            self.encoder_embedding_dim,
            self.encoder_embedding_dim // 2,
            num_layers=2,
            batch_first=True,
            bidirectional=True,
        )
        
        self.proj = nn.Linear(self.encoder_embedding_dim, self.encoder_embedding_dim)
    
    def forward(
        self,
        mel_spectrogram: torch.Tensor,
    ) -> torch.Tensor:
        x = mel_spectrogram
        
        for conv in self.convolutions:
            x = conv(x)
        
        x = x.transpose(1, 2)
        x, _ = self.lstm(x)
        x = self.proj(x)
        
        return x.transpose(1, 2)


class StyleEncoder(nn.Module):
    def __init__(self, config: dict):
        super().__init__()
        ref_config = config["reference_encoder"]
        emotion_config = config["emotion"]
        
        self.n_mel_channels = config["audio"]["n_mel_channels"]
        self.style_embedding_dim = ref_config["style_embedding_dim"]
        self.emotion_embedding_dim = emotion_config["emotion_embedding_dim"]
        
        ref_enc_filters = ref_config["ref_enc_filters"]
        ref_enc_size = ref_config["ref_enc_size"]
        ref_enc_strides = ref_config["ref_enc_strides"]
        ref_enc_pad = ref_config["ref_enc_pad"]
        
        n_layers = len(ref_enc_filters)
        ref_enc_sizes = ref_enc_size * (n_layers // len(ref_enc_size))
        ref_enc_strides_list = ref_enc_strides * (n_layers // len(ref_enc_strides))
        ref_enc_pads_list = ref_enc_pad * (n_layers // len(ref_enc_pad))
        
        self.convolutions = nn.ModuleList()
        in_channels = self.n_mel_channels
        for i, (out_channels, kernel_size, stride, padding) in enumerate(
            zip(ref_enc_filters, ref_enc_sizes, ref_enc_strides_list, ref_enc_pads_list)
        ):
            self.convolutions.append(
                nn.Sequential(
                    nn.Conv2d(
                        in_channels if i == 0 else ref_enc_filters[i-1],
                        out_channels,
                        kernel_size=(kernel_size, kernel_size),
                        stride=(stride, stride),
                        padding=(padding, padding),
                    ),
                    nn.BatchNorm2d(out_channels),
                    nn.ReLU(),
                )
            )
        
        self.gru = nn.GRU(
            ref_enc_filters[-1],
            self.style_embedding_dim,
            batch_first=True,
        )
        
        self.emotion_proj = nn.Linear(
            self.style_embedding_dim, 
            self.emotion_embedding_dim
        )
        self.speaker_proj = nn.Linear(
            self.style_embedding_dim, 
            config["speaker_adaptation"]["dvector_dim"]
        )
    
    def forward(
        self,
        mel_spectrogram: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        if mel_spectrogram.dim() == 3:
            x = mel_spectrogram.unsqueeze(2)
        elif mel_spectrogram.dim() == 2:
            x = mel_spectrogram.unsqueeze(0).unsqueeze(2)
        else:
            x = mel_spectrogram
        
        for conv in self.convolutions:
            x = conv(x)
        
        batch_size = x.size(0)
        x = x.view(batch_size, -1, x.size(-1))
        x = x.transpose(1, 2)
        
        _, style_embedding = self.gru(x)
        style_embedding = style_embedding.squeeze(0)
        
        emotion_embedding = self.emotion_proj(style_embedding)
        speaker_embedding = self.speaker_proj(style_embedding)
        
        return style_embedding, emotion_embedding, speaker_embedding


class AdversarialDiscriminator(nn.Module):
    def __init__(self, config: dict, target_type: str = "emotion"):
        super().__init__()
        model_config = config["model"]
        emotion_config = config["emotion"]
        
        input_dim = model_config["encoder_embedding_dim"]
        hidden_dim = 256
        
        if target_type == "emotion":
            output_dim = emotion_config["num_emotions"] if "num_emotions" in emotion_config else len(emotion_config["emotions"])
        else:
            output_dim = config["speaker_adaptation"]["num_speakers"]
        
        self.layers = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LeakyReLU(0.2),
            nn.Dropout(0.3),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LeakyReLU(0.2),
            nn.Dropout(0.3),
            nn.Linear(hidden_dim, output_dim),
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.dim() == 3:
            x = x.mean(dim=-1)
        return self.layers(x)


class EmotionDisentangler(nn.Module):
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        emotion_config = config["emotion"]
        
        self.content_encoder = ContentEncoder(config)
        self.style_encoder = StyleEncoder(config)
        
        self.emotion_discriminator = AdversarialDiscriminator(config, "emotion")
        self.speaker_discriminator = AdversarialDiscriminator(config, "speaker")
        
        self.reconstruction_decoder = nn.Sequential(
            nn.Conv1d(
                config["model"]["encoder_embedding_dim"] + emotion_config["emotion_embedding_dim"],
                512,
                kernel_size=3,
                padding=1,
            ),
            nn.ReLU(),
            nn.Conv1d(512, 256, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(256, config["audio"]["n_mel_channels"], kernel_size=3, padding=1),
        )
        
        self.lambda_adv = 0.1
        self.lambda_rec = 1.0
        self.lambda_cyc = 0.5
    
    def encode_content(
        self,
        mel_spectrogram: torch.Tensor,
    ) -> torch.Tensor:
        return self.content_encoder(mel_spectrogram)
    
    def encode_style(
        self,
        mel_spectrogram: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        return self.style_encoder(mel_spectrogram)
    
    def disentangle(
        self,
        mel_spectrogram: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        content = self.content_encoder(mel_spectrogram)
        style, emotion, speaker = self.style_encoder(mel_spectrogram)
        
        return {
            "content": content,
            "style": style,
            "emotion_embedding": emotion,
            "speaker_embedding": speaker,
        }
    
    def reconstruct(
        self,
        content: torch.Tensor,
        emotion_embedding: torch.Tensor,
    ) -> torch.Tensor:
        seq_len = content.size(-1)
        emotion_expanded = emotion_embedding.unsqueeze(-1).expand(-1, -1, seq_len)
        
        combined = torch.cat([content, emotion_expanded], dim=1)
        reconstructed = self.reconstruction_decoder(combined)
        
        return reconstructed
    
    def compute_adv_loss(
        self,
        content: torch.Tensor,
        target_emotion_labels: Optional[torch.Tensor] = None,
        target_speaker_labels: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        emotion_logits = self.emotion_discriminator(content)
        speaker_logits = self.speaker_discriminator(content)
        
        emotion_adv_loss = torch.tensor(0.0, device=content.device, dtype=content.dtype)
        speaker_adv_loss = torch.tensor(0.0, device=content.device, dtype=content.dtype)
        
        if target_emotion_labels is not None:
            uniform_target = torch.ones_like(emotion_logits) / emotion_logits.size(-1)
            emotion_adv_loss = F.kl_div(
                F.log_softmax(emotion_logits, dim=-1),
                uniform_target,
                reduction="batchmean",
            )
        
        if target_speaker_labels is not None:
            uniform_target = torch.ones_like(speaker_logits) / speaker_logits.size(-1)
            speaker_adv_loss = F.kl_div(
                F.log_softmax(speaker_logits, dim=-1),
                uniform_target,
                reduction="batchmean",
            )
        
        return emotion_adv_loss, speaker_adv_loss
    
    def compute_rec_loss(
        self,
        reconstructed: torch.Tensor,
        original: torch.Tensor,
    ) -> torch.Tensor:
        return F.l1_loss(reconstructed, original)
    
    def compute_cycle_loss(
        self,
        content1: torch.Tensor,
        content2: torch.Tensor,
    ) -> torch.Tensor:
        return F.l1_loss(content1, content2)
    
    def forward(
        self,
        mel_spectrogram: torch.Tensor,
        target_emotion_embedding: Optional[torch.Tensor] = None,
        emotion_labels: Optional[torch.Tensor] = None,
        speaker_labels: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        disentangled = self.disentangle(mel_spectrogram)
        content = disentangled["content"]
        original_emotion = disentangled["emotion_embedding"]
        
        if target_emotion_embedding is None:
            target_emotion_embedding = original_emotion
        
        reconstructed = self.reconstruct(content, target_emotion_embedding)
        
        losses = {}
        
        losses["rec_loss"] = self.compute_rec_loss(reconstructed, mel_spectrogram)
        
        emotion_adv_loss, speaker_adv_loss = self.compute_adv_loss(
            content, emotion_labels, speaker_labels
        )
        losses["emotion_adv_loss"] = emotion_adv_loss
        losses["speaker_adv_loss"] = speaker_adv_loss
        
        losses["total_loss"] = (
            self.lambda_rec * losses["rec_loss"] +
            self.lambda_adv * (losses["emotion_adv_loss"] + losses["speaker_adv_loss"])
        )
        
        return {
            "disentangled": disentangled,
            "reconstructed": reconstructed,
            "losses": losses,
        }
    
    def transfer_emotion(
        self,
        source_mel: torch.Tensor,
        target_emotion_mel: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        source_disentangled = self.disentangle(source_mel)
        target_disentangled = self.disentangle(target_emotion_mel)
        
        source_content = source_disentangled["content"]
        target_emotion = target_disentangled["emotion_embedding"]
        target_speaker = target_disentangled["speaker_embedding"]
        
        transferred_mel = self.reconstruct(source_content, target_emotion)
        
        return {
            "transferred_mel": transferred_mel,
            "source_content": source_content,
            "target_emotion_embedding": target_emotion,
            "target_speaker_embedding": target_speaker,
        }
    
    def add_emotion_to_neutral(
        self,
        neutral_mel: torch.Tensor,
        target_emotion_embedding: torch.Tensor,
    ) -> torch.Tensor:
        content = self.content_encoder(neutral_mel)
        emotional_mel = self.reconstruct(content, target_emotion_embedding)
        return emotional_mel
    
    def get_content_representation(
        self,
        mel_spectrogram: torch.Tensor,
    ) -> np.ndarray:
        with torch.no_grad():
            content = self.content_encoder(mel_spectrogram)
        return content.cpu().numpy()
    
    def get_style_representation(
        self,
        mel_spectrogram: torch.Tensor,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        with torch.no_grad():
            style, emotion, speaker = self.style_encoder(mel_spectrogram)
        return (
            style.cpu().numpy(),
            emotion.cpu().numpy(),
            speaker.cpu().numpy(),
        )
