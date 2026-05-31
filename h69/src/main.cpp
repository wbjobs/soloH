#include "hbsolver/types.h"
#include "hbsolver/fft.h"
#include "hbsolver/matrix.h"
#include "hbsolver/nonlinear.h"
#include "hbsolver/circuit.h"
#include "hbsolver/hbsolver.h"
#include "hbsolver/analysis.h"
#include "hbsolver/output.h"
#include "hbsolver/memory.h"
#include "hbsolver/loadpull.h"
#include "hbsolver/envelope.h"

#include <iostream>
#include <iomanip>
#include <string>
#include <cstdlib>
#include <memory>
#include <vector>
#include <sstream>
#include <functional>

using namespace hbsolver;

void printHelp(const std::string& programName) {
    std::cout << "Harmonic Balance Solver - C++ Command Line Tool" << std::endl;
    std::cout << "================================================" << std::endl;
    std::cout << std::endl;
    std::cout << "Usage: " << programName << " [options]" << std::endl;
    std::cout << std::endl;
    std::cout << "Nonlinear Device Models:" << std::endl;
    std::cout << "  --model polynomial <coeff1>,<coeff2>,..." << std::endl;
    std::cout << "  --model piecewise <v1>,<v2>,...;<i1>,<i2>,..." << std::endl;
    std::cout << "  --model angelov <vpk>,<ids0>,<vto>,<lambda>,<alpha>" << std::endl;
    std::cout << "  --model diode  (default polynomial diode)" << std::endl;
    std::cout << "  --model fet    (default Angelov FET)" << std::endl;
    std::cout << std::endl;
    std::cout << "Circuit Topology (Matching Networks):" << std::endl;
    std::cout << "  --input-lc <L>,<C>         Input LC section" << std::endl;
    std::cout << "  --input-cl <C>,<L>         Input CL section" << std::endl;
    std::cout << "  --input-pi <C1>,<L>,<C2>   Input Pi network" << std::endl;
    std::cout << "  --input-t <L1>,<C>,<L2>    Input T network" << std::endl;
    std::cout << "  --output-lc <L>,<C>        Output LC section" << std::endl;
    std::cout << "  --output-cl <C>,<L>        Output CL section" << std::endl;
    std::cout << "  --output-pi <C1>,<L>,<C2>  Output Pi network" << std::endl;
    std::cout << "  --output-t <L1>,<C>,<L2>   Output T network" << std::endl;
    std::cout << std::endl;
    std::cout << "Excitation:" << std::endl;
    std::cout << "  --tone <freq>,<amplitude>[,<phase>]" << std::endl;
    std::cout << "  --two-tone <f1>,<f2>,<amp1>,<amp2>[,<ph1>,<ph2>]" << std::endl;
    std::cout << "  --power-sweep <start_dBm>,<end_dBm>,<points>" << std::endl;
    std::cout << "  --freq-sweep <start_Hz>,<end_Hz>,<points>,<power_dBm>" << std::endl;
    std::cout << "  --hysteresis-sweep <start_dBm>,<end_dBm>,<points>[,<threshold>]" << std::endl;
    std::cout << "                            Detect and track hysteresis/bistability" << std::endl;
    std::cout << std::endl;
    std::cout << "Simulation Options:" << std::endl;
    std::cout << "  --harmonics <N>           Number of harmonics (default: 5)" << std::endl;
    std::cout << "  --samples <N>             Time samples (default: auto)" << std::endl;
    std::cout << "  --max-iter <N>            Max Newton iterations (default: 100)" << std::endl;
    std::cout << "  --tolerance <eps>         Convergence tolerance (default: 1e-8)" << std::endl;
    std::cout << "  --impedance <Z>           System impedance (default: 50)" << std::endl;
    std::cout << "  --pwl-smoothing <eps>     PWL model smoothing width (default: 1e-4)" << std::endl;
    std::cout << "  --anti-aliasing           Enable anti-aliasing filter" << std::endl;
    std::cout << "  --verbose                 Verbose output" << std::endl;
    std::cout << std::endl;
    std::cout << "Memory Effects:" << std::endl;
    std::cout << "  --nl-cap <Cj0>,<Vj>,<m>   Nonlinear capacitor (abrupt junction)" << std::endl;
    std::cout << "  --nl-ind <L0>,<alpha>,<Isat>  Nonlinear inductor (saturating)" << std::endl;
    std::cout << std::endl;
    std::cout << "Load/Source Pull Analysis:" << std::endl;
    std::cout << "  --load-pull <freq>,<power>  Run load pull analysis" << std::endl;
    std::cout << "  --source-pull <freq>,<power> Run source pull analysis" << std::endl;
    std::cout << "  --gamma-grid <mag>,<theta>,<r>  Gamma grid resolution" << std::endl;
    std::cout << "  --contours <p1>,<p2>,...  Generate power contours (dBm)" << std::endl;
    std::cout << std::endl;
    std::cout << "Envelope Simulation:" << std::endl;
    std::cout << "  --envelope                Run envelope simulation" << std::endl;
    std::cout << "  --modulation <type>       Modulation type: qpsk, qam16, qam64, ofdm, twotone" << std::endl;
    std::cout << "  --symbol-rate <rate>      Symbol rate (Hz, default: 1e6)" << std::endl;
    std::cout << "  --carrier <freq>          Carrier frequency (Hz, default: 1e9)" << std::endl;
    std::cout << "  --num-symbols <N>         Number of symbols (default: 1024)" << std::endl;
    std::cout << "  --rolloff <alpha>         RRC filter rolloff (default: 0.35)" << std::endl;
    std::cout << "  --oversampling <N>        Oversampling rate (default: 8)" << std::endl;
    std::cout << "  --peak-power <dBm>        Peak power (default: 0 dBm)" << std::endl;
    std::cout << "  --am-am                   Run AM-AM/AM-PM characterization" << std::endl;
    std::cout << std::endl;
    std::cout << "Output Options:" << std::endl;
    std::cout << "  --csv-spectrum <file>     Save spectrum to CSV" << std::endl;
    std::cout << "  --csv-time <file>         Save time domain to CSV" << std::endl;
    std::cout << "  --csv-sweep <file>        Save sweep results to CSV" << std::endl;
    std::cout << "  --csv-hysteresis <file>   Save hysteresis results to CSV" << std::endl;
    std::cout << "  --csv-loadpull <file>     Save load pull results to CSV" << std::endl;
    std::cout << "  --csv-contours <file>     Save contours to CSV" << std::endl;
    std::cout << "  --csv-envelope <file>     Save envelope to CSV" << std::endl;
    std::cout << "  --csv-amam <file>         Save AM-AM/AM-PM to CSV" << std::endl;
    std::cout << "  --plot-spectrum           Show ASCII spectrum plot" << std::endl;
    std::cout << "  --plot-time               Show ASCII time plot" << std::endl;
    std::cout << "  --plot-hysteresis         Show hysteresis plot" << std::endl;
    std::cout << "  --plot-smith              Show Smith chart for load pull" << std::endl;
    std::cout << "  --plot-envelope           Show envelope waveform" << std::endl;
    std::cout << "  --plot-amam               Show AM-AM/AM-PM plots" << std::endl;
    std::cout << std::endl;
    std::cout << "Examples:" << std::endl;
    std::cout << "  " << programName << " --model diode --tone 1e9,0.1 --plot-spectrum" << std::endl;
    std::cout << "  " << programName << " --model fet --two-tone 1e9,1.001e9,0.1,0.1 --harmonics 7" << std::endl;
    std::cout << "  " << programName << " --model polynomial 0,0.01,0.001 --power-sweep -20,20,11 --csv-sweep sweep.csv" << std::endl;
    std::cout << "  " << programName << " --model piecewise -1,-0.5,0,0.5,1;-0.02,-0.01,0,0.01,0.02 --hysteresis-sweep -30,30,21 --plot-hysteresis" << std::endl;
    std::cout << "  " << programName << " --model fet --nl-cap 1e-12,0.7,0.5 --nl-ind 1e-9,1.0,0.1 --tone 1e9,0.1" << std::endl;
    std::cout << "  " << programName << " --model fet --load-pull 1e9,10 --contours 15,20,25 --plot-smith --csv-loadpull lp.csv" << std::endl;
    std::cout << "  " << programName << " --model fet --envelope --modulation qpsk --symbol-rate 1e6 --peak-power 5 --plot-envelope" << std::endl;
    std::cout << "  " << programName << " --model fet --am-am -20,20,21 --csv-amam amam.csv --plot-amam" << std::endl;
}

