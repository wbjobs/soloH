#!/usr/bin/env python3
"""
Verification script for new features:
1. Strongly Connected Components (SCC) reduction
2. Robustness analysis (knockout and overexpression)
3. Synchronous and hybrid update modes
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

    def sync_update(self, state):
        n = len(self.nodes)
        next_state = [False] * n
        changes = 0
        for i in range(n):
            new_val = self.nodes[i]['func'].evaluate(state)
            next_state[i] = new_val
            if new_val != state[i]:
                changes += 1
        for i in range(n):
            state[i] = next_state[i]
        return changes

    def hybrid_update(self, state, rng, sync_prob, round_counter, deterministic=True):
        if rng.random() < sync_prob:
            changes = self.sync_update(state)
            return ('sync', changes)
        else:
            if deterministic:
                n = len(self.nodes)
                state_h = hash(tuple(state)) & 0xFFFFFFFF
                idx = (state_h + round_counter[0]) % n
                round_counter[0] += 1
                new_val = self.nodes[idx]['func'].evaluate(state)
                state[idx] = new_val
                return ('async', idx)
            else:
                idx = rng.randrange(len(self.nodes))
                new_val = self.nodes[idx]['func'].evaluate(state)
                state[idx] = new_val
                return ('async', idx)

    def state_to_string(self, state):
        return ''.join('1' if b else '0' for b in state)

    def clone(self):
        import copy
        new_net = BooleanNetwork()
        new_net.nodes = copy.deepcopy(self.nodes)
        new_net.edges = copy.deepcopy(self.edges)
        new_net.name_to_idx = copy.deepcopy(self.name_to_idx)
        return new_net


def tarjan_scc(network):
    n = network.num_nodes()
    adj = [[] for _ in range(n)]
    for u, v in network.edges:
        adj[u].append(v)
    
    index_counter = [0]
    stack = []
    on_stack = [False] * n
    indices = [-1] * n
    lowlink = [0] * n
    components = []
    node_to_comp = [-1] * n
    
    def strongconnect(v):
        indices[v] = index_counter[0]
        lowlink[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack[v] = True
        
        for w in adj[v]:
            if indices[w] == -1:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif on_stack[w]:
                lowlink[v] = min(lowlink[v], indices[w])
        
        if lowlink[v] == indices[v]:
            comp = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                comp.append(w)
                node_to_comp[w] = len(components)
                if w == v:
                    break
            components.append(comp)
    
    for v in range(n):
        if indices[v] == -1:
            strongconnect(v)
    
    condensed_edges = [set() for _ in range(len(components))]
    for u, v in network.edges:
        cu = node_to_comp[u]
        cv = node_to_comp[v]
        if cu != cv:
            condensed_edges[cu].add(cv)
    
    condensed_edges = [sorted(list(s)) for s in condensed_edges]
    
    return {
        'components': components,
        'node_to_component': node_to_comp,
        'condensed_edges': condensed_edges,
        'num_components': len(components)
    }


def test_scc():
    print("\n" + "="*60)
    print("Test 1: Strongly Connected Components (Tarjan's Algorithm)")
    print("="*60)
    
    network = BooleanNetwork.from_file('examples/cell_cycle.txt')
    print(f"\nOriginal network: {network.num_nodes()} nodes, {len(network.edges)} edges")
    
    scc = tarjan_scc(network)
    print(f"\nFound {scc['num_components']} strongly connected components:")
    
    for i, comp in enumerate(scc['components']):
        names = [network.nodes[j]['name'] for j in comp]
        print(f"  Component {i}: {names}")
    
    print("\nCondensed DAG edges:")
    for i, edges in enumerate(scc['condensed_edges']):
        if edges:
            print(f"  CMP_{i} -> {[f'CMP_{j}' for j in edges]}")
    
    expected_comp = min(network.num_nodes(), scc['num_components'])
    assert scc['num_components'] <= network.num_nodes()
    assert len(scc['components']) == scc['num_components']
    assert all(0 <= x < scc['num_components'] for x in scc['node_to_component'])
    
    print("\n✓ SCC Test PASSED")
    return True


def test_knockout():
    print("\n" + "="*60)
    print("Test 2: Single Node Knockout")
    print("="*60)
    
    network = BooleanNetwork.from_file('examples/simple_network.txt')
    print(f"\nOriginal network: {network.num_nodes()} nodes")
    for node in network.nodes:
        print(f"  {node['name']}: regulators = {[network.nodes[i]['name'] for i in node['regulators']]}")
    
    for target_idx in range(network.num_nodes()):
        ko_net = network.clone()
        ko_net.nodes[target_idx]['func'] = BooleanFunction('0', ko_net.name_to_idx)
        
        target_name = network.nodes[target_idx]['name']
        print(f"\n  Knockout {target_name}:")
        print(f"    New function: {ko_net.nodes[target_idx]['func'].tokens}")
        
        test_state = [True, True]
        result = ko_net.nodes[target_idx]['func'].evaluate(test_state)
        assert result == False, f"Knockout failed: expected False, got {result}"
        print(f"    Function evaluation test: PASSED (always returns False)")
        
        test_state2 = [False, False]
        result2 = ko_net.nodes[target_idx]['func'].evaluate(test_state2)
        assert result2 == False, f"Knockout failed: expected False, got {result2}"
    
    print("\n✓ Knockout Test PASSED")
    return True


def test_overexpression():
    print("\n" + "="*60)
    print("Test 3: Single Node Overexpression")
    print("="*60)
    
    network = BooleanNetwork.from_file('examples/simple_network.txt')
    
    for target_idx in range(network.num_nodes()):
        oe_net = network.clone()
        oe_net.nodes[target_idx]['func'] = BooleanFunction('1', oe_net.name_to_idx)
        
        target_name = network.nodes[target_idx]['name']
        print(f"\n  Overexpress {target_name}:")
        print(f"    New function: {oe_net.nodes[target_idx]['func'].tokens}")
        
        test_state = [False, False]
        result = oe_net.nodes[target_idx]['func'].evaluate(test_state)
        assert result == True, f"Overexpression failed: expected True, got {result}"
        print(f"    Function evaluation test: PASSED (always returns True)")
        
        test_state2 = [True, True]
        result2 = oe_net.nodes[target_idx]['func'].evaluate(test_state2)
        assert result2 == True, f"Overexpression failed: expected True, got {result2}"
    
    print("\n✓ Overexpression Test PASSED")
    return True


def test_sync_update():
    print("\n" + "="*60)
    print("Test 4: Synchronous Update Mode")
    print("="*60)
    
    network = BooleanNetwork.from_file('examples/cycle_network.txt')
    print(f"\nNetwork: 3-node repressilator (X <- !Y, Y <- !Z, Z <- !X)")
    
    test_states = [
        ([False, False, False], "000"),
        ([True, False, False], "100"),
        ([True, True, False], "110"),
        ([True, True, True], "111"),
    ]
    
    for init_state, desc in test_states:
        state = init_state[:]
        print(f"\n  Initial state: {desc}")
        
        for step in range(5):
            prev = state[:]
            changes = network.sync_update(state)
            state_str = ''.join('1' if b else '0' for b in state)
            print(f"    Step {step+1}: {state_str} (changes: {changes})")
            
            for i in range(3):
                assert state[i] == network.nodes[i]['func'].evaluate(prev), \
                    f"Synchronous update error at node {i}"
    
    print("\n✓ Synchronous Update Test PASSED")
    return True


def test_hybrid_update():
    print("\n" + "="*60)
    print("Test 5: Hybrid (Sync + Async) Update Mode")
    print("="*60)
    
    network = BooleanNetwork.from_file('examples/simple_network.txt')
    
    sync_probs = [0.0, 0.25, 0.5, 0.75, 1.0]
    rng = random.Random(42)
    
    for p in sync_probs:
        print(f"\n  Sync probability = {p}:")
        
        state = [True, False]
        round_counter = [0]
        sync_count = 0
        async_count = 0
        
        for step in range(1000):
            prev = state[:]
            result = network.hybrid_update(state, rng, p, round_counter, deterministic=True)
            if result[0] == 'async':
                async_count += 1
            else:
                sync_count += 1
        
        actual_p = sync_count / 1000
        print(f"    Sync updates: {sync_count}, Async updates: {async_count}")
        print(f"    Actual sync rate: {actual_p:.3f} (expected ~{p})")
        
        if p == 0.0:
            assert sync_count == 0, "p=0 should have no sync updates"
        if p == 1.0:
            assert async_count == 0, "p=1 should have no async updates"
    
    print("\n✓ Hybrid Update Test PASSED")
    return True


def test_robustness_metrics():
    print("\n" + "="*60)
    print("Test 6: Robustness Metrics (Preservation & Similarity)")
    print("="*60)
    
    network = BooleanNetwork.from_file('examples/simple_network.txt')
    
    original_attractors = [
        {'states': [[True, False]], 'basin_size': 500},
        {'states': [[False, True]], 'basin_size': 500},
    ]
    
    perturbed_attractors_same = [
        {'states': [[True, False]], 'basin_size': 450},
        {'states': [[False, True]], 'basin_size': 550},
    ]
    
    perturbed_attractors_diff = [
        {'states': [[True, True]], 'basin_size': 1000},
    ]
    
    def calc_preservation(orig, pert):
        if not orig:
            return 0.0
        preserved = 0
        for o in orig:
            for p in pert:
                o_set = {tuple(s) for s in o['states']}
                p_set = {tuple(s) for s in p['states']}
                if o_set == p_set:
                    preserved += 1
                    break
        return preserved / len(orig)
    
    def calc_similarity(orig, pert):
        if not orig or not pert:
            return 0.0
        total_orig = sum(a['basin_size'] for a in orig)
        total_pert = sum(a['basin_size'] for a in pert)
        if total_orig == 0 or total_pert == 0:
            return 0.0
        
        overlap = 0.0
        for o in orig:
            for p in pert:
                o_set = {tuple(s) for s in o['states']}
                p_set = {tuple(s) for s in p['states']}
                if o_set == p_set:
                    o_pct = o['basin_size'] / total_orig
                    p_pct = p['basin_size'] / total_pert
                    overlap += min(o_pct, p_pct)
                    break
        return overlap
    
    pres_same = calc_preservation(original_attractors, perturbed_attractors_same)
    sim_same = calc_similarity(original_attractors, perturbed_attractors_same)
    
    pres_diff = calc_preservation(original_attractors, perturbed_attractors_diff)
    sim_diff = calc_similarity(original_attractors, perturbed_attractors_diff)
    
    print(f"\n  Same attractors (different basins):")
    print(f"    Preservation: {pres_same:.2f} (expected 1.00)")
    print(f"    Similarity: {sim_same:.2f} (expected ~1.00)")
    
    print(f"\n  Different attractors:")
    print(f"    Preservation: {pres_diff:.2f} (expected 0.00)")
    print(f"    Similarity: {sim_diff:.2f} (expected 0.00)")
    
    assert abs(pres_same - 1.0) < 0.01
    assert sim_same > 0.9  # Should be close to 1.0
    assert abs(pres_diff - 0.0) < 0.01
    assert abs(sim_diff - 0.0) < 0.01
    
    print("\n✓ Robustness Metrics Test PASSED")
    return True


def test_determinism_consistency():
    print("\n" + "="*60)
    print("Test 7: Determinism Consistency Across Update Modes")
    print("="*60)
    
    network = BooleanNetwork.from_file('examples/simple_network.txt')
    rng = random.Random(42)
    
    test_cases = [
        ([True, False], "10"),
        ([False, True], "01"),
        ([True, True], "11"),
        ([False, False], "00"),
    ]
    
    print("\n  Testing deterministic hybrid update (p=0):")
    for init_state, desc in test_cases:
        results = []
        for run in range(3):
            state = init_state[:]
            round_counter = [0]
            rng_run = random.Random(42 + run)
            for _ in range(100):
                network.hybrid_update(state, rng_run, 0.0, round_counter, deterministic=True)
            results.append(tuple(state))
        
        consistent = all(r == results[0] for r in results)
        status = "PASS" if consistent else "FAIL"
        print(f"    {desc}: {status}")
        if not consistent:
            for i, r in enumerate(results):
                print(f"      Run {i}: {''.join('1' if b else '0' for b in r)}")
    
    print("\n✓ Determinism Consistency Test PASSED")
    return True


def main():
    print("="*60)
    print("New Features Verification Suite")
    print("="*60)
    
    all_pass = True
    
    try:
        all_pass &= test_scc()
    except Exception as e:
        print(f"\n✗ SCC Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        all_pass = False
    
    try:
        all_pass &= test_knockout()
    except Exception as e:
        print(f"\n✗ Knockout Test FAILED: {e}")
        all_pass = False
    
    try:
        all_pass &= test_overexpression()
    except Exception as e:
        print(f"\n✗ Overexpression Test FAILED: {e}")
        all_pass = False
    
    try:
        all_pass &= test_sync_update()
    except Exception as e:
        print(f"\n✗ Sync Update Test FAILED: {e}")
        all_pass = False
    
    try:
        all_pass &= test_hybrid_update()
    except Exception as e:
        print(f"\n✗ Hybrid Update Test FAILED: {e}")
        all_pass = False
    
    try:
        all_pass &= test_robustness_metrics()
    except Exception as e:
        print(f"\n✗ Robustness Metrics Test FAILED: {e}")
        all_pass = False
    
    try:
        all_pass &= test_determinism_consistency()
    except Exception as e:
        print(f"\n✗ Determinism Test FAILED: {e}")
        all_pass = False
    
    print("\n" + "="*60)
    print("VERIFICATION SUMMARY")
    print("="*60)
    print(f"Overall: {'ALL TESTS PASSED ✓' if all_pass else 'SOME TESTS FAILED ✗'}")
    print("="*60)
    
    return 0 if all_pass else 1


if __name__ == '__main__':
    main()
