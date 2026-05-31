"""State machine inference from message sequences."""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict, Counter
import hashlib
import struct
from collections import deque


@dataclass
class MessageCluster:
    """A cluster of similar messages representing a state."""
    cluster_id: int
    signature: bytes
    messages: List[bytes] = field(default_factory=list)
    representative: bytes = b""
    count: int = 0

    def add(self, msg: bytes):
        self.messages.append(msg)
        self.count += 1
        if not self.representative or len(msg) > len(self.representative):
            self.representative = msg


@dataclass
class StateTransition:
    """Represents a transition between states."""
    from_state: int
    to_state: int
    count: int = 0
    probability: float = 0.0


@dataclass
class StateMachine:
    """Inferred protocol state machine."""
    states: Dict[int, MessageCluster] = field(default_factory=dict)
    transitions: List[StateTransition] = field(default_factory=list)
    transition_matrix: Dict[Tuple[int, int], int] = field(default_factory=dict)
    initial_states: Set[int] = field(default_factory=set)
    terminal_states: Set[int] = field(default_factory=set)
    total_transitions: int = 0
    cluster_algorithm: str = 'prefix'
    anomalies: List[Dict] = field(default_factory=list)
    message_sequence: List[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'num_states': len(self.states),
            'num_transitions': len(self.transitions),
            'total_transitions': self.total_transitions,
            'initial_states': list(self.initial_states),
            'terminal_states': list(self.terminal_states),
            'states': {
                str(k): {
                    'count': v.count,
                    'signature': v.signature.hex(),
                    'representative': v.representative.hex()[:64],
                    'avg_length': sum(len(m) for m in v.messages) / max(len(v.messages), 1)
                }
                for k, v in self.states.items()
            },
            'transitions': [
                {
                    'from': t.from_state,
                    'to': t.to_state,
                    'count': t.count,
                    'probability': t.probability
                }
                for t in self.transitions
            ]
        }

    def to_dot(self) -> str:
        """Generate Graphviz DOT representation."""
        lines = ['digraph ProtocolStateMachine {']
        lines.append('  rankdir=LR;')
        lines.append('  node [shape=circle, style=filled, fontname=Arial];')

        for state_id, cluster in self.states.items():
            avg_len = sum(len(m) for m in cluster.messages) / max(len(cluster.messages), 1)
            color = '#a8d8ea' if state_id in self.initial_states else '#ffd3b6'
            if state_id in self.terminal_states:
                color = '#aaa0ff'

            label = f'S{state_id}\\n({cluster.count})\\n{avg_len:.0f}B'
            lines.append(f'  S{state_id} [label="{label}", fillcolor="{color}"];')

        lines.append('  "" [shape=none, label=""];')
        for init in self.initial_states:
            lines.append(f'  "" -> S{init};')

        for t in self.transitions:
            if t.probability > 0.1:
                width = max(1, int(t.probability * 3))
                label = f"{t.count} ({t.probability:.0%})"
                lines.append(f'  S{t.from_state} -> S{t.to_state} [label="{label}", penwidth={width}];')

        lines.append('}')
        return '\n'.join(lines)

    def detect_cycles(self) -> List[List[int]]:
        """Detect cycles in the state transition graph using DFS."""
        cycles = []
        visited = set()
        path = []
        path_set = set()

        def dfs(state_id):
            visited.add(state_id)
            path.append(state_id)
            path_set.add(state_id)

            for t in self.transitions:
                if t.from_state == state_id:
                    if t.to_state in path_set:
                        cycle_start = path.index(t.to_state)
                        cycle = path[cycle_start:] + [t.to_state]
                        cycles.append(cycle)
                    elif t.to_state not in visited:
                        dfs(t.to_state)

            path.pop()
            path_set.discard(state_id)

        for state_id in self.states:
            if state_id not in visited:
                dfs(state_id)

        unique_cycles = []
        seen = set()
        for cycle in cycles:
            key = tuple(sorted(set(cycle)))
            if key not in seen:
                seen.add(key)
                unique_cycles.append(cycle)

        return unique_cycles

    def detect_anomalies(self, min_probability: float = 0.05) -> List[Dict]:
        """Detect anomalous transitions with low probability."""
        anomalies = []

        for t in self.transitions:
            if t.probability > 0 and t.probability < min_probability:
                anomalies.append({
                    'type': 'low_probability_transition',
                    'from_state': t.from_state,
                    'to_state': t.to_state,
                    'probability': t.probability,
                    'count': t.count,
                    'description': f'Transition S{t.from_state} -> S{t.to_state} has low probability ({t.probability:.1%})'
                })

        out_degree = defaultdict(int)
        for t in self.transitions:
            out_degree[t.from_state] += t.count

        for state_id, cluster in self.states.items():
            total_out = out_degree.get(state_id, 0)
            if cluster.count > 3 and total_out == 0:
                anomalies.append({
                    'type': 'dead_end_state',
                    'state_id': state_id,
                    'message_count': cluster.count,
                    'description': f'State S{state_id} has {cluster.count} messages but no outgoing transitions'
                })

        if len(self.message_sequence) >= 3:
            for i in range(1, len(self.message_sequence) - 1):
                prev_s = self.message_sequence[i - 1]
                curr_s = self.message_sequence[i]
                next_s = self.message_sequence[i + 1]
                if prev_s == next_s and prev_s != curr_s:
                    pass

        self.anomalies = anomalies
        return anomalies


