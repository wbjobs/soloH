#!/usr/bin/env python3
"""
Python implementation of Boolean Network Analyzer - for logic verification
Includes all three bug fixes:
1. Deterministic async update order
2. Trap state detection
3. HDF5 size overflow check
"""
import random
from collections import defaultdict


def tokenize_rpn(expr):
    tokens = []
    current = []
    for c in expr:
        if c.isspace():
            if current:
                tokens.append(''.join(current))
                current = []
        elif c in '&|!()^':
            if current:
                tokens.append(''.join(current))
                current = []
            tokens.append(c)
        else:
            current.append(c)
    if current:
        tokens.append(''.join(current))
    return tokens


class BooleanFunction:
    def __init__(self, rpn_expr, name_to_idx):
        self.tokens = []
        for tok in tokenize_rpn(rpn_expr):
            tok = tok.strip()
            if not tok:
                continue
            if tok in ('AND', '&', '&&'):
                self.tokens.append(('OP', '&'))
            elif tok in ('OR', '|', '||'):
                self.tokens.append(('OP', '|'))
            elif tok in ('NOT', '!', '~'):
                self.tokens.append(('OP', '!'))
            elif tok in ('XOR', '^'):
                self.tokens.append(('OP', '^'))
            elif tok == 'NAND':
                self.tokens.append(('OP', 'n'))
            elif tok == 'NOR':
                self.tokens.append(('OP', 'r'))
            elif tok in ('1', 'TRUE', 'true', 'T'):
                self.tokens.append(('CONST', True))
            elif tok in ('0', 'FALSE', 'false', 'F'):
                self.tokens.append(('CONST', False))
            else:
                if tok not in name_to_idx:
                    raise ValueError(f"Unknown node: {tok}")
                self.tokens.append(('NODE', name_to_idx[tok]))

    def evaluate(self, state):
        stack = []
        for tok_type, tok_val in self.tokens:
            if tok_type == 'CONST':
                stack.append(tok_val)
            elif tok_type == 'NODE':
                stack.append(state[tok_val])
            elif tok_type == 'OP':
                if tok_val == '!':
                    a = stack.pop()
                    stack.append(not a)
                else:
                    b = stack.pop()
                    a = stack.pop()
                    if tok_val == '&':
                        stack.append(a and b)
                    elif tok_val == '|':
                        stack.append(a or b)
                    elif tok_val == '^':
                        stack.append(a != b)
                    elif tok_val == 'n':
                        stack.append(not (a and b))
                    elif tok_val == 'r':
                        stack.append(not (a or b))
        return stack[0]


class BooleanNetwork:
    def __init__(self):
        self.nodes = []
        self.edges = []
        self.name_to_idx = {}

    @classmethod
    def from_file(cls, filename):
        net = cls()
        with open(filename, 'r') as f:
            lines = f.readlines()

        node_funcs = []
        edges = []
        mode = 'nodes'
        expected_nodes = 0

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line == '[Nodes]':
                mode = 'nodes'
                continue
            elif line == '[Edges]':
                mode = 'edges'
                continue
            elif line == '[Functions]':
                mode = 'functions'
                continue

            if mode == 'nodes':
                if expected_nodes == 0:
                    expected_nodes = int(line)
                    continue
                parts = [p.strip() for p in line.split(',')]
                name = parts[0]
                rpn = parts[1] if len(parts) > 1 else ''
                node_funcs.append((name, rpn))
            elif mode == 'edges':
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 2:
                    edges.append((parts[0], parts[1]))
            elif mode == 'functions':
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 2:
                    name, rpn = parts[0], parts[1]
                    for i, (n, _) in enumerate(node_funcs):
                        if n == name:
                            node_funcs[i] = (name, rpn)
                            break

        for name, _ in node_funcs:
            idx = len(net.nodes)
            net.name_to_idx[name] = idx
            net.nodes.append({
                'idx': idx,
                'name': name,
                'func': None,
                'regulators': []
            })

        for name, rpn in node_funcs:
            if rpn:
                idx = net.name_to_idx[name]
                net.nodes[idx]['func'] = BooleanFunction(rpn, net.name_to_idx)

        for from_node, to_node in edges:
            if from_node in net.name_to_idx and to_node in net.name_to_idx:
                net.add_edge(net.name_to_idx[from_node], net.name_to_idx[to_node])

        return net

    def add_node(self, name, rpn_expr):
        idx = len(self.nodes)
        self.name_to_idx[name] = idx
        self.nodes.append({
            'idx': idx,
            'name': name,
            'func': BooleanFunction(rpn_expr, self.name_to_idx) if rpn_expr else None,
            'regulators': []
        })

    def add_edge(self, from_idx, to_idx):
        self.edges.append((from_idx, to_idx))
        if from_idx not in self.nodes[to_idx]['regulators']:
            self.nodes[to_idx]['regulators'].append(from_idx)

    def num_nodes(self):
        return len(self.nodes)

    def random_state(self, rng):
        return [rng.random() < 0.5 for _ in range(len(self.nodes))]

    def async_update(self, state, rng):
        idx = rng.randrange(len(self.nodes))
        new_val = self.nodes[idx]['func'].evaluate(state)
        state[idx] = new_val
        return idx

    def async_update_deterministic(self, state, round_counter):
        n = len(self.nodes)
        state_h = hash(tuple(state)) & 0xFFFFFFFF
        idx = (state_h + round_counter) % n
        new_val = self.nodes[idx]['func'].evaluate(state)
        state[idx] = new_val
        return idx

    def state_to_string(self, state):
        return ''.join('1' if b else '0' for b in state)


