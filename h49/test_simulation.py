import numpy as np
import sys
sys.path.insert(0, r'e:\soloH\h49')

from drone_swarm_mpc import (
    QPSolver, DroneDynamics, MPCController, 
    PotentialField, VelocityObstacle, ObstacleGenerator,
    DMPCCommunicationLayer, HeterogeneousDroneConfig,
    FormationController, RLPolicyNetwork
)

def test_qp_solver():
    print("Testing QP Solver...")
    solver = QPSolver(nV=2, nC=0)
    
    H = np.array([[2, 0], [0, 2]])
    g = np.array([-4, -6])
    lb = np.array([0, 0])
    ub = np.array([10, 10])
    
    solver.init(H, g, lb=lb, ub=ub)
    x_opt, status = solver.solve()
    
    print(f"  Optimal x: {x_opt}")
    print(f"  Status: {status}")
    assert status == 0, "QP solver failed"
    assert np.allclose(x_opt, [2, 3], atol=0.1), f"Expected [2, 3], got {x_opt}"
    print("  QP Solver test PASSED!")

def test_drone_dynamics():
    print("\nTesting Drone Dynamics...")
    dynamics = DroneDynamics(dt=0.1, max_acc=5.0, max_vel=3.0)
    
    state = np.array([0.0, 0.0, 5.0, 1.0, 0.0, 0.0])
    control = np.array([1.0, 0.5, 0.0])
    
    new_state = dynamics.step(state, control)
    print(f"  Initial state: {state}")
    print(f"  Control input: {control}")
    print(f"  New state: {new_state}")
    
    assert new_state[0] > state[0], "X position should increase"
    assert np.abs(new_state[3]) <= dynamics.max_vel, "Velocity should be clipped"
    
    A, B = dynamics.get_linearized_matrices(state, control)
    print(f"  A matrix shape: {A.shape}")
    print(f"  B matrix shape: {B.shape}")
    assert A.shape == (6, 6), "A should be 6x6"
    assert B.shape == (6, 3), "B should be 6x3"
    print("  Drone Dynamics test PASSED!")

def test_mpc_controller():
    print("\nTesting MPC Controller...")
    dynamics = DroneDynamics(dt=0.1)
    mpc = MPCController(dynamics, N=10)
    
    state = np.array([0.0, 0.0, 5.0, 0.0, 0.0, 0.0])
    target = np.array([10.0, 0.0, 5.0, 0.0, 0.0, 0.0])
    
    control, pred_traj, control_seq = mpc.compute_control(state, target)
    print(f"  Control input: {control}")
    print(f"  Predicted trajectory shape: {pred_traj.shape}")
    print(f"  Control sequence shape: {control_seq.shape}")
    print(f"  Final predicted position: {pred_traj[-1, :3]}")
    
    assert pred_traj.shape == (11, 6), "Predicted trajectory should be N+1 x 6"
    assert control_seq.shape == (10, 3), "Control sequence should be N x 3"
    assert control[0] > 0, "Should accelerate towards target in X direction"
    print("  MPC Controller test PASSED!")

def test_mpc_weight_initialization():
    print("\nTesting MPC Weight Initialization (Fix #3)...")
    
    Q, R, Qf = MPCController._default_weights(6, 3)
    
    print(f"  Q shape: {Q.shape}, symmetric: {np.allclose(Q, Q.T)}")
    print(f"  R shape: {R.shape}, symmetric: {np.allclose(R, R.T)}")
    print(f"  Qf shape: {Qf.shape}, symmetric: {np.allclose(Qf, Qf.T)}")
    
    assert np.allclose(Q, Q.T), "Q should be symmetric"
    assert np.allclose(R, R.T), "R should be symmetric"
    assert np.allclose(Qf, Qf.T), "Qf should be symmetric"
    
    eig_Q = np.linalg.eigvalsh(Q)
    eig_R = np.linalg.eigvalsh(R)
    eig_Qf = np.linalg.eigvalsh(Qf)
    
    print(f"  Q min eigenvalue: {min(eig_Q):.6f}")
    print(f"  R min eigenvalue: {min(eig_R):.6f}")
    print(f"  Qf min eigenvalue: {min(eig_Qf):.6f}")
    
    assert min(eig_Q) >= 0, "Q should be positive semi-definite"
    assert min(eig_R) >= 0, "R should be positive semi-definite"
    assert min(eig_Qf) >= 0, "Qf should be positive semi-definite"
    
    dynamics = DroneDynamics(dt=0.1)
    mpc1 = MPCController(dynamics, N=10)
    mpc2 = MPCController(dynamics, N=10)
    
    assert np.allclose(mpc1.Q, mpc2.Q), "All MPCs should have same default Q"
    assert np.allclose(mpc1.R, mpc2.R), "All MPCs should have same default R"
    assert np.allclose(mpc1.Qf, mpc2.Qf), "All MPCs should have same default Qf"
    
    mpc1.reinitialize_weights()
    assert np.allclose(mpc1.Q, mpc2.Q), "Reinitialization should preserve weights"
    
    print("  MPC Weight Initialization test PASSED!")

