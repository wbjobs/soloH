from typing import Optional, Dict, Any, List, Set, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from collections import defaultdict
from datetime import datetime, timedelta

from app.services.base import BaseService
from app.repositories import PatternRepository, GraphRepository, TransactionRepository, AddressRepository
from app.models.blockchain import Transaction, GraphEdge, Address
from app.models.analysis import SuspiciousPattern


class PatternService(BaseService[PatternRepository]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, PatternRepository)
        self.graph_repo = GraphRepository(db)
        self.tx_repo = TransactionRepository(db)
        self.address_repo = AddressRepository(db)

    async def detect_layering_patterns(self, address: str) -> List[SuspiciousPattern]:
        subgraph = await self.graph_repo.get_subgraph(address, depth=3, min_value=0.0001)

        patterns = []
        if len(subgraph) >= 10:
            layers: Dict[int, Set[str]] = defaultdict(set)
            layers[0] = {address}

            for edge in subgraph:
                if edge.from_address in layers[0]:
                    layers[1].add(edge.to_address)

            for depth in range(1, 3):
                for edge in subgraph:
                    if edge.from_address in layers[depth]:
                        layers[depth + 1].add(edge.to_address)

            layer_sizes = [len(layer) for layer in layers.values()]
            if all(size >= 3 for size in layer_sizes if size > 0):
                confidence = min(0.9, len(subgraph) / 50)
                pattern = await self.repository.create_pattern({
                    "pattern_type": "layering",
                    "confidence": confidence,
                    "severity": "high",
                    "description": f"检测到分层模式，涉及{len(subgraph)}条交易，深度为3层",
                    "evidence": {"layers": {k: list(v) for k, v in layers.items()}, "edge_count": len(subgraph)},
                    "address": address
                })
                patterns.append(pattern)

        return patterns

    async def detect_cycle_patterns(self, graph_data: Dict[str, Any]) -> List[SuspiciousPattern]:
        edges = graph_data.get("edges", [])
        patterns = []

        adjacency: Dict[str, List[Tuple[str, float, Any]]] = defaultdict(list)
        edge_map: Dict[Tuple[str, str], Dict[str, Any]] = {}

        processed_edges = []
        for edge in edges:
            from_addr = edge.get("from")
            to_addr = edge.get("to")
            timestamp = edge.get("timestamp")
            if isinstance(timestamp, datetime):
                ts = timestamp.timestamp()
            elif isinstance(timestamp, (int, float)):
                ts = float(timestamp)
            else:
                ts = 0.0

            if from_addr and to_addr:
                processed_edges.append({
                    "from": from_addr,
                    "to": to_addr,
                    "timestamp": ts,
                    "value": edge.get("value", 0),
                    "raw": edge
                })

        processed_edges.sort(key=lambda e: (e["timestamp"], e["from"], e["to"]))

        for i, edge in enumerate(processed_edges):
            from_addr = edge["from"]
            to_addr = edge["to"]
            ts = edge["timestamp"]

            if i > 0:
                prev_ts = processed_edges[i-1]["timestamp"]
                if abs(ts - prev_ts) < 1.0:
                    ts = prev_ts + 0.001 * i

            edge["adjusted_timestamp"] = ts
            adjacency[from_addr].append((to_addr, ts, edge["raw"]))
            edge_map[(from_addr, to_addr)] = edge["raw"]

        for from_addr in adjacency:
            adjacency[from_addr].sort(key=lambda x: x[1])

        cycles = self._find_cycles(adjacency, max_length=6, max_time_window=86400 * 30)

        for cycle in cycles:
            if len(cycle) >= 3:
                cycle_edges = []
                total_value = 0.0
                timestamps = []
                for i in range(len(cycle)):
                    from_addr = cycle[i]
                    to_addr = cycle[(i + 1) % len(cycle)]
                    edge_data = edge_map.get((from_addr, to_addr))
                    if edge_data:
                        cycle_edges.append(edge_data)
                        total_value += edge_data.get("value", 0)
                        ts = edge_data.get("timestamp")
                        if isinstance(ts, datetime):
                            timestamps.append(ts.timestamp())
                        elif isinstance(ts, (int, float)):
                            timestamps.append(float(ts))

                unique_addrs = set(cycle)
                if len(unique_addrs) >= 3:
                    time_span = max(timestamps) - min(timestamps) if timestamps else 0
                    time_penalty = max(0.5, 1.0 - (time_span / (86400 * 30)))
                    base_confidence = min(0.95, len(unique_addrs) / 10)
                    confidence = min(0.95, base_confidence * time_penalty)

                    pattern = await self.repository.create_pattern({
                        "pattern_type": "cycle",
                        "confidence": confidence,
                        "severity": "medium",
                        "description": f"检测到循环模式，涉及{len(unique_addrs)}个地址，总价值{total_value:.8f} BTC，时间跨度{time_span/3600:.1f}小时",
                        "evidence": {"cycle": cycle, "edges": cycle_edges, "total_value": total_value, "time_span_hours": time_span / 3600},
                        "address": cycle[0]
                    })
                    patterns.append(pattern)

        return patterns

    def _find_cycles(self, adjacency: Dict[str, List[Tuple[str, float, Any]]], max_length: int = 6, max_time_window: float = 86400 * 30) -> List[List[str]]:
        cycles = []
        visited = set()

        def dfs(node: str, path: List[str], timestamps: List[float], depth: int):
            if depth > max_length:
                return

            for neighbor, edge_ts, _ in adjacency.get(node, []):
                if timestamps and edge_ts < timestamps[-1] - 1.0:
                    continue

                if neighbor == path[0] and len(path) >= 3:
                    if timestamps:
                        time_span = edge_ts - timestamps[0]
                        if 0 <= time_span <= max_time_window:
                            cycles.append(path.copy())
                elif neighbor not in visited and neighbor not in path:
                    visited.add(neighbor)
                    path.append(neighbor)
                    timestamps.append(edge_ts)
                    dfs(neighbor, path, timestamps, depth + 1)
                    timestamps.pop()
                    path.pop()
                    visited.remove(neighbor)

        for start_node in adjacency:
            if start_node not in visited:
                dfs(start_node, [start_node], [], 1)

        return cycles

    async def detect_structuring_patterns(self, address: str, transactions: List[Transaction]) -> List[SuspiciousPattern]:
        patterns = []

        address_txs = [
            tx for tx in transactions
            if any(inp.address == address for inp in tx.inputs) or
               any(out.address == address for out in tx.outputs)
        ]

        if len(address_txs) < 10:
            return patterns

        outgoing_values = []
        incoming_values = []

        for tx in address_txs:
            for out in tx.outputs:
                if out.address == address:
                    incoming_values.append(out.value)
            for inp in tx.inputs:
                if inp.address == address:
                    outgoing_values.append(inp.value)

        structuring_threshold = 1.0

        small_outgoing = [v for v in outgoing_values if v < structuring_threshold and v > 0]
        small_incoming = [v for v in incoming_values if v < structuring_threshold and v > 0]

        if len(small_outgoing) >= 10 or len(small_incoming) >= 10:
            time_diffs = []
            sorted_txs = sorted(address_txs, key=lambda x: x.block_time)
            for i in range(1, len(sorted_txs)):
                diff = (sorted_txs[i].block_time - sorted_txs[i-1].block_time).total_seconds()
                time_diffs.append(diff)

            avg_interval = sum(time_diffs) / len(time_diffs) if time_diffs else 0

            if 60 < avg_interval < 3600 * 24:
                confidence = min(0.85, (len(small_outgoing) + len(small_incoming)) / 50)
                pattern = await self.repository.create_pattern({
                    "pattern_type": "structuring",
                    "confidence": confidence,
                    "severity": "medium",
                    "description": f"检测到结构化模式，{len(small_outgoing)}笔小额支出，{len(small_incoming)}笔小额收入，平均间隔{avg_interval/60:.1f}分钟",
                    "evidence": {
                        "small_outgoing_count": len(small_outgoing),
                        "small_incoming_count": len(small_incoming),
                        "avg_interval_minutes": avg_interval / 60,
                        "threshold": structuring_threshold
                    },
                    "address": address
                })
                patterns.append(pattern)

        return patterns

    async def detect_mixing_patterns(self, address: str) -> List[SuspiciousPattern]:
        patterns = []

        outgoing_edges = await self.graph_repo.get_outgoing_edges(address, {"limit": 100})
        incoming_edges = await self.graph_repo.get_incoming_edges(address, {"limit": 100})

        if len(incoming_edges) >= 5 and len(outgoing_edges) >= 5:
            unique_senders = {edge.from_address for edge in incoming_edges}
            unique_receivers = {edge.to_address for edge in outgoing_edges}

            if len(unique_senders) >= 3 and len(unique_receivers) >= 3:
                total_in = sum(edge.value for edge in incoming_edges)
                total_out = sum(edge.value for edge in outgoing_edges)

                value_match_ratio = min(total_in, total_out) / max(total_in, total_out) if max(total_in, total_out) > 0 else 0

                if value_match_ratio > 0.8:
                    avg_in_degree = len(incoming_edges) / len(unique_senders)
                    avg_out_degree = len(outgoing_edges) / len(unique_receivers)

                    confidence = min(0.9, value_match_ratio * avg_in_degree * avg_out_degree / 10)
                    pattern = await self.repository.create_pattern({
                        "pattern_type": "mixing",
                        "confidence": confidence,
                        "severity": "high",
                        "description": f"检测到混币模式，{len(unique_senders)}个来源地址，{len(unique_receivers)}个接收地址，价值匹配率{value_match_ratio:.2%}",
                        "evidence": {
                            "unique_senders": len(unique_senders),
                            "unique_receivers": len(unique_receivers),
                            "total_in": total_in,
                            "total_out": total_out,
                            "value_match_ratio": value_match_ratio
                        },
                        "address": address
                    })
                    patterns.append(pattern)

        return patterns

    async def calculate_overall_suspicious_score(self, address: str) -> float:
        patterns = await self.repository.get_address_patterns(address)

        score = 0.0
        pattern_weights = {
            "layering": 25,
            "mixing": 30,
            "structuring": 20,
            "cycle": 25,
            "peeling": 15,
            "funnel": 20,
            "dusting": 10,
        }

        severity_multipliers = {
            "low": 0.5,
            "medium": 1.0,
            "high": 1.5,
            "critical": 2.0
        }

        for pattern in patterns:
            weight = pattern_weights.get(pattern.pattern_type, 10)
            severity_mult = severity_multipliers.get(pattern.severity, 1.0)
            contribution = weight * pattern.confidence * severity_mult
            score += contribution

        return min(score, 100)
