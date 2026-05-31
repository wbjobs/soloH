"""Unit tests for protocol reverse engineering toolkit."""

import unittest
import struct
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from protorev.ngram_analyzer import NGramAnalyzer
from protorev.sequence_alignment import NeedlemanWunsch
from protorev.type_inference import TypeInferrer
from protorev.relation_analyzer import RelationAnalyzer
from protorev.entropy_analyzer import EntropyAnalyzer
from protorev.analyzer import ProtocolAnalyzer


def generate_test_messages():
    """Generate test messages with known structure."""
    messages = []
    for i in range(10):
        header = struct.pack('<H B B H', 0x1234, 0x01, i % 4, i + 1)
        payload = bytes([j % 256 for j in range(8 + i * 2)])
        checksum = sum(header + payload) & 0xFFFF
        full = header + struct.pack('<H', checksum) + payload
        messages.append(full)
    return messages


class TestNGramAnalyzer(unittest.TestCase):
    """Test n-gram analysis module."""

    def test_extract_ngrams(self):
        analyzer = NGramAnalyzer()
        data = b'\x01\x02\x03\x04\x05'
        ngrams = analyzer.extract_ngrams(data, 2)
        self.assertEqual(len(ngrams), 4)
        self.assertEqual(ngrams[0], b'\x01\x02')

    def test_count_ngrams(self):
        analyzer = NGramAnalyzer()
        messages = [b'\x01\x02\x03', b'\x01\x02\x04']
        counts = analyzer.count_ngrams(messages, 2)
        self.assertIn(b'\x01\x02', counts)
        self.assertEqual(counts[b'\x01\x02'], 2)

    def test_detect_boundaries(self):
        analyzer = NGramAnalyzer()
        messages = generate_test_messages()
        boundaries = analyzer.detect_boundaries(messages, threshold=0.2)
        self.assertIsInstance(boundaries, list)


class TestSequenceAlignment(unittest.TestCase):
    """Test sequence alignment module."""

    def test_align_pair(self):
        nw = NeedlemanWunsch()
        seq1 = b'\x01\x02\x03\x04'
        seq2 = b'\x01\x02\xff\x03\x04'
        align1, align2, score = nw.align_pair(seq1, seq2)
        self.assertEqual(len(align1), len(align2))
        self.assertIsInstance(score, int)

    def test_progressive_alignment(self):
        nw = NeedlemanWunsch()
        messages = generate_test_messages()
        result = nw.progressive_alignment(messages)
        self.assertIsNotNone(result.aligned_sequences)
        self.assertIsNotNone(result.consensus)
        self.assertEqual(len(result.aligned_sequences), len(messages))

    def test_extract_fields(self):
        nw = NeedlemanWunsch()
        messages = generate_test_messages()
        alignment = nw.progressive_alignment(messages)
        fields = nw.extract_fields(alignment)
        self.assertIsInstance(fields, list)
        self.assertTrue(len(fields) > 0)


class TestTypeInference(unittest.TestCase):
    """Test type inference module."""

    def test_is_integer_candidate(self):
        inferrer = TypeInferrer()
        values = [struct.pack('<I', i) for i in range(10)]
        result = inferrer.is_integer_candidate(values)
        self.assertEqual(result.type_name, 'integer')
        self.assertGreater(result.confidence, 0.3)

    def test_is_timestamp_candidate(self):
        inferrer = TypeInferrer()
        import time
        base_ts = int(time.time())
        values = [struct.pack('<I', base_ts + i) for i in range(10)]
        result = inferrer.is_timestamp_candidate(values)
        self.assertEqual(result.type_name, 'timestamp')
        self.assertGreater(result.confidence, 0.3)

    def test_is_enum_candidate(self):
        inferrer = TypeInferrer()
        values = [bytes([i % 4]) for i in range(20)]
        result = inferrer.is_enum_candidate(values)
        self.assertEqual(result.type_name, 'enum')
        self.assertGreater(result.confidence, 0.5)

    def test_infer_field(self):
        inferrer = TypeInferrer()
        values = [struct.pack('<I', i) for i in range(10)]
        result = inferrer.infer_field(values)
        self.assertIsNotNone(result.best_type)


