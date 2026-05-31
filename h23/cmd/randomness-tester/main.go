package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io/ioutil"
	"os"
	"strings"
	"time"

	"randomness-tester/internal/config"
	"randomness-tester/internal/report"
	"randomness-tester/internal/rng"
	"randomness-tester/internal/tests"
	"randomness-tester/internal/utils"
)

func main() {
	var (
		inputFile       string
		bitString       string
		rngCommand      string
		outputText      string
		outputJSON      string
		outputHTML      string
		runTests        string
		excludeTests    string
		parallelism     int
		numBits         int
		showConfig      bool
		listTests       bool
		cfgFile         string
		alpha           float64
		useDieharder    bool
		useNISTOnly     bool
		autoCorrect     bool
		showCorrections bool
		validateOnly    bool
	)

	flag.StringVar(&inputFile, "file", "", "Binary file to test")
	flag.StringVar(&bitString, "bits", "", "Bit string to test (e.g., '10110101')")
	flag.StringVar(&rngCommand, "rng", "", "Command to execute that outputs random bits to stdout")
	flag.StringVar(&outputText, "text", "", "Output file for human-readable text report")
	flag.StringVar(&outputJSON, "json", "", "Output file for JSON report")
	flag.StringVar(&outputHTML, "html", "", "Output file for interactive HTML report with Plotly charts")
	flag.StringVar(&runTests, "tests", "", "Comma-separated list of tests to run (default: all tests)")
	flag.StringVar(&excludeTests, "exclude", "", "Comma-separated list of tests to exclude")
	flag.IntVar(&parallelism, "parallel", 0, "Number of parallel workers (default: number of CPU cores)")
	flag.IntVar(&numBits, "num-bits", 0, "Number of bits to read from RNG command (default: read until EOF)")
	flag.BoolVar(&showConfig, "show-config", false, "Show default configuration and exit")
	flag.BoolVar(&listTests, "list-tests", false, "List all available tests and exit")
	flag.StringVar(&cfgFile, "config", "", "Path to JSON configuration file")
	flag.Float64Var(&alpha, "alpha", 0.01, "Significance level (default: 0.01)")
	flag.BoolVar(&useDieharder, "dieharder", false, "Run only Dieharder tests (birthday-spacing, overlapping-permutations)")
	flag.BoolVar(&useNISTOnly, "nist-only", false, "Run only NIST SP 800-22 tests (exclude Dieharder)")
	flag.BoolVar(&autoCorrect, "auto-correct", true, "Automatically correct test parameters based on sample size")
	flag.BoolVar(&showCorrections, "show-corrections", false, "Show parameter validation and recommendations")
	flag.BoolVar(&validateOnly, "validate-only", false, "Only validate parameters, do not run tests")

	flag.Parse()

	if showConfig {
		printDefaultConfig()
		return
	}

	if listTests {
		printAvailableTests()
		return
	}

	if showCorrections {
		printCorrectionInfo()
		return
	}

	if inputFile == "" && bitString == "" && rngCommand == "" {
		fmt.Fprintln(os.Stderr, "Error: Must specify one of -file, -bits, or -rng")
		fmt.Fprintln(os.Stderr, "\nUsage:")
		flag.PrintDefaults()
		os.Exit(1)
	}

	cfg := config.DefaultConfig()
	correctionCfg := config.DefaultCorrectionConfig()

	if cfgFile != "" {
		if err := loadConfig(cfgFile, cfg); err != nil {
			fmt.Fprintf(os.Stderr, "Error loading config: %v\n", err)
			os.Exit(1)
		}
	}

	if alpha != 0.01 {
		cfg.SignificanceLevel = alpha
	}

	var bits []int
	var inputType string
	var inputSource string
	var err error

	switch {
	case inputFile != "":
		inputType = "file"
		inputSource = inputFile
		bits, err = readBitsFromFile(inputFile)
	case bitString != "":
		inputType = "bitstring"
		inputSource = fmt.Sprintf("\"%s...\"", bitString[:min(40, len(bitString))])
		bits, err = utils.ParseBitString(bitString)
	case rngCommand != "":
		inputType = "rng"
		inputSource = rngCommand
		bits, err = readBitsFromRNG(rngCommand, numBits)
	}

	if err != nil {
		fmt.Fprintf(os.Stderr, "Error reading input: %v\n", err)
		os.Exit(1)
	}

	if len(bits) == 0 {
		fmt.Fprintln(os.Stderr, "Error: No bits read from input")
		os.Exit(1)
	}

	fmt.Printf("Input: %d bits from %s\n", len(bits), inputType)

	var corrections []config.ParameterRecommendation
	if autoCorrect {
		fmt.Print("Validating and auto-correcting parameters...")
		corrections = config.ValidateTestParameters(cfg, len(bits))
		oldCfg := *cfg
		cfg = config.AutoCorrectConfig(cfg, len(bits))
		correctionCfg.AutoTuneParameters = true
		if oldCfg != *cfg {
			fmt.Println(" applied corrections.")
		} else {
			fmt.Println(" no corrections needed.")
		}
	} else {
		corrections = config.ValidateTestParameters(cfg, len(bits))
	}

	if validateOnly {
		fmt.Println("\nParameter Validation Results:")
		fmt.Println("-----------------------------")
		hasIssues := false
		for _, c := range corrections {
			if !c.Validated && c.Reason != "" {
				fmt.Printf("⚠️  %s [%s]: %s\n", c.TestName, c.ParameterName, c.Reason)
				if c.Recommended > 0 && c.CurrentValue != c.Recommended {
					fmt.Printf("   Current: %d, Recommended: %d\n", c.CurrentValue, c.Recommended)
				}
				hasIssues = true
			}
		}
		if !hasIssues {
			fmt.Println("✅ All parameters validated successfully.")
		}
		os.Exit(0)
	}

	testsToRun := selectTests(runTests, excludeTests, useDieharder, useNISTOnly)
	if len(testsToRun) == 0 {
		fmt.Fprintln(os.Stderr, "Error: No tests selected to run")
		os.Exit(1)
	}

	runner := tests.NewTestRunner()
	if parallelism > 0 {
		runner.Parallelism = parallelism
	}

	fmt.Printf("\nRunning %d randomness tests on %d bits...\n", len(testsToRun), len(bits))
	fmt.Printf("Using %d parallel workers\n\n", runner.Parallelism)

	startTime := time.Now()
	results := runner.RunTests(bits, cfg, testsToRun)
	duration := time.Since(startTime)

	passed, failed := tests.SummarizeResults(results, cfg)
	overallPassed := failed == 0

	fullReport := &report.FullReport{
		Timestamp:         time.Now(),
		InputType:         inputType,
		InputSource:       inputSource,
		BitLength:         len(bits),
		SignificanceLevel: cfg.SignificanceLevel,
		Config:            cfg,
		CorrectionConfig:  correctionCfg,
		Corrections:       corrections,
		Results:           results,
		Passed:            passed,
		Failed:            failed,
		OverallPassed:     overallPassed,
		Parallelism:       runner.Parallelism,
		Duration:          duration,
	}

	if outputText != "" {
		if err := report.SaveTextReport(fullReport, outputText); err != nil {
			fmt.Fprintf(os.Stderr, "Error saving text report: %v\n", err)
		} else {
			fmt.Printf("Text report saved to: %s\n", outputText)
		}
	}

	if outputJSON != "" {
		if err := report.SaveJSONReport(fullReport, outputJSON); err != nil {
			fmt.Fprintf(os.Stderr, "Error saving JSON report: %v\n", err)
		} else {
			fmt.Printf("JSON report saved to: %s\n", outputJSON)
		}
	}

	if outputHTML != "" {
		visualData := &report.VisualReportData{
			Report:      fullReport,
			Corrections: corrections,
		}
		if err := report.SaveHTMLReport(visualData, outputHTML); err != nil {
			fmt.Fprintf(os.Stderr, "Error saving HTML report: %v\n", err)
		} else {
			fmt.Printf("HTML report saved to: %s\n", outputHTML)
		}
	}

	if outputText == "" && outputJSON == "" && outputHTML == "" {
		if err := report.GenerateTextReport(fullReport, os.Stdout); err != nil {
			fmt.Fprintf(os.Stderr, "Error generating report: %v\n", err)
		}
	}

	if overallPassed {
		fmt.Println("\nOverall result: PASSED")
		os.Exit(0)
	} else {
		fmt.Println("\nOverall result: FAILED")
		os.Exit(1)
	}
}

