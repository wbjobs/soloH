package jira

import (
	"bytes"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"tcp-fuzzer/internal/crash"
)

type Config struct {
	BaseURL   string
	Username  string
	APIToken  string
	ProjectKey string
	IssueType  string
	Component  string
	Assignee   string
	Labels    []string
}

type Client struct {
	cfg    Config
	client *http.Client
}

type CreateIssueRequest struct {
	Fields CreateIssueFields `json:"fields"`
}

type CreateIssueFields struct {
	Project   ProjectField   `json:"project"`
	Summary   string         `json:"summary"`
	Description string       `json:"description"`
	Issuetype IssueTypeField `json:"issuetype"`
	Components []ComponentField `json:"components,omitempty"`
	Assignee  *AssigneeField `json:"assignee,omitempty"`
	Labels    []string       `json:"labels,omitempty"`
	Priority  *PriorityField `json:"priority,omitempty"`
}

type ProjectField struct {
	Key string `json:"key"`
}

type IssueTypeField struct {
	Name string `json:"name"`
}

type ComponentField struct {
	Name string `json:"name"`
}

type AssigneeField struct {
	Name string `json:"name"`
}

type PriorityField struct {
	Name string `json:"name"`
}

type CreateIssueResponse struct {
	ID   string `json:"id"`
	Key  string `json:"key"`
	Self string `json:"self"`
}

type ErrorResponse struct {
	ErrorMessages []string          `json:"errorMessages"`
	Errors        map[string]string `json:"errors"`
}

type SearchResponse struct {
	Expand     string  `json:"expand"`
	StartAt    int     `json:"startAt"`
	MaxResults int     `json:"maxResults"`
	Total      int     `json:"total"`
	Issues     []Issue `json:"issues"`
}

type Issue struct {
	ID     string   `json:"id"`
	Key    string   `json:"key"`
	Self   string   `json:"self"`
	Fields struct {
		Summary string `json:"summary"`
		Status  struct {
			Name string `json:"name"`
		} `json:"status"`
	} `json:"fields"`
}

func NewClient(cfg Config) (*Client, error) {
	if cfg.BaseURL == "" {
		return nil, fmt.Errorf("JIRA base URL is required")
	}
	if cfg.Username == "" {
		return nil, fmt.Errorf("JIRA username is required")
	}
	if cfg.APIToken == "" {
		return nil, fmt.Errorf("JIRA API token is required")
	}
	if cfg.ProjectKey == "" {
		return nil, fmt.Errorf("JIRA project key is required")
	}
	if cfg.IssueType == "" {
		cfg.IssueType = "Bug"
	}

	return &Client{
		cfg: cfg,
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
	}, nil
}

func (c *Client) CreateBugFromCrash(crashEntry crash.CrashEntry) (string, error) {
	existingKey, err := c.findExistingCrashIssue(crashEntry)
	if err != nil {
		return "", fmt.Errorf("failed to search for existing issues: %w", err)
	}
	if existingKey != "" {
		if err := c.addComment(existingKey, crashEntry); err != nil {
			return "", fmt.Errorf("failed to add comment to existing issue: %w", err)
		}
		return existingKey, nil
	}

	summary := c.generateSummary(crashEntry)
	description := c.generateDescription(crashEntry)

	signatureHash := c.generateCrashSignatureHash(crashEntry)

	labels := make([]string, len(c.cfg.Labels))
	copy(labels, c.cfg.Labels)
	labels = append(labels, "fuzzing-crash")
	labels = append(labels, fmt.Sprintf("crash-sig-%s", signatureHash[:16]))

	req := CreateIssueRequest{
		Fields: CreateIssueFields{
			Project:     ProjectField{Key: c.cfg.ProjectKey},
			Summary:     summary,
			Description: description,
			Issuetype:   IssueTypeField{Name: c.cfg.IssueType},
			Labels:      labels,
		},
	}

	if c.cfg.Component != "" {
		req.Fields.Components = []ComponentField{{Name: c.cfg.Component}}
	}

	if c.cfg.Assignee != "" {
		req.Fields.Assignee = &AssigneeField{Name: c.cfg.Assignee}
	}

	priority := c.determinePriority(crashEntry)
	if priority != "" {
		req.Fields.Priority = &PriorityField{Name: priority}
	}

	resp, err := c.CreateIssue(req)
	if err != nil {
		return "", fmt.Errorf("failed to create JIRA issue: %w", err)
	}

	if len(crashEntry.Input) > 0 {
		if err := c.AddAttachment(resp.Key, "crash_input.bin", crashEntry.Input); err != nil {
			return resp.Key, fmt.Errorf("failed to add attachment: %w", err)
		}
	}

	return resp.Key, nil
}

