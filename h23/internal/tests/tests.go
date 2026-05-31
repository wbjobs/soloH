package tests

import (
	"randomness-tester/internal/config"
	"randomness-tester/internal/utils"
)

type TestResult struct {
	Name        string  `json:"name"`
	DisplayName string  `json:"display_name"`
	PValue      float64 `json:"p_value"`
	Passed      bool    `json:"passed"`
	Statistic   float64 `json:"statistic,omitempty"`
	Details     string  `json:"details,omitempty"`
}

type Test interface {
	Name() string
	DisplayName() string
	Run(bits []int, cfg *config.TestConfig) (*TestResult, error)
}

func AllTests() []Test {
	return []Test{
		&FrequencyTest{},
		&BlockFrequencyTest{},
		&RunsTest{},
		&LongestRunTest{},
		&RankTest{},
		&DFTTest{},
		&NonOverlappingTemplateTest{},
		&OverlappingTemplateTest{},
		&UniversalTest{},
		&LZCompressionTest{},
		&LinearComplexityTest{},
		&SerialTest{},
		&ApproximateEntropyTest{},
		&CumulativeSumTest{},
		&RandomExcursionsTest{},
		&BirthdaySpacingTest{},
		&OverlappingPermutationsTest{},
	}
}

func NISTTests() []Test {
	return []Test{
		&FrequencyTest{},
		&BlockFrequencyTest{},
		&RunsTest{},
		&LongestRunTest{},
		&RankTest{},
		&DFTTest{},
		&NonOverlappingTemplateTest{},
		&OverlappingTemplateTest{},
		&UniversalTest{},
		&LZCompressionTest{},
		&LinearComplexityTest{},
		&SerialTest{},
		&ApproximateEntropyTest{},
		&CumulativeSumTest{},
		&RandomExcursionsTest{},
	}
}

func GetTestByName(name string) Test {
	for _, t := range AllTests() {
		if t.Name() == name {
			return t
		}
	}
	return nil
}
