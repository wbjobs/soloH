import os
import json
from typing import Dict, Optional, Tuple, List, Any


class GongcheConverter:
    """工尺谱转换服务，将古琴减字谱转换为工尺谱字和白话文说明。"""

    def __init__(self, dictionary_path: Optional[str] = None):
        """初始化工尺谱转换器，从dictionary.json加载映射表。"""
        if dictionary_path is None:
            dictionary_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'dictionary.json')
        self.dictionary_path = dictionary_path
        self._dictionary = self._load_dictionary()
        
        self._fingers = self._dictionary.get('fingers', {})
        self._strings = self._dictionary.get('strings', {})
        self._hui_positions = self._dictionary.get('hui_positions', {})
        self._gongche_map = self._dictionary.get('gongche_map', {})
        
        self._string_mapping = {}
        for char, info in self._strings.items():
            self._string_mapping[char] = {
                'string': info.get('number', 1),
                'note': info.get('note', 'C')
            }
        
        self._hui_mapping = {}
        for char, info in self._hui_positions.items():
            self._hui_mapping[char.replace('徽', '')] = info.get('position', 1.0)
        
        self._technique_mapping = {}
        self._technique_code_to_char = {}
        for char, info in self._fingers.items():
            finger_type = info.get('type', 'right')
            technique_code = 'sanyin'
            if char == '按':
                technique_code = 'anyin'
            elif char == '泛':
                technique_code = 'fanyin'
            elif char == '散':
                technique_code = 'sanyin'
            
            self._technique_mapping[char] = {
                'code': technique_code,
                'name': info.get('name', char),
                'description': info.get('description', ''),
                'hand': finger_type
            }
            self._technique_code_to_char[technique_code] = char
        
        self._gongche_mapping = {}
        self._gongche_note_to_char = {}
        for note_with_octave, gongche_char in self._gongche_map.items():
            note_name = note_with_octave[:-1] if note_with_octave[:-1].isalpha() else note_with_octave[:-1]
            octave = int(note_with_octave[-1])
            self._gongche_mapping[note_name] = {
                'gongche': gongche_char,
                'pinyin': ''
            }
            self._gongche_note_to_char[note_with_octave] = gongche_char
        
        self._octave_markers = {
            'low': '低',
            'normal': '',
            'high': '高'
        }

        self._base_octave_for_string = {
            1: 2,
            2: 2,
            3: 3,
            4: 3,
            5: 3,
            6: 3,
            7: 3
        }

    def _load_dictionary(self) -> dict:
        """加载映射表字典。"""
        dict_path = self.dictionary_path
        with open(dict_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_technique_name(self, code: str) -> str:
        """
        将技法代码转换为中文名称。

        Args:
            code: 技法代码（如"sanyin"、"anyin"等）

        Returns:
            技法的中文名称，如果未找到则返回原代码
        """
        for char, info in self._technique_mapping.items():
            if info.get('code') == code:
                return info.get('name', code)
        return code

    def _get_technique_info(self, technique_code: str) -> Optional[dict]:
        """根据技法代码获取技法信息。"""
        for char, info in self._technique_mapping.items():
            if info.get('code') == technique_code:
                return info
        return None

    def _parse_hui_position(self, hui_str: str) -> Optional[float]:
        """
        解析徽位字符串为数值。

        Args:
            hui_str: 徽位字符串（如"七"、"七半"、"九徽"等）

        Returns:
            徽位数值（1-13），如果无法解析返回None
        """
        if not hui_str:
            return None

        hui_str = hui_str.replace('徽', '').replace(' ', '')

        if hui_str in self._hui_mapping:
            return self._hui_mapping[hui_str]

        for key in ['半', '少']:
            if key in hui_str:
                base_str = hui_str.replace(key, '')
                if base_str in self._hui_mapping:
                    return self._hui_mapping[base_str] + self._hui_mapping[key]

        return None

    def _get_note_from_hui(self, string_num: int, hui: float, technique: str) -> Tuple[str, int]:
        """
        根据弦号、徽位和技法计算音名和八度。

        Args:
            string_num: 弦号（1-7）
            hui: 徽位（1-13）
            technique: 技法类型

        Returns:
            (音名, 八度) 元组
        """
        base_note = {
            1: 'C', 2: 'D', 3: 'E', 4: 'F', 5: 'G', 6: 'A', 7: 'B'
        }.get(string_num, 'C')

        base_octave = self._base_octave_for_string.get(string_num, 3)

        if technique == 'sanyin':
            return base_note, base_octave

        hui_to_interval = {
            1: 24,
            2: 19,
            3: 16,
            4: 12,
            5: 9,
            6: 7,
            7: 5,
            8: 4,
            9: 2,
            10: 0,
            11: -2,
            12: -4,
            13: -5
        }

        if hui in hui_to_interval:
            interval = hui_to_interval[hui]
        else:
            interval = int(round(-5 + (13 - hui) * 2))

        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        base_index = note_names.index(base_note)
        new_index = (base_index + interval) % 12
        octave_shift = (base_index + interval) // 12

        return note_names[new_index], base_octave + octave_shift

    def _get_octave_marker(self, octave: int, base_octave: int = 4) -> str:
        """根据八度获取工尺谱八度标记。"""
        if octave < base_octave:
            return self._octave_markers['low']
        elif octave > base_octave:
            return self._octave_markers['high']
        return self._octave_markers['normal']

    def jianzi_to_gongche(self, jianzi: dict) -> Dict:
        """
        将减字谱对象转换为工尺谱表示。

        Args:
            jianzi: 减字谱对象，包含string、hui、technique等字段

        Returns:
            包含工尺谱信息的字典，包括gongche_char、octave_marker、pinyin等
        """
        string_id = jianzi.get('string', '一')
        hui_str = jianzi.get('hui', '')
        technique = jianzi.get('technique', 'sanyin')

        string_info = self._string_mapping.get(string_id, {})
        string_num = string_info.get('string', 1)

        hui = self._parse_hui_position(hui_str)

        note_name, octave = self._get_note_from_hui(string_num, hui or 10, technique)

        gongche_info = self._gongche_mapping.get(note_name, {'gongche': note_name, 'pinyin': ''})
        octave_marker = self._get_octave_marker(octave)

        technique_info = self._get_technique_info(technique)
        technique_char = ''
        for char, info in self._technique_mapping.items():
            if info.get('code') == technique:
                technique_char = char
                break

        return {
            'gongche_char': gongche_info['gongche'],
            'octave_marker': octave_marker,
            'full_gongche': octave_marker + gongche_info['gongche'],
            'pinyin': gongche_info['pinyin'],
            'note_name': note_name,
            'octave': octave,
            'technique_char': technique_char,
            'technique_name': technique_info.get('name', '') if technique_info else '',
            'string': string_id,
            'hui': hui_str,
            'display': f"{technique_char}{octave_marker}{gongche_info['gongche']}"
        }

    def generate_description(self, jianzi: dict) -> Dict:
        """
        生成减字谱的白话文指法说明。

        Args:
            jianzi: 减字谱对象

        Returns:
            包含详细说明的字典
        """
        string_id = jianzi.get('string', '一')
        hui_str = jianzi.get('hui', '')
        technique = jianzi.get('technique', 'sanyin')
        right_hand = jianzi.get('right_hand', '')
        left_hand = jianzi.get('left_hand', '')

        string_info = self._string_mapping.get(string_id, {})
        string_num = string_info.get('string', 1)
        string_note = string_info.get('note', 'C')

        technique_info = self._get_technique_info(technique)
        technique_name = technique_info.get('name', technique) if technique_info else technique
        technique_desc = technique_info.get('description', '') if technique_info else ''

        hui = self._parse_hui_position(hui_str)
        hui_desc = ''
        if hui_str:
            if hui and hui == int(hui):
                hui_desc = f"第{int(hui)}徽"
            else:
                hui_desc = f"{hui_str}徽"

        parts = []

        if technique == 'sanyin':
            parts.append(f"散音：右手指法{technique_name}弹第{string_num}弦（{string_note}弦）")
            if right_hand:
                rh_info = self._get_technique_info(right_hand)
                if rh_info:
                    parts.append(f"，用右手{rh_info.get('name', right_hand)}法")
        elif technique == 'anyin':
            parts.append(f"按音：左手按第{string_num}弦{hui_desc}")
            if left_hand:
                lh_info = self._get_technique_info(left_hand)
                if lh_info:
                    parts.append(f"，用左手{lh_info.get('name', left_hand)}法")
            if right_hand:
                rh_info = self._get_technique_info(right_hand)
                if rh_info:
                    parts.append(f"，右手{rh_info.get('name', right_hand)}弹弦")
        elif technique == 'fanyin':
            parts.append(f"泛音：左手轻触第{string_num}弦{hui_desc}")
            if right_hand:
                rh_info = self._get_technique_info(right_hand)
                if rh_info:
                    parts.append(f"，右手{rh_info.get('name', right_hand)}弹弦")
        else:
            parts.append(f"{technique_name}：")
            if hui_desc:
                parts.append(f"第{string_num}弦{hui_desc}")
            else:
                parts.append(f"第{string_num}弦")
            if right_hand:
                rh_info = self._get_technique_info(right_hand)
                if rh_info:
                    parts.append(f"，右手{rh_info.get('name', right_hand)}")
            if left_hand:
                lh_info = self._get_technique_info(left_hand)
                if lh_info:
                    parts.append(f"，左手{lh_info.get('name', left_hand)}")

        note_name, octave = self._get_note_from_hui(string_num, hui or 10, technique)
        gongche = self.jianzi_to_gongche(jianzi)

        description = {
            'short': ''.join(parts),
            'detailed': f"【{gongche['full_gongche']}】{''.join(parts)}。{technique_desc}。",
            'technique_name': technique_name,
            'technique_description': technique_desc,
            'string': f"第{string_num}弦（{string_note}弦）",
            'hui_position': hui_desc,
            'note': f"{note_name}{octave}",
            'gongche': gongche['full_gongche'],
            'pinyin': gongche['pinyin']
        }

        return description

    def batch_convert(self, jianzi_list: List[dict]) -> List[Dict]:
        """
        批量转换减字谱列表为工尺谱。

        Args:
            jianzi_list: 减字谱对象列表

        Returns:
            工尺谱信息列表
        """
        return [self.jianzi_to_gongche(jz) for jz in jianzi_list]

    def batch_describe(self, jianzi_list: List[dict]) -> List[Dict]:
        """
        批量生成减字谱说明。

        Args:
            jianzi_list: 减字谱对象列表

        Returns:
            说明信息列表
        """
        return [self.generate_description(jz) for jz in jianzi_list]

    def get_technique_list(self) -> List[Dict]:
        """
        获取所有技法列表。

        Returns:
            技法信息列表，每个包含code、name、description
        """
        techniques = []
        for char, info in self._technique_mapping.items():
            techniques.append({
                'char': char,
                'code': info.get('code', ''),
                'name': info.get('name', ''),
                'description': info.get('description', '')
            })
        return techniques

    def get_string_list(self) -> List[Dict]:
        """
        获取所有弦的列表。

        Returns:
            弦信息列表，每个包含char、string_number、note
        """
        strings = []
        for char, info in self._string_mapping.items():
            strings.append({
                'char': char,
                'string_number': info.get('string', 0),
                'note': info.get('note', '')
            })
        return strings

    def get_hui_list(self) -> List[Dict]:
        """
        获取所有徽位列表。

        Returns:
            徽位信息列表，每个包含char、position
        """
        hui_list = []
        for char, position in self._hui_mapping.items():
            hui_list.append({
                'char': char,
                'position': position
            })
        return hui_list

    def get_gongche_table(self) -> Dict[str, List[Dict]]:
        """
        获取完整的工尺谱对照表。

        Returns:
            包含gongche_notes、octave_markers、techniques、strings、hui_positions的字典
        """
        gongche_notes = []
        for note, info in self._gongche_mapping.items():
            gongche_notes.append({
                'note': note,
                'gongche': info['gongche'],
                'pinyin': info.get('pinyin', '')
            })
        
        octave_markers_list = [
            {'marker': self._octave_markers['low'], 'octave': 'low', 'description': '低八度'},
            {'marker': self._octave_markers['normal'], 'octave': 'normal', 'description': '正常八度'},
            {'marker': self._octave_markers['high'], 'octave': 'high', 'description': '高八度'}
        ]
        
        return {
            'gongche_notes': gongche_notes,
            'octave_markers': octave_markers_list,
            'techniques': self.get_technique_list(),
            'strings': self.get_string_list(),
            'hui_positions': self.get_hui_list()
        }

    def convert(self, jianzi: dict) -> Dict[str, Any]:
        """
        转换单个减字谱对象为工尺谱和说明。

        Args:
            jianzi: 减字谱对象

        Returns:
            包含gongche和description的字典
        """
        gongche = self.jianzi_to_gongche(jianzi)
        description = self.generate_description(jianzi)
        return {
            'jianzi': jianzi,
            'gongche': gongche,
            'description': description
        }

    def convert_batch(self, jianzi_list: List[dict]) -> List[Dict[str, Any]]:
        """
        批量转换减字谱列表为工尺谱。

        Args:
            jianzi_list: 减字谱对象列表

        Returns:
            工尺谱信息列表
        """
        return [self.convert(jz) for jz in jianzi_list]
