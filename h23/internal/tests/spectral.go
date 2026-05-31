package tests

import (
	"fmt"
	"math"
	"randomness-tester/internal/config"
	"randomness-tester/internal/utils"
)

type DFTTest struct{}

func (t *DFTTest) Name() string        { return "dft" }
func (t *DFTTest) DisplayName() string { return "Discrete Fourier Transform (Spectral) Test" }

func (t *DFTTest) Run(bits []int, cfg *config.TestConfig) (*TestResult, error) {
	n := len(bits)
	if n < 1000 {
		return nil, fmt.Errorf("DFT test requires at least 1000 bits, got %d", n)
	}

	X := make([]float64, n)
	for i, b := range bits {
		if b == 0 {
			X[i] = -1.0
		} else {
			X[i] = 1.0
		}
	}

	fft := utils.FFT(X)

	m := n / 2
	T := math.Sqrt(math.Log(1.0/0.05) * float64(n))
	N0 := 0.95 * float64(m)

	N1 := 0
	for i := 0; i < m; i++ {
		modulus := math.Hypot(fft[i].r, fft[i].i)
		if modulus < T {
			N1++
		}
	}

	d := (float64(N1) - N0) / math.Sqrt(float64(n)*0.95*0.05/4.0)
	pValue := math.Erfc(math.Abs(d) / math.Sqrt(2))

	return &TestResult{
		Name:        t.Name(),
		DisplayName: t.DisplayName(),
		PValue:      pValue,
		Passed:      pValue >= cfg.SignificanceLevel,
		Statistic:   d,
		Details:     fmt.Sprintf("n=%d, m=%d, T=%.4f, N0=%.2f, N1=%d, d=%.6f", n, m, T, N0, N1, d),
	}, nil
}

type NonOverlappingTemplateTest struct{}

func (t *NonOverlappingTemplateTest) Name() string        { return "non-overlapping-template" }
func (t *NonOverlappingTemplateTest) DisplayName() string { return "Non-overlapping Template Matching Test" }

func (t *NonOverlappingTemplateTest) Run(bits []int, cfg *config.TestConfig) (*TestResult, error) {
	n := len(bits)
	m := cfg.NonOverlappingTemplateLength

	if n < 1000000 {
		return nil, fmt.Errorf("non-overlapping template test requires at least 1000000 bits, got %d", n)
	}

	templates := cfg.NonOverlappingTemplates
	if len(templates) == 0 {
		templates = generateTemplates(m)
	}

	M := 1032
	N := n / M
	K := 5

	lambda := float64(M - m + 1) / math.Pow(2.0, float64(m))
	eta := lambda / 2.0

	pi := make([]float64, K+1)
	for i := 0; i < K; i++ {
		pi[i] = math.Pow(eta, float64(i)) * math.Exp(-eta) / float64(factorial(i))
	}
	sum := 0.0
	for i := 0; i < K; i++ {
		sum += pi[i]
	}
	pi[K] = 1.0 - sum

	totalPValue := 0.0
	for _, templateStr := range templates {
		template, err := utils.ParseBitString(templateStr)
		if err != nil {
			return nil, err
		}
		if len(template) != m {
			return nil, fmt.Errorf("template length must be %d, got %d", m, len(template))
		}

		W := make([]int, N)
		for i := 0; i < N; i++ {
			count := 0
			start := i * M
			j := 0
			for j <= M-m {
				match := true
				for k := 0; k < m; k++ {
					if bits[start+j+k] != template[k] {
						match = false
						break
					}
				}
				if match {
					count++
					j += m
				} else {
					j++
				}
			}
			W[i] = count
		}

		chi2 := 0.0
		for i := 0; i <= K; i++ {
			expected := float64(N) * pi[i]
			observed := 0
			for _, w := range W {
				if (i < K && w == i) || (i == K && w >= K) {
					observed++
				}
			}
			term := float64(observed) - expected
			chi2 += (term * term) / expected
		}

		pValue := utils.GammaPValue(float64(K)/2.0, chi2/2.0)
		totalPValue += pValue
	}

	avgPValue := totalPValue / float64(len(templates))

	return &TestResult{
		Name:        t.Name(),
		DisplayName: t.DisplayName(),
		PValue:      avgPValue,
		Passed:      avgPValue >= cfg.SignificanceLevel,
		Statistic:   avgPValue,
		Details:     fmt.Sprintf("n=%d, m=%d, templates=%d, avg_p=%.6f", n, m, len(templates), avgPValue),
	}, nil
}

