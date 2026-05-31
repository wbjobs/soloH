import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import os
from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass, field
import json

from ..utils.config import load_config
from ..utils.audio import AudioProcessor
from ..utils.text import TextProcessor
from ..models.reference_encoder import ReferenceEncoder
from ..models.tacotron2 import Tacotron2
from ..models.waveglow import WaveGlow
from ..models.hifigan import HiFiGAN
from ..emotion.emotion_controller import EmotionController
from ..emotion.emotion_classifier import EmotionQualityValidator
from ..emotion.emotion_disentangler import EmotionDisentangler
from ..speaker.speaker_adapter import SpeakerAdaptation, MultiSpeakerEmotionTransfer


@dataclass
class SynthesisResult:
    wav: np.ndarray
    mel_spectrogram: np.ndarray
    sampling_rate: int
    emotion: Union[str, Dict[str, float]]
    emotion_intensity: float
    speaker_embedding: Optional[torch.Tensor] = None
    style_embedding: Optional[torch.Tensor] = None
    prosody_features: Optional[np.ndarray] = None
    validation_result: Optional[Dict] = None
    output_path: Optional[str] = None
    
    def save(self, output_dir: str, filename: str = None) -> str:
        if filename is None:
            emotion_str = self.emotion if isinstance(self.emotion, str) else "_".join(
                [f"{k}{v:.2f}" for k, v in self.emotion.items()]
            )
            filename = f"{emotion_str}_int{self.emotion_intensity:.2f}.wav"
        
        output_path = os.path.join(output_dir, filename)
        self.save_wav(output_path)
        self.output_path = output_path
        return output_path
    
    def save_wav(self, wav_path: str) -> None:
        from scipy.io.wavfile import write
        wav = self.wav / np.max(np.abs(self.wav)) * 0.95
        write(wav_path, self.sampling_rate, (wav * 32768.0).astype(np.int16))
    
    def save_mel(self, mel_path: str) -> None:
        np.save(mel_path, self.mel_spectrogram)
    
    def to_dict(self) -> Dict:
        return {
            "sampling_rate": self.sampling_rate,
            "emotion": self.emotion,
            "emotion_intensity": self.emotion_intensity,
            "wav_length": len(self.wav) / self.sampling_rate,
            "mel_shape": self.mel_spectrogram.shape,
            "validation_result": self.validation_result,
            "output_path": self.output_path,
        }


