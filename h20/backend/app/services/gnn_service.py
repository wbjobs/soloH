from typing import Optional, Dict, Any, List, Set, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from collections import defaultdict
import numpy as np
from datetime import datetime, timedelta

from app.services.base import BaseService
from app.repositories import GraphRepository, TransactionRepository, AddressRepository
from app.models.blockchain import Transaction, GraphEdge, Address


class GNNAnomalyService(BaseService[GraphRepository]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, GraphRepository)
        self.tx_repo = TransactionRepository(db)
        self.addr_repo = AddressRepository(db)

    async def calculate_gnn_anomaly_score(
        self,
        address: str,
        depth: int = 3
    ) -> Dict[str, Any]:
        subgraph = await self.repository.get_subgraph(address, depth=depth, min_value=0.0001)

        if not subgraph:
            return {
                "address": address,
                "anomaly_score": 0.0,
                "features": {},
                "risk_level": "low"
            }

        nodes, edges = self._extract_subgraph_structure(subgraph, address)

        features = self._extract_node_features(address, nodes, edges, subgraph)

        anomaly_score = self._compute_gnn_score(address, features, edges)

        risk_level = self._get_risk_level(anomaly_score)

        feature_importance = self._compute_feature_importance(features, anomaly_score)

        return {
            "address": address,
            "anomaly_score": round(anomaly_score, 4),
            "risk_level": risk_level,
            "features": features,
            "feature_importance": feature_importance,
            "subgraph_size": {
                "nodes": len(nodes),
                "edges": len(edges)
            },
            "analysis_depth": depth
        }

    async def batch_calculate_gnn_scores(
        self,
        addresses: List[str],
        depth: int = 2
    ) -> List[Dict[str, Any]]:
        results = []
        for address in addresses:
            result = await self.calculate_gnn_anomaly_score(address, depth)
            results.append(result)
        return results

    def _extract_subgraph_structure(
        self,
        edges: List[GraphEdge],
        target_address: str
    ) -> Tuple[Set[str], List[Dict[str, Any]]]:
        nodes = {target_address}
        edge_list = []

        for edge in edges:
            from_addr = edge.from_address
            to_addr = edge.to_address

            if from_addr:
                nodes.add(from_addr)
            if to_addr:
                nodes.add(to_addr)

            edge_list.append({
                "from": from_addr,
                "to": to_addr,
                "value": edge.value,
                "timestamp": edge.timestamp.timestamp() if edge.timestamp else 0,
                "txid": edge.txid
            })

        return nodes, edge_list

    def _extract_node_features(
        self,
        target_address: str,
        nodes: Set[str],
        edges: List[Dict[str, Any]],
        raw_edges: List[GraphEdge]
    ) -> Dict[str, float]:
        features: Dict[str, float] = {}

        in_edges = [e for e in edges if e["to"] == target_address]
        out_edges = [e for e in edges if e["from"] == target_address]

        features["in_degree"] = float(len(in_edges))
        features["out_degree"] = float(len(out_edges))
        features["total_degree"] = float(len(in_edges) + len(out_edges))

        in_values = [e["value"] for e in in_edges]
        out_values = [e["value"] for e in out_edges]
        all_values = in_values + out_values

        if in_values:
            features["avg_in_value"] = float(np.mean(in_values))
            features["max_in_value"] = float(np.max(in_values))
            features["min_in_value"] = float(np.min(in_values))
            features["std_in_value"] = float(np.std(in_values)) if len(in_values) > 1 else 0.0
            features["total_in_value"] = float(np.sum(in_values))
        else:
            features["avg_in_value"] = 0.0
            features["max_in_value"] = 0.0
            features["min_in_value"] = 0.0
            features["std_in_value"] = 0.0
            features["total_in_value"] = 0.0

        if out_values:
            features["avg_out_value"] = float(np.mean(out_values))
            features["max_out_value"] = float(np.max(out_values))
            features["min_out_value"] = float(np.min(out_values))
            features["std_out_value"] = float(np.std(out_values)) if len(out_values) > 1 else 0.0
            features["total_out_value"] = float(np.sum(out_values))
        else:
            features["avg_out_value"] = 0.0
            features["max_out_value"] = 0.0
            features["min_out_value"] = 0.0
            features["std_out_value"] = 0.0
            features["total_out_value"] = 0.0

        if features["total_in_value"] > 0:
            features["flow_ratio"] = float(features["total_out_value"] / features["total_in_value"])
        else:
            features["flow_ratio"] = 1.0 if features["total_out_value"] > 0 else 0.0

        features["value_entropy"] = self._calculate_value_entropy(all_values)

        timestamps = [e["timestamp"] for e in edges if e["timestamp"] > 0]
        if len(timestamps) >= 2:
            timestamps.sort()
            intervals = np.diff(timestamps)
            features["avg_time_interval"] = float(np.mean(intervals))
            features["std_time_interval"] = float(np.std(intervals)) if len(intervals) > 1 else 0.0
            features["min_time_interval"] = float(np.min(intervals))
            features["time_span"] = float(timestamps[-1] - timestamps[0])
        else:
            features["avg_time_interval"] = 0.0
            features["std_time_interval"] = 0.0
            features["min_time_interval"] = 0.0
            features["time_span"] = 0.0

        unique_senders = {e["from"] for e in edges if e["from"] and e["to"] == target_address}
        unique_receivers = {e["to"] for e in edges if e["to"] and e["from"] == target_address}

        features["unique_senders"] = float(len(unique_senders))
        features["unique_receivers"] = float(len(unique_receivers))

        if features["in_degree"] > 0:
            features["sender_diversity"] = float(len(unique_senders) / features["in_degree"])
        else:
            features["sender_diversity"] = 0.0

        if features["out_degree"] > 0:
            features["receiver_diversity"] = float(len(unique_receivers) / features["out_degree"])
        else:
            features["receiver_diversity"] = 0.0

        adjacency: Dict[str, List[str]] = defaultdict(list)
        for e in edges:
            if e["from"] and e["to"]:
                adjacency[e["from"]].append(e["to"])

        clustering_coeff = self._calculate_clustering_coefficient(target_address, adjacency)
        features["clustering_coefficient"] = clustering_coeff

        features["ego_density"] = self._calculate_ego_density(target_address, nodes, edges)

        features["page_rank"] = self._calculate_pagerank(target_address, nodes, edges)

        features["anomaly_pattern_score"] = self._calculate_anomaly_pattern_score(
            target_address, edges, features
        )

        return features

    def _calculate_value_entropy(self, values: List[float]) -> float:
        if not values or sum(values) == 0:
            return 0.0

        total = sum(values)
        probabilities = [v / total for v in values if v > 0]

        if not probabilities:
            return 0.0

        entropy = -sum(p * np.log2(p) for p in probabilities)
        max_entropy = np.log2(len(probabilities)) if len(probabilities) > 1 else 1.0

        return float(entropy / max_entropy if max_entropy > 0 else 0.0)

    def _calculate_clustering_coefficient(
        self,
        node: str,
        adjacency: Dict[str, List[str]]
    ) -> float:
        neighbors = set(adjacency.get(node, []))

        if len(neighbors) < 2:
            return 0.0

        links_between_neighbors = 0
        neighbor_list = list(neighbors)

        for i in range(len(neighbor_list)):
            for j in range(i + 1, len(neighbor_list)):
                n1 = neighbor_list[i]
                n2 = neighbor_list[j]
                if n2 in adjacency.get(n1, []):
                    links_between_neighbors += 1

        possible_links = len(neighbors) * (len(neighbors) - 1) / 2

        return float(links_between_neighbors / possible_links if possible_links > 0 else 0.0)

    def _calculate_ego_density(
        self,
        target: str,
        nodes: Set[str],
        edges: List[Dict[str, Any]]
    ) -> float:
        n = len(nodes)
        if n < 2:
            return 0.0

        max_edges = n * (n - 1)
        actual_edges = len(edges)

        return float(actual_edges / max_edges if max_edges > 0 else 0.0)

    def _calculate_pagerank(
        self,
        target: str,
        nodes: Set[str],
        edges: List[Dict[str, Any]],
        damping: float = 0.85,
        iterations: int = 50
    ) -> float:
        node_list = list(nodes)
        n = len(node_list)
        if n == 0:
            return 0.0

        node_index = {node: i for i, node in enumerate(node_list)}

        out_links: Dict[int, List[int]] = defaultdict(list)
        for e in edges:
            if e["from"] in node_index and e["to"] in node_index:
                out_links[node_index[e["from"]]].append(node_index[e["to"]])

        pr = np.ones(n) / n

        for _ in range(iterations):
            new_pr = np.ones(n) * (1 - damping) / n
            for i in range(n):
                if out_links[i]:
                    contribution = pr[i] / len(out_links[i])
                    for j in out_links[i]:
                        new_pr[j] += damping * contribution
            pr = new_pr

        target_idx = node_index.get(target, 0)
        return float(pr[target_idx] * 100)

    def _calculate_anomaly_pattern_score(
        self,
        address: str,
        edges: List[Dict[str, Any]],
        features: Dict[str, float]
    ) -> float:
        score = 0.0

        if features.get("std_in_value", 0) > 0 and features.get("avg_in_value", 1) > 0:
            cv_in = features["std_in_value"] / features["avg_in_value"]
            if cv_in > 2.0:
                score += min(cv_in / 5.0, 0.3)

        if features.get("value_entropy", 0) < 0.3 and features.get("total_degree", 0) > 5:
            score += 0.2

        if features.get("min_time_interval", 3600) < 60 and features.get("total_degree", 0) > 5:
            burst_score = min(1.0, 3600.0 / (features["min_time_interval"] + 1))
            score += burst_score * 0.15

        if abs(features.get("flow_ratio", 1.0) - 1.0) < 0.05 and features.get("total_degree", 0) > 2:
            score += 0.2

        if features.get("sender_diversity", 0) < 0.2 and features.get("in_degree", 0) > 5:
            score += 0.15

        if features.get("receiver_diversity", 0) < 0.2 and features.get("out_degree", 0) > 5:
            score += 0.15

        if features.get("clustering_coefficient", 0) > 0.5 and features.get("total_degree", 0) > 3:
            score += 0.1

        return min(score, 1.0)

    def _compute_gnn_score(
        self,
        address: str,
        features: Dict[str, float],
        edges: List[Dict[str, Any]]
    ) -> float:
        weights = {
            "value_entropy": 0.15,
            "anomaly_pattern_score": 0.25,
            "flow_ratio": 0.1,
            "std_in_value": 0.1,
            "std_out_value": 0.1,
            "min_time_interval": 0.1,
            "sender_diversity": 0.05,
            "receiver_diversity": 0.05,
            "clustering_coefficient": 0.05,
            "page_rank": 0.05
        }

        normalized_features = self._normalize_features(features)

        score = 0.0
        for feature, weight in weights.items():
            if feature in normalized_features:
                score += normalized_features[feature] * weight

        return min(max(score * 100, 0.0), 100.0)

    def _normalize_features(self, features: Dict[str, float]) -> Dict[str, float]:
        normalized = {}

        for key, value in features.items():
            if value is None:
                normalized[key] = 0.0
                continue

            if key == "value_entropy":
                normalized[key] = 1.0 - min(value, 1.0)
            elif key == "anomaly_pattern_score":
                normalized[key] = min(value, 1.0)
            elif key == "flow_ratio":
                normalized[key] = min(abs(value - 1.0) * 2, 1.0)
            elif key in ["std_in_value", "std_out_value"]:
                normalized[key] = min(value / 10.0, 1.0) if value > 0 else 0.0
            elif key == "min_time_interval":
                normalized[key] = min(1.0, 3600.0 / (value + 1)) if value < 3600 else 0.0
            elif key in ["sender_diversity", "receiver_diversity"]:
                normalized[key] = 1.0 - min(value, 1.0)
            elif key == "clustering_coefficient":
                normalized[key] = min(value * 2, 1.0)
            elif key == "page_rank":
                normalized[key] = min(value / 50.0, 1.0)
            else:
                normalized[key] = 0.0

        return normalized

    def _compute_feature_importance(
        self,
        features: Dict[str, float],
        total_score: float
    ) -> Dict[str, float]:
        importance = {}
        top_features = [
            "value_entropy", "anomaly_pattern_score", "flow_ratio",
            "std_in_value", "min_time_interval", "clustering_coefficient"
        ]

        for f in top_features:
            if f in features:
                importance[f] = round(abs(features[f]), 4)

        total = sum(importance.values()) if importance else 1.0
        return {k: round(v / total, 4) for k, v in importance.items()}

    def _get_risk_level(self, score: float) -> str:
        if score >= 75:
            return "critical"
        elif score >= 50:
            return "high"
        elif score >= 25:
            return "medium"
        else:
            return "low"

    async def explain_anomaly_score(
        self,
        address: str,
        anomaly_result: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        explanations = []
        features = anomaly_result.get("features", {})
        importance = anomaly_result.get("feature_importance", {})
        score = anomaly_result.get("anomaly_score", 0.0)

        if features.get("value_entropy", 1.0) < 0.3:
            explanations.append({
                "type": "value_pattern",
                "severity": "high",
                "description": "交易金额分布高度集中，显示出结构化交易特征",
                "contribution": importance.get("value_entropy", 0) * 100
            })

        if features.get("anomaly_pattern_score", 0) > 0.5:
            explanations.append({
                "type": "anomaly_pattern",
                "severity": "high",
                "description": "检测到多种异常交易模式组合",
                "contribution": importance.get("anomaly_pattern_score", 0) * 100
            })

        if abs(features.get("flow_ratio", 1.0) - 1.0) < 0.1 and features.get("total_degree", 0) > 2:
            explanations.append({
                "type": "balanced_flow",
                "severity": "medium",
                "description": "流入和流出金额几乎相等，可能是中转地址",
                "contribution": importance.get("flow_ratio", 0) * 100
            })

        if features.get("min_time_interval", 3600) < 300 and features.get("total_degree", 0) > 5:
            explanations.append({
                "type": "burst_trading",
                "severity": "medium",
                "description": f"交易间隔极短（最短{features['min_time_interval']:.0f}秒），显示自动化交易特征",
                "contribution": importance.get("min_time_interval", 0) * 100
            })

        if features.get("clustering_coefficient", 0) > 0.4:
            explanations.append({
                "type": "tight_cluster",
                "severity": "low",
                "description": "关联地址之间存在密集交易，可能属于同一实体网络",
                "contribution": importance.get("clustering_coefficient", 0) * 100
            })

        if features.get("sender_diversity", 1.0) < 0.3 and features.get("in_degree", 0) > 5:
            explanations.append({
                "type": "concentrated_source",
                "severity": "low",
                "description": "资金来源高度集中",
                "contribution": importance.get("sender_diversity", 0) * 100
            })

        explanations.sort(key=lambda x: x["contribution"], reverse=True)

        return explanations
