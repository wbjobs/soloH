"""Main protocol analysis orchestrator."""

from typing import List, Dict, Optional
from dataclasses import dataclass, field
import os

from .pcap_reader import PcapReader, Message
from .ngram_analyzer import NGramAnalyzer, FieldBoundary
from .sequence_alignment import NeedlemanWunsch, AlignmentResult, Field
from .type_inference import TypeInferrer, InferredField
from .relation_analyzer import RelationAnalyzer, LengthRelation, ChecksumCandidate
from .entropy_analyzer import EntropyAnalyzer
from .protocol_output import ProtocolDescription, ProtocolField, ProtocolOutputGenerator
from .html_report import HTMLReportGenerator
from .state_machine import StateMachineInferrer, StateMachine
from .crypto_detector import CryptoDetector, CryptoDetectionResult
from .wireshark_dissector import LuaDissectorGenerator


@dataclass
class AnalysisResult:
    """Complete analysis result."""
    protocol_desc: ProtocolDescription
    alignment_result: Optional[AlignmentResult] = None
    ngram_boundaries: List[FieldBoundary] = field(default_factory=list)
    length_relations: List[LengthRelation] = field(default_factory=list)
    checksum_candidates: List[ChecksumCandidate] = field(default_factory=list)
    sequence_candidates: List[Dict] = field(default_factory=list)
    entropy_data: Dict = field(default_factory=dict)
    inferred_fields: Dict[int, InferredField] = field(default_factory=dict)
    messages: List[bytes] = field(default_factory=list)
    heatmap_data: Dict = field(default_factory=dict)
    state_machine: Optional[StateMachine] = None
    crypto_result: Optional[CryptoDetectionResult] = None


