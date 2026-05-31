package distributed

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"net"
	"sync"
	"time"
)

type MasterConfig struct {
	ListenAddr string
	AgentTimeout  time.Duration
	HeartbeatInterval time.Duration
	MaxTasks int
	MaxAgents   int
	QueueDir    string
	CrashDir    string
	AnomalyDir  string
}

type MasterStatus struct {
	ActiveAgents  int
	TotalAgents   int
	PendingTasks  int
	RunningTasks  int
	TotalTasks    int
	TotalCrashes  int
	TotalTests    uint64
	Uptime        time.Duration
}

type Master struct {
	cfg        MasterConfig
	agents     map[string]*AgentInfo
	agentsLock sync.RWMutex
	tasks      []*Task
	tasksLock  sync.Mutex
	taskQueue  chan *Task
	listener   net.Listener
	running    bool
	masterID   string
	startedAt  time.Time
	ctx        context.Context
	cancel     context.CancelFunc
	totalCrashes int
	totalTests   uint64

	OnAgentRegister   func(*AgentInfo)
	OnAgentDisconnect func(*AgentInfo)
	OnTaskComplete    func(*TaskResult)
	OnCrashReported   func(*CrashReport)
}

func NewMaster(cfg MasterConfig) (*Master, error) {
	if cfg.AgentTimeout == 0 {
		cfg.AgentTimeout = 60 * time.Second
	}
	if cfg.HeartbeatInterval == 0 {
		cfg.HeartbeatInterval = 5 * time.Second
	}
	if cfg.MaxTasks == 0 {
		cfg.MaxTasks = 100
	}
	if cfg.MaxAgents == 0 {
		cfg.MaxAgents = 50
	}
	if cfg.QueueDir == "" {
		cfg.QueueDir = "queue_master"
	}
	if cfg.CrashDir == "" {
		cfg.CrashDir = "crashes_master"
	}
	if cfg.AnomalyDir == "" {
		cfg.AnomalyDir = "anomalies_master"
	}

	ctx, cancel := context.WithCancel(context.Background())

	return &Master{
		cfg:        cfg,
		agents:     make(map[string]*AgentInfo),
		tasks:      make([]*Task, 0),
		taskQueue:  make(chan *Task, cfg.MaxTasks),
		masterID:   "master-" + GenerateAgentID("master", cfg.ListenAddr),
		ctx:        ctx,
		cancel:     cancel,
	}, nil
}

func (m *Master) Start(ctx context.Context) error {
	listener, err := net.Listen("tcp", m.cfg.ListenAddr)
	if err != nil {
		return fmt.Errorf("启动Master监听器失败: %w", err)
	}

	m.listener = listener
	m.running = true
	m.startedAt = time.Now()

	fmt.Printf("[Master] 监听地址: %s (ID: %s)\n", m.cfg.ListenAddr, m.masterID)

	go m.acceptConnections()
	go m.heartbeatCheckLoop()
	go m.taskDispatchLoop()

	<-ctx.Done()
	return nil
}

func (m *Master) Shutdown() {
	m.running = false
	m.cancel()
	if m.listener != nil {
		m.listener.Close()
	}

	m.agentsLock.Lock()
	defer m.agentsLock.Unlock()
	for _, agent := range m.agents {
		_ = m.sendShutdown(agent)
	}
}

func (m *Master) Stop() {
	m.Shutdown()
}

func (m *Master) acceptConnections() {
	for m.running {
		conn, err := m.listener.Accept()
		if err != nil {
			if !m.running {
				return
			}
			fmt.Printf("[Master] 接受连接错误: %v\n", err)
			continue
		}

		go m.handleAgentConnection(conn)
	}
}

func (m *Master) handleAgentConnection(conn net.Conn) {
	defer conn.Close()

	remoteAddr := conn.RemoteAddr().String()
	fmt.Printf("[Master] 新连接: %s\n", remoteAddr)

	reader := bufio.NewReader(conn)
	var agent *AgentInfo

	for m.running {
		select {
		case <-m.ctx.Done():
			return
		default:
		}

		line, err := reader.ReadBytes('\n')
		if err != nil {
			if agent != nil {
				m.handleAgentDisconnect(agent)
			}
			return
		}

		var msg Message
		if err := json.Unmarshal(line, &msg); err != nil {
			fmt.Printf("[Master] 解析消息失败 %s: %v\n", remoteAddr, err)
			continue
		}

		if agent == nil && msg.Type != MsgTypeRegister {
			_ = m.sendError(conn, msg.MessageID, 401, "需要先注册")
			continue
		}

		m.handleMessage(conn, &msg, agent)
	}
}

func (m *Master) handleMessage(conn net.Conn, msg *Message, agent *AgentInfo) {
	switch msg.Type {
	case MsgTypeRegister:
		m.handleRegister(conn, msg)

	case MsgTypeHeartbeat:
		m.handleHeartbeat(conn, msg)

	case MsgTypeTaskResult:
		m.handleTaskResult(conn, msg)

	case MsgTypeCrashReport:
		m.handleCrashReport(conn, msg)

	case MsgTypeStatusRequest:
		m.handleStatusRequest(conn, msg)

	case MsgTypeShutdown:
		if agent != nil {
			m.handleAgentDisconnect(agent)
		}
	}
}