def state_hash(state):
    return tuple(state)


def states_equal(a_states, b_states):
    a_set = {tuple(s) for s in a_states}
    b_set = {tuple(s) for s in b_states}
    return a_set == b_set


def is_trap_state(state, no_change_steps, threshold):
    n = len(state)
    active_count = sum(1 for b in state if b)
    if active_count == 0 or active_count == n:
        return True
    if no_change_steps > threshold * n:
        return True
    return False


def find_attractor(network, state, max_steps=1000000):
    trajectory = []
    state_pos = {}
    rng = random.Random()
    no_change_steps = 0
    prev_state = state[:]
    trap_threshold = 100

    for step in range(max_steps):
        key = state_hash(state)
        if key in state_pos:
            cycle_start = state_pos[key]
            if cycle_start == len(trajectory) - 1:
                return {
                    'type': 'FIXED_POINT',
                    'length': 1,
                    'states': [state[:]],
                    'basin_size': 0
                }
            else:
                return {
                    'type': 'LIMIT_CYCLE',
                    'length': len(trajectory) - cycle_start,
                    'states': [s[:] for s in trajectory[cycle_start:]],
                    'basin_size': 0
                }

        if tuple(state) == tuple(prev_state):
            no_change_steps += 1
        else:
            no_change_steps = 0
            prev_state = state[:]

        if is_trap_state(state, no_change_steps, trap_threshold):
            return {
                'type': 'TRAP_STATE',
                'length': 0,
                'states': [state[:]],
                'basin_size': 0
            }

        state_pos[key] = len(trajectory)
        trajectory.append(state[:])
        network.async_update(state, rng)

    return {
        'type': 'TRAP_STATE',
        'length': 0,
        'states': [state[:]],
        'basin_size': 0
    }


def find_attractor_deterministic(network, state, max_steps=1000000):
    trajectory = []
    state_pos = {}
    round_counter = 0
    no_change_steps = 0
    prev_state = state[:]
    trap_threshold = 100

    for step in range(max_steps):
        key = state_hash(state)
        if key in state_pos:
            cycle_start = state_pos[key]
            if cycle_start == len(trajectory) - 1:
                return {
                    'type': 'FIXED_POINT',
                    'length': 1,
                    'states': [state[:]],
                    'basin_size': 0
                }
            else:
                return {
                    'type': 'LIMIT_CYCLE',
                    'length': len(trajectory) - cycle_start,
                    'states': [s[:] for s in trajectory[cycle_start:]],
                    'basin_size': 0
                }

        if tuple(state) == tuple(prev_state):
            no_change_steps += 1
        else:
            no_change_steps = 0
            prev_state = state[:]

        if is_trap_state(state, no_change_steps, trap_threshold):
            return {
                'type': 'TRAP_STATE',
                'length': 0,
                'states': [state[:]],
                'basin_size': 0
            }

        state_pos[key] = len(trajectory)
        trajectory.append(state[:])
        network.async_update_deterministic(state, round_counter)

    return {
        'type': 'TRAP_STATE',
        'length': 0,
        'states': [state[:]],
        'basin_size': 0
    }


def search_attractors(network, num_starts=1000, max_steps=1000000, deterministic=True):
    attractors = []
    rng = random.Random()

    for _ in range(num_starts):
        state = network.random_state(rng)
        if deterministic:
            attr = find_attractor_deterministic(network, state, max_steps)
        else:
            attr = find_attractor(network, state, max_steps)

        is_new = True
        for existing in attractors:
            if states_equal(existing['states'], attr['states']):
                is_new = False
                break
        if is_new:
            attractors.append(attr)
    return attractors


def compute_basin_sizes(network, attractors, num_samples=10000, deterministic=True):
    counts = [0] * len(attractors)
    rng = random.Random()

    for _ in range(num_samples):
        state = network.random_state(rng)
        if deterministic:
            attr = find_attractor_deterministic(network, state)
        else:
            attr = find_attractor(network, state)

        for i, existing in enumerate(attractors):
            if states_equal(existing['states'], attr['states']):
                counts[i] += 1
                break

    for i, c in enumerate(counts):
        attractors[i]['basin_size'] = c


def check_hdf5_size(n_states, n_nodes):
    MAX_HDF5_DIM = 2147483647
    if n_states > MAX_HDF5_DIM or n_nodes > MAX_HDF5_DIM:
        raise RuntimeError("Dataset dimension exceeds HDF5 maximum (2^31-1)")
    total_elements = n_states * n_nodes
    if total_elements > MAX_HDF5_DIM:
        raise RuntimeError("Total dataset size exceeds HDF5 maximum (2^31-1). "
                           "Reduce the number of samples or nodes.")
    return True


