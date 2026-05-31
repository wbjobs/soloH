import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Dict, List, Tuple, Optional, Union
import os
from tqdm import tqdm


class SpeakerEmbedding(nn.Module):
    def __init__(self, config: dict):
        super().__init__()
        spk_config = config["speaker_adaptation"]
        
        self.num_speakers = spk_config["num_speakers"]
        self.dvector_dim = spk_config["dvector_dim"]
        
        self.speaker_embeddings = nn.Embedding(
            self.num_speakers,
            self.dvector_dim,
        )
        
        nn.init.normal_(self.speaker_embeddings.weight, mean=0, std=0.01)

    def forward(self, speaker_ids: torch.Tensor) -> torch.Tensor:
        return self.speaker_embeddings(speaker_ids)

    def get_speaker_embedding(self, speaker_id: int) -> torch.Tensor:
        idx_tensor = torch.tensor([speaker_id], dtype=torch.long)
        return self.forward(idx_tensor).squeeze(0)


class DVectorExtractor(nn.Module):
    def __init__(self, config: dict):
        super().__init__()
        spk_config = config["speaker_adaptation"]
        
        self.dvector_dim = spk_config["dvector_dim"]
        self.n_mel_channels = config["audio"]["n_mel_channels"]
        self.hidden_dim = 768
        self.num_layers = 3
        
        self.lstm = nn.LSTM(
            input_size=self.n_mel_channels,
            hidden_size=self.hidden_dim,
            num_layers=self.num_layers,
            batch_first=True,
            bidirectional=False,
            dropout=0.3,
        )
        
        self.projection = nn.Linear(self.hidden_dim, self.dvector_dim)
        
        self.dropout = nn.Dropout(0.3)

    def forward(self, mel_spectrogram: torch.Tensor) -> torch.Tensor:
        batch_size = mel_spectrogram.size(0)
        
        if mel_spectrogram.dim() == 4:
            mel_spectrogram = mel_spectrogram.squeeze(1)
        
        x = mel_spectrogram.transpose(1, 2)
        
        self.lstm.flatten_parameters()
        output, (h_n, _) = self.lstm(x)
        
        dvector = self.projection(h_n[-1])
        dvector = F.normalize(dvector, p=2, dim=-1)
        
        return dvector

    def extract_from_wav(
        self,
        wav: np.ndarray,
        audio_processor,
    ) -> torch.Tensor:
        mel = audio_processor.wav_to_mel(wav)
        mel_tensor = torch.tensor(mel, dtype=torch.float32).unsqueeze(0)
        
        with torch.no_grad():
            dvector = self.forward(mel_tensor)
        
        return dvector.squeeze(0)

    def extract_from_file(
        self,
        wav_path: str,
        audio_processor,
    ) -> torch.Tensor:
        wav = audio_processor.load_wav(wav_path)
        return self.extract_from_wav(wav, audio_processor)

    def extract_from_files(
        self,
        wav_paths: List[str],
        audio_processor,
    ) -> torch.Tensor:
        dvectors = []
        for wav_path in wav_paths:
            dvector = self.extract_from_file(wav_path, audio_processor)
            dvectors.append(dvector)
        
        dvectors = torch.stack(dvectors)
        mean_dvector = torch.mean(dvectors, dim=0)
        mean_dvector = F.normalize(mean_dvector, p=2, dim=-1)
        
        return mean_dvector