class TTSEngine:
    def __init__(
        self,
        config_path: str,
        device: Optional[str] = None,
        vocoder_type: str = "waveglow",
    ):
        self.config = load_config(config_path)
        
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)
        
        self.vocoder_type = vocoder_type
        
        self._init_processors()
        self._init_models()
        self._init_emotion_controller()
        self._init_validator()
        
        self.output_dir = self.config["paths"]["output_dir"]
        os.makedirs(self.output_dir, exist_ok=True)

    def _init_processors(self):
        self.audio_processor = AudioProcessor(self.config)
        self.text_processor = TextProcessor()

    def _init_models(self):
        self.tacotron2 = Tacotron2(self.config).to(self.device)
        self.tacotron2.eval()
        
        self.reference_encoder = ReferenceEncoder(self.config).to(self.device)
        self.reference_encoder.eval()
        
        if self.vocoder_type == "waveglow":
            self.vocoder = WaveGlow(self.config).to(self.device)
        else:
            self.vocoder = HiFiGAN(self.config).to(self.device)
        self.vocoder.eval()

    def _init_emotion_controller(self):
        self.emotion_controller = EmotionController(self.config).to(self.device)
        self.emotion_controller.eval()
        
        self.emotion_disentangler = EmotionDisentangler(self.config).to(self.device)
        self.emotion_disentangler.eval()
        
        self.speaker_adaptation = SpeakerAdaptation(
            self.config,
            tacotron_model=self.tacotron2,
        )
        
        self.multi_speaker_transfer = MultiSpeakerEmotionTransfer(
            self.config,
            tacotron_model=self.tacotron2,
            device=self.device,
        )
        self.multi_speaker_transfer.eval()

    def _init_validator(self):
        self.validator = EmotionQualityValidator(self.config)

    def load_pretrained_models(
        self,
        tacotron_path: Optional[str] = None,
        reference_encoder_path: Optional[str] = None,
        vocoder_path: Optional[str] = None,
        emotion_embedding_path: Optional[str] = None,
        classifier_path: Optional[str] = None,
    ):
        if tacotron_path and os.path.exists(tacotron_path):
            checkpoint = torch.load(tacotron_path, map_location=self.device)
            self.tacotron2.load_state_dict(checkpoint["model_state_dict"])
            print(f"Loaded Tacotron2 from {tacotron_path}")
        
        if reference_encoder_path and os.path.exists(reference_encoder_path):
            checkpoint = torch.load(reference_encoder_path, map_location=self.device)
            self.reference_encoder.load_state_dict(checkpoint["model_state_dict"])
            print(f"Loaded ReferenceEncoder from {reference_encoder_path}")
        
        if vocoder_path and os.path.exists(vocoder_path):
            checkpoint = torch.load(vocoder_path, map_location=self.device)
            self.vocoder.load_state_dict(checkpoint["model_state_dict"])
            if hasattr(self.vocoder, "remove_weightnorm"):
                self.vocoder.remove_weightnorm()
            print(f"Loaded {self.vocoder_type} from {vocoder_path}")
        
        if emotion_embedding_path and os.path.exists(emotion_embedding_path):
            self.emotion_controller.load_emotion_embeddings(emotion_embedding_path)
            print(f"Loaded emotion embeddings from {emotion_embedding_path}")
        
        if classifier_path and os.path.exists(classifier_path):
            self.validator.load_classifier_weights(classifier_path)
            print(f"Loaded classifier from {classifier_path}")

    def synthesize(
        self,
        text: str,
        emotion: Union[str, Dict[str, float]],
        intensity: float = 1.0,
        reference_audio: Optional[str] = None,
        speaker_embedding: Optional[torch.Tensor] = None,
        speaker_audio: Optional[List[str]] = None,
        speaker_texts: Optional[List[str]] = None,
        do_fine_tuning: bool = False,
        validate: bool = True,
        pitch_shift: float = 0.0,
        energy_scale: float = 1.0,
        duration_scale: float = 1.0,
        output_dir: Optional[str] = None,
        output_filename: Optional[str] = None,
    ) -> SynthesisResult:
        text_seq = self.text_processor.encode(text)
        text_tensor = torch.tensor(text_seq, dtype=torch.long).unsqueeze(0).to(self.device)
        text_length = torch.tensor([len(text_seq)], dtype=torch.long).to(self.device)
        
        emotion_obj, intensity_parsed = self.emotion_controller.parse_emotion_string(
            emotion if isinstance(emotion, str) else emotion
        )
        intensity = intensity if intensity != 1.0 else intensity_parsed
        intensity = self.emotion_controller.adjust_intensity(intensity)
        
        emotion_emb, prosody_features = self.emotion_controller.process_emotion_input(
            emotion,
            intensity,
        )
        emotion_emb = emotion_emb.to(self.device)
        prosody_features = prosody_features.to(self.device)
        
        emotion_idx = self.emotion_controller.get_emotion_idx_from_input(emotion)
        
        prosody_values = prosody_features.detach().cpu().numpy()
        if len(prosody_values) >= 3:
            if pitch_shift == 0.0:
                pitch_shift = float(prosody_values[0]) * 0.3
            if energy_scale == 1.0:
                energy_scale = float(prosody_values[1])
                energy_scale = max(0.5, min(2.0, energy_scale))
            if duration_scale == 1.0:
                duration_scale = float(prosody_values[2])
                duration_scale = max(0.6, min(1.6, duration_scale))
        
        style_embedding = torch.zeros(
            (1, self.config["reference_encoder"]["style_embedding_dim"]),
            dtype=torch.float32,
            device=self.device,
        )
        
        if reference_audio is not None and os.path.exists(reference_audio):
            ref_mel = self.audio_processor.get_mel_from_file(reference_audio)
            ref_mel_tensor = torch.tensor(ref_mel, dtype=torch.float32).unsqueeze(0).to(self.device)
            with torch.no_grad():
                style_embedding = self.reference_encoder(ref_mel_tensor)
        else:
            if speaker_audio is not None:
                spk_emb, _ = self.speaker_adaptation.adapt(
                    speaker_audio,
                    speaker_texts,
                    self.text_processor,
                    emotion_embedding=emotion_emb,
                    do_fine_tuning=do_fine_tuning,
                )
                style_embedding = spk_emb.unsqueeze(0)
            elif speaker_embedding is not None:
                style_embedding = speaker_embedding.unsqueeze(0)
        
        with torch.no_grad():
            _, mel_outputs_postnet, gate_outputs, alignments = self.tacotron2.inference(
                text_tensor,
                text_length,
                style_embedding,
                emotion_emb.unsqueeze(0),
                prosody_features.unsqueeze(0),
            )
            
            mel_spectrogram = mel_outputs_postnet.squeeze(0).cpu().numpy()
        
        if pitch_shift != 0.0 or energy_scale != 1.0 or duration_scale != 1.0 or emotion_idx is not None:
            mel_tensor = torch.tensor(mel_spectrogram, dtype=torch.float32)
            mel_tensor = self.emotion_controller.prosody_regulator.adjust_prosody(
                mel_tensor,
                pitch_shift=pitch_shift,
                energy_scale=energy_scale,
                duration_scale=duration_scale,
                emotion_idx=emotion_idx,
                apply_smoothing=True,
            )
            mel_spectrogram = mel_tensor.cpu().numpy()
        
        with torch.no_grad():
            mel_tensor = torch.tensor(mel_spectrogram, dtype=torch.float32).unsqueeze(0).to(self.device)
            
            if self.vocoder_type == "waveglow":
                wav = self.vocoder.infer(mel_tensor, sigma=0.666)
            else:
                wav = self.vocoder.infer(mel_tensor)
            
            wav = wav.squeeze().cpu().numpy()
        
        if self.config["inference"]["do_trim_silence"]:
            wav = self.audio_processor.trim_silence(
                wav,
                top_db=self.config["inference"]["trim_silence_threshold"],
            )
        
        validation_result = None
        if validate:
            validation_result = self.validator.validate_from_mel(
                mel_spectrogram,
                emotion if isinstance(emotion, str) else list(emotion.keys())[0],
                intensity,
            )
        
        result = SynthesisResult(
            wav=wav,
            mel_spectrogram=mel_spectrogram,
            sampling_rate=self.audio_processor.sampling_rate,
            emotion=emotion,
            emotion_intensity=intensity,
            speaker_embedding=speaker_embedding,
            style_embedding=style_embedding.squeeze(0).cpu(),
            prosody_features=prosody_features.cpu().numpy(),
            validation_result=validation_result,
        )
        
        if output_dir is not None:
            result.save(output_dir, output_filename)
        
        return result

    def synthesize_batch(
        self,
        texts: List[str],
        emotions: List[Union[str, Dict[str, float]]],
        intensities: Optional[List[float]] = None,
        reference_audios: Optional[List[Optional[str]]] = None,
        validate: bool = True,
        output_dir: Optional[str] = None,
    ) -> List[SynthesisResult]:
        if intensities is None:
            intensities = [1.0] * len(texts)
        
        if reference_audios is None:
            reference_audios = [None] * len(texts)
        
        results = []
        for i, (text, emotion, intensity, ref_audio) in enumerate(
            zip(texts, emotions, intensities, reference_audios)
        ):
            result = self.synthesize(
                text=text,
                emotion=emotion,
                intensity=intensity,
                reference_audio=ref_audio,
                validate=validate,
                output_dir=output_dir,
                output_filename=f"output_{i:04d}.wav" if output_dir else None,
            )
            results.append(result)
        
        return results
    
    def disentangle_emotion(
        self,
        audio_path: str,
    ) -> Dict[str, np.ndarray]:
        mel = self.audio_processor.get_mel_from_file(audio_path)
        mel_tensor = torch.tensor(mel, dtype=torch.float32).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            disentangled = self.emotion_disentangler.disentangle(mel_tensor)
        
        return {
            "content": disentangled["content"].squeeze(0).cpu().numpy(),
            "style": disentangled["style"].squeeze(0).cpu().numpy(),
            "emotion_embedding": disentangled["emotion_embedding"].squeeze(0).cpu().numpy(),
            "speaker_embedding": disentangled["speaker_embedding"].squeeze(0).cpu().numpy(),
        }
    
    def transfer_emotion(
        self,
        source_emotion_audio: str,
        target_speaker_audio: str,
        text: str,
        emotion_intensity: float = 1.0,
        reference_emotion: Optional[str] = None,
        validate: bool = True,
        output_dir: Optional[str] = None,
        output_filename: Optional[str] = None,
    ) -> SynthesisResult:
        transfer_result = self.multi_speaker_transfer.transfer_emotion_between_speakers(
            source_emotion_audio=source_emotion_audio,
            target_speaker_audio=target_speaker_audio,
            text=text,
            emotion_controller=self.emotion_controller,
            text_processor=self.text_processor,
            emotion_intensity=emotion_intensity,
            reference_emotion=reference_emotion,
        )
        
        mel_spectrogram = transfer_result["mel_spectrogram"].cpu().numpy()
        
        emotion_idx = None
        if reference_emotion is not None:
            emotion_idx = self.emotion_controller.get_emotion_idx_from_input(reference_emotion)
        
        if emotion_idx is not None:
            mel_tensor = torch.tensor(mel_spectrogram, dtype=torch.float32)
            mel_tensor = self.emotion_controller.prosody_regulator.adjust_prosody(
                mel_tensor,
                emotion_idx=emotion_idx,
                apply_smoothing=True,
            )
            mel_spectrogram = mel_tensor.cpu().numpy()
        
        with torch.no_grad():
            mel_tensor = torch.tensor(mel_spectrogram, dtype=torch.float32).unsqueeze(0).to(self.device)
            
            if self.vocoder_type == "waveglow":
                wav = self.vocoder.infer(mel_tensor, sigma=0.666)
            else:
                wav = self.vocoder.infer(mel_tensor)
            
            wav = wav.squeeze().cpu().numpy()
        
        if self.config["inference"]["do_trim_silence"]:
            wav = self.audio_processor.trim_silence(
                wav,
                top_db=self.config["inference"]["trim_silence_threshold"],
            )
        
        validation_result = None
        if validate:
            target_emotion = reference_emotion if reference_emotion else "neutral"
            if isinstance(target_emotion, dict):
                target_emotion = list(target_emotion.keys())[0]
            validation_result = self.validator.validate_from_mel(
                mel_spectrogram,
                target_emotion,
                emotion_intensity,
            )
        
        emotion = reference_emotion if reference_emotion else "transferred"
        result = SynthesisResult(
            wav=wav,
            mel_spectrogram=mel_spectrogram,
            sampling_rate=self.audio_processor.sampling_rate,
            emotion=emotion,
            emotion_intensity=emotion_intensity,
            speaker_embedding=transfer_result["target_speaker_embedding"],
            style_embedding=transfer_result["combined_style_embedding"],
            prosody_features=None,
            validation_result=validation_result,
        )
        
        if output_dir is not None:
            if output_filename is None:
                output_filename = "transferred_emotion.wav"
            result.save(output_dir, output_filename)
        
        return result
    
    def convert_voice_emotion(
        self,
        neutral_audio_path: str,
        target_emotion: Union[str, Dict[str, float]],
        emotion_intensity: float = 1.0,
        validate: bool = True,
        output_dir: Optional[str] = None,
        output_filename: Optional[str] = None,
    ) -> SynthesisResult:
        neutral_mel = self.audio_processor.get_mel_from_file(neutral_audio_path)
        neutral_mel_tensor = torch.tensor(neutral_mel, dtype=torch.float32).unsqueeze(0).to(self.device)
        
        emotion_emb, prosody_features = self.emotion_controller.process_emotion_input(
            target_emotion, emotion_intensity
        )
        emotion_emb = emotion_emb.to(self.device)
        
        with torch.no_grad():
            converted_mel = self.emotion_disentangler.add_emotion_to_neutral(
                neutral_mel_tensor,
                emotion_emb.unsqueeze(0),
            )
        
        emotion_idx = self.emotion_controller.get_emotion_idx_from_input(target_emotion)
        mel_spectrogram = converted_mel.squeeze(0).cpu().numpy()
        
        if emotion_idx is not None:
            mel_tensor = torch.tensor(mel_spectrogram, dtype=torch.float32)
            mel_tensor = self.emotion_controller.prosody_regulator.adjust_prosody(
                mel_tensor,
                emotion_idx=emotion_idx,
                apply_smoothing=True,
            )
            mel_spectrogram = mel_tensor.cpu().numpy()
        
        with torch.no_grad():
            mel_tensor = torch.tensor(mel_spectrogram, dtype=torch.float32).unsqueeze(0).to(self.device)
            
            if self.vocoder_type == "waveglow":
                wav = self.vocoder.infer(mel_tensor, sigma=0.666)
            else:
                wav = self.vocoder.infer(mel_tensor)
            
            wav = wav.squeeze().cpu().numpy()
        
        if self.config["inference"]["do_trim_silence"]:
            wav = self.audio_processor.trim_silence(
                wav,
                top_db=self.config["inference"]["trim_silence_threshold"],
            )
        
        validation_result = None
        if validate:
            target_emotion_str = target_emotion if isinstance(target_emotion, str) else list(target_emotion.keys())[0]
            validation_result = self.validator.validate_from_mel(
                mel_spectrogram,
                target_emotion_str,
                emotion_intensity,
            )
        
        result = SynthesisResult(
            wav=wav,
            mel_spectrogram=mel_spectrogram,
            sampling_rate=self.audio_processor.sampling_rate,
            emotion=target_emotion,
            emotion_intensity=emotion_intensity,
            speaker_embedding=None,
            style_embedding=emotion_emb.cpu(),
            prosody_features=prosody_features.cpu().numpy(),
            validation_result=validation_result,
        )
        
        if output_dir is not None:
            if output_filename is None:
                emotion_str = target_emotion if isinstance(target_emotion, str) else "_".join(
                    [f"{k}{v:.2f}" for k, v in target_emotion.items()]
                )
                output_filename = f"converted_{emotion_str}.wav"
            result.save(output_dir, output_filename)
        
        return result
    
    def analyze_audio_emotion(
        self,
        audio_path: str,
    ) -> Dict[str, Union[str, float, np.ndarray]]:
        disentangled = self.disentangle_emotion(audio_path)
        emotion_emb = torch.tensor(disentangled["emotion_embedding"])
        
        emotions = self.emotion_controller.get_available_emotions()
        emotion_idx = self.emotion_controller.emotion_to_idx
        
        similarities = {}
        for emotion in emotions:
            idx = emotion_idx[emotion]
            ref_emb = self.emotion_controller.emotion_embedding.get_emotion_embedding(emotion, 1.0)
            sim = F.cosine_similarity(emotion_emb.unsqueeze(0), ref_emb.unsqueeze(0)).item()
            similarities[emotion] = sim
        
        predicted_emotion = max(similarities, key=similarities.get)
        confidence = similarities[predicted_emotion]
        
        return {
            "predicted_emotion": predicted_emotion,
            "confidence": confidence,
            "emotion_similarities": similarities,
            "content_representation": disentangled["content"],
            "emotion_embedding": disentangled["emotion_embedding"],
            "speaker_embedding": disentangled["speaker_embedding"],
        }
    
    def load_disentangler_weights(self, load_path: str) -> None:
        if not os.path.exists(load_path):
            raise FileNotFoundError(f"Disentangler weights not found: {load_path}")
        
        checkpoint = torch.load(load_path, map_location=self.device)
        self.emotion_disentangler.load_state_dict(checkpoint["model_state_dict"])
        self.emotion_disentangler.eval()
        print(f"Loaded EmotionDisentangler from {load_path}")
    
    def load_transfer_weights(self, load_path: str) -> None:
        self.multi_speaker_transfer.load_transfer_model(load_path)

    def adapt_speaker(
        self,
        reference_audio_paths: List[str],
        reference_texts: Optional[List[str]] = None,
        emotion_embedding: Optional[torch.Tensor] = None,
        do_fine_tuning: bool = True,
        save_path: Optional[str] = None,
    ) -> Tuple[torch.Tensor, Optional[Dict]]:
        speaker_embedding, fine_tune_stats = self.speaker_adaptation.adapt(
            reference_audio_paths,
            reference_texts,
            self.text_processor,
            emotion_embedding,
            do_fine_tuning,
        )
        
        if save_path is not None:
            self.speaker_adaptation.save_speaker_embedding(speaker_embedding, save_path)
        
        return speaker_embedding, fine_tune_stats

    def validate_synthesis(
        self,
        wav_path: str,
        target_emotion: str,
        target_intensity: float = 1.0,
    ) -> Dict:
        return self.validator.validate_from_wav(wav_path, target_emotion, target_intensity)

    def get_available_emotions(self) -> List[str]:
        return self.emotion_controller.get_available_emotions()

    def set_device(self, device: str):
        self.device = torch.device(device)
        self.tacotron2.to(self.device)
        self.reference_encoder.to(self.device)
        self.vocoder.to(self.device)
        self.emotion_controller.to(self.device)

    def to(self, device: str):
        self.set_device(device)
        return self

    def eval(self):
        self.tacotron2.eval()
        self.reference_encoder.eval()
        self.vocoder.eval()
        self.emotion_controller.eval()
        return self

    def train(self):
        self.tacotron2.train()
        self.reference_encoder.train()
        self.vocoder.train()
        self.emotion_controller.train()
        return self
