import os
import pickle
import hashlib
import networkx as nx
import redis
from typing import List, Tuple, Optional

class NetworkProcessor:
    def __init__(self, redis_host: str = 'localhost', redis_port: int = 6379, redis_db: int = 0, use_cache: bool = True):
        self.use_cache = use_cache
        self.redis_client = None
        self.cache_ttl = 3600 * 24

        if use_cache:
            try:
                self.redis_client = redis.Redis(
                    host=redis_host, port=redis_port, db=redis_db,
                    decode_responses=False, socket_connect_timeout=2,
                    socket_timeout=2
                )
                self.redis_client.ping()
            except (redis.RedisError, ConnectionError):
                print("Warning: Redis connection failed, caching disabled")
                self.redis_client = None
                self.use_cache = False

    def _get_file_hash(self, file_path: str) -> str:
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            chunk = f.read(8192)
            while chunk:
                hasher.update(chunk)
                chunk = f.read(8192)
        return hasher.hexdigest()

    def _get_cache_key(self, file_path: str, prefix: str = 'network') -> str:
        file_hash = self._get_file_hash(file_path)
        return f"{prefix}:{file_hash}"

    def load_edge_list(self, file_path: str) -> List[Tuple[int, int, float]]:
        edges = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 3:
                    u, v, w = int(parts[0]), int(parts[1]), float(parts[2])
                    edges.append((u, v, w))
                elif len(parts) == 2:
                    u, v = int(parts[0]), int(parts[1])
                    edges.append((u, v, 1.0))
        return edges

    def build_graph(self, edges: List[Tuple[int, int, float]], directed: bool = False) -> nx.Graph:
        if directed:
            G = nx.DiGraph()
        else:
            G = nx.Graph()

        max_weight = max(w for _, _, w in edges) if edges else 1.0

        for u, v, w in edges:
            normalized_weight = w / max_weight
            propagation_prob = min(0.8, normalized_weight * 0.8)
            G.add_edge(u, v, weight=w, propagation_prob=propagation_prob)

        return G

    def preprocess_network(self, file_path: str, directed: bool = False, use_cache: bool = True) -> nx.Graph:
        use_cache = use_cache and self.use_cache and self.redis_client is not None

        if use_cache:
            cache_key = self._get_cache_key(file_path)
            try:
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    return pickle.loads(cached_data)
            except (redis.RedisError, pickle.PickleError, AttributeError):
                pass

        edges = self.load_edge_list(file_path)
        G = self.build_graph(edges, directed)

        G.graph['nodes_sorted_by_degree'] = sorted(G.nodes(), key=lambda x: G.degree(x), reverse=True)
        G.graph['edge_count'] = G.number_of_edges()
        G.graph['node_count'] = G.number_of_nodes()

        if use_cache:
            try:
                cache_key = self._get_cache_key(file_path)
                self.redis_client.setex(cache_key, self.cache_ttl, pickle.dumps(G))
            except (redis.RedisError, AttributeError):
                pass

        return G

    def get_adjacency_with_probs(self, G: nx.Graph) -> dict:
        adj = {}
        for node in G.nodes():
            neighbors = []
            for neighbor in G.neighbors(node):
                prob = G[node][neighbor].get('propagation_prob', 0.1)
                neighbors.append((neighbor, prob))
            adj[node] = neighbors
        return adj

    def clear_cache(self, file_path: Optional[str] = None):
        if self.redis_client is None:
            return
        try:
            if file_path:
                cache_key = self._get_cache_key(file_path)
                self.redis_client.delete(cache_key)
            else:
                for key in self.redis_client.keys('network:*'):
                    self.redis_client.delete(key)
        except (redis.RedisError, AttributeError):
            pass
