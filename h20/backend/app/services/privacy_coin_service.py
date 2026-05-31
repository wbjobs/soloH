from typing import Optional, Dict, Any, List, Set, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from collections import defaultdict
import re
from datetime import datetime, timedelta

from app.services.base import BaseService
from app.repositories import TransactionRepository, AddressRepository, GraphRepository
from app.models.blockchain import Transaction, Address, GraphEdge


PRIVACY_COIN_PATTERNS = {
    "monero": {
        "name": "Monero (XMR)",
        "patterns": [
            r"^4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}$",
            r"^8[1-9A-HJ-NP-Za-km-z]{94}$"
        ],
        "description": "Monero 标准地址",
        "risk_level": "high"
    },
    "zcash": {
        "name": "Zcash (ZEC)",
        "patterns": [
            r"^t1[a-zA-Z0-9]{33}$",
            r"^t3[a-zA-Z0-9]{33}$",
            r"^zs1[a-z0-9]{75}$",
            r"^zcl1[a-z0-9]{75}$"
        ],
        "description": "Zcash 透明地址和屏蔽地址",
        "risk_level": "high"
    },
    "dash": {
        "name": "Dash (DASH)",
        "patterns": [
            r"^X[1-9A-HJ-NP-Za-km-z]{33}$",
            r"^7[1-9A-HJ-NP-Za-km-z]{33}$"
        ],
        "description": "Dash 普通地址和PrivateSend地址",
        "risk_level": "medium"
    },
    "zcash_shielded": {
        "name": "Zcash Shielded",
        "patterns": [
            r"^utxo1[a-z0-9]+$"
        ],
        "description": "Zcash 屏蔽交易输出",
        "risk_level": "critical"
    },
    "coinjoin": {
        "name": "CoinJoin",
        "patterns": [
            r"^bc1q[a-z0-9]{38,}$"
        ],
        "description": "CoinJoin 混币服务地址",
        "risk_level": "high"
    },
    "tornado_cash": {
        "name": "Tornado Cash",
        "patterns": [
            r"^0x[a-fA-F0-9]{40}$"
        ],
        "description": "Tornado Cash 混币合约（以太坊）",
        "risk_level": "critical"
    },
    "wasabi_wallet": {
        "name": "Wasabi Wallet",
        "patterns": [
            r"^bc1q[02][a-z0-9]{37,}$"
        ],
        "description": "Wasabi Wallet CoinJoin 地址",
        "risk_level": "high"
    },
    "samourai_wallet": {
        "name": "Samourai Wallet",
        "patterns": [
            r"^bc1qs[a-z0-9]{37,}$"
        ],
        "description": "Samourai Wallet Whirlpool 混币",
        "risk_level": "high"
    }
}

KNOWN_PRIVACY_GATEWAYS = {
    "changenow": {
        "name": "ChangeNow",
        "addresses": [
            "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq",
            "bc1qrh7wr4v8u64c7a9qk2e67w5u6x9p0u9h7y4x7v"
        ],
        "type": "exchange",
        "risk_level": "medium"
    },
    "fixedfloat": {
        "name": "FixedFloat",
        "addresses": [
            "bc1q9v8q7h8k9j6h5g4f3d2s1a0z9x8c7v6b5n4m3"
        ],
        "type": "exchange",
        "risk_level": "medium"
    },
    "mixer_service": {
        "name": "Generic Mixer",
        "addresses": [
            "bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h"
        ],
        "type": "mixer",
        "risk_level": "high"
    }
}


