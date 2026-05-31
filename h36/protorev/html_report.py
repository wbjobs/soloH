"""HTML visualization report generator."""

import base64
import io
from typing import Dict, List, Any, Optional
from datetime import datetime
import numpy as np

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    from jinja2 import Template
    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Protocol Reverse Engineering Report - {{ protocol_name }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: white;
            padding: 40px;
        }
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        .header .subtitle {
            color: #a0aec0;
            font-size: 1.1em;
        }
        .content {
            padding: 40px;
        }
        .section {
            margin-bottom: 50px;
        }
        .section h2 {
            color: #1a1a2e;
            font-size: 1.8em;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
            display: inline-block;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            padding: 25px;
            border-radius: 12px;
            text-align: center;
        }
        .stat-card .value {
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
        }
        .stat-card .label {
            color: #4a5568;
            font-size: 0.95em;
            margin-top: 5px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        th {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }
        td {
            padding: 12px 15px;
            border-bottom: 1px solid #e2e8f0;
        }
        tr:hover {
            background: #f7fafc;
        }
        .field-fixed { background: #c6f6d5; }
        .field-variable { background: #fed7d7; }
        .field-checksum { background: #fefcbf; }
        .field-length { background: #bee3f8; }
        .confidence-bar {
            height: 8px;
            background: #e2e8f0;
            border-radius: 4px;
            overflow: hidden;
        }
        .confidence-fill {
            height: 100%;
            background: linear-gradient(90deg, #48bb78, #38a169);
            transition: width 0.3s;
        }
        .chart-container {
            background: #f7fafc;
            padding: 30px;
            border-radius: 12px;
            margin: 20px 0;
            text-align: center;
        }
        .chart-container img {
            max-width: 100%;
            height: auto;
            border-radius: 8px;
        }
        .hex-display {
            font-family: 'Courier New', monospace;
            background: #1a1a2e;
            color: #68d391;
            padding: 20px;
            border-radius: 8px;
            overflow-x: auto;
            font-size: 0.9em;
            line-height: 1.6;
        }
        .tag {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
            margin-right: 8px;
        }
        .tag-fixed { background: #c6f6d5; color: #22543d; }
        .tag-variable { background: #fed7d7; color: #742a2a; }
        .tag-integer { background: #bee3f8; color: #2a4365; }
        .tag-float { background: #e9d8fd; color: #553c9a; }
        .tag-timestamp { background: #feebc8; color: #744210; }
        .tag-enum { background: #fed7e0; color: #702459; }
        .tag-ascii { background: #c6f6d5; color: #22543d; }
        .tag-checksum { background: #fefcbf; color: #744210; }
        .tag-length { background: #bee3f8; color: #2a4365; }
        .message-list {
            max-height: 400px;
            overflow-y: auto;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
        }
        .message-item {
            padding: 15px;
            border-bottom: 1px solid #e2e8f0;
            cursor: pointer;
        }
        .message-item:hover {
            background: #f7fafc;
        }
        .footer {
            text-align: center;
            padding: 30px;
            color: #a0aec0;
            font-size: 0.9em;
            border-top: 1px solid #e2e8f0;
        }
        .two-columns {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
        }
        @media (max-width: 768px) {
            .two-columns {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Protocol Reverse Engineering Report</h1>
            <div class="subtitle">Protocol: {{ protocol_name }} | Generated: {{ generated_at }}</div>
        </div>

        <div class="content">
            <div class="section">
                <h2>📊 Analysis Overview</h2>
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="value">{{ messages_analyzed }}</div>
                        <div class="label">Messages Analyzed</div>
                    </div>
                    <div class="stat-card">
                        <div class="value">{{ avg_length }}</div>
                        <div class="label">Avg. Message Length</div>
                    </div>
                    <div class="stat-card">
                        <div class="value">{{ num_fields }}</div>
                        <div class="label">Fields Detected</div>
                    </div>
                    <div class="stat-card">
                        <div class="value">{{ avg_entropy }}</div>
                        <div class="label">Avg. Entropy</div>
                    </div>
                </div>
            </div>

            {% if consensus_header %}
            <div class="section">
                <h2>🏷️ Consensus Header</h2>
                <div class="hex-display">{{ consensus_header }}</div>
            </div>
            {% endif %}

            <div class="section">
                <h2>📐 Detected Fields</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Offset</th>
                            <th>Length</th>
                            <th>Type</th>
                            <th>Inferred</th>
                            <th>Confidence</th>
                            <th>Sample Values</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for field in fields %}
                        <tr class="{{ 'field-fixed' if field.is_fixed else 'field-variable' }}">
                            <td><strong>{{ field.name }}</strong></td>
                            <td>0x{{ '%04X'|format(field.offset) }}</td>
                            <td>{{ field.length }}</td>
                            <td>
                                <span class="tag {{ 'tag-fixed' if field.is_fixed else 'tag-variable' }}">
                                    {{ 'FIXED' if field.is_fixed else 'VARIABLE' }}
                                </span>
                            </td>
                            <td>
                                <span class="tag tag-{{ field.inferred_type }}">{{ field.inferred_type.upper() }}</span>
                                {% if field.is_checksum %}<span class="tag tag-checksum">CHECKSUM</span>{% endif %}
                                {% if field.is_length_field %}<span class="tag tag-length">LENGTH</span>{% endif %}
                            </td>
                            <td>
                                <div class="confidence-bar">
                                    <div class="confidence-fill" style="width: {{ '%0.1f'|format(field.confidence * 100) }}%"></div>
                                </div>
                                <small>{{ '%0.1f'|format(field.confidence * 100) }}%</small>
                            </td>
                            <td><code>{{ field.sample_values[:3]|join(', ') }}</code></td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>

            {% if entropy_chart %}
            <div class="section">
                <h2>📈 Entropy Analysis</h2>
                <div class="chart-container">
                    <img src="data:image/png;base64,{{ entropy_chart }}" alt="Entropy Analysis">
                </div>
            </div>
            {% endif %}

            {% if conservation_chart %}
            <div class="section">
                <h2>🔒 Byte Conservation</h2>
                <div class="chart-container">
                    <img src="data:image/png;base64,{{ conservation_chart }}" alt="Conservation Analysis">
                </div>
            </div>
            {% endif %}

            {% if heatmap_chart %}
            <div class="section">
                <h2>🌡️ Entropy Heatmap</h2>
                <div class="chart-container">
                    <img src="data:image/png;base64,{{ heatmap_chart }}" alt="Entropy Heatmap">
                </div>
            </div>
            {% endif %}

            <div class="two-columns">
                {% if length_relations %}
                <div class="section">
                    <h2>📏 Length Field Relations</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Length Offset</th>
                                <th>Length Len</th>
                                <th>Target Offset</th>
                                <th>Confidence</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for rel in length_relations %}
                            <tr>
                                <td>0x{{ '%04X'|format(rel.length_offset) }}</td>
                                <td>{{ rel.length_length }}</td>
                                <td>0x{{ '%04X'|format(rel.target_offset) }}</td>
                                <td>{{ '%0.1f'|format(rel.confidence * 100) }}%</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                {% endif %}

                {% if checksum_candidates %}
                <div class="section">
                    <h2>✅ Checksum Candidates</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Offset</th>
                                <th>Length</th>
                                <th>Type</th>
                                <th>Confidence</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for cs in checksum_candidates %}
                            <tr>
                                <td>0x{{ '%04X'|format(cs.offset) }}</td>
                                <td>{{ cs.length }}</td>
                                <td>{{ cs.checksum_type }}</td>
                                <td>{{ '%0.1f'|format(cs.confidence * 100) }}%</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                {% endif %}
            </div>

            {% if sample_messages %}
            <div class="section">
                <h2>📝 Sample Messages</h2>
                <div class="message-list">
                    {% for i, msg in enumerate(sample_messages[:10]) %}
                    <div class="message-item">
                        <strong>Message {{ i + 1 }} ({{ len(msg) }} bytes):</strong>
                        <div class="hex-display" style="margin-top: 10px;">{{ msg.hex(' ', 16) }}</div>
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endif %}
        </div>

        <div class="footer">
            <p>Generated by Protocol Reverse Engineering Toolkit v1.0</p>
            <p>{{ generated_at }}</p>
        </div>
    </div>
</body>
</html>
"""


class HTMLReportGenerator:
    """Generates HTML visualization reports."""

    def __init__(self):
        if not HAS_MATPLOTLIB:
            raise ImportError("matplotlib is required. Install with: pip install matplotlib")
        if not HAS_JINJA2:
            raise ImportError("jinja2 is required. Install with: pip install jinja2")

    def _fig_to_base64(self, fig) -> str:
        """Convert matplotlib figure to base64 string."""
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        return img_base64

    def create_entropy_chart(self, entropy_data: Dict) -> Optional[str]:
        """Create entropy analysis chart."""
        offset_entropy = entropy_data.get('offset_entropy', [])
        if not offset_entropy:
            return None

        offsets = [e['offset'] for e in offset_entropy]
        entropies = [e['entropy'] for e in offset_entropy]

        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(offsets, entropies, linewidth=2, color='#667eea')
        ax.fill_between(offsets, entropies, alpha=0.3, color='#667eea')

        ax.axhline(y=4.0, color='#f6ad55', linestyle='--', alpha=0.7, label='Medium Threshold')
        ax.axhline(y=6.0, color='#fc8181', linestyle='--', alpha=0.7, label='High Threshold')

        ax.set_xlabel('Byte Offset')
        ax.set_ylabel('Shannon Entropy')
        ax.set_title('Entropy Analysis by Byte Offset')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, 8)

        return self._fig_to_base64(fig)

    def create_conservation_chart(self, conservation_scores: List[float]) -> Optional[str]:
        """Create byte conservation chart."""
        if not conservation_scores:
            return None

        fig, ax = plt.subplots(figsize=(12, 5))
        positions = list(range(len(conservation_scores)))

        colors = ['#48bb78' if c >= 0.95 else '#ed8936' if c >= 0.7 else '#fc8181' for c in conservation_scores]
        ax.bar(positions, conservation_scores, color=colors, alpha=0.8)

        ax.axhline(y=0.95, color='#48bb78', linestyle='--', alpha=0.7, label='Fixed (>=0.95)')
        ax.axhline(y=0.7, color='#ed8936', linestyle='--', alpha=0.7, label='Semi-fixed (>=0.7)')

        ax.set_xlabel('Byte Position')
        ax.set_ylabel('Conservation Score')
        ax.set_title('Byte Conservation Across Messages')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, 1.1)

        return self._fig_to_base64(fig)

    def create_heatmap_chart(self, heatmap_data: Dict) -> Optional[str]:
        """Create entropy heatmap."""
        heatmap = heatmap_data.get('heatmap', [])
        if not heatmap:
            return None

        hm_array = np.array(heatmap)
        if hm_array.size == 0:
            return None

        fig, ax = plt.subplots(figsize=(14, 8))

        cmap = LinearSegmentedColormap.from_list(
            'entropy',
            ['#48bb78', '#ecc94b', '#fc8181', '#c53030']
        )

        im = ax.imshow(hm_array, aspect='auto', cmap=cmap, vmin=0, vmax=8, interpolation='nearest')

        ax.set_xlabel('Byte Offset')
        ax.set_ylabel('Message Index')
        ax.set_title('Entropy Heatmap Across Messages')

        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Entropy')

        return self._fig_to_base64(fig)

    def generate_report(self, protocol_desc: Dict, messages: List[bytes],
                        conservation_scores: Optional[List[float]] = None,
                        heatmap_data: Optional[Dict] = None) -> str:
        """Generate complete HTML report."""
        entropy_data = protocol_desc.get('entropy_data', {})

        entropy_chart = self.create_entropy_chart(entropy_data)
        conservation_chart = self.create_conservation_chart(conservation_scores or [])
        heatmap_chart = self.create_heatmap_chart(heatmap_data or {})

        fields = protocol_desc.get('fields', [])
        length_relations = protocol_desc.get('length_relations', [])
        checksum_candidates = protocol_desc.get('checksum_candidates', [])

        avg_length = protocol_desc.get('average_message_length', 0)
        avg_entropy = entropy_data.get('average_entropy', 0)

        template = Template(HTML_TEMPLATE)

        class HexWrapper(bytes):
            def __new__(cls, data):
                return super().__new__(cls, data)

        html = template.render(
            protocol_name=protocol_desc.get('protocol_name', 'unknown'),
            generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            messages_analyzed=protocol_desc.get('messages_analyzed', 0),
            avg_length=f"{avg_length:.1f}",
            num_fields=len(fields),
            avg_entropy=f"{avg_entropy:.2f}",
            consensus_header=protocol_desc.get('consensus_header', ''),
            fields=fields,
            length_relations=length_relations,
            checksum_candidates=checksum_candidates,
            sample_messages=messages,
            entropy_chart=entropy_chart,
            conservation_chart=conservation_chart,
            heatmap_chart=heatmap_chart,
            enumerate=enumerate,
            len=len,
            format=format
        )

        return html

    def save_report(self, html_content: str, output_path: str) -> None:
        """Save HTML report to file."""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
