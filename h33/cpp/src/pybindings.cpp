#include "common.hpp"
#include "gadget_reader.hpp"
#include "fof.hpp"
#include "merger_tree.hpp"
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>
#include <pybind11/complex.h>
#include <pybind11/functional.h>
#include <pybind11/chrono.h>

namespace py = pybind11;
using namespace halo_analysis;

PYBIND11_MODULE(halo_analysis_cpp, m) {
    m.doc() = "Halo analysis C++ core module";

    py::class_<ParticleData>(m, "ParticleData")
        .def(py::init<>())
        .def_readwrite("ids", &ParticleData::ids)
        .def_readwrite("positions", &ParticleData::positions)
        .def_readwrite("velocities", &ParticleData::velocities)
        .def_readwrite("masses", &ParticleData::masses)
        .def("size", &ParticleData::size)
        .def("reserve", &ParticleData::reserve)
        .def("clear", &ParticleData::clear);

    py::class_<Halo>(m, "Halo")
        .def(py::init<>())
        .def_readwrite("halo_id", &Halo::halo_id)
        .def_readwrite("snapshot_index", &Halo::snapshot_index)
        .def_readwrite("redshift", &Halo::redshift)
        .def_readwrite("particle_ids", &Halo::particle_ids)
        .def_readwrite("mass", &Halo::mass)
        .def_readwrite("center_of_mass", &Halo::center_of_mass)
        .def_readwrite("mean_velocity", &Halo::mean_velocity)
        .def_readwrite("velocity_dispersion", &Halo::velocity_dispersion)
        .def_readwrite("spin_parameter", &Halo::spin_parameter)
        .def_readwrite("formation_redshift", &Halo::formation_redshift)
        .def_readwrite("descendant_id", &Halo::descendant_id)
        .def_readwrite("progenitor_ids", &Halo::progenitor_ids)
        .def_readwrite("subhalo_ids", &Halo::subhalo_ids);

    py::class_<Snapshot>(m, "Snapshot")
        .def(py::init<>())
        .def_readwrite("index", &Snapshot::index)
        .def_readwrite("redshift", &Snapshot::redshift)
        .def_readwrite("scale_factor", &Snapshot::scale_factor)
        .def_readwrite("box_size", &Snapshot::box_size)
        .def_readwrite("particles", &Snapshot::particles)
        .def_readwrite("halos", &Snapshot::halos);

    py::class_<MergerTreeNode>(m, "MergerTreeNode")
        .def(py::init<>())
        .def_readwrite("halo_id", &MergerTreeNode::halo_id)
        .def_readwrite("snapshot_index", &MergerTreeNode::snapshot_index)
        .def_readwrite("redshift", &MergerTreeNode::redshift)
        .def_readwrite("mass", &MergerTreeNode::mass)
        .def_readwrite("formation_redshift", &MergerTreeNode::formation_redshift)
        .def_readwrite("spin_parameter", &MergerTreeNode::spin_parameter)
        .def_readwrite("descendant_id", &MergerTreeNode::descendant_id)
        .def_readwrite("progenitor_ids", &MergerTreeNode::progenitor_ids)
        .def_readwrite("subhalo_ids", &MergerTreeNode::subhalo_ids)
        .def_readwrite("center_of_mass", &MergerTreeNode::center_of_mass)
        .def_readwrite("num_particles", &MergerTreeNode::num_particles);

    py::class_<GadgetReader>(m, "GadgetReader")
        .def(py::init<>())
        .def("read", &GadgetReader::read,
             py::arg("filename"), py::arg("snapshot"), py::arg("snapshot_index") = 0)
        .def("read_header", &GadgetReader::read_header);

    py::class_<FoFFinder>(m, "FoFFinder")
        .def(py::init<FloatType, size_t>(),
             py::arg("link_length_ratio") = 0.2, py::arg("min_particles") = 20)
        .def("find_halos", &FoFFinder::find_halos)
        .def("compute_halo_properties", &FoFFinder::compute_halo_properties)
        .def_property("link_length_ratio",
                        &FoFFinder::get_link_length_ratio,
                        &FoFFinder::set_link_length_ratio)
        .def_property("min_particles",
                        &FoFFinder::get_min_particles,
                        &FoFFinder::set_min_particles);

    py::class_<MergerTreeBuilder>(m, "MergerTreeBuilder")
        .def(py::init<FloatType, FloatType>(),
             py::arg("particle_share_threshold") = 0.5,
             py::arg("subhalo_mass_ratio_threshold") = 0.1)
        .def("build_trees", &MergerTreeBuilder::build_trees)
        .def("compute_formation_redshifts", &MergerTreeBuilder::compute_formation_redshifts)
        .def("identify_subhalos", &MergerTreeBuilder::identify_subhalos)
        .def("get_nodes", &MergerTreeBuilder::get_nodes)
        .def("get_halo_to_node", &MergerTreeBuilder::get_halo_to_node)
        .def("get_progenitor_chain", &MergerTreeBuilder::get_progenitor_chain)
        .def("get_descendant_chain", &MergerTreeBuilder::get_descendant_chain)
        .def("filter_by_mass", &MergerTreeBuilder::filter_by_mass)
        .def("filter_by_redshift", &MergerTreeBuilder::filter_by_redshift)
        .def("get_halo_id_mapping", &MergerTreeBuilder::get_halo_id_mapping)
        .def("get_original_halo_id", &MergerTreeBuilder::get_original_halo_id)
        .def("sort_progenitors_by_mass", &MergerTreeBuilder::sort_progenitors_by_mass)
        .def("assign_consistent_halo_ids", &MergerTreeBuilder::assign_consistent_halo_ids)
        .def_property("particle_share_threshold",
                        &MergerTreeBuilder::get_particle_share_threshold,
                        &MergerTreeBuilder::set_particle_share_threshold)
        .def_property("subhalo_mass_ratio_threshold",
                        &MergerTreeBuilder::get_subhalo_mass_ratio_threshold,
                        &MergerTreeBuilder::set_subhalo_mass_ratio_threshold);

    m.def("compute_mean_interparticle_spacing", &compute_mean_interparticle_spacing);
    m.def("periodic_distance", &periodic_distance);
}