class TestRelationAnalyzer(unittest.TestCase):
    """Test relation analyzer module."""

    def test_detect_length_fields(self):
        analyzer = RelationAnalyzer()
        messages = generate_test_messages()
        relations = analyzer.detect_length_fields(messages)
        self.assertIsInstance(relations, list)

    def test_detect_checksum_fields(self):
        analyzer = RelationAnalyzer()
        messages = generate_test_messages()
        checksums = analyzer.detect_checksum_fields(messages)
        self.assertIsInstance(checksums, list)

    def test_additive_checksum(self):
        analyzer = RelationAnalyzer()
        data = b'\x01\x02\x03\x04'
        cs = analyzer._additive_checksum(data, 2)
        self.assertIsInstance(cs, int)
        self.assertEqual(cs, 0x000A)


class TestEntropyAnalyzer(unittest.TestCase):
    """Test entropy analyzer module."""

    def test_shannon_entropy(self):
        analyzer = EntropyAnalyzer()
        data = b'\x00' * 100
        entropy = analyzer.shannon_entropy(data)
        self.assertEqual(entropy, 0.0)

        data = bytes(range(256)) * 10
        entropy = analyzer.shannon_entropy(data)
        self.assertGreater(entropy, 7.0)

    def test_analyze_all_offsets(self):
        analyzer = EntropyAnalyzer()
        messages = generate_test_messages()
        results = analyzer.analyze_all_offsets(messages)
        self.assertIsInstance(results, list)
        self.assertTrue(len(results) > 0)

    def test_sliding_window(self):
        analyzer = EntropyAnalyzer(window_size=4)
        data = bytes(range(100))
        result = analyzer.sliding_window(data)
        self.assertIsInstance(result.entropies, list)
        self.assertEqual(len(result.positions), len(result.entropies))


class TestProtocolAnalyzer(unittest.TestCase):
    """Test main protocol analyzer."""

    def test_analyze_messages(self):
        analyzer = ProtocolAnalyzer(min_messages=5)
        messages = generate_test_messages()
        result = analyzer.analyze_messages(messages, protocol_name='TestProtocol')
        self.assertIsNotNone(result.protocol_desc)
        self.assertEqual(result.protocol_desc.protocol_name, 'TestProtocol')
        self.assertEqual(result.protocol_desc.messages_analyzed, len(messages))

    def test_save_results(self):
        analyzer = ProtocolAnalyzer(min_messages=5)
        messages = generate_test_messages()
        result = analyzer.analyze_messages(messages, protocol_name='TestProtocol')

        with tempfile.TemporaryDirectory() as tmpdir:
            output_prefix = os.path.join(tmpdir, 'test_output')
            saved = analyzer.save_results(result, output_prefix, formats=['json', 'xml'])
            self.assertEqual(len(saved), 2)
            self.assertTrue(os.path.exists(saved[0]))
            self.assertTrue(os.path.exists(saved[1]))


