#include "merger_tree.hpp"
#include <iostream>
#include <algorithm>
#include <set>

namespace halo_analysis {

MergerTreeBuilder::MergerTreeBuilder(FloatType particle_share_threshold,
                                     FloatType subhalo_mass_ratio_threshold)
    : share_threshold_(particle_share_threshold),
      subhalo_threshold_(subhalo_mass_ratio_threshold) {}

FloatType MergerTreeBuilder::compute_particle_share(const Halo& h1, const Halo& h2) const {
    std::unordered_set<IDType> set1(h1.particle_ids.begin(), h1.particle_ids.end());
    size_t shared = 0;
    for (IDType id : h2.particle_ids) {
        if (set1.count(id) > 0) shared++;
    }
    size_t min_size = std::min(h1.particle_ids.size(), h2.particle_ids.size());
    return min_size > 0 ? static_cast<FloatType>(shared) / min_size : 0.0;
}

void MergerTreeBuilder::add_halo_node(const Halo& halo) {
    MergerTreeNode node;
    node.halo_id = halo.halo_id;
    node.snapshot_index = halo.snapshot_index;
    node.redshift = halo.redshift;
    node.mass = halo.mass;
    node.formation_redshift = halo.formation_redshift;
    node.spin_parameter = halo.spin_parameter;
    node.descendant_id = halo.descendant_id;
    node.progenitor_ids = halo.progenitor_ids;
    node.subhalo_ids = halo.subhalo_ids;
    node.center_of_mass = halo.center_of_mass;
    node.num_particles = halo.particle_ids.size();
    halo_to_node_[halo.halo_id] = nodes_.size();
    nodes_.push_back(node);
}

IDType MergerTreeBuilder::find_main_progenitor(IDType halo_id,
    const std::unordered_map<IDType, Halo*>& halo_map) const {
    std::unordered_set<IDType> visited;
    IDType current_id = halo_id;
    auto it = halo_map.find(current_id);
    if (it == halo_map.end()) {
        return halo_id;
    }
    Halo* current_halo = it->second;

    while (current_halo != nullptr && !current_halo->progenitor_ids.empty()) {
        if (visited.count(current_id) > 0) {
            break;
        }
        visited.insert(current_id);

        FloatType max_mass = 0;
        IDType main_prog = 0;
        for (IDType prog_id : current_halo->progenitor_ids) {
            auto prog_it = halo_map.find(prog_id);
            if (prog_it == halo_map.end()) continue;
            if (prog_it->second->mass > max_mass) {
                max_mass = prog_it->second->mass;
                main_prog = prog_id;
            }
        }

        if (main_prog == 0) {
            break;
        }

        FloatType mass_ratio = max_mass / current_halo->mass;
        if (mass_ratio < 0.5) {
            break;
        }

        current_id = main_prog;
        auto current_it = halo_map.find(current_id);
        current_halo = (current_it != halo_map.end()) ? current_it->second : nullptr;
    }

    return (current_halo != nullptr) ? current_id : halo_id;
}

void MergerTreeBuilder::assign_consistent_halo_ids(std::vector<Snapshot>& snapshots) {
    std::unordered_map<IDType, Halo*> halo_map;
    for (auto& snapshot : snapshots) {
        for (auto& halo : snapshot.halos) {
            halo_map[halo.halo_id] = &halo;
        }
    }

    halo_id_remap_.clear();
    remap_to_original_.clear();
    IDType next_id = 1;

    std::sort(snapshots.begin(), snapshots.end(),
              [](const Snapshot& a, const Snapshot& b) {
                  return a.redshift < b.redshift;
              });

    for (size_t i = 0; i < snapshots.size(); ++i) {
        snapshots[i].index = static_cast<int>(i);
    }

    for (auto& snapshot : snapshots) {
        for (auto& halo : snapshot.halos) {
            halo.snapshot_index = snapshot.index;
            halo.redshift = snapshot.redshift;
        }
    }

    for (auto& snapshot : snapshots) {
        for (auto& halo : snapshot.halos) {
            IDType root_id = find_main_progenitor(halo.halo_id, halo_map);

            IDType new_id;
            if (halo_id_remap_.find(root_id) != halo_id_remap_.end()) {
                new_id = halo_id_remap_[root_id];
            } else {
                new_id = next_id++;
                halo_id_remap_[root_id] = new_id;
                remap_to_original_[new_id] = root_id;
            }

            halo_id_remap_[halo.halo_id] = new_id;
            remap_to_original_[new_id] = root_id;
        }
    }

    for (auto& snapshot : snapshots) {
        for (auto& halo : snapshot.halos) {
            IDType old_id = halo.halo_id;
            halo.halo_id = halo_id_remap_[old_id];

            if (halo.descendant_id != 0) {
                halo.descendant_id = halo_id_remap_[halo.descendant_id];
            }

            for (auto& prog_id : halo.progenitor_ids) {
                prog_id = halo_id_remap_[prog_id];
            }

            for (auto& sub_id : halo.subhalo_ids) {
                if (halo_id_remap_.find(sub_id) != halo_id_remap_.end()) {
                    sub_id = halo_id_remap_[sub_id];
                }
            }
        }
    }
}

void MergerTreeBuilder::sort_progenitors_by_mass(std::vector<Snapshot>& snapshots) {
    std::unordered_map<IDType, Halo*> halo_map;
    for (auto& snapshot : snapshots) {
        for (auto& halo : snapshot.halos) {
            halo_map[halo.halo_id] = &halo;
        }
    }

    for (auto& snapshot : snapshots) {
        for (auto& halo : snapshot.halos) {
            if (halo.progenitor_ids.size() > 1) {
                std::sort(halo.progenitor_ids.begin(), halo.progenitor_ids.end(),
                    [&](IDType a, IDType b) {
                        auto it_a = halo_map.find(a);
                        auto it_b = halo_map.find(b);
                        FloatType mass_a = (it_a != halo_map.end()) ? it_a->second->mass : 0;
                        FloatType mass_b = (it_b != halo_map.end()) ? it_b->second->mass : 0;
                        return mass_a > mass_b;
                    });
            }
        }
    }

    for (auto& node : nodes_) {
        if (node.progenitor_ids.size() > 1) {
            std::sort(node.progenitor_ids.begin(), node.progenitor_ids.end(),
                [&](IDType a, IDType b) {
                    auto it_a = halo_to_node_.find(a);
                    auto it_b = halo_to_node_.find(b);
                    FloatType mass_a = (it_a != halo_to_node_.end()) ? nodes_[it_a->second].mass : 0;
                    FloatType mass_b = (it_b != halo_to_node_.end()) ? nodes_[it_b->second].mass : 0;
                    return mass_a > mass_b;
                });
        }
    }
}

IDType MergerTreeBuilder::get_original_halo_id(IDType remapped_id) const {
    auto it = remap_to_original_.find(remapped_id);
    if (it != remap_to_original_.end()) {
        return it->second;
    }
    return remapped_id;
}

void MergerTreeBuilder::build_trees(std::vector<Snapshot>& snapshots) {
    nodes_.clear();
    halo_to_node_.clear();
    halo_id_remap_.clear();
    remap_to_original_.clear();

    std::sort(snapshots.begin(), snapshots.end(),
              [](const Snapshot& a, const Snapshot& b) {
                  return a.redshift > b.redshift;
              });

    for (size_t i = 0; i < snapshots.size(); ++i) {
        snapshots[i].index = static_cast<int>(i);
        for (auto& halo : snapshots[i].halos) {
            halo.snapshot_index = static_cast<int>(i);
            halo.redshift = snapshots[i].redshift;
            halo.descendant_id = 0;
            halo.progenitor_ids.clear();
        }
    }

    for (int snap_idx = 0; snap_idx < static_cast<int>(snapshots.size()) - 1; ++snap_idx) {
        int next_snap_idx = snap_idx + 1;
        Snapshot& current_snap = snapshots[snap_idx];
        Snapshot& next_snap = snapshots[next_snap_idx];

        for (Halo& current_halo : current_snap.halos) {
            FloatType best_share = share_threshold_;
            IDType best_descendant = 0;

            for (Halo& next_halo : next_snap.halos) {
                FloatType share = compute_particle_share(current_halo, next_halo);
                if (share > best_share) {
                    best_share = share;
                    best_descendant = next_halo.halo_id;
                }
            }

            current_halo.descendant_id = best_descendant;
            if (best_descendant != 0) {
                for (Halo& next_halo : next_snap.halos) {
                    if (next_halo.halo_id == best_descendant) {
                        next_halo.progenitor_ids.push_back(current_halo.halo_id);
                        break;
                    }
                }
            }
        }
    }

    sort_progenitors_by_mass(snapshots);
    assign_consistent_halo_ids(snapshots);
    sort_progenitors_by_mass(snapshots);

    nodes_.clear();
    halo_to_node_.clear();
    for (auto& snapshot : snapshots) {
        for (auto& halo : snapshot.halos) {
            add_halo_node(halo);
        }
    }
}

void MergerTreeBuilder::compute_formation_redshifts(std::vector<Snapshot>& snapshots) {
    std::unordered_map<IDType, Halo*> halo_map;
    for (auto& snapshot : snapshots) {
        for (auto& halo : snapshot.halos) {
            halo_map[halo.halo_id] = &halo;
        }
    }

    for (auto& snapshot : snapshots) {
        for (auto& halo : snapshot.halos) {
            if (halo.progenitor_ids.empty()) {
                halo.formation_redshift = halo.redshift;
            } else {
                FloatType half_mass = halo.mass * 0.5;
                IDType progenitor_with_half = 0;
                FloatType max_progenitor_mass = 0;

                for (IDType prog_id : halo.progenitor_ids) {
                    auto it = halo_map.find(prog_id);
                    if (it == halo_map.end()) continue;
                    if (it->second->mass >= half_mass && it->second->mass > max_progenitor_mass) {
                        max_progenitor_mass = it->second->mass;
                        progenitor_with_half = prog_id;
                    }
                }

                if (progenitor_with_half != 0) {
                    halo.formation_redshift = halo_map[progenitor_with_half]->formation_redshift;
                } else {
                    halo.formation_redshift = halo.redshift;
                }
            }

            auto node_it = halo_to_node_.find(halo.halo_id);
            if (node_it != halo_to_node_.end()) {
                nodes_[node_it->second].formation_redshift = halo.formation_redshift;
            }
        }
    }
}

void MergerTreeBuilder::identify_subhalos(std::vector<Snapshot>& snapshots) {
    for (auto& snapshot : snapshots) {
        for (size_t i = 0; i < snapshot.halos.size(); ++i) {
            Halo& main_halo = snapshot.halos[i];
            for (size_t j = 0; j < snapshot.halos.size(); ++j) {
                if (i == j) continue;
                Halo& other_halo = snapshot.halos[j];
                FloatType mass_ratio = other_halo.mass / main_halo.mass;
                if (mass_ratio > 0 && mass_ratio < subhalo_threshold_) {
                    FloatType dist = periodic_distance(
                        main_halo.center_of_mass,
                        other_halo.center_of_mass,
                        snapshot.box_size
                    );
                    FloatType main_r_vir = std::cbrt(3.0 * main_halo.mass / (4.0 * M_PI * 200.0));
                    if (dist < 2.0 * main_r_vir) {
                        main_halo.subhalo_ids.push_back(other_halo.halo_id);
                    }
                }
            }

            auto node_it = halo_to_node_.find(main_halo.halo_id);
            if (node_it != halo_to_node_.end()) {
                nodes_[node_it->second].subhalo_ids = main_halo.subhalo_ids;
            }
        }
    }
}

std::vector<IDType> MergerTreeBuilder::get_progenitor_chain(IDType halo_id) const {
    std::vector<IDType> chain;
    std::unordered_set<IDType> visited;
    std::function<void(IDType)> dfs = [&](IDType id) {
        if (visited.count(id) > 0) return;
        visited.insert(id);
        auto it = halo_to_node_.find(id);
        if (it == halo_to_node_.end()) return;
        const auto& node = nodes_[it->second];
        for (IDType prog_id : node.progenitor_ids) {
            dfs(prog_id);
        }
        chain.push_back(id);
    };
    dfs(halo_id);
    return chain;
}

std::vector<IDType> MergerTreeBuilder::get_descendant_chain(IDType halo_id) const {
    std::vector<IDType> chain;
    std::unordered_set<IDType> visited;
    IDType current = halo_id;
    while (current != 0) {
        if (visited.count(current) > 0) break;
        auto it = halo_to_node_.find(current);
        if (it == halo_to_node_.end()) break;
        visited.insert(current);
        chain.push_back(current);
        current = nodes_[it->second].descendant_id;
    }
    return chain;
}

std::vector<MergerTreeNode> MergerTreeBuilder::filter_by_mass(FloatType min_mass, FloatType max_mass) const {
    std::vector<MergerTreeNode> result;
    for (const auto& node : nodes_) {
        if (node.mass >= min_mass && node.mass <= max_mass) {
            result.push_back(node);
        }
    }
    return result;
}

std::vector<MergerTreeNode> MergerTreeBuilder::filter_by_redshift(FloatType min_z, FloatType max_z) const {
    std::vector<MergerTreeNode> result;
    for (const auto& node : nodes_) {
        if (node.redshift >= min_z && node.redshift <= max_z) {
            result.push_back(node);
        }
    }
    return result;
}

}
