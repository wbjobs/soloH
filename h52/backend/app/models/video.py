import torch
import torch.nn as nn
import numpy as np
import cv2
from typing import List, Tuple, Dict, Optional
import logging
from PIL import Image
import io
import base64

logger = logging.getLogger(__name__)

try:
    import mediapipe as mp
    MP_AVAILABLE = True
except ImportError:
    MP_AVAILABLE = False
    logger.warning("MediaPipe not available. Using mock mode.")


class FacialFeatureExtractor(nn.Module):
    def __init__(
        self,
        output_dim: int = 512,
        emotion_dim: int = 7,
        num_landmarks: int = 478,
        device: str = "cuda" if torch.cuda.is_available() else "cpu"
    ):
        super().__init__()
        self.device = device
        self.output_dim = output_dim
        self.num_landmarks = num_landmarks
        
        if MP_AVAILABLE:
            self.face_mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            self.mp_drawing = mp.solutions.drawing_utils
            self.mp_drawing_styles = mp.solutions.drawing_styles
            logger.info("MediaPipe FaceMesh initialized successfully")
        else:
            self.face_mesh = None
            logger.warning("MediaPipe not available. Facial feature extraction will use mock data.")
        
        self.feature_encoder = nn.Sequential(
            nn.Linear(num_landmarks * 3, 1024),
            nn.LayerNorm(1024),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(1024, 512),
            nn.LayerNorm(512),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(512, output_dim)
        ).to(device)
        
        self.emotion_head = nn.Sequential(
            nn.Linear(output_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, emotion_dim)
        ).to(device)
        
        self.valence_arousal_head = nn.Sequential(
            nn.Linear(output_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 2),
            nn.Tanh()
        ).to(device)
        
        self.au_classifier = nn.Sequential(
            nn.Linear(output_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 17)
        ).to(device)

    def extract_landmarks(self, frame: np.ndarray) -> Optional[np.ndarray]:
        if self.face_mesh is None:
            landmarks = np.random.randn(self.num_landmarks, 3) * 0.1
            landmarks = landmarks - landmarks.mean(axis=0)
            return landmarks
        
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(frame_rgb)
        
        if not results.multi_face_landmarks:
            return None
        
        face_landmarks = results.multi_face_landmarks[0]
        landmarks = np.array([
            [lm.x, lm.y, lm.z] for lm in face_landmarks.landmark
        ], dtype=np.float32)
        
        landmarks = landmarks - landmarks.mean(axis=0)
        
        return landmarks

    def compute_faus(self, landmarks: np.ndarray) -> np.ndarray:
        aus = np.zeros(17, dtype=np.float32)
        
        upper_lip = landmarks[13]
        lower_lip = landmarks[14]
        mouth_open = np.linalg.norm(upper_lip - lower_lip)
        aus[0] = min(1.0, mouth_open * 10)
        
        left_eyebrow = landmarks[105]
        right_eyebrow = landmarks[334]
        eyebrow_raise = np.mean([left_eyebrow[1], right_eyebrow[1]])
        aus[1] = max(0, min(1.0, -eyebrow_raise * 5 + 0.5))
        
        left_eye_upper = landmarks[159]
        left_eye_lower = landmarks[145]
        eye_wide = np.linalg.norm(left_eye_upper - left_eye_lower)
        aus[2] = min(1.0, eye_wide * 15)
        
        nose_tip = landmarks[1]
        mouth_left = landmarks[61]
        mouth_right = landmarks[291]
        smile_curve = (mouth_left[1] + mouth_right[1]) / 2 - nose_tip[1]
        aus[3] = max(0, min(1.0, -smile_curve * 5 + 0.3))
        
        jaw = landmarks[152]
        chin_height = jaw[1]
        aus[4] = min(1.0, chin_height * 2)
        
        for i in range(5, 17):
            aus[i] = np.random.random() * 0.5
        
        return aus

    @torch.no_grad()
    def extract_features(
        self,
        frame: np.ndarray,
        return_sequence: bool = False
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, Dict]:
        landmarks = self.extract_landmarks(frame)
        
        if landmarks is None:
            features = torch.randn(1, self.output_dim, device=self.device) * 0.1
            emotion_logits = torch.randn(1, 7, device=self.device) * 0.1
            va = torch.randn(1, 2, device=self.device) * 0.5
            aus = np.random.rand(17).astype(np.float32)
            return features, emotion_logits, va, {'landmarks': None, 'aus': aus}
        
        landmarks_flat = landmarks.flatten()
        aus = self.compute_faus(landmarks)
        
        landmarks_tensor = torch.tensor(landmarks_flat, dtype=torch.float32, device=self.device).unsqueeze(0)
        
        with torch.no_grad():
            features = self.feature_encoder(landmarks_tensor)
            emotion_logits = self.emotion_head(features)
            va = self.valence_arousal_head(features)
            au_logits = self.au_classifier(features)
        
        return features, emotion_logits, va, {
            'landmarks': landmarks,
            'aus': aus,
            'au_logits': au_logits.cpu().numpy()[0]
        }

    def get_emotion_probabilities(self, logits: torch.Tensor) -> dict:
        probs = torch.softmax(logits, dim=-1).cpu().numpy()[0]
        emotions = ['anger', 'joy', 'sadness', 'surprise', 'disgust', 'fear', 'neutral']
        return {emotions[i]: float(probs[i]) for i in range(7)}

    def process_video(
        self,
        video_path: str,
        sample_rate: int = 5,
        max_frames: int = 100
    ) -> Dict:
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_interval = max(1, int(fps / sample_rate))
        
        all_features = []
        all_emotion_probs = []
        all_va = []
        all_metadata = []
        
        frame_count = 0
        sample_count = 0
        
        while cap.isOpened() and sample_count < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_count % frame_interval == 0:
                features, emotion_logits, va, metadata = self.extract_features(frame)
                emotion_probs = self.get_emotion_probabilities(emotion_logits)
                va_values = va.cpu().numpy()[0]
                
                all_features.append(features.cpu().numpy()[0])
                all_emotion_probs.append(emotion_probs)
                all_va.append(va_values)
                all_metadata.append(metadata)
                sample_count += 1
            
            frame_count += 1
        
        cap.release()
        
        features_seq = np.array(all_features)
        avg_features = np.mean(features_seq, axis=0)
        
        avg_emotion_probs = {}
        for key in all_emotion_probs[0].keys():
            avg_emotion_probs[key] = float(np.mean([p[key] for p in all_emotion_probs]))
        
        avg_va = np.mean(all_va, axis=0)
        
        return {
            'features': avg_features,
            'features_sequence': features_seq,
            'emotion_probabilities': avg_emotion_probs,
            'emotion_sequence': all_emotion_probs,
            'valence': float(avg_va[0]),
            'arousal': float(avg_va[1]),
            'va_sequence': all_va,
            'metadata': all_metadata,
            'num_frames': sample_count
        }

    def decode_base64_frame(self, base64_str: str) -> np.ndarray:
        img_data = base64.b64decode(base64_str)
        img = Image.open(io.BytesIO(img_data))
        return np.array(img)

    def process_stream_frame(self, base64_frame: str) -> Optional[Dict]:
        try:
            frame = self.decode_base64_frame(base64_frame)
            features, emotion_logits, va, metadata = self.extract_features(frame)
            emotion_probs = self.get_emotion_probabilities(emotion_logits)
            va_values = va.cpu().numpy()[0]
            
            return {
                'features': features.cpu().numpy()[0],
                'emotion_probabilities': emotion_probs,
                'valence': float(va_values[0]),
                'arousal': float(va_values[1]),
                'metadata': metadata
            }
        except Exception as e:
            logger.error(f"Error processing stream frame: {e}")
            return None
