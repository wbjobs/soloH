#ifndef HALO_ANALYSIS_SUBSTRUCTURE_HPP
#define HALO_ANALYSIS_SUBSTRUCTURE_HPP

#include "common.hpp"
#include <vector>
#include <unordered_map>

namespace halo_analysis {

class SubstructureFinder {
public:
    SubstructureFinder(FloatType mass_ratio_threshold = 0.1,
                       FloatType radius_threshold = 2.0,
                       size_t min_particles = 10);
    ~SubstructureFinder() = default;

    void find_substructures(Snapshot& snapshot);
    void identify_subhalos_within_halo(Halo& host, const std::vector<Halo>& all_halos,
                                        const Snapshot& snapshot);
    void decompose_halo_bound(Halo& halo, const Snapshot& snapshot,
                               int n_iterations = 3);
    void track_substructures(std::vector<Snapshot>& snapshots);

    void set_mass_ratio_threshold(FloatType t) { mass_ratio_threshold_ = t; }
    void set_radius_threshold(FloatType t) { radius_threshold_ = t; }
    void set_min_particles(size_t n) { min_particles_ = n; }

private:
    FloatType mass_ratio_threshold_;
    FloatType radius_threshold_;
    size_t min_particles_;

    FloatType compute_halo_radius(const Halo& halo) const;
    std::vector<IDType> find_bound_particles(const Halo& halo, const Snapshot& snapshot,
                                             int n_iterations);
};

}

#endif
