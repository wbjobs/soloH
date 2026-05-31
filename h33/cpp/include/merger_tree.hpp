#ifndef HALO_ANALYSIS_MERGER_TREE_HPP
#define HALO_ANALYSIS_MERGER_TREE_HPP

#include "common.hpp"
#include <vector>
#include <unordered_map>
#include <unordered_set>

namespace halo_analysis {

struct MergerTreeNode {
    IDType halo_id;
    int snapshot_index;
    FloatType redshift;
    FloatType mass;
    FloatType formation_redshift;
    FloatType spin_parameter;
    IDType descendant_id;
    std::vector<IDType> progenitor_ids;
    std::vector<IDType> subhalo_ids;
    Position center_of_mass;
    size_t num_particles;
};

class MergerTreeBuilder {
public:
    MergerTreeBuilder(FloatType particle_share_threshold = 0.5,
                      FloatType subhalo_mass_ratio_threshold = 0.1);
    ~MergerTreeBuilder() = default;

    void build_trees(std::vector<Snapshot>& snapshots);
    void compute_formation_redshifts(std::vector<Snapshot>& snapshots);
    void identify_subhalos(std::vector<Snapshot>& snapshots);

    const std::vector<MergerTreeNode>& get_nodes() const { return nodes_; }
    const std::unordered_map<IDType, size_t>& get_halo_to_node() const { return halo_to_node_; }

    void set_particle_share_threshold(FloatType t) { share_threshold_ = t; }
    void set_subhalo_mass_ratio_threshold(FloatType t) { subhalo_threshold_ = t; }
    FloatType get_particle_share_threshold() const { return share_threshold_; }
    FloatType get_subhalo_mass_ratio_threshold() const { return subhalo_threshold_; }

    std::vector<IDType> get_progenitor_chain(IDType halo_id) const;
    std::vector<IDType> get_descendant_chain(IDType halo_id) const;
    std::vector<MergerTreeNode> filter_by_mass(FloatType min_mass, FloatType max_mass) const;
    std::vector<MergerTreeNode> filter_by_redshift(FloatType min_z, FloatType max_z) const;

    const std::unordered_map<IDType, IDType>& get_halo_id_mapping() const { return halo_id_remap_; }
    IDType get_original_halo_id(IDType remapped_id) const;

    void sort_progenitors_by_mass(std::vector<Snapshot>& snapshots);
    void assign_consistent_halo_ids(std::vector<Snapshot>& snapshots);

private:
    FloatType share_threshold_;
    FloatType subhalo_threshold_;
    std::vector<MergerTreeNode> nodes_;
    std::unordered_map<IDType, size_t> halo_to_node_;
    std::unordered_map<IDType, IDType> halo_id_remap_;
    std::unordered_map<IDType, IDType> remap_to_original_;

    FloatType compute_particle_share(const Halo& h1, const Halo& h2) const;
    void add_halo_node(const Halo& halo);
    IDType find_main_progenitor(IDType halo_id,
        const std::unordered_map<IDType, Halo*>& halo_map) const;
};

}

#endif
