package distributed

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"net"
	"os"
	"runtime"
	"sync"
	"time"

	"tcp-fuzzer/internal/crash"
	"tcp-fuzzer/internal/feedback"
	"tcp-fuzzer/internal/mutator"
	"tcp-fuzzer/internal/protocol"
	"tcp-fuzzer/internal/symbolic"
	"tcp-fuzzer/internal/worker"
	networkpkg "tcp-fuzzer/pkg/network"
)

type AgentConfig struct {
	Name              string
	MasterAddr        string
	WorkerCount       int
	Timeout           time.Duration
	BaseSeed          int64
	HeartbeatInterval time.Duration
	QueueDir          string
	CrashDir          string
	AnomalyDir        string
}

type Agent struct {
	cfg            AgentConfig
	masterConn     net.Conn
	agentID        string
	running        bool
	ctx            context.Context
	cancel         context.CancelFunc
	status         AgentStatus
	workerPool     *worker.WorkerPool
	currentTask    *Task
	taskCancel     context.CancelFunc
	taskMu         sync.Mutex
	totalTests     uint64
	totalCrashes   int
	totalAnomalies int
	mu             sync.Mutex
}

func NewAgent(cfg AgentConfig) (*Agent, error) {
	if cfg.WorkerCount <= 0 {
		cfg.WorkerCount = runtime.NumCPU()
	}
	if cfg.HeartbeatInterval == 0 {
		cfg.HeartbeatInterval = 5 * time.Second
	}
	if cfg.Name == "" {
		hostname, _ := os.Hostname()
		cfg.Name = fmt.Sprintf("agent-%s", hostname)
	}
	if cfg.BaseSeed == 0 {
		cfg.BaseSeed = time.Now().UnixNano()
	}
	if cfg.QueueDir == "" {
		cfg.QueueDir = "queue_agent"
	}
	if cfg.CrashDir == "" {
		cfg.CrashDir = "crashes_agent"
	}
	if cfg.AnomalyDir == "" {
		cfg.AnomalyDir = "anomalies_agent"
	}

	ctx, cancel := context.WithCancel(context.Background())

	return &Agent{
		cfg:     cfg,
		status:  AgentStatusIdle,
		ctx:     ctx,
		cancel:  cancel,
	}, nil
}

func (a *Agent) Run(ctx context.Context) error {
	a.running = true

	if err := a.connectToMaster(); err != nil {
		fmt.Printf("[Agent] 连接Master失败: %v\n", err)
		fmt.Println("[Agent] 将在后台自动重试...")
		go a.reconnectLoop()
	}

	go a.heartbeatLoop()

	<-ctx.Done()
	a.Stop()
	return nil
}

func (a *Agent) Stop() {
	a.running = false
	a.cancel()

	a.taskMu.Lock()
	if a.taskCancel != nil {
		a.taskCancel()
	}
	a.taskMu.Unlock()

	if a.workerPool != nil {
		a.workerPool.Stop()
	}

	if a.masterConn != nil {
		a.masterConn.Close()
	}
}

func (a *Agent) connectToMaster() error {
	conn, err := net.DialTimeout("tcp", a.cfg.MasterAddr, 10*time.Second)
	if err != nil {
		return err
	}
	a.masterConn = conn

	sysInfo := map[string]string{
		"os":         runtime.GOOS,
		"arch":       runtime.GOARCH,
		"cpus":       fmt.Sprintf("%d", runtime.NumCPU()),
		"go_version": runtime.Version(),
	}

	req := RegisterRequest{
		AgentName:  a.cfg.Name,
		Workers:    a.cfg.WorkerCount,
		Version:    "2.0.0",
		SystemInfo: sysInfo,
	}

	if err := a.sendMessage(a.masterConn, MsgTypeRegister, "", req); err != nil {
		conn.Close()
		return err
	}

	reader := bufio.NewReader(conn)
	line, err := reader.ReadBytes('\n')
	if err != nil {
		conn.Close()
		return err
	}

	var msg Message
	if err := json.Unmarshal(line, &msg); err != nil {
		conn.Close()
		return err
	}

	if msg.Type != MsgTypeRegisterAck {
		conn.Close()
		return fmt.Errorf("expected register ack, got %d", msg.Type)
	}

	var resp RegisterResponse
	if err := msg.GetPayload(&resp); err != nil {
		conn.Close()
		return err
	}

	a.agentID = resp.AgentID
	fmt.Printf("[Agent] 已注册到Master, ID: %s\n", a.agentID)

	go a.handleMasterMessages(conn, reader)

	return nil
}