class TestBugFixes(unittest.TestCase):
    """Test cases for bug fixes."""

    def test_sequence_alignment_no_over_alignment(self):
        """Test that affine gap penalty prevents excessive gap insertion."""
        nw = NeedlemanWunsch()

        seq1 = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
        seq2 = bytes([0x01, 0x02, 0xFF, 0xFF, 0x05, 0x06, 0x07, 0x08])

        align1, align2, score = nw.align_pair(seq1, seq2)

        gap_count_1 = sum(1 for x in align1 if x == -1)
        gap_count_2 = sum(1 for x in align2 if x == -1)

        self.assertLessEqual(gap_count_1, 3, "Too many gaps in sequence 1 - over-alignment detected")
        self.assertLessEqual(gap_count_2, 3, "Too many gaps in sequence 2 - over-alignment detected")

        self.assertEqual(len(align1), len(align2))

        matches = sum(1 for a, b in zip(align1, align2) if a == b and a != -1)
        self.assertGreaterEqual(matches, 4, "Should preserve at least 4 matching bytes")

    def test_sequence_alignment_dissimilar_sequences(self):
        """Test that very dissimilar sequences don't get forced alignment."""
        nw = NeedlemanWunsch(gap_open=-5, gap_extend=-1)

        seq1 = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A])
        seq2 = bytes([0xAA, 0xBB, 0xCC, 0xDD, 0xAA, 0xBB, 0xCC, 0xDD, 0xAA, 0xBB, 0xCC, 0xDD])

        align1, align2, score = nw.align_pair(seq1, seq2)

        gap_count = sum(1 for a, b in zip(align1, align2) if a == -1 or b == -1)
        match_count = sum(1 for a, b in zip(align1, align2) if a == b and a != -1)

        self.assertLessEqual(match_count, 2, "Dissimilar sequences should have very few matches")
        self.assertEqual(len(align1), len(align2), "Aligned sequences should have equal length")
        self.assertEqual(len(align1), max(len(seq1), len(seq2)),
                        "With affine penalty, dissimilar seqs should be padded without excessive gaps")

    def test_length_field_no_self_reference(self):
        """Test that length field detection doesn't create self-referencing relations."""
        analyzer = RelationAnalyzer()

        messages = []
        for i in range(10):
            payload_len = 16 + (i % 5) * 4
            payload = bytes([j & 0xFF for j in range(payload_len)])
            length = len(payload)
            header = struct.pack('<HH', 0x1234, length)
            msg = header + payload
            messages.append(msg)

        relations = analyzer.detect_length_fields(messages)

        for rel in relations:
            length_field_end = rel.length_offset + rel.length_length
            self.assertFalse(
                rel.target_offset >= rel.length_offset and rel.target_offset < length_field_end,
                f"Self-referencing length field detected: length_offset={rel.length_offset}, target_offset={rel.target_offset}"
            )

        valid_relations = [r for r in relations if r.confidence >= 0.5]
        self.assertTrue(len(valid_relations) >= 1, "Should detect at least one valid length relation")

    def test_length_field_negative_values_rejected(self):
        """Test that negative length values are not considered valid."""
        analyzer = RelationAnalyzer()

        messages = []
        for i in range(5):
            payload = bytes([0x00] * 8)
            length_bytes = struct.pack('<h', -1)
            msg = length_bytes + payload
            messages.append(msg)

        relations = analyzer.detect_length_fields(messages)
        for rel in relations:
            self.assertLess(rel.confidence, 0.5, "Negative length values should have low confidence")

    def test_endianness_detection_big_endian(self):
        """Test that big-endian integers are correctly identified."""
        inferrer = TypeInferrer(endianness='auto')

        big_endian_values = []
        for i in range(1, 11):
            value = i * 100
            big_endian_values.append(value.to_bytes(4, byteorder='big', signed=False))

        result = inferrer.is_integer_candidate(big_endian_values)

        self.assertEqual(result.type_name, 'integer')
        self.assertGreaterEqual(result.confidence, 0.5, "Should detect integer with good confidence")

        if 'endianness' in result.details:
            self.assertEqual(result.details['endianness'], 'big', "Should detect big-endian encoding")

        self.assertGreater(
            result.details.get('big_endian_score', 0),
            result.details.get('little_endian_score', 0),
            "Big-endian score should be higher than little-endian score"
        )

    def test_endianness_detection_little_endian(self):
        """Test that little-endian integers are correctly identified."""
        inferrer = TypeInferrer(endianness='auto')

        little_endian_values = []
        for i in range(1, 11):
            value = i * 100
            little_endian_values.append(value.to_bytes(4, byteorder='little', signed=False))

        result = inferrer.is_integer_candidate(little_endian_values)

        self.assertEqual(result.type_name, 'integer')
        self.assertGreaterEqual(result.confidence, 0.5, "Should detect integer with good confidence")

        if 'endianness' in result.details:
            self.assertEqual(result.details['endianness'], 'little', "Should detect little-endian encoding")

    def test_endianness_detection_with_incrementing_values(self):
        """Test endianness detection with incrementing sequence numbers."""
        inferrer = TypeInferrer(endianness='auto')

        big_endian_seq = []
        for i in range(1, 20):
            big_endian_seq.append(i.to_bytes(2, byteorder='big', signed=False))

        result = inferrer.is_integer_candidate(big_endian_seq)

        self.assertGreaterEqual(
            result.details.get('big_endian_score', 0),
            result.details.get('little_endian_score', 0),
            "Incrementing big-endian sequence should have big-endian score >= little-endian score"
        )
        self.assertEqual(result.details.get('endianness'), 'big',
                         "Should detect big-endian encoding")

        little_endian_seq = []
        for i in range(1, 20):
            little_endian_seq.append(i.to_bytes(2, byteorder='little', signed=False))

        result2 = inferrer.is_integer_candidate(little_endian_seq)
        self.assertEqual(result2.details.get('endianness'), 'little')

    def test_endianness_with_extreme_values(self):
        """Test that extreme values from wrong endianness are penalized."""
        inferrer = TypeInferrer(endianness='auto')

        values = []
        for i in range(5):
            values.append((0x00010000 + i).to_bytes(4, byteorder='big', signed=False))

        result = inferrer.is_integer_candidate(values)

        self.assertEqual(result.details.get('endianness'), 'big')

        little_values = [struct.unpack('<I', v)[0] for v in values]
        big_values = [struct.unpack('>I', v)[0] for v in values]

        self.assertGreater(max(little_values), max(big_values) * 100,
                          "Little-endian interpretation should produce much larger values")


