import os
import sys
import time
import numpy as np
from flask import Flask, request, jsonify

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from network_processor import NetworkProcessor
from influence_maximization import InfluenceMaximization
from simulation import ICMModel, CDFPlotter, compute_statistics
from advanced_models import TimeSensitiveICM, MultiRumorModel, DynamicGraphICM, AdvancedPlotter

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')

network_processor = NetworkProcessor(
    redis_host=os.environ.get('REDIS_HOST', 'localhost'),
    redis_port=int(os.environ.get('REDIS_PORT', 6379)),
    redis_db=int(os.environ.get('REDIS_DB', 0))
)

GRAPH_CACHE = {}
INFLUENCE_CACHE = {}
RANDOM_SEED = 42


def get_graph(network_file: str):
    cache_key = network_file
    if cache_key in GRAPH_CACHE:
        return GRAPH_CACHE[cache_key]

    file_path = os.path.join(DATA_DIR, network_file)
    G = network_processor.preprocess_network(file_path, use_cache=True)
    GRAPH_CACHE[cache_key] = G
    return G


def get_influence_maximizer(G):
    graph_id = id(G)
    if graph_id in INFLUENCE_CACHE:
        return INFLUENCE_CACHE[graph_id]

    im = InfluenceMaximization(G, random_seed=RANDOM_SEED)
    INFLUENCE_CACHE[graph_id] = im
    return im


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'ok',
        'timestamp': time.time()
    })