class SpeakerAdapter(nn.Module):
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        spk_config = config["speaker_adaptation"]
        
        self.dvector_dim = spk_config["dvector_dim"]
        self.style_embedding_dim = config["reference_encoder"]["style_embedding_dim"]
        
        self.speaker_embedding = SpeakerEmbedding(config)
        self.dvector_extractor = DVectorExtractor(config)
        
        self.adapter_layer = nn.Sequential(
            nn.Linear(self.dvector_dim, self.style_embedding_dim),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(self.style_embedding_dim, self.style_embedding_dim),
        )
        
        self.layer_norm = nn.LayerNorm(self.style_embedding_dim)

    def get_speaker_embedding_from_id(self, speaker_id: int) -> torch.Tensor:
        return self.speaker_embedding.get_speaker_embedding(speaker_id)

    def get_speaker_embedding_from_reference(
        self,
        reference_mel: torch.Tensor,
    ) -> torch.Tensor:
        with torch.no_grad():
            dvector = self.dvector_extractor(reference_mel.unsqueeze(0))
        adapted_embedding = self.adapter_layer(dvector)
        adapted_embedding = self.layer_norm(adapted_embedding)
        return adapted_embedding.squeeze(0)

    def adapt_speaker_embedding(
        self,
        dvector: torch.Tensor,
        emotion_embedding: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        speaker_emb = self.adapter_layer(dvector.unsqueeze(0)).squeeze(0)
        speaker_emb = self.layer_norm(speaker_emb)
        
        if emotion_embedding is not None:
            combined = speaker_emb + 0.3 * emotion_embedding
            return combined
        
        return speaker_emb

    def combine_speaker_and_emotion(
        self,
        speaker_embedding: torch.Tensor,
        emotion_embedding: torch.Tensor,
        speaker_weight: float = 0.7,
    ) -> torch.Tensor:
        combined = speaker_weight * speaker_embedding + (1 - speaker_weight) * emotion_embedding
        return combined


class SpeakerAdaptation:
    def __init__(
        self,
        config: dict,
        tacotron_model: Optional[nn.Module] = None,
        speaker_adapter: Optional[SpeakerAdapter] = None,
    ):
        self.config = config
        spk_config = config["speaker_adaptation"]
        
        self.fine_tune_steps = spk_config["fine_tune_steps"]
        self.learning_rate = spk_config["learning_rate"]
        self.dvector_dim = spk_config["dvector_dim"]
        
        self.speaker_adapter = speaker_adapter or SpeakerAdapter(config)
        self.tacotron_model = tacotron_model
        
        from ..utils.audio import AudioProcessor
        self.audio_processor = AudioProcessor(config)
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.speaker_adapter.to(self.device)

    def extract_speaker_embedding(
        self,
        reference_audio_paths: List[str],
    ) -> torch.Tensor:
        dvector = self.speaker_adapter.dvector_extractor.extract_from_files(
            reference_audio_paths,
            self.audio_processor,
        )
        return dvector.to(self.device)

    def prepare_for_fine_tuning(
        self,
        dvector: torch.Tensor,
        freeze_encoder: bool = True,
        freeze_decoder: bool = True,
    ):
        if self.tacotron_model is None:
            raise ValueError("Tacotron model is not provided")
        
        if freeze_encoder:
            for param in self.tacotron_model.encoder.parameters():
                param.requires_grad = False
        
        if freeze_decoder:
            for param in self.tacotron_model.decoder.parameters():
                param.requires_grad = False
        
        for param in self.speaker_adapter.adapter_layer.parameters():
            param.requires_grad = True
        
        for param in self.tacotron_model.style_proj.parameters():
            param.requires_grad = True

    def fine_tune(
        self,
        reference_mels: List[np.ndarray],
        reference_texts: List[str],
        text_processor,
        emotion_embedding: Optional[torch.Tensor] = None,
        emotion_intensity: float = 1.0,
    ) -> Dict[str, float]:
        if self.tacotron_model is None:
            raise ValueError("Tacotron model is not provided")
        
        original_train_mode = self.tacotron_model.training
        self.tacotron_model.train()
        
        optimizer = torch.optim.Adam(
            [
                {"params": self.speaker_adapter.adapter_layer.parameters()},
                {"params": self.tacotron_model.style_proj.parameters()},
            ],
            lr=self.learning_rate,
        )
        
        dvector = self.speaker_adapter.dvector_extractor(
            torch.tensor(reference_mels[0], dtype=torch.float32).unsqueeze(0).to(self.device)
        )
        
        speaker_emb = self.speaker_adapter.adapt_speaker_embedding(
            dvector,
            emotion_embedding,
        )
        
        losses = []
        
        pbar = tqdm(range(self.fine_tune_steps), desc="Fine-tuning speaker")
        for step in pbar:
            total_loss = 0.0
            
            for mel, text in zip(reference_mels, reference_texts):
                text_seq = text_processor.encode(text)
                text_tensor = torch.tensor(text_seq, dtype=torch.long).unsqueeze(0).to(self.device)
                text_length = torch.tensor([len(text_seq)], dtype=torch.long).to(self.device)
                
                mel_tensor = torch.tensor(mel, dtype=torch.float32).unsqueeze(0).to(self.device)
                
                gate_target = torch.zeros(
                    (1, mel.shape[1]),
                    dtype=torch.float32,
                    device=self.device,
                )
                gate_target[:, -1] = 1.0
                
                output_length = torch.tensor([mel.shape[1]], dtype=torch.long).to(self.device)
                
                prosody_features = torch.zeros(
                    (1, self.config["emotion"]["prosody_dim"]),
                    dtype=torch.float32,
                    device=self.device,
                )
                
                if emotion_embedding is None:
                    emotion_emb = torch.zeros(
                        (1, self.config["emotion"]["emotion_embedding_dim"]),
                        dtype=torch.float32,
                        device=self.device,
                    )
                else:
                    emotion_emb = emotion_embedding.unsqueeze(0).to(self.device)
                
                mel_outputs, mel_outputs_postnet, gate_outputs, alignments = self.tacotron_model(
                    (
                        text_tensor,
                        text_length,
                        mel_tensor,
                        mel.shape[1],
                        output_length,
                        speaker_emb.unsqueeze(0),
                        emotion_emb,
                        prosody_features,
                    )
                )
                
                mel_loss = nn.MSELoss()(mel_outputs, mel_tensor) + nn.MSELoss()(mel_outputs_postnet, mel_tensor)
                gate_loss = nn.BCEWithLogitsLoss()(gate_outputs, gate_target)
                
                loss = mel_loss + gate_loss
                
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                
                total_loss += loss.item()
            
            avg_loss = total_loss / len(reference_mels)
            losses.append(avg_loss)
            pbar.set_postfix({"loss": f"{avg_loss:.4f}"})
        
        if not original_train_mode:
            self.tacotron_model.eval()
        
        return {
            "final_loss": losses[-1],
            "average_loss": sum(losses) / len(losses),
            "min_loss": min(losses),
            "steps": len(losses),
        }

    def adapt(
        self,
        reference_audio_paths: List[str],
        reference_texts: Optional[List[str]] = None,
        text_processor=None,
        emotion_embedding: Optional[torch.Tensor] = None,
        do_fine_tuning: bool = True,
    ) -> Tuple[torch.Tensor, Optional[Dict[str, float]]]:
        dvector = self.extract_speaker_embedding(reference_audio_paths)
        
        speaker_embedding = self.speaker_adapter.adapt_speaker_embedding(
            dvector,
            emotion_embedding,
        )
        
        fine_tune_stats = None
        if do_fine_tuning and reference_texts is not None and text_processor is not None:
            reference_mels = [
                self.audio_processor.get_mel_from_file(path)
                for path in reference_audio_paths
            ]
            
            fine_tune_stats = self.fine_tune(
                reference_mels,
                reference_texts,
                text_processor,
                emotion_embedding,
            )
        
        return speaker_embedding, fine_tune_stats

    def save_speaker_embedding(self, speaker_embedding: torch.Tensor, save_path: str) -> None:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        torch.save({
            "speaker_embedding": speaker_embedding.cpu(),
            "dvector_dim": self.dvector_dim,
        }, save_path)

    def load_speaker_embedding(self, load_path: str) -> torch.Tensor:
        checkpoint = torch.load(load_path, map_location=self.device)
        speaker_embedding = checkpoint["speaker_embedding"].to(self.device)
        return speaker_embedding

    def save_adapter_weights(self, save_path: str) -> None:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        torch.save({
            "adapter_state_dict": self.speaker_adapter.adapter_layer.state_dict(),
            "layer_norm_state_dict": self.speaker_adapter.layer_norm.state_dict(),
        }, save_path)

    def load_adapter_weights(self, load_path: str) -> None:
        if not os.path.exists(load_path):
            raise FileNotFoundError(f"Adapter weights not found: {load_path}")
        
        checkpoint = torch.load(load_path, map_location=self.device)
        self.speaker_adapter.adapter_layer.load_state_dict(checkpoint["adapter_state_dict"])
        self.speaker_adapter.layer_norm.load_state_dict(checkpoint["layer_norm_state_dict"])
        self.speaker_adapter.eval()


class MultiSpeakerEmotionTransfer(nn.Module):
    def __init__(
        self,
        config: dict,
        tacotron_model: Optional[nn.Module] = None,
        device: Optional[str] = None,
    ):
        super().__init__()
        self.config = config
        self.device = torch.device(device if device else ("cuda" if torch.cuda.is_available() else "cpu"))
        
        self.tacotron_model = tacotron_model
        
        spk_config = config["speaker_adaptation"]
        self.dvector_dim = spk_config["dvector_dim"]
        self.emotion_embedding_dim = config["emotion"]["emotion_embedding_dim"]
        self.style_embedding_dim = config["reference_encoder"]["style_embedding_dim"]
        
        self.dvector_extractor = DVectorExtractor(config)
        
        self.emotion_projection = nn.Sequential(
            nn.Linear(self.emotion_embedding_dim + self.dvector_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, self.style_embedding_dim),
        )
        
        self.content_adapter = nn.Sequential(
            nn.Conv1d(
                config["model"]["encoder_embedding_dim"],
                config["model"]["encoder_embedding_dim"],
                kernel_size=3,
                padding=1,
            ),
            nn.BatchNorm1d(config["model"]["encoder_embedding_dim"]),
            nn.ReLU(),
            nn.Conv1d(
                config["model"]["encoder_embedding_dim"],
                config["model"]["encoder_embedding_dim"],
                kernel_size=3,
                padding=1,
            ),
        )
        
        self.to(self.device)
    
    def extract_speaker_embedding(
        self,
        audio_path: str,
    ) -> torch.Tensor:
        mel = self._load_mel(audio_path)
        with torch.no_grad():
            dvector = self.dvector_extractor(mel.unsqueeze(0).to(self.device))
        return dvector.squeeze(0).cpu()
    
    def extract_emotion_embedding(
        self,
        audio_path: str,
        emotion_controller,
    ) -> torch.Tensor:
        mel = self._load_mel(audio_path)
        mel_tensor = torch.tensor(mel, dtype=torch.float32).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            if hasattr(emotion_controller, 'emotion_disentangler'):
                _, emotion_emb, _ = emotion_controller.emotion_disentangler.encode_style(mel_tensor)
            else:
                emotion_emb = torch.zeros(self.emotion_embedding_dim)
        
        return emotion_emb.squeeze(0).cpu()
    
    def transfer_emotion_between_speakers(
        self,
        source_emotion_audio: str,
        target_speaker_audio: str,
        text: str,
        emotion_controller,
        text_processor,
        emotion_intensity: float = 1.0,
        reference_emotion: Optional[str] = None,
    ) -> Dict[str, torch.Tensor]:
        source_emotion_emb = self.extract_emotion_embedding(
            source_emotion_audio, emotion_controller
        )
        
        target_speaker_emb = self.extract_speaker_embedding(target_speaker_audio)
        
        if reference_emotion is not None:
            source_emotion_emb, _ = emotion_controller.process_emotion_input(
                reference_emotion, emotion_intensity
            )
        
        combined_style = self._combine_emotion_and_speaker(
            source_emotion_emb.to(self.device),
            target_speaker_emb.to(self.device),
        )
        
        text_seq = text_processor.encode(text)
        text_tensor = torch.tensor(text_seq, dtype=torch.long).unsqueeze(0).to(self.device)
        text_length = torch.tensor([len(text_seq)], dtype=torch.long).to(self.device)
        
        if self.tacotron_model is not None:
            with torch.no_grad():
                emotion_emb = source_emotion_emb.unsqueeze(0).to(self.device)
                prosody_features = torch.zeros(
                    (1, self.config["emotion"]["prosody_dim"]),
                    dtype=torch.float32,
                    device=self.device,
                )
                
                mel_outputs, mel_outputs_postnet, gate_outputs, alignments = self.tacotron_model.inference(
                    text_tensor,
                    text_length,
                    combined_style.unsqueeze(0),
                    emotion_emb,
                    prosody_features,
                )
        else:
            mel_outputs_postnet = torch.zeros(1, 80, 100)
        
        return {
            "mel_spectrogram": mel_outputs_postnet.squeeze(0).cpu(),
            "source_emotion_embedding": source_emotion_emb,
            "target_speaker_embedding": target_speaker_emb,
            "combined_style_embedding": combined_style.cpu(),
        }
    
    def _combine_emotion_and_speaker(
        self,
        emotion_embedding: torch.Tensor,
        speaker_embedding: torch.Tensor,
    ) -> torch.Tensor:
        if emotion_embedding.dim() == 1:
            emotion_embedding = emotion_embedding.unsqueeze(0)
        if speaker_embedding.dim() == 1:
            speaker_embedding = speaker_embedding.unsqueeze(0)
        
        combined = torch.cat([emotion_embedding, speaker_embedding], dim=-1)
        style_emb = self.emotion_projection(combined)
        
        return style_emb.squeeze(0)
    
    def _load_mel(self, audio_path: str) -> np.ndarray:
        from ..utils.audio import AudioProcessor
        audio_processor = AudioProcessor(self.config)
        return audio_processor.get_mel_from_file(audio_path)
    
    def save_transfer_model(self, save_path: str) -> None:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        torch.save({
            "emotion_projection_state_dict": self.emotion_projection.state_dict(),
            "content_adapter_state_dict": self.content_adapter.state_dict(),
            "dvector_extractor_state_dict": self.dvector_extractor.state_dict(),
        }, save_path)
    
    def load_transfer_model(self, load_path: str) -> None:
        if not os.path.exists(load_path):
            raise FileNotFoundError(f"Transfer model weights not found: {load_path}")
        
        checkpoint = torch.load(load_path, map_location=self.device)
        self.emotion_projection.load_state_dict(checkpoint["emotion_projection_state_dict"])
        self.content_adapter.load_state_dict(checkpoint["content_adapter_state_dict"])
        self.dvector_extractor.load_state_dict(checkpoint["dvector_extractor_state_dict"])
        self.eval()
