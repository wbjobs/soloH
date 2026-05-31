#include "gadget_reader.hpp"
#include <iostream>
#include <stdexcept>
#include <algorithm>

namespace halo_analysis {

size_t GadgetReader::get_total_particles(const GadgetHeader& header) {
    size_t total = 0;
    for (int i = 0; i < 6; ++i) {
        total += header.npart[i];
    }
    return total;
}

bool GadgetReader::read_block(std::ifstream& file, void* data, size_t size) {
    int32_t block_size_before, block_size_after;
    file.read(reinterpret_cast<char*>(&block_size_before), sizeof(int32_t));
    if (!file || static_cast<size_t>(block_size_before) != size) {
        return false;
    }
    file.read(reinterpret_cast<char*>(data), size);
    if (!file) return false;
    file.read(reinterpret_cast<char*>(&block_size_after), sizeof(int32_t));
    if (!file || block_size_before != block_size_after) {
        return false;
    }
    return true;
}

bool GadgetReader::read_header(const std::string& filename, GadgetHeader& header) {
    std::ifstream file(filename, std::ios::binary);
    if (!file) {
        std::cerr << "Error: Cannot open file " << filename << std::endl;
        return false;
    }
    std::memset(&header, 0, sizeof(GadgetHeader));
    if (!read_block(file, &header, sizeof(GadgetHeader))) {
        std::cerr << "Error: Failed to read Gadget-2 header from " << filename << std::endl;
        return false;
    }
    return true;
}

bool GadgetReader::read(const std::string& filename, Snapshot& snapshot, int snapshot_index) {
    GadgetHeader header;
    if (!read_header(filename, header)) {
        return false;
    }
    std::ifstream file(filename, std::ios::binary);
    if (!file) return false;
    file.seekg(sizeof(int32_t) + sizeof(GadgetHeader) + sizeof(int32_t));
    size_t total_particles = get_total_particles(header);
    snapshot.index = snapshot_index;
    snapshot.redshift = header.redshift;
    snapshot.scale_factor = header.time;
    snapshot.box_size = header.BoxSize;
    snapshot.particles.clear();
    snapshot.particles.reserve(total_particles);
    std::vector<float> pos_data(total_particles * 3);
    if (!read_block(file, pos_data.data(), sizeof(float) * total_particles * 3)) {
        std::cerr << "Error: Failed to read positions" << std::endl;
        return false;
    }
    std::vector<float> vel_data(total_particles * 3);
    if (!read_block(file, vel_data.data(), sizeof(float) * total_particles * 3)) {
        std::cerr << "Error: Failed to read velocities" << std::endl;
        return false;
    }
    size_t id_size = (header.npartTotal[1] & (1UL << 31)) ? sizeof(uint64_t) : sizeof(uint32_t);
    std::vector<uint64_t> id_data(total_particles);
    if (id_size == sizeof(uint32_t)) {
        std::vector<uint32_t> id32(total_particles);
        if (!read_block(file, id32.data(), sizeof(uint32_t) * total_particles)) {
            std::cerr << "Error: Failed to read IDs" << std::endl;
            return false;
        }
        for (size_t i = 0; i < total_particles; ++i) id_data[i] = id32[i];
    } else {
        if (!read_block(file, id_data.data(), sizeof(uint64_t) * total_particles)) {
            std::cerr << "Error: Failed to read IDs" << std::endl;
            return false;
        }
    }
    std::vector<double> mass_data(total_particles);
    size_t mass_offset = 0;
    for (int ptype = 0; ptype < 6; ++ptype) {
        uint32_t n = header.npart[ptype];
        double mass = header.massarr[ptype];
        if (mass == 0.0 && n > 0) {
            std::vector<float> mass_block(n);
            if (!read_block(file, mass_block.data(), sizeof(float) * n)) {
                std::cerr << "Error: Failed to read masses for type " << ptype << std::endl;
                return false;
            }
            for (uint32_t i = 0; i < n; ++i) {
                mass_data[mass_offset + i] = static_cast<double>(mass_block[i]);
            }
        } else {
            for (uint32_t i = 0; i < n; ++i) {
                mass_data[mass_offset + i] = mass;
            }
        }
        mass_offset += n;
    }
    for (size_t i = 0; i < total_particles; ++i) {
        snapshot.particles.ids.push_back(id_data[i]);
        snapshot.particles.positions.push_back({
            static_cast<double>(pos_data[i*3]),
            static_cast<double>(pos_data[i*3+1]),
            static_cast<double>(pos_data[i*3+2])
        });
        snapshot.particles.velocities.push_back({
            static_cast<double>(vel_data[i*3]),
            static_cast<double>(vel_data[i*3+1]),
            static_cast<double>(vel_data[i*3+2])
        });
        snapshot.particles.masses.push_back(mass_data[i]);
    }
    return true;
}

}