func readBitsFromFile(path string) ([]int, error) {
	source, err := utils.NewFileBitSource(path)
	if err != nil {
		return nil, err
	}
	defer source.Close()
	return utils.ReadAllBits(source)
}

func readBitsFromRNG(command string, maxBits int) ([]int, error) {
	crng, err := rng.NewCommandRNG(command)
	if err != nil {
		return nil, err
	}

	if err := crng.Start(); err != nil {
		return nil, err
	}
	defer crng.Stop()

	if maxBits <= 0 {
		maxBits = 10000000
	}

	return crng.ReadAllBits(maxBits)
}

func loadConfig(path string, cfg *config.TestConfig) error {
	data, err := ioutil.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(data, cfg)
}

func selectTests(runList, excludeList string, dieharderOnly, nistOnly bool) []tests.Test {
	var allTests []tests.Test

	if dieharderOnly {
		allTests = tests.DieharderTests()
	} else if nistOnly {
		allTests = tests.NISTTests()
	} else {
		allTests = tests.AllTests()
	}

	if runList == "" && excludeList == "" {
		return allTests
	}

	runNames := make(map[string]bool)
	if runList != "" {
		for _, name := range strings.Split(runList, ",") {
			runNames[strings.TrimSpace(name)] = true
		}
	}

	excludeNames := make(map[string]bool)
	if excludeList != "" {
		for _, name := range strings.Split(excludeList, ",") {
			excludeNames[strings.TrimSpace(name)] = true
		}
	}

	selected := make([]tests.Test, 0)
	for _, t := range allTests {
		if excludeNames[t.Name()] {
			continue
		}
		if runList == "" || runNames[t.Name()] {
			selected = append(selected, t)
		}
	}

	return selected
}

