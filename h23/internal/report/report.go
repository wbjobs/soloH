package report

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"strings"
	"time"

	"randomness-tester/internal/config"
	"randomness-tester/internal/tests"
)

type FullReport struct {
	Timestamp         time.Time                        `json:"timestamp"`
	InputType         string                       `json:"input_type"`
	InputSource       string                       `json:"input_source"`
	BitLength         int                          `json:"bit_length"`
	SignificanceLevel float64                      `json:"significance_level"`
	Config            *config.TestConfig           `json:"config,omitempty"`
	CorrectionConfig  *config.CorrectionConfig    `json:"correction_config,omitempty"`
	Corrections       []config.ParameterRecommendation `json:"corrections,omitempty"`
	Results           []*tests.TestResult           `json:"results"`
	Passed            int                          `json:"passed"`
	Failed            int                          `json:"failed"`
	OverallPassed     bool                         `json:"overall_passed"`
	Parallelism       int                          `json:"parallelism"`
	Duration          time.Duration                `json:"duration_ms"`
}

func GenerateJSONReport(report *FullReport, w io.Writer) error {
	encoder := json.NewEncoder(w)
	encoder.SetIndent("", "  ")
	return encoder.Encode(report)
}

func GenerateTextReport(report *FullReport, w io.Writer) error {
	var sb strings.Builder

	sb.WriteString("========================================\n")
	sb.WriteString("   NIST Randomness Test Suite Report\n")
	sb.WriteString("========================================\n\n")

	sb.WriteString(fmt.Sprintf("Timestamp:         %s\n", report.Timestamp.Format(time.RFC3339)))
	sb.WriteString(fmt.Sprintf("Input Type:        %s\n", report.InputType))
	sb.WriteString(fmt.Sprintf("Input Source:      %s\n", report.InputSource))
	sb.WriteString(fmt.Sprintf("Bit Length:        %d bits\n", report.BitLength))
	sb.WriteString(fmt.Sprintf("Significance Level: %.4f\n", report.SignificanceLevel))
	sb.WriteString(fmt.Sprintf("Parallelism:       %d cores\n", report.Parallelism))
	sb.WriteString(fmt.Sprintf("Duration:          %.2f seconds\n\n", report.Duration.Seconds()))

	sb.WriteString("----------------------------------------\n")
	sb.WriteString("           Test Results\n")
	sb.WriteString("----------------------------------------\n\n")

	maxNameLen := 0
	for _, r := range report.Results {
		if len(r.DisplayName) > maxNameLen {
			maxNameLen = len(r.DisplayName)
		}
	}

	header := fmt.Sprintf("%-*s  %-12s  %-8s  %s\n", maxNameLen, "Test Name", "P-Value", "Status", "Details")
	sb.WriteString(header)
	sb.WriteString(strings.Repeat("-", maxNameLen+45) + "\n")

	for _, r := range report.Results {
		status := "PASS"
		if !r.Passed {
			status = "FAIL"
		}

		pValueStr := fmt.Sprintf("%.6f", r.PValue)
		if r.PValue == 0 && strings.HasPrefix(r.Details, "ERROR:") {
			pValueStr = "ERROR"
			status = "ERROR"
		}

		line := fmt.Sprintf("%-*s  %-12s  %-8s  %s\n",
			maxNameLen, r.DisplayName, pValueStr, status, r.Details)
		sb.WriteString(line)
	}

	sb.WriteString("\n----------------------------------------\n")
	sb.WriteString("           Summary\n")
	sb.WriteString("----------------------------------------\n\n")

	sb.WriteString(fmt.Sprintf("Total Tests:   %d\n", len(report.Results)))
	sb.WriteString(fmt.Sprintf("Passed:        %d\n", report.Passed))
	sb.WriteString(fmt.Sprintf("Failed:        %d\n", report.Failed))
	sb.WriteString(fmt.Sprintf("Overall:       "))
	if report.OverallPassed {
		sb.WriteString("PASSED\n")
	} else {
		sb.WriteString("FAILED\n")
	}

	sb.WriteString("\nNote: A test is considered PASSED if P-value >= ")
	sb.WriteString(fmt.Sprintf("%.4f\n", report.SignificanceLevel))

	if len(report.Corrections) > 0 {
		sb.WriteString("\n----------------------------------------\n")
		sb.WriteString("      Parameter Validation & Corrections\n")
		sb.WriteString("----------------------------------------\n\n")

		hasWarnings := false
		for _, c := range report.Corrections {
			if !c.Validated && c.Reason != "" {
				hasWarnings = true
				sb.WriteString(fmt.Sprintf("⚠️  %s [%s]: %s\n", c.TestName, c.ParameterName, c.Reason))
				if c.Recommended > 0 && c.CurrentValue != c.Recommended {
					sb.WriteString(fmt.Sprintf("   Current: %d, Recommended: %d\n", c.CurrentValue, c.Recommended))
				}
			}
		}

		if !hasWarnings {
			sb.WriteString("✅ All parameters validated successfully.\n")
		}
	}

	_, err := io.WriteString(w, sb.String())
	return err
}

func SaveJSONReport(report *FullReport, path string) error {
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	return GenerateJSONReport(report, f)
}

func SaveTextReport(report *FullReport, path string) error {
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	return GenerateTextReport(report, f)
}
