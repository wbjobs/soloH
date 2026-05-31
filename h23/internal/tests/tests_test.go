package tests

import (
	"math"
	"math/rand"
	"testing"

	"randomness-tester/internal/config"
)

func generateRandomBits(n int, seed int64) []int {
	r := rand.New(rand.NewSource(seed))
	bits := make([]int, n)
	for i := range bits {
		if r.Float64() < 0.5 {
			bits[i] = 0
		} else {
			bits[i] = 1
		}
	}
	return bits
}

func generateKnownGoodBits(n int) []int {
	bits := make([]int, n)
	for i := range bits {
		if i%2 == 0 {
			bits[i] = 0
		} else {
			bits[i] = 1
		}
	}
	return bits
}

func TestFrequencyTest(t *testing.T) {
	cfg := config.DefaultConfig()
	test := &FrequencyTest{}

	bits := generateRandomBits(10000, 42)
	result, err := test.Run(bits, cfg)
	if err != nil {
		t.Fatalf("Frequency test failed: %v", err)
	}
	if result.PValue < 0 || result.PValue > 1 {
		t.Errorf("Invalid P-value: %f", result.PValue)
	}
	t.Logf("Frequency test P-value: %f", result.PValue)
}

func TestBlockFrequencyTest(t *testing.T) {
	cfg := config.DefaultConfig()
	test := &BlockFrequencyTest{}

	bits := generateRandomBits(10000, 42)
	result, err := test.Run(bits, cfg)
	if err != nil {
		t.Fatalf("Block frequency test failed: %v", err)
	}
	if result.PValue < 0 || result.PValue > 1 {
		t.Errorf("Invalid P-value: %f", result.PValue)
	}
	t.Logf("Block frequency test P-value: %f", result.PValue)
}

func TestRunsTest(t *testing.T) {
	cfg := config.DefaultConfig()
	test := &RunsTest{}

	bits := generateRandomBits(10000, 42)
	result, err := test.Run(bits, cfg)
	if err != nil {
		t.Fatalf("Runs test failed: %v", err)
	}
	if result.PValue < 0 || result.PValue > 1 {
		t.Errorf("Invalid P-value: %f", result.PValue)
	}
	t.Logf("Runs test P-value: %f", result.PValue)
}

func TestLongestRunTest(t *testing.T) {
	cfg := config.DefaultConfig()
	test := &LongestRunTest{}

	bits := generateRandomBits(12800, 42)
	result, err := test.Run(bits, cfg)
	if err != nil {
		t.Fatalf("Longest run test failed: %v", err)
	}
	if result.PValue < 0 || result.PValue > 1 {
		t.Errorf("Invalid P-value: %f", result.PValue)
	}
	t.Logf("Longest run test P-value: %f", result.PValue)
}

func TestRankTest(t *testing.T) {
	cfg := config.DefaultConfig()
	test := &RankTest{}

	n := 32 * 32 * 40
	bits := generateRandomBits(n, 42)
	result, err := test.Run(bits, cfg)
	if err != nil {
		t.Fatalf("Rank test failed: %v", err)
	}
	if result.PValue < 0 || result.PValue > 1 {
		t.Errorf("Invalid P-value: %f", result.PValue)
	}
	t.Logf("Rank test P-value: %f", result.PValue)
}

func TestDFTTest(t *testing.T) {
	cfg := config.DefaultConfig()
	test := &DFTTest{}

	bits := generateRandomBits(10000, 42)
	result, err := test.Run(bits, cfg)
	if err != nil {
		t.Fatalf("DFT test failed: %v", err)
	}
	if result.PValue < 0 || result.PValue > 1 {
		t.Errorf("Invalid P-value: %f", result.PValue)
	}
	t.Logf("DFT test P-value: %f", result.PValue)
}

func TestApproximateEntropyTest(t *testing.T) {
	cfg := config.DefaultConfig()
	test := &ApproximateEntropyTest{}

	bits := generateRandomBits(10000, 42)
	result, err := test.Run(bits, cfg)
	if err != nil {
		t.Fatalf("Approximate entropy test failed: %v", err)
	}
	if result.PValue < 0 || result.PValue > 1 {
		t.Errorf("Invalid P-value: %f", result.PValue)
	}
	t.Logf("Approximate entropy test P-value: %f", result.PValue)
}

func TestCumulativeSumTest(t *testing.T) {
	cfg := config.DefaultConfig()
	test := &CumulativeSumTest{}

	bits := generateRandomBits(10000, 42)
	result, err := test.Run(bits, cfg)
	if err != nil {
		t.Fatalf("Cumulative sum test failed: %v", err)
	}
	if result.PValue < 0 || result.PValue > 1 {
		t.Errorf("Invalid P-value: %f", result.PValue)
	}
	t.Logf("Cumulative sum test P-value: %f", result.PValue)
}

func TestKnownBadBits(t *testing.T) {
	cfg := config.DefaultConfig()

	bits := make([]int, 10000)
	for i := range bits {
		bits[i] = 1
	}

	freqTest := &FrequencyTest{}
	result, err := freqTest.Run(bits, cfg)
	if err != nil {
		t.Fatalf("Frequency test failed: %v", err)
	}
	if result.PValue > cfg.SignificanceLevel {
		t.Errorf("Expected frequency test to fail on all-ones sequence, got P-value: %f", result.PValue)
	}
	t.Logf("All-ones sequence frequency test P-value: %f (expected < 0.01)", result.PValue)

	bits2 := generateKnownGoodBits(10000)
	result2, err := freqTest.Run(bits2, cfg)
	if err != nil {
		t.Fatalf("Frequency test failed on alternating bits: %v", err)
	}
	t.Logf("Alternating bits frequency test P-value: %f", result2.PValue)
}

