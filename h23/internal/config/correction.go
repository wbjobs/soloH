package config

import (
	"fmt"
	"math"
)

type ParameterRecommendation struct {
	TestName      string
	ParameterName string
	CurrentValue  int
	Recommended   int
	Validated     bool
	Reason        string
}

type CorrectionConfig struct {
	AutoTuneParameters bool `json:"auto_tune_parameters"`
	MinimizeTypeI      bool `json:"minimize_type_i_error"`
	UseRecommended     bool `json:"use_recommended"`
}

func DefaultCorrectionConfig() *CorrectionConfig {
	return &CorrectionConfig{
		AutoTuneParameters: true,
		MinimizeTypeI:      true,
		UseRecommended:     true,
	}
}

type TestParameterRequirement struct {
	TestName    string
	MinBits     int
	Recommended map[string]int
	Constraints map[string]func(int, int) string
}

func GetTestRequirements() map[string]TestParameterRequirement {
	return map[string]TestParameterRequirement{
		"frequency": {
			TestName: "Frequency (Monobit) Test",
			MinBits:  100,
			Recommended: map[string]int{
				"n_min": 100,
			},
			Constraints: map[string]func(int, int) string{
				"n_min": func(n int, _ int) string {
					if n >= 100 {
						return ""
					}
					return fmt.Sprintf("sequence length %d is below recommended minimum 100", n)
				},
			},
		},
		"block-frequency": {
			TestName: "Block Frequency Test",
			MinBits:  100,
			Recommended: map[string]int{
				"M":       128,
				"min_n_per_block": 100,
			},
			Constraints: map[string]func(int, int) string{
				"M": func(M int, n int) string {
					if M < 20 {
						return fmt.Sprintf("block size %d is below minimum 20", M)
					}
					N := n / M
					if N < 10 {
						return fmt.Sprintf("block size %d gives only %d blocks, recommended at least 10 blocks", M, N)
					}
					if M > n/100 {
						return fmt.Sprintf("block size %d is too large for sequence length %d", M, n)
					}
					return ""
				},
			},
		},
		"runs": {
			TestName: "Runs Test",
			MinBits:  100,
			Recommended: map[string]int{
				"min_n": 100,
			},
			Constraints: map[string]func(int, int) string{
				"tau": func(n int, _ int) string {
					tau := 2.0 / math.Sqrt(float64(n))
					if tau > 0.01 {
						return fmt.Sprintf("tau=%.4f is above threshold 0.01, consider increasing n", tau)
					}
					return ""
				},
			},
		},
		"longest-run": {
			TestName: "Longest Run of Ones Test",
			MinBits:  128,
			Recommended: map[string]int{
				"M": 10000,
				"N": 8,
			},
			Constraints: map[string]func(int, int) string{
				"M": func(M int, n int) string {
					N := n / M
					if N < 8 {
						return fmt.Sprintf("need at least 8 blocks, got N=%d for M=%d", N, M)
					}
					if M < 8 {
						return fmt.Sprintf("M=%d is below minimum 8", M)
					}
					if M >= 128 && N >= 8 {
						return ""
					}
					if M >= 64 && N >= 8 {
						return ""
					}
					if M >= 8 && N >= 8 {
						return ""
					}
					return fmt.Sprintf("block size %d not in recommended range for sequence length %d", M, n)
				},
			},
		},
		"rank": {
			TestName: "Binary Matrix Rank Test",
			MinBits:  38912,
			Recommended: map[string]int{
				"M": 32,
				"Q": 32,
				"N": 38,
			},
			Constraints: map[string]func(int, int) string{
				"matrix": func(n int, _ int) string {
					minRequired := 32 * 32 * 38
					if n < minRequired {
						return fmt.Sprintf("need at least %d bits for 32×32 matrices and 38 blocks, got %d", minRequired, n)
					}
					return ""
				},
			},
		},
		"dft": {
			TestName: "Discrete Fourier Transform Test",
			MinBits:  1000,
			Recommended: map[string]int{
				"min_n": 1000,
			},
			Constraints: map[string]func(int, int) string{
				"n": func(n int, _ int) string {
					if n < 1000 {
						return fmt.Sprintf("need at least 1000 bits, got %d", n)
					}
					return ""
				},
			},
		},
		"non-overlapping-template": {
			TestName: "Non-overlapping Template Matching Test",
			MinBits:  1000000,
			Recommended: map[string]int{
				"m": 9,
				"M": 1032,
				"N": 968,
			},
			Constraints: map[string]func(int, int) string{
				"template": func(n int, m int) string {
					if n < 1000000 {
						return fmt.Sprintf("need at least 1000000 bits, got %d", n)
					}
					if m < 2 || m > 20 {
						return fmt.Sprintf("template length %d not in recommended range 2-20", m)
					}
					return ""
				},
			},
		},
		"overlapping-template": {
			TestName: "Overlapping Template Matching Test",
			MinBits:  1000000,
			Recommended: map[string]int{
				"m": 9,
				"M": 1000000,
			},
			Constraints: map[string]func(int, int) string{
				"template": func(n int, m int) string {
					if n < 1000000 {
						return fmt.Sprintf("need at least 1000000 bits, got %d", n)
					}
					if m < 2 || m > 10 {
						return fmt.Sprintf("template length %d not in recommended range 2-10", m)
					}
					return ""
				},
			},
		},
		"universal": {
			TestName: "Maurer's Universal Statistical Test",
			MinBits:  387840,
			Recommended: map[string]int{
				"L": 7,
				"Q": 1280,
				"K": 40,
			},
			Constraints: map[string]func(int, int) string{
				"L": func(L int, n int) string {
					if L < 6 || L > 16 {
						return fmt.Sprintf("L=%d not in recommended range 6-16", L)
					}
					minBits := (1 << uint(L)) * (L + 1) * 8
					if n < minBits {
						return fmt.Sprintf("need at least %d bits for L=%d, got %d", minBits, L, n)
					}
					return ""
				},
			},
		},
		"lz-compression": {
			TestName: "Lempel-Ziv Compression Test",
			MinBits:  1000000,
			Recommended: map[string]int{
				"M": 1000,
				"N": 1000,
				"W": 16,
				"L": 6,
			},
			Constraints: map[string]func(int, int) string{
				"M": func(M int, n int) string {
					N := n / M
					if N < 1000 {
						return fmt.Sprintf("need at least 1000 blocks, got N=%d for M=%d", N, M)
					}
					return ""
				},
			},
		},
		"linear-complexity": {
			TestName: "Linear Complexity Test",
			MinBits:  1000000,
			Recommended: map[string]int{
				"M": 1000,
				"N": 1000,
			},
			Constraints: map[string]func(int, int) string{
				"M": func(M int, n int) string {
					N := n / M
					if N < 1000 {
						return fmt.Sprintf("need at least 1000 blocks, got N=%d for M=%d", N, M)
					}
					if M < 500 {
						return fmt.Sprintf("M=%d is below minimum 500", M)
					}
					if M > 5000 {
						return fmt.Sprintf("M=%d is above maximum 5000", M)
					}
					return ""
				},
			},
		},
		"serial": {
			TestName: "Serial Test",
			MinBits:  1000000,
			Recommended: map[string]int{
				"m": 16,
			},
			Constraints: map[string]func(int, int) string{
				"m": func(m int, n int) string {
					maxM := int(math.Log2(float64(n))) - 2
					if m < 2 {
						return fmt.Sprintf("m=%d is below minimum 2", m)
					}
					if m > maxM {
						return fmt.Sprintf("m=%d is above maximum %d for sequence length %d", m, maxM, n)
					}
					return ""
				},
			},
		},
		"approximate-entropy": {
			TestName: "Approximate Entropy Test",
			MinBits:  100,
			Recommended: map[string]int{
				"m": 10,
			},
			Constraints: map[string]func(int, int) string{
				"m": func(m int, n int) string {
					maxM := int(math.Log2(float64(n))) - 5
					if m < 2 {
						return fmt.Sprintf("m=%d is below minimum 2", m)
					}
					if m > maxM {
						return fmt.Sprintf("m=%d is above maximum %d for sequence length %d", m, maxM, n)
					}
					return ""
				},
			},
		},
		"cumulative-sums": {
			TestName: "Cumulative Sums Test",
			MinBits:  100,
			Recommended: map[string]int{
				"min_n": 100,
			},
			Constraints: map[string]func(int, int) string{
				"n": func(n int, _ int) string {
					if n < 100 {
						return fmt.Sprintf("need at least 100 bits, got %d", n)
					}
					return ""
				},
			},
		},
		"random-excursions": {
			TestName: "Random Excursions Test",
			MinBits:  1000000,
			Recommended: map[string]int{
				"J": 500,
			},
			Constraints: map[string]func(int, int) string{
				"J": func(n int, _ int) string {
					if n < 1000000 {
						return fmt.Sprintf("need at least 1000000 bits, got %d", n)
					}
					return ""
				},
			},
		},
		"birthday-spacing": {
			TestName: "Dieharder Birthday Spacing Test",
			MinBits:  98304,
			Recommended: map[string]int{
				"word_bits":  24,
				"num_samples": 4096,
			},
			Constraints: map[string]func(int, int) string{
				"n": func(n int, _ int) string {
					if n < 98304 {
						return fmt.Sprintf("need at least 98304 bits, got %d", n)
					}
					return ""
				},
			},
		},
		"overlapping-permutations": {
			TestName: "Dieharder Overlapping Permutations Test",
			MinBits:  3200128,
			Recommended: map[string]int{
				"tuple_size": 5,
				"word_bits":  32,
				"num_tuples": 100000,
			},
			Constraints: map[string]func(int, int) string{
				"n": func(n int, _ int) string {
					if n < 3200128 {
						return fmt.Sprintf("need at least 3200128 bits, got %d", n)
					}
					return ""
				},
			},
		},
	}
}

