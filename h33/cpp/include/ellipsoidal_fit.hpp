#ifndef HALO_ANALYSIS_ELLIPSOIDAL_FIT_HPP
#define HALO_ANALYSIS_ELLIPSOIDAL_FIT_HPP

#include "common.hpp"
#include <vector>

namespace halo_analysis {

class EllipsoidalFitter {
public:
    EllipsoidalFitter(FloatType tolerance = 1e-6, int max_iterations = 100);
    ~EllipsoidalFitter() = default;

    bool fit(const Halo& halo, const Snapshot& snapshot,
             EllipsoidalShape& result,
             int iterations = 3);

    void compute_inertia_tensor(const Halo& halo, const Snapshot& snapshot,
                                Matrix3x3& tensor, FloatType r_max = 0.0);

    bool diagonalize_3x3(const Matrix3x3& tensor,
                         std::array<FloatType, 3>& eigenvalues,
                         Matrix3x3& eigenvectors);

    void compute_ellipsoidal_radii(const std::array<FloatType, 3>& eigenvalues,
                                   FloatType& a, FloatType& b, FloatType& c);

    void compute_euler_angles(const Matrix3x3& rotation_matrix,
                              Position& angles);

    void set_tolerance(FloatType t) { tolerance_ = t; }
    void set_max_iterations(int n) { max_iterations_ = n; }

private:
    FloatType tolerance_;
    int max_iterations_;

    void jacobi_rotation(Matrix3x3& a, int i, int j, FloatType& s, FloatType& tau);
};

}

#endif
