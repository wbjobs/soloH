#include "modified_gravity.hpp"
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace halo_analysis {

ModifiedGravityInterface::ModifiedGravityInterface() {
    F_R_Parameters gr_params = {0.0, 0.0, "GR"};
    model_params_[GravityModel::GR] = gr_params;
    current_model_ = GravityModel::GR;
}

void ModifiedGravityInterface::register_model(GravityModel model, const F_R_Parameters& params) {
    model_params_[model] = params;
}

void ModifiedGravityInterface::set_current_model(GravityModel model) {
    current_model_ = model;
}

const F_R_Parameters& ModifiedGravityInterface::get_parameters(GravityModel model) const {
    auto it = model_params_.find(model);
    if (it == model_params_.end()) {
        throw std::runtime_error("Model parameters not registered");
    }
    return it->second;
}

FloatType ModifiedGravityInterface::compute_fifth_force_coupling(FloatType f_R, FloatType n) {
    if (std::abs(f_R) < 1e-15) return 0.0;
    return std::sqrt(1.0 / 3.0) * (1.0 + n) / std::sqrt(std::abs(f_R));
}

FloatType ModifiedGravityInterface::compute_screeing_scale(FloatType f_R, FloatType n, FloatType density) {
    if (std::abs(f_R) < 1e-15 || density <= 0) return 0.0;
    return std::pow(std::abs(f_R) * std::pow(density / RHO_CRIT, -1.0 - n), 1.0 / (2.0 + n));
}

FloatType ModifiedGravityInterface::compute_boost_factor(FloatType mass, FloatType redshift,
                                                          const F_R_Parameters& params) {
    if (std::abs(params.f_R0) < 1e-15) return 1.0;

    FloatType f_R_z = params.f_R0 * std::pow(1.0 + redshift, -params.n - 1.0);
    FloatType r_s = std::pow(3.0 * mass / (4.0 * M_PI * 200.0 * RHO_CRIT), 1.0/3.0);
    FloatType lambda_s = compute_screeing_scale(params.f_R0, params.n, 200.0 * RHO_CRIT);

    if (lambda_s <= 0) return 1.0;

    FloatType screening_ratio = r_s / lambda_s;
    FloatType beta = compute_fifth_force_coupling(f_R_z, params.n);
    FloatType enhancement = 2.0 * beta * beta / 3.0;

    if (screening_ratio > 1.0) {
        return 1.0 + enhancement * std::exp(-screening_ratio);
    } else {
        return 1.0 + enhancement * (1.0 - screening_ratio * screening_ratio);
    }
}

bool ModifiedGravityInterface::is_halo_chameleon_screened(const Halo& halo, const F_R_Parameters& params) {
    if (std::abs(params.f_R0) < 1e-15) return false;

    if (halo.mass <= 0 || halo.shape.axis_a <= 0) return false;

    FloatType r_vir = std::cbrt(3.0 * halo.mass / (4.0 * M_PI * 200.0 * RHO_CRIT));
    FloatType lambda_s = compute_screeing_scale(params.f_R0, params.n, 200.0 * RHO_CRIT);

    if (lambda_s <= 0) return true;

    FloatType screening_ratio = r_vir / lambda_s;
    return screening_ratio > 1.0;
}

void ModifiedGravityInterface::compute_mass_function_stats(const std::vector<Halo>& halos,
                                                           FloatType box_size,
                                                           HaloStatistics& stats,
                                                           bool use_adaptive_binning,
                                                           int min_count_per_bin) {
    if (halos.empty()) {
        stats.mass_bins = {};
        stats.mass_function = {};
        stats.mass_function_errors = {};
        return;
    }

    std::vector<FloatType> masses;
    masses.reserve(halos.size());
    for (const Halo& h : halos) {
        if (h.mass > 0) masses.push_back(h.mass);
    }
    if (masses.empty()) return;

    std::sort(masses.begin(), masses.end());

    if (use_adaptive_binning && min_count_per_bin > 0) {
        size_t n = masses.size();
        int n_bins = std::min(50, std::max(5, static_cast<int>(n / min_count_per_bin)));

        for (int i = 0; i < n_bins; ++i) {
            size_t start = (i * n) / n_bins;
            size_t end = ((i + 1) * n) / n_bins;
            if (end > n) end = n;
            if (end - start < static_cast<size_t>(min_count_per_bin)) {
                if (i == n_bins - 1 && start > 0) {
                    stats.mass_bins.back() = std::log10(masses.back());
                    size_t count = n - start;
                    FloatType bin_width = std::log10(masses.back()) - std::log10(masses[start]);
                    if (bin_width > 0) {
                        FloatType dn_dlogm = count / (bin_width * box_size * box_size * box_size);
                        stats.mass_function.back() = dn_dlogm;
                        stats.mass_function_errors.back() = std::sqrt(count) / (bin_width * box_size * box_size * box_size);
                    }
                }
                continue;
            }

            FloatType log_m_low = std::log10(masses[start]);
            FloatType log_m_high = std::log10(masses[end - 1]);
            size_t count = end - start;
            FloatType bin_width = log_m_high - log_m_low;

            stats.mass_bins.push_back(0.5 * (log_m_low + log_m_high));
            if (bin_width > 0) {
                FloatType dn_dlogm = count / (bin_width * box_size * box_size * box_size);
                stats.mass_function.push_back(dn_dlogm);
                stats.mass_function_errors.push_back(std::sqrt(count) / (bin_width * box_size * box_size * box_size));
            }
        }
    } else {
        FloatType log_min = std::log10(masses.front());
        FloatType log_max = std::log10(masses.back());
        int n_bins = 20;
        FloatType bin_width = (log_max - log_min) / n_bins;

        for (int i = 0; i < n_bins; ++i) {
            FloatType log_low = log_min + i * bin_width;
            FloatType log_high = log_low + bin_width;
            FloatType m_low = std::pow(10, log_low);
            FloatType m_high = std::pow(10, log_high);

            auto it_low = std::lower_bound(masses.begin(), masses.end(), m_low);
            auto it_high = std::upper_bound(masses.begin(), masses.end(), m_high);
            size_t count = std::distance(it_low, it_high);

            stats.mass_bins.push_back(log_low + 0.5 * bin_width);
            if (bin_width > 0) {
                FloatType dn_dlogm = count / (bin_width * box_size * box_size * box_size);
                stats.mass_function.push_back(dn_dlogm);
                stats.mass_function_errors.push_back(std::sqrt(count) / (bin_width * box_size * box_size * box_size));
            }
        }
    }
}

HaloStatistics ModifiedGravityInterface::compute_statistics(const std::vector<Halo>& halos,
                                                             FloatType box_size,
                                                             bool use_adaptive_binning,
                                                             int min_count_per_bin) {
    HaloStatistics stats;
    stats.num_halos = halos.size();

    if (halos.empty()) {
        stats.mass_mean = stats.mass_median = 0.0;
        stats.concentration_mean = stats.concentration_median = 0.0;
        stats.spin_mean = stats.spin_median = 0.0;
        stats.axis_ratio_mean_b_a = stats.axis_ratio_mean_c_a = 0.0;
        stats.triaxiality_mean = stats.ellipticity_mean = 0.0;
        return stats;
    }

    std::vector<FloatType> masses, spins, axis_b_a, axis_c_a, triaxiality, ellipticity;
    masses.reserve(halos.size());
    spins.reserve(halos.size());
    axis_b_a.reserve(halos.size());
    axis_c_a.reserve(halos.size());
    triaxiality.reserve(halos.size());
    ellipticity.reserve(halos.size());

    for (const Halo& h : halos) {
        if (h.mass > 0) masses.push_back(h.mass);
        if (h.spin_parameter > 0) spins.push_back(h.spin_parameter);
        if (h.shape.converged) {
            axis_b_a.push_back(h.shape.axis_ratio_b_a);
            axis_c_a.push_back(h.shape.axis_ratio_c_a);
            triaxiality.push_back(h.shape.triaxiality);
            ellipticity.push_back(h.shape.ellipticity);
        }
    }

    auto mean = [](const std::vector<FloatType>& v) {
        if (v.empty()) return 0.0;
        FloatType sum = 0.0;
        for (FloatType x : v) sum += x;
        return sum / v.size();
    };

    auto median = [](std::vector<FloatType> v) {
        if (v.empty()) return 0.0;
        std::sort(v.begin(), v.end());
        size_t n = v.size();
        if (n % 2 == 0) return 0.5 * (v[n/2 - 1] + v[n/2]);
        return v[n/2];
    };

    stats.mass_mean = mean(masses);
    stats.mass_median = median(masses);
    stats.spin_mean = mean(spins);
    stats.spin_median = median(spins);
    stats.axis_ratio_mean_b_a = mean(axis_b_a);
    stats.axis_ratio_mean_c_a = mean(axis_c_a);
    stats.triaxiality_mean = mean(triaxiality);
    stats.ellipticity_mean = mean(ellipticity);

    stats.concentration_mean = stats.concentration_median = 4.0;

    compute_mass_function_stats(halos, box_size, stats, use_adaptive_binning, min_count_per_bin);

    std::vector<FloatType> redshifts;
    for (const Halo& h : halos) {
        redshifts.push_back(h.redshift);
    }
    std::sort(redshifts.begin(), redshifts.end());
    if (!redshifts.empty()) {
        FloatType z_min = redshifts.front();
        FloatType z_max = redshifts.back();
        int n_z_bins = std::min(10, (int)redshifts.size() / 5);
        if (n_z_bins < 2) n_z_bins = 2;
        FloatType z_bin_width = (z_max - z_min) / n_z_bins;
        for (int i = 0; i < n_z_bins; ++i) {
            FloatType z_low = z_min + i * z_bin_width;
            FloatType z_high = z_low + z_bin_width;
            auto it_low = std::lower_bound(redshifts.begin(), redshifts.end(), z_low);
            auto it_high = std::upper_bound(redshifts.begin(), redshifts.end(), z_high);
            stats.redshift_bins.push_back(z_low + 0.5 * z_bin_width);
            stats.halo_abundance.push_back(std::distance(it_low, it_high));
        }
    }

    return stats;
}

FloatType ModifiedGravityInterface::kolmogorov_smirnov_statistic(const std::vector<FloatType>& sample1,
                                                                  const std::vector<FloatType>& sample2) {
    if (sample1.empty() || sample2.empty()) return 1.0;

    std::vector<FloatType> s1 = sample1;
    std::vector<FloatType> s2 = sample2;
    std::sort(s1.begin(), s1.end());
    std::sort(s2.begin(), s2.end());

    size_t n1 = s1.size();
    size_t n2 = s2.size();
    FloatType d = 0.0;
    size_t i1 = 0, i2 = 0;

    while (i1 < n1 && i2 < n2) {
        FloatType f1 = (FloatType)(i1 + 1) / n1;
        FloatType f2 = (FloatType)(i2 + 1) / n2;
        d = std::max(d, std::abs(f1 - f2));

        if (s1[i1] < s2[i2]) {
            ++i1;
        } else {
            ++i2;
        }
    }

    return d;
}

FloatType ModifiedGravityInterface::ks_p_value(FloatType d, size_t n1, size_t n2) {
    if (n1 == 0 || n2 == 0) return 0.0;
    FloatType en = std::sqrt((FloatType)n1 * n2 / (n1 + n2));
    FloatType lambda = (en + 0.12 + 0.11 / en) * d;
    return 2.0 * std::exp(-2.0 * lambda * lambda);
}

ModelComparison ModifiedGravityInterface::compare_models(const HaloStatistics& stats1,
                                                          const HaloStatistics& stats2,
                                                          const std::string& name1,
                                                          const std::string& name2) {
    ModelComparison comp;
    comp.model1_name = name1;
    comp.model2_name = name2;
    comp.mass_function_delta = 0.0;
    comp.concentration_delta = 0.0;
    comp.spin_delta = 0.0;
    comp.ellipticity_delta = 0.0;

    if (stats1.num_halos > 0 && stats2.num_halos > 0) {
        if (stats1.spin_mean > 0 && stats2.spin_mean > 0) {
            comp.spin_delta = (stats2.spin_mean - stats1.spin_mean) / stats1.spin_mean;
        }
        if (stats1.ellipticity_mean > 0 && stats2.ellipticity_mean > 0) {
            comp.ellipticity_delta = (stats2.ellipticity_mean - stats1.ellipticity_mean) / stats1.ellipticity_mean;
        }
        if (stats1.concentration_mean > 0 && stats2.concentration_mean > 0) {
            comp.concentration_delta = (stats2.concentration_mean - stats1.concentration_mean) / stats1.concentration_mean;
        }

        size_t n_bins = std::min(stats1.mass_function.size(), stats2.mass_function.size());
        comp.mass_function_ratio.reserve(n_bins);
        comp.mass_bin_centers.reserve(n_bins);

        for (size_t i = 0; i < n_bins; ++i) {
            if (stats1.mass_function[i] > 0) {
                comp.mass_function_ratio.push_back(stats2.mass_function[i] / stats1.mass_function[i]);
                comp.mass_bin_centers.push_back(stats1.mass_bins[i]);
                comp.mass_function_delta += std::abs(stats2.mass_function[i] - stats1.mass_function[i]) / stats1.mass_function[i];
            }
        }
        if (n_bins > 0) {
            comp.mass_function_delta /= n_bins;
        }
    }

    return comp;
}

}
