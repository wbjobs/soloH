package distributed

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"time"
)

type MessageType int

const (
	MsgTypeRegister MessageType = iota
	MsgTypeRegisterAck
	MsgTypeTaskAssign
	MsgTypeTaskResult
	MsgTypeHeartbeat
	MsgTypeConfigUpdate
	MsgTypeCrashReport
	MsgTypeStatusRequest
	MsgTypeStatusResponse
	MsgTypeShutdown
	MsgTypeError
)

type AgentStatus int

const (
	AgentStatusIdle AgentStatus = iota
	AgentStatusRunning
	AgentStatusPaused
	AgentStatusDisconnected
	AgentStatusError
)

type AgentInfo struct {
	ID              string
	Name            string
	Address         string
	Status          AgentStatus
	Workers         int
	TotalTests      uint64
	TotalCrashes    int
	TotalAnomalies  int
	ConnectedAt     time.Time
	LastHeartbeat   time.Time
	Version         string
	SystemInfo      map[string]string
}

type Task struct {
	ID                string
	ProtocolData      []byte
	ProtocolHash      string
	Target            string
	TimeoutSeconds    int
	MaxTests          uint64
	WorkerCount       int
	SeedData          []byte
	PerturbProfile    string
	EnableSymbolic    bool
	CreatedAt         time.Time
	AssignedToAgent   string
}

type TaskResult struct {
	TaskID          string
	AgentID         string
	Completed       bool
	TestsExecuted   uint64
	CrashesFound    int
	AnomaliesFound  int
	PathsDiscovered int
	NewSeeds        [][]byte
	Error           string
	StartedAt       time.Time
	FinishedAt      time.Time
	Duration        time.Duration
}

type CrashReport struct {
	TaskID      string
	AgentID     string
	Timestamp   time.Time
	Input       []byte
	Output      []byte
	CrashType   string
	StackTrace  string
	Strategy    string
}

type Message struct {
	Type      MessageType       `json:"type"`
	MessageID string            `json:"message_id"`
	Timestamp time.Time         `json:"timestamp"`
	Payload   json.RawMessage   `json:"payload,omitempty"`
	Headers   map[string]string `json:"headers,omitempty"`
}

type RegisterRequest struct {
	AgentName  string            `json:"agent_name"`
	Workers    int               `json:"workers"`
	Version    string            `json:"version"`
	SystemInfo map[string]string `json:"system_info"`
}

type RegisterResponse struct {
	AgentID   string    `json:"agent_id"`
	MasterID  string    `json:"master_id"`
	ServerTime time.Time `json:"server_time"`
}

type TaskAssignRequest struct {
	Task *Task `json:"task"`
}

type TaskResultRequest struct {
	Result *TaskResult `json:"result"`
}

type HeartbeatRequest struct {
	AgentID         string   `json:"agent_id"`
	Status          AgentStatus `json:"status"`
	CurrentTaskID   string   `json:"current_task_id,omitempty"`
	TestsExecuted   uint64   `json:"tests_executed"`
	CrashesFound    int      `json:"crashes_found"`
	CPUUsage        float64  `json:"cpu_usage"`
	MemoryUsage     uint64   `json:"memory_usage"`
}

type ConfigUpdateRequest struct {
	Config interface{} `json:"config"`
}

type StatusRequest struct {
	DetailLevel int `json:"detail_level"`
}

type StatusResponse struct {
	Agents     []*AgentInfo `json:"agents"`
	TotalTests uint64       `json:"total_tests"`
	TotalCrashes int        `json:"total_crashes"`
	RunningTasks int        `json:"running_tasks"`
	QueuedTasks  int        `json:"queued_tasks"`
	Uptime      time.Duration `json:"uptime"`
}

type CrashReportRequest struct {
	Crash *CrashReport `json:"crash"`
}

type ErrorResponse struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

func NewMessage(msgType MessageType, payload interface{}) (*Message, error) {
	msg := &Message{
		Type:      msgType,
		MessageID: generateMessageID(),
		Timestamp: time.Now(),
		Headers:   make(map[string]string),
	}

	if payload != nil {
		payloadBytes, err := json.Marshal(payload)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal payload: %w", err)
		}
		msg.Payload = payloadBytes
	}

	return msg, nil
}

func (m *Message) GetPayload(target interface{}) error {
	if len(m.Payload) == 0 {
		return nil
	}
	return json.Unmarshal(m.Payload, target)
}

func generateMessageID() string {
	data := []byte(fmt.Sprintf("%d-%d", time.Now().UnixNano(), time.Now().UnixNano()/1000))
	hash := sha256.Sum256(data)
	return hex.EncodeToString(hash[:16])
}

func GenerateAgentID(name, address string) string {
	data := []byte(fmt.Sprintf("%s-%s-%d", name, address, time.Now().UnixNano()))
	hash := sha256.Sum256(data)
	return "agent-" + hex.EncodeToString(hash[:8])
}

func GenerateTaskID() string {
	data := []byte(fmt.Sprintf("task-%d", time.Now().UnixNano()))
	hash := sha256.Sum256(data)
	return "task-" + hex.EncodeToString(hash[:12])
}

func (m MessageType) String() string {
	switch m {
	case MsgTypeRegister:
		return "REGISTER"
	case MsgTypeRegisterAck:
		return "REGISTER_ACK"
	case MsgTypeTaskAssign:
		return "TASK_ASSIGN"
	case MsgTypeTaskResult:
		return "TASK_RESULT"
	case MsgTypeHeartbeat:
		return "HEARTBEAT"
	case MsgTypeConfigUpdate:
		return "CONFIG_UPDATE"
	case MsgTypeCrashReport:
		return "CRASH_REPORT"
	case MsgTypeStatusRequest:
		return "STATUS_REQUEST"
	case MsgTypeStatusResponse:
		return "STATUS_RESPONSE"
	case MsgTypeShutdown:
		return "SHUTDOWN"
	case MsgTypeError:
		return "ERROR"
	default:
		return fmt.Sprintf("UNKNOWN(%d)", m)
	}
}

func (s AgentStatus) String() string {
	switch s {
	case AgentStatusIdle:
		return "IDLE"
	case AgentStatusRunning:
		return "RUNNING"
	case AgentStatusPaused:
		return "PAUSED"
	case AgentStatusDisconnected:
		return "DISCONNECTED"
	case AgentStatusError:
		return "ERROR"
	default:
		return fmt.Sprintf("UNKNOWN(%d)", s)
	}
}
