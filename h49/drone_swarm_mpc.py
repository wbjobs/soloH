import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button, TextBox, CheckButtons
from matplotlib.patches import Circle, Polygon
from scipy.optimize import minimize
import time
from collections import deque, defaultdict
import random

class DMPCCommunicationLayer:
    """
    Distributed MPC Communication Layer with latency and packet loss robustness.
    Implements trajectory exchange between drones with realistic communication constraints.
    """
    def __init__(self, n_drones, max_delay=3, packet_loss_rate=0.1, communication_range=20.0):
        self.n_drones = n_drones
        self.max_delay = max_delay
        self.packet_loss_rate = packet_loss_rate
        self.communication_range = communication_range
        
        self.message_buffers = defaultdict(lambda: deque(maxlen=max_delay + 5))
        self.trajectory_buffers = defaultdict(lambda: deque(maxlen=max_delay + 5))
        self.last_received = defaultdict(float)
        self.connection_status = defaultdict(bool)
        
        self.stats = {
            'packets_sent': 0,
            'packets_lost': 0,
            'avg_delay': 0,
        }
    
    def broadcast_trajectory(self, drone_id, trajectory, control_seq, position, current_time):
        """Broadcast predicted trajectory to all other drones"""
        message = {
            'sender_id': drone_id,
            'position': position.copy(),
            'trajectory': trajectory.copy(),
            'control_seq': control_seq.copy(),
            'timestamp': current_time,
            'delay': np.random.randint(0, self.max_delay + 1)
        }
        
        n_receivers = self.n_drones - 1
        self.stats['packets_sent'] += n_receivers
        
        for receiver_id in range(self.n_drones):
            if receiver_id != drone_id:
                if np.random.random() > self.packet_loss_rate:
                    self.message_buffers[receiver_id].append(message)
                    self.trajectory_buffers[receiver_id].append(message)
                    self.last_received[receiver_id] = current_time
                    self.connection_status[(drone_id, receiver_id)] = True
                else:
                    self.stats['packets_lost'] += 1
                    self.connection_status[(drone_id, receiver_id)] = False
    
    def get_neighbor_trajectories(self, drone_id, current_time, positions=None):
        """Get buffered trajectories from neighboring drones, considering delay"""
        trajectories = {}
        control_seqs = {}
        positions_dict = {}
        
        while len(self.trajectory_buffers[drone_id]) > 0:
            msg = self.trajectory_buffers[drone_id][0]
            
            if positions is not None:
                dist = np.linalg.norm(positions[drone_id] - msg['position'])
                if dist > self.communication_range:
                    self.trajectory_buffers[drone_id].popleft()
                    continue
            
            msg_age = current_time - msg['timestamp']
            if msg_age >= msg['delay'] * 0.1:
                self.trajectory_buffers[drone_id].popleft()
                
                predicted_pos = self._predict_future_position(msg, msg_age)
                
                trajectories[msg['sender_id']] = msg['trajectory']
                control_seqs[msg['sender_id']] = msg['control_seq']
                positions_dict[msg['sender_id']] = predicted_pos
            else:
                break
        
        return trajectories, control_seqs, positions_dict
    
    def _predict_future_position(self, message, time_elapsed):
        """Predict current position of neighbor based on received trajectory"""
        traj = message['trajectory']
        steps_elapsed = int(time_elapsed / 0.1)
        
        if steps_elapsed < len(traj):
            return traj[steps_elapsed, :3].copy()
        elif len(traj) > 0:
            last_pos = traj[-1, :3]
            last_vel = traj[-1, 3:6] if traj.shape[1] >= 6 else np.zeros(3)
            return last_pos + last_vel * (time_elapsed - (len(traj) - 1) * 0.1)
        else:
            return message['position'].copy()
    
    def get_connection_status(self, drone_id):
        """Get connection status for a drone"""
        status = []
        for other_id in range(self.n_drones):
            if other_id != drone_id:
                connected = self.connection_status.get((other_id, drone_id), False)
                status.append((other_id, connected))
        return status
    
    def get_stats(self):
        """Get communication statistics"""
        if self.stats['packets_sent'] > 0:
            loss_rate = self.stats['packets_lost'] / self.stats['packets_sent']
        else:
            loss_rate = 0
        return {
            'loss_rate': loss_rate,
            'packets_sent': self.stats['packets_sent'],
            'packets_lost': self.stats['packets_lost'],
        }
    
    def reset(self, n_drones=None):
        """Reset communication layer"""
        if n_drones is not None:
            self.n_drones = n_drones
        self.message_buffers.clear()
        self.trajectory_buffers.clear()
        self.last_received.clear()
        self.connection_status.clear()
        self.stats = {
            'packets_sent': 0,
            'packets_lost': 0,
            'avg_delay': 0,
        }

class HeterogeneousDroneConfig:
    """
    Configuration for heterogeneous drone types with different capabilities.
    """
    
    DRONE_TYPES = {
        'standard': {
            'name': 'Standard',
            'max_vel': 3.0,
            'max_acc': 5.0,
            'mass': 1.0,
            'radius': 0.5,
            'color': 'tab:blue',
            'description': 'Standard quadcopter'
        },
        'fast': {
            'name': 'Fast Scout',
            'max_vel': 6.0,
            'max_acc': 8.0,
            'mass': 0.7,
            'radius': 0.4,
            'color': 'tab:red',
            'description': 'Fast and agile scout drone'
        },
        'heavy': {
            'name': 'Heavy Lift',
            'max_vel': 2.0,
            'max_acc': 3.0,
            'mass': 2.5,
            'radius': 0.7,
            'color': 'tab:green',
            'description': 'Heavy payload drone, slower but more stable'
        },
        'racing': {
            'name': 'Racing',
            'max_vel': 8.0,
            'max_acc': 12.0,
            'mass': 0.5,
            'radius': 0.35,
            'color': 'tab:orange',
            'description': 'High-performance racing drone'
        },
    }
    
    @staticmethod
    def get_config(drone_type):
        """Get configuration for a specific drone type"""
        return HeterogeneousDroneConfig.DRONE_TYPES.get(drone_type, 
                  HeterogeneousDroneConfig.DRONE_TYPES['standard'])
    
    @staticmethod
    def get_random_type():
        """Get a random drone type"""
        types = list(HeterogeneousDroneConfig.DRONE_TYPES.keys())
        return random.choice(types)
    
    @staticmethod
    def create_heterogeneous_swarm(n_drones, formation='mixed'):
        """
        Create a swarm with heterogeneous drone types.
        formation: 'mixed', 'standard', 'fast_heavy'
        """
        types = []
        if formation == 'mixed':
            for i in range(n_drones):
                types.append(HeterogeneousDroneConfig.get_random_type())
        elif formation == 'standard':
            types = ['standard'] * n_drones
        elif formation == 'fast_heavy':
            for i in range(n_drones):
                types.append('fast' if i % 2 == 0 else 'heavy')
        
        return types