def test_potential_field():
    print("\nTesting Potential Field...")
    pf = PotentialField(k_att=1.0, k_rep=50.0, d0=2.0)
    
    position = np.array([0.0, 0.0, 5.0])
    target = np.array([10.0, 0.0, 5.0])
    
    obstacles_near = [
        {'type': 'sphere', 'x': 3.0, 'y': 0.0, 'z': 5.0, 'radius': 1.0}
    ]
    
    obstacles_far = [
        {'type': 'sphere', 'x': 20.0, 'y': 0.0, 'z': 5.0, 'radius': 1.0}
    ]
    
    force_far = pf.compute_force(position, target, obstacles_far, velocity=np.zeros(3))
    print(f"  Force with far obstacle: {force_far}")
    assert force_far[0] > 0, "Attractive force should pull towards target when obstacle is far"
    
    pf.reset_filter()
    force_near = pf.compute_force(position, target, obstacles_near, velocity=np.zeros(3))
    print(f"  Force with near obstacle: {force_near}")
    assert force_near[0] < 0, "Repulsive force should push away when obstacle is near"
    
    print("  Potential Field test PASSED!")

def test_smooth_force_transition():
    print("\nTesting Smooth Force Transition (Fix #2)...")
    pf = PotentialField(alpha=0.5, perception_range=10.0, transition_width=3.0)
    
    target = np.array([0.0, 0.0, 5.0])
    velocity = np.array([2.0, 0.0, 0.0])
    dt = 0.1
    
    obstacles_close = [{'type': 'sphere', 'x': 5.0, 'y': 0.0, 'z': 5.0, 'radius': 1.0}]
    obstacles_far = [{'type': 'sphere', 'x': 15.0, 'y': 0.0, 'z': 5.0, 'radius': 1.0}]
    
    forces_close = []
    pf.reset_filter()
    for i in range(5):
        pos = np.array([i * 0.5, 0.0, 5.0])
        force = pf.compute_force(pos, target, obstacles_close, velocity=velocity, dt=dt)
        forces_close.append(force.copy())
    
    forces_far = []
    pf.reset_filter()
    for i in range(5):
        pos = np.array([i * 0.5, 0.0, 5.0])
        force = pf.compute_force(pos, target, obstacles_far, velocity=velocity, dt=dt)
        forces_far.append(force.copy())
    
    forces_close = np.array(forces_close)
    forces_far = np.array(forces_far)
    
    diffs_close = np.linalg.norm(np.diff(forces_close, axis=0), axis=1)
    diffs_far = np.linalg.norm(np.diff(forces_far, axis=0), axis=1)
    
    max_diff_close = np.max(diffs_close)
    max_diff_far = np.max(diffs_far)
    
    print(f"  Max force diff (close obstacles): {max_diff_close:.4f}")
    print(f"  Max force diff (far obstacles): {max_diff_far:.4f}")
    print(f"  Diffs close: {diffs_close}")
    print(f"  Diffs far: {diffs_far}")
    
    assert max_diff_close < 3.0, "Force transitions should be smooth within obstacle sequences"
    
    pf2 = PotentialField(perception_range=10.0, transition_width=3.0)
    forces_perception = []
    
    for d in np.linspace(14.0, 6.0, 20):
        pos = np.array([0.0, 0.0, 5.0])
        obs = [{'type': 'sphere', 'x': d, 'y': 0.0, 'z': 5.0, 'radius': 1.0}]
        f = pf2.compute_force(pos, target, obs, velocity=np.array([1.0, 0, 0]))
        forces_perception.append(f[0])
    
    forces_perception = np.array(forces_perception)
    perception_diffs = np.abs(np.diff(forces_perception))
    max_perception_diff = np.max(perception_diffs)
    
    print(f"  Max force diff at perception boundary: {max_perception_diff:.4f}")
    assert max_perception_diff < 1.0, "Force should not jump at perception boundary"
    
    pf.reset_filter()
    assert pf._filtered_force is None, "Filter should be reset"
    
    print("  Smooth Force Transition test PASSED!")

