#include "substructure.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>

namespace halo_analysis {

SubstructureFinder::SubstructureFinder(FloatType mass_ratio_threshold,
                                       FloatType radius_threshold,
                                       size_t min_particles)
    : mass_ratio_threshold_(mass_ratio_threshold),
      radius_threshold_(radius_threshold),
      min_particles_(min_particles) {}

FloatType SubstructureFinder::compute_halo_radius(const Halo& halo) const {
    if (halo.mass <= 0) return 0.0;
    return std::cbrt(3.0 * halo.mass / (4.0 * M_PI * 200.0 * RHO_CRIT));
}

void SubstructureFinder::identify_subhalos_within_halo(Halo& host, const std::vector<Halo>& all_halos,
                                                        const Snapshot& snapshot) {
    FloatType r_host = compute_halo_radius(host);
    FloatType r_threshold = radius_threshold_ * r_host;
    host.substructure_ids.clear();

    std::unordered_map<IDType, size_t> id_to_idx;
    for (size_t i = 0; i < all_halos.size(); ++i) {
        id_to_idx[all_halos[i].halo_id] = i;
    }

    for (const Halo& candidate : all_halos) {
        if (candidate.halo_id == host.halo_id) continue;
        if (candidate.mass >= host.mass * mass_ratio_threshold_) continue;
        if (candidate.particle_ids.size() < min_particles_) continue;

        FloatType dist = periodic_distance(host.center_of_mass, candidate.center_of_mass, snapshot.box_size);
        if (dist <= r_threshold) {
            host.substructure_ids.push_back(candidate.halo_id);
        }
    }

    std::sort(host.substructure_ids.begin(), host.substructure_ids.end(),
              [&](IDType a, IDType b) {
                  auto ita = id_to_idx.find(a);
                  auto itb = id_to_idx.find(b);
                  if (ita == id_to_idx.end() || itb == id_to_idx.end()) return a < b;
                  return all_halos[ita->second].mass > all_halos[itb->second].mass;
              });
}

void SubstructureFinder::find_substructures(Snapshot& snapshot) {
    for (Halo& halo : snapshot.halos) {
        halo.is_substructure = false;
        halo.parent_halo_id = 0;
        halo.substructure_ids.clear();
    }

    std::sort(snapshot.halos.begin(), snapshot.halos.end(),
              [](const Halo& a, const Halo& b) { return a.mass > b.mass; });

    for (size_t i = 0; i < snapshot.halos.size(); ++i) {
        Halo& host = snapshot.halos[i];
        if (host.is_substructure) continue;

        identify_subhalos_within_halo(host, snapshot.halos, snapshot);

        for (IDType sub_id : host.substructure_ids) {
            for (Halo& halo : snapshot.halos) {
                if (halo.halo_id == sub_id) {
                    halo.is_substructure = true;
                    halo.parent_halo_id = host.halo_id;
                    break;
                }
            }
        }
    }
}

std::vector<IDType> SubstructureFinder::find_bound_particles(const Halo& halo, const Snapshot& snapshot,
                                                              int n_iterations) {
    std::unordered_map<IDType, size_t> id_to_idx;
    for (size_t i = 0; i < snapshot.particles.size(); ++i) {
        id_to_idx[snapshot.particles.ids[i]] = i;
    }

    std::vector<IDType> bound_particles = halo.particle_ids;
    FloatType r_prev = compute_halo_radius(halo);

    for (int iter = 0; iter < n_iterations; ++iter) {
        Position com = {0.0, 0.0, 0.0};
        Velocity mean_vel = {0.0, 0.0, 0.0};
        FloatType total_mass = 0.0;

        for (IDType pid : bound_particles) {
            auto it = id_to_idx.find(pid);
            if (it == id_to_idx.end()) continue;
            size_t idx = it->second;
            FloatType m = snapshot.particles.masses[idx];
            total_mass += m;
            for (int k = 0; k < 3; ++k) {
                com[k] += m * snapshot.particles.positions[idx][k];
                mean_vel[k] += m * snapshot.particles.velocities[idx][k];
            }
        }

        if (total_mass <= 0) break;
        for (int k = 0; k < 3; ++k) {
            com[k] /= total_mass;
            mean_vel[k] /= total_mass;
        }

        FloatType v_rms = 0.0;
        for (IDType pid : bound_particles) {
            auto it = id_to_idx.find(pid);
            if (it == id_to_idx.end()) continue;
            size_t idx = it->second;
            for (int k = 0; k < 3; ++k) {
                FloatType dv = snapshot.particles.velocities[idx][k] - mean_vel[k];
                v_rms += dv * dv;
            }
        }
        v_rms = std::sqrt(v_rms / bound_particles.size());
        FloatType escape_vel = std::sqrt(2.0) * v_rms;

        std::vector<IDType> new_bound;
        for (IDType pid : bound_particles) {
            auto it = id_to_idx.find(pid);
            if (it == id_to_idx.end()) continue;
            size_t idx = it->second;

            FloatType dx = snapshot.particles.positions[idx][0] - com[0];
            FloatType dy = snapshot.particles.positions[idx][1] - com[1];
            FloatType dz = snapshot.particles.positions[idx][2] - com[2];
            dx -= snapshot.box_size * std::round(dx / snapshot.box_size);
            dy -= snapshot.box_size * std::round(dy / snapshot.box_size);
            dz -= snapshot.box_size * std::round(dz / snapshot.box_size);
            FloatType r = std::sqrt(dx*dx + dy*dy + dz*dz);

            FloatType dvx = snapshot.particles.velocities[idx][0] - mean_vel[0];
            FloatType dvy = snapshot.particles.velocities[idx][1] - mean_vel[1];
            FloatType dvz = snapshot.particles.velocities[idx][2] - mean_vel[2];
            FloatType v = std::sqrt(dvx*dvx + dvy*dvy + dvz*dvz);

            if (r > 0 && v <= escape_vel) {
                FloatType pot = -G * total_mass / r;
                FloatType ke = 0.5 * v * v;
                if (ke + pot < 0) {
                    new_bound.push_back(pid);
                }
            } else if (r == 0) {
                new_bound.push_back(pid);
            }
        }

        if (new_bound.size() < min_particles_) break;
        if (new_bound.size() == bound_particles.size()) break;

        bound_particles = new_bound;

        Halo tmp_halo;
        tmp_halo.particle_ids = bound_particles;
        tmp_halo.mass = total_mass;
        FloatType r_new = compute_halo_radius(tmp_halo);
        if (std::abs(r_new - r_prev) / r_prev < 0.01) break;
        r_prev = r_new;
    }

    return bound_particles;
}

void SubstructureFinder::decompose_halo_bound(Halo& halo, const Snapshot& snapshot,
                                               int n_iterations) {
    std::vector<IDType> bound = find_bound_particles(halo, snapshot, n_iterations);
    if (bound.size() >= min_particles_) {
        halo.particle_ids = bound;
        std::unordered_map<IDType, size_t> id_to_idx;
        for (size_t i = 0; i < snapshot.particles.size(); ++i) {
            id_to_idx[snapshot.particles.ids[i]] = i;
        }
        halo.mass = 0.0;
        for (IDType pid : bound) {
            auto it = id_to_idx.find(pid);
            if (it != id_to_idx.end()) {
                halo.mass += snapshot.particles.masses[it->second];
            }
        }
    }
}

void SubstructureFinder::track_substructures(std::vector<Snapshot>& snapshots) {
    if (snapshots.size() < 2) return;

    for (size_t i = 1; i < snapshots.size(); ++i) {
        Snapshot& snap_prev = snapshots[i-1];
        Snapshot& snap_curr = snapshots[i];

        for (Halo& halo_prev : snap_prev.halos) {
            if (!halo_prev.is_substructure) continue;

            std::unordered_set<IDType> prev_particles(halo_prev.particle_ids.begin(),
                                                       halo_prev.particle_ids.end());

            IDType best_match = 0;
            FloatType best_overlap = 0.0;

            for (Halo& halo_curr : snap_curr.halos) {
                if (halo_curr.descendant_id == 0) continue;
                if (!halo_curr.is_substructure) continue;

                size_t overlap = 0;
                for (IDType pid : halo_curr.particle_ids) {
                    if (prev_particles.count(pid) > 0) {
                        overlap++;
                    }
                }

                FloatType overlap_ratio = static_cast<FloatType>(overlap) /
                                          std::min(halo_prev.particle_ids.size(),
                                                    halo_curr.particle_ids.size());

                if (overlap_ratio > best_overlap) {
                    best_overlap = overlap_ratio;
                    best_match = halo_curr.halo_id;
                }
            }

            if (best_overlap > 0.3) {
                halo_prev.descendant_id = best_match;
                for (Halo& halo_curr : snap_curr.halos) {
                    if (halo_curr.halo_id == best_match) {
                        halo_curr.progenitor_ids.push_back(halo_prev.halo_id);
                        break;
                    }
                }
            }
        }
    }
}

}
