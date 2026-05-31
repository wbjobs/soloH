#include <iostream>
#include <string>
#include <vector>
#include <memory>
#include <stdexcept>
#include <cstdlib>
#include <ctime>

#include "sequence.h"
#include "pwm.h"
#include "statistics.h"
#include "prior_knowledge.h"
#include "rna_structure.h"
#include "em_algorithm.h"
#include "gibbs_sampler.h"
#include "tcm_model.h"
#include "output_formatter.h"

struct Options {
    std::string input_file;
    std::string output_prefix = "motif_results";
    std::string algorithm = "EM";
    std::string model = "ZOOPS";
    int min_width = 6;
    int max_width = 20;
    int width = 12;
    int width2 = 12;
    int tcm_min_spacing = 0;
    int tcm_max_spacing = 100;
    int tcm_preferred_spacing = 20;
    double tcm_spacing_sigma = 10.0;
    int max_iterations = 100;
    int n_starts = 5;
    int seed = 42;
    double tolerance = 1e-6;
    double lambda = 0.5;
    double edge_penalty = 0.3;
    bool use_colors = true;
    bool generate_meme = true;
    int weblogo_height = 12;
    int num_threads = 1;
    std::string prior_bed_file = "";
    std::string prior_bed_file2 = "";
    double prior_strength = 1.0;
    double prior_weight = 0.5;
    bool use_rna_structure = false;
    double structure_weight = 0.5;
    bool allow_gu_pairing = true;
    double stem_bonus = 2.0;
    double loop_penalty = 0.5;
};

void print_usage(const char* prog_name) {
    std::cout << "\n=== Motif Discovery Tool ===\n\n";
    std::cout << "Usage: " << prog_name << " [options]\n\n";
    std::cout << "Required:\n";
    std::cout << "  -i, --input <file>      Input FASTA file\n\n";
    std::cout << "Algorithm Options:\n";
    std::cout << "  -a, --algorithm <alg>   Algorithm: EM (default) or Gibbs\n";
    std::cout << "  -m, --model <model>     Model: ZOOPS (default) or TCM\n";
    std::cout << "  -w, --width <int>       Motif width (6-20, default: 12)\n";
    std::cout << "  --width2 <int>          Second motif width for TCM (default: 12)\n";
    std::cout << "  --min-width <int>       Minimum motif width (default: 6)\n";
    std::cout << "  --max-width <int>       Maximum motif width (default: 20)\n";
    std::cout << "  --iter <int>            Max iterations (default: 100)\n";
    std::cout << "  --starts <int>          Number of restarts (default: 5)\n";
    std::cout << "  --seed <int>            Random seed (default: 42)\n";
    std::cout << "  --tolerance <double>    Convergence tolerance (default: 1e-6)\n";
    std::cout << "  --lambda <double>       Initial lambda (default: 0.5)\n";
    std::cout << "  --edge-penalty <double> Edge position penalty (0-1, default: 0.3)\n\n";
    std::cout << "Parallel Processing:\n";
    std::cout << "  -t, --threads <int>     Number of OpenMP threads (default: 1)\n\n";
    std::cout << "Prior Knowledge Options:\n";
    std::cout << "  --prior-bed <file>      BED file with known TF binding sites\n";
    std::cout << "  --prior-bed2 <file>     BED file for second motif (TCM only)\n";
    std::cout << "  --prior-strength <d>    Prior knowledge strength (default: 1.0)\n";
    std::cout << "  --prior-weight <d>      Weight for prior vs data (0-1, default: 0.5)\n\n";
    std::cout << "RNA Structure Options:\n";
    std::cout << "  --rna-structure         Enable RNA secondary structure constraints\n";
    std::cout << "  --structure-weight <d>  Weight for structure constraints (default: 0.5)\n";
    std::cout << "  --no-gu-pairing         Disable G-U base pairing\n";
    std::cout << "  --stem-bonus <d>        Bonus for stem region motifs (default: 2.0)\n";
    std::cout << "  --loop-penalty <d>      Penalty for loop region motifs (default: 0.5)\n\n";
    std::cout << "TCM Spacing Options:\n";
    std::cout << "  --tcm-min-spacing <int>  Minimum motif spacing (default: 0)\n";
    std::cout << "  --tcm-max-spacing <int>  Maximum motif spacing (default: 100)\n";
    std::cout << "  --tcm-preferred <int>    Preferred motif spacing (default: 20)\n";
    std::cout << "  --tcm-sigma <double>     Spacing distribution sigma (default: 10.0)\n\n";
    std::cout << "Output Options:\n";
    std::cout << "  -o, --output <prefix>   Output file prefix (default: motif_results)\n";
    std::cout << "  --no-color              Disable colored output\n";
    std::cout << "  --no-meme               Do not generate MEME output\n";
    std::cout << "  --weblogo-height <int>  Height of weblogo (default: 12)\n\n";
    std::cout << "Examples:\n";
    std::cout << "  " << prog_name << " -i sequences.fasta -t 4\n";
    std::cout << "  " << prog_name << " -i sequences.fasta -a Gibbs -w 8 --prior-bed known_sites.bed\n";
    std::cout << "  " << prog_name << " -i rna_sequences.fasta --rna-structure -w 8\n";
    std::cout << "  " << prog_name << " -i sequences.fasta -m TCM -w 10 --width2 8 --prior-bed tf1.bed --prior-bed2 tf2.bed\n";
    std::cout << "  " << prog_name << " -i sequences.fasta -m TCM -w 8 --width2 6 --tcm-preferred 15 --tcm-sigma 5\n";
    std::cout << "\n";
}

