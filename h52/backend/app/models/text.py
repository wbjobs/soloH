import torch
import torch.nn as nn
import numpy as np
from typing import List, Tuple, Dict, Optional
import logging

logger = logging.getLogger(__name__)

try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logger.warning("Faster Whisper not available. ASR will use mock mode.")

try:
    from transformers import BertModel, BertTokenizer
    BERT_AVAILABLE = True
except ImportError:
    BERT_AVAILABLE = False
    logger.warning("Transformers/BERT not available. Text feature extraction will use mock mode.")


class ASRTranscriber:
    def __init__(
        self,
        model_size: str = "base",
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
        compute_type: str = "float16"
    ):
        self.device = device
        self.model_size = model_size
        
        if WHISPER_AVAILABLE:
            try:
                self.model = WhisperModel(
                    model_size,
                    device=device,
                    compute_type=compute_type
                )
                logger.info(f"Whisper model '{model_size}' loaded successfully on {device}")
            except Exception as e:
                logger.warning(f"Failed to load Whisper model: {e}. Using mock mode.")
                self.model = None
        else:
            self.model = None
        
        self.mock_transcripts = [
            "今天天气真不错，我感到非常开心和愉快。工作也很顺利，一切都在朝着好的方向发展。",
            "我对这件事情感到非常愤怒和失望，为什么总是这样不公平？我需要冷静下来好好思考。",
            "最近发生了很多事情，让我感到有些悲伤和难过。不过我相信一切都会好起来的。",
            "太令人惊讶了！我完全没有想到会是这样的结果，真是太棒了！",
            "这种感觉让我很不舒服，有些厌恶和排斥。我需要远离这种环境。",
            "我感到有些恐惧和不安，不知道接下来会发生什么。希望一切都能平安度过。",
            "今天是普通的一天，没有什么特别的事情发生。工作和生活都按部就班地进行着。",
            "我现在的心情很复杂，既有一些兴奋，也有一些担忧。不过总体来说还是积极的。"
        ]

    def transcribe(self, audio_path: str) -> Tuple[str, List[Dict]]:
        if self.model is None:
            transcript = self.mock_transcripts[np.random.randint(len(self.mock_transcripts))]
            segments = [
                {'start': 0.0, 'end': 10.0, 'text': transcript, 'confidence': 0.85}
            ]
            return transcript, segments
        
        try:
            segments, info = self.model.transcribe(
                audio_path,
                beam_size=5,
                language="zh"
            )
            
            transcript = ""
            segment_list = []
            
            for segment in segments:
                transcript += segment.text + " "
                segment_list.append({
                    'start': segment.start,
                    'end': segment.end,
                    'text': segment.text,
                    'confidence': segment.avg_logprob
                })
            
            return transcript.strip(), segment_list
        except Exception as e:
            logger.error(f"ASR transcription failed: {e}")
            return self.mock_transcripts[0], []


class TextFeatureExtractor(nn.Module):
    def __init__(
        self,
        model_name: str = "bert-base-chinese",
        output_dim: int = 768,
        emotion_dim: int = 7,
        max_length: int = 512,
        device: str = "cuda" if torch.cuda.is_available() else "cpu"
    ):
        super().__init__()
        self.device = device
        self.output_dim = output_dim
        self.max_length = max_length
        
        if BERT_AVAILABLE:
            try:
                self.tokenizer = BertTokenizer.from_pretrained(model_name)
                self.model = BertModel.from_pretrained(model_name)
                self.model = self.model.to(self.device)
                self.model.eval()
                logger.info(f"BERT model '{model_name}' loaded successfully on {device}")
            except Exception as e:
                logger.warning(f"Failed to load BERT model: {e}. Using mock mode.")
                self.tokenizer = None
                self.model = None
        else:
            self.tokenizer = None
            self.model = None
        
        self.emotion_head = nn.Sequential(
            nn.Linear(output_dim, 512),
            nn.LayerNorm(512),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, emotion_dim)
        ).to(device)
        
        self.valence_arousal_head = nn.Sequential(
            nn.Linear(output_dim, 512),
            nn.LayerNorm(512),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, 2),
            nn.Tanh()
        ).to(device)

    @torch.no_grad()
    def extract_features(
        self,
        text: str,
        return_sequence: bool = False
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        if self.model is None or self.tokenizer is None:
            batch_size = 1
            seq_len = min(len(text.split()), self.max_length) if return_sequence else 1
            features = torch.randn(batch_size, seq_len, self.output_dim, device=self.device) * 0.1
            emotion_logits = torch.randn(batch_size, 7, device=self.device) * 0.1
            va = torch.randn(batch_size, 2, device=self.device) * 0.5
            return features, emotion_logits, va
        
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            max_length=self.max_length,
            truncation=True,
            padding=True
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            hidden_states = outputs.last_hidden_state
            
            if return_sequence:
                features = hidden_states
            else:
                features = hidden_states[:, 0, :]
            
            pooled_features = hidden_states[:, 0, :]
            emotion_logits = self.emotion_head(pooled_features)
            va = self.valence_arousal_head(pooled_features)
        
        return features, emotion_logits, va

    def get_emotion_probabilities(self, logits: torch.Tensor) -> dict:
        probs = torch.softmax(logits, dim=-1).cpu().numpy()[0]
        emotions = ['anger', 'joy', 'sadness', 'surprise', 'disgust', 'fear', 'neutral']
        return {emotions[i]: float(probs[i]) for i in range(7)}

    def __call__(self, text: str, return_sequence: bool = False):
        if not text or not text.strip():
            features = torch.zeros(1, self.output_dim, device=self.device)
            emotion_logits = torch.zeros(1, 7, device=self.device)
            emotion_logits[0, 6] = 5.0
            va = torch.zeros(1, 2, device=self.device)
        else:
            features, emotion_logits, va = self.extract_features(
                text, return_sequence=return_sequence
            )
        
        emotion_probs = self.get_emotion_probabilities(emotion_logits)
        va_values = va.cpu().numpy()[0]
        
        return {
            'features': features.cpu().numpy(),
            'emotion_probabilities': emotion_probs,
            'valence': float(va_values[0]),
            'arousal': float(va_values[1])
        }


class TextStreamProcessor:
    def __init__(self, extractor: TextFeatureExtractor, asr: Optional[ASRTranscriber] = None):
        self.extractor = extractor
        self.asr = asr
        self.text_buffer = []
        self.full_transcript = ""

    def process_audio_chunk(self, audio_chunk: np.ndarray, sample_rate: int = 16000) -> Optional[Dict]:
        if self.asr is not None:
            try:
                import tempfile
                import soundfile as sf
                
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                    sf.write(f.name, audio_chunk, sample_rate)
                    transcript, _ = self.asr.transcribe(f.name)
                
                if transcript.strip():
                    self.text_buffer.append(transcript)
                    self.full_transcript += " " + transcript
                    
                    return self.process_text(transcript)
            except Exception as e:
                logger.error(f"Error processing audio chunk for ASR: {e}")
        
        return None

    def process_text(self, text: str) -> Optional[Dict]:
        if not text.strip():
            return None
        
        result = self.extractor(text)
        
        return {
            'features': result['features'][0] if len(result['features'].shape) > 1 else result['features'],
            'emotion_probabilities': result['emotion_probabilities'],
            'valence': result['valence'],
            'arousal': result['arousal'],
            'text': text
        }

    def get_full_transcript(self) -> str:
        return self.full_transcript.strip()
