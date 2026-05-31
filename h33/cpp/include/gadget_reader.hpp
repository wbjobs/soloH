#ifndef HALO_ANALYSIS_GADGET_READER_HPP
#define HALO_ANALYSIS_GADGET_READER_HPP

#include "common.hpp"
#include <string>
#include <fstream>
#include <cstring>

namespace halo_analysis {

struct GadgetHeader {
    uint32_t npart[6];
    double massarr[6];
    double time;
    double redshift;
    int32_t flag_sfr;
    int32_t flag_feedback;
    uint32_t npartTotal[6];
    int32_t flag_cooling;
    int32_t num_files;
    double BoxSize;
    double Omega0;
    double OmegaLambda;
    double HubbleParam;
    int32_t flag_stellarage;
    int32_t flag_metals;
    uint32_t npartTotalHighWord[6];
    int32_t flag_entropy_instead_u;
    char fill[60];
};

class GadgetReader {
public:
    GadgetReader() = default;
    ~GadgetReader() = default;

    bool read(const std::string& filename, Snapshot& snapshot, int snapshot_index = 0);
    bool read_header(const std::string& filename, GadgetHeader& header);

private:
    bool read_block(std::ifstream& file, void* data, size_t size);
    size_t get_total_particles(const GadgetHeader& header);
};

}

#endif
