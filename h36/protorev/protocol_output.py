"""Protocol description output (XML/JSON) generation."""

import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime


@dataclass
class ProtocolField:
    """Protocol field description."""
    name: str
    offset: int
    length: int
    field_type: str
    is_fixed: bool
    inferred_type: str = "unknown"
    confidence: float = 0.0
    description: str = ""
    sample_values: List[str] = field(default_factory=list)
    enum_values: Dict[str, int] = field(default_factory=dict)
    is_checksum: bool = False
    checksum_type: str = ""
    is_length_field: bool = False
    points_to_offset: int = -1

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'offset': self.offset,
            'length': self.length,
            'field_type': self.field_type,
            'is_fixed': self.is_fixed,
            'inferred_type': self.inferred_type,
            'confidence': self.confidence,
            'description': self.description,
            'sample_values': self.sample_values[:5],
            'enum_values': self.enum_values,
            'is_checksum': self.is_checksum,
            'checksum_type': self.checksum_type,
            'is_length_field': self.is_length_field,
            'points_to_offset': self.points_to_offset
        }


@dataclass
class ProtocolDescription:
    """Complete protocol description."""
    protocol_name: str = "unknown"
    version: str = "1.0"
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    messages_analyzed: int = 0
    average_message_length: float = 0.0
    endianness: str = "auto"
    fields: List[ProtocolField] = field(default_factory=list)
    consensus_header: str = ""
    length_relations: List[Dict] = field(default_factory=list)
    checksum_candidates: List[Dict] = field(default_factory=list)
    sequence_candidates: List[Dict] = field(default_factory=list)
    entropy_data: Dict = field(default_factory=dict)
    statistics: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'protocol_name': self.protocol_name,
            'version': self.version,
            'description': self.description,
            'created_at': self.created_at,
            'messages_analyzed': self.messages_analyzed,
            'average_message_length': self.average_message_length,
            'endianness': self.endianness,
            'fields': [f.to_dict() for f in self.fields],
            'consensus_header': self.consensus_header,
            'length_relations': self.length_relations,
            'checksum_candidates': self.checksum_candidates,
            'sequence_candidates': self.sequence_candidates,
            'entropy_data': self.entropy_data,
            'statistics': self.statistics
        }


class ProtocolOutputGenerator:
    """Generates protocol description files in various formats."""

    def __init__(self, protocol_desc: ProtocolDescription):
        self.protocol = protocol_desc

    def to_json(self, indent: int = 2) -> str:
        """Generate JSON protocol description."""
        return json.dumps(self.protocol.to_dict(), indent=indent, ensure_ascii=False)

    def to_xml(self, pretty: bool = True) -> str:
        """Generate XML protocol description."""
        root = ET.Element('protocol')
        root.set('name', self.protocol.protocol_name)
        root.set('version', self.protocol.version)

        info = ET.SubElement(root, 'info')
        ET.SubElement(info, 'description').text = self.protocol.description
        ET.SubElement(info, 'created_at').text = self.protocol.created_at
        ET.SubElement(info, 'messages_analyzed').text = str(self.protocol.messages_analyzed)
        ET.SubElement(info, 'average_message_length').text = f"{self.protocol.average_message_length:.2f}"
        ET.SubElement(info, 'endianness').text = self.protocol.endianness

        if self.protocol.consensus_header:
            ET.SubElement(info, 'consensus_header').text = self.protocol.consensus_header

        fields_elem = ET.SubElement(root, 'fields')
        for field in self.protocol.fields:
            field_elem = ET.SubElement(fields_elem, 'field')
            field_elem.set('name', field.name)
            field_elem.set('offset', str(field.offset))
            field_elem.set('length', str(field.length))

            ET.SubElement(field_elem, 'field_type').text = field.field_type
            ET.SubElement(field_elem, 'is_fixed').text = str(field.is_fixed)
            ET.SubElement(field_elem, 'inferred_type').text = field.inferred_type
            ET.SubElement(field_elem, 'confidence').text = f"{field.confidence:.3f}"
            ET.SubElement(field_elem, 'description').text = field.description

            if field.sample_values:
                samples_elem = ET.SubElement(field_elem, 'sample_values')
                for val in field.sample_values[:5]:
                    ET.SubElement(samples_elem, 'value').text = val

            if field.enum_values:
                enums_elem = ET.SubElement(field_elem, 'enum_values')
                for val, count in field.enum_values.items():
                    enum_elem = ET.SubElement(enums_elem, 'enum')
                    enum_elem.set('value', val)
                    enum_elem.set('count', str(count))

            if field.is_checksum:
                ET.SubElement(field_elem, 'is_checksum').text = 'true'
                ET.SubElement(field_elem, 'checksum_type').text = field.checksum_type

            if field.is_length_field:
                ET.SubElement(field_elem, 'is_length_field').text = 'true'
                ET.SubElement(field_elem, 'points_to_offset').text = str(field.points_to_offset)

        if self.protocol.length_relations:
            relations_elem = ET.SubElement(root, 'length_relations')
            for rel in self.protocol.length_relations:
                rel_elem = ET.SubElement(relations_elem, 'relation')
                rel_elem.set('length_offset', str(rel.get('length_offset', -1)))
                rel_elem.set('length_length', str(rel.get('length_length', -1)))
                rel_elem.set('target_offset', str(rel.get('target_offset', -1)))
                rel_elem.set('confidence', f"{rel.get('confidence', 0):.3f}")

        if self.protocol.checksum_candidates:
            checksums_elem = ET.SubElement(root, 'checksum_candidates')
            for cs in self.protocol.checksum_candidates:
                cs_elem = ET.SubElement(checksums_elem, 'checksum')
                cs_elem.set('offset', str(cs.get('offset', -1)))
                cs_elem.set('length', str(cs.get('length', -1)))
                cs_elem.set('type', cs.get('checksum_type', ''))
                cs_elem.set('confidence', f"{cs.get('confidence', 0):.3f}")

        stats_elem = ET.SubElement(root, 'statistics')
        for key, value in self.protocol.statistics.items():
            stat_elem = ET.SubElement(stats_elem, 'stat')
            stat_elem.set('name', key)
            stat_elem.text = str(value)

        xml_str = ET.tostring(root, encoding='unicode')
        if pretty:
            xml_str = minidom.parseString(xml_str).toprettyxml(indent="  ")

        return xml_str

    def save_json(self, output_path: str) -> None:
        """Save protocol description as JSON file."""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(self.to_json())

    def save_xml(self, output_path: str) -> None:
        """Save protocol description as XML file."""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(self.to_xml())