func (m *Master) handleRegister(conn net.Conn, msg *Message) {
	var req RegisterRequest
	if err := msg.GetPayload(&req); err != nil {
		_ = m.sendError(conn, msg.MessageID, 400, fmt.Sprintf("无效的注册请求: %v", err))
		return
	}

	m.agentsLock.RLock()
	if len(m.agents) >= m.cfg.MaxAgents {
		m.agentsLock.RUnlock()
		_ = m.sendError(conn, msg.MessageID, 503, "Agent数量已达上限")
		return
	}
	m.agentsLock.RUnlock()

	agentID := GenerateAgentID(req.AgentName, conn.RemoteAddr().String())
	now := time.Now()

	agent := &AgentInfo{
		ID:            agentID,
		Name:          req.AgentName,
		Address:       conn.RemoteAddr().String(),
		Status:        AgentStatusIdle,
		Workers:       req.Workers,
		ConnectedAt:   now,
		LastHeartbeat: now,
		Version:       req.Version,
		SystemInfo:    req.SystemInfo,
	}

	m.agentsLock.Lock()
	m.agents[agentID] = agent
	m.agentsLock.Unlock()

	resp := RegisterResponse{
		AgentID:    agentID,
		MasterID:   m.masterID,
		ServerTime: now,
	}

	if err := m.sendMessage(conn, MsgTypeRegisterAck, msg.MessageID, resp); err != nil {
		fmt.Printf("[Master] 发送注册确认失败: %v\n", err)
		return
	}

	fmt.Printf("[Master] Agent注册成功: %s (%s, %d workers)\n", agentID, req.AgentName, req.Workers)

	if m.OnAgentRegister != nil {
		m.OnAgentRegister(agent)
	}
}

func (m *Master) handleHeartbeat(conn net.Conn, msg *Message) {
	var req HeartbeatRequest
	if err := msg.GetPayload(&req); err != nil {
		_ = m.sendError(conn, msg.MessageID, 400, fmt.Sprintf("无效的心跳: %v", err))
		return
	}

	m.agentsLock.Lock()
	agent, ok := m.agents[req.AgentID]
	if ok {
		agent.Status = req.Status
		agent.LastHeartbeat = time.Now()
		agent.TotalTests = req.TestsExecuted
		agent.TotalCrashes = req.CrashesFound
	}
	m.agentsLock.Unlock()

	if !ok {
		_ = m.sendError(conn, msg.MessageID, 404, "Agent未注册")
	}
}

func (m *Master) handleTaskResult(conn net.Conn, msg *Message) {
	var req TaskResultRequest
	if err := msg.GetPayload(&req); err != nil {
		_ = m.sendError(conn, msg.MessageID, 400, fmt.Sprintf("无效的任务结果: %v", err))
		return
	}

	m.tasksLock.Lock()
	for i, task := range m.tasks {
		if task.ID == req.Result.TaskID {
			m.tasks = append(m.tasks[:i], m.tasks[i+1:]...)
			break
		}
	}
	m.tasksLock.Unlock()

	m.agentsLock.RLock()
	agent := m.agents[req.Result.AgentID]
	if agent != nil {
		agent.Status = AgentStatusIdle
	}
	m.agentsLock.RUnlock()

	m.totalCrashes += req.Result.CrashesFound
	m.totalTests += req.Result.TestsExecuted

	if m.OnTaskComplete != nil {
		m.OnTaskComplete(req.Result)
	}

	fmt.Printf("\n[Master] 任务完成: %s, Agent: %s, 测试: %d, 崩溃: %d\n",
		req.Result.TaskID, req.Result.AgentID, req.Result.TestsExecuted, req.Result.CrashesFound)
}

func (m *Master) handleCrashReport(conn net.Conn, msg *Message) {
	var req CrashReportRequest
	if err := msg.GetPayload(&req); err != nil {
		_ = m.sendError(conn, msg.MessageID, 400, fmt.Sprintf("无效的崩溃报告: %v", err))
		return
	}

	m.totalCrashes++

	fmt.Printf("\n[Master] 收到崩溃报告: Agent=%s, Type=%s\n", req.Crash.AgentID, req.Crash.CrashType)

	if m.OnCrashReported != nil {
		m.OnCrashReported(req.Crash)
	}
}

func (m *Master) handleStatusRequest(conn net.Conn, msg *Message) {
	resp := m.GetStatus()
	_ = m.sendMessage(conn, MsgTypeStatusResponse, msg.MessageID, resp)
}

func (m *Master) handleAgentDisconnect(agent *AgentInfo) {
	m.agentsLock.Lock()
	defer m.agentsLock.Unlock()

	if agent != nil {
		agent.Status = AgentStatusDisconnected
		delete(m.agents, agent.ID)
		fmt.Printf("\n[Master] Agent断开: %s (%s)\n", agent.ID, agent.Name)

		if m.OnAgentDisconnect != nil {
			m.OnAgentDisconnect(agent)
		}
	}
}

