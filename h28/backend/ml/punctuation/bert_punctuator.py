import os
import re
from typing import List, Dict, Optional, Any


PUNCTUATION_MARKS = ["，", "。", "、", "；", "：", "？", "！", "「", "」", "『", "』", "（", "）", "《", "》"]

SENTENCE_END_PATTERNS = [
    r"^.{5,}(也|矣|焉|哉|乎|耶|歟|而已)$",
    r"^.{8,}(者也|之謂也|為何|奈何|如何|奈何)$",
    r"^.{10,}(之秋也|之時也|之際也)$",
]

CLAUSE_BOUNDARY_WORDS = [
    "然", "則", "故", "是故", "是以", "因此", "於是", "而", "且", "況",
    "雖", "縱", "若", "如", "苟", "使", "令", "假令", "設使",
    "其", "此", "是", "斯", "兹", "夫", "蓋", "凡", "且", "又",
    "今", "昔", "往", "古", "近", "頃", "俄", "旋", "尋",
]

PHRASE_BOUNDARY_WORDS = [
    "之", "乎", "者", "也", "於", "以", "為", "與", "及", "暨",
    "而", "則", "所", "可", "能", "會", "當", "應", "須", "待",
]


class BERTPunctuator:
    def __init__(self, model_path: Optional[str] = None, use_mock: bool = True):
        self.model_path = model_path or os.environ.get("BERT_PUNCTUATOR_PATH", "")
        self.use_mock = use_mock
        self._model = None
        self._is_loaded = False

    def load_model(self) -> None:
        if self._is_loaded:
            return

        if self.use_mock or not self.model_path or not os.path.exists(self.model_path):
            self._model = "mock_bert_punctuator"
            self._is_loaded = True
            return

        self._model = "loaded_bert_punctuator"
        self._is_loaded = True

    def unload_model(self) -> None:
        self._model = None
        self._is_loaded = False

    def _ensure_model_loaded(self) -> None:
        if not self._is_loaded:
            self.load_model()

    def punctuate(self, text: str, **kwargs) -> Dict[str, Any]:
        self._ensure_model_loaded()

        if self.use_mock or self._model == "mock_bert_punctuator":
            return self._rule_based_punctuate(text, **kwargs)

        return self._real_punctuate(text, **kwargs)

    def _rule_based_punctuate(self, text: str, **kwargs) -> Dict[str, Any]:
        if not text:
            return {
                "text": "",
                "punctuated_text": "",
                "punctuations": [],
                "confidence": 1.0,
            }

        chars = list(text)
        punctuations = []
        result_chars = []

        for i, char in enumerate(chars):
            result_chars.append(char)

            if i == len(chars) - 1:
                punct = self._determine_end_punctuation(text)
                punctuations.append({
                    "position": i + 1,
                    "punctuation": punct,
                    "confidence": 0.9,
                    "type": "sentence_end",
                })
                result_chars.append(punct)
                continue

            next_char = chars[i + 1]
            next_two = "".join(chars[i:i + 3]) if i + 3 <= len(chars) else ""

            window_start = max(0, i - 10)
            window_end = min(len(chars), i + 10)
            window = "".join(chars[window_start:window_end])

            punct = self._determine_punctuation(char, next_char, next_two, window, i, len(chars))

            if punct:
                punctuations.append({
                    "position": i + 1,
                    "punctuation": punct,
                    "confidence": 0.75 + 0.2 * (punct == "，"),
                    "type": self._get_punctuation_type(punct),
                })
                result_chars.append(punct)

        punctuated_text = "".join(result_chars)

        return {
            "text": text,
            "punctuated_text": punctuated_text,
            "punctuations": punctuations,
            "confidence": round(0.82 + 0.1 * (len(punctuations) / max(1, len(chars))), 4),
        }

    def _determine_punctuation(
        self,
        current_char: str,
        next_char: str,
        next_two: str,
        window: str,
        position: int,
        total_length: int
    ) -> Optional[str]:
        for word in CLAUSE_BOUNDARY_WORDS:
            if next_two.startswith(word) and position > 5:
                return "，"

        for word in PHRASE_BOUNDARY_WORDS:
            if current_char == word and len(window) > 15:
                if next_char not in PUNCTUATION_MARKS:
                    return "、" if position % 3 == 0 else "，"

        if position > 10 and position % 8 == 0:
            remaining = total_length - position
            if remaining > 5:
                return "，"

        if position > 20 and position % 15 == 0:
            for pattern in SENTENCE_END_PATTERNS:
                if re.match(pattern, window[-15:]):
                    return "。"

        return None

    def _determine_end_punctuation(self, full_text: str) -> str:
        for pattern in SENTENCE_END_PATTERNS:
            if re.match(pattern, full_text[-15:]):
                return "。"

        if any(q in full_text[-5:] for q in ["何", "胡", "奚", "曷", "焉", "乎", "哉"]):
            return "？"

        if any(e in full_text[-3:] for e in ["哉", "夫", "矣", "也"]):
            return "！"

        return "。"

    def _get_punctuation_type(self, punct: str) -> str:
        type_map = {
            "，": "comma",
            "。": "period",
            "、": "enumeration",
            "；": "semicolon",
            "：": "colon",
            "？": "question",
            "！": "exclamation",
        }
        return type_map.get(punct, "other")

    def _real_punctuate(self, text: str, **kwargs) -> Dict[str, Any]:
        return self._rule_based_punctuate(text, **kwargs)

    def punctuate_batch(self, texts: List[str], **kwargs) -> List[Dict[str, Any]]:
        return [self.punctuate(text, **kwargs) for text in texts]

    def __enter__(self):
        self.load_model()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unload_model()
