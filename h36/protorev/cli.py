"""Command-line interface for protocol reverse engineering."""

import argparse
import sys
import os
from typing import List

from .analyzer import ProtocolAnalyzer


def parse_args(args: List[str] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog='protorev',
        description='Protocol Reverse Engineering Toolkit - Analyze PCAP files to reverse engineer custom protocols',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  protorev -i capture.pcap -o protocol_report
  protorev -i capture.pcap -f json xml html -n "MyCustomProtocol"
  protorev -i capture.pcap --endianness big --min-messages 5
        """
    )

    parser.add_argument(
        '-i', '--input',
        required=True,
        help='Input PCAP file path'
    )

    parser.add_argument(
        '-o', '--output',
        default='protocol_analysis',
        help='Output file prefix (default: protocol_analysis)'
    )

    parser.add_argument(
        '-f', '--formats',
        nargs='+',
        choices=['json', 'xml', 'html', 'dot', 'lua', 'crypto'],
        default=['json', 'xml', 'html'],
        help='Output formats to generate (default: json xml html). Additional: dot (state machine), lua (Wireshark dissector), crypto (crypto report)'
    )

    parser.add_argument(
        '--no-state-machine',
        action='store_true',
        help='Disable state machine inference'
    )

    parser.add_argument(
        '--no-crypto-detection',
        action='store_true',
        help='Disable cryptographic protocol detection'
    )

    parser.add_argument(
        '--cluster-algorithm',
        choices=['prefix', 'similarity', 'length', 'type'],
        default='prefix',
        help='Clustering algorithm for state machine inference (default: prefix)'
    )

    parser.add_argument(
        '-n', '--name',
        default='unknown',
        help='Protocol name for the report (default: unknown)'
    )

    parser.add_argument(
        '--endianness',
        choices=['auto', 'little', 'big'],
        default='auto',
        help='Byte endianness for numeric fields (default: auto)'
    )

    parser.add_argument(
        '--min-messages',
        type=int,
        default=3,
        help='Minimum number of messages required for analysis (default: 3)'
    )

    parser.add_argument(
        '--filter-port',
        type=int,
        default=None,
        help='Filter messages by destination port (optional)'
    )

    parser.add_argument(
        '--no-summary',
        action='store_true',
        help='Do not print analysis summary to console'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )

    return parser.parse_args(args)


def main(args: List[str] = None) -> int:
    """Main entry point."""
    try:
        parsed_args = parse_args(args)

        if not os.path.exists(parsed_args.input):
            print(f"Error: Input file not found: {parsed_args.input}", file=sys.stderr)
            return 1

        if parsed_args.verbose:
            print(f"[*] Protocol Reverse Engineering Toolkit v1.0")
            print(f"[*] Input file: {parsed_args.input}")
            print(f"[*] Output prefix: {parsed_args.output}")
            print(f"[*] Output formats: {', '.join(parsed_args.formats)}")
            print(f"[*] Endianness: {parsed_args.endianness}")
            print(f"[*] State machine: {'Disabled' if parsed_args.no_state_machine else 'Enabled'}")
            print(f"[*] Crypto detection: {'Disabled' if parsed_args.no_crypto_detection else 'Enabled'}")
            print(f"[*] Cluster algorithm: {parsed_args.cluster_algorithm}")
            print()

        analyzer = ProtocolAnalyzer(
            endianness=parsed_args.endianness,
            min_messages=parsed_args.min_messages,
            enable_state_machine=not parsed_args.no_state_machine,
            enable_crypto_detection=not parsed_args.no_crypto_detection
        )

        if hasattr(parsed_args, 'cluster_algorithm'):
            analyzer.state_machine_inferrer.cluster_algorithm = parsed_args.cluster_algorithm

        result = analyzer.analyze_pcap(
            pcap_file=parsed_args.input,
            protocol_name=parsed_args.name
        )

        if not parsed_args.no_summary:
            analyzer.print_summary(result)

        saved_files = analyzer.save_results(
            result=result,
            output_prefix=parsed_args.output,
            formats=parsed_args.formats
        )

        print(f"\n[✓] All files saved successfully!")
        for f in saved_files:
            print(f"    - {f}")

        return 0

    except KeyboardInterrupt:
        print("\n[!] Analysis interrupted by user", file=sys.stderr)
        return 130

    except ImportError as e:
        print(f"\n[!] Missing dependency: {e}", file=sys.stderr)
        print("    Install required dependencies with: pip install -r requirements.txt", file=sys.stderr)
        return 2

    except Exception as e:
        print(f"\n[!] Error during analysis: {e}", file=sys.stderr)
        if parsed_args and parsed_args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