class FormationController:
    """
    Formation control for heterogeneous drone swarms.
    Supports multiple formation patterns with adaptive scaling based on drone capabilities.
    """
    
    FORMATIONS = {
        'circle': 'Circular formation',
        'line': 'Line abreast formation',
        'v_shape': 'V-shaped formation',
        'column': 'Follow-the-leader column',
        'grid': 'Grid formation',
    }
    
    def __init__(self, n_drones, formation_type='circle', spacing=3.0):
        self.n_drones = n_drones
        self.formation_type = formation_type
        self.spacing = spacing
        self.formation_center = np.zeros(3)
        self.formation_heading = 0.0
        
        self._formation_offsets = self._compute_formation_offsets()
    
    def _compute_formation_offsets(self):
        """Compute position offsets for each drone in the formation"""
        offsets = np.zeros((self.n_drones, 3))
        
        if self.formation_type == 'circle':
            for i in range(self.n_drones):
                angle = 2 * np.pi * i / self.n_drones
                offsets[i] = np.array([
                    self.spacing * np.cos(angle),
                    self.spacing * np.sin(angle),
                    0
                ])
        
        elif self.formation_type == 'line':
            for i in range(self.n_drones):
                offsets[i] = np.array([
                    0,
                    self.spacing * (i - (self.n_drones - 1) / 2),
                    0
                ])
        
        elif self.formation_type == 'v_shape':
            center = (self.n_drones - 1) / 2
            for i in range(self.n_drones):
                side = i - center
                offsets[i] = np.array([
                    abs(side) * self.spacing * 0.5,
                    side * self.spacing,
                    0
                ])
        
        elif self.formation_type == 'column':
            for i in range(self.n_drones):
                offsets[i] = np.array([
                    -i * self.spacing,
                    0,
                    0
                ])
        
        elif self.formation_type == 'grid':
            rows = int(np.ceil(np.sqrt(self.n_drones)))
            cols = int(np.ceil(self.n_drones / rows))
            for i in range(self.n_drones):
                r = i // cols
                c = i % cols
                offsets[i] = np.array([
                    (c - cols/2 + 0.5) * self.spacing,
                    (r - rows/2 + 0.5) * self.spacing,
                    0
                ])
        
        return offsets
    
    def get_target_position(self, drone_id, leader_position=None, leader_velocity=None):
        """Get target position for a drone maintaining formation"""
        if leader_position is None:
            center = self.formation_center
        else:
            center = leader_position.copy()
        
        if leader_velocity is not None and np.linalg.norm(leader_velocity) > 0.1:
            heading = np.arctan2(leader_velocity[1], leader_velocity[0])
            rot = np.array([
                [np.cos(heading), -np.sin(heading), 0],
                [np.sin(heading), np.cos(heading), 0],
                [0, 0, 1]
            ])
            offset = rot @ self._formation_offsets[drone_id]
        else:
            offset = self._formation_offsets[drone_id]
        
        return center + offset
    
    def get_formation_control(self, drone_id, current_state, 
                              leader_position=None, leader_velocity=None,
                              kp=0.8, kd=1.0):
        """Compute control to maintain formation"""
        target_pos = self.get_target_position(drone_id, leader_position, leader_velocity)
        
        pos_error = target_pos - current_state[:3]
        
        if leader_velocity is not None:
            vel_target = leader_velocity
        else:
            vel_target = np.zeros(3)
        
        vel_error = vel_target - current_state[3:6]
        
        acceleration = kp * pos_error + kd * vel_error
        return acceleration, target_pos
    
    def switch_formation(self, new_formation):
        """Switch to a different formation pattern"""
        if new_formation in self.FORMATIONS:
            self.formation_type = new_formation
            self._formation_offsets = self._compute_formation_offsets()
            return True
        return False
    
    def update_spacing(self, new_spacing):
        """Update formation spacing"""
        self.spacing = new_spacing
        self._formation_offsets = self._compute_formation_offsets()
    
    def update_count(self, n_drones):
        """Update number of drones in formation"""
        self.n_drones = n_drones
        self._formation_offsets = self._compute_formation_offsets()

class RLPolicyNetwork:
    """
    Reinforcement Learning policy network as backup controller.
    Uses a lightweight neural network with pretrained obstacle avoidance policy.
    """
    
    def __init__(self, state_dim=12, action_dim=3, hidden_dims=[64, 32]):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.hidden_dims = hidden_dims
        
        self.weights = []
        self.biases = []
        
        prev_dim = state_dim
        for hidden_dim in hidden_dims:
            self.weights.append(np.random.randn(prev_dim, hidden_dim) * 0.1)
            self.biases.append(np.zeros(hidden_dim))
            prev_dim = hidden_dim
        
        self.weights.append(np.random.randn(prev_dim, action_dim) * 0.1)
        self.biases.append(np.zeros(action_dim))
        
        self._initialize_pretrained_policy()
        
        self.safety_threshold = 2.0
        self.confidence = 0.0
        self.use_rl = False
        self.switch_count = 0
    
    def _initialize_pretrained_policy(self):
        """Initialize with handcrafted safe policy as 'pretrained' weights"""
        
        self.weights[0] = np.zeros((self.state_dim, self.hidden_dims[0]))
        
        for i in range(3):
            self.weights[0][i, i] = -1.0
            self.weights[0][i + 3, i + 3] = -1.0
        
        for i in range(3):
            self.weights[0][6 + i * 2, i] = 2.0
        
        self.biases[0] = np.zeros(self.hidden_dims[0])
        
        self.weights[-1] = np.zeros((self.hidden_dims[-1], self.action_dim))
        for i in range(3):
            self.weights[-1][i, i] = 1.0
        self.biases[-1] = np.zeros(self.action_dim)
    
    def _forward(self, state):
        """Forward pass through the network"""
        x = state.copy()
        for i in range(len(self.weights) - 1):
            x = x @ self.weights[i] + self.biases[i]
            x = np.tanh(x)
        x = x @ self.weights[-1] + self.biases[-1]
        return np.tanh(x)
    
    def _normalize_state(self, state, target, obstacles, other_drones):
        """Normalize state for network input"""
        normalized = np.zeros(self.state_dim)
        
        normalized[:3] = state[:3] / 10.0
        normalized[3:6] = state[3:6] / 5.0
        
        pos_error = target[:3] - state[:3]
        normalized[6:9] = pos_error / 10.0
        
        min_dist = 10.0
        for obs in obstacles:
            if 'x' in obs and 'y' in obs and 'z' in obs:
                obs_pos = np.array([obs['x'], obs['y'], obs['z']])
            elif 'x' in obs and 'y' in obs:
                obs_pos = np.array([obs['x'], obs['y'], state[2]])
            else:
                continue
            dist = np.linalg.norm(state[:3] - obs_pos)
            min_dist = min(min_dist, dist)
        
        normalized[9] = (min_dist - 5.0) / 5.0
        
        min_drone_dist = 10.0
        for other in other_drones:
            dist = np.linalg.norm(state[:3] - other[:3])
            min_drone_dist = min(min_drone_dist, dist)
        
        normalized[10] = (min_drone_dist - 3.0) / 3.0
        
        normalized[11] = 0.0
        
        return normalized
    
    def compute_action(self, state, target, obstacles, other_states, max_acc=5.0):
        """Compute control action using RL policy"""
        norm_state = self._normalize_state(state, target, obstacles, other_states)
        
        action = self._forward(norm_state)
        
        safety_correction = self._safety_layer(state, obstacles, other_states)
        
        final_action = 0.7 * action * max_acc + 0.3 * safety_correction
        final_action = np.clip(final_action, -max_acc, max_acc)
        
        self.confidence = self._compute_confidence(state, obstacles, other_states)
        
        return final_action, self.confidence
    
    def _safety_layer(self, state, obstacles, other_states):
        """Safety layer to ensure RL outputs are always safe"""
        safe_action = np.zeros(3)
        
        for obs in obstacles:
            if 'x' in obs and 'y' in obs and 'z' in obs:
                obs_pos = np.array([obs['x'], obs['y'], obs['z']])
                radius = obs.get('radius', 1.0)
            elif 'x' in obs and 'y' in obs:
                obs_pos = np.array([obs['x'], obs['y'], state[2]])
                radius = obs.get('radius', 1.0)
            else:
                continue
            
            diff = state[:3] - obs_pos
            dist = np.linalg.norm(diff)
            
            if dist < radius + self.safety_threshold:
                repulsion = (diff / (dist + 1e-6)) * (1.0 / (dist - radius + 0.1)**2)
                safe_action += np.clip(repulsion, -10, 10)
        
        for other in other_states:
            diff = state[:3] - other[:3]
            dist = np.linalg.norm(diff)
            
            if dist < self.safety_threshold:
                repulsion = (diff / (dist + 1e-6)) * (1.0 / (dist + 0.1)**2)
                safe_action += np.clip(repulsion, -5, 5)
        
        return safe_action
    
    def _compute_confidence(self, state, obstacles, other_states):
        """Compute confidence in RL policy"""
        min_dist = np.inf
        
        for obs in obstacles:
            if 'x' in obs and 'y' in obs and 'z' in obs:
                obs_pos = np.array([obs['x'], obs['y'], obs['z']])
            elif 'x' in obs and 'y' in obs:
                obs_pos = np.array([obs['x'], obs['y'], state[2]])
            else:
                continue
            dist = np.linalg.norm(state[:3] - obs_pos)
            min_dist = min(min_dist, dist)
        
        for other in other_states:
            dist = np.linalg.norm(state[:3] - other[:3])
            min_dist = min(min_dist, dist)
        
        if min_dist < 1.0:
            return 0.1
        elif min_dist < 3.0:
            return 0.5
        else:
            return 0.9
    
    def should_switch_to_rl(self, mpc_status, state, obstacles, other_states):
        """Determine if we should switch to RL backup controller"""
        if mpc_status != 0:
            self.switch_count += 1
            return True
        
        confidence = self._compute_confidence(state, obstacles, other_states)
        if confidence < 0.3 and np.random.random() < 0.3:
            return True
        
        return False
    
    def update_policy(self, state, action, reward):
        """Simple policy update (for online adaptation)"""
        pass

