package tests

import (
	"runtime"
	"sync"

	"randomness-tester/internal/config"
)

type TestRunner struct {
	Parallelism int
}

func NewTestRunner() *TestRunner {
	return &TestRunner{
		Parallelism: runtime.NumCPU(),
	}
}

func (r *TestRunner) RunAll(bits []int, cfg *config.TestConfig) []*TestResult {
	allTests := AllTests()
	return r.RunTests(bits, cfg, allTests)
}

func (r *TestRunner) RunTests(bits []int, cfg *config.TestConfig, testsToRun []Test) []*TestResult {
	results := make([]*TestResult, len(testsToRun))
	errors := make([]error, len(testsToRun))

	if r.Parallelism <= 1 {
		for i, test := range testsToRun {
			results[i], errors[i] = test.Run(bits, cfg)
		}
	} else {
		sem := make(chan struct{}, r.Parallelism)
		var wg sync.WaitGroup

		for i, test := range testsToRun {
			wg.Add(1)
			sem <- struct{}{}

			go func(idx int, t Test) {
				defer wg.Done()
				defer func() { <-sem }()

				results[idx], errors[idx] = t.Run(bits, cfg)
			}(i, test)
		}

		wg.Wait()
	}

	finalResults := make([]*TestResult, 0, len(results))
	for i, res := range results {
		if errors[i] != nil {
			finalResults = append(finalResults, &TestResult{
				Name:        testsToRun[i].Name(),
				DisplayName: testsToRun[i].DisplayName(),
				PValue:      0.0,
				Passed:      false,
				Details:     "ERROR: " + errors[i].Error(),
			})
		} else {
			finalResults = append(finalResults, res)
		}
	}

	return finalResults
}

func SummarizeResults(results []*TestResult, cfg *config.TestConfig) (int, int) {
	passed := 0
	failed := 0
	for _, r := range results {
		if r.PValue >= cfg.SignificanceLevel {
			passed++
		} else {
			failed++
		}
	}
	return passed, failed
}