@app.route('/api/networks', methods=['GET'])
def list_networks():
    try:
        files = [f for f in os.listdir(DATA_DIR) if f.endswith('.txt')]
        return jsonify({
            'networks': files
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/network/info', methods=['GET'])
def network_info():
    try:
        network_file = request.args.get('network', 'sample_network.txt')
        G = get_graph(network_file)

        return jsonify({
            'network_file': network_file,
            'nodes': G.number_of_nodes(),
            'edges': G.number_of_edges(),
            'average_degree': float(np.mean([d for _, d in G.degree()])),
            'is_directed': G.is_directed()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/immunize', methods=['POST'])
def immunize():
    try:
        data = request.get_json()

        network_file = data.get('network', 'sample_network.txt')
        seeds = data.get('seeds', [])
        k = data.get('k', 5)
        simulations = data.get('simulations', 200)
        algorithms = data.get('algorithms', None)

        if not seeds:
            return jsonify({'error': '必须指定初始传播源节点(seeds)'}), 400

        if len(seeds) != 10:
            return jsonify({'error': f'需要指定10个初始传播源节点，当前提供{len(seeds)}个'}), 400

        seeds_set = set(seeds)

        G = get_graph(network_file)

        for seed in seeds:
            if seed not in G.nodes():
                return jsonify({'error': f'初始传播源节点 {seed} 不在网络中'}), 400

        im = get_influence_maximizer(G)

        print("Starting immunization analysis...")
        start_total = time.time()

        if algorithms is None:
            algo_results = im.run_all_algorithms(k, seeds_set)
        else:
            algo_results = {}
            exclude_nodes = set(seeds)

            for algo in algorithms:
                if algo == 'pagerank':
                    selected, t = im.pagerank(k, exclude_nodes)
                elif algo == 'degree_centrality':
                    selected, t = im.degree_centrality(k, exclude_nodes)
                elif algo == 'k_core':
                    selected, t = im.k_core(k, exclude_nodes)
                elif algo == 'greedy':
                    selected, t = im.greedy(k, seeds_set, exclude_nodes)
                elif algo == 'celf':
                    selected, t = im.celf(k, seeds_set, exclude_nodes)
                else:
                    continue
                algo_results[algo] = {'nodes': selected, 'time': t}

        print("Evaluating strategies...")
        adj = network_processor.get_adjacency_with_probs(G)
        icm_model = ICMModel(adj, random_seed=RANDOM_SEED)

        base_spreads = icm_model.run_multiple_simulations(
            seeds_set, num_simulations=simulations, use_adaptive=True)

        distributions = {'无免疫 (Baseline)': base_spreads}
        evaluations = {}
        sim_counts = {'base': len(base_spreads)}

        for algo_name, algo_data in algo_results.items():
            vaccinated = set(algo_data['nodes'])
            protected_spreads = icm_model.run_multiple_simulations(
                seeds_set, vaccinated, num_simulations=simulations, use_adaptive=True)

            sim_counts[algo_name] = len(protected_spreads)

            algo_label = f'{algo_name} (免疫)'
            distributions[algo_label] = protected_spreads

            base_mean = np.mean(base_spreads)
            protected_mean = np.mean(protected_spreads)
            reduction = base_mean - protected_mean
            reduction_ratio = reduction / base_mean if base_mean > 0 else 0

            evaluations[algo_name] = {
                'base_spread': float(base_mean),
                'protected_spread': float(protected_mean),
                'reduction': float(reduction),
                'reduction_ratio': float(reduction_ratio),
                'base_stats': compute_statistics(base_spreads),
                'protected_stats': compute_statistics(protected_spreads),
                'actual_simulations': len(protected_spreads)
            }

        print("Generating CDF plots...")
        cdf_image = CDFPlotter.generate_cdf_plot(distributions, f"传播范围CDF对比 (k={k})")
        bar_image = CDFPlotter.generate_reduction_bar_chart(evaluations)

        total_time = time.time() - start_total

        response = {
            'network_file': network_file,
            'seeds': list(seeds),
            'k': k,
            'requested_simulations': simulations,
            'actual_simulations': sim_counts,
            'total_runtime': total_time,
            'algorithms': {},
            'cdf_plot_base64': cdf_image,
            'reduction_plot_base64': bar_image
        }

        for algo_name, algo_data in algo_results.items():
            response['algorithms'][algo_name] = {
                'recommended_nodes': algo_data['nodes'],
                'algorithm_runtime': algo_data['time'],
                'base_spread_mean': evaluations[algo_name]['base_spread'],
                'protected_spread_mean': evaluations[algo_name]['protected_spread'],
                'infected_reduction': evaluations[algo_name]['reduction'],
                'reduction_ratio': evaluations[algo_name]['reduction_ratio'],
                'base_stats': evaluations[algo_name]['base_stats'],
                'protected_stats': evaluations[algo_name]['protected_stats'],
                'actual_simulations': evaluations[algo_name]['actual_simulations']
            }

        return jsonify(response)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/simulate', methods=['POST'])
def simulate():
    try:
        data = request.get_json()

        network_file = data.get('network', 'sample_network.txt')
        seeds = data.get('seeds', [])
        vaccinated = data.get('vaccinated', [])
        simulations = data.get('simulations', 200)
        use_adaptive = data.get('use_adaptive', True)

        seeds_set = set(seeds)
        vaccinated_set = set(vaccinated)

        G = get_graph(network_file)
        adj = network_processor.get_adjacency_with_probs(G)
        icm_model = ICMModel(adj, random_seed=RANDOM_SEED)

        base_spreads = icm_model.run_multiple_simulations(
            seeds_set, num_simulations=simulations, use_adaptive=use_adaptive)
        protected_spreads = icm_model.run_multiple_simulations(
            seeds_set, vaccinated_set, num_simulations=simulations, use_adaptive=use_adaptive)

        distributions = {
            '无免疫': base_spreads,
            '免疫后': protected_spreads
        }

        cdf_image = CDFPlotter.generate_cdf_plot(distributions, "传播范围CDF对比")

        base_mean = np.mean(base_spreads)
        protected_mean = np.mean(protected_spreads)
        reduction = base_mean - protected_mean
        reduction_ratio = reduction / base_mean if base_mean > 0 else 0

        return jsonify({
            'base_spread': {
                'mean': float(base_mean),
                'stats': compute_statistics(base_spreads),
                'distribution': base_spreads,
                'actual_simulations': len(base_spreads)
            },
            'protected_spread': {
                'mean': float(protected_mean),
                'stats': compute_statistics(protected_spreads),
                'distribution': protected_spreads,
                'actual_simulations': len(protected_spreads)
            },
            'reduction': float(reduction),
            'reduction_ratio': float(reduction_ratio),
            'requested_simulations': simulations,
            'cdf_plot_base64': cdf_image
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/cache/clear', methods=['POST'])
def clear_cache():
    try:
        data = request.get_json() or {}
        network_file = data.get('network', None)

        network_processor.clear_cache(
            os.path.join(DATA_DIR, network_file) if network_file else None
        )
        GRAPH_CACHE.clear()
        INFLUENCE_CACHE.clear()

        return jsonify({'status': 'cache cleared'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/simulate/time_sensitive', methods=['POST'])
def simulate_time_sensitive():
    try:
        data = request.get_json()

        network_file = data.get('network', 'sample_network.txt')
        seeds = data.get('seeds', [])
        vaccinated = data.get('vaccinated', [])
        simulations = data.get('simulations', 100)
        max_time_steps = data.get('max_time_steps', 50)
        decay_rate = data.get('decay_rate', 0.1)
        recovery_rate = data.get('recovery_rate', 0.05)
        memory_decay = data.get('memory_decay', 0.02)
        use_adaptive = data.get('use_adaptive', True)

        seeds_set = set(seeds)
        vaccinated_set = set(vaccinated)

        G = get_graph(network_file)
        adj = network_processor.get_adjacency_with_probs(G)

        model = TimeSensitiveICM(
            adj,
            decay_rate=decay_rate,
            recovery_rate=recovery_rate,
            memory_decay=memory_decay,
            random_seed=RANDOM_SEED
        )

        result = model.run_multiple_simulations(
            seeds_set, vaccinated_set,
            num_simulations=simulations,
            use_adaptive=use_adaptive,
            max_time_steps=max_time_steps
        )

        plot_base64 = AdvancedPlotter.plot_time_sensitive_curves(
            result, title=f"时间敏感传播动态 (衰减率={decay_rate}, 康复率={recovery_rate})"
        )

        response = {
            'network_file': network_file,
            'seeds': seeds,
            'vaccinated': vaccinated,
            'parameters': {
                'decay_rate': decay_rate,
                'recovery_rate': recovery_rate,
                'memory_decay': memory_decay,
                'max_time_steps': max_time_steps
            },
            'requested_simulations': simulations,
            'actual_simulations': result['actual_simulations'],
            'mean_total_infected': result['mean_total_infected'],
            'std_total_infected': result['std_total_infected'],
            'mean_final_active': float(np.mean(result['final_active_distribution'])),
            'mean_total_recovered': float(np.mean(result['total_recovered_distribution'])),
            'avg_infection_curve': result['avg_infection_curve'],
            'avg_recovered_curve': result['avg_recovered_curve'],
            'total_infected_distribution': result['total_infected_distribution'],
            'plot_base64': plot_base64
        }

        return jsonify(response)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/simulate/multi_rumor', methods=['POST'])
def simulate_multi_rumor():
    try:
        data = request.get_json()

        network_file = data.get('network', 'sample_network.txt')
        seeds_by_rumor = data.get('seeds_by_rumor', {})
        vaccinated = data.get('vaccinated', [])
        rumor_configs = data.get('rumor_configs', {})
        competition_matrix = data.get('competition_matrix', None)
        enhancement_matrix = data.get('enhancement_matrix', None)
        simulations = data.get('simulations', 100)
        max_time_steps = data.get('max_time_steps', 50)
        use_adaptive = data.get('use_adaptive', True)

        if not rumor_configs:
            return jsonify({'error': '必须提供rumor_configs参数'}), 400

        if not seeds_by_rumor:
            return jsonify({'error': '必须提供seeds_by_rumor参数'}), 400

        for rumor in rumor_configs.keys():
            if rumor not in seeds_by_rumor:
                return jsonify({'error': f'谣言 {rumor} 未提供初始传播源'}), 400

        vaccinated_set = set(vaccinated)
        seeds_set_by_rumor = {k: set(v) for k, v in seeds_by_rumor.items()}

        G = get_graph(network_file)
        adj = network_processor.get_adjacency_with_probs(G)

        comp_matrix = None
        if competition_matrix:
            comp_matrix = {}
            for k, v in competition_matrix.items():
                key = tuple(k.split(',')) if isinstance(k, str) else tuple(k)
                comp_matrix[key] = float(v)

        enh_matrix = None
        if enhancement_matrix:
            enh_matrix = {}
            for k, v in enhancement_matrix.items():
                key = tuple(k.split(',')) if isinstance(k, str) else tuple(k)
                enh_matrix[key] = float(v)

        model = MultiRumorModel(
            adj,
            rumor_configs=rumor_configs,
            competition_matrix=comp_matrix,
            enhancement_matrix=enh_matrix,
            random_seed=RANDOM_SEED
        )

        summary = model.run_multiple_simulations(
            seeds_set_by_rumor, vaccinated_set,
            num_simulations=simulations,
            use_adaptive=use_adaptive,
            max_time_steps=max_time_steps
        )

        rumor_names = list(rumor_configs.keys())
        plot_base64 = AdvancedPlotter.plot_multi_rumor_curves(
            summary, rumor_names, title="多谣言传播动态对比"
        )

        response = {
            'network_file': network_file,
            'seeds_by_rumor': seeds_by_rumor,
            'vaccinated': vaccinated,
            'rumor_configs': rumor_configs,
            'has_competition': competition_matrix is not None,
            'has_enhancement': enhancement_matrix is not None,
            'requested_simulations': simulations,
            'actual_simulations': summary['actual_simulations'],
            'infection_by_rumor_mean': summary['infection_by_rumor_mean'],
            'infection_by_rumor_std': summary['infection_by_rumor_std'],
            'coinfection_mean': summary['coinfection_mean'],
            'coinfection_std': summary['coinfection_std'],
            'plot_base64': plot_base64
        }

        for rumor in rumor_names:
            response[f'avg_infection_curve_{rumor}'] = summary[f'avg_infection_curve_{rumor}']
        response['avg_coinfection_curve'] = summary['avg_coinfection_curve']

        return jsonify(response)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/simulate/dynamic_graph', methods=['POST'])
def simulate_dynamic_graph():
    try:
        data = request.get_json()

        network_file = data.get('network', 'sample_network.txt')
        seeds = data.get('seeds', [])
        vaccinated = data.get('vaccinated', [])
        edge_changes = data.get('edge_changes', None)
        node_changes = data.get('node_changes', None)
        simulations = data.get('simulations', 100)
        max_time_steps = data.get('max_time_steps', 50)
        use_adaptive = data.get('use_adaptive', True)

        seeds_set = set(seeds)
        vaccinated_set = set(vaccinated)

        G = get_graph(network_file)
        adj = network_processor.get_adjacency_with_probs(G)

        edge_changes_parsed = None
        if edge_changes:
            edge_changes_parsed = {}
            for t, changes in edge_changes.items():
                time_key = int(t) if isinstance(t, str) else t
                edge_changes_parsed[time_key] = []
                for change in changes:
                    change_type = change[0]
                    u = int(change[1])
                    v = int(change[2])
                    prob = float(change[3]) if len(change) > 3 else 0.5
                    edge_changes_parsed[time_key].append((change_type, u, v, prob))

        node_changes_parsed = None
        if node_changes:
            node_changes_parsed = {}
            for t, changes in node_changes.items():
                time_key = int(t) if isinstance(t, str) else t
                node_changes_parsed[time_key] = []
                for change in changes:
                    change_type = change[0]
                    node = int(change[1])
                    node_changes_parsed[time_key].append((change_type, node))

        model = DynamicGraphICM(
            adj,
            edge_changes=edge_changes_parsed,
            node_changes=node_changes_parsed,
            random_seed=RANDOM_SEED
        )

        summary = model.run_multiple_simulations(
            seeds_set, vaccinated_set,
            num_simulations=simulations,
            use_adaptive=use_adaptive,
            max_time_steps=max_time_steps
        )

        plot_base64 = AdvancedPlotter.plot_dynamic_graph_curves(
            summary, title="动态图传播模拟"
        )

        response = {
            'network_file': network_file,
            'seeds': seeds,
            'vaccinated': vaccinated,
            'has_edge_changes': edge_changes is not None,
            'has_node_changes': node_changes is not None,
            'requested_simulations': simulations,
            'actual_simulations': summary['actual_simulations'],
            'mean_total_infected': summary['mean_total_infected'],
            'std_total_infected': summary['std_total_infected'],
            'avg_infection_curve': summary['avg_infection_curve'],
            'avg_edge_curve': summary['avg_edge_curve'],
            'avg_node_curve': summary['avg_node_curve'],
            'total_infected_distribution': summary['total_infected_distribution'],
            'plot_base64': plot_base64
        }

        return jsonify(response)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    os.makedirs(DATA_DIR, exist_ok=True)
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