def test_emergency_braking():
    print("\nTesting Emergency Braking Continuity (Fix #2)...")
    pf = PotentialField(perception_range=10.0, max_decel=5.0)
    
    position = np.array([0.0, 0.0, 5.0])
    target = np.array([20.0, 0.0, 5.0])
    velocity = np.array([5.0, 0.0, 0.0])
    
    obstacles_sudden = [{'type': 'sphere', 'x': 6.0, 'y': 0.0, 'z': 5.0, 'radius': 1.0}]
    
    pf.reset_filter()
    f1 = pf.compute_force(position, target, obstacles_sudden, velocity=velocity)
    
    f2 = pf.compute_force(position, target, obstacles_sudden, velocity=velocity)
    
    force_change = np.linalg.norm(f2 - f1)
    print(f"  Force on first encounter: {f1}")
    print(f"  Force on second step: {f2}")
    print(f"  Force change: {force_change:.4f}")
    
    assert force_change < 3.0, "Emergency braking force should be filtered"
    
    stopping_distance = np.linalg.norm(velocity)**2 / (2 * 5.0)
    obstacle_dist = 6.0 - 1.0 - 2.0
    
    print(f"  Stopping distance needed: {stopping_distance:.2f}m")
    print(f"  Available distance: {obstacle_dist:.2f}m")
    
    if stopping_distance > obstacle_dist:
        assert f1[0] < 0, "Should brake when stopping distance exceeds available"
        print("  Emergency braking activated correctly")
    
    print("  Emergency Braking Continuity test PASSED!")

def test_velocity_obstacle():
    print("\nTesting Velocity Obstacle...")
    vo = VelocityObstacle(drone_radius=0.5, time_horizon=3.0)
    
    pos_a = np.array([0.0, 0.0, 5.0])
    vel_a = np.array([1.0, 0.0, 0.0])
    pos_b = np.array([5.0, 0.0, 5.0])
    vel_b = np.array([-1.0, 0.0, 0.0])
    
    avoid_vel = vo.compute_avoidance_velocity(pos_a, vel_a, pos_b, vel_b, v_max=3.0)
    print(f"  Drone A position: {pos_a}, velocity: {vel_a}")
    print(f"  Drone B position: {pos_b}, velocity: {vel_b}")
    print(f"  Avoidance velocity: {avoid_vel}")
    
    assert np.linalg.norm(avoid_vel) > 0, "Should return avoidance velocity"
    print("  Velocity Obstacle test PASSED!")

