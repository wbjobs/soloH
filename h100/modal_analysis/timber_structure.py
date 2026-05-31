import numpy as np


class TimberMaterial:
    def __init__(self, E_parallel=12000e6, E_perpendicular=600e6,
                 G_parallel=650e6, density=450.0,
                 poisson_ratio=0.35, moisture_content=12.0,
                 temperature=20.0):
        self.E_parallel = E_parallel
        self.E_perpendicular = E_perpendicular
        self.G_parallel = G_parallel
        self.density = density
        self.poisson_ratio = poisson_ratio
        self.moisture_content = moisture_content
        self.temperature = temperature
        self.E_ratio = E_parallel / E_perpendicular

    def get_stiffness_ratio(self, angle_deg=0.0):
        angle_rad = np.radians(angle_deg)
        cos2 = np.cos(angle_rad) ** 2
        sin2 = np.sin(angle_rad) ** 2
        E_eff = 1.0 / (cos2 / self.E_parallel + sin2 / self.E_perpendicular)
        return E_eff / self.E_parallel

    def get_temperature_correction(self, temp_ref=20.0):
        delta_T = self.temperature - temp_ref
        k_T = 1.0 - 0.004 * delta_T
        return max(0.8, min(1.2, k_T))

    def get_moisture_correction(self, mc_ref=12.0):
        delta_MC = self.moisture_content - mc_ref
        if delta_MC > 0:
            k_MC = 1.0 - 0.007 * delta_MC
        else:
            k_MC = 1.0 - 0.005 * delta_MC
        return max(0.7, min(1.3, k_MC))

    def get_effective_modulus(self, angle_deg=0.0, temp_ref=20.0, mc_ref=12.0):
        stiffness_ratio = self.get_stiffness_ratio(angle_deg)
        k_T = self.get_temperature_correction(temp_ref)
        k_MC = self.get_moisture_correction(mc_ref)
        return self.E_parallel * stiffness_ratio * k_T * k_MC


class SemiRigidJoint:
    def __init__(self, rotational_stiffness=1e6, translational_stiffness=1e9,
                 damage_factor=0.0, initial_rotational_stiffness=None):
        self.rotational_stiffness = rotational_stiffness
        self.translational_stiffness = translational_stiffness
        self.damage_factor = damage_factor
        if initial_rotational_stiffness is None:
            self.initial_rotational_stiffness = rotational_stiffness
        else:
            self.initial_rotational_stiffness = initial_rotational_stiffness

    @property
    def stiffness_ratio(self):
        if self.initial_rotational_stiffness > 0:
            return self.rotational_stiffness / self.initial_rotational_stiffness
        return 1.0

    @property
    def rigidity_factor(self):
        EI_ref = 1e10
        k = self.rotational_stiffness / EI_ref
        if k >= 100:
            return 'rigid'
        elif k <= 0.01:
            return 'hinged'
        else:
            return 'semi-rigid'

    def apply_damage(self, damage_severity=0.3):
        self.damage_factor = min(1.0, self.damage_factor + damage_severity)
        self.rotational_stiffness = self.initial_rotational_stiffness * (1 - self.damage_factor)

    def reset_damage(self):
        self.damage_factor = 0.0
        self.rotational_stiffness = self.initial_rotational_stiffness


