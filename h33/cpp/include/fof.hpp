#ifndef HALO_ANALYSIS_FOF_HPP
#define HALO_ANALYSIS_FOF_HPP

#include "common.hpp"
#include "ellipsoidal_fit.hpp"
#include <vector>
#include <unordered_map>
#include <unordered_set>
#include <functional>

namespace halo_analysis {

class FoFFinder {
public:
    FoFFinder(FloatType link_length_ratio = 0.2, size_t min_particles = 20);
    ~FoFFinder() = default;

    void find_halos(Snapshot& snapshot);
    void compute_halo_properties(Halo& halo, const Snapshot& snapshot);
    void compute_ellipsoidal_shape(Halo& halo, const Snapshot& snapshot);

    void set_link_length_ratio(FloatType r) { link_length_ratio_ = r; }
    void set_min_particles(size_t n) { min_particles_ = n; }
    FloatType get_link_length_ratio() const { return link_length_ratio_; }
    size_t get_min_particles() const { return min_particles_; }

    void set_compute_shape(bool b) { compute_shape_ = b; }
    bool get_compute_shape() const { return compute_shape_; }

private:
    FloatType link_length_ratio_;
    size_t min_particles_;
    bool compute_shape_ = true;
    EllipsoidalFitter shape_fitter_;

    using GridKey = std::tuple<int, int, int>;
    struct GridKeyHash {
        size_t operator()(const GridKey& k) const {
            return std::get<0>(k) ^ (std::get<1>(k) << 10) ^ (std::get<2>(k) << 20);
        }
    };

    GridKey get_grid_key(const Position& pos, FloatType cell_size, FloatType box_size) const;
    void get_neighbor_keys(const GridKey& key, int n_cells, std::vector<GridKey>& neighbors) const;
};

}

#endif
