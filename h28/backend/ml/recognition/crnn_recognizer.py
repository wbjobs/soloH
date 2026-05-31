import os
import numpy as np
from typing import List, Dict, Optional, Tuple, Any


TRADITIONAL_VARIANT_DICT = {
    "為": ["爲", "為", "谓"],
    "後": ["后", "後", "逅"],
    "裡": ["里", "裏", "裡"],
    "發": ["发", "發", "髮"],
    "複": ["复", "複", "覆"],
    "獲": ["获", "獲", "穫"],
    "幹": ["干", "幹", "榦"],
    "鬥": ["斗", "鬥", "鬬"],
    "幾": ["几", "幾", "机"],
    "瞭": ["了", "瞭", "辽"],
    "麽": ["么", "麽", "摩"],
    "纔": ["才", "纔", "财"],
    "濛": ["蒙", "濛", "蒙"],
    "嚐": ["尝", "嚐", "偿"],
    "捨": ["舍", "捨", "舍"],
    "雙": ["双", "雙", "霜"],
    "臺": ["台", "臺", "台"],
    "颱": ["台", "颱", "抬"],
    "體": ["体", "體", "休"],
    "鬱": ["郁", "鬱", "郁"],
    "願": ["愿", "願", "原"],
    "嶽": ["岳", "嶽", "狱"],
    "雲": ["云", "雲", "云"],
    "隻": ["只", "隻", "织"],
    "準": ["准", "準", "淮"],
    "總": ["总", "總", "聪"],
    "鑽": ["钻", "鑽", "躜"],
    "巖": ["岩", "巖", "严"],
    "異": ["异", "異", "翼"],
    "韻": ["韵", "韻", "均"],
    "髒": ["脏", "髒", "葬"],
    "鑑": ["鉴", "鑑", "监"],
    "蘋": ["苹", "蘋", "萍"],
    "盧": ["卢", "盧", "炉"],
    "肅": ["肃", "肅", "萧"],
    "舊": ["旧", "舊", "臼"],
    "羅": ["罗", "羅", "萝"],
    "樂": ["乐", "樂", "泺"],
    "爾": ["尔", "爾", "迩"],
    "諸": ["诸", "諸", "猪"],
}

COMMON_TRADITIONAL_CHARS = "的一是了我不人在他有这个上们来到时大地为子中你说生国年着就那和要她出也得里后自以会家可下而过天去能用好我时作多然事学么都好看起发天当没成只还进样道理群工部者力己些山但水二高问今外从学自者众它石四合先间向关经百更五自无何加日万明六通十真打才本公料现月长四外定民那北字由章平重反并关数气每此少非文各儿入风别果月它定新公体件利别都改原正完间理必期近此经求正风决西那"

MOCK_TEXTS = [
    "先帝創業未半而中道崩殂",
    "今天下三分益州疲弊",
    "此誠危急存亡之秋也",
    "然侍衛之臣不懈於內",
    "忠志之士忘身於外者",
    "蓋追先帝之殊遇欲報之於陛下也",
    "誠宜開張聖聽以光先帝遺德",
    "恢弘志士之氣不宜妄自菲薄",
    "引喻失義以塞忠諫之路也",
    "宮中府中俱為一體",
    "陟罰臧否不宜異同",
    "若有作奸犯科及為忠善者",
    "宜付有司論其刑賞",
    "以昭陛下平明之理",
    "不宜偏私使內外異法也",
]