func GetRecommendedParametersForTest(testName string, bitLength int) map[string]int {
	requirements := GetTestRequirements()
	req, ok := requirements[testName]
	if !ok {
		return nil
	}

	params := make(map[string]int)
	for k, v := range req.Recommended {
		params[k] = v
	}

	switch testName {
	case "block-frequency":
		if bitLength > 0 {
			M := 128
			N := bitLength / M
			if N < 10 && bitLength > 1000 {
				M = bitLength / 10
				if M < 20 {
					M = 20
				}
			}
			params["M"] = M
			params["N"] = bitLength / M
		}
	case "longest-run":
		if bitLength >= 1280000 {
			params["M"] = 10000
		} else if bitLength >= 64000 {
			params["M"] = 8000
		} else if bitLength >= 1024 {
			params["M"] = 128
		} else {
			params["M"] = 8
		}
		params["N"] = bitLength / params["M"]
	case "universal":
		L := 7
		if bitLength >= 15000000 {
			L = 16
		} else if bitLength >= 7500000 {
			L = 15
		} else if bitLength >= 3750000 {
			L = 14
		} else if bitLength >= 1875000 {
			L = 13
		} else if bitLength >= 937500 {
			L = 12
		} else if bitLength >= 468750 {
			L = 11
		} else if bitLength >= 234375 {
			L = 10
		} else if bitLength >= 117187 {
			L = 9
		} else if bitLength >= 58593 {
			L = 8
		}
		params["L"] = L
		minQ := 10 * (1 << uint(L))
		params["Q"] = minQ
		if params["Q"]*L*8 < bitLength {
			params["K"] = (bitLength/L/8 - params["Q"])
		}
	case "serial":
		maxM := int(math.Log2(float64(bitLength))) - 2
		if maxM > 16 {
			maxM = 16
		}
		if maxM < 2 {
			maxM = 2
		}
		params["m"] = maxM
	case "approximate-entropy":
		maxM := int(math.Log2(float64(bitLength))) - 5
		if maxM > 10 {
			maxM = 10
		}
		if maxM < 2 {
			maxM = 2
		}
		params["m"] = maxM
	case "linear-complexity":
		if bitLength >= 5000000 {
			params["M"] = 5000
		} else if bitLength >= 1000000 {
			params["M"] = 1000
		} else {
			params["M"] = 500
		}
		params["N"] = bitLength / params["M"]
	}

	return params
}