class TestStateMachine(unittest.TestCase):
    """Test state machine inference module."""

    def test_state_machine_import(self):
        """Test that state_machine module can be imported."""
        from protorev.state_machine import StateMachineInferrer, StateMachine
        self.assertIsNotNone(StateMachineInferrer)
        self.assertIsNotNone(StateMachine)

    def test_message_clustering(self):
        """Test message clustering for state machine inference."""
        from protorev.state_machine import StateMachineInferrer

        inferrer = StateMachineInferrer(signature_length=4)
        messages = [
            b'\x01\x00\x00\x00' + bytes(range(10)),
            b'\x01\x00\x00\x01' + bytes(range(10)),
            b'\x02\x00\x00\x00' + bytes(range(10)),
            b'\x02\x00\x00\x01' + bytes(range(10)),
            b'\x01\x00\x00\x02' + bytes(range(10)),
        ]

        result = inferrer.infer(messages)
        self.assertIsNotNone(result)
        self.assertGreater(len(result.states), 0)
        self.assertGreater(len(result.transitions), 0)

    def test_state_machine_dot_export(self):
        """Test DOT format export of state machine."""
        from protorev.state_machine import StateMachineInferrer

        inferrer = StateMachineInferrer()
        messages = [
            b'\x01' + bytes(range(8)),
            b'\x02' + bytes(range(8)),
            b'\x01' + bytes(range(8)),
            b'\x03' + bytes(range(8)),
        ]

        result = inferrer.infer(messages)
        dot = result.to_dot()

        self.assertIn('digraph', dot)
        self.assertIn('->', dot)

    def test_different_clustering_algorithms(self):
        """Test different clustering algorithms."""
        from protorev.state_machine import StateMachineInferrer

        messages = [
            b'\x01\x02\x03' + bytes(range(5)),
            b'\x01\x02\x04' + bytes(range(5)),
            b'\x04\x05\x06' + bytes(range(5)),
        ]

        for algo in ['prefix', 'similarity', 'length', 'type']:
            inferrer = StateMachineInferrer(cluster_algorithm=algo)
            result = inferrer.infer(messages)
            self.assertIsNotNone(result)
            self.assertGreater(len(result.states), 0)

    def test_cycle_detection(self):
        """Test cycle detection in state machine."""
        from protorev.state_machine import StateMachineInferrer

        inferrer = StateMachineInferrer()
        messages = [
            b'\x01' + bytes(range(4)),
            b'\x02' + bytes(range(4)),
            b'\x01' + bytes(range(4)),
            b'\x02' + bytes(range(4)),
        ]

        result = inferrer.infer(messages)
        cycles = result.detect_cycles()
        self.assertIsInstance(cycles, list)

    def test_anomaly_detection(self):
        """Test anomaly detection in state machine."""
        from protorev.state_machine import StateMachineInferrer

        inferrer = StateMachineInferrer()
        messages = [
            b'\x01' + bytes(range(4)),
            b'\x02' + bytes(range(4)),
            b'\x03' + bytes(range(4)),
            b'\x01' + bytes(range(4)),
            b'\x99' + bytes(range(4)),
        ]

        result = inferrer.infer(messages)
        anomalies = result.detect_anomalies()
        self.assertIsInstance(anomalies, list)


