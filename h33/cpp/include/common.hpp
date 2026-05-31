#ifndef HALO_ANALYSIS_COMMON_HPP
#define HALO_ANALYSIS_COMMON_HPP

#include <vector>
#include <array>
#include <cstdint>
#include <string>
#include <cmath>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace halo_analysis {

constexpr FloatType G = 4.30091e-9;
constexpr FloatType RHO_CRIT = 2.77536627e11;

using IDType = uint64_t;
using FloatType = double;
using Position = std::array<FloatType, 3>;
using Velocity = std::array<FloatType, 3>;
using Matrix3x3 = std::array<std::array<FloatType, 3>, 3>;

struct EllipsoidalShape {
    FloatType axis_a;
    FloatType axis_b;
    FloatType axis_c;
    FloatType axis_ratio_b_a;
    FloatType axis_ratio_c_a;
    FloatType ellipticity;
    FloatType prolateness;
    FloatType triaxiality;
    Matrix3x3 orientation_matrix;
    Position euler_angles;
    bool converged;
};

struct Particle {
    IDType id;
    Position pos;
    Velocity vel;
    FloatType mass;
};

struct ParticleData {
    std::vector<IDType> ids;
    std::vector<Position> positions;
    std::vector<Velocity> velocities;
    std::vector<FloatType> masses;
    size_t size() const { return ids.size(); }
    void reserve(size_t n) {
        ids.reserve(n);
        positions.reserve(n);
        velocities.reserve(n);
        masses.reserve(n);
    }
    void clear() {
        ids.clear();
        positions.clear();
        velocities.clear();
        masses.clear();
    }
};

struct Halo {
    IDType halo_id;
    int snapshot_index;
    FloatType redshift;
    std::vector<IDType> particle_ids;
    FloatType mass;
    Position center_of_mass;
    Velocity mean_velocity;
    Velocity velocity_dispersion;
    FloatType spin_parameter;
    FloatType formation_redshift;
    IDType descendant_id;
    std::vector<IDType> progenitor_ids;
    std::vector<IDType> subhalo_ids;
    EllipsoidalShape shape;
    std::vector<IDType> substructure_ids;
    IDType parent_halo_id;
    bool is_substructure;
};

struct Snapshot {
    int index;
    FloatType redshift;
    FloatType scale_factor;
    FloatType box_size;
    ParticleData particles;
    std::vector<Halo> halos;
};

inline FloatType compute_mean_interparticle_spacing(FloatType box_size, size_t num_particles) {
    return box_size / std::cbrt(static_cast<FloatType>(num_particles));
}

inline FloatType periodic_distance(const Position& a, const Position& b, FloatType box_size) {
    FloatType dx = a[0] - b[0];
    FloatType dy = a[1] - b[1];
    FloatType dz = a[2] - b[2];
    dx -= box_size * std::round(dx / box_size);
    dy -= box_size * std::round(dy / box_size);
    dz -= box_size * std::round(dz / box_size);
    return std::sqrt(dx*dx + dy*dy + dz*dz);
}

}

#endif
