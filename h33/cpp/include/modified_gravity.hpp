#ifndef HALO_ANALYSIS_MODIFIED_GRAVITY_HPP
#define HALO_ANALYSIS_MODIFIED_GRAVITY_HPP

#include "common.hpp"
#include <vector>
#include <string>
#include <unordered_map>

namespace halo_analysis {

enum class GravityModel {
    GR,
    F_R
};

struct F_R_Parameters {
    FloatType f_R0;
    FloatType n;
    std::string name;
};

struct HaloStatistics {
    FloatType mass_mean;
    FloatType mass_median;
    FloatType concentration_mean;
    FloatType concentration_median;
    FloatType spin_mean;
    FloatType spin_median;
    FloatType axis_ratio_mean_b_a;
    FloatType axis_ratio_mean_c_a;
    FloatType triaxiality_mean;
    FloatType ellipticity_mean;
    size_t num_halos;
    std::vector<FloatType> mass_bins;
    std::vector<FloatType> mass_function;
    std::vector<FloatType> mass_function_errors;
    std::vector<FloatType> redshift_bins;
    std::vector<FloatType> halo_abundance;
};

struct ModelComparison {
    GravityModel model1;
    GravityModel model2;
    std::string model1_name;
    std::string model2_name;
    FloatType mass_function_delta;
    FloatType concentration_delta;
    FloatType spin_delta;
    FloatType ellipticity_delta;
    std::vector<FloatType> mass_function_ratio;
    std::vector<FloatType> mass_bin_centers;
    FloatType ks_statistic;
    FloatType ks_p_value;
    std::vector<std::string> significant_differences;
};

class ModifiedGravityInterface {
public:
    ModifiedGravityInterface();
    ~ModifiedGravityInterface() = default;

    void register_model(GravityModel model, const F_R_Parameters& params);
    void set_current_model(GravityModel model);

    HaloStatistics compute_statistics(const std::vector<Halo>& halos,
                                       FloatType box_size,
                                       bool use_adaptive_binning = true,
                                       int min_count_per_bin = 10);

    ModelComparison compare_models(const HaloStatistics& stats1,
                                    const HaloStatistics& stats2,
                                    const std::string& name1 = "GR",
                                    const std::string& name2 = "F(R)");

    FloatType compute_fifth_force_coupling(FloatType f_R, FloatType n = 1.0);
    FloatType compute_screeing_scale(FloatType f_R, FloatType n = 1.0,
                                     FloatType density = 1.0);
    FloatType compute_boost_factor(FloatType mass, FloatType redshift,
                                    const F_R_Parameters& params);
    bool is_halo_chameleon_screened(const Halo& halo, const F_R_Parameters& params);

    const F_R_Parameters& get_parameters(GravityModel model) const;
    GravityModel get_current_model() const { return current_model_; }

private:
    std::unordered_map<GravityModel, F_R_Parameters> model_params_;
    GravityModel current_model_;

    FloatType kolmogorov_smirnov_statistic(const std::vector<FloatType>& sample1,
                                            const std::vector<FloatType>& sample2);
    FloatType ks_p_value(FloatType d, size_t n1, size_t n2);

    void compute_mass_function_stats(const std::vector<Halo>& halos,
                                     FloatType box_size,
                                     HaloStatistics& stats,
                                     bool use_adaptive_binning,
                                     int min_count_per_bin);
};

}

#endif