class ProtocolAnalyzer:
    """Main protocol analysis orchestrator."""

    def __init__(self, endianness: str = 'auto', min_messages: int = 3,
                 enable_state_machine: bool = True,
                 enable_crypto_detection: bool = True):
        self.endianness = endianness
        self.min_messages = min_messages
        self.enable_state_machine = enable_state_machine
        self.enable_crypto_detection = enable_crypto_detection

        self.pcap_reader: Optional[PcapReader] = None
        self.ngram_analyzer = NGramAnalyzer()
        self.alignment = NeedlemanWunsch()
        self.type_inferrer = TypeInferrer(endianness)
        self.relation_analyzer = RelationAnalyzer(endianness)
        self.entropy_analyzer = EntropyAnalyzer()
        self.state_machine_inferrer = StateMachineInferrer()
        self.crypto_detector = CryptoDetector()

    def analyze_pcap(self, pcap_file: str, protocol_name: str = "unknown") -> AnalysisResult:
        """Analyze a PCAP file to reverse engineer the protocol."""
        if not os.path.exists(pcap_file):
            raise FileNotFoundError(f"PCAP file not found: {pcap_file}")

        self.pcap_reader = PcapReader(pcap_file)
        messages = self.pcap_reader.get_all_payloads()

        if len(messages) < self.min_messages:
            print(f"Warning: Only {len(messages)} messages found. At least {self.min_messages} recommended for reliable analysis.")

        return self.analyze_messages(messages, protocol_name)

    def analyze_messages(self, messages: List[bytes], protocol_name: str = "unknown") -> AnalysisResult:
        """Analyze a list of message payloads."""
        if not messages:
            raise ValueError("No messages to analyze")

        print(f"[*] Analyzing {len(messages)} messages...")

        print("[1/8] Performing n-gram boundary detection...")
        boundaries = self.ngram_analyzer.detect_boundaries(messages)

        print("[2/8] Performing multi-sequence alignment...")
        alignment_result = self.alignment.progressive_alignment(messages)
        fields = self.alignment.extract_fields(alignment_result)
        fields = self.alignment.merge_fields(fields)

        print("[3/8] Performing type inference...")
        field_values: Dict[int, List[bytes]] = {}
        for f in fields:
            values = []
            for seq in alignment_result.aligned_sequences:
                if f.offset + f.length <= len(seq):
                    field_bytes = bytes([b for b in seq[f.offset:f.offset + f.length] if b != -1])
                    if len(field_bytes) == f.length:
                        values.append(field_bytes)
            if values:
                field_values[f.offset] = values

        inferred_fields = self.type_inferrer.infer_fields(field_values)

        print("[4/8] Analyzing field relationships...")
        length_relations = self.relation_analyzer.detect_length_fields(messages)
        checksum_candidates = self.relation_analyzer.detect_checksum_fields(messages)
        sequence_candidates = self.relation_analyzer.detect_sequence_numbers(messages)

        print("[5/8] Performing entropy analysis...")
        entropy_data = self.entropy_analyzer.analyze_messages(messages)
        heatmap_data = self.entropy_analyzer.get_entropy_heatmap(messages)

        state_machine = None
        if self.enable_state_machine and len(messages) >= 3:
            print("[6/8] Inferring state machine...")
            state_machine = self.state_machine_inferrer.infer(messages)

        crypto_result = None
        if self.enable_crypto_detection:
            print("[7/8] Detecting cryptographic patterns...")
            crypto_result = self.crypto_detector.detect(messages)

        print("[8/8] Building protocol description...")
        protocol_desc = self._build_protocol_description(
            messages, fields, inferred_fields, alignment_result,
            length_relations, checksum_candidates, sequence_candidates,
            entropy_data, protocol_name
        )

        result = AnalysisResult(
            protocol_desc=protocol_desc,
            alignment_result=alignment_result,
            ngram_boundaries=boundaries,
            length_relations=length_relations,
            checksum_candidates=checksum_candidates,
            sequence_candidates=sequence_candidates,
            entropy_data=entropy_data,
            inferred_fields=inferred_fields,
            messages=messages,
            heatmap_data=heatmap_data,
            state_machine=state_machine,
            crypto_result=crypto_result
        )

        print("[✓] Analysis complete!")
        return result

    def _build_protocol_description(
        self,
        messages: List[bytes],
        fields: List[Field],
        inferred_fields: Dict[int, InferredField],
        alignment_result: AlignmentResult,
        length_relations: List[LengthRelation],
        checksum_candidates: List[ChecksumCandidate],
        sequence_candidates: List[Dict],
        entropy_data: Dict,
        protocol_name: str
    ) -> ProtocolDescription:
        """Build complete protocol description."""
        protocol_fields = []

        checksum_offsets = {(c.offset, c.length): (c.checksum_type, c.confidence) for c in checksum_candidates}
        length_offsets = {(r.length_offset, r.length_length): r for r in length_relations}

        for field in fields:
            inferred = inferred_fields.get(field.offset)

            pf = ProtocolField(
                name=field.name,
                offset=field.offset,
                length=field.length,
                field_type=field.field_type,
                is_fixed=field.is_fixed,
                inferred_type=inferred.best_type if inferred else "unknown",
                confidence=field.confidence,
                description=field.description,
                sample_values=[v.hex() for v in field.values[:10]],
                enum_values=inferred.enum_values if inferred and inferred.is_enum else {}
            )

            if (field.offset, field.length) in checksum_offsets:
                cs_type, cs_conf = checksum_offsets[(field.offset, field.length)]
                pf.is_checksum = True
                pf.checksum_type = cs_type
                pf.confidence = max(pf.confidence, cs_conf)

            if (field.offset, field.length) in length_offsets:
                rel = length_offsets[(field.offset, field.length)]
                pf.is_length_field = True
                pf.points_to_offset = rel.target_offset
                pf.confidence = max(pf.confidence, rel.confidence)

            protocol_fields.append(pf)

        consensus_bytes = bytes([b for b in alignment_result.consensus if b != -1])
        consensus_header = consensus_bytes.hex(' ')

        avg_length = sum(len(m) for m in messages) / len(messages)

        unique_lengths = len(set(len(m) for m in messages))
        min_length = min(len(m) for m in messages)
        max_length = max(len(m) for m in messages)

        total_fixed = sum(1 for f in protocol_fields if f.is_fixed)
        total_variable = len(protocol_fields) - total_fixed

        protocol_desc = ProtocolDescription(
            protocol_name=protocol_name,
            description=f"Reverse engineered protocol from {len(messages)} messages",
            messages_analyzed=len(messages),
            average_message_length=avg_length,
            endianness=self.endianness,
            fields=protocol_fields,
            consensus_header=consensus_header,
            length_relations=[
                {
                    'length_offset': r.length_offset,
                    'length_length': r.length_length,
                    'target_offset': r.target_offset,
                    'confidence': r.confidence,
                    'matches': r.matches,
                    'total': r.total,
                    'endianness': r.endianness
                }
                for r in length_relations
            ],
            checksum_candidates=[
                {
                    'offset': c.offset,
                    'length': c.length,
                    'checksum_type': c.checksum_type,
                    'confidence': c.confidence,
                    'matches': c.matches,
                    'total': c.total,
                    'covered_range': list(c.covered_range)
                }
                for c in checksum_candidates
            ],
            sequence_candidates=sequence_candidates,
            entropy_data=entropy_data,
            statistics={
                'total_messages': len(messages),
                'unique_lengths': unique_lengths,
                'min_length': min_length,
                'max_length': max_length,
                'avg_length': avg_length,
                'total_fields': len(protocol_fields),
                'fixed_fields': total_fixed,
                'variable_fields': total_variable,
                'avg_entropy': entropy_data.get('average_entropy', 0),
                'std_entropy': entropy_data.get('std_entropy', 0)
            }
        )

        return protocol_desc

    def save_results(self, result: AnalysisResult, output_prefix: str,
                     formats: Optional[List[str]] = None) -> List[str]:
        """Save analysis results in specified formats."""
        if formats is None:
            formats = ['json', 'xml', 'html']

        output_dir = os.path.dirname(output_prefix)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        saved_files = []
        output_gen = ProtocolOutputGenerator(result.protocol_desc)

        if 'json' in formats:
            json_path = f"{output_prefix}.json"
            output_gen.save_json(json_path)
            saved_files.append(json_path)
            print(f"[+] JSON protocol description saved to {json_path}")

        if 'xml' in formats:
            xml_path = f"{output_prefix}.xml"
            output_gen.save_xml(xml_path)
            saved_files.append(xml_path)
            print(f"[+] XML protocol description saved to {xml_path}")

        if 'html' in formats:
            html_path = f"{output_prefix}.html"
            html_gen = HTMLReportGenerator()
            conservation_scores = result.alignment_result.conservation_scores if result.alignment_result else []
            html_content = html_gen.generate_report(
                result.protocol_desc.to_dict(),
                result.messages,
                conservation_scores,
                result.heatmap_data
            )
            html_gen.save_report(html_content, html_path)
            saved_files.append(html_path)
            print(f"[+] HTML report saved to {html_path}")

        if 'dot' in formats and result.state_machine:
            dot_path = f"{output_prefix}_state_machine.dot"
            with open(dot_path, 'w', encoding='utf-8') as f:
                f.write(result.state_machine.to_dot())
            saved_files.append(dot_path)
            print(f"[+] State machine DOT file saved to {dot_path}")

        if 'lua' in formats:
            lua_path = f"{output_prefix}_dissector.lua"
            dissector_gen = LuaDissectorGenerator(result.protocol_desc.protocol_name)
            dissector_gen.generate(result.protocol_desc.to_dict(), lua_path)
            saved_files.append(lua_path)

        if 'crypto' in formats and result.crypto_result:
            crypto_path = f"{output_prefix}_crypto_analysis.txt"
            with open(crypto_path, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write("CRYPTOGRAPHIC ANALYSIS REPORT\n")
                f.write("=" * 60 + "\n\n")
                cr = result.crypto_result
                f.write(f"Is encrypted: {cr.is_encrypted}\n")
                f.write(f"Overall confidence: {cr.confidence:.2%}\n")
                f.write(f"Likely algorithm: {cr.likely_algorithm}\n\n")

                f.write("Randomness Test Results:\n")
                f.write("-" * 40 + "\n")
                for test_name, res in cr.test_results.items():
                    passed = "PASS" if res.get('passed', False) else "FAIL"
                    score = res.get('score', 0)
                    f.write(f"  {test_name:25s} [{passed}] score={score:.3f}\n")

                f.write(f"\nAverage entropy: {cr.avg_entropy:.4f}\n")
                f.write(f"Entropy standard deviation: {cr.entropy_std:.4f}\n")
                f.write(f"High entropy regions: {len(cr.high_entropy_regions)}\n")

                if cr.likely_algorithm_details:
                    f.write(f"\nAlgorithm guess details:\n")
                    for key, val in cr.likely_algorithm_details.items():
                        f.write(f"  {key}: {val}\n")
            saved_files.append(crypto_path)
            print(f"[+] Crypto analysis report saved to {crypto_path}")

        return saved_files

    def print_summary(self, result: AnalysisResult) -> None:
        """Print analysis summary to console."""
        desc = result.protocol_desc
        stats = desc.statistics

        print("\n" + "=" * 60)
        print("PROTOCOL ANALYSIS SUMMARY")
        print("=" * 60)
        print(f"Protocol: {desc.protocol_name}")
        print(f"Messages analyzed: {stats.get('total_messages', 0)}")
        print(f"Message length range: {stats.get('min_length', 0)} - {stats.get('max_length', 0)} bytes")
        print(f"Average length: {stats.get('avg_length', 0):.1f} bytes")
        print(f"\nFields detected: {stats.get('total_fields', 0)}")
        print(f"  - Fixed fields: {stats.get('fixed_fields', 0)}")
        print(f"  - Variable fields: {stats.get('variable_fields', 0)}")
        print(f"\nAverage entropy: {stats.get('avg_entropy', 0):.2f}")
        print(f"Entropy std dev: {stats.get('std_entropy', 0):.2f}")

        if desc.consensus_header:
            print(f"\nConsensus header (first 32 bytes):")
            print(f"  {desc.consensus_header[:96]}")

        if result.checksum_candidates:
            print(f"\nChecksum candidates: {len(result.checksum_candidates)}")
            for cs in result.checksum_candidates[:3]:
                print(f"  - Offset 0x{cs.offset:04X}, Length {cs.length}, Type: {cs.checksum_type}, Confidence: {cs.confidence:.1%}")

        if result.length_relations:
            print(f"\nLength field relations: {len(result.length_relations)}")
            for rel in result.length_relations[:3]:
                print(f"  - Length at 0x{rel.length_offset:04X} -> Data at 0x{rel.target_offset:04X}, Confidence: {rel.confidence:.1%}")

        if result.state_machine:
            sm = result.state_machine
            print(f"\nState Machine Analysis:")
            print(f"  - States detected: {len(sm.states)}")
            print(f"  - Transitions: {len(sm.transitions)}")
            print(f"  - Clustering algorithm: {sm.cluster_algorithm}")
            if sm.anomalies:
                print(f"  - Anomalies detected: {len(sm.anomalies)}")

        if result.crypto_result:
            cr = result.crypto_result
            print(f"\nCryptographic Analysis:")
            print(f"  - Encrypted: {cr.is_encrypted}")
            print(f"  - Confidence: {cr.confidence:.1%}")
            print(f"  - Likely algorithm: {cr.likely_algorithm}")
            print(f"  - Average entropy: {cr.avg_entropy:.3f}")

        print("\n" + "=" * 60)
        print("FIELDS:")
        print("-" * 60)
        for field in desc.fields:
            tags = []
            if field.is_checksum:
                tags.append("CHECKSUM")
            if field.is_length_field:
                tags.append("LENGTH")
            tag_str = f" [{', '.join(tags)}]" if tags else ""

            print(f"\n  {field.name} (offset=0x{field.offset:04X}, length={field.length})")
            print(f"    Type: {field.field_type.upper()} | Inferred: {field.inferred_type.upper()}")
            print(f"    Confidence: {field.confidence:.1%}{tag_str}")
            if field.sample_values:
                print(f"    Samples: {', '.join(field.sample_values[:3])}")

        print("\n" + "=" * 60)
