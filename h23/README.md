# NIST Randomness Tester - Go Implementation

A comprehensive Go command-line tool for testing the randomness of binary data using the NIST SP 800-22 statistical test suite and Dieharder tests. This tool implements 17 randomness tests with parallel computing support, detailed parameter configuration, auto-correction for sample size, and multiple output formats including interactive HTML visualization.

## Features

- **15 NIST Randomness Tests**:
  1. Frequency (Monobit) Test
  2. Frequency Test within a Block
  3. Runs Test
  4. Test for the Longest Run of Ones in a Block
  5. Binary Matrix Rank Test
  6. Discrete Fourier Transform (Spectral) Test
  7. Non-overlapping Template Matching Test
  8. Overlapping Template Matching Test
  9. Maurer's Universal Statistical Test
  10. Lempel-Ziv Compression Test (LZ77 sliding window)
  11. Linear Complexity Test
  12. Serial Test
  13. Approximate Entropy Test
  14. Cumulative Sums (Cusum) Test (forward + backward)
  15. Random Excursions Test

- **2 Dieharder Tests**:
  16. Birthday Spacing Test
  17. Overlapping Permutations Test

- **Parameter Auto-Correction**: Automatically adjusts test parameters based on sample size
- **Parallel Computation**: Multi-core support using goroutines for faster testing
- **Multiple Input Sources**:
  - Binary files
  - Bit strings
  - Custom RNG commands (execute external commands that output random bits)
- **Flexible Output**:
  - Human-readable text reports
  - JSON reports for programmatic processing
  - Interactive HTML reports with Plotly dynamic charts
- **Customizable Parameters**: Detailed configuration of all test parameters
- **Test Selection**: Run specific tests, NIST-only, or Dieharder-only tests as needed

## Installation

### Prerequisites
- Go 1.22 or higher

### Building from Source
```bash
go build -o randomness-tester.exe ./cmd/randomness-tester
```

Or using the build script:
```powershell
.\build.ps1
```

## Usage

### Basic Usage

```bash
# Test a binary file
randomness-tester.exe -file <path-to-binary-file>

# Test a bit string
randomness-tester.exe -bits "101101010011..."

# Test output from a custom RNG command
randomness-tester.exe -rng "my-rng-command --generate-bits"
```

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `-file` | Path to binary file to test | |
| `-bits` | Bit string to test (e.g., '10110101') | |
| `-rng` | Command to execute that outputs random bits to stdout | |
| `-num-bits` | Number of bits to read from RNG command (0 = read until EOF) | 10000000 |
| `-text` | Output file for human-readable text report | stdout |
| `-json` | Output file for JSON report | |
| `-tests` | Comma-separated list of tests to run | all tests |
| `-exclude` | Comma-separated list of tests to exclude | |
| `-parallel` | Number of parallel workers | number of CPU cores |
| `-alpha` | Significance level for pass/fail determination | 0.01 |
| `-config` | Path to JSON configuration file | |
| `-show-config` | Show default configuration and exit | |
| `-list-tests` | List all available tests and exit | |

### Test Names

Use these names with `-tests` and `-exclude` flags:

- `frequency` - Frequency (Monobit) Test
- `block-frequency` - Frequency Test within a Block
- `runs` - Runs Test
- `longest-run` - Test for the Longest Run of Ones in a Block
- `rank` - Binary Matrix Rank Test
- `dft` - Discrete Fourier Transform (Spectral) Test
- `non-overlapping-template` - Non-overlapping Template Matching Test
- `overlapping-template` - Overlapping Template Matching Test
- `universal` - Maurer's Universal Statistical Test
- `lz-compression` - Lempel-Ziv Compression Test
- `linear-complexity` - Linear Complexity Test
- `serial` - Serial Test
- `approximate-entropy` - Approximate Entropy Test
- `cumulative-sums` - Cumulative Sums (Cusum) Test
- `random-excursions` - Random Excursions Test

### Examples

#### 1. Run all tests on a binary file with text output
```bash
randomness-tester.exe -file random_data.bin -text report.txt
```

#### 2. Run specific tests with JSON output
```bash
randomness-tester.exe -file random_data.bin -tests "frequency,runs,dft" -json report.json
```

#### 3. Exclude slow tests and use parallel computation
```bash
randomness-tester.exe -file random_data.bin -exclude "lz-compression,linear-complexity" -parallel 8
```

#### 4. Test with custom significance level
```bash
randomness-tester.exe -file random_data.bin -alpha 0.05
```

#### 5. Use a custom RNG command
```bash
randomness-tester.exe -rng "openssl rand 1000000" -num-bits 8000000
```

