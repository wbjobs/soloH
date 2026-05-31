package worker

import (
	"context"
	"fmt"
	"net"
	"sync"
	"time"

	"tcp-fuzzer/internal/crash"
	"tcp-fuzzer/internal/feedback"
	"tcp-fuzzer/internal/mutator"
	"tcp-fuzzer/internal/protocol"
	"tcp-fuzzer/internal/symbolic"
	networkpkg "tcp-fuzzer/pkg/network"
	tcppkg "tcp-fuzzer/pkg/tcp"
)

type WorkerConfig struct {
	ID             int
	TargetHost     string
	TargetPort     int
	Timeout        time.Duration
	Proto          *protocol.ProtocolDescription
	FeedbackQueue  *feedback.Queue
	CrashRecorder  *crash.Recorder
	Mutator        *mutator.Mutator
	Generator      *protocol.MessageGenerator
	SymbolicEngine *symbolic.Engine
	PerturbConfig  *networkpkg.PerturbationConfig
	OnCrash        func(crash.CrashEntry)
}

type Worker struct {
	cfg           WorkerConfig
	pool          *tcppkg.ConnectionPool
	stats         *WorkerStats
	statsMu       sync.RWMutex
	stopChan      chan struct{}
	wg            sync.WaitGroup
	mu            sync.Mutex
}

type WorkerStats struct {
	ID             int
	TestsExecuted  uint64
	CrashesFound   uint64
	AnomaliesFound uint64
	BytesSent      uint64
	BytesReceived  uint64
	StartTime      time.Time
	LastUpdate     time.Time
}

type TestResult struct {
	WorkerID   int
	Seed       []byte
	Input      []byte
	Output     []byte
	Crash      bool
	Anomaly    bool
	CrashType  string
	StackTrace string
	Error      string
	Duration   time.Duration
	Strategy   mutator.MutationStrategy
	NewPath    bool
}

func NewWorker(cfg WorkerConfig) (*Worker, error) {
	pool, err := tcppkg.NewConnectionPool(tcppkg.Config{
		Host:        cfg.TargetHost,
		Port:        cfg.TargetPort,
		MaxConns:    2,
		Timeout:     cfg.Timeout,
		DialTimeout: 5 * time.Second,
	})
	if err != nil {
		return nil, fmt.Errorf("worker %d: failed to create connection pool: %w", cfg.ID, err)
	}

	return &Worker{
		cfg:      cfg,
		pool:     pool,
		stopChan: make(chan struct{}),
		stats: &WorkerStats{
			ID:        cfg.ID,
			StartTime: time.Now(),
		},
	}, nil
}

func (w *Worker) Start(ctx context.Context) {
	w.wg.Add(1)
	go w.run(ctx)
}

func (w *Worker) run(ctx context.Context) {
	defer w.wg.Done()

	for {
		select {
		case <-ctx.Done():
			return
		case <-w.stopChan:
			return
		default:
			result := w.runTest()
			w.processResult(result)
		}
	}
}

