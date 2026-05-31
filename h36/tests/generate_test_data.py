"""Generate test PCAP files with custom protocol messages."""

import struct
import random
import time
import os
from datetime import datetime, timezone

try:
    from scapy.all import Ether, IP, UDP, Raw, wrpcap
except ImportError:
    print("scapy is required to generate test data")
    exit(1)


def generate_custom_protocol_messages(num_messages: int = 20) -> list:
    """Generate messages with a custom protocol structure.

    Protocol format (16 bytes header + variable payload):
    - Magic (2 bytes): 0x1234 (fixed)
    - Version (1 byte): 0x01 (fixed)
    - Message Type (1 byte): enum (0x00, 0x01, 0x02, 0x03)
    - Sequence Number (2 bytes): increasing
    - Timestamp (4 bytes): Unix timestamp
    - Length (2 bytes): payload length
    - Checksum (2 bytes): additive checksum of header + payload
    - Payload (variable): random bytes
    """
    messages = []
    seq_num = 0

    for i in range(num_messages):
        msg_type = random.choice([0x00, 0x01, 0x02, 0x03])
        seq_num += 1
        timestamp = int(datetime.now().timestamp()) - random.randint(0, 3600)
        payload_len = random.randint(8, 64)
        payload = bytes([random.randint(0, 255) for _ in range(payload_len)])

        header = struct.pack(
            '<H B B H I H',
            0x1234,
            0x01,
            msg_type,
            seq_num,
            timestamp,
            payload_len
        )

        checksum = sum(header + payload) & 0xFFFF
        header += struct.pack('<H', checksum)

        full_message = header + payload
        messages.append(full_message)

    return messages


def generate_test_pcap(output_path: str, num_messages: int = 20) -> str:
    """Generate a test PCAP file with custom protocol messages."""
    messages = generate_custom_protocol_messages(num_messages)

    packets = []
    src_ip = "192.168.1.100"
    dst_ip = "192.168.1.200"
    src_port = 12345
    dst_port = 54321

    for i, msg in enumerate(messages):
        pkt = Ether() / IP(src=src_ip, dst=dst_ip) / UDP(sport=src_port, dport=dst_port) / Raw(load=msg)
        pkt.time = time.time() - (num_messages - i) * 0.1
        packets.append(pkt)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    wrpcap(output_path, packets)

    print(f"[+] Generated test PCAP: {output_path}")
    print(f"[+] Contains {len(messages)} messages with custom protocol")
    print()
    print("Protocol structure used for generation:")
    print("  Offset 0x00: Magic (2 bytes) = 0x1234 (fixed)")
    print("  Offset 0x02: Version (1 byte) = 0x01 (fixed)")
    print("  Offset 0x03: Message Type (1 byte) = enum [0x00, 0x01, 0x02, 0x03]")
    print("  Offset 0x04: Sequence Number (2 bytes) = increasing")
    print("  Offset 0x06: Timestamp (4 bytes) = Unix timestamp")
    print("  Offset 0x0A: Payload Length (2 bytes) = variable")
    print("  Offset 0x0C: Checksum (2 bytes) = additive checksum")
    print("  Offset 0x0E: Payload (variable) = random bytes")
    print()

    return output_path


if __name__ == '__main__':
    output_dir = os.path.join(os.path.dirname(__file__), 'data')
    output_path = os.path.join(output_dir, 'test_protocol.pcap')
    generate_test_pcap(output_path, num_messages=15)
