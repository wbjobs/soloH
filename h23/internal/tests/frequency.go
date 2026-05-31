package tests

import (
	"fmt"
	"math"
	"randomness-tester/internal/config"
	"randomness-tester/internal/utils"
)

type FrequencyTest struct{}

func (t *FrequencyTest) Name() string        { return "frequency" }
func (t *FrequencyTest) DisplayName() string { return "Frequency (Monobit) Test" }

func (t *FrequencyTest) Run(bits []int, cfg *config.TestConfig) (*TestResult, error) {
	n := len(bits)
	if n < 100 {
		return nil, fmt.Errorf("frequency test requires at least 100 bits, got %d", n)
	}

	sum := 0
	for _, b := range bits {
		if b == 0 {
			sum--
		} else {
			sum++
		}
	}

	sObs := math.Abs(float64(sum)) / math.Sqrt(float64(n))
	pValue := math.Erfc(sObs / math.Sqrt(2))

	return &TestResult{
		Name:        t.Name(),
		DisplayName: t.DisplayName(),
		PValue:      pValue,
		Passed:      pValue >= cfg.SignificanceLevel,
		Statistic:   sObs,
		Details:     fmt.Sprintf("n=%d, sum=%d, s_obs=%.6f", n, sum, sObs),
	}, nil
}

type BlockFrequencyTest struct{}

func (t *BlockFrequencyTest) Name() string        { return "block-frequency" }
func (t *BlockFrequencyTest) DisplayName() string { return "Frequency Test within a Block" }

func (t *BlockFrequencyTest) Run(bits []int, cfg *config.TestConfig) (*TestResult, error) {
	n := len(bits)
	M := cfg.BlockFrequencyBlockSize

	if n < 100 {
		return nil, fmt.Errorf("block frequency test requires at least 100 bits, got %d", n)
	}
	if M < 20 {
		return nil, fmt.Errorf("block size M must be at least 20, got %d", M)
	}

	N := n / M
	if N == 0 {
		return nil, fmt.Errorf("block size %d is too large for sequence length %d", M, n)
	}

	chi2 := 0.0
	for i := 0; i < N; i++ {
		ones := 0
		start := i * M
		for j := 0; j < M; j++ {
			ones += bits[start+j]
		}
		pi := float64(ones) / float64(M)
		term := pi - 0.5
		chi2 += term * term
	}

	chi2 *= 4.0 * float64(M)
	pValue := utils.GammaPValue(float64(N)/2.0, chi2/2.0)

	return &TestResult{
		Name:        t.Name(),
		DisplayName: t.DisplayName(),
		PValue:      pValue,
		Passed:      pValue >= cfg.SignificanceLevel,
		Statistic:   chi2,
		Details:     fmt.Sprintf("n=%d, M=%d, N=%d, chi2=%.6f", n, M, N, chi2),
	}, nil
}

type RunsTest struct{}

func (t *RunsTest) Name() string        { return "runs" }
func (t *RunsTest) DisplayName() string { return "Runs Test" }

func (t *RunsTest) Run(bits []int, cfg *config.TestConfig) (*TestResult, error) {
	n := len(bits)
	if n < 100 {
		return nil, fmt.Errorf("runs test requires at least 100 bits, got %d", n)
	}

	pi := 0.0
	for _, b := range bits {
		pi += float64(b)
	}
	pi /= float64(n)

	tau := 2.0 / math.Sqrt(float64(n))
	if math.Abs(pi-0.5) >= tau {
		return nil, fmt.Errorf("proportion of ones %.4f is too far from 0.5 (tau=%.4f)", pi, tau)
	}

	v := 0
	for i := 1; i < n; i++ {
		if bits[i] != bits[i-1] {
			v++
		}
	}
	v++

	term := math.Abs(float64(v) - 2.0*float64(n)*pi*(1.0-pi))
	denom := 2.0 * math.Sqrt(2.0*float64(n)) * pi * (1.0 - pi)
	pValue := math.Erfc(term / denom)

	return &TestResult{
		Name:        t.Name(),
		DisplayName: t.DisplayName(),
		PValue:      pValue,
		Passed:      pValue >= cfg.SignificanceLevel,
		Statistic:   float64(v),
		Details:     fmt.Sprintf("n=%d, pi=%.4f, v=%d, pValue=%.6f", n, pi, v, pValue),
	}, nil
}

type LongestRunTest struct{}

func (t *LongestRunTest) Name() string        { return "longest-run" }
func (t *LongestRunTest) DisplayName() string { return "Test for the Longest Run of Ones in a Block" }