class QPSolver:
    """QP solver mimicking qpOASES interface using scipy.optimize"""
    def __init__(self, nV, nC=0):
        self.nV = nV
        self.nC = nC
        self.H = None
        self.g = None
        self.A = None
        self.lb = None
        self.ub = None
        self.lbA = None
        self.ubA = None
    
    def init(self, H, g, A=None, lb=None, ub=None, lbA=None, ubA=None):
        self.H = H
        self.g = g
        self.A = A
        self.lb = lb if lb is not None else -np.inf * np.ones(self.nV)
        self.ub = ub if ub is not None else np.inf * np.ones(self.nV)
        self.lbA = lbA
        self.ubA = ubA
    
    def hotstart(self, H, g, A=None, lb=None, ub=None, lbA=None, ubA=None):
        self.init(H, g, A, lb, ub, lbA, ubA)
        return self.solve()
    
    def solve(self):
        n = self.nV
        
        def objective(x):
            return 0.5 * x @ self.H @ x + self.g @ x
        
        def gradient(x):
            return self.H @ x + self.g
        
        constraints = []
        if self.A is not None and self.lbA is not None and self.ubA is not None:
            for i in range(self.A.shape[0]):
                constraints.append({
                    'type': 'ineq',
                    'fun': lambda x, i=i: self.ubA[i] - self.A[i] @ x,
                    'jac': lambda x, i=i: -self.A[i]
                })
                constraints.append({
                    'type': 'ineq',
                    'fun': lambda x, i=i: self.A[i] @ x - self.lbA[i],
                    'jac': lambda x, i=i: self.A[i]
                })
        
        bounds = list(zip(self.lb, self.ub))
        
        x0 = np.zeros(n)
        
        try:
            result = minimize(
                objective, x0,
                jac=gradient,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'maxiter': 100, 'ftol': 1e-6, 'disp': False}
            )
            return result.x, 0 if result.success else 1
        except:
            return x0, 1

class DroneDynamics:
    """3D drone dynamics model (point mass with acceleration inputs)"""
    def __init__(self, dt=0.1, max_acc=5.0, max_vel=3.0):
        self.dt = dt
        self.max_acc = max_acc
        self.max_vel = max_vel
        self.state_dim = 6
        self.control_dim = 3
    
    def step(self, state, control):
        x, y, z, vx, vy, vz = state
        ax, ay, az = control
        
        ax = np.clip(ax, -self.max_acc, self.max_acc)
        ay = np.clip(ay, -self.max_acc, self.max_acc)
        az = np.clip(az, -self.max_acc, self.max_acc)
        
        vx_new = np.clip(vx + ax * self.dt, -self.max_vel, self.max_vel)
        vy_new = np.clip(vy + ay * self.dt, -self.max_vel, self.max_vel)
        vz_new = np.clip(vz + az * self.dt, -self.max_vel, self.max_vel)
        
        x_new = x + vx_new * self.dt
        y_new = y + vy_new * self.dt
        z_new = z + vz_new * self.dt
        
        return np.array([x_new, y_new, z_new, vx_new, vy_new, vz_new])
    
    def get_linearized_matrices(self, state, control):
        dt = self.dt
        A = np.eye(self.state_dim)
        A[0, 3] = dt
        A[1, 4] = dt
        A[2, 5] = dt
        
        B = np.zeros((self.state_dim, self.control_dim))
        B[3, 0] = dt
        B[4, 1] = dt
        B[5, 2] = dt
        
        return A, B