def test_symmetric_collision_resolution():
    print("\nTesting Symmetric Collision Resolution (Fix #1)...")
    vo = VelocityObstacle(drone_radius=0.5, time_horizon=3.0)
    
    pos_a = np.array([-3.0, 0.0, 5.0])
    vel_a = np.array([2.0, 0.0, 0.0])
    pos_b = np.array([3.0, 0.0, 5.0])
    vel_b = np.array([-2.0, 0.0, 0.0])
    
    v_max = 3.0
    
    avoid_a = vo.compute_avoidance_velocity(pos_a, vel_a, pos_b, vel_b, v_max, id_a=0, id_b=1)
    avoid_b = vo.compute_avoidance_velocity(pos_b, vel_b, pos_a, vel_a, v_max, id_a=1, id_b=0)
    
    print(f"  Drone 0 (lower ID) avoidance velocity: {avoid_a}")
    print(f"  Drone 1 (higher ID) avoidance velocity: {avoid_b}")
    
    dot_product = np.dot(avoid_a[:2], avoid_b[:2])
    print(f"  Dot product of avoidance directions: {dot_product:.4f}")
    
    assert np.linalg.norm(avoid_a) > 0, "Drone A should have avoidance velocity"
    assert np.linalg.norm(avoid_b) > 0, "Drone B should have avoidance velocity"
    assert dot_product < 0, "Drones should turn in opposite directions"
    
    side_a = avoid_a[1]
    side_b = avoid_b[1]
    
    print(f"  Y component drone 0 (lower ID): {side_a:.4f}")
    print(f"  Y component drone 1 (higher ID): {side_b:.4f}")
    
    if abs(side_a) > 0.1 and abs(side_b) > 0.1:
        assert side_a * side_b < 0, "Y components should have opposite signs"
    
    assert side_a >= -0.5, "Lower ID drone should not turn strongly right"
    assert side_b <= 0.5, "Higher ID drone should not turn strongly left"
    
    bias_a = vo._get_priority_bias(0, 1)
    bias_b = vo._get_priority_bias(1, 0)
    assert bias_a == 1.0, "Lower ID should have positive bias"
    assert bias_b == -1.0, "Higher ID should have negative bias"
    assert bias_a == -bias_b, "Biases should be symmetric"
    
    print("  Symmetric Collision Resolution test PASSED!")

def test_obstacle_generator():
    print("\nTesting Obstacle Generator...")
    og = ObstacleGenerator(world_size=30)
    
    obstacles = og.generate(n_trees=5, n_buildings=3)
    print(f"  Generated {len(obstacles)} obstacles")
    print(f"  Trees: {len([o for o in obstacles if o['type'] == 'tree'])}")
    print(f"  Buildings: {len([o for o in obstacles if o['type'] == 'building'])}")
    
    assert len(obstacles) == 8, "Should generate 8 obstacles"
    for obs in obstacles:
        assert 'type' in obs
        assert 'x' in obs and 'y' in obs
    print("  Obstacle Generator test PASSED!")

def test_dmpc_communication_layer():
    print("\nTesting DMPC Communication Layer (Feature #1)...")
    n_drones = 5
    comm = DMPCCommunicationLayer(
        n_drones=n_drones,
        max_delay=2,
        packet_loss_rate=0.0,
        communication_range=30.0
    )
    
    positions = [np.array([i * 2.0, 0, 5]) for i in range(n_drones)]
    trajectories = [np.random.randn(11, 6) for _ in range(n_drones)]
    control_seqs = [np.random.randn(10, 3) for _ in range(n_drones)]
    
    current_time = 0.0
    for i in range(n_drones):
        comm.broadcast_trajectory(
            i, trajectories[i], control_seqs[i],
            positions[i], current_time
        )
    
    current_time = 0.3
    for i in range(n_drones):
        trajs, ctrls, pos = comm.get_neighbor_trajectories(i, current_time)
        
        print(f"  Drone {i} received {len(trajs)} trajectories")
        if i > 0:
            assert 0 in trajs, f"Drone {i} should have received trajectory from drone 0"
    
    stats = comm.get_stats()
    print(f"  Packets sent: {stats['packets_sent']}")
    print(f"  Packets lost: {stats['packets_lost']}")
    print(f"  Loss rate: {stats['loss_rate']:.2%}")
    
    assert stats['packets_sent'] == n_drones * (n_drones - 1)
    assert stats['loss_rate'] == 0.0
    
    comm_lossy = DMPCCommunicationLayer(
        n_drones=3, max_delay=1, packet_loss_rate=1.0, communication_range=30.0
    )
    
    for i in range(3):
        comm_lossy.broadcast_trajectory(
            i, trajectories[i], control_seqs[i],
            positions[i], 0.0
        )
    
    current_time = 0.2
    trajs_0, _, _ = comm_lossy.get_neighbor_trajectories(0, current_time)
    assert len(trajs_0) == 0, "Should have lost all packets with 100% loss rate"
    
    print(f"  Lossy test - received {len(trajs_0)} trajectories (expected 0)")
    
    comm.reset(n_drones=5)
    assert comm.n_drones == 5
    
    print("  DMPC Communication Layer test PASSED!")