class TestCryptoDetector(unittest.TestCase):
    """Test cryptographic protocol detection module."""

    def test_crypto_detector_import(self):
        """Test that crypto_detector module can be imported."""
        from protorev.crypto_detector import CryptoDetector, CryptoDetectionResult
        self.assertIsNotNone(CryptoDetector)
        self.assertIsNotNone(CryptoDetectionResult)

    def test_entropy_calculation(self):
        """Test Shannon entropy calculation."""
        from protorev.crypto_detector import CryptoDetector

        detector = CryptoDetector()
        low_entropy_data = b'AAAAA' * 100
        high_entropy_data = bytes(range(256)) * 4

        low_entropy = detector._calculate_entropy(low_entropy_data)
        high_entropy = detector._calculate_entropy(high_entropy_data)

        self.assertLess(low_entropy, 1.0)
        self.assertGreater(high_entropy, 7.0)

    def test_encrypted_data_detection(self):
        """Test detection of encrypted-like data."""
        from protorev.crypto_detector import CryptoDetector
        import os

        detector = CryptoDetector()
        encrypted_like = os.urandom(1024)
        plaintext = b'Hello, World! ' * 100

        result_encrypted = detector.detect([encrypted_like])
        result_plain = detector.detect([plaintext])

        self.assertGreaterEqual(result_encrypted.confidence, 0.3)
        self.assertLess(result_plain.confidence, result_encrypted.confidence)

    def test_chi_square_test(self):
        """Test chi-square randomness test."""
        from protorev.crypto_detector import CryptoDetector
        import os

        detector = CryptoDetector()
        random_data = os.urandom(256)
        uniform_data = bytes(range(256))

        chi_random = detector._chi_square_test(random_data)
        chi_uniform = detector._chi_square_test(uniform_data)

        self.assertIn('passed', chi_random)
        self.assertIn('score', chi_random)

    def test_runs_test(self):
        """Test runs test for randomness."""
        from protorev.crypto_detector import CryptoDetector
        import os

        detector = CryptoDetector()
        random_data = os.urandom(256)
        pattern_data = b'\x00\xFF' * 128

        runs_random = detector._runs_test(random_data)
        runs_pattern = detector._runs_test(pattern_data)

        self.assertIn('passed', runs_random)
        self.assertIn('score', runs_random)

    def test_autocorrelation_test(self):
        """Test autocorrelation test for randomness."""
        from protorev.crypto_detector import CryptoDetector
        import os

        detector = CryptoDetector()
        random_data = os.urandom(256)

        autocorr = detector._autocorrelation_test(random_data)
        self.assertIn('passed', autocorr)
        self.assertIn('score', autocorr)

    def test_block_entropy_analysis(self):
        """Test block-based entropy analysis."""
        from protorev.crypto_detector import CryptoDetector
        import os

        detector = CryptoDetector()
        data = os.urandom(512)

        block_entropy = detector._block_entropy_analysis(data)
        self.assertIsInstance(block_entropy, list)
        self.assertGreater(len(block_entropy), 0)

    def test_high_entropy_region_detection(self):
        """Test detection of high entropy regions."""
        from protorev.crypto_detector import CryptoDetector
        import os

        detector = CryptoDetector()
        mixed_data = b'Header' + os.urandom(256) + b'Footer'

        result = detector.detect([mixed_data])
        self.assertIsInstance(result.high_entropy_regions, list)


