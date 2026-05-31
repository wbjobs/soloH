package tests

import (
	"fmt"
	"math"
	"sort"

	"randomness-tester/internal/config"
	"randomness-tester/internal/utils"
)

type BirthdaySpacingTest struct{}

func (t *BirthdaySpacingTest) Name() string        { return "birthday-spacing" }
func (t *BirthdaySpacingTest) DisplayName() string { return "Dieharder Birthday Spacing Test" }

func (t *BirthdaySpacingTest) Run(bits []int, cfg *config.TestConfig) (*TestResult, error) {
	n := len(bits)

	wordBits := 24
	numSamples := 4096
	lambda := 512.0
	K := 5

	requiredBits := numSamples * wordBits
	if n < requiredBits {
		return nil, fmt.Errorf("birthday spacing test requires at least %d bits, got %d", requiredBits, n)
	}

	ints := make([]int, numSamples)
	for i := 0; i < numSamples; i++ {
		val := 0
		for j := 0; j < wordBits; j++ {
			bitIdx := i*wordBits + j
			if bitIdx >= n {
				break
			}
			val = (val << 1) | bits[bitIdx]
		}
		ints[i] = val
	}

	sort.Ints(ints)

	spacings := make([]int, numSamples)
	for i := 1; i < numSamples; i++ {
		spacings[i] = ints[i] - ints[i-1]
	}

	sort.Ints(spacings[1:])

	uniqueSpacings := 0
	for i := 2; i < numSamples; i++ {
		if spacings[i] != spacings[i-1] {
			uniqueSpacings++
		}
	}

	K_val := float64(numSamples - uniqueSpacings)

	chi2 := 0.0
	prob := make([]float64, K+1)
	for i := 0; i < K; i++ {
		prob[i] = math.Pow(lambda, float64(i)) * math.Exp(-lambda) / float64(factorial(i))
	}
	sumP := 0.0
	for i := 0; i < K; i++ {
		sumP += prob[i]
	}
	prob[K] = 1.0 - sumP

	Y := make([]int, K+1)
	for i := 0; i < K+1; i++ {
		if i < K {
			Y[i] = 0
		}
	}

	kmin := 0
	count := 0
	for i := 1; i < numSamples; i++ {
		if i == numSamples-1 || spacings[i] != spacings[i+1] {
			k := i - kmin
			kmin = i + 1
			if k >= K {
				Y[K]++
			} else {
				Y[k]++
			}
			count++
		}
	}

	for i := 0; i <= K; i++ {
		expected := float64(count) * prob[i]
		term := float64(Y[i]) - expected
		chi2 += (term * term) / expected
	}

	pValue := utils.GammaPValue(float64(K)/2.0, chi2/2.0)

	return &TestResult{
		Name:        t.Name(),
		DisplayName: t.DisplayName(),
		PValue:      pValue,
		Passed:      pValue >= cfg.SignificanceLevel,
		Statistic:   chi2,
		Details:     fmt.Sprintf("n=%d, samples=%d, word_bits=%d, unique_spacings=%d, K=%.2f, chi2=%.6f",
			n, numSamples, wordBits, uniqueSpacings, K_val, chi2),
	}, nil
}

type OverlappingPermutationsTest struct{}

func (t *OverlappingPermutationsTest) Name() string        { return "overlapping-permutations" }
func (t *OverlappingPermutationsTest) DisplayName() string { return "Dieharder Overlapping Permutations Test" }

func (t *OverlappingPermutationsTest) Run(bits []int, cfg *config.TestConfig) (*TestResult, error) {
	n := len(bits)

	tupleSize := 5
	wordBits := 32
	numTuples := 100000

	requiredBits := (numTuples + tupleSize - 1) * wordBits
	if n < requiredBits {
		return nil, fmt.Errorf("overlapping permutations test requires at least %d bits, got %d", requiredBits, n)
	}

	words := make([]uint32, numTuples+tupleSize-1)
	for i := 0; i < numTuples+tupleSize-1; i++ {
		var val uint32 = 0
		for j := 0; j < wordBits; j++ {
			bitIdx := i*wordBits + j
			if bitIdx >= n {
				break
			}
			val = (val << 1) | uint32(bits[bitIdx])
		}
		words[i] = val
	}

	fact5 := 120
	counts := make([]int, fact5)

	for i := 0; i < numTuples; i++ {
		tuple := make([]uint32, tupleSize)
		for j := 0; j < tupleSize; j++ {
			tuple[j] = words[i+j]
		}

		permRank := computePermutationRank(tuple)
		counts[permRank]++
	}

	chi2 := 0.0
	expected := float64(numTuples) / float64(fact5)
	for i := 0; i < fact5; i++ {
		term := float64(counts[i]) - expected
		chi2 += (term * term) / expected
	}

	df := fact5 - 1
	pValue := utils.GammaPValue(float64(df)/2.0, chi2/2.0)

	return &TestResult{
		Name:        t.Name(),
		DisplayName: t.DisplayName(),
		PValue:      pValue,
		Passed:      pValue >= cfg.SignificanceLevel,
		Statistic:   chi2,
		Details:     fmt.Sprintf("n=%d, tuples=%d, tuple_size=%d, word_bits=%d, df=%d, chi2=%.6f",
			n, numTuples, tupleSize, wordBits, df, chi2),
	}, nil
}

func computePermutationRank(tuple []uint32) int {
	n := len(tuple)
	rank := 0
	used := make([]bool, n)

	for i := 0; i < n; i++ {
		smallerCount := 0
		for j := 0; j < n; j++ {
			if !used[j] && tuple[j] < tuple[i] {
				smallerCount++
			}
		}
		rank = rank*(n-i) + smallerCount
		used[i] = true
	}

	return rank
}

func DieharderTests() []Test {
	return []Test{
		&BirthdaySpacingTest{},
		&OverlappingPermutationsTest{},
	}
}