func (w *Worker) runTest() *TestResult {
	result := &TestResult{
		WorkerID: w.cfg.ID,
	}

	startTime := time.Now()
	defer func() {
		result.Duration = time.Since(startTime)
		w.updateStats(result)
	}()

	seed, err := w.cfg.FeedbackQueue.GetNextSeed()
	if err != nil {
		result.Error = fmt.Sprintf("failed to get seed: %v", err)
		return result
	}
	result.Seed = seed

	var mutResult *mutator.MutationResult
	mutResult, err = w.cfg.Mutator.Mutate(seed)
	if err != nil {
		result.Error = fmt.Sprintf("failed to mutate: %v", err)
		return result
	}
	result.Input = mutResult.Data
	result.Strategy = mutResult.Strategy

	if w.cfg.SymbolicEngine != nil {
		solverResult, err := w.cfg.SymbolicEngine.Solve(nil, result.Input)
		if err == nil && solverResult != nil && solverResult.Solved {
			result.Input = solverResult.FullPacket
		}
	}

	conn, err := w.pool.Get()
	if err != nil {
		if netErr, ok := err.(net.Error); ok && netErr.Timeout() {
			result.Crash = true
			result.CrashType = "connection_timeout"
			result.StackTrace = fmt.Sprintf("Connection timed out: %v", err)
		} else {
			result.Crash = true
			result.CrashType = "connection_failed"
			result.StackTrace = fmt.Sprintf("Connection failed: %v", err)
		}
		return result
	}
	defer w.pool.Put(conn)

	actualConn := net.Conn(conn)
	if w.cfg.PerturbConfig != nil && w.cfg.PerturbConfig.Enabled {
		actualConn = networkpkg.NewPerturbedConn(conn, w.cfg.PerturbConfig)
	}

	client := tcppkg.NewTCPClient(actualConn, w.cfg.Timeout)

	w.statsMu.Lock()
	w.stats.BytesSent += uint64(len(result.Input))
	w.statsMu.Unlock()

	resp, err := client.SendReceive(result.Input, w.cfg.Proto.MaxMsgSize*2)
	if err != nil {
		if netErr, ok := err.(net.Error); ok && netErr.Timeout() {
			result.Anomaly = true
			result.Error = fmt.Sprintf("read timeout: %v", err)
		} else {
			result.Crash = true
			result.CrashType = "connection_reset"
			result.StackTrace = fmt.Sprintf("Connection reset by peer: %v\nInput: %x", err, result.Input)
		}
		return result
	}
	result.Output = resp

	w.statsMu.Lock()
	w.stats.BytesReceived += uint64(len(resp))
	w.statsMu.Unlock()

	anomalyType := w.detectAnomaly(result.Input, resp)
	if anomalyType != "" {
		result.Anomaly = true
		result.CrashType = anomalyType
		result.StackTrace = fmt.Sprintf("Anomaly detected: %s\nInput: %x\nOutput: %x", anomalyType, result.Input, resp)
	}

	return result
}

func (w *Worker) detectAnomaly(input, output []byte) string {
	if len(output) == 0 {
		return "empty_response"
	}

	if len(output) > w.cfg.Proto.MaxMsgSize*2 {
		return "oversized_response"
	}

	expectedPatterns := []struct {
		pattern []byte
		name    string
	}{
		{[]byte("error"), "error_message"},
		{[]byte("Error"), "error_message"},
		{[]byte("ERROR"), "error_message"},
		{[]byte("exception"), "exception_message"},
		{[]byte("panic"), "panic_message"},
		{[]byte("stack"), "stack_trace"},
		{[]byte("traceback"), "stack_trace"},
	}

	lowerOutput := make([]byte, len(output))
	for i, b := range output {
		if b >= 'A' && b <= 'Z' {
			lowerOutput[i] = b + 32
		} else {
			lowerOutput[i] = b
		}
	}

	for _, ep := range expectedPatterns {
		if bytesContains(lowerOutput, ep.pattern) {
			return ep.name
		}
	}

	if len(output) > 0 {
		firstByte := output[0]
		if firstByte >= 0x80 {
			return "unusual_response_code"
		}
	}

	return ""
}

func bytesContains(data, pattern []byte) bool {
	if len(pattern) == 0 || len(data) < len(pattern) {
		return false
	}
	for i := 0; i <= len(data)-len(pattern); i++ {
		match := true
		for j := 0; j < len(pattern); j++ {
			if data[i+j] != pattern[j] {
				match = false
				break
			}
		}
		if match {
			return true
		}
	}
	return false
}

func (w *Worker) processResult(result *TestResult) {
	if result.Crash {
		entry := crash.CrashEntry{
			Timestamp:  time.Now(),
			WorkerID:   result.WorkerID,
			Input:      result.Input,
			Output:     result.Output,
			CrashType:  result.CrashType,
			StackTrace: result.StackTrace,
			Strategy:   string(result.Strategy),
		}
		w.cfg.CrashRecorder.RecordCrash(entry)
		if w.cfg.OnCrash != nil {
			w.cfg.OnCrash(entry)
		}
	}

	if result.Anomaly {
		w.cfg.CrashRecorder.RecordAnomaly(crash.AnomalyEntry{
			Timestamp:   time.Now(),
			WorkerID:    result.WorkerID,
			Input:       result.Input,
			Output:      result.Output,
			AnomalyType: result.CrashType,
			Details:     result.StackTrace,
			Strategy:    string(result.Strategy),
		})
	}

	isNewPath := w.cfg.FeedbackQueue.ReportResult(result.Input, result.Output, result.Crash || result.Anomaly)
	result.NewPath = isNewPath
}