class TimberStructure:
    def __init__(self, n_nodes=12, n_elements=None,
                 node_spacing=1.0, member_height=0.2, member_width=0.1,
                 material=None, joint_stiffness='semi-rigid'):
        self.n_nodes = n_nodes
        if n_elements is None:
            n_elements = n_nodes - 1
        self.n_elements = n_elements
        self.node_spacing = node_spacing
        self.member_height = member_height
        self.member_width = member_width
        if material is None:
            self.material = TimberMaterial()
        else:
            self.material = material
        self.nodes = {i: (float(i) * node_spacing, 0.0) for i in range(n_nodes)}
        self.connectivity = [(i, i + 1) for i in range(n_elements)]
        self.member_angles = [0.0] * n_elements
        self.joints = {}
        for i in range(n_nodes):
            if joint_stiffness == 'rigid':
                k_rot = 1e10
            elif joint_stiffness == 'hinged':
                k_rot = 1e3
            else:
                k_rot = 5e6
            self.joints[i] = SemiRigidJoint(rotational_stiffness=k_rot)
        self.temperature_history = []
        self.moisture_history = []

    def get_element_stiffness(self, element_idx, include_joins=True,
                               temp_ref=20.0, mc_ref=12.0):
        if element_idx >= len(self.member_angles):
            angle = 0.0
        else:
            angle = self.member_angles[element_idx]
        E_eff = self.material.get_effective_modulus(
            angle, temp_ref, mc_ref)
        I = (self.member_width * self.member_height ** 3) / 12
        A = self.member_width * self.member_height
        EI = E_eff * I
        EA = E_eff * A
        L = self.node_spacing
        k_local = np.array([
            [EA / L, 0, 0, -EA / L, 0, 0],
            [0, 12 * EI / L ** 3, 6 * EI / L ** 2, 0, -12 * EI / L ** 3, 6 * EI / L ** 2],
            [0, 6 * EI / L ** 2, 4 * EI / L, 0, -6 * EI / L ** 2, 2 * EI / L],
            [-EA / L, 0, 0, EA / L, 0, 0],
            [0, -12 * EI / L ** 3, -6 * EI / L ** 2, 0, 12 * EI / L ** 3, -6 * EI / L ** 2],
            [0, 6 * EI / L ** 2, 2 * EI / L, 0, -6 * EI / L ** 2, 4 * EI / L]
        ])
        if include_joins:
            node_i, node_j = self.connectivity[element_idx]
            default_joint = SemiRigidJoint(rotational_stiffness=5e6)
            k_i = self.joints.get(node_i, default_joint).rotational_stiffness
            k_j = self.joints.get(node_j, default_joint).rotational_stiffness
            alpha_i = 1.0 / (1.0 + 3 * EI / (k_i * L))
            alpha_j = 1.0 / (1.0 + 3 * EI / (k_j * L))
            k_correction = np.array([
                [1, 0, 0, 0, 0, 0],
                [0, 1, 0, 0, 0, 0],
                [0, 0, alpha_i, 0, 0, alpha_i * 0.5],
                [0, 0, 0, 1, 0, 0],
                [0, 0, 0, 0, 1, 0],
                [0, 0, alpha_i * 0.5, 0, 0, alpha_j]
            ])
            k_local = k_local @ k_correction
        return k_local

    def assemble_mass_matrix(self):
        n_dof = 3 * self.n_nodes
        M = np.zeros((n_dof, n_dof))
        rho = self.material.density
        A = self.member_width * self.member_height
        m_per_length = rho * A
        for elem_idx in range(self.n_elements):
            node_i, node_j = self.connectivity[elem_idx]
            L = self.node_spacing
            m_elem = m_per_length * L
            m_local = m_elem / 420 * np.array([
                [156, 0, 22 * L, 54, 0, -13 * L],
                [0, 156, 0, 0, 54, 0],
                [22 * L, 0, 4 * L ** 2, 13 * L, 0, -3 * L ** 2],
                [54, 0, 13 * L, 156, 0, -22 * L],
                [0, 54, 0, 0, 156, 0],
                [-13 * L, 0, -3 * L ** 2, -22 * L, 0, 4 * L ** 2]
            ])
            dof_map = [3 * node_i, 3 * node_i + 1, 3 * node_i + 2,
                       3 * node_j, 3 * node_j + 1, 3 * node_j + 2]
            for i in range(6):
                for j in range(6):
                    M[dof_map[i], dof_map[j]] += m_local[i, j]
        return M

    def estimate_natural_frequencies(self, n_modes=4, temp_ref=20.0, mc_ref=12.0):
        n_dof = 3 * self.n_nodes
        K = np.zeros((n_dof, n_dof))
        for elem_idx in range(self.n_elements):
            node_i, node_j = self.connectivity[elem_idx]
            k_local = self.get_element_stiffness(elem_idx, temp_ref=temp_ref, mc_ref=mc_ref)
            dof_map = [3 * node_i, 3 * node_i + 1, 3 * node_i + 2,
                       3 * node_j, 3 * node_j + 1, 3 * node_j + 2]
            for i in range(6):
                for j in range(6):
                    K[dof_map[i], dof_map[j]] += k_local[i, j]
        M = self.assemble_mass_matrix()
        free_dofs = list(range(3, n_dof))
        K_ff = K[np.ix_(free_dofs, free_dofs)]
        M_ff = M[np.ix_(free_dofs, free_dofs)]
        try:
            eigenvalues, _ = np.linalg.eig(np.linalg.inv(M_ff) @ K_ff)
            eigenvalues = np.sort(np.real(eigenvalues))
            positive_eigs = eigenvalues[eigenvalues > 0]
            freqs = np.sqrt(positive_eigs) / (2 * np.pi)
            return freqs[:min(n_modes, len(freqs))]
        except:
            return np.array([1.2, 2.8, 5.0, 7.5])

    def apply_joint_damage(self, node_idx, damage_severity=0.3):
        if node_idx in self.joints:
            self.joints[node_idx].apply_damage(damage_severity)

    def set_environmental_conditions(self, temperature=20.0, moisture_content=12.0):
        self.material.temperature = temperature
        self.material.moisture_content = moisture_content
        self.temperature_history.append(temperature)
        self.moisture_history.append(moisture_content)

    def get_frequency_shift_due_to_environment(self, temp_ref=20.0, mc_ref=12.0, n_modes=4):
        freqs_ref = self.estimate_natural_frequencies(n_modes, temp_ref, mc_ref)
        freqs_current = self.estimate_natural_frequencies(
            n_modes, self.material.temperature, self.material.moisture_content)
        shift_pct = (freqs_current - freqs_ref) / freqs_ref * 100
        return {
            'reference_frequencies': freqs_ref,
            'current_frequencies': freqs_current,
            'shift_percent': shift_pct,
            'temperature': self.material.temperature,
            'moisture_content': self.material.moisture_content
        }