class TestWiresharkDissector(unittest.TestCase):
    """Test Wireshark Lua dissector generator."""

    def test_dissector_import(self):
        """Test that wireshark_dissector module can be imported."""
        from protorev.wireshark_dissector import LuaDissectorGenerator
        self.assertIsNotNone(LuaDissectorGenerator)

    def test_get_uint_type(self):
        """Test uint type selection based on length."""
        from protorev.wireshark_dissector import LuaDissectorGenerator

        gen = LuaDissectorGenerator()
        self.assertEqual(gen._get_uint_type(1), 'uint8')
        self.assertEqual(gen._get_uint_type(2), 'uint16')
        self.assertEqual(gen._get_uint_type(4), 'uint32')
        self.assertEqual(gen._get_uint_type(8), 'uint64')
        self.assertEqual(gen._get_uint_type(3), 'bytes')

    def test_generate_dissector_code(self):
        """Test generation of Lua dissector code."""
        from protorev.wireshark_dissector import LuaDissectorGenerator

        gen = LuaDissectorGenerator(protocol_name='TestProto')

        protocol_desc = {
            'description': 'Test Protocol',
            'fields': [
                {
                    'name': 'header',
                    'offset': 0,
                    'length': 4,
                    'field_type': 'fixed',
                    'inferred_type': 'integer',
                    'confidence': 0.9,
                    'is_fixed': True,
                },
                {
                    'name': 'length',
                    'offset': 4,
                    'length': 2,
                    'field_type': 'variable',
                    'inferred_type': 'integer',
                    'confidence': 0.85,
                    'is_length_field': True,
                },
                {
                    'name': 'checksum',
                    'offset': 6,
                    'length': 2,
                    'field_type': 'variable',
                    'inferred_type': 'integer',
                    'confidence': 0.75,
                    'is_checksum': True,
                    'checksum_type': 'CRC16',
                },
            ],
        }

        lua_code = gen.generate(protocol_desc)
        self.assertIn('Proto("testproto"', lua_code)
        self.assertIn('ProtoField.uint32', lua_code)
        self.assertIn('dissector', lua_code)
        self.assertIn('heur_dissect', lua_code)

    def test_generate_dissector_with_output_file(self):
        """Test generation of dissector with file output."""
        from protorev.wireshark_dissector import LuaDissectorGenerator
        import tempfile

        gen = LuaDissectorGenerator('TestProtocol')

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, 'test_dissector.lua')
            protocol_desc = {'fields': []}

            lua_code = gen.generate(protocol_desc, output_path)
            self.assertTrue(os.path.exists(output_path))

            with open(output_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.assertEqual(content, lua_code)

    def test_quick_start_package(self):
        """Test quick start package generation."""
        from protorev.wireshark_dissector import LuaDissectorGenerator
        import tempfile

        gen = LuaDissectorGenerator('QuickTest')

        with tempfile.TemporaryDirectory() as tmpdir:
            files = gen.generate_quick_start('QuickTest', tmpdir)

            self.assertIn('lua', files)
            self.assertIn('readme', files)
            self.assertTrue(os.path.exists(files['lua']))
            self.assertTrue(os.path.exists(files['readme']))


class TestIntegrationNewFeatures(unittest.TestCase):
    """Integration tests for new features with the main analyzer."""

    def test_analyzer_with_state_machine(self):
        """Test that analyzer runs with state machine enabled."""
        analyzer = ProtocolAnalyzer(enable_state_machine=True)
        messages = generate_test_messages()

        result = analyzer.analyze_messages(messages, 'TestProtocol')
        self.assertIsNotNone(result.state_machine)
        self.assertGreater(len(result.state_machine.states), 0)

    def test_analyzer_with_crypto_detection(self):
        """Test that analyzer runs with crypto detection enabled."""
        analyzer = ProtocolAnalyzer(enable_crypto_detection=True)
        messages = generate_test_messages()

        result = analyzer.analyze_messages(messages, 'TestProtocol')
        self.assertIsNotNone(result.crypto_result)

    def test_analyzer_disable_features(self):
        """Test disabling new features."""
        analyzer = ProtocolAnalyzer(
            enable_state_machine=False,
            enable_crypto_detection=False
        )
        messages = generate_test_messages()

        result = analyzer.analyze_messages(messages, 'TestProtocol')
        self.assertIsNone(result.state_machine)
        self.assertIsNone(result.crypto_result)

    def test_save_dot_format(self):
        """Test saving state machine in DOT format."""
        analyzer = ProtocolAnalyzer(enable_state_machine=True)
        messages = generate_test_messages()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_prefix = os.path.join(tmpdir, 'test_output')
            result = analyzer.analyze_messages(messages, 'TestProtocol')

            saved = analyzer.save_results(result, output_prefix, formats=['dot'])
            self.assertEqual(len(saved), 1)
            self.assertTrue(saved[0].endswith('.dot'))

    def test_save_lua_dissector(self):
        """Test saving Wireshark Lua dissector."""
        analyzer = ProtocolAnalyzer()
        messages = generate_test_messages()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_prefix = os.path.join(tmpdir, 'test_output')
            result = analyzer.analyze_messages(messages, 'TestProtocol')

            saved = analyzer.save_results(result, output_prefix, formats=['lua'])
            self.assertEqual(len(saved), 1)
            self.assertTrue(saved[0].endswith('.lua'))

            with open(saved[0], 'r', encoding='utf-8') as f:
                content = f.read()
            self.assertIn('Proto(', content)

    def test_save_crypto_report(self):
        """Test saving crypto analysis report."""
        analyzer = ProtocolAnalyzer(enable_crypto_detection=True)
        messages = generate_test_messages()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_prefix = os.path.join(tmpdir, 'test_output')
            result = analyzer.analyze_messages(messages, 'TestProtocol')

            saved = analyzer.save_results(result, output_prefix, formats=['crypto'])
            self.assertEqual(len(saved), 1)
            self.assertTrue(saved[0].endswith('.txt'))

    def test_full_integration_all_formats(self):
        """Test full integration with all new formats."""
        analyzer = ProtocolAnalyzer()
        messages = generate_test_messages()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_prefix = os.path.join(tmpdir, 'full_test')
            result = analyzer.analyze_messages(messages, 'FullTest')

            formats = ['json', 'xml', 'html', 'dot', 'lua', 'crypto']
            saved = analyzer.save_results(result, output_prefix, formats=formats)

            self.assertEqual(len(saved), 6)
            for f in saved:
                self.assertTrue(os.path.exists(f))

    def test_summary_includes_new_features(self):
        """Test that print_summary includes new feature info."""
        import io
        import contextlib

        analyzer = ProtocolAnalyzer()
        messages = generate_test_messages()
        result = analyzer.analyze_messages(messages, 'SummaryTest')

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            analyzer.print_summary(result)

        summary_text = output.getvalue()
        self.assertIn('State Machine Analysis', summary_text)
        self.assertIn('Cryptographic Analysis', summary_text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