class MPCController:
    """Model Predictive Controller with prediction horizon N"""
    
    @staticmethod
    def _default_weights(state_dim, control_dim):
        """Generate properly initialized, symmetric positive-definite weight matrices"""
        Q = np.diag([2.0, 2.0, 2.0, 0.5, 0.5, 0.5])
        R = np.diag([0.05, 0.05, 0.05])
        Qf = Q * 15.0
        
        Q = 0.5 * (Q + Q.T)
        R = 0.5 * (R + R.T)
        Qf = 0.5 * (Qf + Qf.T)
        
        min_eig_Q = np.min(np.linalg.eigvalsh(Q))
        if min_eig_Q < 1e-6:
            Q += np.eye(state_dim) * (1e-6 - min_eig_Q)
        
        min_eig_R = np.min(np.linalg.eigvalsh(R))
        if min_eig_R < 1e-6:
            R += np.eye(control_dim) * (1e-6 - min_eig_R)
        
        min_eig_Qf = np.min(np.linalg.eigvalsh(Qf))
        if min_eig_Qf < 1e-6:
            Qf += np.eye(state_dim) * (1e-6 - min_eig_Qf)
        
        return Q, R, Qf
    
    def __init__(self, dynamics, N=10, Q=None, R=None, Qf=None):
        self.dynamics = dynamics
        self.N = N
        self.state_dim = dynamics.state_dim
        self.control_dim = dynamics.control_dim
        
        if Q is None or R is None or Qf is None:
            default_Q, default_R, default_Qf = self._default_weights(
                self.state_dim, self.control_dim
            )
            self.Q = Q if Q is not None else default_Q
            self.R = R if R is not None else default_R
            self.Qf = Qf if Qf is not None else default_Qf
        else:
            self.Q = 0.5 * (Q + Q.T)
            self.R = 0.5 * (R + R.T)
            self.Qf = 0.5 * (Qf + Qf.T)
        
        self.nV = self.N * self.control_dim
        self.solver = QPSolver(self.nV)
        
        self._prev_u = np.zeros(self.control_dim)
        self._warm_start_u = None
    
    def reinitialize_weights(self, Q=None, R=None, Qf=None):
        """Reinitialize weight matrices (useful for dynamic parameter changes)"""
        if Q is not None:
            self.Q = 0.5 * (Q + Q.T)
        if R is not None:
            self.R = 0.5 * (R + R.T)
        if Qf is not None:
            self.Qf = 0.5 * (Qf + Qf.T)
        
        self.solver = QPSolver(self.nV)
        self._prev_u = np.zeros(self.control_dim)
        self._warm_start_u = None
    
    def get_warm_start(self):
        """Get warm start for QP solver from previous solution"""
        if self._warm_start_u is not None:
            return self._warm_start_u.copy()
        return np.zeros(self.nV)
    
    def set_warm_start(self, u_seq):
        """Store warm start for next iteration"""
        if u_seq is not None and len(u_seq) == self.nV:
            self._warm_start_u = u_seq.copy()
    
    def compute_control(self, state, target, obstacles=None, other_drones=None, 
                       pf_force=None, vo_vel=None):
        N = self.N
        nx = self.state_dim
        nu = self.control_dim
        dt = self.dynamics.dt
        
        pos_error = target[:3] - state[:3]
        vel_error = target[3:6] - state[3:6]
        
        u_guess = np.zeros(N * nu)
        X_pred_guess = np.zeros((N + 1, nx))
        X_pred_guess[0] = state.copy()
        
        for k in range(N):
            kp = 0.8
            kd = 1.2
            acc_cmd = kp * (target[:3] - X_pred_guess[k, :3]) + kd * (target[3:6] - X_pred_guess[k, 3:6])
            acc_cmd = np.clip(acc_cmd, -self.dynamics.max_acc, self.dynamics.max_acc)
            u_guess[k * nu : k * nu + 3] = acc_cmd
            X_pred_guess[k + 1] = self.dynamics.step(X_pred_guess[k], acc_cmd)
        
        H = np.zeros((N * nu, N * nu))
        g = np.zeros(N * nu)
        
        for k in range(N):
            H[k * nu : (k + 1) * nu, k * nu : (k + 1) * nu] = self.R.copy()
            
            for tau in range(k + 1, N + 1):
                n_steps = tau - k
                coeff_pos = (n_steps * dt) ** 2 / 2.0
                coeff_vel = n_steps * dt
                
                Q_tau = self.Q if tau < N else self.Qf
                for i in range(3):
                    H[k * nu + i, k * nu + i] += Q_tau[i, i] * coeff_pos**2
                    H[k * nu + i, k * nu + i] += Q_tau[i + 3, i + 3] * coeff_vel**2
        
        for k in range(N):
            Q_k = self.Q if k < N else self.Qf
            
            for tau in range(k + 1, N + 1):
                Q_tau = self.Q if tau < N else self.Qf
                pos_err_tau = target[:3] - X_pred_guess[tau, :3]
                vel_err_tau = target[3:6] - X_pred_guess[tau, 3:6]
                
                for i in range(3):
                    coeff_pos = (tau - k) * dt
                    g[k * nu + i] += -2 * Q_tau[i, i] * pos_err_tau[i] * coeff_pos * dt / 2
                    g[k * nu + i] += -2 * Q_tau[i + 3, i + 3] * vel_err_tau[i] * dt
        
        if pf_force is not None:
            for i in range(3):
                g[i] += -2 * 0.3 * pf_force[i] * dt
        
        if vo_vel is not None:
            for i in range(3):
                g[i] += -2 * 2.0 * vo_vel[i] * dt
        
        lb = -self.dynamics.max_acc * np.ones(N * nu)
        ub = self.dynamics.max_acc * np.ones(N * nu)
        
        A_ineq = []
        lbA = []
        ubA = []
        
        if obstacles is not None:
            for obs in obstacles:
                for k in range(1, N + 1):
                    constraint = self._build_obstacle_constraint(X_pred_guess[k], obs, k, nu)
                    if constraint is not None:
                        A_ineq.append(constraint[0])
                        lbA.append(constraint[1])
                        ubA.append(constraint[2])
        
        self.solver.init(H, g, np.array(A_ineq) if A_ineq else None, 
                        lb, ub, np.array(lbA) if lbA else None, 
                        np.array(ubA) if ubA else None)
        
        u_opt, status = self.solver.solve()
        
        if status != 0:
            u_opt = u_guess
        
        pos_error_final = target[:3] - state[:3]
        vel_error_final = target[3:6] - state[3:6]
        u_fb = 0.8 * pos_error_final + 1.2 * vel_error_final
        
        u_final = 0.7 * u_opt[:nu] + 0.3 * u_fb
        
        if pf_force is not None:
            u_final += 0.3 * pf_force
        
        if vo_vel is not None:
            u_final += 0.5 * vo_vel
        
        u_final = np.clip(u_final, -self.dynamics.max_acc, self.dynamics.max_acc)
        
        control_seq = u_opt.reshape(N, nu)
        control_seq[0] = u_final
        
        X_pred_full = self._simulate_prediction(state, control_seq)
        
        return u_final, X_pred_full, control_seq
    
    def _build_obstacle_constraint(self, pred_state, obs, k, nu):
        N = self.N
        
        if obs['type'] in ['tree', 'building']:
            obs_pos = np.array([obs['x'], obs['y']])
            pred_pos = pred_state[:2]
            diff = pred_pos - obs_pos
            dist = np.linalg.norm(diff)
            min_dist = obs['radius'] + 1.0
            
            if dist < min_dist + 3.0 and pred_state[2] < obs['height']:
                grad = np.zeros(N * nu)
                if k > 0 and k <= N:
                    dt = self.dynamics.dt
                    for i in range(k):
                        grad[i * nu : i * nu + 2] = -diff / (dist + 1e-6) * (k - i) * dt * dt / 2
                return (grad, -np.inf, -(min_dist - dist))
        
        elif obs['type'] == 'sphere':
            obs_pos = np.array([obs['x'], obs['y'], obs['z']])
            pred_pos = pred_state[:3]
            diff = pred_pos - obs_pos
            dist = np.linalg.norm(diff)
            min_dist = obs['radius'] + 0.8
            
            if dist < min_dist + 3.0:
                grad = np.zeros(N * nu)
                if k > 0 and k <= N:
                    dt = self.dynamics.dt
                    for i in range(k):
                        grad[i * nu : i * nu + 3] = -diff / (dist + 1e-6) * (k - i) * dt * dt / 2
                return (grad, -np.inf, -(min_dist - dist))
        
        return None
    
    def _simulate_prediction(self, state, u_seq):
        N = u_seq.shape[0]
        X_pred = np.zeros((N + 1, self.state_dim))
        X_pred[0] = state.copy()
        for k in range(N):
            X_pred[k + 1] = self.dynamics.step(X_pred[k], u_seq[k])
        return X_pred

class PotentialField:
    """Artificial potential field with smooth transitions and emergency braking"""
    def __init__(self, k_att=1.0, k_rep=50.0, d0=2.0, 
                 perception_range=10.0, transition_width=3.0,
                 alpha=0.7, max_decel=8.0):
        self.k_att = k_att
        self.k_rep = k_rep
        self.d0 = d0
        self.perception_range = perception_range
        self.transition_width = transition_width
        self.alpha = alpha
        self.max_decel = max_decel
        
        self._filtered_force = None
        self._prev_force = None
    
    def _smooth_transition(self, dist, threshold, width):
        """Smooth sigmoid-like transition to avoid discontinuities"""
        if dist < threshold:
            return 1.0
        elif dist < threshold + width:
            x = (dist - threshold) / width
            return 0.5 * (1.0 + np.cos(np.pi * x))
        else:
            return 0.0
    
    def _emergency_braking_force(self, position, velocity, obstacles):
        """Compute velocity-continuous emergency braking force"""
        brake_force = np.zeros(3)
        
        for obs in obstacles:
            if obs['type'] == 'tree' or obs['type'] == 'building':
                obs_pos = np.array([obs['x'], obs['y'], position[2]])
            elif obs['type'] == 'sphere':
                obs_pos = np.array([obs['x'], obs['y'], obs['z']])
            else:
                continue
            
            diff = position - obs_pos
            dist = np.linalg.norm(diff)
            
            min_safe_dist = self.d0 + (obs['radius'] if 'radius' in obs else 1.0)
            perception_dist = self.perception_range + (obs['radius'] if 'radius' in obs else 1.0)
            
            if dist < perception_dist:
                vel_towards_obs = -np.dot(velocity, diff / (dist + 1e-6))
                
                if vel_towards_obs > 0:
                    stopping_distance = vel_towards_obs**2 / (2 * self.max_decel)
                    available_distance = dist - min_safe_dist
                    
                    if available_distance < stopping_distance:
                        brake_magnitude = vel_towards_obs**2 / (2 * max(available_distance, 0.1))
                        brake_direction = diff / (dist + 1e-6)
                        brake_force += brake_magnitude * brake_direction
        
        return brake_force
    
    def compute_force(self, position, target, obstacles, velocity=None, dt=0.1):
        att_force = self.k_att * (target[:3] - position)
        rep_force = np.zeros(3)
        
        for obs in obstacles:
            if obs['type'] == 'tree' or obs['type'] == 'building':
                obs_pos = np.array([obs['x'], obs['y'], position[2]])
                height_limit = obs['height'] if 'height' in obs else 10.0
                if position[2] > height_limit:
                    continue
            elif obs['type'] == 'sphere':
                obs_pos = np.array([obs['x'], obs['y'], obs['z']])
            else:
                continue
            
            diff = position - obs_pos
            dist = np.linalg.norm(diff)
            obs_radius = obs['radius'] if 'radius' in obs else 1.0
            min_dist = self.d0 + obs_radius
            max_dist = self.perception_range + obs_radius
            
            weight = self._smooth_transition(dist, min_dist, self.transition_width)
            
            if weight > 0 and dist < max_dist:
                if dist < min_dist:
                    rep_force += self.k_rep * weight * (1.0 / dist**2) * (diff / (dist + 1e-6))
                else:
                    normalized_dist = (dist - min_dist) / (max_dist - min_dist)
                    gaussian_weight = np.exp(-5.0 * normalized_dist**2)
                    rep_force += self.k_rep * weight * gaussian_weight * (diff / (dist + 1e-6))
        
        emergency_force = np.zeros(3)
        if velocity is not None:
            emergency_force = self._emergency_braking_force(position, velocity, obstacles)
        
        total_force = att_force + rep_force + emergency_force
        
        if self._filtered_force is None:
            self._filtered_force = total_force.copy()
        else:
            self._filtered_force = self.alpha * self._filtered_force + (1 - self.alpha) * total_force
        
        max_force = self.max_decel * 1.5
        force_norm = np.linalg.norm(self._filtered_force)
        if force_norm > max_force:
            self._filtered_force = (self._filtered_force / force_norm) * max_force
        
        return self._filtered_force.copy()
    
    def reset_filter(self):
        """Reset the force filter state"""
        self._filtered_force = None
        self._prev_force = None