func (a *Agent) reconnectLoop() {
	backoff := 1 * time.Second
	maxBackoff := 60 * time.Second

	for a.running {
		select {
		case <-a.ctx.Done():
			return
		default:
		}

		if err := a.connectToMaster(); err == nil {
			return
		}

		fmt.Printf("[Agent] 重连Master失败，%v后重试...\n", backoff)
		time.Sleep(backoff)

		backoff *= 2
		if backoff > maxBackoff {
			backoff = maxBackoff
		}
	}
}

func (a *Agent) handleMasterMessages(conn net.Conn, reader *bufio.Reader) {
	defer conn.Close()

	for a.running {
		select {
		case <-a.ctx.Done():
			return
		default:
		}

		line, err := reader.ReadBytes('\n')
		if err != nil {
			fmt.Printf("[Agent] Master连接断开: %v\n", err)
			a.mu.Lock()
			a.masterConn = nil
			a.mu.Unlock()
			go a.reconnectLoop()
			return
		}

		var msg Message
		if err := json.Unmarshal(line, &msg); err != nil {
			continue
		}

		a.handleMasterMessage(conn, &msg)
	}
}

func (a *Agent) handleMasterMessage(conn net.Conn, msg *Message) {
	switch msg.Type {
	case MsgTypeShutdown:
		fmt.Println("[Agent] 收到Master关闭指令")
		a.Stop()

	case MsgTypeTaskAssign:
		var req TaskAssignRequest
		if err := msg.GetPayload(&req); err != nil {
			return
		}
		fmt.Printf("[Agent] 收到任务: %s, 目标: %s\n", req.Task.ID, req.Task.Target)
		go a.executeTask(req.Task)

	case MsgTypeConfigUpdate:
		var req ConfigUpdateRequest
		if err := msg.GetPayload(&req); err != nil {
			return
		}
		fmt.Println("[Agent] 收到配置更新")

	case MsgTypeStatusRequest:
		status := a.GetStatus()
		_ = a.sendMessage(conn, MsgTypeStatusResponse, msg.MessageID, status)

	default:
		fmt.Printf("[Agent] 收到未知消息类型: %d\n", msg.Type)
	}
}

