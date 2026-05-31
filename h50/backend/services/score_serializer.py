import os
import json
import uuid
import numpy as np
import cv2
from typing import Dict, Optional, List, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class PageInfo:
    page_number: int
    image_path: str
    width: int
    height: int
    jianzi_count: int
    detected_boxes: List[Dict[str, Any]]


@dataclass
class ScoreMetadata:
    title: str
    composer: str
    dynasty: str
    genre: str
    difficulty: str
    description: str
    total_pages: int
    total_jianzi: int
    created_at: str
    updated_at: str


@dataclass
class SerializedScore:
    id: str
    metadata: ScoreMetadata
    pages: List[PageInfo]
    jianzi_sequence: List[Dict[str, Any]]
    gongche_sequence: List[Dict[str, Any]]
    audio_synthesis_params: Dict[str, Any]


class ScoreSerializer:
    def __init__(self, temp_dir: Optional[str] = None):
        if temp_dir is None:
            temp_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'temp')
        self.temp_dir = temp_dir
        os.makedirs(self.temp_dir, exist_ok=True)
        self.scores_dir = os.path.join(self.temp_dir, 'scores')
        os.makedirs(self.scores_dir, exist_ok=True)
        
        self.column_detection_threshold = 0.1
        self.min_column_gap = 20
        self.stitching_overlap = 50

    def stitch_multipage_scores(
        self,
        images: List[np.ndarray],
        page_order: Optional[List[int]] = None
    ) -> Tuple[np.ndarray, List[Tuple[int, int, int, int]]]:
        if page_order is None:
            page_order = list(range(len(images)))
        
        ordered_images = [images[i] for i in page_order]
        
        if len(ordered_images) == 1:
            h, w = ordered_images[0].shape[:2]
            return ordered_images[0], [(0, 0, w, h)]
        
        preprocessed = []
        for img in ordered_images:
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img.copy()
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            preprocessed.append(binary)
        
        total_height = max(img.shape[0] for img in preprocessed)
        total_width = sum(img.shape[1] for img in preprocessed) - self.stitching_overlap * (len(preprocessed) - 1)
        
        stitched = np.ones((total_height, total_width), dtype=np.uint8) * 255
        page_bounds = []
        
        current_x = 0
        for i, img in enumerate(preprocessed):
            h, w = img.shape[:2]
            y_offset = (total_height - h) // 2
            
            if i > 0:
                current_x -= self.stitching_overlap
                
            stitched[y_offset:y_offset + h, current_x:current_x + w] = img
            page_bounds.append((current_x, y_offset, current_x + w, y_offset + h))
            current_x += w
        
        _, stitched_binary = cv2.threshold(stitched, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return stitched_binary, page_bounds

    def detect_columns(self, image: np.ndarray) -> List[Tuple[int, int]]:
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        vertical_proj = np.sum(binary, axis=0) / 255.0
        threshold = np.max(vertical_proj) * self.column_detection_threshold
        
        columns = []
        in_column = False
        col_start = 0
        
        for x, val in enumerate(vertical_proj):
            if val > threshold and not in_column:
                col_start = x
                in_column = True
            elif val <= threshold and in_column:
                col_end = x
                if col_end - col_start > self.min_column_gap:
                    columns.append((col_start, col_end))
                in_column = False
        
        if in_column:
            columns.append((col_start, len(vertical_proj)))
        
        return columns

    def sort_jianzi_vertical(
        self,
        jianzi_boxes: List[Dict[str, Any]],
        columns: Optional[List[Tuple[int, int]]] = None
    ) -> List[Dict[str, Any]]:
        if columns is None:
            all_x = [box['bbox'][0] for box in jianzi_boxes]
            if not all_x:
                return jianzi_boxes
            img_width = max(all_x) + 100
            dummy_img = np.zeros((100, img_width), dtype=np.uint8)
            for box in jianzi_boxes:
                x1, y1, x2, y2 = box['bbox']
                dummy_img[10:90, x1:x2] = 255
            columns = self.detect_columns(dummy_img)
        
        def get_column_index(bbox):
            center_x = (bbox[0] + bbox[2]) // 2
            for i, (col_start, col_end) in enumerate(columns):
                if col_start <= center_x <= col_end:
                    return i
            return len(columns)
        
        sorted_boxes = sorted(
            jianzi_boxes,
            key=lambda box: (get_column_index(box['bbox']), box['bbox'][1])
        )
        
        for i, box in enumerate(sorted_boxes):
            box['sequence_id'] = i
            box['column'] = get_column_index(box['bbox'])
        
        return sorted_boxes

    def create_serialized_score(
        self,
        title: str,
        page_images: List[np.ndarray],
        page_jianzi_list: List[List[Dict[str, Any]]],
        metadata: Optional[Dict[str, Any]] = None,
        genre: str = "classical"
    ) -> SerializedScore:
        score_id = str(uuid.uuid4())
        
        stitched_image, page_bounds = self.stitch_multipage_scores(page_images)
        
        all_jianzi = []
        for page_idx, jianzi_list in enumerate(page_jianzi_list):
            for jz in jianzi_list:
                jz_copy = jz.copy()
                jz_copy['page_number'] = page_idx + 1
                if 'bbox' in jz_copy and page_idx < len(page_bounds):
                    px, py, _, _ = page_bounds[page_idx]
                    x1, y1, x2, y2 = jz_copy['bbox']
                    jz_copy['global_bbox'] = (x1 + px, y1 + py, x2 + px, y2 + py)
                all_jianzi.append(jz_copy)
        
        columns = self.detect_columns(stitched_image)
        sorted_jianzi = self.sort_jianzi_vertical(all_jianzi, columns)
        
        gongche_sequence = self._generate_gongche_sequence(sorted_jianzi)
        
        now = datetime.now().isoformat()
        default_metadata = {
            "title": title,
            "composer": "传统古谱",
            "dynasty": "不详",
            "genre": genre,
            "difficulty": "中级",
            "description": "古琴曲数字化减字谱",
            "total_pages": len(page_images),
            "total_jianzi": len(sorted_jianzi),
            "created_at": now,
            "updated_at": now
        }
        if metadata:
            default_metadata.update(metadata)
        
        pages_info = []
        for i, (img, jianzi_list) in enumerate(zip(page_images, page_jianzi_list)):
            h, w = img.shape[:2]
            pages_info.append(PageInfo(
                page_number=i + 1,
                image_path=f"pages/{score_id}_page_{i+1}.png",
                width=w,
                height=h,
                jianzi_count=len(jianzi_list),
                detected_boxes=jianzi_list
            ))
        
        score = SerializedScore(
            id=score_id,
            metadata=ScoreMetadata(**default_metadata),
            pages=pages_info,
            jianzi_sequence=sorted_jianzi,
            gongche_sequence=gongche_sequence,
            audio_synthesis_params={
                "tempo": 60.0,
                "volume": 0.8,
                "reverb": 0.3,
                "style": "traditional"
            }
        )
        
        self._save_score(score, stitched_image, page_images)
        
        return score

    def _generate_gongche_sequence(self, jianzi_sequence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        try:
            from services import GongcheConverter
            converter = GongcheConverter()
            
            gongche_seq = []
            for i, jz in enumerate(jianzi_sequence):
                try:
                    gongche = converter.jianzi_to_gongche(jz)
                    description = converter.generate_description(jz)
                    gongche_seq.append({
                        "sequence_id": i,
                        "jianzi_id": jz.get('id', ''),
                        "gongche": gongche,
                        "description": description
                    })
                except Exception:
                    gongche_seq.append({
                        "sequence_id": i,
                        "jianzi_id": jz.get('id', ''),
                        "gongche": None,
                        "description": None
                    })
            return gongche_seq
        except Exception:
            return []

    def _save_score(
        self,
        score: SerializedScore,
        stitched_image: np.ndarray,
        page_images: List[np.ndarray]
    ) -> None:
        score_dir = os.path.join(self.scores_dir, score.id)
        os.makedirs(score_dir, exist_ok=True)
        os.makedirs(os.path.join(score_dir, 'pages'), exist_ok=True)
        
        cv2.imwrite(os.path.join(score_dir, 'stitched.png'), stitched_image)
        
        for i, img in enumerate(page_images):
            cv2.imwrite(os.path.join(score_dir, f'pages/page_{i+1}.png'), img)
        
        score_dict = {
            "id": score.id,
            "metadata": asdict(score.metadata),
            "pages": [asdict(p) for p in score.pages],
            "jianzi_sequence": score.jianzi_sequence,
            "gongche_sequence": score.gongche_sequence,
            "audio_synthesis_params": score.audio_synthesis_params
        }
        
        with open(os.path.join(score_dir, 'score.json'), 'w', encoding='utf-8') as f:
            json.dump(score_dict, f, ensure_ascii=False, indent=2)

    def load_score(self, score_id: str) -> Optional[SerializedScore]:
        score_dir = os.path.join(self.scores_dir, score_id)
        score_path = os.path.join(score_dir, 'score.json')
        
        if not os.path.exists(score_path):
            return None
        
        with open(score_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return SerializedScore(
            id=data['id'],
            metadata=ScoreMetadata(**data['metadata']),
            pages=[PageInfo(**p) for p in data['pages']],
            jianzi_sequence=data['jianzi_sequence'],
            gongche_sequence=data['gongche_sequence'],
            audio_synthesis_params=data['audio_synthesis_params']
        )

    def list_scores(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.scores_dir):
            return []
        
        scores = []
        for score_id in os.listdir(self.scores_dir):
            score_dir = os.path.join(self.scores_dir, score_id)
            score_path = os.path.join(score_dir, 'score.json')
            
            if os.path.exists(score_path):
                try:
                    with open(score_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    scores.append({
                        "id": data['id'],
                        "title": data['metadata']['title'],
                        "composer": data['metadata']['composer'],
                        "difficulty": data['metadata']['difficulty'],
                        "total_pages": data['metadata']['total_pages'],
                        "total_jianzi": data['metadata']['total_jianzi'],
                        "created_at": data['metadata']['created_at']
                    })
                except Exception:
                    continue
        
        return sorted(scores, key=lambda x: x['created_at'], reverse=True)

    def export_score_to_midi(self, score_id: str, output_path: str) -> bool:
        try:
            from services import AudioSynthesizer, MidiGenerator
            
            score = self.load_score(score_id)
            if not score:
                return False
            
            synthesizer = AudioSynthesizer()
            midi_gen = MidiGenerator()
            
            notes = []
            for jz in score.jianzi_sequence:
                midi = jz.get('midi', 60)
                technique = jz.get('technique', 'sanyin')
                duration = jz.get('duration', 1.0)
                string_id = jz.get('string', None)
                
                notes.append({
                    "midi": midi,
                    "technique": technique,
                    "duration": duration,
                    "string": string_id
                })
            
            tempo = score.audio_synthesis_params.get("tempo", 60.0)
            return midi_gen.generate_midi(notes, output_path, tempo)
            
        except Exception:
            return False

    def update_jianzi_sequence(
        self,
        score_id: str,
        jianzi_updates: List[Dict[str, Any]]
    ) -> bool:
        score = self.load_score(score_id)
        if not score:
            return False
        
        for update in jianzi_updates:
            seq_id = update.get('sequence_id')
            if seq_id is not None and 0 <= seq_id < len(score.jianzi_sequence):
                score.jianzi_sequence[seq_id].update(update)
        
        score.metadata.updated_at = datetime.now().isoformat()
        score.gongche_sequence = self._generate_gongche_sequence(score.jianzi_sequence)
        
        score_dir = os.path.join(self.scores_dir, score_id)
        score_dict = {
            "id": score.id,
            "metadata": asdict(score.metadata),
            "pages": [asdict(p) for p in score.pages],
            "jianzi_sequence": score.jianzi_sequence,
            "gongche_sequence": score.gongche_sequence,
            "audio_synthesis_params": score.audio_synthesis_params
        }
        
        with open(os.path.join(score_dir, 'score.json'), 'w', encoding='utf-8') as f:
            json.dump(score_dict, f, ensure_ascii=False, indent=2)
        
        return True

    def delete_score(self, score_id: str) -> bool:
        import shutil
        score_dir = os.path.join(self.scores_dir, score_id)
        if os.path.exists(score_dir):
            shutil.rmtree(score_dir)
            return True
        return False