func (c *Client) CreateIssue(req CreateIssueRequest) (*CreateIssueResponse, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	httpReq, err := http.NewRequest("POST", c.cfg.BaseURL+"/rest/api/2/issue", bytes.NewBuffer(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	c.setAuthHeader(httpReq)
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := c.client.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, c.parseErrorResponse(resp)
	}

	var createResp CreateIssueResponse
	if err := json.NewDecoder(resp.Body).Decode(&createResp); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return &createResp, nil
}

func (c *Client) generateSummary(crashEntry crash.CrashEntry) string {
	protoName := "Unknown"
	if len(crashEntry.Input) >= 4 {
		protoName = fmt.Sprintf("0x%x", crashEntry.Input[:4])
	}

	return fmt.Sprintf("[Fuzzing] %s crash detected - %s", crashEntry.CrashType, protoName)
}

func (c *Client) generateDescription(crashEntry crash.CrashEntry) string {
	desc := fmt.Sprintf(`h1. Fuzzing Crash Report

*Crash Type:* %s
*Detected At:* %s
*Worker ID:* %d
*Mutation Strategy:* %s

h2. Stack Trace
{code}
%s
{code}

h2. Input Data (%d bytes)
*Hex:* %s

{code:title=Hex Dump}
%s
{code}

h2. Output Data (%d bytes)
*Hex:* %s

{code:title=Hex Dump}
%s
{code}

h2. Environment
*Fuzzer:* tcp-fuzzer
*Protocol:* Custom TCP Protocol
*Target:* %s
*Detection Method:* Automated fuzzing

h3. Reproduction Steps
# Use the attached binary input to reproduce the crash
# Send the input to the target TCP service
# Observe the crash/exception behavior
`,
		crashEntry.CrashType,
		crashEntry.Timestamp.Format(time.RFC3339),
		crashEntry.WorkerID,
		crashEntry.Strategy,
		crashEntry.StackTrace,
		len(crashEntry.Input),
		crashEntry.InputHex,
		formatHexDump(crashEntry.Input),
		len(crashEntry.Output),
		crashEntry.OutputHex,
		formatHexDump(crashEntry.Output),
		"tcp://target:port",
	)

	return desc
}

func (c *Client) determinePriority(crashEntry crash.CrashEntry) string {
	switch crashEntry.CrashType {
	case "connection_reset", "remote_crash", "segmentation_fault":
		return "Critical"
	case "connection_failed", "connection_timeout":
		return "High"
	case "exception_message", "panic_message":
		return "High"
	case "error_message", "stack_trace":
		return "Medium"
	default:
		return "Medium"
	}
}

func (c *Client) setAuthHeader(req *http.Request) {
	auth := base64.StdEncoding.EncodeToString([]byte(c.cfg.Username + ":" + c.cfg.APIToken))
	req.Header.Set("Authorization", "Basic "+auth)
}

func (c *Client) parseErrorResponse(resp *http.Response) error {
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("JIRA API error (status %d): unable to read response", resp.StatusCode)
	}

	var errResp ErrorResponse
	if err := json.Unmarshal(body, &errResp); err != nil {
		return fmt.Errorf("JIRA API error (status %d): %s", resp.StatusCode, string(body))
	}

	errMsg := fmt.Sprintf("JIRA API error (status %d):", resp.StatusCode)
	for _, msg := range errResp.ErrorMessages {
		errMsg += fmt.Sprintf(" %s;", msg)
	}
	for field, msg := range errResp.Errors {
		errMsg += fmt.Sprintf(" %s: %s;", field, msg)
	}

	return fmt.Errorf(errMsg)
}