func (a *Agent) executeTask(task *Task) {
	a.taskMu.Lock()
	if a.currentTask != nil {
		a.taskMu.Unlock()
		fmt.Printf("[Agent] 已有任务在运行: %s, 拒绝新任务: %s\n", a.currentTask.ID, task.ID)
		return
	}

	taskCtx, taskCancel := context.WithCancel(a.ctx)
	a.currentTask = task
	a.taskCancel = taskCancel
	a.taskMu.Unlock()

	a.mu.Lock()
	a.status = AgentStatusRunning
	a.mu.Unlock()

	startTime := time.Now()
	result := &TaskResult{
		TaskID:    task.ID,
		AgentID:   a.agentID,
		StartedAt: startTime,
	}

	defer func() {
		result.FinishedAt = time.Now()
		result.Duration = result.FinishedAt.Sub(startTime)
		a.sendTaskResult(result)

		a.taskMu.Lock()
		a.currentTask = nil
		a.taskCancel = nil
		a.taskMu.Unlock()

		a.mu.Lock()
		a.status = AgentStatusIdle
		a.mu.Unlock()
	}()

	proto, err := protocol.LoadProtocolDescriptionFromData(task.ProtocolData)
	if err != nil {
		result.Error = fmt.Sprintf("加载协议失败: %v", err)
		return
	}
	a.mu.Lock()
	a.totalTests = 0
	a.totalCrashes = 0
	a.totalAnomalies = 0
	a.mu.Unlock()

	gen := protocol.NewMessageGenerator(proto, a.cfg.BaseSeed)
	initialSeed, err := gen.Generate()
	if err != nil {
		result.Error = fmt.Sprintf("生成初始种子失败: %v", err)
		return
	}
	if len(task.SeedData) > 0 {
		initialSeed = task.SeedData
	}

	feedbackQueue, err := feedback.NewQueue(feedback.QueueConfig{
		QueueDir:    fmt.Sprintf("%s_%s", a.cfg.QueueDir, task.ID[:8]),
		InitialSeed: initialSeed,
		BaseSeed:    a.cfg.BaseSeed,
	})
	if err != nil {
		result.Error = fmt.Sprintf("创建反馈队列失败: %v", err)
		return
	}

	crashRecorder, err := crash.NewRecorder(crash.RecorderConfig{
		CrashDir:    fmt.Sprintf("%s_%s", a.cfg.CrashDir, task.ID[:8]),
		AnomalyDir:  fmt.Sprintf("%s_%s", a.cfg.AnomalyDir, task.ID[:8]),
		EnableDedup: true,
	})
	if err != nil {
		result.Error = fmt.Sprintf("创建崩溃记录器失败: %v", err)
		return
	}

	_ = mutator.NewMutator(proto, a.cfg.BaseSeed)

	var symbolicEngine *symbolic.Engine
	if task.EnableSymbolic {
		symbolicEngine = symbolic.NewEngine(symbolic.EngineConfig{
			Proto:    proto,
			BaseSeed: a.cfg.BaseSeed,
		})
		fmt.Println("[Agent] 符号执行引擎已启用")
	}

	var perturbConfig *networkpkg.PerturbationConfig
	if task.PerturbProfile != "" {
		profile, err := networkpkg.GetProfileByName(task.PerturbProfile)
		if err == nil {
			perturbConfig = profile.Config
			fmt.Printf("[Agent] 网络扰动已启用: %s\n", task.PerturbProfile)
		} else {
			fmt.Printf("[Agent] 警告: 未知的扰动配置文件: %s\n", task.PerturbProfile)
		}
	}

	workerPool, err := worker.NewWorkerPool(worker.WorkerPoolConfig{
		NumWorkers:     task.WorkerCount,
		Target:         task.Target,
		Timeout:        time.Duration(task.TimeoutSeconds) * time.Second,
		Proto:          proto,
		FeedbackQueue:  feedbackQueue,
		CrashRecorder:  crashRecorder,
		SymbolicEngine: symbolicEngine,
		PerturbConfig:  perturbConfig,
		BaseSeed:       a.cfg.BaseSeed,
		OnCrash: func(entry crash.CrashEntry) {
			a.reportCrash(task.ID, entry)
		},
	})
	if err != nil {
		result.Error = fmt.Sprintf("创建Worker池失败: %v", err)
		return
	}

	a.workerPool = workerPool
	workerPool.Start(taskCtx)

	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-taskCtx.Done():
			result.Completed = true
			return
		case <-ticker.C:
			_, totalTests, totalPaths := feedbackQueue.Stats()
			numCrashes, numAnomalies := crashRecorder.Stats()

			result.TestsExecuted = totalTests
			result.CrashesFound = numCrashes
			result.AnomaliesFound = numAnomalies
			result.PathsDiscovered = int(totalPaths)

			a.mu.Lock()
			a.totalTests = totalTests
			a.totalCrashes = numCrashes
			a.totalAnomalies = numAnomalies
			a.mu.Unlock()

			stats := workerPool.TotalStats()
			fmt.Printf("\r[Agent] 任务: %s  测试: %d  速率: %.1f/s  崩溃: %d  路径: %d",
				task.ID[:8],
				totalTests,
				float64(totalTests)/time.Since(startTime).Seconds(),
				numCrashes,
				totalPaths)
			_ = stats

			if task.MaxTests > 0 && totalTests >= task.MaxTests {
				result.Completed = true
				return
			}
		}
	}
}