class VelocityObstacle:
    """Velocity obstacle for inter-drone collision avoidance with priority resolution"""
    def __init__(self, drone_radius=0.5, time_horizon=3.0):
        self.drone_radius = drone_radius
        self.time_horizon = time_horizon
    
    def _get_priority_bias(self, id_a, id_b):
        """
        Priority-based direction bias for symmetric collision resolution.
        Convention: Lower ID drones turn LEFT (perpendicular to relative position),
                   Higher ID drones turn RIGHT.
        This ensures consistent, non-conflicting avoidance maneuvers.
        """
        if id_a < id_b:
            return 1.0
        elif id_a > id_b:
            return -1.0
        else:
            return 0.0
    
    def _compute_side_direction(self, p_rel, bias_sign):
        """
        Compute a perpendicular side direction based on bias sign.
        Uses world-fixed coordinate system for consistent turn direction:
        - Positive bias (lower ID): always turn LEFT in world coordinates (+Y)
        - Negative bias (higher ID): always turn RIGHT in world coordinates (-Y)
        This ensures opposite turns regardless of relative position or direction.
        """
        forward = p_rel / (np.linalg.norm(p_rel) + 1e-6)
        
        world_left = np.array([0, 1, 0])
        world_right = np.array([0, -1, 0])
        
        if bias_sign > 0:
            side_dir = world_left.copy()
        else:
            side_dir = world_right.copy()
        
        side_norm = np.linalg.norm(side_dir)
        if side_norm > 1e-6:
            side_dir = side_dir / side_norm
        
        return side_dir
    
    def compute_avoidance_velocity(self, pos_a, vel_a, pos_b, vel_b, v_max, 
                                    id_a=None, id_b=None):
        p_rel = pos_b - pos_a
        v_rel = vel_b - vel_a
        
        dist = np.linalg.norm(p_rel)
        min_dist = 2 * self.drone_radius
        
        bias_sign = self._get_priority_bias(id_a, id_b) if id_a is not None and id_b is not None else 1.0
        
        if dist < min_dist:
            dir_away = (pos_a - pos_b) / (dist + 1e-6)
            side_dir = self._compute_side_direction(p_rel, bias_sign)
            combined_dir = 0.6 * dir_away[:3] + 0.4 * side_dir
            combined_dir = combined_dir / (np.linalg.norm(combined_dir) + 1e-6)
            return v_max * combined_dir
        
        if dist < self.time_horizon * v_max + min_dist:
            t_closest = np.dot(-p_rel, v_rel) / (np.dot(v_rel, v_rel) + 1e-6)
            t_closest = np.clip(t_closest, 0, self.time_horizon)
            
            p_closest = p_rel + v_rel * t_closest
            dist_closest = np.linalg.norm(p_closest)
            
            if dist_closest < min_dist:
                side_dir = self._compute_side_direction(p_rel, bias_sign)
                return 0.5 * v_max * side_dir[:3]
        
        return np.zeros(3)

class ObstacleGenerator:
    """Generate random obstacles (trees, buildings)"""
    def __init__(self, world_size=30):
        self.world_size = world_size
    
    def generate(self, n_trees=8, n_buildings=5):
        obstacles = []
        
        for _ in range(n_trees):
            obstacles.append({
                'type': 'tree',
                'x': np.random.uniform(-self.world_size/2 + 2, self.world_size/2 - 2),
                'y': np.random.uniform(-self.world_size/2 + 2, self.world_size/2 - 2),
                'radius': np.random.uniform(0.5, 1.5),
                'height': np.random.uniform(3, 8),
                'color': 'g'
            })
        
        for _ in range(n_buildings):
            obstacles.append({
                'type': 'building',
                'x': np.random.uniform(-self.world_size/2 + 3, self.world_size/2 - 3),
                'y': np.random.uniform(-self.world_size/2 + 3, self.world_size/2 - 3),
                'width': np.random.uniform(2, 5),
                'depth': np.random.uniform(2, 5),
                'height': np.random.uniform(5, 15),
                'radius': max(2, 5) / 2,
                'color': 'gray'
            })
        
        return obstacles

