import os
import json
from typing import List, Dict, Tuple, Optional
from mido import MidiFile, MidiTrack, Message, MetaMessage, bpm2tempo


class MidiGenerator:
    """MIDI生成服务，将减字谱转换为标准MIDI文件。"""

    def __init__(self, ticks_per_beat: int = 480, default_program: int = 0):
        """
        初始化MIDI生成器。

        Args:
            ticks_per_beat: 每拍的tick数，默认480
            default_program: 默认音色编号，默认0（钢琴）
        """
        self.ticks_per_beat = ticks_per_beat
        self.default_program = default_program
        self._dictionary = self._load_dictionary()

        self._note_name_to_semitone = {
            'C': 0, 'C#': 1, 'Db': 1,
            'D': 2, 'D#': 3, 'Eb': 3,
            'E': 4, 'Fb': 4,
            'F': 5, 'F#': 6, 'Gb': 6,
            'G': 7, 'G#': 8, 'Ab': 8,
            'A': 9, 'A#': 10, 'Bb': 10,
            'B': 11, 'Cb': 11
        }

        self._technique_velocity = {
            'sanyin': 80,
            'anyin': 70,
            'fanyin': 60,
            'gou': 75,
            'ti': 72,
            'mo': 68,
            'tiao': 70,
            'tuo': 78,
            'bo': 76,
            'da': 65,
            'zhai': 62,
            'cuo': 85
        }

    def _load_dictionary(self) -> dict:
        """加载映射表字典。"""
        dict_path = os.path.join(os.path.dirname(__file__), 'dictionary.json')
        with open(dict_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def note_to_midi(self, note_name: str, octave: int) -> int:
        """
        将音名和八度转换为MIDI编号。

        Args:
            note_name: 音名（如"C"、"D#"、"Eb"等）
            octave: 八度编号（如4代表中央C所在的八度）

        Returns:
            MIDI编号（0-127）

        Raises:
            ValueError: 当音名无效时抛出
        """
        if note_name not in self._note_name_to_semitone:
            raise ValueError(f"无效的音名: {note_name}")

        semitone = self._note_name_to_semitone[note_name]
        midi_number = (octave + 1) * 12 + semitone

        if midi_number < 0 or midi_number > 127:
            raise ValueError(f"MIDI编号超出范围: {midi_number}")

        return midi_number

    def _get_velocity(self, technique: str) -> int:
        """根据技法获取力度值。"""
        return self._technique_velocity.get(technique, 70)

    def _duration_to_ticks(self, duration: float, tempo: float) -> int:
        """
        将持续时间（以拍为单位）转换为MIDI ticks。

        Args:
            duration: 持续时间（拍）
            tempo: 速度（拍/分钟）

        Returns:
            MIDI tick数
        """
        return int(duration * self.ticks_per_beat)

    def jianzi_to_midi_events(
        self,
        jianzi: dict,
        start_tick: int = 0,
        tempo: float = 60.0
    ) -> List[Tuple[int, Message]]:
        """
        将单个减字谱对象转换为MIDI事件列表。

        Args:
            jianzi: 减字谱对象，包含midi、technique、duration、string等字段
            start_tick: 起始tick时间
            tempo: 速度（拍/分钟）

        Returns:
            (tick, message) 元组列表，包含note_on和note_off事件
        """
        events = []

        midi_number = jianzi.get('midi', 60)
        technique = jianzi.get('technique', 'sanyin')
        duration = jianzi.get('duration', 1.0)
        velocity = jianzi.get('velocity', self._get_velocity(technique))
        channel = jianzi.get('channel', 0)

        duration_ticks = self._duration_to_ticks(duration, tempo)

        note_on = Message(
            'note_on',
            note=midi_number,
            velocity=velocity,
            time=0,
            channel=channel
        )
        events.append((start_tick, note_on))

        note_off = Message(
            'note_off',
            note=midi_number,
            velocity=64,
            time=0,
            channel=channel
        )
        events.append((start_tick + duration_ticks, note_off))

        if technique in ['chuo', 'zhu', 'shang', 'xia']:
            control_change = Message(
                'control_change',
                control=1,
                value=64,
                time=0,
                channel=channel
            )
            events.append((start_tick + duration_ticks // 2, control_change))

        if technique in ['yin', 'nao']:
            pitch_bend = Message(
                'pitchwheel',
                pitch=200,
                time=0,
                channel=channel
            )
            events.append((start_tick + duration_ticks // 4, pitch_bend))

            pitch_bend_reset = Message(
                'pitchwheel',
                pitch=0,
                time=0,
                channel=channel
            )
            events.append((start_tick + duration_ticks * 3 // 4, pitch_bend_reset))

        return events

    def _sort_events(self, events: List[Tuple[int, Message]]) -> List[Tuple[int, Message]]:
        """按时间排序MIDI事件。"""
        return sorted(events, key=lambda x: (x[0], x[1].type == 'note_off'))

    def _events_to_track(
        self,
        events: List[Tuple[int, Message]],
        track_name: str,
        program: Optional[int] = None
    ) -> MidiTrack:
        """
        将事件列表转换为MIDI轨道。

        Args:
            events: (tick, message) 元组列表
            track_name: 轨道名称
            program: 音色编号，如为None则使用默认值

        Returns:
            MidiTrack对象
        """
        track = MidiTrack()
        track.append(MetaMessage('track_name', name=track_name, time=0))

        if program is None:
            program = self.default_program

        track.append(Message('program_change', program=program, time=0, channel=0))

        sorted_events = self._sort_events(events)

        last_tick = 0
        for tick, message in sorted_events:
            delta_time = tick - last_tick
            msg = message.copy(time=delta_time)
            track.append(msg)
            last_tick = tick

        track.append(MetaMessage('end_of_track', time=0))
        return track

    def generate_midi(
        self,
        jianzi_list: List[dict],
        tempo: float = 60.0,
        output_path: Optional[str] = None,
        multi_track: bool = False
    ) -> MidiFile:
        """
        生成标准MIDI文件。

        Args:
            jianzi_list: 减字谱对象列表
            tempo: 速度（拍/分钟）
            output_path: 输出文件路径，如为None则不保存
            multi_track: 是否使用多轨道模式，按技法分组

        Returns:
            MidiFile对象
        """
        midi = MidiFile(ticks_per_beat=self.ticks_per_beat)

        tempo_track = MidiTrack()
        tempo_track.append(MetaMessage('track_name', name='Tempo Track', time=0))
        tempo_track.append(MetaMessage('set_tempo', tempo=bpm2tempo(tempo), time=0))
        tempo_track.append(MetaMessage('time_signature', numerator=4, denominator=4,
                                        clocks_per_click=24, notated_32nd_notes_per_beat=8, time=0))
        tempo_track.append(MetaMessage('key_signature', key='C', time=0))
        tempo_track.append(MetaMessage('end_of_track', time=0))
        midi.tracks.append(tempo_track)

        if multi_track:
            technique_groups: Dict[str, List[dict]] = {}
            for i, jianzi in enumerate(jianzi_list):
                technique = jianzi.get('technique', 'sanyin')
                if technique not in technique_groups:
                    technique_groups[technique] = []
                jianzi_with_index = dict(jianzi)
                jianzi_with_index['_index'] = i
                jianzi_with_index['channel'] = list(technique_groups.keys()).index(technique)
                technique_groups[technique].append(jianzi_with_index)

            for technique, group in technique_groups.items():
                all_events: List[Tuple[int, Message]] = []
                current_tick = 0

                for jianzi in group:
                    rest_before = jianzi.get('rest_before', 0.0)
                    if rest_before > 0:
                        current_tick += self._duration_to_ticks(rest_before, tempo)

                    events = self.jianzi_to_midi_events(jianzi, current_tick, tempo)
                    all_events.extend(events)

                    duration = jianzi.get('duration', 1.0)
                    current_tick += self._duration_to_ticks(duration, tempo)

                technique_info = self._dictionary['technique_mapping'].get(technique, {})
                track_name = technique_info.get('name', f'Track_{technique}')
                track = self._events_to_track(all_events, track_name)
                midi.tracks.append(track)
        else:
            all_events: List[Tuple[int, Message]] = []
            current_tick = 0

            for jianzi in jianzi_list:
                rest_before = jianzi.get('rest_before', 0.0)
                if rest_before > 0:
                    current_tick += self._duration_to_ticks(rest_before, tempo)

                events = self.jianzi_to_midi_events(jianzi, current_tick, tempo)
                all_events.extend(events)

                duration = jianzi.get('duration', 1.0)
                current_tick += self._duration_to_ticks(duration, tempo)

            track = self._events_to_track(all_events, 'Guqin Melody')
            midi.tracks.append(track)

        if output_path:
            midi.save(output_path)

        return midi

    def jianzi_list_to_timeline(
        self,
        jianzi_list: List[dict],
        tempo: float = 60.0
    ) -> List[Dict]:
        """
        将减字谱列表转换为时间线表示。

        Args:
            jianzi_list: 减字谱对象列表
            tempo: 速度（拍/分钟）

        Returns:
            时间线条目列表，每个条目包含start_time、end_time、midi、technique等
        """
        beat_duration = 60.0 / tempo
        timeline = []
        current_time = 0.0

        for jianzi in jianzi_list:
            rest_before = jianzi.get('rest_before', 0.0) * beat_duration
            if rest_before > 0:
                current_time += rest_before

            duration = jianzi.get('duration', 1.0) * beat_duration
            entry = {
                'start_time': current_time,
                'end_time': current_time + duration,
                'midi': jianzi.get('midi', 60),
                'technique': jianzi.get('technique', 'sanyin'),
                'string': jianzi.get('string', None),
                'velocity': jianzi.get('velocity', self._get_velocity(jianzi.get('technique', 'sanyin')))
            }
            timeline.append(entry)
            current_time += duration

        return timeline
