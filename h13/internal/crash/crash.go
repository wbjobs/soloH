package crash

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"
)

type CrashEntry struct {
	ID           string    `json:"id"`
	Timestamp    time.Time `json:"timestamp"`
	WorkerID     int       `json:"worker_id"`
	Input        []byte    `json:"input"`
	Output       []byte    `json:"output"`
	CrashType    string    `json:"crash_type"`
	StackTrace   string    `json:"stack_trace"`
	Strategy     string    `json:"strategy"`
	InputHex     string    `json:"input_hex"`
	OutputHex    string    `json:"output_hex"`
	JiraIssueKey string    `json:"jira_issue_key,omitempty"`
	Reported     bool      `json:"reported"`
}

type AnomalyEntry struct {
	ID          string    `json:"id"`
	Timestamp   time.Time `json:"timestamp"`
	WorkerID    int       `json:"worker_id"`
	Input       []byte    `json:"input"`
	Output      []byte    `json:"output"`
	AnomalyType string    `json:"anomaly_type"`
	Details     string    `json:"details"`
	Strategy    string    `json:"strategy"`
	InputHex    string    `json:"input_hex"`
	OutputHex   string    `json:"output_hex"`
}

type RecorderConfig struct {
	CrashDir     string
	AnomalyDir   string
	EnableDedup  bool
	MaxCrashes   int
}

type CrashSignature struct {
	Primary   string
	Secondary string
}

type Recorder struct {
	cfg           RecorderConfig
	crashes       []CrashEntry
	anomalies     []AnomalyEntry
	seenCrashes   map[string]*CrashSignature
	seenAnomalies map[string]*CrashSignature
	mu            sync.RWMutex
}

func NewRecorder(cfg RecorderConfig) (*Recorder, error) {
	if cfg.EnableDedup == false {
		cfg.EnableDedup = true
	}
	if cfg.MaxCrashes <= 0 {
		cfg.MaxCrashes = 1000
	}
	if cfg.CrashDir == "" {
		cfg.CrashDir = "crashes"
	}
	if cfg.AnomalyDir == "" {
		cfg.AnomalyDir = "anomalies"
	}

	if err := os.MkdirAll(cfg.CrashDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create crash directory: %w", err)
	}
	if err := os.MkdirAll(cfg.AnomalyDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create anomaly directory: %w", err)
	}

	return &Recorder{
		cfg:           cfg,
		crashes:       make([]CrashEntry, 0),
		anomalies:     make([]AnomalyEntry, 0),
		seenCrashes:   make(map[string]*CrashSignature),
		seenAnomalies: make(map[string]*CrashSignature),
	}, nil
}

func (r *Recorder) RecordCrash(entry CrashEntry) {
	r.mu.Lock()
	defer r.mu.Unlock()

	if entry.ID == "" {
		entry.ID = generateID()
	}
	entry.InputHex = hex.EncodeToString(entry.Input)
	entry.OutputHex = hex.EncodeToString(entry.Output)

	if r.cfg.EnableDedup {
		sig := r.crashSignature(&entry)
		if existing, ok := r.seenCrashes[sig.Primary]; ok {
			if existing.Secondary == sig.Secondary {
				return
			}
		}
		r.seenCrashes[sig.Primary] = sig
	}

	if len(r.crashes) >= r.cfg.MaxCrashes {
		r.crashes = r.crashes[1:]
	}

	r.crashes = append(r.crashes, entry)

	if err := r.saveCrash(&entry); err != nil {
		fmt.Fprintf(os.Stderr, "Warning: failed to save crash: %v\n", err)
	}

	fmt.Printf("\n=== CRASH DETECTED ===\n")
	fmt.Printf("Type:      %s\n", entry.CrashType)
	fmt.Printf("Worker:    %d\n", entry.WorkerID)
	fmt.Printf("Timestamp: %s\n", entry.Timestamp.Format(time.RFC3339))
	fmt.Printf("Strategy:  %s\n", entry.Strategy)
	fmt.Printf("Input:     %s...\n", truncateHex(entry.InputHex, 64))
	fmt.Printf("ID:        %s\n", entry.ID)
	fmt.Printf("======================\n\n")
}

func (r *Recorder) RecordAnomaly(entry AnomalyEntry) {
	r.mu.Lock()
	defer r.mu.Unlock()

	if entry.ID == "" {
		entry.ID = generateID()
	}
	entry.InputHex = hex.EncodeToString(entry.Input)
	entry.OutputHex = hex.EncodeToString(entry.Output)

	if r.cfg.EnableDedup {
		sig := r.anomalySignature(&entry)
		if existing, ok := r.seenAnomalies[sig.Primary]; ok {
			if existing.Secondary == sig.Secondary {
				return
			}
		}
		r.seenAnomalies[sig.Primary] = sig
	}

	r.anomalies = append(r.anomalies, entry)

	if err := r.saveAnomaly(&entry); err != nil {
		fmt.Fprintf(os.Stderr, "Warning: failed to save anomaly: %v\n", err)
	}
}