func ValidateTestParameters(cfg *TestConfig, bitLength int) []ParameterRecommendation {
	var recommendations []ParameterRecommendation

	requirements := GetTestRequirements()

	if rec := validateParameter("frequency", "n_min", bitLength, 100, requirements["frequency"].Constraints["n_min"], bitLength); rec != nil {
		recommendations = append(recommendations, *rec)
	}

	if rec := validateParameter("block-frequency", "M", cfg.BlockFrequencyBlockSize,
		GetRecommendedParametersForTest("block-frequency", bitLength)["M"],
		requirements["block-frequency"].Constraints["M"], bitLength); rec != nil {
		recommendations = append(recommendations, *rec)
	}

	if rec := validateParameter("longest-run", "M", cfg.LongestRunBlockSize,
		GetRecommendedParametersForTest("longest-run", bitLength)["M"],
		requirements["longest-run"].Constraints["M"], bitLength); rec != nil {
		recommendations = append(recommendations, *rec)
	}

	if rec := validateParameter("rank", "matrix", bitLength, 38912,
		requirements["rank"].Constraints["matrix"], bitLength); rec != nil {
		recommendations = append(recommendations, *rec)
	}

	if rec := validateParameter("dft", "n", bitLength, 1000,
		requirements["dft"].Constraints["n"], bitLength); rec != nil {
		recommendations = append(recommendations, *rec)
	}

	if rec := validateParameter("non-overlapping-template", "template", bitLength,
		cfg.NonOverlappingTemplateLength,
		requirements["non-overlapping-template"].Constraints["template"],
		cfg.NonOverlappingTemplateLength); rec != nil {
		recommendations = append(recommendations, *rec)
	}

	if rec := validateParameter("overlapping-template", "template", bitLength,
		cfg.OverlappingTemplateLength,
		requirements["overlapping-template"].Constraints["template"],
		cfg.OverlappingTemplateLength); rec != nil {
		recommendations = append(recommendations, *rec)
	}

	if rec := validateParameter("universal", "L", cfg.UniversalL,
		GetRecommendedParametersForTest("universal", bitLength)["L"],
		requirements["universal"].Constraints["L"], bitLength); rec != nil {
		recommendations = append(recommendations, *rec)
	}

	if rec := validateParameter("lz-compression", "M", cfg.LZCompressionBlockSize,
		GetRecommendedParametersForTest("lz-compression", bitLength)["M"],
		requirements["lz-compression"].Constraints["M"], bitLength); rec != nil {
		recommendations = append(recommendations, *rec)
	}

	if rec := validateParameter("linear-complexity", "M", cfg.LinearComplexityBlockSize,
		GetRecommendedParametersForTest("linear-complexity", bitLength)["M"],
		requirements["linear-complexity"].Constraints["M"], bitLength); rec != nil {
		recommendations = append(recommendations, *rec)
	}

	if rec := validateParameter("serial", "m", cfg.SerialBlockSize,
		GetRecommendedParametersForTest("serial", bitLength)["m"],
		requirements["serial"].Constraints["m"], bitLength); rec != nil {
		recommendations = append(recommendations, *rec)
	}

	if rec := validateParameter("approximate-entropy", "m", cfg.ApproximateEntropyBlockSize,
		GetRecommendedParametersForTest("approximate-entropy", bitLength)["m"],
		requirements["approximate-entropy"].Constraints["m"], bitLength); rec != nil {
		recommendations = append(recommendations, *rec)
	}

	if rec := validateParameter("cumulative-sums", "n", bitLength, 100,
		requirements["cumulative-sums"].Constraints["n"], bitLength); rec != nil {
		recommendations = append(recommendations, *rec)
	}

	if rec := validateParameter("random-excursions", "J", bitLength, 0,
		requirements["random-excursions"].Constraints["J"], bitLength); rec != nil {
		recommendations = append(recommendations, *rec)
	}

	return recommendations
}