Options parse_options(int argc, char* argv[]) {
    Options opts;

    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        
        if (arg == "-h" || arg == "--help") {
            print_usage(argv[0]);
            std::exit(0);
        }
        else if (arg == "-i" || arg == "--input") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.input_file = argv[++i];
        }
        else if (arg == "-o" || arg == "--output") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.output_prefix = argv[++i];
        }
        else if (arg == "-a" || arg == "--algorithm") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.algorithm = argv[++i];
        }
        else if (arg == "-m" || arg == "--model") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.model = argv[++i];
        }
        else if (arg == "-w" || arg == "--width") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.width = std::stoi(argv[++i]);
        }
        else if (arg == "--width2") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.width2 = std::stoi(argv[++i]);
        }
        else if (arg == "--min-width") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.min_width = std::stoi(argv[++i]);
        }
        else if (arg == "--max-width") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.max_width = std::stoi(argv[++i]);
        }
        else if (arg == "--iter") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.max_iterations = std::stoi(argv[++i]);
        }
        else if (arg == "--starts") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.n_starts = std::stoi(argv[++i]);
        }
        else if (arg == "--seed") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.seed = std::stoi(argv[++i]);
        }
        else if (arg == "--tolerance") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.tolerance = std::stod(argv[++i]);
        }
        else if (arg == "--lambda") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.lambda = std::stod(argv[++i]);
        }
        else if (arg == "--edge-penalty") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.edge_penalty = std::stod(argv[++i]);
            if (opts.edge_penalty < 0 || opts.edge_penalty > 1) {
                throw std::runtime_error("Edge penalty must be between 0 and 1");
            }
        }
        else if (arg == "--tcm-min-spacing") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.tcm_min_spacing = std::stoi(argv[++i]);
        }
        else if (arg == "--tcm-max-spacing") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.tcm_max_spacing = std::stoi(argv[++i]);
        }
        else if (arg == "--tcm-preferred") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.tcm_preferred_spacing = std::stoi(argv[++i]);
        }
        else if (arg == "--tcm-sigma") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.tcm_spacing_sigma = std::stod(argv[++i]);
        }
        else if (arg == "-t" || arg == "--threads") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.num_threads = std::stoi(argv[++i]);
            if (opts.num_threads < 1) opts.num_threads = 1;
        }
        else if (arg == "--prior-bed") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.prior_bed_file = argv[++i];
        }
        else if (arg == "--prior-bed2") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.prior_bed_file2 = argv[++i];
        }
        else if (arg == "--prior-strength") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.prior_strength = std::stod(argv[++i]);
        }
        else if (arg == "--prior-weight") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.prior_weight = std::stod(argv[++i]);
            if (opts.prior_weight < 0 || opts.prior_weight > 1) {
                throw std::runtime_error("Prior weight must be between 0 and 1");
            }
        }
        else if (arg == "--rna-structure") {
            opts.use_rna_structure = true;
        }
        else if (arg == "--structure-weight") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.structure_weight = std::stod(argv[++i]);
        }
        else if (arg == "--no-gu-pairing") {
            opts.allow_gu_pairing = false;
        }
        else if (arg == "--stem-bonus") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.stem_bonus = std::stod(argv[++i]);
        }
        else if (arg == "--loop-penalty") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.loop_penalty = std::stod(argv[++i]);
        }
        else if (arg == "--no-color") {
            opts.use_colors = false;
        }
        else if (arg == "--no-meme") {
            opts.generate_meme = false;
        }
        else if (arg == "--weblogo-height") {
            if (i + 1 >= argc) throw std::runtime_error("Missing argument for " + arg);
            opts.weblogo_height = std::stoi(argv[++i]);
        }
        else {
            throw std::runtime_error("Unknown option: " + arg);
        }
    }

    if (opts.input_file.empty()) {
        throw std::runtime_error("Input file is required. Use -h for help.");
    }

    if (opts.width < opts.min_width || opts.width > opts.max_width) {
        throw std::runtime_error("Motif width must be between " + 
            std::to_string(opts.min_width) + " and " + std::to_string(opts.max_width));
    }

    if (opts.algorithm != "EM" && opts.algorithm != "Gibbs") {
        throw std::runtime_error("Algorithm must be 'EM' or 'Gibbs'");
    }

    if (opts.model != "ZOOPS" && opts.model != "TCM") {
        throw std::runtime_error("Model must be 'ZOOPS' or 'TCM'");
    }

    return opts;
}