func (t *LongestRunTest) Run(bits []int, cfg *config.TestConfig) (*TestResult, error) {
	n := len(bits)
	M := cfg.LongestRunBlockSize

	if n < 128 {
		return nil, fmt.Errorf("longest run test requires at least 128 bits, got %d", n)
	}

	N := n / M
	if N < 8 {
		return nil, fmt.Errorf("need at least 8 blocks, got N=%d for M=%d and n=%d", N, M, n)
	}

	K := 0
	pi := make([]float64, 0)

	switch {
	case M >= 128:
		K = 5
		pi = []float64{0.1174035788, 0.242955959, 0.249363483, 0.17517706, 0.102701071, 0.112398847}
	case M >= 64:
		K = 4
		pi = []float64{0.0882, 0.2092, 0.2483, 0.1933, 0.2610}
	case M >= 8:
		K = 3
		pi = []float64{0.2148, 0.3672, 0.2305, 0.1875}
	default:
		return nil, fmt.Errorf("block size M must be at least 8, got %d", M)
	}

	v := make([]int, K+1)
	for i := 0; i < N; i++ {
		longest := 0
		current := 0
		start := i * M
		for j := 0; j < M; j++ {
			if bits[start+j] == 1 {
				current++
				if current > longest {
					longest = current
				}
			} else {
				current = 0
			}
		}

		switch {
		case M >= 128:
			switch {
			case longest <= 4:
				v[0]++
			case longest == 5:
				v[1]++
			case longest == 6:
				v[2]++
			case longest == 7:
				v[3]++
			case longest == 8:
				v[4]++
			default:
				v[5]++
			}
		case M >= 64:
			switch {
			case longest <= 4:
				v[0]++
			case longest == 5:
				v[1]++
			case longest == 6:
				v[2]++
			case longest == 7:
				v[3]++
			default:
				v[4]++
			}
		default:
			switch {
			case longest <= 1:
				v[0]++
			case longest == 2:
				v[1]++
			case longest == 3:
				v[2]++
			default:
				v[3]++
			}
		}
	}

	chi2 := 0.0
	for i := 0; i <= K; i++ {
		expected := float64(N) * pi[i]
		term := float64(v[i]) - expected
		chi2 += (term * term) / expected
	}

	pValue := utils.GammaPValue(float64(K)/2.0, chi2/2.0)

	return &TestResult{
		Name:        t.Name(),
		DisplayName: t.DisplayName(),
		PValue:      pValue,
		Passed:      pValue >= cfg.SignificanceLevel,
		Statistic:   chi2,
		Details:     fmt.Sprintf("n=%d, M=%d, N=%d, K=%d, chi2=%.6f", n, M, N, K, chi2),
	}, nil
}

type RankTest struct{}

func (t *RankTest) Name() string        { return "rank" }
func (t *RankTest) DisplayName() string { return "Binary Matrix Rank Test" }

func (t *RankTest) Run(bits []int, cfg *config.TestConfig) (*TestResult, error) {
	n := len(bits)
	M := cfg.RankMatrixRows
	Q := cfg.RankMatrixCols

	if n < M*Q*38 {
		return nil, fmt.Errorf("rank test requires at least %d bits, got %d", M*Q*38, n)
	}

	N := n / (M * Q)
	if N == 0 {
		return nil, fmt.Errorf("sequence too short for matrix size %dx%d", M, Q)
	}

	F := make([]int, 3)

	for i := 0; i < N; i++ {
		matrix := make([][]int, M)
		for r := 0; r < M; r++ {
			matrix[r] = make([]int, Q)
			start := i*M*Q + r*Q
			for c := 0; c < Q; c++ {
				matrix[r][c] = bits[start+c]
			}
		}

		rank := computeRank(matrix, M, Q)

		if rank == min(M, Q) {
			F[0]++
		} else if rank == min(M, Q)-1 {
			F[1]++
		} else {
			F[2]++
		}
	}

	chi2 := 0.0
	p := []float64{0.2888, 0.5776, 0.1336}
	for i := 0; i < 3; i++ {
		expected := float64(N) * p[i]
		term := float64(F[i]) - expected
		chi2 += (term * term) / expected
	}

	pValue := utils.GammaPValue(1.0, chi2/2.0)

	return &TestResult{
		Name:        t.Name(),
		DisplayName: t.DisplayName(),
		PValue:      pValue,
		Passed:      pValue >= cfg.SignificanceLevel,
		Statistic:   chi2,
		Details:     fmt.Sprintf("n=%d, M=%d, Q=%d, N=%d, F=[%d,%d,%d], chi2=%.6f", n, M, Q, N, F[0], F[1], F[2], chi2),
	}, nil
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func computeRank(matrix [][]int, rows, cols int) int {
	A := make([][]int, rows)
	for i := range A {
		A[i] = make([]int, cols)
		copy(A[i], matrix[i])
	}

	rank := 0
	for col := 0; col < cols && rank < rows; col++ {
		pivot := -1
		for row := rank; row < rows; row++ {
			if A[row][col] == 1 {
				pivot = row
				break
			}
		}

		if pivot == -1 {
			continue
		}

		A[rank], A[pivot] = A[pivot], A[rank]

		for row := 0; row < rows; row++ {
			if row != rank && A[row][col] == 1 {
				for c := col; c < cols; c++ {
					A[row][c] ^= A[rank][c]
				}
			}
		}

		rank++
	}

	return rank
}