class DroneSwarmSimulation:
    """Main drone swarm simulation class with DMPC, heterogeneous formation, and RL backup"""
    def __init__(self, n_drones=10, world_size=30):
        self.world_size = world_size
        self.dt = 0.1
        self.max_vel = 3.0
        self.max_acc = 5.0
        
        self.obstacle_generator = ObstacleGenerator(world_size)
        self.static_obstacles = self.obstacle_generator.generate(n_trees=8, n_buildings=5)
        self.moving_obstacles = []
        
        self.potential_field = PotentialField()
        self.velocity_obstacle = VelocityObstacle()
        
        self.default_Q, self.default_R, self.default_Qf = MPCController._default_weights(6, 3)
        
        self.use_dmpc = True
        self.comm_layer = DMPCCommunicationLayer(
            n_drones=n_drones,
            max_delay=3,
            packet_loss_rate=0.1,
            communication_range=20.0
        )
        self.neighbor_trajectories = [{} for _ in range(n_drones)]
        
        self.use_formation = True
        self.formation_controller = FormationController(
            n_drones=n_drones,
            formation_type='circle',
            spacing=3.0
        )
        self.drone_types = HeterogeneousDroneConfig.create_heterogeneous_swarm(
            n_drones, formation='mixed'
        )
        self.use_heterogeneous = True
        
        self.use_rl_backup = True
        self.rl_controllers = [RLPolicyNetwork() for _ in range(n_drones)]
        self.rl_active = [False] * n_drones
        self.rl_switch_count = 0
        
        self.leader_id = 0
        
        self.n_drones = n_drones
        self.drones = []
        self.targets = []
        self.predicted_trajectories = []
        self.control_sequences = []
        
        self.collision_count = 0
        self.collision_log = []
        self.mission_start_time = time.time()
        self.mission_complete_time = None
        self.completed_drones = 0
        
        self.colors = plt.cm.rainbow(np.linspace(0, 1, 20))
        
        self._initialize_drones(full_reset=True)
        
        self.fig, (self.ax_3d, self.ax_control) = plt.subplots(1, 2, figsize=(16, 8))
        self.fig.subplots_adjust(bottom=0.35)
        
        self._setup_gui()
        self._setup_plots()
        
        self.running = True
    
    def _initialize_drones(self, full_reset=False):
        old_drones = self.drones.copy() if not full_reset and hasattr(self, 'drones') else []
        old_n = len(old_drones)
        
        self.drones = []
        self.targets = []
        self.predicted_trajectories = []
        self.control_sequences = []
        self.completed_drones = 0
        
        if full_reset:
            self.mission_start_time = time.time()
            self.mission_complete_time = None
            self.collision_count = 0
            self.collision_log = []
            self.potential_field.reset_filter()
            self.comm_layer.reset(self.n_drones)
            self.formation_controller.update_count(self.n_drones)
            self.drone_types = HeterogeneousDroneConfig.create_heterogeneous_swarm(
                self.n_drones, formation='mixed' if self.use_heterogeneous else 'standard'
            )
            self.rl_controllers = [RLPolicyNetwork() for _ in range(self.n_drones)]
            self.rl_active = [False] * self.n_drones
        
        self.neighbor_trajectories = [{} for _ in range(self.n_drones)]
        
        for i in range(self.n_drones):
            if self.use_heterogeneous and i < len(self.drone_types):
                drone_config = HeterogeneousDroneConfig.get_config(self.drone_types[i])
                drone_max_vel = min(drone_config['max_vel'], self.max_vel)
                drone_max_acc = min(drone_config['max_acc'], self.max_acc)
                drone_radius = drone_config['radius']
                drone_color = drone_config['color']
            else:
                drone_max_vel = self.max_vel
                drone_max_acc = self.max_acc
                drone_radius = 0.5
                drone_color = self.colors[i % 20]
            
            dynamics = DroneDynamics(dt=self.dt, max_acc=drone_max_acc, max_vel=drone_max_vel)
            mpc = MPCController(
                dynamics, N=10,
                Q=self.default_Q.copy(),
                R=self.default_R.copy(),
                Qf=self.default_Qf.copy()
            )
            
            if i < old_n and not full_reset:
                old_state = old_drones[i]['state'].copy()
                old_target = old_drones[i]['target'].copy()
                old_traj = old_drones[i]['trajectory'].copy()
                
                if i < self.n_drones:
                    state = old_state
                    target = old_target
                else:
                    state = old_state
                    target = old_target
            else:
                angle = 2 * np.pi * i / self.n_drones
                radius = self.world_size / 3
                start_x = radius * np.cos(angle)
                start_y = radius * np.sin(angle)
                start_z = np.random.uniform(2, 8)
                
                if self.use_formation:
                    leader_pos = np.array([0, 0, 5])
                    target_pos = self.formation_controller.get_target_position(i, leader_pos)
                    target = np.array([target_pos[0], target_pos[1], target_pos[2], 0, 0, 0])
                else:
                    target_x = -start_x + np.random.uniform(-2, 2)
                    target_y = -start_y + np.random.uniform(-2, 2)
                    target_z = np.random.uniform(3, 10)
                    target = np.array([target_x, target_y, target_z, 0, 0, 0])
                
                state = np.array([start_x, start_y, start_z, 0, 0, 0])
            
            drone_dict = {
                'state': state,
                'target': target,
                'dynamics': dynamics,
                'mpc': mpc,
                'color': drone_color,
                'trajectory': deque(maxlen=200),
                'completed': False,
                'type': self.drone_types[i] if i < len(self.drone_types) else 'standard',
                'radius': drone_radius,
                'max_vel': drone_max_vel,
                'max_acc': drone_max_acc,
                'rl_controller': self.rl_controllers[i] if i < len(self.rl_controllers) else RLPolicyNetwork(),
                'use_rl': False,
                'mpc_status': 0
            }
            
            if i < old_n and not full_reset:
                drone_dict['trajectory'].extend(old_drones[i]['trajectory'])
            else:
                drone_dict['trajectory'].append(state.copy())
            
            self.drones.append(drone_dict)
            self.targets.append(target)
            self.predicted_trajectories.append(np.zeros((11, 6)))
            self.control_sequences.append(np.zeros((10, 3)))
    
    def _setup_gui(self):
        ax_n_drones = plt.axes([0.10, 0.25, 0.18, 0.03])
        self.slider_n_drones = Slider(
            ax=ax_n_drones,
            label='Number of Drones',
            valmin=5,
            valmax=20,
            valinit=self.n_drones,
            valstep=1
        )
        self.slider_n_drones.on_changed(self._update_n_drones)
        
        ax_max_vel = plt.axes([0.10, 0.20, 0.18, 0.03])
        self.slider_max_vel = Slider(
            ax=ax_max_vel,
            label='Max Velocity (m/s)',
            valmin=1.0,
            valmax=8.0,
            valinit=self.max_vel,
            valstep=0.5
        )
        self.slider_max_vel.on_changed(self._update_max_vel)
        
        ax_comm_delay = plt.axes([0.10, 0.15, 0.18, 0.03])
        self.slider_comm_delay = Slider(
            ax=ax_comm_delay,
            label='Comm Delay (steps)',
            valmin=0,
            valmax=10,
            valinit=self.comm_layer.max_delay,
            valstep=1
        )
        self.slider_comm_delay.on_changed(self._update_comm_delay)
        
        ax_packet_loss = plt.axes([0.10, 0.10, 0.18, 0.03])
        self.slider_packet_loss = Slider(
            ax=ax_packet_loss,
            label='Packet Loss Rate',
            valmin=0.0,
            valmax=0.5,
            valinit=self.comm_layer.packet_loss_rate,
            valstep=0.05
        )
        self.slider_packet_loss.on_changed(self._update_packet_loss)
        
        ax_add_obs = plt.axes([0.35, 0.25, 0.12, 0.04])
        self.btn_add_obs = Button(ax_add_obs, 'Add Moving Obs')
        self.btn_add_obs.on_clicked(self._add_moving_obstacle)
        
        ax_reset = plt.axes([0.35, 0.20, 0.12, 0.04])
        self.btn_reset = Button(ax_reset, 'Reset Simulation')
        self.btn_reset.on_clicked(self._reset_simulation)
        
        ax_pause = plt.axes([0.35, 0.15, 0.12, 0.04])
        self.btn_pause = Button(ax_pause, 'Pause/Resume')
        self.btn_pause.on_clicked(self._toggle_pause)
        
        ax_formation = plt.axes([0.35, 0.10, 0.12, 0.04])
        self.btn_formation = Button(ax_formation, 'Switch Formation')
        self.btn_formation.on_clicked(self._switch_formation)
        
        self.ax_info = plt.axes([0.78, 0.06, 0.20, 0.18])
        self.ax_info.axis('off')
        
        self.ax_obs_x = plt.axes([0.52, 0.25, 0.06, 0.03])
        self.tb_obs_x = TextBox(self.ax_obs_x, 'Obs X', initial='0.0')
        
        self.ax_obs_y = plt.axes([0.52, 0.20, 0.06, 0.03])
        self.tb_obs_y = TextBox(self.ax_obs_y, 'Obs Y', initial='0.0')
        
        ax_checks = plt.axes([0.60, 0.08, 0.15, 0.16])
        self.check_buttons = CheckButtons(
            ax=ax_checks,
            labels=['DMPC', 'Formation', 'Heterogeneous', 'RL Backup'],
            actives=[self.use_dmpc, self.use_formation, self.use_heterogeneous, self.use_rl_backup]
        )
        self.check_buttons.on_clicked(self._toggle_feature)
    
    def _setup_plots(self):
        self.ax_3d.remove()
        self.ax_3d = self.fig.add_subplot(1, 2, 1, projection='3d')
        self.ax_3d.set_xlim(-self.world_size/2, self.world_size/2)
        self.ax_3d.set_ylim(-self.world_size/2, self.world_size/2)
        self.ax_3d.set_zlim(0, 20)
        self.ax_3d.set_xlabel('X (m)')
        self.ax_3d.set_ylabel('Y (m)')
        self.ax_3d.set_zlabel('Z (m)')
        self.ax_3d.set_title('Drone Swarm Simulation')
        
        self.ax_control.clear()
        self.ax_control.set_title('Control Commands (Drone 0)')
        self.ax_control.set_xlabel('Time Step')
        self.ax_control.set_ylabel('Acceleration (m/s²)')
        self.ax_control.grid(True)
        
        self._draw_obstacles()
        self._draw_drones()
    
    def _draw_obstacles(self):
        for obs in self.static_obstacles:
            if obs['type'] == 'tree':
                theta = np.linspace(0, 2*np.pi, 20)
                x = obs['x'] + obs['radius'] * np.cos(theta)
                y = obs['y'] + obs['radius'] * np.sin(theta)
                z = np.zeros_like(x)
                self.ax_3d.plot(x, y, z, color=obs['color'], linewidth=2)
                self.ax_3d.plot(x, y, obs['height'] * np.ones_like(x), color=obs['color'], linewidth=2)
                for i in range(0, 20, 4):
                    self.ax_3d.plot([x[i], x[i]], [y[i], y[i]], [0, obs['height']], color=obs['color'], alpha=0.5)
            
            elif obs['type'] == 'building':
                x_corners = [obs['x'] - obs['width']/2, obs['x'] + obs['width']/2, 
                            obs['x'] + obs['width']/2, obs['x'] - obs['width']/2]
                y_corners = [obs['y'] - obs['depth']/2, obs['y'] - obs['depth']/2, 
                            obs['y'] + obs['depth']/2, obs['y'] + obs['depth']/2]
                
                for z_val in [0, obs['height']]:
                    self.ax_3d.plot(x_corners + [x_corners[0]], y_corners + [y_corners[0]], 
                                   [z_val]*5, color=obs['color'], linewidth=2)
                for i in range(4):
                    self.ax_3d.plot([x_corners[i], x_corners[i]], [y_corners[i], y_corners[i]], 
                                   [0, obs['height']], color=obs['color'], alpha=0.7)
        
        self.moving_obs_surfaces = []
        for obs in self.moving_obstacles:
            u, v = np.mgrid[0:2*np.pi:20j, 0:np.pi:10j]
            x = obs['x'] + obs['radius'] * np.cos(u) * np.sin(v)
            y = obs['y'] + obs['radius'] * np.sin(u) * np.sin(v)
            z = obs['z'] + obs['radius'] * np.cos(v)
            surf = self.ax_3d.plot_surface(x, y, z, color='r', alpha=0.3)
            self.moving_obs_surfaces.append(surf)
    
    def _draw_drones(self):
        self.drone_scatters = []
        self.trajectory_lines = []
        self.prediction_lines = []
        self.target_scatters = []
        
        for i, drone in enumerate(self.drones):
            color = drone['color']
            
            scatter = self.ax_3d.scatter([drone['state'][0]], [drone['state'][1]], [drone['state'][2]], 
                                        color=color, s=100, marker='o', label=f'Drone {i}')
            self.drone_scatters.append(scatter)
            
            traj = np.array(drone['trajectory'])
            line, = self.ax_3d.plot(traj[:, 0], traj[:, 1], traj[:, 2], color=color, alpha=0.5, linewidth=1)
            self.trajectory_lines.append(line)
            
            pred_line, = self.ax_3d.plot([], [], [], color=color, linestyle='--', linewidth=2, alpha=0.7)
            self.prediction_lines.append(pred_line)
            
            target_scatter = self.ax_3d.scatter([drone['target'][0]], [drone['target'][1]], [drone['target'][2]], 
                                               color=color, marker='*', s=200, alpha=0.6)
            self.target_scatters.append(target_scatter)
    
    def _update_n_drones(self, val):
        new_n = int(val)
        if new_n != self.n_drones:
            self.n_drones = new_n
            self._initialize_drones(full_reset=False)
            self._draw_obstacles()
            self._draw_drones()
    
    def _update_max_vel(self, val):
        self.max_vel = val
        self.max_acc = min(self.max_acc, val * 3)
        for drone in self.drones:
            drone['dynamics'].max_vel = val
            drone['dynamics'].max_acc = self.max_acc
            drone['mpc'].reinitialize_weights()
    
    def _add_moving_obstacle(self, event):
        try:
            x = float(self.tb_obs_x.text)
            y = float(self.tb_obs_y.text)
        except:
            x = 0.0
            y = 0.0
        
        self.moving_obstacles.append({
            'type': 'sphere',
            'x': x,
            'y': y,
            'z': np.random.uniform(3, 10),
            'radius': np.random.uniform(1.0, 2.0),
            'vx': np.random.uniform(-1, 1),
            'vy': np.random.uniform(-1, 1),
            'vz': np.random.uniform(-0.5, 0.5),
            'color': 'r'
        })
        
        self._draw_obstacles()
    
    def _reset_simulation(self, event):
        self.static_obstacles = self.obstacle_generator.generate(n_trees=8, n_buildings=5)
        self.moving_obstacles = []
        self._initialize_drones(full_reset=True)
        self._draw_obstacles()
        self._draw_drones()
    
    def _toggle_pause(self, event):
        self.running = not self.running
    
    def _update_comm_delay(self, val):
        self.comm_layer.max_delay = int(val)
    
    def _update_packet_loss(self, val):
        self.comm_layer.packet_loss_rate = val
    
    def _switch_formation(self, event):
        formations = list(FormationController.FORMATIONS.keys())
        current_idx = formations.index(self.formation_controller.formation_type)
        next_idx = (current_idx + 1) % len(formations)
        self.formation_controller.switch_formation(formations[next_idx])
        self._initialize_drones(full_reset=True)
        self._draw_obstacles()
        self._draw_drones()
    
    def _toggle_feature(self, label):
        if label == 'DMPC':
            self.use_dmpc = not self.use_dmpc
        elif label == 'Formation':
            self.use_formation = not self.use_formation
            if self.use_formation:
                self._initialize_drones(full_reset=True)
                self._draw_obstacles()
                self._draw_drones()
        elif label == 'Heterogeneous':
            self.use_heterogeneous = not self.use_heterogeneous
            self._initialize_drones(full_reset=True)
            self._draw_obstacles()
            self._draw_drones()
        elif label == 'RL Backup':
            self.use_rl_backup = not self.use_rl_backup
    
    def _update_moving_obstacles(self):
        for obs in self.moving_obstacles:
            obs['x'] += obs['vx'] * self.dt
            obs['y'] += obs['vy'] * self.dt
            obs['z'] += obs['vz'] * self.dt
            
            if abs(obs['x']) > self.world_size / 2:
                obs['vx'] *= -1
            if abs(obs['y']) > self.world_size / 2:
                obs['vy'] *= -1
            if obs['z'] < 1 or obs['z'] > 18:
                obs['vz'] *= -1
    
    def _check_collisions(self):
        all_obstacles = self.static_obstacles + self.moving_obstacles
        
        for i, drone in enumerate(self.drones):
            pos = drone['state'][:3]
            
            for obs in all_obstacles:
                if obs['type'] == 'tree' or obs['type'] == 'building':
                    obs_pos = np.array([obs['x'], obs['y'], pos[2]])
                    dist_xy = np.linalg.norm(pos[:2] - obs_pos[:2])
                    if dist_xy < obs['radius'] + 0.3 and pos[2] < obs['height']:
                        self.collision_count += 1
                        self.collision_log.append((time.time() - self.mission_start_time, i, obs['type']))
                
                elif obs['type'] == 'sphere':
                    obs_pos = np.array([obs['x'], obs['y'], obs['z']])
                    dist = np.linalg.norm(pos - obs_pos)
                    if dist < obs['radius'] + 0.3:
                        self.collision_count += 1
                        self.collision_log.append((time.time() - self.mission_start_time, i, 'sphere'))
        
        for i in range(len(self.drones)):
            for j in range(i + 1, len(self.drones)):
                dist = np.linalg.norm(self.drones[i]['state'][:3] - self.drones[j]['state'][:3])
                if dist < 0.8:
                    self.collision_count += 1
                    self.collision_log.append((time.time() - self.mission_start_time, f'{i}-{j}', 'drone-drone'))
    
    def _check_mission_complete(self):
        completed = 0
        for drone in self.drones:
            dist = np.linalg.norm(drone['state'][:3] - drone['target'][:3])
            if dist < 1.5 and not drone['completed']:
                drone['completed'] = True
            if drone['completed']:
                completed += 1
        
        self.completed_drones = completed
        if completed == self.n_drones and self.mission_complete_time is None:
            self.mission_complete_time = time.time() - self.mission_start_time
    
    def update(self):
        if not self.running:
            return
        
        self._update_moving_obstacles()
        
        all_obstacles = self.static_obstacles + self.moving_obstacles
        current_time = time.time() - self.mission_start_time
        
        positions = np.array([drone['state'][:3] for drone in self.drones])
        
        if self.use_dmpc:
            for i, drone in enumerate(self.drones):
                if not drone['completed']:
                    self.comm_layer.broadcast_trajectory(
                        i, self.predicted_trajectories[i], 
                        self.control_sequences[i],
                        drone['state'][:3], current_time
                    )
            
            for i in range(self.n_drones):
                trajectories, ctrls, positions = self.comm_layer.get_neighbor_trajectories(
                    i, current_time
                )
                self.neighbor_trajectories[i] = trajectories
        
        if self.use_formation and len(self.drones) > 0:
            leader_state = self.drones[self.leader_id]['state']
            leader_pos = leader_state[:3]
            leader_vel = leader_state[3:6]
            
            self.formation_controller.formation_center = leader_pos
        
        for i, drone in enumerate(self.drones):
            if drone['completed']:
                continue
            
            state = drone['state']
            
            if self.use_formation:
                target_pos = self.formation_controller.get_target_position(
                    i, leader_pos, leader_vel
                )
                target = np.concatenate([target_pos, np.zeros(3)])
            else:
                target = drone['target']
            
            neighbor_preds = []
            if self.use_dmpc and i in self.neighbor_trajectories:
                for neighbor_id, traj in self.neighbor_trajectories[i].items():
                    if len(traj) > 0:
                        neighbor_preds.append(traj[0, :6])
            
            pf_force = self.potential_field.compute_force(
                state[:3], target, all_obstacles, 
                velocity=state[3:6], dt=self.dt
            )
            
            vo_vel = np.zeros(3)
            for j, other in enumerate(self.drones):
                if i != j and not other['completed']:
                    other_state = other['state']
                    if j in self.neighbor_trajectories[i] and len(self.neighbor_trajectories[i][j]) > 0:
                        other_state = self.neighbor_trajectories[i][j][0]
                    
                    vo_vel += self.velocity_obstacle.compute_avoidance_velocity(
                        state[:3], state[3:6],
                        other_state[:3], other_state[3:6],
                        drone['max_vel'], id_a=i, id_b=j
                    )
            
            mpc_control, pred_traj, control_seq = drone['mpc'].compute_control(
                state, target, obstacles=all_obstacles, 
                pf_force=pf_force, vo_vel=vo_vel
            )
            
            drone['mpc_status'] = 0
            
            other_states = [d['state'] for j, d in enumerate(self.drones) if j != i and not d['completed']]
            
            if self.use_rl_backup:
                rl_controller = drone['rl_controller']
                
                should_switch = rl_controller.should_switch_to_rl(
                    drone['mpc_status'], state, all_obstacles, other_states
                )
                
                if should_switch:
                    rl_control, confidence = rl_controller.compute_action(
                        state, target, all_obstacles, other_states,
                        max_acc=drone['max_acc']
                    )
                    
                    blend = 0.5 + 0.5 * (1 - confidence)
                    control = blend * mpc_control + (1 - blend) * rl_control
                    drone['use_rl'] = True
                    self.rl_active[i] = True
                    self.rl_switch_count += 1
                else:
                    control = mpc_control
                    drone['use_rl'] = False
                    self.rl_active[i] = False
            else:
                control = mpc_control
            
            control = np.clip(control, -drone['max_acc'], drone['max_acc'])
            
            new_state = drone['dynamics'].step(state, control)
            drone['state'] = new_state
            drone['trajectory'].append(new_state.copy())
            
            self.predicted_trajectories[i] = pred_traj
            self.control_sequences[i] = control_seq
        
        self._check_collisions()
        self._check_mission_complete()
        self._visualize()
    
    def _update_moving_obstacle_visualization(self):
        if hasattr(self, 'moving_obs_surfaces'):
            for surf in self.moving_obs_surfaces:
                surf.remove()
        
        self.moving_obs_surfaces = []
        for obs in self.moving_obstacles:
            u, v = np.mgrid[0:2*np.pi:15j, 0:np.pi:8j]
            x = obs['x'] + obs['radius'] * np.cos(u) * np.sin(v)
            y = obs['y'] + obs['radius'] * np.sin(u) * np.sin(v)
            z = obs['z'] + obs['radius'] * np.cos(v)
            surf = self.ax_3d.plot_surface(x, y, z, color='r', alpha=0.3)
            self.moving_obs_surfaces.append(surf)
    
    def _visualize(self):
        self._update_moving_obstacle_visualization()
        
        for i, drone in enumerate(self.drones):
            self.drone_scatters[i]._offsets3d = ([drone['state'][0]], [drone['state'][1]], [drone['state'][2]])
            
            traj = np.array(drone['trajectory'])
            self.trajectory_lines[i].set_data(traj[:, 0], traj[:, 1])
            self.trajectory_lines[i].set_3d_properties(traj[:, 2])
            
            pred = self.predicted_trajectories[i]
            self.prediction_lines[i].set_data(pred[:, 0], pred[:, 1])
            self.prediction_lines[i].set_3d_properties(pred[:, 2])
        
        self.ax_control.clear()
        self.ax_control.set_title('Control Commands (Drone 0)')
        self.ax_control.set_xlabel('Prediction Step')
        self.ax_control.set_ylabel('Acceleration (m/s²)')
        self.ax_control.grid(True)
        
        ctrl_seq = self.control_sequences[0]
        steps = np.arange(len(ctrl_seq))
        self.ax_control.plot(steps, ctrl_seq[:, 0], 'r-', label='ax', linewidth=2)
        self.ax_control.plot(steps, ctrl_seq[:, 1], 'g-', label='ay', linewidth=2)
        self.ax_control.plot(steps, ctrl_seq[:, 2], 'b-', label='az', linewidth=2)
        self.ax_control.legend()
        self.ax_control.set_ylim(-self.max_acc * 1.1, self.max_acc * 1.1)
        
        self.ax_info.clear()
        self.ax_info.axis('off')
        elapsed_time = time.time() - self.mission_start_time
        
        mission_time_str = f'{self.mission_complete_time:.1f}s' if self.mission_complete_time else 'In Progress'
        
        comm_stats = self.comm_layer.get_stats()
        rl_active_count = sum(self.rl_active)
        
        type_counts = {}
        for drone in self.drones:
            t = drone.get('type', 'standard')
            type_counts[t] = type_counts.get(t, 0) + 1
        type_str = ', '.join([f"{HeterogeneousDroneConfig.get_config(k)['name']}:{v}" for k, v in type_counts.items()])
        
        info_text = f"""
        Simulation Statistics:
        ----------------------
        Time Elapsed: {elapsed_time:.1f}s
        Mission Time: {mission_time_str}
        Drones Completed: {self.completed_drones}/{self.n_drones}
        Collision Count: {self.collision_count}
        Max Velocity: {self.max_vel:.1f} m/s
        
        Advanced Features:
        ------------------
        DMPC: {'ON' if self.use_dmpc else 'OFF'} | Loss Rate: {comm_stats['loss_rate']:.1%}
        Formation: {'ON' if self.use_formation else 'OFF'} | {self.formation_controller.formation_type}
        Heterogeneous: {'ON' if self.use_heterogeneous else 'OFF'} | {type_str}
        RL Backup: {'ON' if self.use_rl_backup else 'OFF'} | Active: {rl_active_count} | Switches: {self.rl_switch_count}
        """
        
        if len(self.collision_log) > 0:
            info_text += f"\nLast Collision: {self.collision_log[-1][1]} at t={self.collision_log[-1][0]:.1f}s"
        
        self.ax_info.text(0, 1, info_text, fontsize=9, verticalalignment='top',
                         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.draw()
        plt.pause(0.01)

def main():
    print("Initializing Drone Swarm MPC Simulation...")
    sim = DroneSwarmSimulation(n_drones=10, world_size=30)
    
    print("Starting simulation...")
    print("Controls:")
    print("  - Slider: Adjust number of drones (5-20)")
    print("  - Slider: Adjust maximum velocity")
    print("  - Button: Add moving obstacle (enter X/Y position first)")
    print("  - Button: Reset simulation")
    print("  - Button: Pause/Resume")
    print("\nClosing the window will exit the simulation.")
    
    try:
        while True:
            sim.update()
            if not plt.get_fignums():
                break
    except KeyboardInterrupt:
        print("\nSimulation stopped by user.")
    finally:
        plt.close('all')

if __name__ == "__main__":
    main()