int main(int argc, char* argv[]) {
    try {
        Options opts = parse_options(argc, argv);
        
        std::srand(opts.seed);
        
        std::cout << "\n=== Motif Discovery Tool ===\n\n";
        std::cout << "Input file: " << opts.input_file << "\n";
        std::cout << "Algorithm: " << opts.algorithm << "\n";
        std::cout << "Model: " << opts.model << "\n";
        std::cout << "Motif width: " << opts.width << "\n";
        if (opts.model == "TCM") {
            std::cout << "Second motif width: " << opts.width2 << "\n";
        }
        std::cout << "Random seed: " << opts.seed << "\n\n";

        std::cout << "Reading sequences...\n";
        auto sequences = FastaParser::parse(opts.input_file);
        std::cout << "Loaded " << sequences.size() << " sequences\n\n";

        if (sequences.empty()) {
            std::cerr << "Error: No sequences found in input file\n";
            return 1;
        }

        BackgroundModel background;
        background.estimate(sequences);
        std::cout << "Background model:\n";
        std::cout << "  A: " << background.frequencies[0] << "\n";
        std::cout << "  C: " << background.frequencies[1] << "\n";
        std::cout << "  G: " << background.frequencies[2] << "\n";
        std::cout << "  T: " << background.frequencies[3] << "\n";
        std::cout << "  GC content: " << background.gc_content << "\n";
        std::cout << "Threads: " << opts.num_threads << "\n\n";

        PriorKnowledge prior1, prior2;
        bool has_prior1 = false, has_prior2 = false;

        if (!opts.prior_bed_file.empty()) {
            std::cout << "Loading prior knowledge: " << opts.prior_bed_file << "\n";
            prior1.load_bed_file(opts.prior_bed_file, "experiment");
            has_prior1 = true;
            std::cout << "  Loaded " << prior1.num_sites() << " prior sites\n\n";
        }

        if (!opts.prior_bed_file2.empty()) {
            std::cout << "Loading prior knowledge 2: " << opts.prior_bed_file2 << "\n";
            prior2.load_bed_file(opts.prior_bed_file2, "experiment");
            has_prior2 = true;
            std::cout << "  Loaded " << prior2.num_sites() << " prior sites\n\n";
        }

        std::vector<RnaStructure> rna_structures;
        if (opts.use_rna_structure) {
            std::cout << "Predicting RNA secondary structures...\n";
            RnaStructurePredictor::Options rna_opts;
            rna_opts.allow_gu_pairing = opts.allow_gu_pairing;
            rna_opts.stem_bonus = opts.stem_bonus;
            rna_opts.loop_penalty = opts.loop_penalty;
            rna_opts.structure_weight = opts.structure_weight;
            rna_structures = RnaStructurePredictor::predict_all(sequences, rna_opts);
            std::cout << "  Predicted structures for " << rna_structures.size() << " sequences\n\n";
        }

        std::cout << "Running motif discovery...\n\n";

        if (opts.model == "ZOOPS") {
            MotifResult result;
            
            if (opts.algorithm == "EM") {
                EMAlgorithm::Options em_opts;
                em_opts.width = opts.width;
                em_opts.min_width = opts.min_width;
                em_opts.max_width = opts.max_width;
                em_opts.max_iterations = opts.max_iterations;
                em_opts.tolerance = opts.tolerance;
                em_opts.lambda = opts.lambda;
                em_opts.edge_penalty = opts.edge_penalty;
                em_opts.n_starts = opts.n_starts;
                em_opts.seed = opts.seed;
                em_opts.num_threads = opts.num_threads;
                em_opts.use_prior_knowledge = has_prior1;
                em_opts.use_rna_structure = opts.use_rna_structure;
                em_opts.prior_options.prior_strength = opts.prior_strength;
                em_opts.prior_weight = opts.prior_weight;
                em_opts.structure_weight = opts.structure_weight;
                em_opts.rna_options.allow_gu_pairing = opts.allow_gu_pairing;
                em_opts.rna_options.stem_bonus = opts.stem_bonus;
                em_opts.rna_options.loop_penalty = opts.loop_penalty;
                
                result = EMAlgorithm::run_zoops(sequences, background, em_opts,
                    has_prior1 ? &prior1 : nullptr,
                    opts.use_rna_structure ? &rna_structures : nullptr);
            } else {
                GibbsSampler::Options gibbs_opts;
                gibbs_opts.width = opts.width;
                gibbs_opts.min_width = opts.min_width;
                gibbs_opts.max_width = opts.max_width;
                gibbs_opts.iterations = opts.max_iterations * 5;
                gibbs_opts.burn_in = opts.max_iterations;
                gibbs_opts.n_starts = opts.n_starts;
                gibbs_opts.lambda = opts.lambda;
                gibbs_opts.edge_penalty = opts.edge_penalty;
                gibbs_opts.seed = opts.seed;
                gibbs_opts.num_threads = opts.num_threads;
                gibbs_opts.use_prior_knowledge = has_prior1;
                gibbs_opts.use_rna_structure = opts.use_rna_structure;
                gibbs_opts.prior_options.prior_strength = opts.prior_strength;
                gibbs_opts.prior_weight = opts.prior_weight;
                gibbs_opts.structure_weight = opts.structure_weight;
                gibbs_opts.rna_options.allow_gu_pairing = opts.allow_gu_pairing;
                gibbs_opts.rna_options.stem_bonus = opts.stem_bonus;
                gibbs_opts.rna_options.loop_penalty = opts.loop_penalty;
                
                result = GibbsSampler::run(sequences, background, gibbs_opts,
                    has_prior1 ? &prior1 : nullptr,
                    opts.use_rna_structure ? &rna_structures : nullptr);
            }

            std::cout << OutputFormatter::format_result_summary(result, sequences, 1);

            std::cout << "Sequence Logo:\n";
            if (opts.use_colors) {
                std::cout << OutputFormatter::generate_weblogo(result.pwm, background, opts.weblogo_height);
            } else {
                std::cout << OutputFormatter::generate_weblogo_plain(result.pwm, background, opts.weblogo_height);
            }

            if (opts.generate_meme) {
                std::string meme_file = opts.output_prefix + ".meme";
                std::vector<MotifResult> results = {result};
                OutputFormatter::write_meme_file(meme_file, results, background, argv[0]);
                std::cout << "MEME output written to: " << meme_file << "\n";
            }

        } else if (opts.model == "TCM") {
            TCMModel::Options tcm_opts;
            tcm_opts.width1 = opts.width;
            tcm_opts.width2 = opts.width2;
            tcm_opts.min_spacing = opts.tcm_min_spacing;
            tcm_opts.max_spacing = opts.tcm_max_spacing;
            tcm_opts.preferred_spacing = opts.tcm_preferred_spacing;
            tcm_opts.spacing_sigma = opts.tcm_spacing_sigma;
            tcm_opts.max_iterations = opts.max_iterations;
            tcm_opts.tolerance = opts.tolerance;
            tcm_opts.seed = opts.seed;
            tcm_opts.n_starts = opts.n_starts;
            tcm_opts.num_threads = opts.num_threads;
            tcm_opts.edge_penalty = opts.edge_penalty;
            tcm_opts.use_prior_knowledge = has_prior1 || has_prior2;
            tcm_opts.use_rna_structure = opts.use_rna_structure;
            tcm_opts.prior_options.prior_strength = opts.prior_strength;
            tcm_opts.prior_weight = opts.prior_weight;
            tcm_opts.structure_weight = opts.structure_weight;
            tcm_opts.rna_options.allow_gu_pairing = opts.allow_gu_pairing;
            tcm_opts.rna_options.stem_bonus = opts.stem_bonus;
            tcm_opts.rna_options.loop_penalty = opts.loop_penalty;
            
            TCMResult tcm_result = TCMModel::run(sequences, background, tcm_opts,
                has_prior1 ? &prior1 : nullptr,
                has_prior2 ? &prior2 : nullptr,
                opts.use_rna_structure ? &rna_structures : nullptr);
            
            std::cout << OutputFormatter::format_tcm_summary(tcm_result, sequences);

            std::cout << "\n=== Motif 1 Sequence Logo ===\n";
            if (opts.use_colors) {
                std::cout << OutputFormatter::generate_weblogo(tcm_result.motif1.pwm, background, opts.weblogo_height);
            } else {
                std::cout << OutputFormatter::generate_weblogo_plain(tcm_result.motif1.pwm, background, opts.weblogo_height);
            }

            std::cout << "\n=== Motif 2 Sequence Logo ===\n";
            if (opts.use_colors) {
                std::cout << OutputFormatter::generate_weblogo(tcm_result.motif2.pwm, background, opts.weblogo_height);
            } else {
                std::cout << OutputFormatter::generate_weblogo_plain(tcm_result.motif2.pwm, background, opts.weblogo_height);
            }

            if (opts.generate_meme) {
                std::string meme_file = opts.output_prefix + ".meme";
                std::vector<MotifResult> results = {tcm_result.motif1, tcm_result.motif2};
                OutputFormatter::write_meme_file(meme_file, results, background, argv[0]);
                std::cout << "MEME output written to: " << meme_file << "\n";
            }
        }

        std::cout << "\n=== Analysis Complete ===\n\n";
        return 0;

    } catch (const std::exception& e) {
        std::cerr << "\nError: " << e.what() << "\n";
        std::cerr << "Use -h for help.\n\n";
        return 1;
    }
}