class StateMachineInferrer:
    """Infers protocol state machine from message sequences."""

    def __init__(self, signature_length: int = 8, similarity_threshold: float = 0.8,
                 cluster_algorithm: str = 'prefix'):
        self.signature_length = signature_length
        self.similarity_threshold = similarity_threshold
        self.cluster_algorithm = cluster_algorithm

    def _extract_signature(self, msg: bytes) -> bytes:
        """Extract message signature for clustering."""
        if len(msg) >= self.signature_length:
            return msg[:self.signature_length]
        return msg + b'\x00' * (self.signature_length - len(msg))

    def _calculate_similarity(self, msg1: bytes, msg2: bytes) -> float:
        """Calculate byte-level similarity between two messages."""
        min_len = min(len(msg1), len(msg2))
        if min_len == 0:
            return 0.0

        matches = sum(1 for i in range(min_len) if msg1[i] == msg2[i])
        return matches / min_len

    def _cluster_by_prefix(self, messages: List[bytes]) -> Dict[bytes, List[bytes]]:
        """Cluster messages by prefix signature."""
        clusters: Dict[bytes, List[bytes]] = defaultdict(list)
        for msg in messages:
            sig = self._extract_signature(msg)
            clusters[sig].append(msg)
        return clusters

    def _cluster_by_similarity(self, messages: List[bytes]) -> List[List[bytes]]:
        """Cluster messages by similarity using greedy approach."""
        clusters: List[List[bytes]] = []
        cluster_centers: List[bytes] = []

        for msg in messages:
            best_cluster = -1
            best_similarity = 0.0

            for i, center in enumerate(cluster_centers):
                sim = self._calculate_similarity(msg, center)
                if sim > best_similarity:
                    best_similarity = sim
                    best_cluster = i

            if best_similarity >= self.similarity_threshold and best_cluster >= 0:
                clusters[best_cluster].append(msg)
                if len(msg) > len(cluster_centers[best_cluster]):
                    cluster_centers[best_cluster] = msg
            else:
                clusters.append([msg])
                cluster_centers.append(msg)

        return clusters

    def _cluster_by_length(self, messages: List[bytes]) -> Dict[int, List[bytes]]:
        """Cluster messages by length."""
        clusters: Dict[int, List[bytes]] = defaultdict(list)
        for msg in messages:
            clusters[len(msg)].append(msg)
        return clusters

    def _cluster_by_type_field(self, messages: List[bytes], type_offset: int = 3,
                               type_length: int = 1) -> Dict[int, List[bytes]]:
        """Cluster messages by a type field at specified offset."""
        clusters: Dict[int, List[bytes]] = defaultdict(list)
        for msg in messages:
            if type_offset + type_length <= len(msg):
                type_bytes = msg[type_offset:type_offset + type_length]
                type_val = int.from_bytes(type_bytes, byteorder='big', signed=False)
            else:
                type_val = -1
            clusters[type_val].append(msg)
        return clusters

    def infer(self, messages: List[bytes]) -> StateMachine:
        """Infer state machine from message sequence."""
        if len(messages) < 2:
            return StateMachine()

        print(f"[*] Inferring state machine from {len(messages)} messages...")

        clusters: Dict[bytes, List[bytes]]
        if self.cluster_algorithm == 'prefix':
            clusters = self._cluster_by_prefix(messages)
        elif self.cluster_algorithm == 'similarity':
            sim_clusters = self._cluster_by_similarity(messages)
            clusters = {self._extract_signature(c[0]): c for c in sim_clusters}
        elif self.cluster_algorithm == 'length':
            len_clusters = self._cluster_by_length(messages)
            clusters = {struct.pack('>I', k): v for k, v in len_clusters.items()}
        elif self.cluster_algorithm == 'type':
            type_clusters = self._cluster_by_type_field(messages)
            clusters = {struct.pack('>I', k): v for k, v in type_clusters.items()}
        else:
            clusters = self._cluster_by_prefix(messages)

        sig_to_id: Dict[bytes, int] = {}
        state_machine = StateMachine()
        state_machine.cluster_algorithm = self.cluster_algorithm

        for sig, msgs in clusters.items():
            state_id = len(sig_to_id)
            sig_to_id[sig] = state_id
            state_machine.states[state_id] = MessageCluster(
                cluster_id=state_id,
                signature=sig,
                messages=msgs,
                count=len(msgs),
                representative=msgs[0] if msgs else b""
            )

        if messages:
            first_sig = self._extract_signature(messages[0])
            if first_sig in sig_to_id:
                state_machine.initial_states.add(sig_to_id[first_sig])

            last_sig = self._extract_signature(messages[-1])
            if last_sig in sig_to_id:
                state_machine.terminal_states.add(sig_to_id[last_sig])

        transition_counts: Dict[Tuple[int, int], int] = defaultdict(int)
        message_sequence = []

        for msg in messages:
            sig = self._extract_signature(msg)
            if sig in sig_to_id:
                message_sequence.append(sig_to_id[sig])

        state_machine.message_sequence = message_sequence

        for i in range(len(messages) - 1):
            current_sig = self._extract_signature(messages[i])
            next_sig = self._extract_signature(messages[i + 1])

            if current_sig in sig_to_id and next_sig in sig_to_id:
                from_id = sig_to_id[current_sig]
                to_id = sig_to_id[next_sig]
                transition_counts[(from_id, to_id)] += 1

        state_machine.total_transitions = sum(transition_counts.values())

        from_counts: Dict[int, int] = defaultdict(int)
        for (from_id, _), count in transition_counts.items():
            from_counts[from_id] += count

        for (from_id, to_id), count in transition_counts.items():
            state_machine.transition_matrix[(from_id, to_id)] = count

            prob = count / max(from_counts[from_id], 1)
            state_machine.transitions.append(StateTransition(
                from_state=from_id,
                to_state=to_id,
                count=count,
                probability=prob
            ))

        state_machine.transitions.sort(key=lambda t: -t.count)

        print(f"[+] State machine inferred: {len(state_machine.states)} states, "
              f"{len(state_machine.transitions)} transitions")

        return state_machine

    def find_cycles(self, state_machine: StateMachine, max_length: int = 5) -> List[List[int]]:
        """Find repeating cycles in the state machine."""
        cycles = []
        seen = set()

        for start in state_machine.states:
            stack = [(start, [start])]
            while stack:
                current, path = stack.pop()
                if len(path) > max_length:
                    continue

                for t in state_machine.transitions:
                    if t.from_state == current:
                        if t.to_state == start and len(path) > 1:
                            cycle = tuple(path)
                            if cycle not in seen:
                                seen.add(cycle)
                                cycles.append(path.copy())
                        elif t.to_state not in path:
                            stack.append((t.to_state, path + [t.to_state]))

        cycles.sort(key=lambda c: len(c))
        return cycles

    def predict_next_state(self, state_machine: StateMachine, current_state: int) -> List[Tuple[int, float]]:
        """Predict possible next states with probabilities."""
        predictions = []
        for t in state_machine.transitions:
            if t.from_state == current_state:
                predictions.append((t.to_state, t.probability))

        predictions.sort(key=lambda x: -x[1])
        return predictions

    def detect_anomalies(self, state_machine: StateMachine, messages: List[bytes]) -> List[int]:
        """Detect anomalous transitions in the message sequence."""
        if len(messages) < 2:
            return []

        sig_to_id = {}
        for state_id, cluster in state_machine.states.items():
            sig_to_id[cluster.signature] = state_id

        anomalies = []
        allowed_transitions = set(state_machine.transition_matrix.keys())

        for i in range(len(messages) - 1):
            current_sig = self._extract_signature(messages[i])
            next_sig = self._extract_signature(messages[i + 1])

            if current_sig in sig_to_id and next_sig in sig_to_id:
                transition = (sig_to_id[current_sig], sig_to_id[next_sig])
                if transition not in allowed_transitions:
                    anomalies.append(i)
            elif current_sig not in sig_to_id or next_sig not in sig_to_id:
                anomalies.append(i)

        return anomalies
