package tests

import (
	"fmt"
	"math"
	"randomness-tester/internal/config"
	"randomness-tester/internal/utils"
)

type LinearComplexityTest struct{}

func (t *LinearComplexityTest) Name() string        { return "linear-complexity" }
func (t *LinearComplexityTest) DisplayName() string { return "Linear Complexity Test" }

func (t *LinearComplexityTest) Run(bits []int, cfg *config.TestConfig) (*TestResult, error) {
	n := len(bits)
	M := cfg.LinearComplexityBlockSize

	if n < 1000000 {
		return nil, fmt.Errorf("linear complexity test requires at least 1000000 bits, got %d", n)
	}
	if M < 500 {
		return nil, fmt.Errorf("block size M must be at least 500, got %d", M)
	}

	N := n / M
	if N == 0 {
		return nil, fmt.Errorf("block size %d is too large for sequence length %d", M, n)
	}

	meanMap := map[int]float64{
		500:  250.0,
		1000: 500.0,
		5000: 2500.0,
	}
	mean := meanMap[M]
	if mean == 0 {
		mean = float64(M) / 2.0
	}

	K := 6
	pi := []float64{0.010417, 0.03125, 0.125, 0.5, 0.25, 0.0625, 0.020833}

	v := make([]int, K+1)
	for i := 0; i < N; i++ {
		block := bits[i*M : (i+1)*M]
		L := berlekampMassey(block)

		T := (math.Pow(-1.0, float64(M))*(float64(L)-mean) + 2.0/9.0)
		idx := 0
		switch {
		case T <= -2.5:
			idx = 0
		case T <= -1.5:
			idx = 1
		case T <= -0.5:
			idx = 2
		case T <= 0.5:
			idx = 3
		case T <= 1.5:
			idx = 4
		case T <= 2.5:
			idx = 5
		default:
			idx = 6
		}
		v[idx]++
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

func berlekampMassey(s []int) int {
	n := len(s)
	c := make([]int, n)
	b := make([]int, n)
	c[0] = 1
	b[0] = 1

	L := 0
	m := -1
	for i := 0; i < n; i++ {
		d := s[i]
		for j := 1; j <= L; j++ {
			d ^= c[j] & s[i-j]
		}

		if d != 0 {
			t := make([]int, n)
			copy(t, c)
			for j := 0; i-m+j < n; j++ {
				if b[j] != 0 {
					c[i-m+j] ^= 1
				}
			}
			if 2*L <= i {
				L = i + 1 - L
				m = i
				copy(b, t)
			}
		}
	}

	return L
}

type SerialTest struct{}

func (t *SerialTest) Name() string        { return "serial" }
func (t *SerialTest) DisplayName() string { return "Serial Test" }

func (t *SerialTest) Run(bits []int, cfg *config.TestConfig) (*TestResult, error) {
	n := len(bits)
	m := cfg.SerialBlockSize

	if n < 1000000 {
		return nil, fmt.Errorf("serial test requires at least 1000000 bits, got %d", n)
	}
	if m < 2 || m > int(math.Log2(float64(n)))-2 {
		return nil, fmt.Errorf("block size m must be between 2 and log2(n)-2, got %d", m)
	}

	extendedBits := make([]int, n+m-1)
	copy(extendedBits, bits)
	copy(extendedBits[n:], bits[:m-1])

	p1, p2 := serialTestCompute(extendedBits, n, m)

	minP := math.Min(p1, p2)

	return &TestResult{
		Name:        t.Name(),
		DisplayName: t.DisplayName(),
		PValue:      minP,
		Passed:      minP >= cfg.SignificanceLevel,
		Statistic:   minP,
		Details:     fmt.Sprintf("n=%d, m=%d, p1=%.6f, p2=%.6f, min_p=%.6f", n, m, p1, p2, minP),
	}, nil
}

func serialTestCompute(bits []int, n, m int) (float64, float64) {
	if m > 1 {
		_, psi2m := computePsi(bits, n, m)
		_, psi2m1 := computePsi(bits, n, m-1)
		_, psi2m2 := computePsi(bits, n, m-2)

		delta1 := psi2m - psi2m1
		delta2 := psi2m - 2.0*psi2m1 + psi2m2

		df1 := 1 << uint(m-1)
		df2 := 1 << uint(m-2)

		p1 := utils.GammaPValue(float64(df1)/2.0, delta1/2.0)
		p2 := utils.GammaPValue(float64(df2)/2.0, delta2/2.0)
		return p1, p2
	}
	return 1.0, 1.0
}

func computePsi(bits []int, n, m int) (map[int]int, float64) {
	counts := make(map[int]int)
	size := 1 << uint(m)

	for i := 0; i < n; i++ {
		val := 0
		for j := 0; j < m; j++ {
			val = (val << 1) | bits[i+j]
		}
		counts[val]++
	}

	psi := 0.0
	for v := 0; v < size; v++ {
		c := counts[v]
		psi += float64(c) * float64(c)
	}
	psi = (float64(size)/float64(n))*psi - float64(n)

	return counts, psi
}

type ApproximateEntropyTest struct{}

func (t *ApproximateEntropyTest) Name() string        { return "approximate-entropy" }
func (t *ApproximateEntropyTest) DisplayName() string { return "Approximate Entropy Test" }

func (t *ApproximateEntropyTest) Run(bits []int, cfg *config.TestConfig) (*TestResult, error) {
	n := len(bits)
	m := cfg.ApproximateEntropyBlockSize

	if n < 100 {
		return nil, fmt.Errorf("approximate entropy test requires at least 100 bits, got %d", n)
	}
	if m < 2 || m > int(math.Log2(float64(n)))-5 {
		return nil, fmt.Errorf("block size m must be between 2 and log2(n)-5, got %d", m)
	}

	phiM := computePhi(bits, n, m)
	phiM1 := computePhi(bits, n, m+1)

	apen := phiM - phiM1
	chi2 := 2.0 * float64(n) * (math.Log(2.0) - apen)
	df := 1 << uint(m-1)

	pValue := utils.GammaPValue(float64(df)/2.0, chi2/2.0)

	return &TestResult{
		Name:        t.Name(),
		DisplayName: t.DisplayName(),
		PValue:      pValue,
		Passed:      pValue >= cfg.SignificanceLevel,
		Statistic:   chi2,
		Details:     fmt.Sprintf("n=%d, m=%d, phi_m=%.6f, phi_m1=%.6f, apen=%.6f, chi2=%.6f", n, m, phiM, phiM1, apen, chi2),
	}, nil
}

func computePhi(bits []int, n, m int) float64 {
	extendedBits := make([]int, n+m-1)
	copy(extendedBits, bits)
	copy(extendedBits[n:], bits[:m-1])

	size := 1 << uint(m)
	counts := make([]int, size)

	for i := 0; i < n; i++ {
		val := 0
		for j := 0; j < m; j++ {
			val = (val << 1) | extendedBits[i+j]
		}
		counts[val]++
	}

	sum := 0.0
	for v := 0; v < size; v++ {
		if counts[v] > 0 {
			c := float64(counts[v]) / float64(n)
			sum += c * math.Log(c)
		}
	}

	return sum
}

type CumulativeSumTest struct{}

func (t *CumulativeSumTest) Name() string        { return "cumulative-sums" }
func (t *CumulativeSumTest) DisplayName() string { return "Cumulative Sums (Cusum) Test" }

func (t *CumulativeSumTest) Run(bits []int, cfg *config.TestConfig) (*TestResult, error) {
	n := len(bits)

	if n < 100 {
		return nil, fmt.Errorf("cumulative sums test requires at least 100 bits, got %d", n)
	}

	X := make([]int, n)
	for i, b := range bits {
		if b == 0 {
			X[i] = -1
		} else {
			X[i] = 1
		}
	}

	S_forward := make([]int, n)
	S_forward[0] = X[0]
	for i := 1; i < n; i++ {
		S_forward[i] = S_forward[i-1] + X[i]
	}

	maxAbs_forward := 0
	for _, s := range S_forward {
		abs := s
		if abs < 0 {
			abs = -abs
		}
		if abs > maxAbs_forward {
			maxAbs_forward = abs
		}
	}

	S_backward := make([]int, n)
	S_backward[n-1] = X[n-1]
	for i := n - 2; i >= 0; i-- {
		S_backward[i] = S_backward[i+1] + X[i]
	}

	maxAbs_backward := 0
	for _, s := range S_backward {
		abs := s
		if abs < 0 {
			abs = -abs
		}
		if abs > maxAbs_backward {
			maxAbs_backward = abs
		}
	}

	p_forward := computeCumulativeSumPValue(float64(maxAbs_forward), n)
	p_backward := computeCumulativeSumPValue(float64(maxAbs_backward), n)

	p := math.Min(p_forward, p_backward)

	return &TestResult{
		Name:        t.Name(),
		DisplayName: t.DisplayName(),
		PValue:      p,
		Passed:      p >= cfg.SignificanceLevel,
		Statistic:   p,
		Details:     fmt.Sprintf("n=%d, forward_max|S|=%d, backward_max|S|=%d, p_forward=%.6f, p_backward=%.6f, p=%.6f",
			n, maxAbs_forward, maxAbs_backward, p_forward, p_backward, p),
	}, nil
}

func computeCumulativeSumPValue(z float64, n int) float64 {
	if z <= 0 {
		return 1.0
	}

	sqrtN := math.Sqrt(float64(n))

	startK := int(math.Floor((-float64(n)/z + 1.0) / 4.0))
	endK := int(math.Floor((float64(n)/z - 1.0) / 4.0))

	sum1 := 0.0
	for k := startK; k <= endK; k++ {
		arg1 := (4.0*float64(k)+1.0)*z / sqrtN
		term1 := math.Erfc(arg1)
		arg2 := (4.0*float64(k)-1.0)*z / sqrtN
		term2 := math.Erfc(arg2)
		sum1 += term1 - term2
	}

	startK = int(math.Floor((-float64(n)/z - 3.0) / 4.0))
	endK = int(math.Floor((float64(n)/z - 1.0) / 4.0))

	sum2 := 0.0
	for k := startK; k <= endK; k++ {
		arg1 := (4.0*float64(k)+3.0)*z / sqrtN
		term1 := math.Erfc(arg1)
		arg2 := (4.0*float64(k)+1.0)*z / sqrtN
		term2 := math.Erfc(arg2)
		sum2 += term1 - term2
	}

	return 1.0 - sum1 + sum2
}

type RandomExcursionsTest struct{}

func (t *RandomExcursionsTest) Name() string        { return "random-excursions" }
func (t *RandomExcursionsTest) DisplayName() string { return "Random Excursions Test" }

func (t *RandomExcursionsTest) Run(bits []int, cfg *config.TestConfig) (*TestResult, error) {
	n := len(bits)

	if n < 1000000 {
		return nil, fmt.Errorf("random excursions test requires at least 1000000 bits, got %d", n)
	}

	X := make([]int, n+1)
	X[0] = 0
	for i, b := range bits {
		if b == 0 {
			X[i+1] = X[i] - 1
		} else {
			X[i+1] = X[i] + 1
		}
	}

	J := 0
	for i := 1; i <= n; i++ {
		if X[i] == 0 {
			J++
		}
	}

	if J < 500 {
		return nil, fmt.Errorf("need at least 500 cycles for random excursions test, got %d", J)
	}

	cycles := make([][]int, 0)
	start := 0
	for i := 1; i <= n; i++ {
		if X[i] == 0 {
			cycles = append(cycles, X[start:i+1])
			start = i
		}
	}

	states := []int{-4, -3, -2, -1, 1, 2, 3, 4}
	targetState := cfg.RandomExcursionsState
	if targetState == 0 {
		targetState = 1
	}

	pi := map[int][]float64{
		-4: {0.875000, 0.015625, 0.013672, 0.011963, 0.083740},
		-3: {0.833333, 0.027778, 0.023148, 0.019290, 0.096451},
		-2: {0.750000, 0.062500, 0.046875, 0.035156, 0.105469},
		-1: {0.500000, 0.250000, 0.125000, 0.062500, 0.062500},
		1:  {0.500000, 0.250000, 0.125000, 0.062500, 0.062500},
		2:  {0.750000, 0.062500, 0.046875, 0.035156, 0.105469},
		3:  {0.833333, 0.027778, 0.023148, 0.019290, 0.096451},
		4:  {0.875000, 0.015625, 0.013672, 0.011963, 0.083740},
	}

	found := false
	for _, s := range states {
		if s == targetState {
			found = true
			break
		}
	}
	if !found {
		targetState = 1
	}

	v := make([]int, 5)
	for _, cycle := range cycles {
		count := 0
		for _, x := range cycle {
			if x == targetState {
				count++
			}
		}

		switch {
		case count == 0:
			v[0]++
		case count == 1:
			v[1]++
		case count == 2:
			v[2]++
		case count == 3:
			v[3]++
		default:
			v[4]++
		}
	}

	piVals := pi[targetState]
	chi2 := 0.0
	for i := 0; i < 5; i++ {
		expected := float64(J) * piVals[i]
		term := float64(v[i]) - expected
		chi2 += (term * term) / expected
	}

	pValue := utils.GammaPValue(2.0, chi2/2.0)

	return &TestResult{
		Name:        t.Name(),
		DisplayName: t.DisplayName(),
		PValue:      pValue,
		Passed:      pValue >= cfg.SignificanceLevel,
		Statistic:   chi2,
		Details:     fmt.Sprintf("n=%d, J=%d, state=%d, chi2=%.6f, v=[%d,%d,%d,%d,%d]", n, J, targetState, chi2, v[0], v[1], v[2], v[3], v[4]),
	}, nil
}