class CRNNRecognizer:
    def __init__(self, model_path: Optional[str] = None, use_mock: bool = True):
        self.model_path = model_path or os.environ.get("CRNN_MODEL_PATH", "")
        self.use_mock = use_mock
        self.variant_dict = TRADITIONAL_VARIANT_DICT
        self._model = None
        self._is_loaded = False

    def load_model(self) -> None:
        if self._is_loaded:
            return

        if self.use_mock or not self.model_path or not os.path.exists(self.model_path):
            self._model = "mock_crnn_model"
            self._is_loaded = True
            return

        self._model = "loaded_crnn_model"
        self._is_loaded = True

    def unload_model(self) -> None:
        self._model = None
        self._is_loaded = False

    def _ensure_model_loaded(self) -> None:
        if not self._is_loaded:
            self.load_model()

    def recognize(
        self,
        image: np.ndarray,
        return_candidates: bool = True,
        top_k: int = 5,
        **kwargs
    ) -> Dict[str, Any]:
        self._ensure_model_loaded()

        if self.use_mock or self._model == "mock_crnn_model":
            return self._mock_recognize(image, return_candidates, top_k, **kwargs)

        return self._real_recognize(image, return_candidates, top_k, **kwargs)

    def _mock_recognize(
        self,
        image: np.ndarray,
        return_candidates: bool,
        top_k: int,
        **kwargs
    ) -> Dict[str, Any]:
        text_idx = kwargs.get("text_index", np.random.randint(0, len(MOCK_TEXTS)))
        base_text = MOCK_TEXTS[text_idx % len(MOCK_TEXTS)]

        confidence = 0.88 + np.random.uniform(-0.1, 0.1)

        result = {
            "text": base_text,
            "confidence": round(confidence, 4),
            "char_confidences": [round(0.85 + np.random.uniform(-0.15, 0.1), 4) for _ in base_text],
        }

        if return_candidates:
            candidates = self._generate_candidates(base_text, top_k)
            result["candidates"] = candidates

        return result

    def _generate_candidates(self, text: str, top_k: int) -> List[Dict[str, Any]]:
        candidates = []

        main_candidate = {
            "text": text,
            "confidence": round(0.88 + np.random.uniform(-0.05, 0.05), 4),
            "is_variant": False,
        }
        candidates.append(main_candidate)

        for i, char in enumerate(text):
            if char in self.variant_dict and len(candidates) < top_k:
                variants = self.variant_dict[char]
                for variant in variants:
                    if len(candidates) >= top_k:
                        break
                    variant_text = text[:i] + variant + text[i + 1:]
                    variant_confidence = round(0.7 + np.random.uniform(0, 0.15), 4)
                    candidates.append({
                        "text": variant_text,
                        "confidence": variant_confidence,
                        "is_variant": True,
                        "original_char": char,
                        "variant_char": variant,
                        "position": i,
                    })

        while len(candidates) < top_k:
            random_text = "".join([
                COMMON_TRADITIONAL_CHARS[np.random.randint(0, len(COMMON_TRADITIONAL_CHARS))]
                for _ in range(len(text))
            ])
            candidates.append({
                "text": random_text,
                "confidence": round(0.5 + np.random.uniform(0, 0.2), 4),
                "is_variant": False,
            })

        candidates.sort(key=lambda x: x["confidence"], reverse=True)
        return candidates[:top_k]

    def ctc_decode(
        self,
        probs: np.ndarray,
        characters: List[str],
        blank_index: int = 0,
        merge_repeated: bool = True,
        beam_width: int = 5,
        time_step_threshold: float = 0.3
    ) -> Dict[str, Any]:
        seq_length = probs.shape[0]
        num_classes = probs.shape[1]

        if beam_width <= 1:
            return self._ctc_greedy_decode(
                probs, characters, blank_index, merge_repeated, time_step_threshold
            )

        return self._ctc_beam_search_decode(
            probs, characters, blank_index, beam_width, time_step_threshold
        )

    def _ctc_greedy_decode(
        self,
        probs: np.ndarray,
        characters: List[str],
        blank_index: int,
        merge_repeated: bool,
        time_step_threshold: float
    ) -> Dict[str, Any]:
        seq_length = probs.shape[0]
        argmax_indices = np.argmax(probs, axis=1)
        max_probs = np.max(probs, axis=1)

        decoded_indices: List[int] = []
        char_confidences: List[float] = []
        char_time_spans: List[Tuple[int, int]] = []

        prev_index = -1
        current_char_start = 0
        current_char_probs: List[float] = []

        for t in range(seq_length):
            current_index = argmax_indices[t]
            current_prob = max_probs[t]

            if current_index == blank_index:
                if prev_index != blank_index and prev_index != -1:
                    decoded_indices.append(prev_index)
                    char_confidences.append(np.mean(current_char_probs))
                    char_time_spans.append((current_char_start, t - 1))
                prev_index = blank_index
                current_char_probs = []
                continue

            if current_index != prev_index:
                if prev_index != blank_index and prev_index != -1:
                    if merge_repeated:
                        time_span = t - current_char_start
                        seq_avg_frames = len(current_char_probs)
                        if time_span >= seq_length * time_step_threshold or seq_avg_frames >= seq_length * time_step_threshold * 2:
                            decoded_indices.append(prev_index)
                            char_confidences.append(np.mean(current_char_probs))
                            char_time_spans.append((current_char_start, t - 1))
                        elif len(current_char_probs) >= 5 and time_span >= seq_length * time_step_threshold * 0.5:
                            avg_prob = np.mean(current_char_probs)
                            if avg_prob > 0.7:
                                decoded_indices.append(prev_index)
                                char_confidences.append(avg_prob)
                                char_time_spans.append((current_char_start, t - 1))
                    else:
                        decoded_indices.append(prev_index)
                        char_confidences.append(np.mean(current_char_probs))
                        char_time_spans.append((current_char_start, t - 1))

                current_char_start = t
                current_char_probs = [current_prob]
            else:
                current_char_probs.append(current_prob)

            prev_index = current_index

        if prev_index != blank_index and prev_index != -1 and current_char_probs:
            decoded_indices.append(prev_index)
            char_confidences.append(np.mean(current_char_probs))
            char_time_spans.append((current_char_start, seq_length - 1))

        text = ''.join([characters[i] for i in decoded_indices if i < len(characters)])

        return {
            'text': text,
            'indices': decoded_indices,
            'char_confidences': char_confidences,
            'char_time_spans': char_time_spans,
            'confidence': np.mean(char_confidences) if char_confidences else 0.0
        }

    def _ctc_beam_search_decode(
        self,
        probs: np.ndarray,
        characters: List[str],
        blank_index: int,
        beam_width: int,
        time_step_threshold: float
    ) -> Dict[str, Any]:
        seq_length = probs.shape[0]
        num_classes = len(characters) + 1

        beams: List[Dict[str, Any]] = [
            {
                'text': '',
                'indices': [],
                'prob': 1.0,
                'prob_non_blank': 1.0,
                'prob_blank': 0.0,
                'last_char_index': -1,
                'char_confidences': [],
                'char_time_spans': [],
                'current_char_probs': [],
                'current_char_start': 0
            }
        ]

        for t in range(seq_length):
            new_beams: Dict[str, Dict[str, Any]] = {}

            for beam in beams:
                for c in range(num_classes):
                    prob = probs[t, c]
                    if prob < 1e-10:
                        continue

                    if c == blank_index:
                        new_beam = self._extend_beam_with_blank(beam, t, time_step_threshold)
                        new_beam['prob'] += beam['prob'] * prob
                        new_beam['prob_blank'] += beam['prob'] * prob

                        key = new_beam['text'] + '|' + str(new_beam['last_char_index']) + '|blank'
                        if key in new_beams:
                            new_beams[key]['prob'] += new_beam['prob']
                            new_beams[key]['prob_blank'] += new_beam['prob_blank']
                        else:
                            new_beams[key] = new_beam
                    else:
                        char_index = c - 1 if c > blank_index else c
                        if char_index >= len(characters):
                            continue

                        new_beam = self._extend_beam_with_char(
                            beam, char_index, characters[char_index], t, prob,
                            time_step_threshold
                        )
                        new_beam['prob'] += beam['prob'] * prob
                        new_beam['prob_non_blank'] += beam['prob'] * prob

                        key = new_beam['text'] + '|' + str(new_beam['last_char_index']) + '|char'
                        if key in new_beams:
                            new_beams[key]['prob'] += new_beam['prob']
                            new_beams[key]['prob_non_blank'] += new_beam['prob_non_blank']
                        else:
                            new_beams[key] = new_beam

            beams = sorted(new_beams.values(), key=lambda x: x['prob'], reverse=True)[:beam_width]
            total_prob = sum(b['prob'] for b in beams) + 1e-10
            for beam in beams:
                beam['prob'] /= total_prob
                beam['prob_blank'] /= total_prob
                beam['prob_non_blank'] /= total_prob

        best_beam = beams[0] if beams else {}

        if best_beam.get('current_char_probs'):
            best_beam['indices'].append(best_beam['last_char_index'])
            best_beam['char_confidences'].append(np.mean(best_beam['current_char_probs']))
            best_beam['char_time_spans'].append((best_beam['current_char_start'], seq_length - 1))

        return {
            'text': best_beam.get('text', ''),
            'indices': best_beam.get('indices', []),
            'char_confidences': best_beam.get('char_confidences', []),
            'char_time_spans': best_beam.get('char_time_spans', []),
            'confidence': float(np.mean(best_beam.get('char_confidences', [0.0]))),
            'beam_probs': [b.get('prob', 0.0) for b in beams[:beam_width]]
        }

    def _extend_beam_with_blank(
        self,
        beam: Dict[str, Any],
        time_step: int,
        time_step_threshold: float
    ) -> Dict[str, Any]:
        new_beam = {
            'text': beam['text'],
            'indices': beam['indices'].copy(),
            'prob': 0.0,
            'prob_non_blank': 0.0,
            'prob_blank': 0.0,
            'last_char_index': -1,
            'char_confidences': beam['char_confidences'].copy(),
            'char_time_spans': beam['char_time_spans'].copy(),
            'current_char_probs': [],
            'current_char_start': time_step + 1
        }

        if beam['last_char_index'] != -1 and beam['current_char_probs']:
            time_span = time_step - beam['current_char_start']
            seq_length = 100
            if time_span >= seq_length * time_step_threshold or len(beam['current_char_probs']) >= 3:
                new_beam['indices'].append(beam['last_char_index'])
                new_beam['char_confidences'].append(np.mean(beam['current_char_probs']))
                new_beam['char_time_spans'].append((beam['current_char_start'], time_step - 1))

        return new_beam

    def _extend_beam_with_char(
        self,
        beam: Dict[str, Any],
        char_index: int,
        char: str,
        time_step: int,
        prob: float,
        time_step_threshold: float
    ) -> Dict[str, Any]:
        if char_index == beam['last_char_index'] and beam['last_char_index'] != -1:
            time_span = time_step - beam['current_char_start']
            seq_length = 100
            current_frames = len(beam['current_char_probs']) + 1

            should_emit_new = False
            if time_span >= seq_length * time_step_threshold or current_frames >= seq_length * time_step_threshold * 2:
                should_emit_new = True
            elif current_frames >= 6 and time_span >= seq_length * time_step_threshold * 0.4:
                avg_prob = np.mean(beam['current_char_probs'] + [prob])
                if avg_prob > 0.75:
                    should_emit_new = True

            if should_emit_new:
                new_beam = {
                    'text': beam['text'] + char,
                    'indices': beam['indices'].copy() + [char_index],
                    'prob': 0.0,
                    'prob_non_blank': 0.0,
                    'prob_blank': 0.0,
                    'last_char_index': char_index,
                    'char_confidences': beam['char_confidences'].copy() + [np.mean(beam['current_char_probs'] + [prob])],
                    'char_time_spans': beam['char_time_spans'].copy() + [(beam['current_char_start'], time_step)],
                    'current_char_probs': [prob],
                    'current_char_start': time_step
                }
            else:
                new_beam = {
                    'text': beam['text'],
                    'indices': beam['indices'].copy(),
                    'prob': 0.0,
                    'prob_non_blank': 0.0,
                    'prob_blank': 0.0,
                    'last_char_index': char_index,
                    'char_confidences': beam['char_confidences'].copy(),
                    'char_time_spans': beam['char_time_spans'].copy(),
                    'current_char_probs': beam['current_char_probs'] + [prob],
                    'current_char_start': beam['current_char_start']
                }
        else:
            new_text = beam['text'] + char
            new_indices = beam['indices'].copy()
            new_confidences = beam['char_confidences'].copy()
            new_time_spans = beam['char_time_spans'].copy()

            if beam['last_char_index'] != -1 and beam['current_char_probs']:
                new_indices.append(beam['last_char_index'])
                new_confidences.append(np.mean(beam['current_char_probs']))
                new_time_spans.append((beam['current_char_start'], time_step - 1))

            new_beam = {
                'text': new_text,
                'indices': new_indices,
                'prob': 0.0,
                'prob_non_blank': 0.0,
                'prob_blank': 0.0,
                'last_char_index': char_index,
                'char_confidences': new_confidences,
                'char_time_spans': new_time_spans,
                'current_char_probs': [prob],
                'current_char_start': time_step
            }

        return new_beam

    def fix_repeated_chars(
        self,
        text: str,
        char_time_spans: Optional[List[Tuple[int, int]]] = None,
        char_confidences: Optional[List[float]] = None,
        common_repeats: Optional[List[str]] = None,
        protected_phrases: Optional[List[str]] = None
    ) -> str:
        if common_repeats is None:
            common_repeats = ['人人', '年年', '月月', '日日', '一一', '二二', '三三',
                              '九九', '十十', '百百']

        if protected_phrases is None:
            protected_phrases = ['千千万万', '大大小小', '多多少少', '长长短短',
                                 '高高低低', '进进出出', '来来往往', '明明白白']

        if char_time_spans is not None and len(char_time_spans) > 1:
            return text

        for phrase in protected_phrases:
            if phrase in text:
                text = text.replace(phrase, f'{{{{PROTECT_{phrase}}}}}')

        result = []
        i = 0
        while i < len(text):
            if text[i:i+2] == '{{':
                end_idx = text.find('}}', i)
                if end_idx != -1:
                    protected = text[i:end_idx+2]
                    result.append(protected)
                    i = end_idx + 2
                    continue

            if i + 1 < len(text) and text[i] == text[i + 1]:
                repeat_pair = text[i:i + 2]
                if repeat_pair in common_repeats:
                    result.append(text[i])
                    result.append(text[i + 1])
                    i += 2
                    continue

                if char_confidences and i < len(char_confidences) - 1:
                    conf1 = char_confidences[i]
                    conf2 = char_confidences[i + 1]
                    if abs(conf1 - conf2) < 0.1 and conf1 > 0.7:
                        result.append(text[i])
                        result.append(text[i + 1])
                        i += 2
                        continue

                result.append(text[i])
                i += 2
            else:
                result.append(text[i])
                i += 1

        result_text = ''.join(result)
        for phrase in protected_phrases:
            result_text = result_text.replace(f'{{{{PROTECT_{phrase}}}}}', phrase)

        return result_text

    def _real_recognize(
        self,
        image: np.ndarray,
        return_candidates: bool,
        top_k: int,
        **kwargs
    ) -> Dict[str, Any]:
        return self._mock_recognize(image, return_candidates, top_k, **kwargs)

    def recognize_batch(
        self,
        images: List[np.ndarray],
        return_candidates: bool = True,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        return [
            self.recognize(img, return_candidates, top_k, text_index=i)
            for i, img in enumerate(images)
        ]

    def __enter__(self):
        self.load_model()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unload_model()