def test_heterogeneous_drone_config():
    print("\nTesting Heterogeneous Drone Config (Feature #2)...")
    
    drone_types = HeterogeneousDroneConfig.DRONE_TYPES
    print(f"  Available drone types: {list(drone_types.keys())}")
    
    for type_name, config in drone_types.items():
        drone_config = HeterogeneousDroneConfig.get_config(type_name)
        
        assert 'max_vel' in drone_config
        assert 'max_acc' in drone_config
        assert 'mass' in drone_config
        assert 'radius' in drone_config
        
        print(f"  {type_name}: vel={config['max_vel']}, acc={config['max_acc']}, mass={config['mass']}")
    
    random_type = HeterogeneousDroneConfig.get_random_type()
    print(f"  Random type: {random_type}")
    assert random_type in drone_types
    
    swarm_mixed = HeterogeneousDroneConfig.create_heterogeneous_swarm(10, formation='mixed')
    print(f"  Mixed swarm types: {swarm_mixed}")
    assert len(swarm_mixed) == 10
    
    swarm_standard = HeterogeneousDroneConfig.create_heterogeneous_swarm(5, formation='standard')
    assert all(t == 'standard' for t in swarm_standard)
    
    swarm_fast_heavy = HeterogeneousDroneConfig.create_heterogeneous_swarm(6, formation='fast_heavy')
    for i in range(6):
        expected = 'fast' if i % 2 == 0 else 'heavy'
        assert swarm_fast_heavy[i] == expected
    
    print("  Heterogeneous Drone Config test PASSED!")

def test_formation_controller():
    print("\nTesting Formation Controller (Feature #2)...")
    n_drones = 5
    
    for formation_type in ['circle', 'line', 'v_shape', 'column', 'grid']:
        fc = FormationController(n_drones, formation_type=formation_type, spacing=3.0)
        
        assert fc.formation_type == formation_type
        assert fc._formation_offsets.shape == (n_drones, 3)
        
        leader_pos = np.array([10.0, 0.0, 5.0])
        leader_vel = np.array([1.0, 0.0, 0.0])
        
        target_pos_0 = fc.get_target_position(0, leader_pos, leader_vel)
        target_pos_1 = fc.get_target_position(1, leader_pos, leader_vel)
        
        dist = np.linalg.norm(target_pos_0 - target_pos_1)
        print(f"  Formation {formation_type}: drone 0-1 distance = {dist:.2f}m")
        
        assert dist > 1.0, "Drones should be spaced apart"
    
    fc = FormationController(n_drones, formation_type='circle', spacing=3.0)
    fc.update_spacing(5.0)
    assert fc.spacing == 5.0
    
    fc.update_count(10)
    assert fc.n_drones == 10
    assert fc._formation_offsets.shape == (10, 3)
    
    success = fc.switch_formation('line')
    assert success
    assert fc.formation_type == 'line'
    
    fc.formation_center = np.array([5.0, 5.0, 5.0])
    control, target = fc.get_formation_control(
        0, np.array([0.0, 0.0, 5.0, 0, 0, 0]),
        leader_position=None, leader_velocity=None
    )
    
    print(f"  Formation control output: {control}, target: {target}")
    assert control.shape == (3,)
    assert target.shape == (3,)
    
    print("  Formation Controller test PASSED!")