func (w *Worker) updateStats(result *TestResult) {
	w.statsMu.Lock()
	defer w.statsMu.Unlock()

	w.stats.TestsExecuted++
	if result.Crash {
		w.stats.CrashesFound++
	}
	if result.Anomaly {
		w.stats.AnomaliesFound++
	}
	w.stats.LastUpdate = time.Now()
}

func (w *Worker) Stop() {
	close(w.stopChan)
	w.wg.Wait()
	w.pool.Close()
}

func (w *Worker) GetStats() *WorkerStats {
	w.statsMu.RLock()
	defer w.statsMu.RUnlock()
	s := *w.stats
	return &s
}

type WorkerPool struct {
	workers []*Worker
	cfg     WorkerPoolConfig
	wg      sync.WaitGroup
}

type WorkerPoolConfig struct {
	NumWorkers     int
	Target         string
	TargetHost     string
	TargetPort     int
	Timeout        time.Duration
	Proto          *protocol.ProtocolDescription
	FeedbackQueue  *feedback.Queue
	CrashRecorder  *crash.Recorder
	Mutator        *mutator.Mutator
	SymbolicEngine *symbolic.Engine
	PerturbConfig  *networkpkg.PerturbationConfig
	OnCrash        func(crash.CrashEntry)
	BaseSeed       int64
}

func NewWorkerPool(cfg WorkerPoolConfig) (*WorkerPool, error) {
	if cfg.NumWorkers <= 0 {
		cfg.NumWorkers = 10
	}
	if cfg.Timeout <= 0 {
		cfg.Timeout = 5 * time.Second
	}

	if cfg.Target != "" && (cfg.TargetHost == "" || cfg.TargetPort == 0) {
		host, portStr, err := net.SplitHostPort(cfg.Target)
		if err != nil {
			return nil, fmt.Errorf("invalid target address: %w", err)
		}
		cfg.TargetHost = host
		fmt.Sscanf(portStr, "%d", &cfg.TargetPort)
	}

	pool := &WorkerPool{
		workers: make([]*Worker, 0, cfg.NumWorkers),
		cfg:     cfg,
	}

	for i := 0; i < cfg.NumWorkers; i++ {
		workerCfg := WorkerConfig{
			ID:             i,
			TargetHost:     cfg.TargetHost,
			TargetPort:     cfg.TargetPort,
			Timeout:        cfg.Timeout,
			Proto:          cfg.Proto,
			FeedbackQueue:  cfg.FeedbackQueue,
			CrashRecorder:  cfg.CrashRecorder,
			Mutator:        mutator.NewMutator(cfg.Proto, cfg.BaseSeed+int64(i)),
			Generator:      protocol.NewMessageGenerator(cfg.Proto, cfg.BaseSeed+int64(i)+1000),
			SymbolicEngine: cfg.SymbolicEngine,
			PerturbConfig:  cfg.PerturbConfig,
			OnCrash:        cfg.OnCrash,
		}

		worker, err := NewWorker(workerCfg)
		if err != nil {
			for _, w := range pool.workers {
				w.Stop()
			}
			return nil, fmt.Errorf("failed to create worker %d: %w", i, err)
		}
		pool.workers = append(pool.workers, worker)
	}

	return pool, nil
}

func (p *WorkerPool) Start(ctx context.Context) {
	for _, w := range p.workers {
		w.Start(ctx)
	}
}

func (p *WorkerPool) Stop() {
	for _, w := range p.workers {
		w.Stop()
	}
}

func (p *WorkerPool) GetStats() []*WorkerStats {
	stats := make([]*WorkerStats, len(p.workers))
	for i, w := range p.workers {
		stats[i] = w.GetStats()
	}
	return stats
}

func (p *WorkerPool) TotalStats() *WorkerStats {
	total := &WorkerStats{
		ID:       -1,
		StartTime: time.Now(),
	}
	for _, w := range p.workers {
		s := w.GetStats()
		total.TestsExecuted += s.TestsExecuted
		total.CrashesFound += s.CrashesFound
		total.AnomaliesFound += s.AnomaliesFound
		total.BytesSent += s.BytesSent
		total.BytesReceived += s.BytesReceived
		if s.LastUpdate.After(total.LastUpdate) {
			total.LastUpdate = s.LastUpdate
		}
		if s.StartTime.Before(total.StartTime) {
			total.StartTime = s.StartTime
		}
	}
	return total
}
