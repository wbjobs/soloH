"""PCAP file reader and payload extractor."""

import struct
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

try:
    from scapy.all import rdpcap, Packet, Raw, IP, TCP, UDP
except ImportError:
    rdpcap = None
    Packet = None
    Raw = None
    IP = None
    TCP = None
    UDP = None


@dataclass
class Message:
    """Represents a single extracted message."""
    data: bytes
    timestamp: float
    length: int
    src_ip: Optional[str] = None
    dst_ip: Optional[str] = None
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    protocol: Optional[str] = None


@dataclass
class PcapSession:
    """Represents a session (flow) of related messages."""
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str
    messages: List[Message] = field(default_factory=list)

    @property
    def key(self) -> Tuple[str, str, int, int, str]:
        return (self.src_ip, self.dst_ip, self.src_port, self.dst_port, self.protocol)


class PcapReader:
    """Reads PCAP files and extracts application-layer payloads."""

    def __init__(self, pcap_file: str):
        if rdpcap is None:
            raise ImportError("scapy is required. Install with: pip install scapy")
        self.pcap_file = pcap_file
        self._packets: Optional[List] = None

    def read_packets(self) -> List:
        """Read all packets from the pcap file."""
        if self._packets is None:
            self._packets = rdpcap(self.pcap_file)
        return self._packets

    def extract_payload(self, packet: Packet) -> Optional[bytes]:
        """Extract application-layer payload from a packet."""
        if Raw in packet:
            return bytes(packet[Raw].load)
        return None

    def get_packet_info(self, packet: Packet) -> dict:
        """Extract metadata from a packet."""
        info = {
            'timestamp': float(packet.time),
            'src_ip': None,
            'dst_ip': None,
            'src_port': None,
            'dst_port': None,
            'protocol': None,
        }

        if IP in packet:
            info['src_ip'] = packet[IP].src
            info['dst_ip'] = packet[IP].dst

            if TCP in packet:
                info['src_port'] = packet[TCP].sport
                info['dst_port'] = packet[TCP].dport
                info['protocol'] = 'TCP'
            elif UDP in packet:
                info['src_port'] = packet[UDP].sport
                info['dst_port'] = packet[UDP].dport
                info['protocol'] = 'UDP'

        return info

    def extract_messages(self, filter_empty: bool = True) -> List[Message]:
        """Extract all messages with payload from the pcap file."""
        packets = self.read_packets()
        messages = []

        for packet in packets:
            payload = self.extract_payload(packet)
            if payload is None:
                continue
            if filter_empty and len(payload) == 0:
                continue

            info = self.get_packet_info(packet)
            message = Message(
                data=payload,
                timestamp=info['timestamp'],
                length=len(payload),
                src_ip=info['src_ip'],
                dst_ip=info['dst_ip'],
                src_port=info['src_port'],
                dst_port=info['dst_port'],
                protocol=info['protocol'],
            )
            messages.append(message)

        return messages

    def extract_sessions(self, filter_empty: bool = True) -> List[PcapSession]:
        """Extract messages grouped by session (flow)."""
        messages = self.extract_messages(filter_empty)
        sessions: dict = {}

        for msg in messages:
            if None in (msg.src_ip, msg.dst_ip, msg.src_port, msg.dst_port, msg.protocol):
                continue

            session_key = (msg.src_ip, msg.dst_ip, msg.src_port, msg.dst_port, msg.protocol)
            if session_key not in sessions:
                sessions[session_key] = PcapSession(
                    src_ip=msg.src_ip,
                    dst_ip=msg.dst_ip,
                    src_port=msg.src_port,
                    dst_port=msg.dst_port,
                    protocol=msg.protocol,
                )
            sessions[session_key].messages.append(msg)

        return list(sessions.values())

    def get_all_payloads(self, filter_empty: bool = True) -> List[bytes]:
        """Get just the payload bytes from all messages."""
        messages = self.extract_messages(filter_empty)
        return [msg.data for msg in messages]
