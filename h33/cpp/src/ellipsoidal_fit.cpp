#include "ellipsoidal_fit.hpp"
#include <iostream>
#include <algorithm>
#include <cmath>
#include <unordered_map>

namespace halo_analysis {

EllipsoidalFitter::EllipsoidalFitter(FloatType tolerance, int max_iterations)
    : tolerance_(tolerance), max_iterations_(max_iterations) {}

void EllipsoidalFitter::compute_inertia_tensor(const Halo& halo, const Snapshot& snapshot,
                                               Matrix3x3& tensor, FloatType r_max) {
    std::unordered_map<IDType, size_t> id_to_idx;
    for (size_t i = 0; i < snapshot.particles.size(); ++i) {
        id_to_idx[snapshot.particles.ids[i]] = i;
    }

    for (int i = 0; i < 3; ++i) {
        for (int j = 0; j < 3; ++j) {
            tensor[i][j] = 0.0;
        }
    }

    FloatType total_mass = 0.0;
    const Position& com = halo.center_of_mass;

    for (IDType pid : halo.particle_ids) {
        auto it = id_to_idx.find(pid);
        if (it == id_to_idx.end()) continue;
        size_t idx = it->second;
        FloatType m = snapshot.particles.masses[idx];
        const Position& p = snapshot.particles.positions[idx];

        FloatType dx = p[0] - com[0];
        FloatType dy = p[1] - com[1];
        FloatType dz = p[2] - com[2];
        dx -= snapshot.box_size * std::round(dx / snapshot.box_size);
        dy -= snapshot.box_size * std::round(dy / snapshot.box_size);
        dz -= snapshot.box_size * std::round(dz / snapshot.box_size);

        if (r_max > 0) {
            FloatType r = std::sqrt(dx*dx + dy*dy + dz*dz);
            if (r > r_max) continue;
        }

        total_mass += m;

        tensor[0][0] += m * dx * dx;
        tensor[1][1] += m * dy * dy;
        tensor[2][2] += m * dz * dz;
        tensor[0][1] += m * dx * dy;
        tensor[0][2] += m * dx * dz;
        tensor[1][2] += m * dy * dz;
    }

    tensor[1][0] = tensor[0][1];
    tensor[2][0] = tensor[0][2];
    tensor[2][1] = tensor[1][2];

    if (total_mass > 0) {
        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) {
                tensor[i][j] /= total_mass;
            }
        }
    }
}

void EllipsoidalFitter::jacobi_rotation(Matrix3x3& a, int i, int j, FloatType& s, FloatType& tau) {
    FloatType theta = (a[j][j] - a[i][i]) / (2.0 * a[i][j]);
    FloatType t;
    if (theta >= 0) {
        t = 1.0 / (theta + std::sqrt(1.0 + theta * theta));
    } else {
        t = -1.0 / (-theta + std::sqrt(1.0 + theta * theta));
    }
    FloatType c = 1.0 / std::sqrt(1.0 + t * t);
    s = t * c;
    tau = s / (1.0 + c);

    FloatType a_ii = a[i][i];
    FloatType a_jj = a[j][j];
    FloatType a_ij = a[i][j];

    a[i][i] = a_ii - t * a_ij;
    a[j][j] = a_jj + t * a_ij;
    a[i][j] = 0.0;

    for (int k = 0; k < 3; ++k) {
        if (k != i && k != j) {
            FloatType a_ki = a[k][i];
            FloatType a_kj = a[k][j];
            a[k][i] = a_ki - s * (a_kj + tau * a_ki);
            a[i][k] = a[k][i];
            a[k][j] = a_kj + s * (a_ki - tau * a_kj);
            a[j][k] = a[k][j];
        }
    }
}

bool EllipsoidalFitter::diagonalize_3x3(const Matrix3x3& tensor,
                                        std::array<FloatType, 3>& eigenvalues,
                                        Matrix3x3& eigenvectors) {
    Matrix3x3 a = tensor;
    for (int i = 0; i < 3; ++i) {
        for (int j = 0; j < 3; ++j) {
            eigenvectors[i][j] = (i == j) ? 1.0 : 0.0;
        }
    }

    for (int iter = 0; iter < max_iterations_; ++iter) {
        FloatType sum = 0.0;
        for (int p = 0; p < 2; ++p) {
            for (int q = p + 1; q < 3; ++q) {
                sum += std::abs(a[p][q]);
            }
        }

        if (sum < tolerance_) {
            for (int i = 0; i < 3; ++i) {
                eigenvalues[i] = a[i][i];
            }
            return true;
        }

        int p = 0, q = 1;
        FloatType max_abs = 0.0;
        for (int i = 0; i < 2; ++i) {
            for (int j = i + 1; j < 3; ++j) {
                if (std::abs(a[i][j]) > max_abs) {
                    max_abs = std::abs(a[i][j]);
                    p = i;
                    q = j;
                }
            }
        }

        FloatType s, tau;
        jacobi_rotation(a, p, q, s, tau);

        for (int k = 0; k < 3; ++k) {
            FloatType v_kp = eigenvectors[k][p];
            FloatType v_kq = eigenvectors[k][q];
            eigenvectors[k][p] = v_kp - s * (v_kq + tau * v_kp);
            eigenvectors[k][q] = v_kq + s * (v_kp - tau * v_kq);
        }
    }

    for (int i = 0; i < 3; ++i) {
        eigenvalues[i] = a[i][i];
    }
    return false;
}