func printDefaultConfig() {
	cfg := config.DefaultConfig()
	data, _ := json.MarshalIndent(cfg, "", "  ")
	fmt.Println("Default configuration:")
	fmt.Println(string(data))

	fmt.Println("\nDefault correction configuration:")
	corrCfg := config.DefaultCorrectionConfig()
	corrData, _ := json.MarshalIndent(corrCfg, "", "  ")
	fmt.Println(string(corrData))
}

func printAvailableTests() {
	fmt.Println("NIST SP 800-22 Tests (15):")
	fmt.Println("----------------------------------------")
	for _, t := range tests.NISTTests() {
		fmt.Printf("  %-25s - %s\n", t.Name(), t.DisplayName())
	}

	fmt.Println("\nDieharder Tests (2):")
	fmt.Println("----------------------------------------")
	for _, t := range tests.DieharderTests() {
		fmt.Printf("  %-25s - %s\n", t.Name(), t.DisplayName())
	}

	fmt.Println("\nTotal: 17 tests available")
	fmt.Println("\nOptions:")
	fmt.Println("  Use -nist-only to run only NIST tests")
	fmt.Println("  Use -dieharder to run only Dieharder tests")
	fmt.Println("  Use -tests to run specific tests (comma-separated)")
	fmt.Println("  Use -exclude to exclude specific tests")
}

func printCorrectionInfo() {
	fmt.Println("Parameter Auto-Correction System")
	fmt.Println("=================================")
	fmt.Println("\nThe system automatically validates and corrects test parameters")
	fmt.Println("based on the available sample size (number of bits).")
	fmt.Println("\nAuto-corrected parameters:")
	fmt.Println("  - Block frequency block size")
	fmt.Println("  - Longest run block size")
	fmt.Println("  - Universal test L, Q, K parameters")
	fmt.Println("  - Serial test block size")
	fmt.Println("  - Approximate entropy block size")
	fmt.Println("  - Linear complexity block size")
	fmt.Println("\nUsage:")
	fmt.Println("  -auto-correct=true   Enable auto-correction (default)")
	fmt.Println("  -auto-correct=false  Disable auto-correction")
	fmt.Println("  -validate-only       Only validate parameters, don't run tests")
	fmt.Println("  -show-corrections    Show this help message")
	fmt.Println("\nValidation checks:")
	fmt.Println("  - Minimum sequence length requirements")
	fmt.Println("  - Optimal block sizes based on sample size")
	fmt.Println("  - Template length constraints")
	fmt.Println("  - Chi-square test assumptions")
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