func (c *Client) SearchIssues(jql string) (*SearchResponse, error) {
	query := map[string]interface{}{
		"jql":        jql,
		"startAt":    0,
		"maxResults": 50,
		"fields":     []string{"summary", "status"},
	}

	body, err := json.Marshal(query)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	httpReq, err := http.NewRequest("POST", c.cfg.BaseURL+"/rest/api/2/search", bytes.NewBuffer(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	c.setAuthHeader(httpReq)
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := c.client.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, c.parseErrorResponse(resp)
	}

	var searchResp SearchResponse
	if err := json.NewDecoder(resp.Body).Decode(&searchResp); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return &searchResp, nil
}

func (c *Client) GetIssue(issueKey string) (*Issue, error) {
	httpReq, err := http.NewRequest("GET", c.cfg.BaseURL+"/rest/api/2/issue/"+issueKey, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	c.setAuthHeader(httpReq)

	resp, err := c.client.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, c.parseErrorResponse(resp)
	}

	var issue Issue
	if err := json.NewDecoder(resp.Body).Decode(&issue); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return &issue, nil
}

func (c *Client) AddComment(issueKey, comment string) error {
	body := map[string]interface{}{
		"body": comment,
	}

	jsonBody, err := json.Marshal(body)
	if err != nil {
		return fmt.Errorf("failed to marshal request: %w", err)
	}

	httpReq, err := http.NewRequest("POST",
		c.cfg.BaseURL+"/rest/api/2/issue/"+issueKey+"/comment",
		bytes.NewBuffer(jsonBody))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	c.setAuthHeader(httpReq)
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := c.client.Do(httpReq)
	if err != nil {
		return fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return c.parseErrorResponse(resp)
	}

	return nil
}

func (c *Client) AddAttachment(issueKey string, filename string, data []byte) error {
	boundary := "----WebKitFormBoundary" + fmt.Sprintf("%d", time.Now().UnixNano())

	var buf bytes.Buffer
	buf.WriteString("--" + boundary + "\r\n")
	buf.WriteString(fmt.Sprintf("Content-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\n", filename))
	buf.WriteString("Content-Type: application/octet-stream\r\n\r\n")
	buf.Write(data)
	buf.WriteString("\r\n--" + boundary + "--\r\n")

	httpReq, err := http.NewRequest("POST",
		c.cfg.BaseURL+"/rest/api/2/issue/"+issueKey+"/attachments",
		&buf)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	c.setAuthHeader(httpReq)
	httpReq.Header.Set("Content-Type", "multipart/form-data; boundary="+boundary)
	httpReq.Header.Set("X-Atlassian-Token", "no-check")

	resp, err := c.client.Do(httpReq)
	if err != nil {
		return fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return c.parseErrorResponse(resp)
	}

	return nil
}

func formatHexDump(data []byte) string {
	if len(data) == 0 {
		return "(empty)"
	}

	var result string
	for i := 0; i < len(data); i += 16 {
		end := len(data)
		if i+16 < len(data) {
			end = i + 16
		}
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

		result += fmt.Sprintf("%08x:  %-48s  %s\n", i, hexPart, asciiPart)

		if i > 512 {
			result += fmt.Sprintf("... (%d more bytes)\n", len(data)-i)
			break
		}
	}
	return result
}

func (c *Client) TestConnection() error {
	httpReq, err := http.NewRequest("GET", c.cfg.BaseURL+"/rest/api/2/myself", nil)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	c.setAuthHeader(httpReq)

	resp, err := c.client.Do(httpReq)
	if err != nil {
		return fmt.Errorf("connection test failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return c.parseErrorResponse(resp)
	}

	return nil
}

func (c *Client) generateCrashSignatureHash(crashEntry crash.CrashEntry) string {
	h := sha256.New()
	h.Write([]byte(crashEntry.CrashType))
	h.Write([]byte{0x00})
	h.Write([]byte(crashEntry.StackTrace))
	h.Write([]byte{0x00})
	inputHash := sha256.Sum256(crashEntry.Input)
	h.Write(inputHash[:16])
	return hex.EncodeToString(h.Sum(nil))
}

func (c *Client) findExistingCrashIssue(crashEntry crash.CrashEntry) (string, error) {
	sigHash := c.generateCrashSignatureHash(crashEntry)
	sigLabel := fmt.Sprintf("crash-sig-%s", sigHash[:16])

	jql := fmt.Sprintf(
		"project = %s AND labels = \"%s\" AND resolution = Unresolved ORDER BY created DESC",
		c.cfg.ProjectKey,
		sigLabel,
	)

	searchResp, err := c.SearchIssues(jql)
	if err != nil {
		return "", err
	}

	if searchResp.Total > 0 && len(searchResp.Issues) > 0 {
		return searchResp.Issues[0].Key, nil
	}

	return "", nil
}

func (c *Client) addComment(issueKey string, crashEntry crash.CrashEntry) error {
	comment := fmt.Sprintf(
		"h4. Additional crash occurrence detected\n\n"+
			"*Timestamp:* %s\n"+
			"*Worker ID:* %d\n"+
			"*Strategy:* %s\n"+
			"*Input Size:* %d bytes\n"+
			"*Output Size:* %d bytes\n\n"+
			"Input (first 64 bytes): {{%s}}\n\n"+
			"Output (first 64 bytes): {{%s}}",
		crashEntry.Timestamp.Format(time.RFC3339),
		crashEntry.WorkerID,
		crashEntry.Strategy,
		len(crashEntry.Input),
		len(crashEntry.Output),
		truncateHex(crashEntry.InputHex, 128),
		truncateHex(crashEntry.OutputHex, 128),
	)

	return c.AddComment(issueKey, comment)
}

func truncateHex(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen] + "..."
}