#### 6. Test a bit string directly
```bash
randomness-tester.exe -bits "10110101001110101100"
```

#### 7. Use a custom configuration file
```bash
randomness-tester.exe -file random_data.bin -config sample-config.json
```

### Configuration File

The configuration file allows you to customize all test parameters. See `sample-config.json` for the default configuration.

```json
{
  "significance_level": 0.01,
  "block_frequency_block_size": 128,
  "runs_block_size": 10000,
  "longest_run_block_size": 10000,
  "rank_matrix_rows": 32,
  "rank_matrix_cols": 32,
  "non_overlapping_template_length": 9,
  "overlapping_template_length": 9,
  "overlapping_block_size": 1000000,
  "universal_L": 7,
  "universal_Q": 1280,
  "universal_K": 40,
  "lz_compression_block_size": 1000,
  "linear_complexity_block_size": 1000,
  "serial_block_size": 16,
  "approximate_entropy_block_size": 10,
  "cumulative_sum_mode": 0,
  "random_excursions_state": 1
}
```

### Test Requirements

Each test has minimum bit length requirements:

| Test | Minimum Bits |
|------|--------------|
| Frequency | 100 |
| Block Frequency | 100 |
| Runs | 100 |
| Longest Run | 128 |
| Rank | 38,912 (32×32×38) |
| DFT | 1,000 |
| Non-overlapping Template | 1,000,000 |
| Overlapping Template | 1,000,000 |
| Universal | 387,840 |
| LZ Compression | 1,000,000 |
| Linear Complexity | 1,000,000 |
| Serial | 1,000,000 |
| Approximate Entropy | 100 |
| Cumulative Sums | 100 |
| Random Excursions | 1,000,000 |

## Interpreting Results

- **P-value**: A value between 0 and 1 that represents the probability that a perfect random number generator would produce a sequence less random than the one tested.
- **Pass/Fail**: A test passes if P-value ≥ significance level (default 0.01).
- **Overall Result**: The overall result is PASSED only if all tests pass.

### Example Text Report

```
========================================
   NIST Randomness Test Suite Report
========================================

Timestamp:         2024-05-23T12:00:00Z
Input Type:        file
Input Source:      random_data.bin
Bit Length:        1000000 bits
Significance Level: 0.0100
Parallelism:       8 cores
Duration:          2.34 seconds

----------------------------------------
           Test Results
----------------------------------------

Test Name                      P-Value       Status    Details
------------------------------------------------------------------------
Frequency (Monobit) Test       0.543210      PASS      n=1000000, sum=...
Frequency Test within a Block  0.789012      PASS      n=1000000, M=128, ...
Runs Test                      0.345678      PASS      n=1000000, pi=0.50...
...

----------------------------------------
           Summary
----------------------------------------

Total Tests:   17
Passed:        17
Failed:        0
Overall:       PASSED
```

### Parameter Auto-Correction Example

```
      Parameter Validation & Corrections
----------------------------------------

⚠️  block-frequency [M]: block size 10000 gives only 10 blocks, recommended at least 10 blocks
   Current: 10000, Recommended: 128
⚠️  universal [L]: need at least 1000000 bits for L=16, got 387840
   Current: 16, Recommended: 7
✅ All other parameters validated successfully.
```

## Running Tests

```bash
# Run unit tests
go test -v ./...

# Run with coverage
go test -cover ./...

# Format code
go fmt ./...
```

## Project Structure

```
randomness-tester/
├── cmd/
│   └── randomness-tester/
│       └── main.go              # CLI entry point
├── internal/
│   ├── config/
│   │   └── config.go            # Test configuration
│   ├── rng/
│   │   └── command.go           # Custom RNG command support
│   ├── report/
│   │   └── report.go            # Report generation (text/JSON)
│   ├── tests/
│   │   ├── tests.go             # Test interface and registry
│   │   ├── runner.go            # Parallel test runner
│   │   ├── frequency.go         # Tests 1-5
│   │   ├── spectral.go          # Tests 6-10
│   │   ├── complex.go           # Tests 11-15
│   │   └── tests_test.go        # Unit tests
│   └── utils/
│       ├── math.go              # Statistical/math functions
│       ├── bitstream.go         # Bit stream handling
│       └── fft.go               # Fast Fourier Transform
├── go.mod
├── go.sum
├── Makefile
├── build.ps1                    # Windows build script
├── sample-config.json           # Sample configuration
└── README.md
```

## License

This project implements the NIST SP 800-22 statistical tests. The implementation is provided as-is for educational and testing purposes.