def test_determinism(network, num_tests=10):
    print("\n=== Test 1: Deterministic Update Verification ===")
    rng = random.Random(42)
    all_consistent = True

    for test_idx in range(num_tests):
        initial_state = network.random_state(rng)
        results = []

        for run in range(3):
            state = initial_state[:]
            attr = find_attractor_deterministic(network, state)
            results.append(attr['states'][0])

        consistent = all(tuple(r) == tuple(results[0]) for r in results)
        status = "PASS" if consistent else "FAIL"
        if not consistent:
            all_consistent = False
        print(f"  Test {test_idx + 1}: {status}")
        if not consistent:
            print(f"    Run 1: {network.state_to_string(results[0])}")
            print(f"    Run 2: {network.state_to_string(results[1])}")
            print(f"    Run 3: {network.state_to_string(results[2])}")

    return all_consistent


def test_trap_detection():
    print("\n=== Test 2: Trap State Detection ===")

    class MockNetwork:
        def num_nodes(self): return 5
        def async_update_deterministic(self, state, rc):
            return 0
        def async_update(self, state, rng):
            return 0

    all_zeros = [False, False, False, False, False]
    all_ones = [True, True, True, True, True]
    normal = [True, False, True, False, True]

    trap1 = is_trap_state(all_zeros, 0, 100)
    trap2 = is_trap_state(all_ones, 0, 100)
    not_trap = is_trap_state(normal, 0, 100)
    stuck = is_trap_state(normal, 1000, 100)

    print(f"  All zeros trap: {'PASS' if trap1 else 'FAIL'} (got {trap1})")
    print(f"  All ones trap: {'PASS' if trap2 else 'FAIL'} (got {trap2})")
    print(f"  Normal not trap: {'PASS' if not not_trap else 'FAIL'} (got {not_trap})")
    print(f"  Long no-change trap: {'PASS' if stuck else 'FAIL'} (got {stuck})")

    return trap1 and trap2 and not not_trap and stuck


def test_hdf5_size_check():
    print("\n=== Test 3: HDF5 Size Overflow Check ===")

    try:
        check_hdf5_size(1000, 10)
        print("  Normal size: PASS")
    except Exception as e:
        print(f"  Normal size: FAIL ({e})")
        return False

    try:
        check_hdf5_size(3000000000, 10)
        print("  Large dim: FAIL (should have raised)")
        return False
    except RuntimeError as e:
        if "2^31-1" in str(e):
            print(f"  Large dim: PASS (raised: {e})")
        else:
            print(f"  Large dim: FAIL (wrong error: {e})")
            return False

    try:
        check_hdf5_size(50000, 50000)
        print("  Large product: FAIL (should have raised)")
        return False
    except RuntimeError as e:
        if "2^31-1" in str(e):
            print(f"  Large product: PASS (raised: {e})")
        else:
            print(f"  Large product: FAIL (wrong error: {e})")
            return False

    return True


def main():
    print("=" * 60)
    print("Boolean Network Analyzer - Bug Fix Verification")
    print("=" * 60)

    import sys
    if len(sys.argv) < 2:
        filename = 'examples/simple_network.txt'
    else:
        filename = sys.argv[1]

    print(f"\nLoading network: {filename}")
    network = BooleanNetwork.from_file(filename)

    print("Network loaded:")
    print(f"  Nodes: {network.num_nodes()}")
    print(f"  Edges: {len(network.edges)}")
    for node in network.nodes:
        reg_names = [network.nodes[i]['name'] for i in node['regulators']]
        print(f"  {node['name']}: regulators = {reg_names}")

    test1_pass = test_determinism(network)
    test2_pass = test_trap_detection()
    test3_pass = test_hdf5_size_check()

    print("\n=== Searching for attractors with deterministic update ===")
    attractors = search_attractors(network, num_starts=500, deterministic=True)
    compute_basin_sizes(network, attractors, num_samples=2000, deterministic=True)

    print(f"\nFound {len(attractors)} attractors:")
    for i, attr in enumerate(attractors):
        print(f"\n--- Attractor {i} ---")
        print(f"  Type: {attr['type']}")
        print(f"  Length: {attr['length']}")
        print(f"  Basin size: {attr['basin_size']} ({100.0 * attr['basin_size'] / 2000:.2f}%)")
        print(f"  States:")
        for j, s in enumerate(attr['states']):
            arrow = f" -> [{(j + 1) % attr['length']}]" if attr['type'] == 'LIMIT_CYCLE' else ''
            print(f"    [{j}] {network.state_to_string(s)}{arrow}")

    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    print(f"1. Deterministic update: {'PASS' if test1_pass else 'FAIL'}")
    print(f"2. Trap state detection: {'PASS' if test2_pass else 'FAIL'}")
    print(f"3. HDF5 size check:     {'PASS' if test3_pass else 'FAIL'}")

    all_pass = test1_pass and test2_pass and test3_pass
    print(f"\nOverall: {'ALL TESTS PASSED' if all_pass else 'SOME TESTS FAILED'}")

    return 0 if all_pass else 1


if __name__ == '__main__':
    main()