func validateParameter(testName, paramName string, current, recommended int, validator func(int, int) string, validateArg int) *ParameterRecommendation {
	if validator == nil {
		return nil
	}

	reason := validator(validateArg, 0)
	return &ParameterRecommendation{
		TestName:      testName,
		ParameterName: paramName,
		CurrentValue:  current,
		Recommended:   recommended,
		Validated:     reason == "",
		Reason:        reason,
	}
}

func AutoCorrectConfig(cfg *TestConfig, bitLength int) *TestConfig {
	corrected := *cfg

	recParams := GetRecommendedParametersForTest("block-frequency", bitLength)
	if recParams != nil {
		if M, ok := recParams["M"]; ok && M > 0 {
			corrected.BlockFrequencyBlockSize = M
		}
	}

	recParams = GetRecommendedParametersForTest("longest-run", bitLength)
	if recParams != nil {
		if M, ok := recParams["M"]; ok && M > 0 {
			corrected.LongestRunBlockSize = M
		}
	}

	recParams = GetRecommendedParametersForTest("universal", bitLength)
	if recParams != nil {
		if L, ok := recParams["L"]; ok && L > 0 {
			corrected.UniversalL = L
		}
		if Q, ok := recParams["Q"]; ok && Q > 0 {
			corrected.UniversalQ = Q
		}
		if K, ok := recParams["K"]; ok && K > 0 {
			corrected.UniversalK = K
		}
	}

	recParams = GetRecommendedParametersForTest("serial", bitLength)
	if recParams != nil {
		if m, ok := recParams["m"]; ok && m > 0 {
			corrected.SerialBlockSize = m
		}
	}

	recParams = GetRecommendedParametersForTest("approximate-entropy", bitLength)
	if recParams != nil {
		if m, ok := recParams["m"]; ok && m > 0 {
			corrected.ApproximateEntropyBlockSize = m
		}
	}

	recParams = GetRecommendedParametersForTest("linear-complexity", bitLength)
	if recParams != nil {
		if M, ok := recParams["M"]; ok && M > 0 {
			corrected.LinearComplexityBlockSize = M
		}
	}

	return &corrected
}