void EllipsoidalFitter::compute_ellipsoidal_radii(const std::array<FloatType, 3>& eigenvalues,
                                                   FloatType& a, FloatType& b, FloatType& c) {
    std::array<FloatType, 3> vals = eigenvalues;
    std::sort(vals.begin(), vals.end(), std::greater<FloatType>());

    for (int i = 0; i < 3; ++i) {
        if (vals[i] < 0) vals[i] = 0;
    }

    a = std::sqrt(5.0 * vals[0]);
    b = std::sqrt(5.0 * vals[1]);
    c = std::sqrt(5.0 * vals[2]);
}

void EllipsoidalFitter::compute_euler_angles(const Matrix3x3& rotation_matrix,
                                             Position& angles) {
    const Matrix3x3& R = rotation_matrix;

    FloatType phi, theta, psi;

    if (std::abs(R[2][2]) < 1.0) {
        theta = std::acos(std::max(-1.0, std::min(1.0, R[2][2])));
        phi = std::atan2(R[1][2], R[0][2]);
        psi = std::atan2(R[2][1], -R[2][0]);
    } else {
        if (R[2][2] > 0) {
            theta = 0.0;
            phi = std::atan2(-R[1][0], R[0][0]);
            psi = 0.0;
        } else {
            theta = M_PI;
            phi = std::atan2(R[1][0], -R[0][0]);
            psi = 0.0;
        }
    }

    angles[0] = phi;
    angles[1] = theta;
    angles[2] = psi;
}

bool EllipsoidalFitter::fit(const Halo& halo, const Snapshot& snapshot,
                            EllipsoidalShape& result,
                            int iterations) {
    result.converged = false;

    if (halo.particle_ids.size() < 10) {
        result.axis_a = result.axis_b = result.axis_c = 0.0;
        result.axis_ratio_b_a = result.axis_ratio_c_a = 0.0;
        result.ellipticity = result.prolateness = result.triaxiality = 0.0;
        for (int i = 0; i < 3; ++i) {
            result.euler_angles[i] = 0.0;
            for (int j = 0; j < 3; ++j) {
                result.orientation_matrix[i][j] = (i == j) ? 1.0 : 0.0;
            }
        }
        return false;
    }

    Matrix3x3 tensor;
    std::array<FloatType, 3> eigenvalues;
    Matrix3x3 eigenvectors;

    compute_inertia_tensor(halo, snapshot, tensor);

    if (!diagonalize_3x3(tensor, eigenvalues, eigenvectors)) {
        result.converged = false;
    } else {
        result.converged = true;
    }

    std::array<FloatType, 3> vals = eigenvalues;
    std::array<int, 3> idx = {0, 1, 2};
    std::sort(idx.begin(), idx.end(),
              [&](int i, int j) { return vals[i] > vals[j]; });

    Matrix3x3 sorted_eigenvectors;
    std::array<FloatType, 3> sorted_eigenvalues;
    for (int i = 0; i < 3; ++i) {
        sorted_eigenvalues[i] = vals[idx[i]];
        for (int j = 0; j < 3; ++j) {
            sorted_eigenvectors[j][i] = eigenvectors[j][idx[i]];
        }
    }

    for (int iter = 1; iter < iterations; ++iter) {
        FloatType a, b, c;
        compute_ellipsoidal_radii(sorted_eigenvalues, a, b, c);
        FloatType r_max = std::max({a, b, c});

        compute_inertia_tensor(halo, snapshot, tensor, r_max);

        if (!diagonalize_3x3(tensor, eigenvalues, eigenvectors)) {
            break;
        }

        std::array<FloatType, 3> new_vals = eigenvalues;
        std::array<int, 3> new_idx = {0, 1, 2};
        std::sort(new_idx.begin(), new_idx.end(),
                  [&](int i, int j) { return new_vals[i] > new_vals[j]; });

        bool converged = true;
        for (int i = 0; i < 3; ++i) {
            if (std::abs(new_vals[new_idx[i]] - sorted_eigenvalues[i]) > tolerance_ * sorted_eigenvalues[i]) {
                converged = false;
                break;
            }
        }

        for (int i = 0; i < 3; ++i) {
            sorted_eigenvalues[i] = new_vals[new_idx[i]];
            for (int j = 0; j < 3; ++j) {
                sorted_eigenvectors[j][i] = eigenvectors[j][new_idx[i]];
            }
        }

        if (converged) {
            result.converged = true;
            break;
        }
    }

    compute_ellipsoidal_radii(sorted_eigenvalues, result.axis_a, result.axis_b, result.axis_c);

    if (result.axis_a > 0) {
        result.axis_ratio_b_a = result.axis_b / result.axis_a;
        result.axis_ratio_c_a = result.axis_c / result.axis_a;
        result.ellipticity = 1.0 - result.axis_c / result.axis_a;
        result.prolateness = (result.axis_b - result.axis_c) / (result.axis_b + result.axis_c);
        if (result.axis_a > result.axis_c) {
            result.triaxiality = (result.axis_a * result.axis_a - result.axis_b * result.axis_b) /
                                  (result.axis_a * result.axis_a - result.axis_c * result.axis_c);
        } else {
            result.triaxiality = 0.0;
        }
    } else {
        result.axis_ratio_b_a = result.axis_ratio_c_a = 0.0;
        result.ellipticity = result.prolateness = result.triaxiality = 0.0;
    }

    result.orientation_matrix = sorted_eigenvectors;
    compute_euler_angles(sorted_eigenvectors, result.euler_angles);

    return result.converged;
}

}
