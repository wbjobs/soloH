from typing import Optional, Dict, Any, List, Tuple, Set
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.services.base import BaseService
from app.repositories import GraphRepository
from app.models.blockchain import Transaction, GraphEdge


class GraphService(BaseService[GraphRepository]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, GraphRepository)

    async def build_transaction_graph(self, transactions: List[Transaction]) -> List[GraphEdge]:
        return await self.repository.build_graph_edges(transactions)

    async def extract_subgraph(
        self,
        center_address: str,
        depth: int = 2,
        min_value: float = 0
    ) -> Dict[str, Any]:
        edges = await self.repository.get_subgraph(center_address, depth, min_value)

        nodes: Set[str] = {center_address}
        edge_list = []

        for edge in edges:
            nodes.add(edge.from_address)
            nodes.add(edge.to_address)
            edge_list.append({
                "id": edge.id,
                "from": edge.from_address,
                "to": edge.to_address,
                "value": edge.value,
                "txid": edge.txid,
                "block_time": edge.block_time.isoformat() if edge.block_time else None
            })

        node_list = [{"id": addr} for addr in nodes]

        return {
            "nodes": node_list,
            "edges": edge_list,
            "center": center_address,
            "depth": depth,
            "node_count": len(node_list),
            "edge_count": len(edge_list)
        }

    async def filter_graph(
        self,
        graph_data: Dict[str, Any],
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not filters:
            return graph_data

        edges = graph_data.get("edges", [])
        nodes = graph_data.get("nodes", [])

        filtered_edges = []
        included_nodes: Set[str] = set()

        min_value = filters.get("min_value", 0)
        start_time = filters.get("start_time")
        end_time = filters.get("end_time")

        for edge in edges:
            if edge["value"] < min_value:
                continue

            if start_time and edge["block_time"]:
                edge_time = datetime.fromisoformat(edge["block_time"].replace('Z', '+00:00'))
                if edge_time < start_time:
                    continue

            if end_time and edge["block_time"]:
                edge_time = datetime.fromisoformat(edge["block_time"].replace('Z', '+00:00'))
                if edge_time > end_time:
                    continue

            filtered_edges.append(edge)
            included_nodes.add(edge["from"])
            included_nodes.add(edge["to"])

        filtered_nodes = [node for node in nodes if node["id"] in included_nodes]

        return {
            **graph_data,
            "nodes": filtered_nodes,
            "edges": filtered_edges,
            "node_count": len(filtered_nodes),
            "edge_count": len(filtered_edges)
        }

    async def calculate_graph_metrics(self, graph_data: Dict[str, Any]) -> Dict[str, Any]:
        edges = graph_data.get("edges", [])
        nodes = graph_data.get("nodes", [])
        node_ids = {node["id"] for node in nodes}

        in_degree: Dict[str, int] = {n: 0 for n in node_ids}
        out_degree: Dict[str, int] = {n: 0 for n in node_ids}
        in_value: Dict[str, float] = {n: 0.0 for n in node_ids}
        out_value: Dict[str, float] = {n: 0.0 for n in node_ids}

        for edge in edges:
            out_degree[edge["from"]] = out_degree.get(edge["from"], 0) + 1
            in_degree[edge["to"]] = in_degree.get(edge["to"], 0) + 1
            out_value[edge["from"]] = out_value.get(edge["from"], 0.0) + edge["value"]
            in_value[edge["to"]] = in_value.get(edge["to"], 0.0) + edge["value"]

        node_metrics = {}
        for node_id in node_ids:
            total_degree = in_degree[node_id] + out_degree[node_id]
            total_value = in_value[node_id] + out_value[node_id]
            net_value = in_value[node_id] - out_value[node_id]

            node_metrics[node_id] = {
                "in_degree": in_degree[node_id],
                "out_degree": out_degree[node_id],
                "total_degree": total_degree,
                "in_value": in_value[node_id],
                "out_value": out_value[node_id],
                "total_value": total_value,
                "net_value": net_value
            }

        total_transaction_value = sum(edge["value"] for edge in edges)
        avg_degree = (sum(in_degree.values()) + sum(out_degree.values())) / max(len(nodes), 1)

        return {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "total_transaction_value": total_transaction_value,
            "avg_degree": avg_degree,
            "density": len(edges) / max(len(nodes) * (len(nodes) - 1), 1) * 2 if len(nodes) > 1 else 0,
            "node_metrics": node_metrics,
            "hubs": sorted(
                node_metrics.items(),
                key=lambda x: x[1]["total_degree"],
                reverse=True
            )[:10],
            "top_receivers": sorted(
                node_metrics.items(),
                key=lambda x: x[1]["in_value"],
                reverse=True
            )[:10],
            "top_senders": sorted(
                node_metrics.items(),
                key=lambda x: x[1]["out_value"],
                reverse=True
            )[:10]
        }