class PrivacyCoinAnalysisService(BaseService[TransactionRepository]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, TransactionRepository)
        self.addr_repo = AddressRepository(db)
        self.graph_repo = GraphRepository(db)

    async def analyze_privacy_coin_associations(
        self,
        address: str,
        depth: int = 3
    ) -> Dict[str, Any]:
        subgraph = await self.graph_repo.get_subgraph(address, depth=depth, min_value=0.0)

        detected_privacy_coins: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        associated_addresses: Set[str] = set()
        suspicious_transactions: List[Dict[str, Any]] = []
        total_privacy_value = 0.0

        nodes, edges = self._extract_graph_data(subgraph, address)

        for node in nodes:
            privacy_type = self._identify_privacy_coin_address(node)
            if privacy_type:
                coin_info = PRIVACY_COIN_PATTERNS[privacy_type]
                detected_privacy_coins[privacy_type].append({
                    "address": node,
                    "coin_name": coin_info["name"],
                    "description": coin_info["description"],
                    "risk_level": coin_info["risk_level"]
                })
                associated_addresses.add(node)

        for edge in edges:
            from_addr = edge["from"]
            to_addr = edge["to"]

            from_privacy = self._identify_privacy_coin_address(from_addr)
            to_privacy = self._identify_privacy_coin_address(to_addr)

            gateway_info = self._check_gateway_association(from_addr, to_addr)

            if from_privacy or to_privacy or gateway_info:
                suspicious_transactions.append({
                    "txid": edge["txid"],
                    "from_address": from_addr,
                    "to_address": to_addr,
                    "value": edge["value"],
                    "timestamp": edge["timestamp"],
                    "privacy_type": from_privacy or to_privacy,
                    "gateway_info": gateway_info,
                    "direction": "incoming" if to_addr == address else "outgoing"
                })
                total_privacy_value += edge["value"]
                if from_addr and from_addr != address:
                    associated_addresses.add(from_addr)
                if to_addr and to_addr != address:
                    associated_addresses.add(to_addr)

        mixing_patterns = self._detect_mixing_patterns(address, edges)

        risk_score = self._calculate_privacy_risk_score(
            detected_privacy_coins,
            suspicious_transactions,
            mixing_patterns,
            total_privacy_value
        )

        cross_chain_links = await self._detect_cross_chain_links(
            address,
            associated_addresses,
            edges
        )

        return {
            "address": address,
            "overall_risk_score": risk_score,
            "risk_level": self._get_risk_level(risk_score),
            "detected_privacy_coins": dict(detected_privacy_coins),
            "privacy_coin_count": len(detected_privacy_coins),
            "associated_address_count": len(associated_addresses),
            "suspicious_transactions": suspicious_transactions,
            "total_privacy_related_value": total_privacy_value,
            "mixing_patterns": mixing_patterns,
            "cross_chain_links": cross_chain_links,
            "analysis_depth": depth,
            "analysis_timestamp": datetime.utcnow().isoformat()
        }

    async def batch_analyze_privacy_associations(
        self,
        addresses: List[str],
        depth: int = 2
    ) -> List[Dict[str, Any]]:
        results = []
        for address in addresses:
            result = await self.analyze_privacy_coin_associations(address, depth)
            results.append(result)
        return results

    def _identify_privacy_coin_address(self, address: Optional[str]) -> Optional[str]:
        if not address:
            return None

        for coin_type, coin_info in PRIVACY_COIN_PATTERNS.items():
            for pattern in coin_info["patterns"]:
                if re.match(pattern, address):
                    return coin_type

        return None

    def _check_gateway_association(
        self,
        from_addr: Optional[str],
        to_addr: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        for gateway_id, gateway_info in KNOWN_PRIVACY_GATEWAYS.items():
            if from_addr in gateway_info["addresses"] or to_addr in gateway_info["addresses"]:
                return {
                    "gateway_id": gateway_id,
                    "name": gateway_info["name"],
                    "type": gateway_info["type"],
                    "risk_level": gateway_info["risk_level"]
                }
        return None

    def _extract_graph_data(
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

    def _detect_mixing_patterns(
        self,
        address: str,
        edges: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        patterns = []

        in_edges = [e for e in edges if e["to"] == address]
        out_edges = [e for e in edges if e["from"] == address]

        if len(in_edges) >= 5 and len(out_edges) >= 5:
            in_values = sorted([e["value"] for e in in_edges])
            out_values = sorted([e["value"] for e in out_edges])

            in_total = sum(in_values)
            out_total = sum(out_values)

            if in_total > 0 and abs(in_total - out_total) / in_total < 0.1:
                unique_in = {e["from"] for e in in_edges}
                unique_out = {e["to"] for e in out_edges}

                if len(unique_in) >= 3 and len(unique_out) >= 3:
                    patterns.append({
                        "type": "value_matching",
                        "description": "总流入与总流出金额高度匹配，疑似混币中转",
                        "confidence": min(0.9, (len(unique_in) + len(unique_out)) / 10),
                        "evidence": {
                            "in_count": len(in_edges),
                            "out_count": len(out_edges),
                            "in_total": in_total,
                            "out_total": out_total,
                            "match_ratio": 1 - abs(in_total - out_total) / max(in_total, out_total)
                        }
                    })

        if len(edges) >= 5:
            timestamps = sorted([e["timestamp"] for e in edges if e["timestamp"] > 0])
            if len(timestamps) >= 5:
                intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
                avg_interval = sum(intervals) / len(intervals)

                if avg_interval < 3600 and max(intervals) < 7200:
                    values = [e["value"] for e in edges]
                    std_val = (sum((v - sum(values)/len(values))**2 for v in values) / len(values)) ** 0.5

                    if std_val < 0.1 * sum(values) / len(values):
                        patterns.append({
                            "type": "automated_mixing",
                            "description": "在短时间内发生多笔金额相近的交易，疑似自动化混币",
                            "confidence": 0.75,
                            "evidence": {
                                "avg_interval_seconds": avg_interval,
                                "transaction_count": len(edges),
                                "value_std": std_val
                            }
                        })

        in_by_source: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for e in in_edges:
            if e["from"]:
                in_by_source[e["from"]].append(e)

        for source, txs in in_by_source.items():
            if len(txs) >= 3:
                values = [t["value"] for t in txs]
                if max(values) < 2 * min(values):
                    patterns.append({
                        "type": "structuring_split",
                        "description": f"从同一来源({source[:8]}...)收到多笔金额相近的交易，疑似结构化拆分",
                        "confidence": 0.7,
                        "evidence": {
                            "source_address": source,
                            "transaction_count": len(txs),
                            "min_value": min(values),
                            "max_value": max(values)
                        }
                    })

        return patterns

    def _calculate_privacy_risk_score(
        self,
        detected_coins: Dict[str, List[Dict[str, Any]]],
        suspicious_txs: List[Dict[str, Any]],
        mixing_patterns: List[Dict[str, Any]],
        total_value: float
    ) -> float:
        score = 0.0

        risk_weights = {
            "critical": 30,
            "high": 20,
            "medium": 10,
            "low": 5
        }

        for coin_type, matches in detected_coins.items():
            if matches:
                coin_info = PRIVACY_COIN_PATTERNS[coin_type]
                weight = risk_weights.get(coin_info["risk_level"], 10)
                score += weight * len(matches)

        for pattern in mixing_patterns:
            confidence = pattern.get("confidence", 0.5)
            pattern_type = pattern.get("type", "")

            if pattern_type == "value_matching":
                score += 25 * confidence
            elif pattern_type == "automated_mixing":
                score += 20 * confidence
            elif pattern_type == "structuring_split":
                score += 15 * confidence

        if suspicious_txs:
            incoming_count = len([t for t in suspicious_txs if t["direction"] == "incoming"])
            outgoing_count = len([t for t in suspicious_txs if t["direction"] == "outgoing"])

            if incoming_count > 0:
                score += min(incoming_count * 5, 20)
            if outgoing_count > 0:
                score += min(outgoing_count * 5, 20)

        if total_value > 0:
            value_score = min(10, total_value)
            score += value_score

        return min(score, 100.0)

    async def _detect_cross_chain_links(
        self,
        target_address: str,
        associated_addresses: Set[str],
        edges: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        cross_chain_links = []

        for addr in associated_addresses:
            if addr == target_address:
                continue

            privacy_type = self._identify_privacy_coin_address(addr)
            if privacy_type:
                coin_info = PRIVACY_COIN_PATTERNS[privacy_type]

                related_txs = [
                    e for e in edges
                    if e["from"] == addr or e["to"] == addr
                ]

                total_value = sum(e["value"] for e in related_txs)

                cross_chain_links.append({
                    "type": "privacy_coin",
                    "privacy_type": privacy_type,
                    "coin_name": coin_info["name"],
                    "address": addr,
                    "description": coin_info["description"],
                    "risk_level": coin_info["risk_level"],
                    "transaction_count": len(related_txs),
                    "total_value": total_value,
                    "first_seen": min([e["timestamp"] for e in related_txs]) if related_txs else None,
                    "last_seen": max([e["timestamp"] for e in related_txs]) if related_txs else None
                })

        for edge in edges:
            gateway_info = self._check_gateway_association(edge["from"], edge["to"])
            if gateway_info:
                cross_chain_links.append({
                    "type": "privacy_gateway",
                    "gateway_name": gateway_info["name"],
                    "gateway_type": gateway_info["type"],
                    "transaction": {
                        "txid": edge["txid"],
                        "from": edge["from"],
                        "to": edge["to"],
                        "value": edge["value"]
                    },
                    "risk_level": gateway_info["risk_level"]
                })

        return cross_chain_links

    def _get_risk_level(self, score: float) -> str:
        if score >= 75:
            return "critical"
        elif score >= 50:
            return "high"
        elif score >= 25:
            return "medium"
        else:
            return "low"

    async def generate_privacy_threat_intel(
        self,
        privacy_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        risk_level = privacy_analysis.get("risk_level", "low")
        detected_coins = privacy_analysis.get("detected_privacy_coins", {})
        cross_chain_links = privacy_analysis.get("cross_chain_links", [])
        mixing_patterns = privacy_analysis.get("mixing_patterns", [])

        threat_indicators = []
        recommended_actions = []

        if risk_level in ["critical", "high"]:
            recommended_actions.extend([
                "增强对该地址的监控力度",
                "冻结相关交易进行人工审核",
                "上报至合规部门和监管机构",
                "限制与该地址的进一步交易"
            ])
        elif risk_level == "medium":
            recommended_actions.extend([
                "加强交易监控",
                "进行进一步的尽职调查",
                "记录相关交易以备后续审计"
            ])

        if detected_coins:
            coin_names = [
                PRIVACY_COIN_PATTERNS.get(ct, {}).get("name", ct)
                for ct in detected_coins.keys()
            ]
            threat_indicators.append({
                "type": "privacy_coin_interaction",
                "description": f"与以下隐私币相关地址有交互: {', '.join(coin_names)}",
                "severity": "high"
            })

        if mixing_patterns:
            threat_indicators.append({
                "type": "mixing_pattern_detected",
                "description": f"检测到 {len(mixing_patterns)} 种混币模式",
                "severity": "high"
            })

        if cross_chain_links:
            gateway_count = len([l for l in cross_chain_links if l.get("type") == "privacy_gateway"])
            if gateway_count > 0:
                threat_indicators.append({
                    "type": "privacy_gateway_interaction",
                    "description": f"与 {gateway_count} 个隐私币网关/交易所存在交易",
                    "severity": "medium"
                })

        return {
            "threat_level": risk_level,
            "threat_indicators": threat_indicators,
            "recommended_actions": recommended_actions,
            "summary": self._generate_threat_summary(privacy_analysis)
        }

    def _generate_threat_summary(self, analysis: Dict[str, Any]) -> str:
        risk_level = analysis.get("risk_level", "low")
        coin_count = analysis.get("privacy_coin_count", 0)
        tx_count = len(analysis.get("suspicious_transactions", []))
        total_value = analysis.get("total_privacy_related_value", 0)

        if risk_level == "critical":
            return (f"极高风险：该地址与 {coin_count} 类隐私币有 {tx_count} 笔交易，"
                    f"总金额 {total_value:.4f} BTC，强烈建议进行深入调查。")
        elif risk_level == "high":
            return (f"高风险：该地址与 {coin_count} 类隐私币存在关联，"
                    f"涉及 {tx_count} 笔交易，总金额 {total_value:.4f} BTC，需重点关注。")
        elif risk_level == "medium":
            return (f"中风险：检测到潜在的隐私币关联特征，"
                    f"涉及 {tx_count} 笔交易，建议进行进一步调查。")
        else:
            return "低风险：未检测到明显的隐私币关联或混币特征。"
