import os
import json
import random
import hashlib
import cv2
import numpy as np
from typing import Tuple, Dict, Optional, List, Any, Union

BBox = Tuple[int, int, int, int]
ComponentImage = np.ndarray
RecognitionResult = Dict[str, Any]

class ComponentRecognizer:
    def __init__(self, dictionary_path: Optional[str] = None):
        if dictionary_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            dictionary_path = os.path.join(current_dir, "dictionary.json")
        self.dictionary_path = dictionary_path
        self.dictionary = self._load_dictionary()
        self.component_templates: Dict[str, List[np.ndarray]] = {}
        self._initialize_templates()

    def _load_dictionary(self) -> Dict[str, Any]:
        if not os.path.exists(self.dictionary_path):
            raise FileNotFoundError(f"Dictionary file not found: {self.dictionary_path}")
        with open(self.dictionary_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _initialize_templates(self) -> None:
        for category, items in self.dictionary.items():
            self.component_templates[category] = []
            if isinstance(items, dict):
                for item_id, item_data in items.items():
                    template = self._generate_template(item_id)
                    self.component_templates[category].append({
                        "id": item_id,
                        "data": item_data,
                        "template": template
                    })
            else:
                for item in items:
                    item_id = item.get("id", "") if isinstance(item, dict) else str(item)
                    template = self._generate_template(item_id)
                    self.component_templates[category].append({
                        "id": item_id,
                        "data": item if isinstance(item, dict) else {},
                        "template": template
                    })

    def _generate_template(self, text: str, size: Tuple[int, int] = (64, 64)) -> np.ndarray:
        template = np.ones(size, dtype=np.uint8) * 255
        hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
        random.seed(hash_val)
        num_strokes = random.randint(3, 8)
        for _ in range(num_strokes):
            x1 = random.randint(5, size[0] - 5)
            y1 = random.randint(5, size[1] - 5)
            x2 = random.randint(5, size[0] - 5)
            y2 = random.randint(5, size[1] - 5)
            thickness = random.randint(1, 3)
            cv2.line(template, (x1, y1), (x2, y2), 0, thickness)
        kernel = np.ones((2, 2), np.uint8)
        template = cv2.dilate(template, kernel, iterations=1)
        return template

    def _preprocess_component(self, component_image: ComponentImage) -> ComponentImage:
        if len(component_image.shape) == 3:
            gray = cv2.cvtColor(component_image, cv2.COLOR_BGR2GRAY)
        else:
            gray = component_image.copy()
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if np.mean(binary) > 127:
            binary = 255 - binary
        binary = cv2.resize(binary, (64, 64), interpolation=cv2.INTER_AREA)
        return binary

    def _template_match(self, image: ComponentImage, template: np.ndarray) -> float:
        if image.shape != template.shape:
            image = cv2.resize(image, template.shape[:2][::-1], interpolation=cv2.INTER_AREA)
        result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        return max_val

    def _extract_features(self, image: ComponentImage) -> np.ndarray:
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        gray = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        features = binary.flatten().astype(np.float32) / 255.0
        return features

    def _cosine_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        dot_product = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)

    def _extract_hui_shape_features(self, image: ComponentImage) -> Dict[str, float]:
        """
        提取徽位数字的形状特征，专门用于区分"一"（1）和"七"（7）。
        
        特征包括：
        - horizontal_strokes: 横笔画数量
        - vertical_strokes: 竖笔画数量
        - has_bottom_hook: 是否有底部钩（"七"的特征）
        - top_heavy: 上部是否较重（"七"的特征）
        - aspect_ratio: 宽高比
        - pixel_density_top: 上半部分像素密度
        - pixel_density_bottom: 下半部分像素密度
        - diagonal_elements: 是否有斜笔画（"七"的特征）
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if np.mean(binary) > 127:
            binary = 255 - binary
        
        binary = cv2.resize(binary, (64, 64), interpolation=cv2.INTER_AREA)
        
        h, w = binary.shape
        features = {}
        
        horizontal_proj = np.sum(binary, axis=1) / 255.0
        vertical_proj = np.sum(binary, axis=0) / 255.0
        
        h_threshold = np.max(horizontal_proj) * 0.3
        horizontal_strokes = 0
        in_stroke = False
        for val in horizontal_proj:
            if val > h_threshold and not in_stroke:
                horizontal_strokes += 1
                in_stroke = True
            elif val <= h_threshold and in_stroke:
                in_stroke = False
        features["horizontal_strokes"] = float(horizontal_strokes)
        
        v_threshold = np.max(vertical_proj) * 0.3
        vertical_strokes = 0
        in_stroke = False
        for val in vertical_proj:
            if val > v_threshold and not in_stroke:
                vertical_strokes += 1
                in_stroke = True
            elif val <= v_threshold and in_stroke:
                in_stroke = False
        features["vertical_strokes"] = float(vertical_strokes)
        
        bottom_quarter = binary[int(h * 0.75):, :]
        bottom_left = bottom_quarter[:, :int(w * 0.3)]
        bottom_right = bottom_quarter[:, int(w * 0.7):]
        has_bottom_hook = np.sum(bottom_right) > np.sum(bottom_left) * 1.5 and np.sum(bottom_right) > 0
        features["has_bottom_hook"] = 1.0 if has_bottom_hook else 0.0
        
        top_half = binary[:h//2, :]
        bottom_half = binary[h//2:, :]
        features["pixel_density_top"] = np.sum(top_half) / (h//2 * w * 255)
        features["pixel_density_bottom"] = np.sum(bottom_half) / (h//2 * w * 255)
        features["top_heavy"] = 1.0 if features["pixel_density_top"] > features["pixel_density_bottom"] * 1.3 else 0.0
        
        features["aspect_ratio"] = float(w) / float(h)
        
        edges = cv2.Canny(binary, 50, 150)
        lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=30)
        diagonal_count = 0
        if lines is not None:
            for rho, theta in lines[:, 0]:
                angle = theta * 180 / np.pi
                if 30 < angle < 60 or 120 < angle < 150:
                    diagonal_count += 1
        features["diagonal_elements"] = float(diagonal_count)
        
        left_half = binary[:, :w//2]
        right_half = binary[:, w//2:]
        features["left_density"] = np.sum(left_half) / (h * w//2 * 255)
        features["right_density"] = np.sum(right_half) / (h * w//2 * 255)
        
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            x, y, cw, ch = cv2.boundingRect(largest_contour)
            features["contour_aspect"] = float(cw) / float(ch)
            features["contour_fill"] = cv2.contourArea(largest_contour) / (cw * ch) if cw * ch > 0 else 0.0
        else:
            features["contour_aspect"] = 0.0
            features["contour_fill"] = 0.0
        
        return features

    def _calculate_hui_similarity(self, features1: Dict[str, float], features2: Dict[str, float]) -> float:
        """计算两个徽位特征向量的相似度"""
        weights = {
            "horizontal_strokes": 0.2,
            "vertical_strokes": 0.15,
            "has_bottom_hook": 0.2,
            "top_heavy": 0.15,
            "aspect_ratio": 0.05,
            "pixel_density_top": 0.05,
            "pixel_density_bottom": 0.05,
            "diagonal_elements": 0.1,
            "contour_aspect": 0.03,
            "contour_fill": 0.02
        }
        
        similarity = 0.0
        for key, weight in weights.items():
            v1 = features1.get(key, 0.0)
            v2 = features2.get(key, 0.0)
            if key in ["has_bottom_hook", "top_heavy"]:
                diff = 0.0 if v1 == v2 else 1.0
            elif key == "horizontal_strokes" or key == "vertical_strokes" or key == "diagonal_elements":
                max_val = max(abs(v1), abs(v2), 1.0)
                diff = abs(v1 - v2) / max_val
            else:
                diff = abs(v1 - v2)
            similarity += weight * (1.0 - min(diff, 1.0))
        
        return similarity

    def _build_hui_templates(self) -> Dict[str, Dict[str, float]]:
        """
        构建徽位数字的模板特征，用于快速匹配。
        特别优化"一"和"七"的区分。
        """
        templates = {}
        
        templates["一"] = {
            "horizontal_strokes": 1.0,
            "vertical_strokes": 0.0,
            "has_bottom_hook": 0.0,
            "top_heavy": 0.0,
            "aspect_ratio": 3.0,
            "pixel_density_top": 0.5,
            "pixel_density_bottom": 0.5,
            "diagonal_elements": 0.0,
            "left_density": 0.5,
            "right_density": 0.5,
            "contour_aspect": 3.0,
            "contour_fill": 0.1
        }
        
        templates["七"] = {
            "horizontal_strokes": 1.0,
            "vertical_strokes": 1.0,
            "has_bottom_hook": 1.0,
            "top_heavy": 1.0,
            "aspect_ratio": 0.8,
            "pixel_density_top": 0.7,
            "pixel_density_bottom": 0.3,
            "diagonal_elements": 1.0,
            "left_density": 0.3,
            "right_density": 0.7,
            "contour_aspect": 0.8,
            "contour_fill": 0.3
        }
        
        templates["二"] = {
            "horizontal_strokes": 2.0,
            "vertical_strokes": 0.0,
            "has_bottom_hook": 0.0,
            "top_heavy": 0.5,
            "aspect_ratio": 2.5,
            "pixel_density_top": 0.5,
            "pixel_density_bottom": 0.5,
            "diagonal_elements": 0.0,
            "left_density": 0.5,
            "right_density": 0.5,
            "contour_aspect": 2.5,
            "contour_fill": 0.15
        }
        
        templates["三"] = {
            "horizontal_strokes": 3.0,
            "vertical_strokes": 0.0,
            "has_bottom_hook": 0.0,
            "top_heavy": 0.5,
            "aspect_ratio": 2.0,
            "pixel_density_top": 0.5,
            "pixel_density_bottom": 0.5,
            "diagonal_elements": 0.0,
            "left_density": 0.5,
            "right_density": 0.5,
            "contour_aspect": 2.0,
            "contour_fill": 0.2
        }
        
        templates["四"] = {
            "horizontal_strokes": 2.0,
            "vertical_strokes": 2.0,
            "has_bottom_hook": 0.0,
            "top_heavy": 0.5,
            "aspect_ratio": 1.0,
            "pixel_density_top": 0.5,
            "pixel_density_bottom": 0.5,
            "diagonal_elements": 0.0,
            "left_density": 0.5,
            "right_density": 0.5,
            "contour_aspect": 1.0,
            "contour_fill": 0.5
        }
        
        templates["五"] = {
            "horizontal_strokes": 2.0,
            "vertical_strokes": 2.0,
            "has_bottom_hook": 0.0,
            "top_heavy": 0.5,
            "aspect_ratio": 1.0,
            "pixel_density_top": 0.5,
            "pixel_density_bottom": 0.5,
            "diagonal_elements": 1.0,
            "left_density": 0.5,
            "right_density": 0.5,
            "contour_aspect": 1.0,
            "contour_fill": 0.45
        }
        
        templates["六"] = {
            "horizontal_strokes": 1.0,
            "vertical_strokes": 2.0,
            "has_bottom_hook": 0.0,
            "top_heavy": 0.3,
            "aspect_ratio": 1.0,
            "pixel_density_top": 0.3,
            "pixel_density_bottom": 0.7,
            "diagonal_elements": 1.0,
            "left_density": 0.5,
            "right_density": 0.5,
            "contour_aspect": 1.0,
            "contour_fill": 0.4
        }
        
        templates["八"] = {
            "horizontal_strokes": 0.0,
            "vertical_strokes": 0.0,
            "has_bottom_hook": 0.0,
            "top_heavy": 1.0,
            "aspect_ratio": 1.2,
            "pixel_density_top": 0.7,
            "pixel_density_bottom": 0.3,
            "diagonal_elements": 2.0,
            "left_density": 0.5,
            "right_density": 0.5,
            "contour_aspect": 1.2,
            "contour_fill": 0.25
        }
        
        templates["九"] = {
            "horizontal_strokes": 1.0,
            "vertical_strokes": 1.0,
            "has_bottom_hook": 1.0,
            "top_heavy": 0.5,
            "aspect_ratio": 0.9,
            "pixel_density_top": 0.5,
            "pixel_density_bottom": 0.5,
            "diagonal_elements": 1.0,
            "left_density": 0.3,
            "right_density": 0.7,
            "contour_aspect": 0.9,
            "contour_fill": 0.35
        }
        
        templates["十"] = {
            "horizontal_strokes": 1.0,
            "vertical_strokes": 1.0,
            "has_bottom_hook": 0.0,
            "top_heavy": 0.5,
            "aspect_ratio": 1.0,
            "pixel_density_top": 0.5,
            "pixel_density_bottom": 0.5,
            "diagonal_elements": 0.0,
            "left_density": 0.5,
            "right_density": 0.5,
            "contour_aspect": 1.0,
            "contour_fill": 0.3
        }
        
        return templates

    def _validate_hui_range(self, recognized_id: str, all_hui_labels: List[str]) -> Tuple[str, float]:
        """
        校验徽位识别结果是否在合理范围内（1-13）。
        如果识别结果不合理，返回最可能的替代选项。
        """
        valid_hui = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二", "十三"]
        
        if recognized_id in valid_hui:
            return recognized_id, 1.0
        
        for valid in valid_hui:
            if recognized_id in valid or valid in recognized_id:
                return valid, 0.8
        
        if "十" in recognized_id:
            if "一" in recognized_id or "1" in recognized_id:
                return "十一", 0.7
            elif "二" in recognized_id or "2" in recognized_id:
                return "十二", 0.7
            elif "三" in recognized_id or "3" in recognized_id:
                return "十三", 0.7
            else:
                return "十", 0.6
        
        return recognized_id, 0.5

    def recognize_component(
        self,
        component_image: ComponentImage,
        component_type: str
    ) -> RecognitionResult:
        preprocessed = self._preprocess_component(component_image)
        candidates_data = self.dictionary.get(component_type, {})
        
        if isinstance(candidates_data, dict):
            candidates = []
            for cid, cdata in candidates_data.items():
                candidate = {"id": cid}
                candidate.update(cdata)
                candidates.append(candidate)
        else:
            candidates = list(candidates_data) if candidates_data else []
        
        if not candidates:
            return {
                "component_type": component_type,
                "recognized": None,
                "confidence": 0.0,
                "candidates": []
            }
        
        is_hui = "hui" in component_type.lower() or "徽" in component_type or component_type == "string_numbers"
        
        if is_hui:
            return self._recognize_hui_component(preprocessed, candidates, component_type)
        
        template_list = self.component_templates.get(component_type, [])
        image_features = self._extract_features(preprocessed)
        results = []
        for i, candidate in enumerate(candidates):
            template_obj = template_list[i] if i < len(template_list) else {"template": self._generate_template(candidate["id"])}
            template = template_obj["template"] if isinstance(template_obj, dict) else template_obj
            template_features = self._extract_features(template)
            feature_sim = self._cosine_similarity(image_features, template_features)
            template_sim = self._template_match(preprocessed, template)
            combined_confidence = (feature_sim * 0.4 + template_sim * 0.6)
            random_noise = random.uniform(-0.05, 0.05)
            final_confidence = max(0.0, min(1.0, combined_confidence + random_noise))
            results.append({
                "id": candidate["id"],
                "name": candidate.get("name", candidate["id"]),
                "pinyin": candidate.get("pinyin", ""),
                "confidence": final_confidence
            })
        results.sort(key=lambda x: x["confidence"], reverse=True)
        top_result = results[0]
        return {
            "component_type": component_type,
            "recognized": {
                "id": top_result["id"],
                "name": top_result["name"],
                "pinyin": top_result["pinyin"]
            },
            "confidence": top_result["confidence"],
            "candidates": results[:5]
        }

    def _recognize_hui_component(
        self,
        preprocessed_image: ComponentImage,
        candidates: List[Dict[str, Any]],
        component_type: str
    ) -> RecognitionResult:
        """
        专门识别徽位数字的方法，优化"一"和"七"的区分。
        结合模板匹配、形状特征和上下文校验三重识别。
        """
        hui_templates = self._build_hui_templates()
        image_shape_features = self._extract_hui_shape_features(preprocessed_image)
        
        template_list = self.component_templates.get(component_type, [])
        image_features = self._extract_features(preprocessed_image)
        
        results = []
        for i, candidate in enumerate(candidates):
            candidate_id = candidate["id"]
            
            template_obj = template_list[i] if i < len(template_list) else {"template": self._generate_template(candidate_id)}
            template = template_obj["template"] if isinstance(template_obj, dict) else template_obj
            template_features = self._extract_features(template)
            feature_sim = self._cosine_similarity(image_features, template_features)
            template_sim = self._template_match(preprocessed_image, template)
            base_confidence = (feature_sim * 0.3 + template_sim * 0.4)
            
            shape_confidence = 0.0
            if candidate_id in hui_templates:
                shape_confidence = self._calculate_hui_similarity(
                    image_shape_features, 
                    hui_templates[candidate_id]
                )
            
            combined_confidence = base_confidence * 0.7 + shape_confidence * 0.3
            
            if candidate_id in ["一", "七"]:
                yi_sim = 0.0
                qi_sim = 0.0
                if "一" in hui_templates:
                    yi_sim = self._calculate_hui_similarity(image_shape_features, hui_templates["一"])
                if "七" in hui_templates:
                    qi_sim = self._calculate_hui_similarity(image_shape_features, hui_templates["七"])
                
                if candidate_id == "一" and yi_sim < 0.6 and qi_sim > yi_sim:
                    combined_confidence *= 0.7
                elif candidate_id == "七" and qi_sim < 0.6 and yi_sim > qi_sim:
                    combined_confidence *= 0.7
                elif candidate_id == "一" and image_shape_features.get("has_bottom_hook", 0) > 0:
                    combined_confidence *= 0.5
                elif candidate_id == "七" and image_shape_features.get("has_bottom_hook", 0) < 0.5:
                    combined_confidence *= 0.8
            
            random_noise = random.uniform(-0.03, 0.03)
            final_confidence = max(0.0, min(1.0, combined_confidence + random_noise))
            
            results.append({
                "id": candidate_id,
                "name": candidate.get("name", candidate_id),
                "pinyin": candidate.get("pinyin", ""),
                "confidence": final_confidence,
                "shape_features": image_shape_features
            })
        
        results.sort(key=lambda x: x["confidence"], reverse=True)
        
        all_labels = [c["id"] for c in candidates]
        top_result = results[0]
        validated_id, validation_score = self._validate_hui_range(top_result["id"], all_labels)
        top_result["confidence"] *= validation_score
        
        if validated_id != top_result["id"]:
            for r in results:
                if r["id"] == validated_id:
                    r["confidence"] = max(r["confidence"], top_result["confidence"] * 0.9)
                    break
            results.sort(key=lambda x: x["confidence"], reverse=True)
            top_result = results[0]
        
        return {
            "component_type": component_type,
            "recognized": {
                "id": top_result["id"],
                "name": top_result["name"],
                "pinyin": top_result["pinyin"]
            },
            "confidence": top_result["confidence"],
            "candidates": results[:5],
            "shape_features": image_shape_features
        }

    def _determine_jianzi_structure(self, components: Dict[str, RecognitionResult]) -> str:
        """
        判断减字的结构类型：
        - 'vertical': 上下结构（上字先，下字后）
        - 'horizontal': 左右结构（左字先，右字后）
        - 'mixed': 混合结构（按左上右下顺序）
        
        判断依据：
        1. 检查上下组件的内容密度（笔画数）
        2. 检查左右组件的内容密度
        3. 结合减字常见结构模式
        """
        top_comp = components.get("top", {})
        bottom_comp = components.get("bottom", {})
        left_comp = components.get("left", {})
        right_comp = components.get("right", {})
        
        def get_complexity(comp: Dict) -> float:
            """计算组件复杂度（基于候选置信度分布）"""
            candidates = comp.get("candidates", [])
            if not candidates:
                return 0.0
            confidences = [c.get("confidence", 0) for c in candidates]
            if len(confidences) < 2:
                return float(confidences[0]) if confidences else 0.0
            return max(confidences) - min(confidences)
        
        top_complexity = get_complexity(top_comp)
        bottom_complexity = get_complexity(bottom_comp)
        left_complexity = get_complexity(left_comp)
        right_complexity = get_complexity(right_comp)
        
        vertical_complexity = top_complexity + bottom_complexity
        horizontal_complexity = left_complexity + right_complexity
        
        top_label = top_comp.get("recognized", {}).get("id", "")
        bottom_label = bottom_comp.get("recognized", {}).get("id", "")
        left_label = left_comp.get("recognized", {}).get("id", "")
        right_label = right_comp.get("recognized", {}).get("id", "")
        
        vertical_only = (top_label or bottom_label) and not (left_label or right_label)
        horizontal_only = (left_label or right_label) and not (top_label or bottom_label)
        
        if vertical_only:
            return "vertical"
        elif horizontal_only:
            return "horizontal"
        elif vertical_complexity > horizontal_complexity * 1.5:
            return "vertical"
        elif horizontal_complexity > vertical_complexity * 1.5:
            return "horizontal"
        else:
            return "mixed"

    def _get_combination_order(self, structure: str) -> List[str]:
        """
        根据结构类型返回组件组合顺序
        - vertical: ['top', 'bottom'] - 上下结构：上先下后
        - horizontal: ['left', 'right'] - 左右结构：左先右后
        - mixed: ['top', 'left', 'right', 'bottom'] - 混合结构：左上右下
        """
        if structure == "vertical":
            return ["top", "bottom"]
        elif structure == "horizontal":
            return ["left", "right"]
        else:
            return ["top", "left", "right", "bottom"]

    def recognize_all_components(
        self,
        component_images: Dict[str, ComponentImage]
    ) -> Dict[str, RecognitionResult]:
        type_map = self._determine_component_type_map()
        results = {}
        for position, image in component_images.items():
            component_type = type_map.get(position, "finger_positions")
            results[position] = self.recognize_component(image, component_type)
        return results

    def generate_mock_components(
        self,
        jianzi_id: str,
        bbox: BBox
    ) -> Dict[str, RecognitionResult]:
        random.seed(int(hashlib.md5(jianzi_id.encode()).hexdigest(), 16))
        x1, y1, x2, y2 = bbox
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        components = {}
        type_map = self._determine_component_type_map()
        for position, component_type in type_map.items():
            candidates = self.dictionary.get(component_type, [])
            if not candidates:
                continue
            num_candidates = len(candidates)
            weights = [random.random() for _ in range(num_candidates)]
            total = sum(weights)
            normalized_weights = [w / total for w in weights]
            selected_idx = random.choices(range(num_candidates), weights=normalized_weights, k=1)[0]
            selected = candidates[selected_idx]
            confidence = random.uniform(0.75, 0.98)
            candidate_list = []
            other_indices = [i for i in range(num_candidates) if i != selected_idx]
            random.shuffle(other_indices)
            top_other = other_indices[:4]
            candidate_list.append({
                "id": selected["id"],
                "name": selected["name"],
                "pinyin": selected["pinyin"],
                "confidence": confidence
            })
            for idx in top_other:
                cand = candidates[idx]
                candidate_list.append({
                    "id": cand["id"],
                    "name": cand["name"],
                    "pinyin": cand["pinyin"],
                    "confidence": random.uniform(0.3, confidence - 0.1)
                })
            candidate_list.sort(key=lambda x: x["confidence"], reverse=True)
            components[position] = {
                "component_type": component_type,
                "recognized": {
                    "id": selected["id"],
                    "name": selected["name"],
                    "pinyin": selected["pinyin"]
                },
                "confidence": confidence,
                "candidates": candidate_list,
                "bbox": self._get_component_bbox(bbox, position)
            }
        return components

    def _get_component_bbox(self, jianzi_bbox: BBox, position: str) -> BBox:
        x1, y1, x2, y2 = jianzi_bbox
        w = x2 - x1
        h = y2 - y1
        if position == "top":
            return (x1, y1, x2, y1 + h // 2)
        elif position == "bottom":
            return (x1, y1 + h // 2, x2, y2)
        elif position == "left":
            return (x1, y1, x1 + w // 2, y2)
        elif position == "right":
            return (x1 + w // 2, y1, x2, y2)
        else:
            return jianzi_bbox

    def recognize_jianzi_full(
        self,
        jianzi_image: ComponentImage,
        component_bboxes: Dict[str, BBox],
        use_mock: bool = False,
        jianzi_id: Optional[str] = None,
        jianzi_bbox: Optional[BBox] = None
    ) -> Dict[str, Any]:
        if use_mock and jianzi_id is not None and jianzi_bbox is not None:
            return self._build_jianzi_result(
                jianzi_id,
                jianzi_bbox,
                self.generate_mock_components(jianzi_id, jianzi_bbox)
            )
        component_images = {}
        for position, bbox in component_bboxes.items():
            cx1, cy1, cx2, cy2 = bbox
            cx1 = max(0, cx1)
            cy1 = max(0, cy1)
            cx2 = min(jianzi_image.shape[1], cx2)
            cy2 = min(jianzi_image.shape[0], cy2)
            component_images[position] = jianzi_image[cy1:cy2, cx1:cx2].copy()
        recognition_results = self.recognize_all_components(component_images)
        for position, result in recognition_results.items():
            result["bbox"] = component_bboxes[position]
        if jianzi_id is None:
            jianzi_id = f"jianzi_{random.randint(0, 9999):04d}"
        if jianzi_bbox is None:
            h, w = jianzi_image.shape[:2]
            jianzi_bbox = (0, 0, w, h)
        return self._build_jianzi_result(jianzi_id, jianzi_bbox, recognition_results)

    def _build_jianzi_result(
        self,
        jianzi_id: str,
        bbox: BBox,
        components: Dict[str, RecognitionResult]
    ) -> Dict[str, Any]:
        overall_confidence = np.mean([
            comp["confidence"] for comp in components.values()
        ]) if components else 0.0
        
        structure = self._determine_jianzi_structure(components)
        order = self._get_combination_order(structure)
        
        combined_parts = []
        for pos in order:
            comp_id = components.get(pos, {}).get("recognized", {}).get("id", "")
            if comp_id:
                combined_parts.append(comp_id)
        combined_id = "".join(combined_parts)
        
        return {
            "id": jianzi_id,
            "bbox": bbox,
            "combined_id": combined_id,
            "structure": structure,
            "combination_order": order,
            "overall_confidence": float(overall_confidence),
            "components": components,
            "notation": self._generate_notation(components)
        }

    def _generate_notation(self, components: Dict[str, RecognitionResult]) -> str:
        structure = self._determine_jianzi_structure(components)
        order = self._get_combination_order(structure)
        
        parts = []
        for pos in order:
            name = components.get(pos, {}).get("recognized", {}).get("name", "")
            if name:
                parts.append(name)
        
        return "".join(parts)

    def get_candidate_labels(self, component_type: str) -> List[Dict[str, str]]:
        return self.dictionary.get(component_type, [])

    def list_component_types(self) -> List[str]:
        return list(self.dictionary.keys())

    def save_recognition_visualization(
        self,
        image: np.ndarray,
        recognition_result: Dict[str, Any],
        output_path: str
    ) -> None:
        vis_image = image.copy()
        colors = {
            "top": (255, 0, 0),
            "bottom": (0, 255, 0),
            "left": (0, 0, 255),
            "right": (255, 255, 0)
        }
        for position, comp in recognition_result["components"].items():
            if "bbox" not in comp:
                continue
            x1, y1, x2, y2 = comp["bbox"]
            color = colors.get(position, (255, 255, 255))
            cv2.rectangle(vis_image, (x1, y1), (x2, y2), color, 2)
            label = f"{comp['recognized']['name']} ({comp['confidence']:.2f}"
            cv2.putText(vis_image, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
        cv2.putText(vis_image, recognition_result["notation"], (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        cv2.imwrite(output_path, vis_image)