func (r *Recorder) crashSignature(entry *CrashEntry) *CrashSignature {
	hPrimary := sha256.New()
	hPrimary.Write([]byte(entry.CrashType))
	hPrimary.Write([]byte{0x00})
	hPrimary.Write([]byte(entry.StackTrace))
	hPrimary.Write([]byte{0x00})

	inputHash := sha256.Sum256(entry.Input)
	hPrimary.Write(inputHash[:16])

	primarySig := hex.EncodeToString(hPrimary.Sum(nil))

	hSecondary := sha256.New()
	hSecondary.Write([]byte(entry.CrashType))
	hSecondary.Write([]byte{0x00})
	hSecondary.Write([]byte(fmt.Sprintf("%d", len(entry.Input))))
	hSecondary.Write([]byte{0x00})
	outputHash := sha256.Sum256(entry.Output)
	hSecondary.Write(outputHash[:16])
	hSecondary.Write([]byte{0x00})
	hSecondary.Write([]byte(fmt.Sprintf("%d", len(entry.Output))))

	if entry.Strategy != "" {
		hSecondary.Write([]byte{0x00})
		hSecondary.Write([]byte(entry.Strategy))
	}

	secondarySig := hex.EncodeToString(hSecondary.Sum(nil))

	return &CrashSignature{
		Primary:   primarySig,
		Secondary: secondarySig,
	}
}

func (r *Recorder) anomalySignature(entry *AnomalyEntry) *CrashSignature {
	hPrimary := sha256.New()
	hPrimary.Write([]byte(entry.AnomalyType))
	hPrimary.Write([]byte{0x00})
	hPrimary.Write([]byte(entry.Details))
	hPrimary.Write([]byte{0x00})

	inputHash := sha256.Sum256(entry.Input)
	hPrimary.Write(inputHash[:16])

	primarySig := hex.EncodeToString(hPrimary.Sum(nil))

	hSecondary := sha256.New()
	hSecondary.Write([]byte(entry.AnomalyType))
	hSecondary.Write([]byte{0x00})
	hSecondary.Write([]byte(fmt.Sprintf("%d", len(entry.Input))))
	hSecondary.Write([]byte{0x00})
	outputHash := sha256.Sum256(entry.Output)
	hSecondary.Write(outputHash[:16])

	if entry.Strategy != "" {
		hSecondary.Write([]byte{0x00})
		hSecondary.Write([]byte(entry.Strategy))
	}

	secondarySig := hex.EncodeToString(hSecondary.Sum(nil))

	return &CrashSignature{
		Primary:   primarySig,
		Secondary: secondarySig,
	}
}

func (r *Recorder) saveCrash(entry *CrashEntry) error {
	timestamp := entry.Timestamp.Format("20060102_150405")
	baseName := fmt.Sprintf("crash_%s_%s", timestamp, entry.ID[:8])

	jsonPath := filepath.Join(r.cfg.CrashDir, baseName+".json")
	inputPath := filepath.Join(r.cfg.CrashDir, baseName+".bin")
	txtPath := filepath.Join(r.cfg.CrashDir, baseName+".txt")

	jsonData, err := json.MarshalIndent(entry, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal crash JSON: %w", err)
	}
	if err := os.WriteFile(jsonPath, jsonData, 0644); err != nil {
		return fmt.Errorf("failed to write crash JSON: %w", err)
	}

	if err := os.WriteFile(inputPath, entry.Input, 0644); err != nil {
		return fmt.Errorf("failed to write crash input: %w", err)
	}

	txtContent := fmt.Sprintf(`Crash Report
============
Timestamp: %s
Worker ID: %d
Crash Type: %s
Strategy: %s
ID: %s

Stack Trace:
%s

Input (%d bytes):
%s

Output (%d bytes):
%s
`,
		entry.Timestamp.Format(time.RFC3339),
		entry.WorkerID,
		entry.CrashType,
		entry.Strategy,
		entry.ID,
		entry.StackTrace,
		len(entry.Input),
		formatHexDump(entry.Input),
		len(entry.Output),
		formatHexDump(entry.Output),
	)
	if err := os.WriteFile(txtPath, []byte(txtContent), 0644); err != nil {
		return fmt.Errorf("failed to write crash text: %w", err)
	}

	return nil
}