RealVec parseDoubleList(const std::string& str, char separator = ',') {
    RealVec values;
    std::stringstream ss(str);
    std::string token;
    while (std::getline(ss, token, separator)) {
        try {
            values.push_back(std::stod(token));
        } catch (...) {
            std::cerr << "Warning: Invalid number '" << token << "'" << std::endl;
        }
    }
    return values;
}

std::pair<RealVec, RealVec> parseTwoDoubleLists(const std::string& str) {
    size_t sepPos = str.find(';');
    if (sepPos == std::string::npos) {
        return {parseDoubleList(str), RealVec()};
    }
    std::string first = str.substr(0, sepPos);
    std::string second = str.substr(sepPos + 1);
    return {parseDoubleList(first), parseDoubleList(second)};
}

double dBmToVoltage(double power_dBm, double impedance = 50.0) {
    double power_watts = std::pow(10.0, power_dBm / 10.0) / 1000.0;
    return std::sqrt(2.0 * impedance * power_watts);
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        printHelp(argv[0]);
        return 1;
    }

    HBConfig config;
    config.num_harmonics = 5;
    config.max_iterations = 100;
    config.tolerance = 1e-8;
    config.impedance = 50.0;
    config.verbose = false;

    std::unique_ptr<NonlinearDevice> device = nullptr;
    CircuitTopology topology;
    MatchingNetwork input_matching, output_matching;

    std::vector<Tone> tones;
    int excitationMode = 0;

    double sweepStart = 0, sweepEnd = 0;
    int sweepPoints = 0;
    double sweepPower = 0;
    double sweepFreq = 1e9;
    double sweepFreq2 = 0;
    bool twoToneSweep = false;

    std::string csvSpectrum, csvTime, csvSweep, csvHysteresis;
    std::string csvLoadPull, csvContours, csvEnvelope, csvAmAm;
    bool plotSpectrum = false, plotTime = false, plotHysteresis = false;
    bool plotSmith = false, plotEnvelope = false, plotAmAm = false;
    double pwlSmoothing = 1e-4;
    bool hysteresisMode = false;
    double hysteresisThreshold = 0.5;

    bool useNLCap = false, useNLInd = false;
    double nlCapCj0 = 1e-12, nlCapVj = 0.7, nlCapM = 0.5;
    double nlIndL0 = 1e-9, nlIndAlpha = 1.0, nlIndIsat = 0.1;

    bool loadPullMode = false, sourcePullMode = false;
    double loadPullFreq = 1e9, loadPullPower = 10.0;
    double gammaMax = 0.9;
    int gammaThetaPoints = 37, gammaMagPoints = 11;
    RealVec contourLevels;

    bool envelopeMode = false, amAmMode = false;
    ModulationType modType = ModulationType::QPSK;
    double symbolRate = 1e6, carrierFreq = 1e9;
    int numSymbols = 1024, oversampling = 8;
    double rolloff = 0.35, peakPower = 0.0;
    double amamStart = -20.0, amamEnd = 20.0;
    int amamPoints = 21;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];

        if (arg == "--help" || arg == "-h") {
            printHelp(argv[0]);
            return 0;
        } else if (arg == "--model" && i + 1 < argc) {
            std::string modelType = argv[++i];
            if (modelType == "polynomial" && i + 1 < argc) {
                RealVec coeffs = parseDoubleList(argv[++i]);
                device = NonlinearModelFactory::createPolynomial(coeffs);
            } else if (modelType == "piecewise" && i + 1 < argc) {
                auto [voltages, currents] = parseTwoDoubleLists(argv[++i]);
                device = NonlinearModelFactory::createPiecewiseLinear(voltages, currents);
            } else if (modelType == "angelov" && i + 1 < argc) {
                RealVec params = parseDoubleList(argv[++i]);
                if (params.size() >= 5) {
                    device = NonlinearModelFactory::createAngelov(params[0], params[1], params[2], params[3], params[4]);
                }
            } else if (modelType == "diode") {
                device = NonlinearModelFactory::createDefaultDiode();
            } else if (modelType == "fet") {
                device = NonlinearModelFactory::createDefaultFET();
            }
        } else if (arg == "--input-lc" && i + 1 < argc) {
            RealVec params = parseDoubleList(argv[++i]);
            if (params.size() >= 2) input_matching.buildLCSection(params[0], params[1]);
        } else if (arg == "--input-cl" && i + 1 < argc) {
            RealVec params = parseDoubleList(argv[++i]);
            if (params.size() >= 2) input_matching.buildCLSection(params[0], params[1]);
        } else if (arg == "--input-pi" && i + 1 < argc) {
            RealVec params = parseDoubleList(argv[++i]);
            if (params.size() >= 3) input_matching.buildPiNetwork(params[0], params[1], params[2]);
        } else if (arg == "--input-t" && i + 1 < argc) {
            RealVec params = parseDoubleList(argv[++i]);
            if (params.size() >= 3) input_matching.buildTNetwork(params[0], params[1], params[2]);
        } else if (arg == "--output-lc" && i + 1 < argc) {
            RealVec params = parseDoubleList(argv[++i]);
            if (params.size() >= 2) output_matching.buildLCSection(params[0], params[1]);
        } else if (arg == "--output-cl" && i + 1 < argc) {
            RealVec params = parseDoubleList(argv[++i]);
            if (params.size() >= 2) output_matching.buildCLSection(params[0], params[1]);
        } else if (arg == "--output-pi" && i + 1 < argc) {
            RealVec params = parseDoubleList(argv[++i]);
            if (params.size() >= 3) output_matching.buildPiNetwork(params[0], params[1], params[2]);
        } else if (arg == "--output-t" && i + 1 < argc) {
            RealVec params = parseDoubleList(argv[++i]);
            if (params.size() >= 3) output_matching.buildTNetwork(params[0], params[1], params[2]);
        } else if (arg == "--tone" && i + 1 < argc) {
            RealVec params = parseDoubleList(argv[++i]);
            if (params.size() >= 2) {
                double phase = params.size() >= 3 ? params[2] : 0.0;
                tones.push_back({params[0], params[1], phase});
                excitationMode = 1;
            }
        } else if (arg == "--two-tone" && i + 1 < argc) {
            RealVec params = parseDoubleList(argv[++i]);
            if (params.size() >= 4) {
                double ph1 = params.size() >= 5 ? params[4] : 0.0;
                double ph2 = params.size() >= 6 ? params[5] : 0.0;
                tones.push_back({params[0], params[2], ph1});
                tones.push_back({params[1], params[3], ph2});
                excitationMode = 2;
            }
        } else if (arg == "--power-sweep" && i + 1 < argc) {
            RealVec params = parseDoubleList(argv[++i]);
            if (params.size() >= 3) {
                sweepStart = params[0];
                sweepEnd = params[1];
                sweepPoints = static_cast<int>(params[2]);
                excitationMode = 3;
            }
        } else if (arg == "--freq-sweep" && i + 1 < argc) {
            RealVec params = parseDoubleList(argv[++i]);
            if (params.size() >= 4) {
                sweepStart = params[0];
                sweepEnd = params[1];
                sweepPoints = static_cast<int>(params[2]);
                sweepPower = params[3];
                excitationMode = 4;
            }
        } else if (arg == "--harmonics" && i + 1 < argc) {
            config.num_harmonics = std::stoi(argv[++i]);
        } else if (arg == "--samples" && i + 1 < argc) {
            config.num_time_samples = std::stoi(argv[++i]);
        } else if (arg == "--max-iter" && i + 1 < argc) {
            config.max_iterations = std::stoi(argv[++i]);
        } else if (arg == "--tolerance" && i + 1 < argc) {
            config.tolerance = std::stod(argv[++i]);
        } else if (arg == "--impedance" && i + 1 < argc) {
            config.impedance = std::stod(argv[++i]);
        } else if (arg == "--freq2" && i + 1 < argc) {
            sweepFreq2 = std::stod(argv[++i]);
            twoToneSweep = true;
        } else if (arg == "--hysteresis-sweep" && i + 1 < argc) {
            RealVec params = parseDoubleList(argv[++i]);
            if (params.size() >= 3) {
                sweepStart = params[0];
                sweepEnd = params[1];
                sweepPoints = static_cast<int>(params[2]);
                hysteresisThreshold = params.size() >= 4 ? params[3] : 0.5;
                hysteresisMode = true;
                excitationMode = 5;
            }
        } else if (arg == "--pwl-smoothing" && i + 1 < argc) {
            pwlSmoothing = std::stod(argv[++i]);
        } else if (arg == "--verbose") {
            config.verbose = true;
        } else if (arg == "--csv-spectrum" && i + 1 < argc) {
            csvSpectrum = argv[++i];
        } else if (arg == "--csv-time" && i + 1 < argc) {
            csvTime = argv[++i];
        } else if (arg == "--csv-sweep" && i + 1 < argc) {
            csvSweep = argv[++i];
        } else if (arg == "--csv-hysteresis" && i + 1 < argc) {
            csvHysteresis = argv[++i];
        } else if (arg == "--plot-spectrum") {
            plotSpectrum = true;
        } else if (arg == "--plot-time") {
            plotTime = true;
        } else if (arg == "--plot-hysteresis") {
            plotHysteresis = true;
        } else if (arg == "--nl-cap" && i + 1 < argc) {
            RealVec params = parseDoubleList(argv[++i]);
            if (params.size() >= 3) {
                nlCapCj0 = params[0];
                nlCapVj = params[1];
                nlCapM = params[2];
                useNLCap = true;
            }
        } else if (arg == "--nl-ind" && i + 1 < argc) {
            RealVec params = parseDoubleList(argv[++i]);
            if (params.size() >= 3) {
                nlIndL0 = params[0];
                nlIndAlpha = params[1];
                nlIndIsat = params[2];
                useNLInd = true;
            }
        } else if (arg == "--load-pull" && i + 1 < argc) {
            RealVec params = parseDoubleList(argv[++i]);
            if (params.size() >= 2) {
                loadPullFreq = params[0];
                loadPullPower = params[1];
                loadPullMode = true;
            }
        } else if (arg == "--source-pull" && i + 1 < argc) {
            RealVec params = parseDoubleList(argv[++i]);
            if (params.size() >= 2) {
                loadPullFreq = params[0];
                loadPullPower = params[1];
                sourcePullMode = true;
            }
        } else if (arg == "--gamma-grid" && i + 1 < argc) {
            RealVec params = parseDoubleList(argv[++i]);
            if (params.size() >= 3) {
                gammaMax = params[0];
                gammaThetaPoints = static_cast<int>(params[1]);
                gammaMagPoints = static_cast<int>(params[2]);
            }
        } else if (arg == "--contours" && i + 1 < argc) {
            contourLevels = parseDoubleList(argv[++i]);
        } else if (arg == "--envelope") {
            envelopeMode = true;
        } else if (arg == "--modulation" && i + 1 < argc) {
            std::string type = argv[++i];
            if (type == "qpsk") modType = ModulationType::QPSK;
            else if (type == "qam16") modType = ModulationType::QAM16;
            else if (type == "qam64") modType = ModulationType::QAM64;
            else if (type == "ofdm") modType = ModulationType::OFDM;
            else if (type == "twotone") modType = ModulationType::TwoTone;
            else if (type == "cw") modType = ModulationType::CW;
        } else if (arg == "--symbol-rate" && i + 1 < argc) {
            symbolRate = std::stod(argv[++i]);
        } else if (arg == "--carrier" && i + 1 < argc) {
            carrierFreq = std::stod(argv[++i]);
        } else if (arg == "--num-symbols" && i + 1 < argc) {
            numSymbols = std::stoi(argv[++i]);
        } else if (arg == "--rolloff" && i + 1 < argc) {
            rolloff = std::stod(argv[++i]);
        } else if (arg == "--oversampling" && i + 1 < argc) {
            oversampling = std::stoi(argv[++i]);
        } else if (arg == "--peak-power" && i + 1 < argc) {
            peakPower = std::stod(argv[++i]);
        } else if (arg == "--am-am" && i + 1 < argc) {
            RealVec params = parseDoubleList(argv[++i]);
            if (params.size() >= 3) {
                amamStart = params[0];
                amamEnd = params[1];
                amamPoints = static_cast<int>(params[2]);
                amAmMode = true;
            }
        } else if (arg == "--csv-loadpull" && i + 1 < argc) {
            csvLoadPull = argv[++i];
        } else if (arg == "--csv-contours" && i + 1 < argc) {
            csvContours = argv[++i];
        } else if (arg == "--csv-envelope" && i + 1 < argc) {
            csvEnvelope = argv[++i];
        } else if (arg == "--csv-amam" && i + 1 < argc) {
            csvAmAm = argv[++i];
        } else if (arg == "--plot-smith") {
            plotSmith = true;
        } else if (arg == "--plot-envelope") {
            plotEnvelope = true;
        } else if (arg == "--plot-amam") {
            plotAmAm = true;
        } else {
            std::cerr << "Unknown option: " << arg << std::endl;
        }
    }

    if (!device) {
        device = NonlinearModelFactory::createDefaultDiode();
        std::cout << "Using default diode model..." << std::endl;
    }

    PiecewiseLinearModel* pwl = dynamic_cast<PiecewiseLinearModel*>(device.get());
    if (pwl) {
        pwl->setSmoothingWidth(pwlSmoothing);
        std::cout << "PWL smoothing width: " << pwlSmoothing << std::endl;
    }

    topology.setInputMatching(input_matching);
    topology.setOutputMatching(output_matching);

    HarmonicBalanceSolver solver;
    solver.setConfig(config);
    solver.setNonlinearDevice(std::move(device));
    solver.setCircuitTopology(topology);

    if (useNLCap || useNLInd) {
        auto memory = std::make_shared<MemoryEffect>();
        if (useNLCap) {
            memory->setAbruptJunctionCapacitor(nlCapCj0, nlCapVj, nlCapM);
        }
        if (useNLInd) {
            memory->setSaturatingInductor(nlIndL0, nlIndAlpha, nlIndIsat);
        }
        solver.setMemoryEffect(memory);
        OutputWriter::printMemoryEffectSummary(memory->getConfig());
    }

    std::cout << "================================================" << std::endl;
    std::cout << "Harmonic Balance Simulation" << std::endl;
    std::cout << "================================================" << std::endl;

    if (excitationMode == 1 || excitationMode == 2) {
        solver.setTones(tones);

        std::cout << "Excitation: " << tones.size() << " tone(s)" << std::endl;
        for (size_t i = 0; i < tones.size(); ++i) {
            std::cout << "  Tone " << i + 1 << ": " << tones[i].frequency / 1e6
                      << " MHz, " << dBmFromVoltage(tones[i].amplitude, config.impedance) << " dBm" << std::endl;
        }

        HBSolution solution = solver.solve();
        PowerMetrics metrics = SpectrumAnalyzer::extractPowerMetrics(solution, tones, config.impedance);

        OutputWriter::printSolutionSummary(solution);
        OutputWriter::printPowerMetrics(metrics);
        OutputWriter::printSpectrumTable(solution);

        if (plotSpectrum) {
            std::cout << OutputWriter::generateAsciiSpectrum(solution, 80, 0, -80, 20);
        }
        if (plotTime) {
            std::cout << OutputWriter::generateAsciiTimeDomain(solution, 80, 20);
        }

        if (!csvSpectrum.empty()) {
            if (OutputWriter::writeSpectrumCSV(solution, csvSpectrum)) {
                std::cout << "Spectrum saved to: " << csvSpectrum << std::endl;
            } else {
                std::cerr << "Failed to write spectrum CSV" << std::endl;
            }
        }
        if (!csvTime.empty()) {
            if (OutputWriter::writeTimeDomainCSV(solution, csvTime)) {
                std::cout << "Time domain data saved to: " << csvTime << std::endl;
            } else {
                std::cerr << "Failed to write time domain CSV" << std::endl;
            }
        }

        if (tones.size() == 1) {
            double f0 = tones[0].frequency;
            std::function<HBSolution(double)> solveFunc = [&](double pin) -> HBSolution {
                double amp = dBmToVoltage(pin, config.impedance);
                solver.setSingleTone(f0, amp);
                return solver.solve();
            };
            double p1dB = SpectrumAnalyzer::computeP1dB(solveFunc, -20, 30, 26);
            std::cout << "1dB Compression Point: " << std::fixed << std::setprecision(2) << p1dB << " dBm (input)" << std::endl;
        }

        if (tones.size() >= 2) {
            double f1 = tones[0].frequency;
            double f2 = tones[1].frequency;
            double amp0 = tones[0].amplitude;
            double pin0 = dBmFromVoltage(amp0, config.impedance);
            std::function<HBSolution(double)> solveFunc = [&](double pin) -> HBSolution {
                double amp = dBmToVoltage(pin, config.impedance);
                solver.setTwoTone(f1, f2, amp, amp);
                return solver.solve();
            };
            double ip3 = SpectrumAnalyzer::computeIP3(solveFunc, pin0 - 10, pin0, 6);
            std::cout << "Third Order Intercept (IP3): " << std::fixed << std::setprecision(2) << ip3 << " dBm (input)" << std::endl;
        }

    } else if (excitationMode == 3) {
        if (!tones.empty()) {
            sweepFreq = tones[0].frequency;
            if (tones.size() >= 2) sweepFreq2 = tones[1].frequency;
        }

        SweepAnalysis sweep(solver);
        auto results = sweep.powerSweep(sweepFreq, sweepStart, sweepEnd, sweepPoints,
                                        (twoToneSweep || sweepFreq2 > 0), sweepFreq2);

        std::cout << "Power Sweep: " << sweepStart << " to " << sweepEnd << " dBm, "
                  << sweepPoints << " points" << std::endl;

        std::cout << OutputWriter::generateSweepPlot(results, "power", 80, 20);

        if (!csvSweep.empty()) {
            if (OutputWriter::writeSweepCSV(results, csvSweep, "power")) {
                std::cout << "Sweep results saved to: " << csvSweep << std::endl;
            }
        }

        if (!results.empty() && plotSpectrum) {
            size_t midIdx = results.size() / 2;
            std::cout << "\nSpectrum at midpoint (" << results[midIdx].parameter << " dBm):" << std::endl;
            std::cout << OutputWriter::generateAsciiSpectrum(results[midIdx].solution, 80, 0, -80, 20);
        }

    } else if (excitationMode == 4) {
        SweepAnalysis sweep(solver);
        auto results = sweep.frequencySweep(sweepPower, sweepStart, sweepEnd, sweepPoints,
                                            twoToneSweep, sweepFreq2 > 0 ? sweepFreq2 : 1e6);

        std::cout << "Frequency Sweep: " << sweepStart / 1e6 << " to " << sweepEnd / 1e6
                  << " MHz, " << sweepPoints << " points, " << sweepPower << " dBm" << std::endl;

        std::cout << OutputWriter::generateSweepPlot(results, "frequency", 80, 20);

        if (!csvSweep.empty()) {
            if (OutputWriter::writeSweepCSV(results, csvSweep, "frequency")) {
                std::cout << "Sweep results saved to: " << csvSweep << std::endl;
            }
        }
    } else if (excitationMode == 5) {
        if (!tones.empty()) {
            sweepFreq = tones[0].frequency;
            if (tones.size() >= 2) sweepFreq2 = tones[1].frequency;
        }

        SweepAnalysis sweep(solver);
        auto hysteresis = sweep.powerSweepWithHysteresis(
            sweepFreq, sweepStart, sweepEnd, sweepPoints,
            hysteresisThreshold, (twoToneSweep || sweepFreq2 > 0), sweepFreq2);

        OutputWriter::printHysteresisSummary(hysteresis);

        if (plotHysteresis) {
            std::cout << OutputWriter::generateHysteresisPlot(hysteresis, 80, 25);
        }

        if (!csvHysteresis.empty()) {
            if (OutputWriter::writeHysteresisCSV(hysteresis, csvHysteresis)) {
                std::cout << "Hysteresis results saved to: " << csvHysteresis << std::endl;
            }
        }

        if (plotSpectrum && !hysteresis.forward_sweep.empty()) {
            size_t midIdx = hysteresis.forward_sweep.size() / 2;
            std::cout << "\nSpectrum at forward sweep midpoint ("
                      << hysteresis.forward_sweep[midIdx].parameter << " dBm):" << std::endl;
            std::cout << OutputWriter::generateAsciiSpectrum(
                hysteresis.forward_sweep[midIdx].solution, 80, 0, -80, 20);
        }
    } else if (loadPullMode) {
        LoadPullAnalysis lp(solver);
        lp.setFrequency(loadPullFreq);
        lp.setInputPower(loadPullPower);
        lp.setGammaRange(gammaMax, gammaThetaPoints, gammaMagPoints);

        std::cout << "Load Pull Analysis: " << loadPullFreq / 1e9 << " GHz, "
                  << loadPullPower << " dBm input" << std::endl;
        std::cout << "Gamma grid: " << gammaMagPoints << " x " << gammaThetaPoints
                  << ", max |Gamma| = " << gammaMax << std::endl;

        auto results = lp.runLoadPull();
        auto optimum = lp.findOptimumLoad();

        std::vector<ImpedanceContour> contours;
        if (!contourLevels.empty()) {
            for (double level : contourLevels) {
                auto contour = lp.computePowerContour(level, 0.5);
                if (!contour.points.empty()) {
                    contours.push_back(contour);
                }
            }
        }

        OutputWriter::printLoadPullSummary(optimum, contours);
        std::cout << OutputWriter::generateLoadPullTable(results, 10);

        if (plotSmith) {
            if (!contours.empty()) {
                std::cout << OutputWriter::generateSmithChartWithContours(results, contours, 40);
            } else {
                std::cout << OutputWriter::generateSmithChart(results, 40);
            }
        }

        if (!csvLoadPull.empty()) {
            if (OutputWriter::writeLoadPullCSV(results, csvLoadPull)) {
                std::cout << "Load pull results saved to: " << csvLoadPull << std::endl;
            }
        }
        if (!csvContours.empty() && !contours.empty()) {
            if (OutputWriter::writeContoursCSV(contours, csvContours)) {
                std::cout << "Contours saved to: " << csvContours << std::endl;
            }
        }
    } else if (sourcePullMode) {
        LoadPullAnalysis sp(solver);
        sp.setFrequency(loadPullFreq);
        sp.setInputPower(loadPullPower);
        sp.setGammaRange(gammaMax, gammaThetaPoints, gammaMagPoints);

        std::cout << "Source Pull Analysis: " << loadPullFreq / 1e9 << " GHz, "
                  << loadPullPower << " dBm input" << std::endl;

        auto results = sp.runSourcePull();
        auto optimum = sp.findOptimumSource();

        OutputWriter::printSourcePullSummary(optimum);
        std::cout << OutputWriter::generateSourcePullTable(results, 10);

        if (plotSmith) {
            std::cout << OutputWriter::generateSmithChart(
                std::vector<LoadPullResult>(), 40);
        }

        if (!csvLoadPull.empty()) {
            if (OutputWriter::writeSourcePullCSV(results, csvLoadPull)) {
                std::cout << "Source pull results saved to: " << csvLoadPull << std::endl;
            }
        }
    } else if (envelopeMode) {
        EnvelopeSimulator env_sim(solver);
        ModulationConfig mod_config;
        mod_config.type = modType;
        mod_config.carrier_freq = carrierFreq;
        mod_config.symbol_rate = symbolRate;
        mod_config.num_symbols = numSymbols;
        mod_config.rolloff = rolloff;
        mod_config.oversampling = oversampling;
        mod_config.peak_power_dBm = peakPower;

        env_sim.setModulationConfig(mod_config);

        std::cout << "Envelope Simulation: ";
        if (modType == ModulationType::QPSK) std::cout << "QPSK";
        else if (modType == ModulationType::QAM16) std::cout << "16QAM";
        else if (modType == ModulationType::QAM64) std::cout << "64QAM";
        else if (modType == ModulationType::OFDM) std::cout << "OFDM";
        else if (modType == ModulationType::TwoTone) std::cout << "Two-Tone";
        std::cout << ", " << symbolRate / 1e6 << " Msym/s, "
                  << carrierFreq / 1e9 << " GHz carrier" << std::endl;

        EnvelopeSolution env_sol = env_sim.runEnvelopeSimulation();
        OutputWriter::printEnvelopeSummary(env_sol);

        if (plotEnvelope) {
            std::cout << OutputWriter::generateEnvelopeWaveform(env_sol, 80, 20);
        }

        if (!csvEnvelope.empty()) {
            if (OutputWriter::writeEnvelopeCSV(env_sol, csvEnvelope)) {
                std::cout << "Envelope data saved to: " << csvEnvelope << std::endl;
            }
        }
    } else if (amAmMode) {
        AMAMPAnalysis amam(solver);

        std::cout << "AM-AM/AM-PM Characterization: " << amamStart
                  << " to " << amamEnd << " dBm, " << amamPoints << " points" << std::endl;

        auto characteristics = amam.runAmAmPm(amamStart, amamEnd, amamPoints, loadPullFreq);

        OutputWriter::printAmAmPmSummary(characteristics);

        if (plotAmAm) {
            std::cout << OutputWriter::generateAmAmPlot(characteristics, 60, 25);
            std::cout << OutputWriter::generateAmPmPlot(characteristics, 60, 25);
        }

        if (!csvAmAm.empty()) {
            if (OutputWriter::writeAmAmPmCSV(characteristics, csvAmAm)) {
                std::cout << "AM-AM/AM-PM data saved to: " << csvAmAm << std::endl;
            }
        }
    } else {
        std::cout << "No excitation specified. Running demo simulation..." << std::endl;
        solver.setTwoTone(1e9, 1.001e9, dBmToVoltage(0, config.impedance), dBmToVoltage(0, config.impedance));

        HBSolution solution = solver.solve();
        PowerMetrics metrics = SpectrumAnalyzer::extractPowerMetrics(solution, solver.getTones(), config.impedance);

        OutputWriter::printSolutionSummary(solution);
        OutputWriter::printPowerMetrics(metrics);
        std::cout << OutputWriter::generateAsciiSpectrum(solution, 80, 0, -80, 20);
    }

    std::cout << "================================================" << std::endl;
    std::cout << "Simulation complete." << std::endl;
    std::cout << "================================================" << std::endl;

    return 0;
}