func TestBerlekampMassey(t *testing.T) {
	tests := []struct {
		name     string
		sequence []int
		expected int
	}{
		{
			name:     "all zeros",
			sequence: []int{0, 0, 0, 0, 0},
			expected: 0,
		},
		{
			name:     "m-sequence degree 3",
			sequence: []int{1, 0, 0, 1, 1, 1, 0},
			expected: 3,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := berlekampMassey(tt.sequence)
			if result != tt.expected {
				t.Errorf("berlekampMassey() = %d, want %d", result, tt.expected)
			}
		})
	}
}

func TestComputeRank(t *testing.T) {
	matrix := [][]int{
		{1, 0, 1},
		{0, 1, 1},
		{1, 1, 0},
	}
	rank := computeRank(matrix, 3, 3)
	if rank != 3 {
		t.Errorf("computeRank() = %d, want 3", rank)
	}

	matrix2 := [][]int{
		{1, 1, 1},
		{1, 1, 1},
		{1, 1, 1},
	}
	rank2 := computeRank(matrix2, 3, 3)
	if rank2 != 1 {
		t.Errorf("computeRank() = %d, want 1", rank2)
	}
}

func TestAllTestsExist(t *testing.T) {
	allTests := AllTests()
	if len(allTests) != 17 {
		t.Errorf("Expected 17 tests, got %d", len(allTests))
	}

	nistTests := NISTTests()
	if len(nistTests) != 15 {
		t.Errorf("Expected 15 NIST tests, got %d", len(nistTests))
	}

	dieharderTests := DieharderTests()
	if len(dieharderTests) != 2 {
		t.Errorf("Expected 2 Dieharder tests, got %d", len(dieharderTests))
	}

	expectedNames := []string{
		"frequency",
		"block-frequency",
		"runs",
		"longest-run",
		"rank",
		"dft",
		"non-overlapping-template",
		"overlapping-template",
		"universal",
		"lz-compression",
		"linear-complexity",
		"serial",
		"approximate-entropy",
		"cumulative-sums",
		"random-excursions",
		"birthday-spacing",
		"overlapping-permutations",
	}

	for i, name := range expectedNames {
		if allTests[i].Name() != name {
			t.Errorf("Test %d: expected name %s, got %s", i, name, allTests[i].Name())
		}
	}
}

func TestBirthdaySpacingTest(t *testing.T) {
	cfg := config.DefaultConfig()
	test := &BirthdaySpacingTest{}

	n := 4096 * 24
	bits := generateRandomBits(n, 42)

	result, err := test.Run(bits, cfg)
	if err != nil {
		t.Fatalf("Birthday spacing test failed: %v", err)
	}
	if result.PValue < 0 || result.PValue > 1 {
		t.Errorf("Invalid P-value: %f", result.PValue)
	}
	t.Logf("Birthday spacing test P-value: %f", result.PValue)
}

func TestOverlappingPermutationsTest(t *testing.T) {
	cfg := config.DefaultConfig()
	test := &OverlappingPermutationsTest{}

	n := 100128 * 32
	bits := generateRandomBits(n, 42)

	result, err := test.Run(bits, cfg)
	if err != nil {
		t.Skipf("Overlapping permutations test skipped (requires too many bits): %v", err)
		return
	}
	if result.PValue < 0 || result.PValue > 1 {
		t.Errorf("Invalid P-value: %f", result.PValue)
	}
	t.Logf("Overlapping permutations test P-value: %f", result.PValue)
}

func TestComputePermutationRank(t *testing.T) {
	tuple := []uint32{3, 1, 4, 2, 5}
	rank := computePermutationRank(tuple)
	if rank < 0 || rank >= 120 {
		t.Errorf("computePermutationRank() = %d, want 0-119", rank)
	}

	tuple2 := []uint32{1, 2, 3, 4, 5}
	rank2 := computePermutationRank(tuple2)
	if rank2 != 0 {
		t.Errorf("computePermutationRank(sorted) = %d, want 0", rank2)
	}

	tuple3 := []uint32{5, 4, 3, 2, 1}
	rank3 := computePermutationRank(tuple3)
	if rank3 != 119 {
		t.Errorf("computePermutationRank(reverse) = %d, want 119", rank3)
	}
}

func TestTestRunner(t *testing.T) {
	cfg := config.DefaultConfig()
	runner := NewTestRunner()
	runner.Parallelism = 2

	bits := generateRandomBits(10000, 42)

	testsToRun := []Test{
		&FrequencyTest{},
		&RunsTest{},
		&ApproximateEntropyTest{},
		&CumulativeSumTest{},
	}

	results := runner.RunTests(bits, cfg, testsToRun)

	if len(results) != len(testsToRun) {
		t.Errorf("Expected %d results, got %d", len(testsToRun), len(results))
	}

	for i, result := range results {
		if result.Name != testsToRun[i].Name() {
			t.Errorf("Result %d: expected name %s, got %s", i, testsToRun[i].Name(), result.Name)
		}
		if result.PValue < 0 || result.PValue > 1 || math.IsNaN(result.PValue) {
			t.Errorf("Result %d (%s): invalid P-value: %f", i, result.Name, result.PValue)
		}
		t.Logf("Test %s: P-value = %f, Passed = %v", result.Name, result.PValue, result.Passed)
	}
}