func (r *Recorder) saveAnomaly(entry *AnomalyEntry) error {
	timestamp := entry.Timestamp.Format("20060102_150405")
	baseName := fmt.Sprintf("anomaly_%s_%s", timestamp, entry.ID[:8])

	jsonPath := filepath.Join(r.cfg.AnomalyDir, baseName+".json")
	inputPath := filepath.Join(r.cfg.AnomalyDir, baseName+".bin")

	jsonData, err := json.MarshalIndent(entry, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal anomaly JSON: %w", err)
	}
	if err := os.WriteFile(jsonPath, jsonData, 0644); err != nil {
		return fmt.Errorf("failed to write anomaly JSON: %w", err)
	}

	if err := os.WriteFile(inputPath, entry.Input, 0644); err != nil {
		return fmt.Errorf("failed to write anomaly input: %w", err)
	}

	return nil
}

func (r *Recorder) GetCrashes() []CrashEntry {
	r.mu.RLock()
	defer r.mu.RUnlock()
	crashes := make([]CrashEntry, len(r.crashes))
	copy(crashes, r.crashes)
	return crashes
}

func (r *Recorder) GetAnomalies() []AnomalyEntry {
	r.mu.RLock()
	defer r.mu.RUnlock()
	anomalies := make([]AnomalyEntry, len(r.anomalies))
	copy(anomalies, r.anomalies)
	return anomalies
}

func (r *Recorder) GetUnreportedCrashes() []CrashEntry {
	r.mu.RLock()
	defer r.mu.RUnlock()
	unreported := make([]CrashEntry, 0)
	for _, c := range r.crashes {
		if !c.Reported {
			unreported = append(unreported, c)
		}
	}
	return unreported
}

func (r *Recorder) MarkAsReported(crashID, jiraKey string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	for i := range r.crashes {
		if r.crashes[i].ID == crashID {
			r.crashes[i].Reported = true
			r.crashes[i].JiraIssueKey = jiraKey
			break
		}
	}
}

func (r *Recorder) Stats() (numCrashes, numAnomalies int) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return len(r.crashes), len(r.anomalies)
}

func (r *Recorder) WriteSummary(path string) error {
	r.mu.RLock()
	defer r.mu.RUnlock()

	summary := fmt.Sprintf(`Fuzzing Summary
===============
Generated: %s
Total Crashes: %d
Total Anomalies: %d

Crash Types:
`,
		time.Now().Format(time.RFC3339),
		len(r.crashes),
		len(r.anomalies),
	)

	crashTypes := make(map[string]int)
	for _, c := range r.crashes {
		crashTypes[c.CrashType]++
	}
	for t, count := range crashTypes {
		summary += fmt.Sprintf("  %-30s: %d\n", t, count)
	}

	summary += "\nAnomaly Types:\n"
	anomalyTypes := make(map[string]int)
	for _, a := range r.anomalies {
		anomalyTypes[a.AnomalyType]++
	}
	for t, count := range anomalyTypes {
		summary += fmt.Sprintf("  %-30s: %d\n", t, count)
	}

	if len(r.crashes) > 0 {
		summary += "\nRecent Crashes:\n"
		for i := len(r.crashes) - 1; i >= max(0, len(r.crashes)-10); i-- {
			c := r.crashes[i]
			summary += fmt.Sprintf("  [%s] %s (worker %d)\n",
				c.Timestamp.Format("15:04:05"),
				c.CrashType,
				c.WorkerID,
			)
		}
	}

	return os.WriteFile(path, []byte(summary), 0644)
}

func formatHexDump(data []byte) string {
	if len(data) == 0 {
		return "(empty)"
	}

	var result string
	for i := 0; i < len(data); i += 16 {
		end := min(i+16, len(data))
		line := data[i:end]

		hexPart := ""
		for j, b := range line {
			if j == 8 {
				hexPart += " "
			}
			hexPart += fmt.Sprintf("%02x ", b)
		}

		asciiPart := ""
		for _, b := range line {
			if b >= 32 && b < 127 {
				asciiPart += string(b)
			} else {
				asciiPart += "."
			}
		}

		result += fmt.Sprintf("  %08x: %-49s  %s\n", i, hexPart, asciiPart)

		if i > 256 {
			result += fmt.Sprintf("  ... (%d more bytes)\n", len(data)-i)
			break
		}
	}
	return result
}

func truncateHex(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen] + "..."
}

func generateID() string {
	b := make([]byte, 16)
	for i := range b {
		b[i] = byte(time.Now().UnixNano() % 256)
	}
	return hex.EncodeToString(b)
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