func generateTemplates(m int) []string {
	templates := make([]string, 0)
	max := 1 << uint(m)
	for i := 0; i < max && len(templates) < 100; i++ {
		s := fmt.Sprintf("%0*b", m, i)
		good := true
		for j := 0; j < len(s)-1; j++ {
			if s[j] == '1' && s[j+1] == '1' {
				good = false
				break
			}
		}
		if good {
			templates = append(templates, s)
		}
	}
	return templates
}

func factorial(n int) int {
	if n <= 1 {
		return 1
	}
	result := 1
	for i := 2; i <= n; i++ {
		result *= i
	}
	return result
}

type OverlappingTemplateTest struct{}

func (t *OverlappingTemplateTest) Name() string        { return "overlapping-template" }
func (t *OverlappingTemplateTest) DisplayName() string { return "Overlapping Template Matching Test" }

func (t *OverlappingTemplateTest) Run(bits []int, cfg *config.TestConfig) (*TestResult, error) {
	n := len(bits)
	m := cfg.OverlappingTemplateLength
	K := 5

	if n < 1000000 {
		return nil, fmt.Errorf("overlapping template test requires at least 1000000 bits, got %d", n)
	}

	M := cfg.OverlappingBlockSize
	if M <= 0 {
		M = 1000000
	}
	N := n / M
	if N == 0 {
		return nil, fmt.Errorf("block size %d is too large for sequence length %d", M, n)
	}

	lambda := float64(M - m + 1) / math.Pow(2.0, float64(m))
	eta := lambda / 2.0

	pi := make([]float64, K+1)
	for i := 0; i < K; i++ {
		pi[i] = math.Pow(eta, float64(i)) * math.Exp(-eta) / float64(factorial(i))
	}
	sum := 0.0
	for i := 0; i < K; i++ {
		sum += pi[i]
	}
	pi[K] = 1.0 - sum

	template := make([]int, m)
	for i := range template {
		template[i] = 1
	}

	v := make([]int, K+1)
	for i := 0; i < N; i++ {
		count := 0
		start := i * M
		for j := 0; j <= M-m; j++ {
			match := true
			for k := 0; k < m; k++ {
				if bits[start+j+k] != template[k] {
					match = false
					break
				}
			}
			if match {
				count++
			}
		}

		if count <= K {
			v[count]++
		} else {
			v[K]++
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
		Details:     fmt.Sprintf("n=%d, M=%d, N=%d, m=%d, K=%d, chi2=%.6f", n, M, N, m, K, chi2),
	}, nil
}

type UniversalTest struct{}

func (t *UniversalTest) Name() string        { return "universal" }
func (t *UniversalTest) DisplayName() string { return "Maurer's Universal Statistical Test" }

func (t *UniversalTest) Run(bits []int, cfg *config.TestConfig) (*TestResult, error) {
	n := len(bits)
	L := cfg.UniversalL
	Q := cfg.UniversalQ
	K := cfg.UniversalK

	if n < 387840 {
		return nil, fmt.Errorf("universal test requires at least 387840 bits, got %d", n)
	}

	if L < 6 || L > 16 {
		return nil, fmt.Errorf("L must be between 6 and 16, got %d", L)
	}

	expectedValues := map[int]float64{
		6:  5.2177052,
		7:  6.1962507,
		8:  7.1836656,
		9:  8.1764248,
		10: 9.1723243,
		11: 10.170032,
		12: 11.168765,
		13: 12.168070,
		14: 13.167693,
		15: 14.167488,
		16: 15.167379,
	}
	varianceValues := map[int]float64{
		6:  2.954,
		7:  3.125,
		8:  3.238,
		9:  3.311,
		10: 3.356,
		11: 3.384,
		12: 3.401,
		13: 3.410,
		14: 3.416,
		15: 3.419,
		16: 3.421,
	}

	expected := expectedValues[L]
	variance := varianceValues[L]

	table := make([]int, 1<<uint(L))
	for i := range table {
		table[i] = -1
	}

	idx := 0
	for i := 0; i < Q; i++ {
		block := 0
		for j := 0; j < L; j++ {
			block = (block << 1) | bits[idx]
			idx++
		}
		table[block] = i + 1
	}

	sum := 0.0
	for i := 0; i < K; i++ {
		block := 0
		for j := 0; j < L; j++ {
			block = (block << 1) | bits[idx]
			idx++
		}
		if table[block] >= 0 {
			diff := (Q + i + 1) - table[block]
			sum += math.Log2(float64(diff))
		}
		table[block] = Q + i + 1
	}

	fn := sum / float64(K)
	sigma := math.Sqrt(variance) * math.Sqrt(1.0/float64(K))
	z := (fn - expected) / (sigma * math.Sqrt(2.0))
	pValue := math.Erfc(math.Abs(z))

	return &TestResult{
		Name:        t.Name(),
		DisplayName: t.DisplayName(),
		PValue:      pValue,
		Passed:      pValue >= cfg.SignificanceLevel,
		Statistic:   fn,
		Details:     fmt.Sprintf("n=%d, L=%d, Q=%d, K=%d, fn=%.6f, expected=%.3f, sigma=%.4f, z=%.6f", n, L, Q, K, fn, expected, sigma, z),
	}, nil
}

type LZCompressionTest struct{}

func (t *LZCompressionTest) Name() string        { return "lz-compression" }
func (t *LZCompressionTest) DisplayName() string { return "Lempel-Ziv Compression Test" }

func (t *LZCompressionTest) Run(bits []int, cfg *config.TestConfig) (*TestResult, error) {
	n := len(bits)
	if n < 1000000 {
		return nil, fmt.Errorf("LZ compression test requires at least 1000000 bits, got %d", n)
	}

	M := cfg.LZCompressionBlockSize
	if M < 1000 {
		M = 1000
	}

	N := n / M
	if N < 1000 {
		return nil, fmt.Errorf("need at least 1000 blocks for LZ compression test, got %d (M=%d, n=%d)", N, M, n)
	}

	W := 16
	L := 6

	compressedSizes := make([]int, N)

	for i := 0; i < N; i++ {
		block := bits[i*M : (i+1)*M]
		compressedSizes[i] = lz77CompressBlock(block, W, L)
	}

	K := 5
	minSize := math.MaxInt32
	maxSize := 0
	for _, s := range compressedSizes {
		if s < minSize {
			minSize = s
		}
		if s > maxSize {
			maxSize = s
		}
	}

	binWidth := float64(maxSize-minSize+1) / float64(K)
	if binWidth < 1 {
		binWidth = 1
	}

	observed := make([]int, K)
	for _, s := range compressedSizes {
		bin := int(float64(s-minSize) / binWidth)
		if bin >= K {
			bin = K - 1
		}
		observed[bin]++
	}

	meanSize := 0.0
	for _, s := range compressedSizes {
		meanSize += float64(s)
	}
	meanSize /= float64(N)

	variance := 0.0
	for _, s := range compressedSizes {
		diff := float64(s) - meanSize
		variance += diff * diff
	}
	variance /= float64(N - 1)
	sigma := math.Sqrt(variance)

	chi2 := 0.0
	expected := float64(N) / float64(K)
	for i := 0; i < K; i++ {
		term := float64(observed[i]) - expected
		chi2 += (term * term) / expected
	}

	pValue := utils.GammaPValue(float64(K-1)/2.0, chi2/2.0)

	return &TestResult{
		Name:        t.Name(),
		DisplayName: t.DisplayName(),
		PValue:      pValue,
		Passed:      pValue >= cfg.SignificanceLevel,
		Statistic:   chi2,
		Details:     fmt.Sprintf("n=%d, M=%d, N=%d, W=%d, L=%d, mean_size=%.2f, sigma=%.2f, chi2=%.6f",
			n, M, N, W, L, meanSize, sigma, chi2),
	}, nil
}

func lz77CompressBlock(bits []int, windowSize, lookaheadSize int) int {
	n := len(bits)
	if n == 0 {
		return 0
	}

	compressedSize := 0
	i := 0

	for i < n {
		maxMatchLen := 0
		bestMatchPos := 0

		windowStart := i - windowSize
		if windowStart < 0 {
			windowStart = 0
		}
		windowEnd := i

		lookaheadEnd := i + lookaheadSize
		if lookaheadEnd > n {
			lookaheadEnd = n
		}
		maxPossibleMatch := lookaheadEnd - i

		for j := windowStart; j < windowEnd; j++ {
			matchLen := 0
			for matchLen < maxPossibleMatch && j+matchLen < i && i+matchLen < n {
				if bits[j+matchLen] != bits[i+matchLen] {
					break
				}
				matchLen++
			}
			if matchLen > maxMatchLen {
				maxMatchLen = matchLen
				bestMatchPos = i - j
			}
		}

		if maxMatchLen >= 2 {
			offsetBits := int(math.Ceil(math.Log2(float64(windowSize))))
			lengthBits := int(math.Ceil(math.Log2(float64(lookaheadSize))))
			compressedSize += offsetBits + lengthBits
			i += maxMatchLen
		} else {
			compressedSize += 1
			i++
		}
	}

	return compressedSize
}
