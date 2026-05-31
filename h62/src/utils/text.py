import re
import numpy as np
from typing import List, Dict, Optional

_pad = "_"
_punctuation = "!'(),.:;? "
_special = "-"
_letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_numbers = "0123456789"

symbols = [_pad] + list(_special) + list(_punctuation) + list(_letters) + list(_numbers)

_symbol_to_id = {s: i for i, s in enumerate(symbols)}
_id_to_symbol = {i: s for i, s in enumerate(symbols)}

_curly_re = re.compile(r"(.*?)\{(.+?)\}(.*)")


def text_to_sequence(text: str, cleaner_names: Optional[List[str]] = None) -> List[int]:
    if cleaner_names is None:
        cleaner_names = ["english_cleaners"]
    
    sequence = []
    while len(text):
        m = _curly_re.match(text)
        if not m:
            sequence += _symbols_to_sequence(_clean_text(text, cleaner_names))
            break
        sequence += _symbols_to_sequence(_clean_text(m.group(1), cleaner_names))
        sequence += _arpabet_to_sequence(m.group(2))
        text = m.group(3)
    
    return sequence


def sequence_to_text(sequence: List[int]) -> str:
    return "".join([_id_to_symbol[s] for s in sequence if s in _id_to_symbol])


def _clean_text(text: str, cleaner_names: List[str]) -> str:
    for name in cleaner_names:
        cleaner = getattr(_cleaners, name)
        if not cleaner:
            raise Exception(f"Unknown cleaner: {name}")
        text = cleaner(text)
    return text


def _symbols_to_sequence(symbols_str: str) -> List[int]:
    return [_symbol_to_id[s] for s in symbols_str if _should_keep_symbol(s)]


def _arpabet_to_sequence(text: str) -> List[int]:
    return _symbols_to_sequence(["@" + s for s in text.split()])


def _should_keep_symbol(s: str) -> bool:
    return s in _symbol_to_id and s != _pad


class _cleaners:
    @staticmethod
    def english_cleaners(text: str) -> str:
        text = convert_to_ascii(text)
        text = lowercase(text)
        text = expand_numbers(text)
        text = collapse_whitespace(text)
        return text

    @staticmethod
    def basic_cleaners(text: str) -> str:
        text = lowercase(text)
        text = collapse_whitespace(text)
        return text

    @staticmethod
    def transliteration_cleaners(text: str) -> str:
        text = convert_to_ascii(text)
        text = lowercase(text)
        text = collapse_whitespace(text)
        return text


def convert_to_ascii(text: str) -> str:
    try:
        text = text.encode("ascii", "ignore").decode("ascii")
    except Exception:
        pass
    return text


def lowercase(text: str) -> str:
    return text.lower()


def collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def expand_numbers(text: str) -> str:
    return text


def text_to_tensor(text: str, cleaner_names: Optional[List[str]] = None) -> np.ndarray:
    sequence = text_to_sequence(text, cleaner_names)
    return np.array(sequence, dtype=np.int32)


class TextProcessor:
    def __init__(self, cleaner_names: Optional[List[str]] = None):
        self.cleaner_names = cleaner_names or ["english_cleaners"]
        self.symbols = symbols
        self.n_symbols = len(symbols)

    def encode(self, text: str) -> np.ndarray:
        return text_to_tensor(text, self.cleaner_names)

    def decode(self, sequence: List[int]) -> str:
        return sequence_to_text(sequence)

    def encode_batch(self, texts: List[str]) -> List[np.ndarray]:
        return [self.encode(text) for text in texts]

    def get_symbol_count(self) -> int:
        return self.n_symbols


class MultilingualTextProcessor(TextProcessor):
    def __init__(self, language: str = "en", cleaner_names: Optional[List[str]] = None):
        super().__init__(cleaner_names)
        self.language = language
        self._init_language_symbols()

    def _init_language_symbols(self):
        if self.language == "zh":
            chinese_chars = "，。！？、；：\"\"''（）【】《》"
            self.symbols += list(chinese_chars)
            self._symbol_to_id = {s: i for i, s in enumerate(self.symbols)}
            self._id_to_symbol = {i: s for i, s in enumerate(self.symbols)}
            self.n_symbols = len(self.symbols)

    def encode(self, text: str) -> np.ndarray:
        if self.language == "zh":
            return self._encode_chinese(text)
        return super().encode(text)

    def _encode_chinese(self, text: str) -> np.ndarray:
        text = text.lower()
        text = collapse_whitespace(text)
        sequence = []
        for char in text:
            if char in self._symbol_to_id:
                sequence.append(self._symbol_to_id[char])
            else:
                pinyin = self._char_to_pinyin(char)
                for p in pinyin:
                    if p in self._symbol_to_id:
                        sequence.append(self._symbol_to_id[p])
        return np.array(sequence, dtype=np.int32)

    @staticmethod
    def _char_to_pinyin(char: str) -> str:
        return char


def get_mask_from_lengths(lengths: np.ndarray, max_len: Optional[int] = None) -> np.ndarray:
    if max_len is None:
        max_len = np.max(lengths)
    batch_size = len(lengths)
    ids = np.tile(np.arange(max_len), (batch_size, 1))
    mask = ids < lengths[:, np.newaxis]
    return mask
