#include "fof.hpp"
#include <iostream>
#include <algorithm>
#include <tuple>
#include <numeric>

namespace halo_analysis {

class UnionFind {
public:
    UnionFind(size_t n) : parent(n), rank(n, 0) {
        std::iota(parent.begin(), parent.end(), 0);
    }
    size_t find(size_t x) {
        while (parent[x] != x) {
            parent[x] = parent[parent[x]];
            x = parent[x];
        }
        return x;
    }
    void unite(size_t x, size_t y) {
        x = find(x);
        y = find(y);
        if (x == y) return;
        if (rank[x] < rank[y]) std::swap(x, y);
        parent[y] = x;
        if (rank[x] == rank[y]) rank[x]++;
    }
private:
    std::vector<size_t> parent;
    std::vector<size_t> rank;
};

FoFFinder::FoFFinder(FloatType link_length_ratio, size_t min_particles)
    : link_length_ratio_(link_length_ratio), min_particles_(min_particles) {}

auto FoFFinder::get_grid_key(const Position& pos, FloatType cell_size, FloatType box_size) const -> GridKey {
    int nx = static_cast<int>(std::floor(pos[0] / cell_size));
    int ny = static_cast<int>(std::floor(pos[1] / cell_size));
    int nz = static_cast<int>(std::floor(pos[2] / cell_size));
    int n_cells = static_cast<int>(std::floor(box_size / cell_size));
    nx = ((nx % n_cells) + n_cells) % n_cells;
    ny = ((ny % n_cells) + n_cells) % n_cells;
    nz = ((nz % n_cells) + n_cells) % n_cells;
    return std::make_tuple(nx, ny, nz);
}

void FoFFinder::get_neighbor_keys(const GridKey& key, int n_cells, std::vector<GridKey>& neighbors) const {
    int x = std::get<0>(key);
    int y = std::get<1>(key);
    int z = std::get<2>(key);
    neighbors.clear();
    for (int dx = -1; dx <= 1; ++dx) {
        for (int dy = -1; dy <= 1; ++dy) {
            for (int dz = -1; dz <= 1; ++dz) {
                int nx = ((x + dx) % n_cells + n_cells) % n_cells;
                int ny = ((y + dy) % n_cells + n_cells) % n_cells;
                int nz = ((z + dz) % n_cells + n_cells) % n_cells;
                neighbors.push_back(std::make_tuple(nx, ny, nz));
            }
        }
    }
}

void FoFFinder::find_halos(Snapshot& snapshot) {
    size_t n = snapshot.particles.size();
    if (n == 0) return;

    FloatType mean_spacing = compute_mean_interparticle_spacing(snapshot.box_size, n);
    FloatType link_length = link_length_ratio_ * mean_spacing;
    FloatType cell_size = link_length;
    int n_cells = static_cast<int>(std::floor(snapshot.box_size / cell_size));
    if (n_cells < 1) n_cells = 1;

    std::unordered_map<GridKey, std::vector<size_t>, GridKeyHash> grid;
    for (size_t i = 0; i < n; ++i) {
        GridKey key = get_grid_key(snapshot.particles.positions[i], cell_size, snapshot.box_size);
        grid[key].push_back(i);
    }

    UnionFind uf(n);
    std::vector<GridKey> neighbors;
    std::vector<bool> processed(n, false);

    for (size_t i = 0; i < n; ++i) {
        if (processed[i]) continue;
        GridKey key = get_grid_key(snapshot.particles.positions[i], cell_size, snapshot.box_size);
        get_neighbor_keys(key, n_cells, neighbors);

        for (const auto& neighbor_key : neighbors) {
            auto it = grid.find(neighbor_key);
            if (it == grid.end()) continue;
            for (size_t j : it->second) {
                if (j <= i) continue;
                FloatType dist = periodic_distance(
                    snapshot.particles.positions[i],
                    snapshot.particles.positions[j],
                    snapshot.box_size
                );
                if (dist < link_length) {
                    uf.unite(i, j);
                }
            }
        }
        processed[i] = true;
    }

    std::unordered_map<size_t, std::vector<size_t>> groups;
    for (size_t i = 0; i < n; ++i) {
        size_t root = uf.find(i);
        groups[root].push_back(i);
    }

    snapshot.halos.clear();
    IDType halo_id_counter = 0;
    for (const auto& [root, members] : groups) {
        if (members.size() < min_particles_) continue;
        Halo halo;
        halo.halo_id = static_cast<IDType>(snapshot.index) * 1000000 + halo_id_counter++;
        halo.snapshot_index = snapshot.index;
        halo.redshift = snapshot.redshift;
        halo.descendant_id = 0;
        for (size_t idx : members) {
            halo.particle_ids.push_back(snapshot.particles.ids[idx]);
        }
        compute_halo_properties(halo, snapshot);
        snapshot.halos.push_back(std::move(halo));
    }

    std::sort(snapshot.halos.begin(), snapshot.halos.end(),
              [](const Halo& a, const Halo& b) { return a.mass > b.mass; });
}

void FoFFinder::compute_halo_properties(Halo& halo, const Snapshot& snapshot) {
    std::unordered_map<IDType, size_t> id_to_idx;
    for (size_t i = 0; i < snapshot.particles.size(); ++i) {
        id_to_idx[snapshot.particles.ids[i]] = i;
    }

    halo.mass = 0.0;
    halo.center_of_mass = {0.0, 0.0, 0.0};
    halo.mean_velocity = {0.0, 0.0, 0.0};

    for (IDType pid : halo.particle_ids) {
        auto it = id_to_idx.find(pid);
        if (it == id_to_idx.end()) continue;
        size_t idx = it->second;
        FloatType m = snapshot.particles.masses[idx];
        halo.mass += m;
        for (int k = 0; k < 3; ++k) {
            halo.center_of_mass[k] += m * snapshot.particles.positions[idx][k];
            halo.mean_velocity[k] += m * snapshot.particles.velocities[idx][k];
        }
    }

    if (halo.mass > 0) {
        for (int k = 0; k < 3; ++k) {
            halo.center_of_mass[k] /= halo.mass;
            halo.mean_velocity[k] /= halo.mass;
        }
    }

    halo.velocity_dispersion = {0.0, 0.0, 0.0};
    Position angular_momentum = {0.0, 0.0, 0.0};
    for (IDType pid : halo.particle_ids) {
        auto it = id_to_idx.find(pid);
        if (it == id_to_idx.end()) continue;
        size_t idx = it->second;
        FloatType m = snapshot.particles.masses[idx];
        const Position& p = snapshot.particles.positions[idx];
        const Velocity& v = snapshot.particles.velocities[idx];
        FloatType dx = p[0] - halo.center_of_mass[0];
        FloatType dy = p[1] - halo.center_of_mass[1];
        FloatType dz = p[2] - halo.center_of_mass[2];
        dx -= snapshot.box_size * std::round(dx / snapshot.box_size);
        dy -= snapshot.box_size * std::round(dy / snapshot.box_size);
        dz -= snapshot.box_size * std::round(dz / snapshot.box_size);
        FloatType dvx = v[0] - halo.mean_velocity[0];
        FloatType dvy = v[1] - halo.mean_velocity[1];
        FloatType dvz = v[2] - halo.mean_velocity[2];
        for (int k = 0; k < 3; ++k) {
            halo.velocity_dispersion[k] += m * (v[k] - halo.mean_velocity[k]) * (v[k] - halo.mean_velocity[k]);
        }
        angular_momentum[0] += m * (dy * dvz - dz * dvy);
        angular_momentum[1] += m * (dz * dvx - dx * dvz);
        angular_momentum[2] += m * (dx * dvy - dy * dvx);
    }

    if (halo.mass > 0) {
        for (int k = 0; k < 3; ++k) {
            halo.velocity_dispersion[k] = std::sqrt(halo.velocity_dispersion[k] / halo.mass);
        }
    }

    FloatType L = std::sqrt(
        angular_momentum[0]*angular_momentum[0] +
        angular_momentum[1]*angular_momentum[1] +
        angular_momentum[2]*angular_momentum[2]
    );

    FloatType sigma_total = std::sqrt(
        halo.velocity_dispersion[0]*halo.velocity_dispersion[0] +
        halo.velocity_dispersion[1]*halo.velocity_dispersion[1] +
        halo.velocity_dispersion[2]*halo.velocity_dispersion[2]
    );

    size_t n_p = halo.particle_ids.size();
    if (sigma_total > 0 && n_p > 0 && halo.mass > 0) {
        FloatType r_vir = std::cbrt(3.0 * halo.mass / (4.0 * M_PI * 200.0 * RHO_CRIT));
        halo.spin_parameter = L / (std::sqrt(2.0) * halo.mass * sigma_total * r_vir);
    } else {
        halo.spin_parameter = 0.0;
    }

    if (compute_shape_) {
        compute_ellipsoidal_shape(halo, snapshot);
    }
}

void FoFFinder::compute_ellipsoidal_shape(Halo& halo, const Snapshot& snapshot) {
    shape_fitter_.fit(halo, snapshot, halo.shape, 3);
}

}