func (m *Master) heartbeatCheckLoop() {
	ticker := time.NewTicker(m.cfg.HeartbeatInterval)
	defer ticker.Stop()

	for m.running {
		select {
		case <-m.ctx.Done():
			return
		case <-ticker.C:
			m.checkAgentTimeouts()
		}
	}
}

func (m *Master) checkAgentTimeouts() {
	m.agentsLock.Lock()
	defer m.agentsLock.Unlock()

	now := time.Now()
	for id, agent := range m.agents {
		if now.Sub(agent.LastHeartbeat) > m.cfg.AgentTimeout {
			agent.Status = AgentStatusDisconnected
			delete(m.agents, id)
			fmt.Printf("\n[Master] Agent超时: %s (%s)\n", id, agent.Name)

			if m.OnAgentDisconnect != nil {
				m.OnAgentDisconnect(agent)
			}
		}
	}
}

func (m *Master) taskDispatchLoop() {
	for m.running {
		select {
		case <-m.ctx.Done():
			return
		case task := <-m.taskQueue:
			m.dispatchTask(task)
		}
	}
}

func (m *Master) dispatchTask(task *Task) {
	m.agentsLock.RLock()
	var targetAgent *AgentInfo
	for _, agent := range m.agents {
		if agent.Status == AgentStatusIdle {
			targetAgent = agent
			break
		}
	}
	m.agentsLock.RUnlock()

	if targetAgent == nil {
		time.Sleep(100 * time.Millisecond)
		select {
		case m.taskQueue <- task:
		default:
			fmt.Printf("\n[Master] 任务队列已满，丢弃任务 %s\n", task.ID)
		}
		return
	}

	m.agentsLock.Lock()
	targetAgent.Status = AgentStatusRunning
	m.agentsLock.Unlock()

	task.AssignedToAgent = targetAgent.ID

	conn, err := net.DialTimeout("tcp", targetAgent.Address, 5*time.Second)
	if err != nil {
		fmt.Printf("\n[Master] 连接Agent %s 失败: %v\n", targetAgent.ID, err)
		m.agentsLock.Lock()
		targetAgent.Status = AgentStatusIdle
		m.agentsLock.Unlock()
		select {
		case m.taskQueue <- task:
		default:
		}
		return
	}
	defer conn.Close()

	req := TaskAssignRequest{Task: task}
	if err := m.sendMessage(conn, MsgTypeTaskAssign, "", req); err != nil {
		fmt.Printf("\n[Master] 发送任务到Agent %s 失败: %v\n", targetAgent.ID, err)
		m.agentsLock.Lock()
		targetAgent.Status = AgentStatusIdle
		m.agentsLock.Unlock()
		return
	}

	m.tasksLock.Lock()
	m.tasks = append(m.tasks, task)
	m.tasksLock.Unlock()

	fmt.Printf("\n[Master] 任务已分发: %s -> %s\n", task.ID, targetAgent.ID)
}

func (m *Master) SubmitTask(task *Task) error {
	if task.ID == "" {
		task.ID = GenerateTaskID()
	}
	task.CreatedAt = time.Now()

	select {
	case m.taskQueue <- task:
		return nil
	default:
		return fmt.Errorf("任务队列已满")
	}
}

func (m *Master) GetStatus() *MasterStatus {
	m.agentsLock.RLock()
	defer m.agentsLock.RUnlock()

	activeAgents := 0
	totalAgents := len(m.agents)
	var totalTests uint64
	var totalCrashes int
	for _, agent := range m.agents {
		if agent.Status == AgentStatusRunning || agent.Status == AgentStatusIdle {
			activeAgents++
		}
		totalTests += agent.TotalTests
		totalCrashes += agent.TotalCrashes
	}

	m.tasksLock.Lock()
	runningTasks := len(m.tasks)
	queuedTasks := len(m.taskQueue)
	m.tasksLock.Unlock()

	return &MasterStatus{
		ActiveAgents:  activeAgents,
		TotalAgents:   totalAgents,
		PendingTasks:  queuedTasks,
		RunningTasks:  runningTasks,
		TotalTasks:    runningTasks + queuedTasks,
		TotalCrashes:  totalCrashes + m.totalCrashes,
		TotalTests:    totalTests + m.totalTests,
		Uptime:        time.Since(m.startedAt),
	}
}

func (m *Master) sendMessage(conn net.Conn, msgType MessageType, replyTo string, payload interface{}) error {
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

func (m *Master) sendError(conn net.Conn, replyTo string, code int, message string) error {
	resp := ErrorResponse{Code: code, Message: message}
	return m.sendMessage(conn, MsgTypeError, replyTo, resp)
}

func (m *Master) sendShutdown(agent *AgentInfo) error {
	conn, err := net.DialTimeout("tcp", agent.Address, 2*time.Second)
	if err != nil {
		return err
	}
	defer conn.Close()

	return m.sendMessage(conn, MsgTypeShutdown, "", nil)
}