func (a *Agent) sendTaskResult(result *TaskResult) {
	if a.masterConn == nil {
		return
	}

	req := TaskResultRequest{Result: result}
	if err := a.sendMessage(a.masterConn, MsgTypeTaskResult, "", req); err != nil {
		fmt.Printf("\n[Agent] 发送任务结果失败: %v\n", err)
	}
}

func (a *Agent) reportCrash(taskID string, entry crash.CrashEntry) {
	if a.masterConn == nil {
		return
	}

	report := &CrashReport{
		TaskID:     taskID,
		AgentID:    a.agentID,
		Timestamp:  entry.Timestamp,
		Input:      entry.Input,
		Output:     entry.Output,
		CrashType:  entry.CrashType,
		StackTrace: entry.StackTrace,
		Strategy:   entry.Strategy,
	}

	req := CrashReportRequest{Crash: report}
	if err := a.sendMessage(a.masterConn, MsgTypeCrashReport, "", req); err != nil {
		fmt.Printf("\n[Agent] 报告崩溃失败: %v\n", err)
	}
}

func (a *Agent) heartbeatLoop() {
	ticker := time.NewTicker(a.cfg.HeartbeatInterval)
	defer ticker.Stop()

	for a.running {
		select {
		case <-a.ctx.Done():
			return
		case <-ticker.C:
			a.sendHeartbeat()
		}
	}
}

func (a *Agent) sendHeartbeat() {
	if a.masterConn == nil {
		return
	}

	a.mu.Lock()
	status := a.status
	totalTests := a.totalTests
	totalCrashes := a.totalCrashes
	a.mu.Unlock()

	a.taskMu.Lock()
	currentTaskID := ""
	if a.currentTask != nil {
		currentTaskID = a.currentTask.ID
	}
	a.taskMu.Unlock()

	req := HeartbeatRequest{
		AgentID:       a.agentID,
		Status:        status,
		CurrentTaskID: currentTaskID,
		TestsExecuted: totalTests,
		CrashesFound:  totalCrashes,
	}

	if err := a.sendMessage(a.masterConn, MsgTypeHeartbeat, "", req); err != nil {
		fmt.Printf("\n[Agent] 发送心跳失败: %v\n", err)
	}
}

func (a *Agent) GetStatus() map[string]interface{} {
	a.mu.Lock()
	defer a.mu.Unlock()

	a.taskMu.Lock()
	currentTaskID := ""
	if a.currentTask != nil {
		currentTaskID = a.currentTask.ID
	}
	a.taskMu.Unlock()

	return map[string]interface{}{
		"agent_id":        a.agentID,
		"agent_name":      a.cfg.Name,
		"status":          statusToString(a.status),
		"workers":         a.cfg.WorkerCount,
		"current_task":    currentTaskID,
		"total_tests":     a.totalTests,
		"total_crashes":   a.totalCrashes,
		"total_anomalies": a.totalAnomalies,
	}
}

func statusToString(s AgentStatus) string {
	switch s {
	case AgentStatusIdle:
		return "idle"
	case AgentStatusRunning:
		return "running"
	case AgentStatusPaused:
		return "paused"
	case AgentStatusDisconnected:
		return "disconnected"
	case AgentStatusError:
		return "error"
	default:
		return "unknown"
	}
}

func (a *Agent) sendMessage(conn net.Conn, msgType MessageType, replyTo string, payload interface{}) error {
	msg, err := NewMessage(msgType, payload)
	if err != nil {
		return err
	}
	if replyTo != "" {
		msg.Headers["reply_to"] = replyTo
	}

	data, err := json.Marshal(msg)
	if err != nil {
		return err
	}
	data = append(data, '\n')

	_, err = conn.Write(data)
	return err
}