def test_rl_policy_network():
    print("\nTesting RL Policy Network (Feature #3)...")
    
    rl = RLPolicyNetwork(state_dim=12, action_dim=3, hidden_dims=[64, 32])
    
    assert len(rl.weights) == 3
    assert rl.weights[0].shape == (12, 64)
    assert rl.weights[1].shape == (64, 32)
    assert rl.weights[2].shape == (32, 3)
    
    state = np.array([0.0, 0.0, 5.0, 1.0, 0.0, 0.0])
    target = np.array([10.0, 0.0, 5.0, 0, 0, 0])
    obstacles = [
        {'type': 'sphere', 'x': 5.0, 'y': 0.0, 'z': 5.0, 'radius': 1.0}
    ]
    other_states = [np.array([3.0, 3.0, 5.0, 0, 0, 0])]
    
    action, confidence = rl.compute_action(
        state, target, obstacles, other_states, max_acc=5.0
    )
    
    print(f"  RL action: {action}")
    print(f"  RL confidence: {confidence:.2f}")
    
    assert action.shape == (3,)
    assert np.all(np.abs(action) <= 5.0)
    assert 0.0 <= confidence <= 1.0
    
    mpc_status = 1
    should_switch = rl.should_switch_to_rl(mpc_status, state, obstacles, other_states)
    assert should_switch, "Should switch to RL when MPC fails"
    
    mpc_status = 0
    state_danger = np.array([0.5, 0.0, 5.0, 0.0, 0.0, 0.0])
    obstacles_close = [
        {'type': 'sphere', 'x': 1.0, 'y': 0.0, 'z': 5.0, 'radius': 0.5}
    ]
    rl.should_switch_to_rl(mpc_status, state_danger, obstacles_close, [])
    
    print(f"  RL switch count: {rl.switch_count}")
    
    safe_action = rl._safety_layer(state, obstacles, other_states)
    print(f"  Safety layer action: {safe_action}")
    assert safe_action.shape == (3,)
    
    norm_state = rl._normalize_state(state, target, obstacles, other_states)
    print(f"  Normalized state shape: {norm_state.shape}")
    assert norm_state.shape == (12,)
    
    print("  RL Policy Network test PASSED!")

def test_full_simulation_step():
    print("\nTesting Full Simulation Step...")
    dynamics = DroneDynamics(dt=0.1)
    mpc = MPCController(dynamics, N=10)
    pf = PotentialField()
    vo = VelocityObstacle()
    og = ObstacleGenerator()
    
    obstacles = og.generate(n_trees=3, n_buildings=2)
    
    state = np.array([-10.0, 0.0, 5.0, 0.0, 0.0, 0.0])
    target = np.array([10.0, 0.0, 5.0, 0.0, 0.0, 0.0])
    
    other_state = np.array([0.0, 3.0, 5.0, 0.0, 0.0, 0.0])
    other_vel = np.array([0.0, 0.0, 0.0])
    
    comm = DMPCCommunicationLayer(n_drones=2, packet_loss_rate=0.0)
    
    positions = []
    for step in range(5):
        pf_force = pf.compute_force(state[:3], target, obstacles, velocity=state[3:6])
        vo_vel = vo.compute_avoidance_velocity(
            state[:3], state[3:6],
            other_state[:3], other_vel,
            v_max=3.0, id_a=0, id_b=1
        )
        
        control, pred_traj, control_seq = mpc.compute_control(
            state, target, obstacles=obstacles,
            pf_force=pf_force, vo_vel=vo_vel
        )
        
        state = dynamics.step(state, control)
        positions.append(state[:3].copy())
        
        if step == 0:
            print(f"  Step {step}: pos={state[:3]}, control={control}")
    
    positions = np.array(positions)
    print(f"  Final position after 5 steps: {state[:3]}")
    assert state[0] > -10.0, "Drone should move towards target"
    
    vel_changes = np.linalg.norm(np.diff(positions, axis=0) / 0.1, axis=1)
    print(f"  Velocity changes: {vel_changes}")
    assert np.max(vel_changes) < 5.0, "Velocity changes should be smooth"
    
    rl = RLPolicyNetwork()
    rl_action, confidence = rl.compute_action(
        state, target, obstacles, [other_state], max_acc=5.0
    )
    print(f"  RL backup action: {rl_action}, confidence: {confidence:.2f}")
    
    print("  Full Simulation Step test PASSED!")

def main():
    print("=" * 60)
    print("Running Drone Swarm MPC Simulation Tests")
    print("=" * 60)
    
    try:
        test_qp_solver()
        test_drone_dynamics()
        test_mpc_controller()
        test_mpc_weight_initialization()
        test_potential_field()
        test_smooth_force_transition()
        test_emergency_braking()
        test_velocity_obstacle()
        test_symmetric_collision_resolution()
        test_obstacle_generator()
        test_dmpc_communication_layer()
        test_heterogeneous_drone_config()
        test_formation_controller()
        test_rl_policy_network()
        test_full_simulation_step()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\nUNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
